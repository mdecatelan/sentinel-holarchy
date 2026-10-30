"""Tests for Holon 2: Ecocert UAB Certification Validator."""

import pytest
from sentinel_holarchy.holon2_workshop.ecocert_validator import (
    EcocertUABAuditor,
    LabAssayResults,
    ComplianceStatus
)
from sentinel_holarchy.holon2_workshop.batch_record import ProductionBatchRecord

def test_ecocert_audit_pass():
    auditor = EcocertUABAuditor()
    clean_assay = LabAssayResults(
        cadmium_mg_kg=0.2,
        lead_mg_kg=8.5,
        mercury_mg_kg=0.02,
        salmonella_detected_25g=False,
        ecoli_cfu_g=10,
        source_separated_biowaste_only=True,
        no_synthetic_solvents_used=True,
        no_gmo_used=True
    )
    report = auditor.audit_batch(clean_assay, "BATCH-001")
    assert report["status"] == ComplianceStatus.APPROVED.value
    assert report["uab_eligible"] is True
    assert report["clotaire_registration_ready"] is True
    assert report["violations_count"] == 0

def test_ecocert_audit_fail_heavy_metal():
    auditor = EcocertUABAuditor()
    toxic_assay = LabAssayResults(
        cadmium_mg_kg=2.5, # Over the 1.5 limit
        lead_mg_kg=10.0
    )
    report = auditor.audit_batch(toxic_assay, "BATCH-002")
    assert report["status"] == ComplianceStatus.REJECTED.value
    assert report["uab_eligible"] is False
    assert any("cadmium_mg_kg" in v for v in report["violations"])

def test_ecocert_audit_fail_salmonella():
    auditor = EcocertUABAuditor()
    contaminated_assay = LabAssayResults(salmonella_detected_25g=True)
    report = auditor.audit_batch(contaminated_assay, "BATCH-003")
    assert report["status"] == ComplianceStatus.REJECTED.value
    assert any("Salmonella" in v for v in report["violations"])

def test_production_batch_record():
    record = ProductionBatchRecord(
        batch_id="CLAMART-2026-B1",
        input_biomass_kg=1.2,
        yield_grade_a_pha_g=42.5,
        yield_grade_b_biostimulant_l=1.8,
        yield_grade_c_compost_g=320.0,
        raman_purity_score=0.91,
        ecocert_compliance_status="APPROVED_UAB"
    )
    d = record.to_dict()
    assert d["batch_id"] == "CLAMART-2026-B1"
    assert d["outputs"]["grade_a_pha_g"] == 42.5
    assert d["quality_assurance"]["raman_purity"] == 0.91
