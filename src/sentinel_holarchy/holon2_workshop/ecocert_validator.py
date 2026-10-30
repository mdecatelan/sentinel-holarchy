"""
Holon 2: Ecocert & UAB Regulatory Compliance Validator.
Audits biostimulant (Grade B) and solid compost (Grade C) against EU 2018/848, 2021/1165, and NF U 42-001.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any
from enum import Enum

class ComplianceStatus(str, Enum):
    APPROVED = "APPROVED_UAB"
    REJECTED = "REJECTED"
    WARNING = "WARNING_REQUIRES_ATTENTION"

@dataclass
class LabAssayResults:
    # Heavy Metals (mg/kg dry matter)
    cadmium_mg_kg: float = 0.4      # Limit <= 1.5
    lead_mg_kg: float = 12.0        # Limit <= 45.0
    mercury_mg_kg: float = 0.05     # Limit <= 0.4
    arsenic_mg_kg: float = 3.5      # Limit <= 10.0
    copper_mg_kg: float = 45.0      # Limit <= 200.0
    nickel_mg_kg: float = 18.0      # Limit <= 50.0

    # Microbiological Pathogens
    salmonella_detected_25g: bool = False  # Must be False (absence)
    ecoli_cfu_g: int = 15                  # Limit < 1000 CFU/g
    enterococci_cfu_g: int = 20            # Limit < 1000 CFU/g

    # Processing & Sourcing Criteria
    source_separated_biowaste_only: bool = True
    no_synthetic_solvents_used: bool = True
    no_gmo_used: bool = True
    no_pfas_or_synthetic_pesticides: bool = True

class EcocertUABAuditor:
    """Verifies and generates audit certification dossier for Clotaire database."""

    # Regulatory thresholds based on EU 2019/1009 (CMC 3 / CMC 5) & French NF U 42-001
    MAX_HEAVY_METALS = {
        "cadmium_mg_kg": 1.5,
        "lead_mg_kg": 45.0,
        "mercury_mg_kg": 0.4,
        "arsenic_mg_kg": 10.0,
        "copper_mg_kg": 200.0,
        "nickel_mg_kg": 50.0
    }

    def audit_batch(self, assay: LabAssayResults, batch_id: str) -> Dict[str, Any]:
        violations: List[str] = []
        warnings: List[str] = []

        # 1. Process & Sourcing Checks
        if not assay.source_separated_biowaste_only:
            violations.append("NON-COMPLIANCE: Feedstock is not 100% source-separated household biowaste (Art. 3, Reg UE 2021/1165).")
        if not assay.no_synthetic_solvents_used:
            violations.append("NON-COMPLIANCE: Extraction must only use physical means, steam, or pure water (Art. 6, Reg UE 2018/848).")
        if not assay.no_gmo_used:
            violations.append("NON-COMPLIANCE: GMO organisms or substrates are strictly prohibited in organic agriculture.")
        if not assay.no_pfas_or_synthetic_pesticides:
            violations.append("NON-COMPLIANCE: Detectable synthetic pesticides or PFAS residues above reporting threshold.")

        # 2. Pathogen Checks
        if assay.salmonella_detected_25g:
            violations.append("CRITICAL: Salmonella detected in 25g sample. Batch quarantined.")
        if assay.ecoli_cfu_g >= 1000:
            violations.append(f"CRITICAL: E. coli count ({assay.ecoli_cfu_g} CFU/g) exceeds legal ceiling of 1000 CFU/g.")

        # 3. Heavy Metals Thresholds
        for metal, limit in self.MAX_HEAVY_METALS.items():
            val = getattr(assay, metal, 0.0)
            if val > limit:
                violations.append(f"HEAVY METAL EXCEEDED: {metal} = {val} mg/kg (Max allowable: {limit} mg/kg).")
            elif val > 0.8 * limit:
                warnings.append(f"ELEVATED CONCENTRATION: {metal} is within 20% of legal ceiling.")

        status = ComplianceStatus.APPROVED if not violations else ComplianceStatus.REJECTED
        if status == ComplianceStatus.APPROVED and warnings:
            status = ComplianceStatus.WARNING

        return {
            "batch_id": batch_id,
            "status": status.value,
            "uab_eligible": (status != ComplianceStatus.REJECTED),
            "clotaire_registration_ready": (status == ComplianceStatus.APPROVED),
            "violations_count": len(violations),
            "violations": violations,
            "warnings": warnings,
            "applicable_regulations": [
                "Règlement (UE) 2018/848 (Production Biologique)",
                "Règlement d'Exécution (UE) 2021/1165 (Intrants autorisés UAB)",
                "Règlement Fertilisants (UE) 2019/1009 (CMC 3 / CMC 5)",
                "Norme Française NF U 42-001 (Engrais organiques et biostimulants)"
            ]
        }
