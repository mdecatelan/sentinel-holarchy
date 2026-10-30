#!/usr/bin/env python3
"""
Sentinel-Holarchy: Multi-Lot Demonstration & Knowledge Accumulation.
Executes 3 sequential batches demonstrating:
1. Substrate Formulation (Household Waste)
2. Kinetic 72h Run (Acidogenesis + Feast/Famine PHA)
3. OpenRAMAN Spectral Verification & Automated CoA
4. Ecocert UAB Regulatory Audit
5. Federated Knowledge Ledger Experience Growth
"""

import sys
import os
import json
import time

# Ensure src is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from sentinel_holarchy.holon0_microbial.protocol import BatchCycleRunner
from sentinel_holarchy.holon1_hardware.controller import BioDrumStateMachine, DrumState
from sentinel_holarchy.holon2_workshop.ecocert_validator import EcocertUABAuditor, LabAssayResults
from sentinel_holarchy.holon2_workshop.batch_record import ProductionBatchRecord
from sentinel_holarchy.holon3_intelligence.openraman import OpenRamanPipeline
from sentinel_holarchy.holon3_intelligence.knowledge_ledger import KnowledgeLedgerManager
from sentinel_holarchy.holon4_territory.clamart_hub import ClamartTerritoryModel
from sentinel_holarchy.holon5_paradigm.impact_metrics import SocietalImpactCalculator

def main():
    print("=" * 75)
    print("      SENTINEL-HOLARCHY | DECENTRALIZED BIO-FOUNDRY MULTI-LOT RUN       ")
    print("=" * 75)

    ledger_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "knowledge_ledger.json"))
    ledger = KnowledgeLedgerManager(ledger_path)
    raman = OpenRamanPipeline()
    auditor = EcocertUABAuditor()
    territory = ClamartTerritoryModel()
    lca = SocietalImpactCalculator()

    for batch_num in range(1, 4):
        batch_id = f"CLAMART-2026-B{batch_num:02d}"
        exp_score = ledger.calculate_experience_factor("organique")
        print(f"\n>>> LAUNCHING BATCH #{batch_num:02d} ({batch_id}) | Experience Factor: {exp_score}x")

        # 1. Holon 0: Run 72h bio-conversion
        runner = BatchCycleRunner()
        results = runner.run_cycle(total_hours=72.0, dt_h=2.0)
        pha_yield_g = results["final_pha_g"] * exp_score
        biostim_L = results["final_biostimulant_L"]
        compost_g = results["final_compost_solid_g"]

        print(f"  [Holon 0] Fermentation 72h completed:")
        print(f"            - Grade A (PHA Polymer):   {pha_yield_g:.1f} g")
        print(f"            - Grade B (Biostimulant):  {biostim_L:.2f} L")
        print(f"            - Grade C (Solid Compost): {compost_g:.1f} g")

        # 2. Holon 3: OpenRAMAN 785nm analysis & CoA
        wn, raw_intensity = raman.generate_synthetic_spectrum(pha_purity=min(0.96, 0.82 + 0.04 * batch_num))
        coa = raman.analyze_sample(wn, raw_intensity, sample_id=batch_id)
        print(f"  [Holon 3] OpenRAMAN 785nm Spectral Assay:")
        print(f"            - PHA Purity Index: {coa['purity_estimate_pct']}% (Grade A Certified: {coa['meets_grade_a_specs']})")
        print(f"            - SHA-256 Verifiable CoA: {coa['coa_sha256'][:16]}...")

        # 3. Holon 2: Ecocert UAB Audit
        assay = LabAssayResults(cadmium_mg_kg=0.25, salmonella_detected_25g=False, ecoli_cfu_g=25)
        audit_rep = auditor.audit_batch(assay, batch_id)
        print(f"  [Holon 2] Ecocert/Clotaire Audit: {audit_rep['status']} (UAB Eligible: {audit_rep['uab_eligible']})")

        # 4. Save to Knowledge Ledger
        ledger_entry = {
            "batch_id": batch_id,
            "intrant_type": "organique",
            "t_total": 72.0,
            "adaptation_factor": exp_score,
            "final_GradeA": round(pha_yield_g, 2),
            "final_GradeB": round(biostim_L, 2),
            "final_GradeC": round(compost_g, 2),
            "raman_purity_pct": coa["purity_estimate_pct"],
            "ecocert_status": audit_rep["status"]
        }
        total_records = ledger.record_batch(ledger_entry)
        print(f"  [Knowledge Ledger] Batch recorded. Total lifetime batches: {total_records}")

    # Summary of Bioregional & Planetary impact
    print("\n" + "=" * 75)
    print("                     BIOREGIONAL & SOCIETAL IMPACT                      ")
    print("=" * 75)
    balance = territory.compute_weekly_mass_balance()
    impact = lca.compute_avoided_footprint(
        pha_produced_kg=balance["weekly_outputs"]["pha_biopolymer_kg"] * 52.0,
        biostimulant_produced_L=balance["weekly_outputs"]["uab_biostimulant_L"] * 52.0
    )
    print(f"  Territory Scope:     Clamart (120 participating households, 4 decentralized units)")
    print(f"  Annual Biowaste:     {balance['weekly_biowaste_collected_kg'] * 52.0:.0f} kg / year diverted from incineration")
    print(f"  Annual Projected Rev:{balance['economic_value']['annual_projected_revenue_eur']:.2f} € / year")
    print(f"  Annual CO2 Avoided:  {impact['total_co2_eq_avoided_kg']:.1f} kg CO2-eq")
    print(f"  Ocean Microplastics: Zero persistent microplastics (100% bio-assimilable PHA)")
    print("=" * 75 + "\n")

if __name__ == "__main__":
    main()
