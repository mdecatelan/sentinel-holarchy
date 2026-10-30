"""
Holon 3: OpenRAMAN 785nm Spectroscopy Signal Processing & Automated CoA Generator.
Analyzes vibrational spectra (TCD1304 CCD), subtracts baseline, integrates ester peaks, and computes purity.
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
    """Processes 785nm Raman spectra to quantify PHA purity and VFA concentration."""

    # Key Raman fingerprint bands
    BAND_PHA_ESTER_CO = RamanBand(name="PHA Ester C=O", target_cm=1732.0, window_cm=20.0)
    BAND_CH_BENDING = RamanBand(name="C-H Bending (Ref)", target_cm=1453.0, window_cm=25.0)
    BAND_ACETATE_CC = RamanBand(name="Acetate C-C", target_cm=892.0, window_cm=18.0)

    def __init__(self, laser_wavelength_nm: float = 785.0):
        self.laser_wavelength_nm = laser_wavelength_nm

    def generate_synthetic_spectrum(
        self,
        pha_purity: float = 0.85,
        vfa_level: float = 2.0,
        noise_level: float = 0.03,
        num_points: int = 3648
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Generates realistic synthetic 785nm Raman spectrum across 400 - 3200 cm^-1."""
        wavenumbers = np.linspace(400.0, 3200.0, num_points)
        # Fluorescence baseline curve (exponential + polynomial background)
        baseline = 120.0 + 800.0 * np.exp(-wavenumbers / 1200.0) + 0.05 * wavenumbers

        # Peaks (Lorentzian profiles)
        def lorentzian(x, x0, gamma, amp):
            return amp * (gamma**2 / ((x - x0)**2 + gamma**2))

        intensity = baseline.copy()

        # PHA Ester peak ~ 1732 cm^-1
        intensity += lorentzian(wavenumbers, 1732.0, 12.0, 450.0 * pha_purity)

        # C-H reference peak ~ 1453 cm^-1
        intensity += lorentzian(wavenumbers, 1453.0, 15.0, 320.0)

        # Acetate peak ~ 892 cm^-1
        intensity += lorentzian(wavenumbers, 892.0, 10.0, 60.0 * vfa_level)

        # Add Gaussian noise
        noise = np.random.normal(0.0, noise_level * np.max(intensity), num_points)
        intensity += noise

        return wavenumbers, np.maximum(intensity, 0.0)

    def subtract_baseline(self, wavenumbers: np.ndarray, intensity: np.ndarray, deg: int = 4) -> np.ndarray:
        """Removes broad background fluorescence via iterative polynomial fit."""
        # Simple iterative polynomial baseline subtraction
        fit_intensity = intensity.copy()
        for _ in range(5):
            coeffs = np.polyfit(wavenumbers, fit_intensity, deg)
            baseline = np.polyval(coeffs, wavenumbers)
            fit_intensity = np.minimum(fit_intensity, baseline)

        corrected = intensity - baseline
        return np.maximum(corrected, 0.0)

    def integrate_band(self, wavenumbers: np.ndarray, intensity_clean: np.ndarray, band: RamanBand) -> float:
        """Integrates area under a designated Raman peak window."""
        mask = (wavenumbers >= band.target_cm - band.window_cm) & (wavenumbers <= band.target_cm + band.window_cm)
        if not np.any(mask):
            return 0.0
        return trapezoid_compat(intensity_clean[mask], wavenumbers[mask])

    def analyze_sample(
        self,
        wavenumbers: np.ndarray,
        raw_intensity: np.ndarray,
        sample_id: str = "SAMPLE-CLAMART-01"
    ) -> Dict[str, Any]:
        """Runs end-to-end spectrum evaluation, baseline removal, and purity assessment."""
        clean_intensity = self.subtract_baseline(wavenumbers, raw_intensity)

        area_pha = self.integrate_band(wavenumbers, clean_intensity, self.BAND_PHA_ESTER_CO)
        area_ref = self.integrate_band(wavenumbers, clean_intensity, self.BAND_CH_BENDING)
        area_acetate = self.integrate_band(wavenumbers, clean_intensity, self.BAND_ACETATE_CC)

        # Calibration ratio: at 100% pure PHA, (Area_1732 / Area_1453) = (12 * 450) / (15 * 320) = 1.125
        k_calib = 1.0 / 1.125
        ratio_raw = (area_pha / max(area_ref, 1e-4))
        purity_estimate = min(0.99, max(0.0, ratio_raw * k_calib))

        # Residual VFA proxy
        residual_vfa_g_l = round(area_acetate / 450.0, 2)

        # Generate cryptographic signature for Certificate of Analysis
        data_hash = hashlib.sha256(f"{sample_id}:{purity_estimate}:{residual_vfa_g_l}".encode()).hexdigest()

        return {
            "sample_id": sample_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "purity_estimate_pct": round(purity_estimate * 100.0, 1),
            "area_pha_ester_1732": round(area_pha, 1),
            "area_ch_ref_1453": round(area_ref, 1),
            "area_acetate_892": round(area_acetate, 1),
            "residual_vfa_g_l": residual_vfa_g_l,
            "meets_grade_a_specs": (purity_estimate >= 0.80),
            "coa_sha256": data_hash
        }
