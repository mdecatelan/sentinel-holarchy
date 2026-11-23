"""
Comprehensive test suite for Digital Twin v3.0 — Bioeconomy Operating System:
  - 100% Elemental Carbon Mass Balance Closure & Winter Workshop Thermal Model
  - Nonlinear Model Predictive Control (NMPC) Self-Healing across 4 Crisis Scenarios
  - Multi-Stream B2B Arbitrage Optimizer & Petrochemical Substitution Ledger
  - 36-Month Self-Financing Clamart Network Emergence & Federated Bayesian Boost
  - EU Digital Product Passport (ESPR 2024/1781) & v3 REST API Endpoints
"""

from http import HTTPStatus
from pathlib import Path
import pytest

from sentinel_holarchy.holon0_microbial.multi_molecules import (
    BiorefineryBatchInput,
    MultiMoleculeEngine,
    RefiningProgramId,
)
from sentinel_holarchy.holon0_microbial.thermodynamics_flux import (
    CarbonAndThermalBalanceEngine,
    ThermalReactorConfig,
)
from sentinel_holarchy.holon1_hardware.nmpc_autopilot import (
    CrisisScenarioId,
    NMPCAutopilotEngine,
)
from sentinel_holarchy.holon3_intelligence.digital_twin import ClamartDigitalTwinService
from sentinel_holarchy.holon4_territory.bioeconomy_os import (
    BioeconomyArbitrageOptimizer,
    ClamartDailySupplyAndDemand,
    ClamartHolarchicNetworkSimulator,
)
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
def test_strict_carbon_closure_and_winter_insulation_roi(program_id: str) -> None:
    sim = MultiMoleculeEngine().simulate_batch(BiorefineryBatchInput(program_id=program_id))
    cb = CarbonAndThermalBalanceEngine.compute_carbon_mass_balance(sim)

    assert cb["mass_balance_closure_pct"] == pytest.approx(100.0, abs=0.05)
    assert cb["total_carbon_input_g"] > 50.0
    assert cb["carbon_sequestered_in_products_pct"] > 35.0

    # At 8 °C winter workshop temperature, 25mm cork/neoprene jacket must save >35% heating energy
    th_insulated = CarbonAndThermalBalanceEngine.simulate_thermal_profile(
        sim, ThermalReactorConfig(ambient_workshop_temp_c=8.0, insulated_jacket=True)
    )
    th_bare = CarbonAndThermalBalanceEngine.simulate_thermal_profile(
        sim, ThermalReactorConfig(ambient_workshop_temp_c=8.0, insulated_jacket=False)
    )
    assert th_insulated["thermal_heating_kwh"] < th_bare["thermal_heating_kwh"] * 0.65
    assert th_insulated["insulation_energy_saved_pct"] > 35.0


@pytest.mark.parametrize(
    "scenario_id",
    [
        CrisisScenarioId.CRISIS_ACID_OVERLOAD.value,
        CrisisScenarioId.CRISIS_AERATION_FOULING.value,
        CrisisScenarioId.CRISIS_WINTER_COLD_SNAP.value,
        CrisisScenarioId.CRISIS_HIGH_SALT_CANTEEN.value,
    ],
)
def test_nmpc_autopilot_outperforms_open_loop_across_all_crises(scenario_id: str) -> None:
    res = NMPCAutopilotEngine.simulate_resilience_comparison(scenario_id)
    cmp = res["comparison"]

    assert cmp["nmpc_autopilot_pha_g"] > cmp["open_loop_pha_g"] * 1.35
    assert cmp["value_saved_by_nmpc_eur"] > 1.0
    assert len(res["interventions_log"]) >= 1


def test_bioeconomy_arbitrage_optimizer_and_fossil_substitution() -> None:
    supply = ClamartDailySupplyAndDemand(
        bakery_bread_kg=16.0,
        cafe_coffee_grounds_kg=12.0,
        market_ripe_fruits_kg=15.0,
        household_canteen_peels_kg=28.0,
        active_drums_count=8,
    )
    plan = BioeconomyArbitrageOptimizer.optimize_cycle_dispatch(supply)

    assert plan["supply_summary"]["total_processed_per_cycle_kg"] > 20.0
    assert plan["cycle_economics"]["net_margin_per_73h_cycle_eur"] > 100.0
    assert plan["cycle_economics"]["bioeconomy_value_multiplier_x"] > 15.0
    assert plan["cycle_economics"]["annual_municipal_savings_eur"] > 200.0


def test_36_month_self_financing_clamart_emergence() -> None:
    em = ClamartHolarchicNetworkSimulator.simulate_36_month_emergence(
        initial_drums=1,
        reinvestment_rate=0.65,
        months=36,
        max_clamart_drums=48,
    )
    assert em["initial_seed_capital_eur"] == 3250.0
    f = em["final_month_36"]
    assert f["active_drums_clamart"] >= 15
    assert f["active_neighborhood_hubs"] >= 2
    assert f["annualized_runrate_net_eur"] > 25000.0
    assert f["federated_yield_gain_pct"] > 10.0
    assert len(em["clamart_districts"]) == 6


def test_v3_rest_api_and_eu_dpp_passport(tmp_path: Path) -> None:
    svc = ClamartDigitalTwinService(
        db_path=str(tmp_path / "v3_api.db"),
        ledger_path=str(tmp_path / "v3_ledger.json"),
    )

    st_boot, boot = dispatch_api_request("GET", "/api/v3/bootstrap", service=svc)
    assert st_boot == HTTPStatus.OK
    assert boot["version"] == "3.0.0-bioeconomy-os"
    assert len(boot["crisis_scenarios"]) == 4
    assert len(boot["clamart_districts"]) == 6

    st_sim, sim = dispatch_api_request(
        "POST",
        "/api/twin/simulate",
        {"hx711_waste_kg": 3.0, "ambient_workshop_temp_c": 12.0, "insulated_jacket": True},
        service=svc,
    )
    assert st_sim == HTTPStatus.OK
    assert sim["carbon_balance"]["mass_balance_closure_pct"] == pytest.approx(100.0, abs=0.05)

    st_coa, coa = dispatch_api_request(
        "POST",
        "/api/twin/certify",
        {"batch_id": sim["batch_id"]},
        service=svc,
    )
    assert st_coa == HTTPStatus.OK
    dpp = coa["eu_digital_product_passport"]
    assert dpp["espr_2024_1781_compliant"] is True
    assert dpp["en_16640_biogenic_carbon_pct"] == 100.0
    assert dpp["product_carbon_footprint_kg_co2e_per_kg"] < 0.0

    st_nmpc, nmpc = dispatch_api_request(
        "POST",
        "/api/v3/nmpc_resilience",
        {"scenario_id": "CRISIS_ACID_OVERLOAD"},
        service=svc,
    )
    assert st_nmpc == HTTPStatus.OK
    assert nmpc["comparison"]["value_saved_by_nmpc_eur"] > 0.0

    st_arb, arb = dispatch_api_request("POST", "/api/v3/arbitrage_dispatch", {"active_drums_count": 6}, service=svc)
    assert st_arb == HTTPStatus.OK
    assert len(arb["dispatch_plan"]) == 4

    st_em, em = dispatch_api_request("POST", "/api/v3/clamart_emergence", {"initial_drums": 1}, service=svc)
    assert st_em == HTTPStatus.OK
    assert em["final_month_36"]["active_drums_clamart"] >= 15
