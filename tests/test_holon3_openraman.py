"""Tests for Holon 3: OpenRAMAN 785nm Spectral Processing."""

import pytest
import numpy as np
from sentinel_holarchy.holon3_intelligence.openraman import OpenRamanPipeline

def test_raman_synthetic_spectrum_and_baseline_subtraction():
    pipeline = OpenRamanPipeline(laser_wavelength_nm=785.0)
    wavenumbers, raw_intensity = pipeline.generate_synthetic_spectrum(
        pha_purity=0.88,
        vfa_level=2.5,
        noise_level=0.01
    )

    assert len(wavenumbers) == 3648
    assert np.all(raw_intensity >= 0.0)

    clean_intensity = pipeline.subtract_baseline(wavenumbers, raw_intensity)
    assert np.max(clean_intensity) < np.max(raw_intensity)
    assert np.all(clean_intensity >= 0.0)

def test_raman_purity_estimation_and_coa():
    pipeline = OpenRamanPipeline()
    wavenumbers, raw_intensity = pipeline.generate_synthetic_spectrum(
        pha_purity=0.85,
        vfa_level=1.0,
        noise_level=0.01
    )

    analysis = pipeline.analyze_sample(wavenumbers, raw_intensity, sample_id="BATCH-TEST-PHA")
    assert analysis["sample_id"] == "BATCH-TEST-PHA"
    assert 70.0 <= analysis["purity_estimate_pct"] <= 99.0
    assert analysis["meets_grade_a_specs"] is True
    assert len(analysis["coa_sha256"]) == 64
