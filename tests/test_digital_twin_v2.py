"""
End-to-end unit & integration tests for Clamart Biorefinery Digital Twin v2.0:
  - 4 Multi-Molecule Refining Programs & NaCl Salt-Immune Delta_EC Stoichiometry
  - SQLite Persistence & Live ESP32 Telemetry Ingestion
  - Nelder-Mead Automated Parametric Calibration + Bayesian SHA-256 Ledger
  - OpenRAMAN Quality Proof & CoA Certification + REST API Dispatcher
"""

from http import HTTPStatus
from pathlib import Path
import pytest

from sentinel_holarchy.holon0_microbial.multi_molecules import (
    BiorefineryBatchInput,
    MultiMoleculeEngine,
    RefiningProgramId,
)
from sentinel_holarchy.holon3_intelligence.digital_twin import ClamartDigitalTwinService
from sentinel_holarchy.webapp.server import dispatch_api_request


@pytest.mark.parametrize(
    "program_id",
    [
        RefiningProgramId.PROG_1_PHBV_COSMETIC_PIEZO.value,
        RefiningProgramId.PROG_2_CHIRAL_R3HB_MONOMER.value,
        RefiningProgramId.PROG_3_CAPROIC_C6_OIL.value,
        RefiningProgramId.PROG_4_RHAMNOLIPIDS_COFFEE.value,
    ],
)
def test_all_four_clamart_programs_yield_and_economics(program_id: str) -> None:
    engine = MultiMoleculeEngine()
    inp = BiorefineryBatchInput(
        program_id=program_id,
        hx711_waste_kg=2.50,
        brown_starch_ratio=0.33,
        baseline_ec0_ms_cm=4.20,
        cartridge_caco3_g=250.0,
        coffee_grounds_fraction=0.30,
    )
    res = engine.simulate_batch(inp, dt_h=0.5)

    assert res["feedstock"]["compost_rule_compliant"] is True
    assert res["products"]["grade_a_mass_g"] > 5.0
    assert res["economics"]["gross_revenue_batch_eur"] > res["economics"]["opex_batch_eur"]
    assert res["economics"]["net_margin_batch_eur"] > 0.0
    assert res["lca"]["total_co2_eq_avoided_kg"] > 0.0
    assert res["cartridge_status"]["dissolved_this_batch_g"] > 0.0
    assert len(res["trajectory"]) >= 145


def test_delta_ec_stoichiometry_is_immune_to_kitchen_salt() -> None:
    """Proves that high kitchen NaCl (EC0 = 8.8 mS/cm) does not distort Delta_EC or Grade A yield."""
    engine = MultiMoleculeEngine()
    low_salt = engine.simulate_batch(
        BiorefineryBatchInput(baseline_ec0_ms_cm=2.40, hx711_waste_kg=2.20)
    )
    high_salt = engine.simulate_batch(
        BiorefineryBatchInput(baseline_ec0_ms_cm=8.80, hx711_waste_kg=2.20)
    )

    assert low_salt["products"]["grade_a_mass_g"] == high_salt["products"]["grade_a_mass_g"]
    for p_low, p_high in zip(low_salt["trajectory"], high_salt["trajectory"]):
        assert abs(p_low["delta_ec_ms"] - p_high["delta_ec_ms"]) < 1e-6
        assert abs((p_high["ec_ms"] - p_low["ec_ms"]) - (8.80 - 2.40)) < 0.02


