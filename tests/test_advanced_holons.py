"""
Tests for Enriched Holarchic Logic:
- Holon 0: RK4 integration, undissociated HVFA inhibition, VFA speciation & Flory-Huggins PHBV copolymer model
- Holon 1: Anti-windup PID controller, Kolmogorov microscale shear model, Extended Kalman Filter (EKF) soft-sensor
- Holon 2: Solvent-free green PHA extraction & molecular weight scission tracking
- Holon 3: Savitzky-Golay smoothing, carbonyl 1724/1740 cm^-1 crystallinity deconvolution, SHA-256 hash chain & Bayesian posterior
- Holon 4 & 5: Clamart feedstock C/N blend optimizer & ISO-14040 LCA + 10-year NPV techno-economic model
"""

import os
import numpy as np
import pytest

from sentinel_holarchy.holon0_microbial import (
    Holon0Engine,
    MicrobialState,
    VFAProfile,
    PHBVCopolymerModel
)
from sentinel_holarchy.holon1_hardware import (
    AntiWindupPID,
    PIDGains,
    HydrodynamicShearModel,
    BioprocessEKFSoftSensor
)
from sentinel_holarchy.holon2_workshop import (
    GreenPHAExtractor,
    ExtractionProtocolConfig
)
from sentinel_holarchy.holon3_intelligence import (
    OpenRamanPipeline,
    KnowledgeLedgerManager
)
from sentinel_holarchy.holon4_territory import ClamartTerritoryModel
from sentinel_holarchy.holon5_paradigm import SocietalImpactCalculator


def test_phbv_copolymer_flory_huggins_properties():
    # Pure even-chain (acetate/butyrate) -> nearly pure PHB (high Tm ~ 177C, brittle)
    vfa_pure_even = VFAProfile(acetate_c2_g_l=8.0, propionate_c3_g_l=0.0, butyrate_c4_g_l=4.0, valerate_c5_g_l=0.0)
    props_phb = PHBVCopolymerModel.predict_from_vfa_profile(vfa_pure_even)
    assert props_phb.hv_molar_fraction_pct == 0.0
    assert props_phb.melting_temp_c == pytest.approx(177.0, abs=0.5)
    assert props_phb.crystallinity_pct >= 65.0

    # Mixed odd/even VFA -> PHBV copolymer with depressed melting point and high elongation
    vfa_mixed = VFAProfile(acetate_c2_g_l=4.0, propionate_c3_g_l=2.5, butyrate_c4_g_l=2.0, valerate_c5_g_l=1.2)
    props_phbv = PHBVCopolymerModel.predict_from_vfa_profile(vfa_mixed)
    assert props_phbv.hv_molar_fraction_pct > 15.0
    assert props_phbv.melting_temp_c < 155.0
    assert props_phbv.elongation_at_break_pct > 40.0
    assert props_phbv.piezoelectric_d33_pc_n > 10.0


def test_rk4_undissociated_hvfa_and_copolymer_state():
    engine = Holon0Engine()
    state = MicrobialState(carbohydrates_g_l=40.0, vfa_g_l=5.0, ph=5.2, odd_vfa_ratio=0.25)
    hvfa = engine.calculate_undissociated_vfa(state.vfa_g_l, state.ph)
    assert 0.5 < hvfa < 3.0

    next_state = engine.step(state, dt_h=0.5, aerated=False)
    props = next_state.predict_copolymer_properties()
    assert props.hv_molar_fraction_pct > 10.0


def test_anti_windup_pid_and_kolmogorov_shear():
    pid = AntiWindupPID(PIDGains(kp=4.0, ki=0.8, kd=0.2, output_min=0.0, output_max=100.0), setpoint=28.0)
    out_cold = pid.compute(measurement=20.0, dt=1.0)
    assert out_cold > 25.0

    # Above setpoint -> output saturates at 0.0 without windup
    for _ in range(10):
        out_hot = pid.compute(measurement=35.0, dt=1.0)
    assert out_hot == 0.0

    shear = HydrodynamicShearModel()
    gentle = shear.evaluate_regime(rpm=12.0)
    centrifuge = shear.evaluate_regime(rpm=750.0)
    assert gentle["floc_integrity_safe"] is True
    assert gentle["kolmogorov_scale_um"] > 100.0
    assert centrifuge["rcf_g_force"] > 120.0


def test_ekf_soft_sensor_convergence():
    ekf = BioprocessEKFSoftSensor(initial_vfa=2.0, initial_do=6.0)
    for _ in range(8):
        est = ekf.step(measured_ph=5.65, measured_orp_mv=-180.0, dt_h=0.25, aerated=False)
    assert est["estimated_vfa_g_l"] > 2.0
    assert est["vfa_uncertainty_std"] < 1.2


def test_green_pha_extractor_molecular_weight():
    extractor = GreenPHAExtractor(ExtractionProtocolConfig(lysis_temp_c=70.0, lysis_duration_min=25.0))
    res = extractor.simulate_extraction(total_biomass_g=100.0, intracellular_pha_fraction=0.72)
    assert res["recovered_pha_g"] > 55.0
    assert res["final_purity_pct"] > 88.0
    assert res["final_mw_kda"] > 300.0
    assert res["extrusion_grade_viable"] is True
    assert res["halogenated_solvents_used_ml"] == 0.0


def test_raman_savitzky_golay_and_crystallinity_deconvolution():
    pipeline = OpenRamanPipeline()
    wn, raw = pipeline.generate_synthetic_spectrum(pha_purity=0.90, crystallinity=0.68, noise_level=0.01)
    res = pipeline.analyze_sample(wn, raw, sample_id="SAMPLE-CRYST-01")
    assert res["purity_estimate_pct"] > 75.0
    assert 45.0 <= res["crystallinity_index_pct"] <= 85.0


def test_ledger_hash_chain_and_bayesian_posterior(tmp_path):
    ledger_path = os.path.join(tmp_path, "chained_ledger.json")
    mgr = KnowledgeLedgerManager(ledger_path)
    mgr.record_batch({"batch_id": "B1", "intrant_type": "organique", "final_GradeA": 38.0})
    mgr.record_batch({"batch_id": "B2", "intrant_type": "organique", "final_GradeA": 42.0})
    mgr.record_batch({"batch_id": "B3", "intrant_type": "organique", "final_GradeA": 40.0})

    integrity = mgr.verify_chain_integrity()
    assert integrity["valid"] is True
    assert integrity["checked_blocks"] == 3

    post = mgr.estimate_posterior_yield("organique", prior_mean_g=30.0, prior_std_g=8.0)
    assert 35.0 < post["posterior_mean_g"] < 42.0
    assert post["posterior_std_g"] < 8.0
    assert post["sample_size"] == 3


def test_clamart_blend_optimizer_and_npv():
    hub = ClamartTerritoryModel()
    blend = hub.optimize_feedstock_blend(target_cn_ratio=25.0, target_batch_wet_kg=15.0)
    assert blend["achieved_cn_ratio"] == pytest.approx(25.0, abs=0.5)
    assert sum(blend["recipe_kg"].values()) == pytest.approx(15.0, abs=0.1)

    lca = SocietalImpactCalculator()
    econ = lca.compute_techno_economic_npv()
    assert econ["npv_10y_eur"] > 15000.0
    assert econ["payback_period_months"] < 6.0
