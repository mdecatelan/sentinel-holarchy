"""Tests for Holon 0: Microbial Kinetics & Biomass Formulations."""

import pytest
from sentinel_holarchy.holon0_microbial.kinetics import Holon0Engine, MicrobialState
from sentinel_holarchy.holon0_microbial.biomass import HouseholdSubstrateFormulator
from sentinel_holarchy.holon0_microbial.protocol import BatchCycleRunner

def test_formulator_clamart_batch():
    formulator = HouseholdSubstrateFormulator(added_water_liters=1.5)
    formulator.load_default_clamart_batch()
    props = formulator.compute_mixture_properties()

    assert props["liquid_volume_L"] > 1.5
    assert props["carbohydrates_g_L"] > 10.0
    assert props["caco3_g_L"] > 5.0
    assert props["total_dry_mass_g"] > 100.0

def test_acidogenesis_vfa_production():
    engine = Holon0Engine()
    initial_state = MicrobialState(
        carbohydrates_g_l=30.0,
        vfa_g_l=1.0,
        caco3_g_l=10.0,
        biomass_acid_g_l=1.0,
        ph=6.5
    )

    # Step forward 10 hours without aeration
    state = initial_state
    for _ in range(10):
        state = engine.step(state, dt_h=1.0, aerated=False)

    # Carbohydrates must be consumed, VFA must increase
    assert state.carbohydrates_g_l < 30.0
    assert state.vfa_g_l > 1.0
    # pH must remain buffered above 5.0 thanks to CaCO3
    assert state.ph >= 5.0

def test_pha_accumulation_feast_famine():
    engine = Holon0Engine()
    # High VFA, low nitrogen, aerated
    initial_state = MicrobialState(
        carbohydrates_g_l=0.5,
        vfa_g_l=15.0,
        nitrogen_g_l=0.05,
        biomass_pha_active_g_l=2.0,
        pha_stored_g_l=0.1,
        dissolved_oxygen_mg_l=7.0
    )

    state = initial_state
    for _ in range(24):
        state = engine.step(state, dt_h=1.0, aerated=True)

    # PHA should accumulate and VFA should decrease
    assert state.pha_stored_g_l > 0.5
    assert state.pha_fraction > 0.15
    assert state.vfa_g_l < 15.0

def test_full_72h_protocol_runner():
    runner = BatchCycleRunner()
    results = runner.run_cycle(total_hours=72.0, dt_h=2.0)

    assert results["volume_L"] > 1.0
    assert results["final_pha_g"] > 0.0
    assert results["final_biostimulant_L"] > 0.5
    assert len(results["history"]) == 36