def test_esp32_live_ingestion_and_phase_triggers(tmp_path: Path) -> None:
    svc = ClamartDigitalTwinService(
        db_path=str(tmp_path / "twin_test.db"),
        ledger_path=str(tmp_path / "ledger_test.json"),
    )
    sim = svc.run_simulation(BiorefineryBatchInput(baseline_ec0_ms_cm=4.0), batch_id="BATCH-ESP32-1")
    assert sim["batch_id"] == "BATCH-ESP32-1"

    # 1. Acidogenesis plateau packet (high EC above EC0 + low CO2 evolution)
    pkt1 = svc.ingest_esp32_packet(
        {
            "batch_id": "BATCH-ESP32-1",
            "t_h": 28.0,
            "ph": 5.85,
            "orp_mv": -215.0,
            "ec_ms_cm": 6.20,
            "co2_ml_min": 4.2,
            "do_mg_l": 0.15,
            "aerated": False,
        }
    )
    assert pkt1["delta_ec_ms_cm"] == pytest.approx(2.20, abs=0.02)
    assert pkt1["alerts"]["acidogenesis_plateau_reached"] is True
    assert pkt1["alerts"]["recommended_action"] == "BASCULER_ESSORAGE_650RPM_PUIS_AERATION"

    # 2. Aerobic DO Spike harvest trigger packet (DO >= 7.8 mg/L & flat slope after 4h+ aeration)
    svc.ingest_esp32_packet(
        {
            "batch_id": "BATCH-ESP32-1",
            "t_h": 64.0,
            "ph": 7.1,
            "orp_mv": 165.0,
            "ec_ms_cm": 4.3,
            "co2_ml_min": 3.5,
            "do_mg_l": 7.92,
            "aerated": True,
        }
    )
    pkt2 = svc.ingest_esp32_packet(
        {
            "batch_id": "BATCH-ESP32-1",
            "t_h": 64.5,
            "ph": 7.12,
            "orp_mv": 168.0,
            "ec_ms_cm": 4.28,
            "co2_ml_min": 3.2,
            "do_mg_l": 7.94,
            "aerated": True,
        }
    )
    assert pkt2["alerts"]["do_spike_harvest_ready"] is True
    assert pkt2["alerts"]["recommended_action"] == "DECLENCHER_LYSE_70C_RECOLTE"


def test_wetlab_auto_calibration_reduces_rmse_and_updates_ledger(tmp_path: Path) -> None:
    svc = ClamartDigitalTwinService(
        db_path=str(tmp_path / "cal_test.db"),
        ledger_path=str(tmp_path / "cal_ledger.json"),
    )
    inp = BiorefineryBatchInput(
        program_id=RefiningProgramId.PROG_1_PHBV_COSMETIC_PIEZO.value,
        hx711_waste_kg=2.50,
    )
    wetlab = svc.simulate_wetlab_noisy_batch(inp, seed=101)
    assert wetlab["rmse_uncalibrated_pct"] > 8.0

    cal = svc.calibrate_on_batch(wetlab["batch_id"])
    assert cal["rmse_after_pct"] < cal["rmse_before_pct"] * 0.45
    assert cal["rmse_after_pct"] < 4.5
    assert cal["ledger_integrity"]["valid"] is True
    assert cal["bayesian_posterior"]["sample_size"] >= 1


def test_rest_api_dispatcher_and_coa_sha256(tmp_path: Path) -> None:
    svc = ClamartDigitalTwinService(
        db_path=str(tmp_path / "api_test.db"),
        ledger_path=str(tmp_path / "api_ledger.json"),
    )

    st_prog, progs = dispatch_api_request("GET", "/api/twin/programs", service=svc)
    assert st_prog == HTTPStatus.OK
    assert len(progs["programs"]) == 4

    st_sim, sim = dispatch_api_request(
        "POST",
        "/api/twin/simulate",
        {"program_id": RefiningProgramId.PROG_2_CHIRAL_R3HB_MONOMER.value, "hx711_waste_kg": 3.0},
        service=svc,
    )
    assert st_sim == HTTPStatus.OK
    batch_id = sim["batch_id"]

    st_coa, coa = dispatch_api_request(
        "POST",
        "/api/twin/certify",
        {"batch_id": batch_id},
        service=svc,
    )
    assert st_coa == HTTPStatus.OK
    assert len(coa["coa_sha256"]) == 64
    assert coa["eu_2023_2055_microplastic_free"] is True
    assert len(coa["spectrum_plot"]["wavenumbers_cm1"]) > 50

    st_hist, hist = dispatch_api_request("GET", "/api/batches", service=svc)
    assert st_hist == HTTPStatus.OK
    assert any(b["batch_id"] == batch_id and b["status"] == "CERTIFIED_COA" for b in hist["batches"])
