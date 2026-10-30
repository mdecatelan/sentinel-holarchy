"""
Holon 0: Biomass & Substrate Feedstock Formulator.
Calculates nutritional composition and buffering capacity for household and algae waste.
"""

from dataclasses import dataclass
from typing import Dict, List

@dataclass
class WasteIngredient:
    name: str
    weight_kg: float
    moisture_pct: float
    carbohydrates_pct_dry: float
    nitrogen_pct_dry: float
    calcium_carbonate_pct_dry: float
    inert_fibers_pct_dry: float

class HouseholdSubstrateFormulator:
    """Calculates batch feedstock composition for the Clamart prototype."""

    STANDARD_LIBRARY = {
        "vegetable_peels": WasteIngredient(
            name="Épluchures légumes/fruits",
            weight_kg=0.8,
            moisture_pct=85.0,
            carbohydrates_pct_dry=65.0,
            nitrogen_pct_dry=2.0,
            calcium_carbonate_pct_dry=0.0,
            inert_fibers_pct_dry=25.0
        ),
        "cooked_starches": WasteIngredient(
            name="Restes pâtes/riz/pain",
            weight_kg=0.2,
            moisture_pct=60.0,
            carbohydrates_pct_dry=85.0,
            nitrogen_pct_dry=2.5,
            calcium_carbonate_pct_dry=0.0,
            inert_fibers_pct_dry=5.0
        ),
        "eggshells": WasteIngredient(
            name="Coquilles d'œufs broyées",
            weight_kg=0.04,
            moisture_pct=2.0,
            carbohydrates_pct_dry=0.0,
            nitrogen_pct_dry=0.5,
            calcium_carbonate_pct_dry=94.0,
            inert_fibers_pct_dry=5.0
        )
    }

    def __init__(self, added_water_liters: float = 1.5):
        self.ingredients: List[WasteIngredient] = []
        self.added_water_liters = added_water_liters

    def add_ingredient(self, ingredient: WasteIngredient):
        self.ingredients.append(ingredient)

    def load_default_clamart_batch(self):
        """Loads default recipe for 3L pilot test (approx 1kg waste + 1.5L water)."""
        self.ingredients = [
            self.STANDARD_LIBRARY["vegetable_peels"],
            self.STANDARD_LIBRARY["cooked_starches"],
            self.STANDARD_LIBRARY["eggshells"]
        ]

    def compute_mixture_properties(self) -> Dict[str, float]:
        """Calculates initial concentrations in g/L for the fermentation liquid."""
        total_water_kg = self.added_water_liters
        total_dry_mass_kg = 0.0
        total_carbs_g = 0.0
        total_n_g = 0.0
        total_caco3_g = 0.0
        total_fibers_g = 0.0

        for ing in self.ingredients:
            wet_weight = ing.weight_kg
            dry_weight = wet_weight * (1.0 - ing.moisture_pct / 100.0)
            water_weight = wet_weight - dry_weight

            total_water_kg += water_weight
            total_dry_mass_kg += dry_weight

            total_carbs_g += dry_weight * (ing.carbohydrates_pct_dry / 100.0) * 1000.0
            total_n_g += dry_weight * (ing.nitrogen_pct_dry / 100.0) * 1000.0
            total_caco3_g += dry_weight * (ing.calcium_carbonate_pct_dry / 100.0) * 1000.0
            total_fibers_g += dry_weight * (ing.inert_fibers_pct_dry / 100.0) * 1000.0

        liquid_volume_liters = max(0.5, total_water_kg)

        return {
            "liquid_volume_L": round(liquid_volume_liters, 2),
            "carbohydrates_g_L": round(total_carbs_g / liquid_volume_liters, 2),
            "nitrogen_g_L": round(total_n_g / liquid_volume_liters, 2),
            "caco3_g_L": round(total_caco3_g / liquid_volume_liters, 2),
            "inert_fibers_g_L": round(total_fibers_g / liquid_volume_liters, 2),
            "total_dry_mass_g": round(total_dry_mass_kg * 1000.0, 1)
        }
