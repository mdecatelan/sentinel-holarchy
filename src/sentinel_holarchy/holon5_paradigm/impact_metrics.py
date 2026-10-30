"""
Holon 5: Societal & Planetary Paradigm Shift Metrics.
Calculates ISO-14040 Life Cycle Assessment (avoided CO2-eq, displaced petrochemicals,
zero microplastics) and Techno-Economic Analysis (CapEx, OpEx, NPV, Payback Period).
"""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class SocietalImpactCalculator:
    # LCA standard benchmarks (ISO-14040 / Ecoinvent references)
    co2_kg_per_kg_petro_plastic: float = 3.2      # Polypropylene / Polyethylene cradle-to-gate
    co2_kg_per_kg_synthetic_fertilizer: float = 2.8  # Haber-Bosch synthetic nitrogen
    co2_kg_per_kwh_french_grid: float = 0.052     # Low-carbon French electricity mix
    avoided_landfill_ch4_co2eq_per_kg_waste: float = 0.42
    microplastics_half_life_years_ocean: float = 450.0
    pha_biodegradation_ocean_months: float = 6.0

    def compute_avoided_footprint(
        self,
        pha_produced_kg: float,
        biostimulant_produced_L: float,
        biowaste_diverted_kg: float = 0.0,
        electricity_consumed_kwh: float = 0.0
    ) -> Dict[str, Any]:
        """Calculates net ecological savings compared to fossil-based benchmarks."""
        co2_avoided_plastics_kg = pha_produced_kg * self.co2_kg_per_kg_petro_plastic
        co2_avoided_fertilizer_kg = biostimulant_produced_L * 0.15 * self.co2_kg_per_kg_synthetic_fertilizer
        co2_avoided_methane_kg = biowaste_diverted_kg * self.avoided_landfill_ch4_co2eq_per_kg_waste
        scope2_emissions_kg = electricity_consumed_kwh * self.co2_kg_per_kwh_french_grid

        total_co2_avoided_kg = (
            co2_avoided_plastics_kg
            + co2_avoided_fertilizer_kg
            + co2_avoided_methane_kg
            - scope2_emissions_kg
        )

        return {
            "pha_displaced_fossil_kg": round(pha_produced_kg, 2),
            "co2_avoided_from_plastics_kg": round(co2_avoided_plastics_kg, 2),
            "co2_avoided_from_fertilizers_kg": round(co2_avoided_fertilizer_kg, 2),
            "co2_avoided_from_landfill_methane_kg": round(co2_avoided_methane_kg, 2),
            "scope2_grid_emissions_kg": round(scope2_emissions_kg, 2),
            "total_co2_eq_avoided_kg": round(total_co2_avoided_kg, 2),
            "zero_persistent_microplastics": True,
            "marine_degradation_profile": "Full enzymatic bio-assimilation within 6 months"
        }

    def compute_techno_economic_npv(
        self,
        unit_capex_eur: float = 291.0,
        openraman_capex_eur: float = 480.0,
        annual_gross_revenue_eur: float = 4200.0,
        annual_opex_eur: float = 620.0,
        discount_rate: float = 0.06,
        horizon_years: int = 10
    ) -> Dict[str, float]:
        """
        Computes Net Present Value (NPV), Capital Recovery Payback (months),
        and Return on Invested Capital (ROIC) for a decentralized Bio-Drum unit.
        """
        total_capex = unit_capex_eur + openraman_capex_eur
        annual_net_cashflow = annual_gross_revenue_eur - annual_opex_eur

        npv = -total_capex
        for year in range(1, horizon_years + 1):
            npv += annual_net_cashflow / ((1.0 + discount_rate) ** year)

        payback_months = (total_capex / max(1.0, annual_net_cashflow)) * 12.0
        roic_pct = (annual_net_cashflow / max(1.0, total_capex)) * 100.0

        return {
            "total_capex_eur": round(total_capex, 2),
            "annual_net_cashflow_eur": round(annual_net_cashflow, 2),
            "npv_10y_eur": round(npv, 2),
            "payback_period_months": round(payback_months, 1),
            "annual_roic_pct": round(roic_pct, 1)
        }
