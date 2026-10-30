"""
Holon 5: Societal & Planetary Paradigm Shift Metrics.
Calculates net avoided CO2-eq, displaced petrochemical polymers, and microplastic prevention.
"""

from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class SocietalImpactCalculator:
    # LCA standard benchmarks
    co2_kg_per_kg_petro_plastic: float = 3.2   # Polypropylene / Polyethylene cradle-to-gate
    co2_kg_per_kg_synthetic_fertilizer: float = 2.8 # Haber-Bosch synthetic nitrogen
    microplastics_half_life_years_ocean: float = 450.0
    pha_biodegradation_ocean_months: float = 6.0

    def compute_avoided_footprint(self, pha_produced_kg: float, biostimulant_produced_L: float) -> Dict[str, Any]:
        """Calculates ecological savings compared to fossil-based benchmarks."""
        # 1 kg PHA produced locally displaces ~1 kg fossil plastics
        co2_avoided_plastics_kg = pha_produced_kg * self.co2_kg_per_kg_petro_plastic

        # 1 L biostimulant displaces ~0.15 kg synthetic N/P/K equivalent
        co2_avoided_fertilizer_kg = biostimulant_produced_L * 0.15 * self.co2_kg_per_kg_synthetic_fertilizer

        total_co2_avoided_kg = co2_avoided_plastics_kg + co2_avoided_fertilizer_kg

        return {
            "pha_displaced_fossil_kg": round(pha_produced_kg, 2),
            "co2_avoided_from_plastics_kg": round(co2_avoided_plastics_kg, 2),
            "co2_avoided_from_fertilizers_kg": round(co2_avoided_fertilizer_kg, 2),
            "total_co2_eq_avoided_kg": round(total_co2_avoided_kg, 2),
            "zero_persistent_microplastics": True,
            "marine_degradation_profile": "Full enzymatic bio-assimilation within 6 months"
        }
