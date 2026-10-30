"""
Holon 4: Bioregional Logistics & Mass Balance for the Clamart Micro-Hub.
Calculates collection radius, household coverage, and product distribution loops in Île-de-France.
"""

from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class ClamartTerritoryModel:
    clamart_population: int = 53000
    avg_biowaste_kg_person_year: float = 75.0
    num_participating_households: int = 120
    avg_persons_per_household: float = 2.3
    unit_reactor_capacity_L: float = 60.0
    number_of_decentralized_units: int = 4

    def compute_weekly_mass_balance(self) -> Dict[str, Any]:
        """Calculates weekly inputs and valorised outputs for the Clamart network."""
        persons = self.num_participating_households * self.avg_persons_per_household
        weekly_biowaste_kg = (persons * self.avg_biowaste_kg_person_year) / 52.0

        # Output conversion factors
        # 1 kg wet waste -> ~0.35 kg dry -> ~35g PHA + ~0.8 L biostimulant + ~0.25 kg compost
        weekly_pha_kg = (weekly_biowaste_kg * 0.035)
        weekly_biostimulant_L = (weekly_biowaste_kg * 0.78)
        weekly_compost_kg = (weekly_biowaste_kg * 0.28)

        # Revenue potential
        rev_pha = weekly_pha_kg * 12.0          # 12 €/kg
        rev_biostim = weekly_biostimulant_L * 4.5 # 4.5 €/L
        rev_compost = weekly_compost_kg * 0.5   # 0.5 €/kg
        total_weekly_rev = rev_pha + rev_biostim + rev_compost

        return {
            "participating_citizens": int(persons),
            "weekly_biowaste_collected_kg": round(weekly_biowaste_kg, 1),
            "weekly_outputs": {
                "pha_biopolymer_kg": round(weekly_pha_kg, 2),
                "uab_biostimulant_L": round(weekly_biostimulant_L, 1),
                "organic_compost_kg": round(weekly_compost_kg, 1)
            },
            "economic_value": {
                "pha_eur": round(rev_pha, 2),
                "biostimulant_eur": round(rev_biostim, 2),
                "compost_eur": round(rev_compost, 2),
                "total_weekly_revenue_eur": round(total_weekly_rev, 2),
                "annual_projected_revenue_eur": round(total_weekly_rev * 52.0, 2)
            },
            "collection_radius_meters": 450.0  # Ultra-short walking distance in Clamart
        }
