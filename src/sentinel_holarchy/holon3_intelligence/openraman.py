"""
Holon 3: OpenRAMAN 785nm Spectroscopy Signal Processing & Automated CoA Generator.
Analyzes vibrational spectra (TCD1304 CCD), performs Savitzky-Golay smoothing,
subtracts fluorescence baseline, deconvolutes crystalline/amorphous ester peaks (1724 vs 1740 cm^-1),
and computes PHA purity and crystallinity index.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple, Any
import numpy as np
import hashlib
from datetime import datetime, timezone


@dataclass
class RamanBand:
    name: str
    target_cm: float
    window_cm: float


def trapezoid_compat(y, x):
    if hasattr(np, "trapezoid"):
        return float(np.trapezoid(y, x))
    return float(np.trapz(y, x))


class OpenRamanPipeline:
    """Processes 785nm Raman spectra to quantify PHA purity, crystallinity, and VFA concentration."""

    # Key Raman fingerprint bands
    BAND_PHA_ESTER_CO = RamanBand(name="PHA Ester C=O Total", target_cm=1732.0, window_cm=22.0)
    BAND_PHA_CRYSTALLINE = RamanBand(name="PHA Crystalline C=O", target_cm=1724.0, window_cm=8.0)
    BAND_PHA_AMORPHOUS = RamanBand(name="PHA Amorphous C=O", target_cm=1740.0, window_cm=8.0)
    BAND_CH_BENDING = RamanBand(name="C-H Bending (Ref)", target_cm=1453.0, window_cm=25.0)
    BAND_ACETATE_CC = RamanBand(name="Acetate C-C", target_cm=892.0, window_cm=18.0)

    def __init__(self, laser_wavelength_nm: float = 785.0):
        self.laser_wavelength_nm = laser_wavelength_nm

    def generate_synthetic_spectrum(
        self,
        pha_purity: float = 0.85,
        crystallinity: float = 0.60,
        vfa_level: float = 2.0,
        noise_level: float = 0.03,
        num_points: int = 3648
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Generates realistic synthetic 785nm Raman spectrum across 400 - 3200 cm^-1."""
        wavenumbers = np.linspace(400.0, 3200.0, num_points)
        baseline = 120.0 + 800.0 * np.exp(-wavenumbers / 1200.0) + 0.05 * wavenumbers

        def lorentzian(x, x0, gamma, amp):
            return amp * (gamma**2 / ((x - x0)**2 + gamma**2))

        intensity = baseline.copy()

        # Split ester carbonyl intensity between crystalline (1724 cm^-1) and amorphous (1740 cm^-1)
        total_ester_amp = 450.0 * pha_purity
        intensity += lorentzian(wavenumbers, 1724.0, 7.5, total_ester_amp * crystallinity)
        intensity += lorentzian(wavenumbers, 1740.0, 9.5, total_ester_amp * (1.0 - crystallinity))
        # Also keep central envelope contribution at 1732 cm^-1 for composite band
        intensity += lorentzian(wavenumbers, 1732.0, 12.0, total_ester_amp * 0.45)

        # C-H reference peak ~ 1453 cm^-1
        intensity += lorentzian(wavenumbers, 1453.0, 15.0, 320.0)

        # Acetate peak ~ 892 cm^-1
        intensity += lorentzian(wavenumbers, 892.0, 10.0, 60.0 * vfa_level)

        noise = np.random.normal(0.0, noise_level * np.max(intensity), num_points)
        intensity += noise

        return wavenumbers, np.maximum(intensity, 0.0)

    def savitzky_golay_smooth(self, y: np.ndarray, window_size: int = 11, order: int = 3) -> np.ndarray:
        """Applies Savitzky-Golay polynomial smoothing filter using Vandermonde pseudoinverse."""
        if window_size % 2 == 0:
            window_size += 1
        half_w = window_size // 2
        x = np.arange(-half_w, half_w + 1, dtype=float)
        # Vandermonde matrix
        vander = np.vander(x, order + 1, increasing=True)
        coeffs = np.linalg.pinv(vander)[0]
        padded = np.pad(y, (half_w, half_w), mode="edge")
        return np.convolve(padded, coeffs[::-1], mode="valid")

    def subtract_baseline(self, wavenumbers: np.ndarray, intensity: np.ndarray, deg: int = 4) -> np.ndarray:
        """Removes broad background fluorescence via iterative polynomial suppression."""
        smoothed = self.savitzky_golay_smooth(intensity, window_size=15, order=3)
        fit_intensity = smoothed.copy()
        for _ in range(6):
            coeffs = np.polyfit(wavenumbers, fit_intensity, deg)
            baseline = np.polyval(coeffs, wavenumbers)
            fit_intensity = np.minimum(fit_intensity, baseline)

        corrected = smoothed - baseline
        return np.maximum(corrected, 0.0)

    def integrate_band(self, wavenumbers: np.ndarray, intensity_clean: np.ndarray, band: RamanBand) -> float:
        """Integrates area under a designated Raman peak window."""
        mask = (wavenumbers >= band.target_cm - band.window_cm) & (wavenumbers <= band.target_cm + band.window_cm)
        if not np.any(mask):
            return 0.0
        return trapezoid_compat(intensity_clean[mask], wavenumbers[mask])

    def deconvolute_carbonyl_crystallinity(
        self,
        wavenumbers: np.ndarray,
        intensity_clean: np.ndarray
    ) -> Dict[str, float]:
        """
        Deconvolutes the 1700-1760 cm^-1 ester carbonyl region into Crystalline (1724 cm^-1)
        and Amorphous (1740 cm^-1) sub-bands to determine polymer Crystallinity Index X_c.
        """
        a_cryst = self.integrate_band(wavenumbers, intensity_clean, self.BAND_PHA_CRYSTALLINE)
        a_amorph = self.integrate_band(wavenumbers, intensity_clean, self.BAND_PHA_AMORPHOUS)
        total = max(1e-4, a_cryst + a_amorph)
        xc_pct = (a_cryst / total) * 100.0
        return {
            "area_crystalline_1724": round(a_cryst, 1),
            "area_amorphous_1740": round(a_amorph, 1),
            "crystallinity_index_pct": round(min(85.0, max(10.0, xc_pct)), 1)
        }

    def analyze_sample(
        self,
        wavenumbers: np.ndarray,
        raw_intensity: np.ndarray,
        sample_id: str = "SAMPLE-CLAMART-01"
    ) -> Dict[str, Any]:
        """Runs end-to-end spectrum evaluation, baseline removal, deconvolution, and purity assessment."""
        clean_intensity = self.subtract_baseline(wavenumbers, raw_intensity)

        area_pha = self.integrate_band(wavenumbers, clean_intensity, self.BAND_PHA_ESTER_CO)
        area_ref = self.integrate_band(wavenumbers, clean_intensity, self.BAND_CH_BENDING)
        area_acetate = self.integrate_band(wavenumbers, clean_intensity, self.BAND_ACETATE_CC)

        deconv = self.deconvolute_carbonyl_crystallinity(wavenumbers, clean_intensity)

        k_calib = 1.0 / 1.125
        ratio_raw = (area_pha / max(area_ref, 1e-4))
        purity_estimate = min(0.99, max(0.0, ratio_raw * k_calib))

        residual_vfa_g_l = round(area_acetate / 450.0, 2)

        data_hash = hashlib.sha256(
            f"{sample_id}:{purity_estimate:.4f}:{deconv['crystallinity_index_pct']}:{residual_vfa_g_l}".encode()
        ).hexdigest()

        return {
            "sample_id": sample_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "purity_estimate_pct": round(purity_estimate * 100.0, 1),
            "crystallinity_index_pct": deconv["crystallinity_index_pct"],
            "area_pha_ester_1732": round(area_pha, 1),
            "area_ch_ref_1453": round(area_ref, 1),
            "area_acetate_892": round(area_acetate, 1),
            "residual_vfa_g_l": residual_vfa_g_l,
            "meets_grade_a_specs": (purity_estimate >= 0.75),
            "coa_sha256": data_hash
        }
