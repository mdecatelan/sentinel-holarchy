"""Tests for Simulation, Knowledge Ledger, Territory, and Impact Metrics."""

import pytest
import os
from sentinel_holarchy.holon3_intelligence.knowledge_ledger import KnowledgeLedgerManager
from sentinel_holarchy.holon3_intelligence.simulator import DigitalTwinSimulator
from sentinel_holarchy.holon4_territory.clamart_hub import ClamartTerritoryModel
from sentinel_holarchy.holon5_paradigm.impact_metrics import SocietalImpactCalculator

def test_knowledge_ledger_experience_gain(tmp_path):
    ledger_file = os.path.join(tmp_path, "test_ledger.json")
    manager = KnowledgeLedgerManager(ledger_file)

    # Initial factor should be 1.00
    assert manager.calculate_experience_factor("organique") == 1.00

    # Add mock batch
    manager.record_batch({
        "batch_id": "BATCH-01",
        "intrant_type": "organique",
        "final_GradeA": 30.0
    })

    assert manager.calculate_experience_factor("organique") > 1.00

def test_digital_twin_simulation_step(tmp_path):
    ledger_file = os.path.join(tmp_path, "sim_ledger.json")
    sim = DigitalTwinSimulator(intrant_type="organique", ledger_file=ledger_file)

    for _ in range(72):
        telemetry = sim.step(dt_h=1.0)

    assert telemetry["time_h"] == 72.0
    assert telemetry["grade_a_pha_g"] > 0.0
    assert telemetry["grade_b_biostimulant_l"] > 0.0
    assert telemetry["progress_pct"] == 100.0

def test_clamart_territory_mass_balance():
    model = ClamartTerritoryModel(num_participating_households=100)
    balance = model.compute_weekly_mass_balance()

    assert balance["participating_citizens"] > 200
    assert balance["weekly_biowaste_collected_kg"] > 100.0
    assert balance["weekly_outputs"]["pha_biopolymer_kg"] > 3.0
    assert balance["economic_value"]["total_weekly_revenue_eur"] > 100.0

def test_societal_impact_lca():
    lca = SocietalImpactCalculator()
    impact = lca.compute_avoided_footprint(pha_produced_kg=50.0, biostimulant_produced_L=400.0)

    assert impact["pha_displaced_fossil_kg"] == 50.0
    assert impact["total_co2_eq_avoided_kg"] > 250.0
    assert impact["zero_persistent_microplastics"] is True
