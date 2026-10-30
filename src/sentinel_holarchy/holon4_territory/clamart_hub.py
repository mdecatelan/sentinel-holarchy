"""
Holon 4: Bioregional Logistics, Mass Balance & Stoichiometric Feedstock Blend Optimizer
for the Clamart Micro-Hub (Hauts-de-Seine, Île-de-France).
"""

from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class UrbanWasteStream:
    source_name: str
    available_kg_week: float
    carbon_pct_dry: float
    nitrogen_pct_dry: float
    moisture_pct: float
    odd_vfa_potential: float  # Propionate/Valerate precursor propensity (0.0 - 1.0)


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

        weekly_pha_kg = weekly_biowaste_kg * 0.035
        weekly_biostimulant_L = weekly_biowaste_kg * 0.78
        weekly_compost_kg = weekly_biowaste_kg * 0.28

        rev_pha = weekly_pha_kg * 12.0
        rev_biostim = weekly_biostimulant_L * 4.5
        rev_compost = weekly_compost_kg * 0.5
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
            "collection_radius_meters": 450.0
        }

    def optimize_feedstock_blend(
        self,
        target_cn_ratio: float = 25.0,
        target_batch_wet_kg: float = 15.0
    ) -> Dict[str, Any]:
        """
        Optimizes the blend of Clamart local waste streams (bakery bread, vegetable peels,
        coffee grounds, eggshells) to hit the target C/N ratio for acidogenesis.
        """
        # Standard Clamart neighborhood streams:
        # 1. Stale bakery bread / starch (C/N ~ 38, low N)
        # 2. Household vegetable/fruit peels (C/N ~ 24, balanced)
        # 3. Spent coffee grounds / canteen legume residues (C/N ~ 14, rich N)
        # 4. Crushed eggshells (CaCO3 buffer, 4% w/w fixed)
        eggshell_kg = round(target_batch_wet_kg * 0.04, 2)
        organic_kg = target_batch_wet_kg - eggshell_kg

        # Solve 2-variable linear interpolation around vegetable peel base (50% of organic)
        peel_kg = organic_kg * 0.50
        rem_kg = organic_kg - peel_kg

        # Effective C/N of peels = 24.0; Bakery = 38.0; Coffee/Legumes = 14.0
        # We choose fraction alpha of Bakery vs (1-alpha) of Coffee/Legumes so weighted C/N == target_cn_ratio
        # 0.5 * 24 + 0.5 * (alpha * 38 + (1 - alpha) * 14) = target_cn_ratio
        req_secondary_cn = 2.0 * target_cn_ratio - 24.0
        alpha_bakery = (req_secondary_cn - 14.0) / (38.0 - 14.0)
        alpha_bakery = max(0.05, min(0.95, alpha_bakery))

        bakery_kg = round(rem_kg * alpha_bakery, 2)
        coffee_kg = round(rem_kg * (1.0 - alpha_bakery), 2)
        peel_kg = round(peel_kg, 2)

        achieved_cn = 0.5 * 24.0 + 0.5 * (alpha_bakery * 38.0 + (1.0 - alpha_bakery) * 14.0)
        odd_vfa_fraction = 0.5 * 0.25 + 0.5 * (alpha_bakery * 0.08 + (1.0 - alpha_bakery) * 0.38)

        return {
            "target_batch_wet_kg": target_batch_wet_kg,
            "recipe_kg": {
                "vegetable_fruit_peels_kg": peel_kg,
                "bakery_starch_bread_kg": bakery_kg,
                "coffee_grounds_canteen_kg": coffee_kg,
                "crushed_eggshells_caco3_kg": eggshell_kg
            },
            "achieved_cn_ratio": round(achieved_cn, 2),
            "predicted_odd_vfa_fraction": round(odd_vfa_fraction, 3),
            "caco3_buffer_dose_g_l": round((eggshell_kg * 1000.0) / (target_batch_wet_kg * 2.0), 1)
        }
