"""
Holon 2: Batch Manufacturing Record & Traceability Ledger.
Ensures GMP-style local traceability for decentralized bio-foundry units.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List

@dataclass
class ProductionBatchRecord:
    batch_id: str
    site_location: str = "Clamart-Workshop-01"
    start_time: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    operator_id: str = "Marc-Founder"
    input_biomass_kg: float = 1.0
    input_water_liters: float = 1.5
    calcium_carbonate_buffer_g: float = 40.0
    yield_grade_a_pha_g: float = 0.0
    yield_grade_b_biostimulant_l: float = 0.0
    yield_grade_c_compost_g: float = 0.0
    raman_purity_score: float = 0.0
    ecocert_compliance_status: str = "PENDING"
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "site_location": self.site_location,
            "start_time": self.start_time,
            "operator_id": self.operator_id,
            "inputs": {
                "biomass_kg": self.input_biomass_kg,
                "water_L": self.input_water_liters,
                "caco3_g": self.calcium_carbonate_buffer_g
            },
            "outputs": {
                "grade_a_pha_g": round(self.yield_grade_a_pha_g, 2),
                "grade_b_biostimulant_L": round(self.yield_grade_b_biostimulant_l, 2),
                "grade_c_compost_g": round(self.yield_grade_c_compost_g, 2)
            },
            "quality_assurance": {
                "raman_purity": round(self.raman_purity_score, 3),
                "ecocert_status": self.ecocert_compliance_status
            },
            "notes": self.notes
        }
