"""
Holon 4 & 5+: Decentralized Bioeconomy Operating System (Clamart & Grand Paris).

Implements:
  1. `BioeconomyArbitrageOptimizer`: Matches heterogeneous daily urban biowaste streams
     (bakeries, cafés, street markets, canteens, households) against real B2B molecule orders
     across a fleet of Bio-Drums, maximizing net bioeconomic value + fossil substitution.
  2. `ClamartHolarchicNetworkSimulator`: Models the 6 neighborhoods of Clamart (53,000 residents),
     simulating 36-month self-financing fractal expansion (March 2027 -> March 2030), federated
     Bayesian network learning, municipal incineration tax savings (Syctom/ValoSeine), and
     direct comparison against centralized industrial megaplants.
"""

from dataclasses import dataclass
from typing import Dict, List, Any
import math

from sentinel_holarchy.holon0_microbial.multi_molecules import (
    BiorefineryBatchInput,
    MultiMoleculeEngine,
    RefiningProgramId,
)


CLAMART_DISTRICTS: List[Dict[str, Any]] = [
    {
        "hub_id": "HUB-TROSY",
        "name_fr": "Centre-Ville / Marché du Trosy",
        "x": 0.46,
        "y": 0.44,
        "dominant_stream_fr": "Fruits mûrs forains & pains artisanaux",
        "recommended_program": RefiningProgramId.PROG_3_CAPROIC_C6_OIL.value,
        "households_potential": 3800,
    },
    {
        "hub_id": "HUB-GARE",
        "name_fr": "Gare / Fort d'Issy-Vanves-Clamart (L15)",
        "x": 0.64,
        "y": 0.22,
        "dominant_stream_fr": "Marc de café brasseries & pelures d'agrumes",
        "recommended_program": RefiningProgramId.PROG_4_RHAMNOLIPIDS_COFFEE.value,
        "households_potential": 4600,
    },
    {
        "hub_id": "HUB-PERCY",
        "name_fr": "Percy-Schneider",
        "x": 0.30,
        "y": 0.28,
        "dominant_stream_fr": "Restauration collective & biodéchets triés",
        "recommended_program": RefiningProgramId.PROG_2_CHIRAL_R3HB_MONOMER.value,
        "households_potential": 3100,
    },
    {
        "hub_id": "HUB-JARDIN",
        "name_fr": "Jardin Parisien / Soleil Levant",
        "x": 0.26,
        "y": 0.64,
        "dominant_stream_fr": "Épluchures ménagères, cantines scolaires & serres",
        "recommended_program": RefiningProgramId.PROG_1_PHBV_COSMETIC_PIEZO.value,
        "households_potential": 3500,
    },
    {
        "hub_id": "HUB-PLAINE",
        "name_fr": "Petit-Clamart / Plaine Sud",
        "x": 0.70,
        "y": 0.76,
        "dominant_stream_fr": "Boulangeries, RIE entreprises & marc de café",
        "recommended_program": RefiningProgramId.PROG_1_PHBV_COSMETIC_PIEZO.value,
        "households_potential": 4200,
    },
    {
        "hub_id": "HUB-GALVENTS",
        "name_fr": "Galvents-Corby",
        "x": 0.54,
        "y": 0.35,
        "dominant_stream_fr": "Collecte citoyenne d'immeubles & commerces",
        "recommended_program": RefiningProgramId.PROG_4_RHAMNOLIPIDS_COFFEE.value,
        "households_potential": 2900,
    },
]


@dataclass
class ClamartDailySupplyAndDemand:
    # Available biowaste per 73h cycle window across participating local partners (kg)
    bakery_bread_kg: float = 12.0
    cafe_coffee_grounds_kg: float = 10.0
    market_ripe_fruits_kg: float = 14.0
    household_canteen_peels_kg: float = 24.0
    eggshells_oyster_shells_kg: float = 3.0

    # Active Bio-Drums available in the fleet (each drum processes up to 6.0 kg wet biowaste per 73h batch)
    active_drums_count: int = 6

    # Local B2B spot prices (EUR/kg)
    price_phbv_cosmetic_piezo_eur_kg: float = 185.0
    price_chiral_r3hb_eur_kg: float = 240.0
    price_caproic_c6_eur_kg: float = 28.0
    price_rhamnolipids_eur_kg: float = 64.0


class BioeconomyArbitrageOptimizer:
    """
    Allocates incoming urban waste streams and reactor drums across the 4 molecular programs
    to maximize net bioeconomic margin while tracking fossil petrochemical displacement.
    """

    @classmethod
    def optimize_cycle_dispatch(
        cls,
        state: ClamartDailySupplyAndDemand = None,
    ) -> Dict[str, Any]:
        s = state or ClamartDailySupplyAndDemand()
        engine = MultiMoleculeEngine()

        total_organic_kg = (
            s.bakery_bread_kg
            + s.cafe_coffee_grounds_kg
            + s.market_ripe_fruits_kg
            + s.household_canteen_peels_kg
        )
        drum_cap_kg = 5.0  # Optimal 60L drum wet waste charge (5 kg waste + 7.5 L water = 12.5 L working slurry)

        # Evaluate each of the 4 programs with its natural Clamart feedstock pairing
        candidates_cfg = [
            {
                "program_id": RefiningProgramId.PROG_2_CHIRAL_R3HB_MONOMER.value,
                "name_fr": "Monomère Chiral (R)-3HB (Pharma / Cétones)",
                "feed_recipe_fr": "35 % Pain boulangerie + 65 % Épluchures ménagères",
                "brown_ratio": 0.35,
                "coffee_frac": 0.15,
                "custom_price_eur_kg": s.price_chiral_r3hb_eur_kg,
                "max_demand_drums": max(1, int(math.ceil(s.active_drums_count * 0.25))),  # Niche pharma cap
                "available_pool_kg": s.bakery_bread_kg * 0.45 + s.household_canteen_peels_kg * 0.40,
            },
            {
                "program_id": RefiningProgramId.PROG_1_PHBV_COSMETIC_PIEZO.value,
                "name_fr": "PHBV Cosmétique Sans Microplastique & Grade Piézo",
                "feed_recipe_fr": "32 % Pain sec + 68 % Épluchures cantines/ménages",
                "brown_ratio": 0.32,
                "coffee_frac": 0.20,
                "custom_price_eur_kg": s.price_phbv_cosmetic_piezo_eur_kg,
                "max_demand_drums": max(1, int(math.ceil(s.active_drums_count * 0.45))),
                "available_pool_kg": s.bakery_bread_kg * 0.55 + s.household_canteen_peels_kg * 0.60,
            },
            {
                "program_id": RefiningProgramId.PROG_4_RHAMNOLIPIDS_COFFEE.value,
                "name_fr": "Rhamnolipides Tensioactifs & Polyphénols",
                "feed_recipe_fr": "18 % Pain + 55 % Marc de café bistrots + 27 % Pelures",
                "brown_ratio": 0.18,
                "coffee_frac": 0.65,
                "custom_price_eur_kg": s.price_rhamnolipids_eur_kg,
                "max_demand_drums": max(1, int(math.ceil(s.active_drums_count * 0.40))),
                "available_pool_kg": s.cafe_coffee_grounds_kg * 1.45,
            },
            {
                "program_id": RefiningProgramId.PROG_3_CAPROIC_C6_OIL.value,
                "name_fr": "Huile Caproïque C6/C8 Sans Huile de Palme",
                "feed_recipe_fr": "28 % Pain + 72 % Fruits mûrs du Marché du Trosy",
                "brown_ratio": 0.28,
                "coffee_frac": 0.10,
                "custom_price_eur_kg": s.price_caproic_c6_eur_kg,
                "max_demand_drums": s.active_drums_count,  # Bulk green chemistry market absorbs any volume
                "available_pool_kg": s.market_ripe_fruits_kg * 1.35,
            },
        ]

        evaluated = []
        for c in candidates_cfg:
            inp = BiorefineryBatchInput(
                program_id=c["program_id"],
                hx711_waste_kg=drum_cap_kg,
                brown_starch_ratio=c["brown_ratio"],
                baseline_ec0_ms_cm=4.20,
                cartridge_caco3_g=250.0,
                coffee_grounds_fraction=c["coffee_frac"],
            )
            sim = engine.simulate_batch(inp, dt_h=0.5)
            grade_a_g = float(sim["products"]["grade_a_mass_g"])
            grade_a_eur = (grade_a_g / 1000.0) * c["custom_price_eur_kg"]
            sec_eur = float(sim["products"]["secondary_co_products_eur"])
            opex_eur = float(sim["economics"]["opex_batch_eur"])
            net_eur_per_drum = grade_a_eur + sec_eur - opex_eur

            evaluated.append(
                {
                    **c,
                    "grade_a_g_per_drum": round(grade_a_g, 2),
                    "grade_b_l_per_drum": float(sim["products"]["grade_b_biostimulant_l"]),
                    "grade_c_kg_per_drum": float(sim["products"]["grade_c_substrate_kg"]),
                    "net_margin_eur_per_drum": round(net_eur_per_drum, 2),
                    "gross_rev_eur_per_drum": round(grade_a_eur + sec_eur, 2),
                    "opex_eur_per_drum": round(opex_eur, 2),
                    "co2_avoided_kg_per_drum": float(sim["lca"]["total_co2_eq_avoided_kg"]),
                    "margin_eur_per_hour": round(net_eur_per_drum / 73.0, 3),
                }
            )

        # Sort by highest net bioeconomic value per reactor-hour (greedy Pareto-optimal dispatch)
        evaluated.sort(key=lambda x: x["margin_eur_per_hour"], reverse=True)

        remaining_drums = max(1, s.active_drums_count)
        remaining_waste_kg = total_organic_kg
        allocations = []

        for ev in evaluated:
            if remaining_drums <= 0 or remaining_waste_kg < 1.5:
                alloc_drums = 0
            else:
                max_by_pool = max(1, int(round(ev["available_pool_kg"] / drum_cap_kg)))
                alloc_drums = min(remaining_drums, ev["max_demand_drums"], max_by_pool)
                if alloc_drums * drum_cap_kg > remaining_waste_kg:
                    alloc_drums = max(0, int(remaining_waste_kg // drum_cap_kg))

            remaining_drums -= alloc_drums
            waste_used_kg = round(alloc_drums * drum_cap_kg, 2)
            remaining_waste_kg = max(0.0, remaining_waste_kg - waste_used_kg)

            allocations.append(
                {
                    "program_id": ev["program_id"],
                    "name_fr": ev["name_fr"],
                    "feed_recipe_fr": ev["feed_recipe_fr"],
                    "drums_assigned": alloc_drums,
                    "waste_processed_kg": waste_used_kg,
                    "grade_a_total_g": round(alloc_drums * ev["grade_a_g_per_drum"], 1),
                    "net_margin_total_eur": round(alloc_drums * ev["net_margin_eur_per_drum"], 2),
                    "co2_avoided_total_kg": round(alloc_drums * ev["co2_avoided_kg_per_drum"], 2),
                    "unit_net_eur_per_drum": ev["net_margin_eur_per_drum"],
                }
            )

        # If drums remain and waste remains, assign remaining capacity to highest-ranked program
        if remaining_drums > 0 and remaining_waste_kg >= drum_cap_kg and allocations:
            extra = min(remaining_drums, int(remaining_waste_kg // drum_cap_kg))
            top = allocations[0]
            ev0 = evaluated[0]
            top["drums_assigned"] += extra
            top["waste_processed_kg"] = round(top["waste_processed_kg"] + extra * drum_cap_kg, 2)
            top["grade_a_total_g"] = round(top["grade_a_total_g"] + extra * ev0["grade_a_g_per_drum"], 1)
            top["net_margin_total_eur"] = round(
                top["net_margin_total_eur"] + extra * ev0["net_margin_eur_per_drum"], 2
            )
            top["co2_avoided_total_kg"] = round(
                top["co2_avoided_total_kg"] + extra * ev0["co2_avoided_kg_per_drum"], 2
            )

        tot_waste_processed = sum(a["waste_processed_kg"] for a in allocations)
        tot_net_eur_cycle = sum(a["net_margin_total_eur"] for a in allocations)
        tot_co2_cycle = sum(a["co2_avoided_total_kg"] for a in allocations)

        # Compare against naive mono-composting (selling raw compost at 0.08 EUR/kg)
        naive_compost_eur = round(tot_waste_processed * 0.35 * 0.08, 2)
        value_multiplier = round(tot_net_eur_cycle / max(0.25, naive_compost_eur), 1)

        # Municipal savings: avoided collection + ValoSeine incineration cost (~0.138 EUR/kg wet biowaste)
        avoided_municipal_tax_cycle_eur = round(tot_waste_processed * 0.138, 2)

        # Annualized metrics (100 cycles of 73h per year)
        cycles_yr = 100
        fossil_displaced = {
            "microplastics_pmma_pe_replaced_kg_yr": round(
                sum(
                    a["grade_a_total_g"]
                    for a in allocations
                    if a["program_id"] == RefiningProgramId.PROG_1_PHBV_COSMETIC_PIEZO.value
                )
                * cycles_yr
                / 1000.0,
                1,
            ),
            "palm_kernel_oil_c6_c8_replaced_kg_yr": round(
                sum(
                    a["grade_a_total_g"]
                    for a in allocations
                    if a["program_id"] == RefiningProgramId.PROG_3_CAPROIC_C6_OIL.value
                )
                * cycles_yr
                / 1000.0,
                1,
            ),
            "petro_surfactants_sles_replaced_kg_yr": round(
                sum(
                    a["grade_a_total_g"]
                    for a in allocations
                    if a["program_id"] == RefiningProgramId.PROG_4_RHAMNOLIPIDS_COFFEE.value
                )
                * cycles_yr
                / 1000.0,
                1,
            ),
            "chiral_pharma_building_blocks_kg_yr": round(
                sum(
                    a["grade_a_total_g"]
                    for a in allocations
                    if a["program_id"] == RefiningProgramId.PROG_2_CHIRAL_R3HB_MONOMER.value
                )
                * cycles_yr
                / 1000.0,
                1,
            ),
        }

        return {
            "supply_summary": {
                "total_available_biowaste_kg": round(total_organic_kg, 1),
                "total_processed_per_cycle_kg": round(tot_waste_processed, 1),
                "active_drums": s.active_drums_count,
                "eggshells_caco3_available_kg": s.eggshells_oyster_shells_kg,
            },
            "dispatch_plan": allocations,
            "cycle_economics": {
                "net_margin_per_73h_cycle_eur": round(tot_net_eur_cycle, 2),
                "naive_composting_value_eur": naive_compost_eur,
                "bioeconomy_value_multiplier_x": value_multiplier,
                "avoided_municipal_incineration_eur": avoided_municipal_tax_cycle_eur,
                "annual_fleet_net_cashflow_eur": round(tot_net_eur_cycle * cycles_yr, 0),
                "annual_municipal_savings_eur": round(avoided_municipal_tax_cycle_eur * cycles_yr, 0),
                "annual_co2_avoided_tonnes": round((tot_co2_cycle * cycles_yr) / 1000.0, 2),
            },
            "petrochemical_substitution_annual": fossil_displaced,
        }


class ClamartHolarchicNetworkSimulator:
    """
    Simulates 36-month self-financing fractal scaling across Clamart (March 2027 -> March 2030):
      - Starts with 1 single prototype drum + OpenRAMAN in March 2027 (initial seed = 3,250 EUR)
      - Reinvests a fraction of net bioeconomic cashflows into building new drums (1,100 EUR/drum)
        and neighborhood OpenRAMAN certification stations (1,250 EUR per 6 drums)
      - Quantifies Federated Bayesian Learning network effect across all connected drums.
    """

    @classmethod
    def simulate_36_month_emergence(
        cls,
        initial_drums: int = 1,
        reinvestment_rate: float = 0.65,
        months: int = 36,
        max_clamart_drums: int = 48,
    ) -> Dict[str, Any]:
        reinvest = min(0.95, max(0.0, reinvestment_rate))
        drums = max(1, initial_drums)
        openraman_stations = 1

        # Initial seed capital (March 2027 prototype + OpenRAMAN + 3m tiers-lieu)
        initial_seed_eur = 3250.0 + max(0, drums - 1) * 1100.0
        reinvestment_pool_eur = 0.0
        cumulative_founder_treasury_eur = 0.0
        cumulative_batches = 0
        cumulative_biowaste_tonnes = 0.0
        cumulative_co2_tonnes = 0.0
        cumulative_municipal_saved_eur = 0.0

        # Nominal 60L drum charge (10 kg biowaste + 15 L water = 25 L working volume):
        # ~68 EUR net margin/batch * 8.3 batches/month = ~565 EUR/month per drum before hub rent
        base_net_before_rent_per_drum_month = 565.0

        timeline: List[Dict[str, Any]] = []

        for m in range(1, months + 1):
            # Federated learning boost: shared SHA-256 ledger across drums improves conversion efficiency up to +22%
            federated_yield_multiplier = 1.0 + 0.22 * (1.0 - math.exp(-cumulative_batches / 280.0))
            uncertainty_std_pct = round(18.0 / math.sqrt(1.0 + cumulative_batches * 0.25), 2)

            batches_this_month = int(round(drums * 8.3))
            cumulative_batches += batches_this_month

            biowaste_kg_m = batches_this_month * 5.0
            cumulative_biowaste_tonnes += biowaste_kg_m / 1000.0
            cumulative_co2_tonnes += (batches_this_month * 5.2) / 1000.0
            cumulative_municipal_saved_eur += biowaste_kg_m * 0.138

            # Workshop space rent scales gently by neighborhood micro-hubs (1 hub hosts up to 8 drums)
            active_hubs = min(6, max(1, int(math.ceil(drums / 8.0))))
            monthly_hubs_rent_eur = active_hubs * 320.0

            gross_net_before_rent = drums * base_net_before_rent_per_drum_month * federated_yield_multiplier
            net_operating_cashflow_m = gross_net_before_rent - monthly_hubs_rent_eur

            if net_operating_cashflow_m > 0:
                reinvestment_pool_eur += net_operating_cashflow_m * reinvest
                cumulative_founder_treasury_eur += net_operating_cashflow_m * (1.0 - reinvest)
            else:
                cumulative_founder_treasury_eur += net_operating_cashflow_m

            # Self-financed replication: build new drums from cashflow without external debt!
            while reinvestment_pool_eur >= 1100.0 and drums < max_clamart_drums:
                # Every 8th drum requires an additional neighborhood OpenRAMAN station (1,250 EUR)
                needed_capex = 1100.0 + (1250.0 if (drums % 8 == 0) else 0.0)
                if reinvestment_pool_eur >= needed_capex:
                    reinvestment_pool_eur -= needed_capex
                    drums += 1
                    if drums % 8 == 1 and drums > 1:
                        openraman_stations += 1
                else:
                    break

            active_hubs = min(6, max(1, int(math.ceil(drums / 8.0))))
            timeline.append(
                {
                    "month": m,
                    "label": f"M+{m}",
                    "active_drums": drums,
                    "active_hubs": active_hubs,
                    "openraman_stations": openraman_stations,
                    "monthly_net_cashflow_eur": round(net_operating_cashflow_m, 0),
                    "cumulative_treasury_eur": round(cumulative_founder_treasury_eur + reinvestment_pool_eur, 0),
                    "federated_efficiency_boost_pct": round((federated_yield_multiplier - 1.0) * 100.0, 1),
                    "bayesian_uncertainty_pct": uncertainty_std_pct,
                    "cumulative_biowaste_tonnes": round(cumulative_biowaste_tonnes, 1),
                }
            )

        # Distribute final active drums across the 6 Clamart districts
        districts_status = []
        remaining = drums
        for idx, d in enumerate(CLAMART_DISTRICTS):
            if idx < min(6, int(math.ceil(drums / 8.0))):
                hub_drums = min(8, remaining) if idx < 5 else remaining
                remaining = max(0, remaining - hub_drums)
            else:
                hub_drums = 0
            districts_status.append(
                {
                    **d,
                    "active_drums": hub_drums,
                    "online": hub_drums > 0,
                    "annual_biowaste_tonnes": round(hub_drums * 100 * 5.0 / 1000.0, 1),
                }
            )

        final_m = timeline[-1]
        # Equivalent centralized industrial bioreactor plant comparison
        centralized_comparison = {
            "holarchic_initial_capital_eur": round(initial_seed_eur, 0),
            "centralized_factory_capex_eur": 4800000,
            "holarchic_permitting_months": 3,
            "centralized_icpe_permitting_months": 42,
            "diesel_collection_trucks_needed": 0,
            "single_point_of_failure": False,
        }

        return {
            "initial_seed_capital_eur": round(initial_seed_eur, 0),
            "reinvestment_rate_pct": round(reinvest * 100.0, 0),
            "final_month_36": {
                "active_drums_clamart": final_m["active_drums"],
                "active_neighborhood_hubs": final_m["active_hubs"],
                "openraman_stations": final_m["openraman_stations"],
                "monthly_net_cashflow_eur": final_m["monthly_net_cashflow_eur"],
                "annualized_runrate_net_eur": round(final_m["monthly_net_cashflow_eur"] * 12.0, 0),
                "cumulative_free_treasury_eur": final_m["cumulative_treasury_eur"],
                "cumulative_biowaste_diverted_tonnes": round(cumulative_biowaste_tonnes, 1),
                "cumulative_co2_avoided_tonnes": round(cumulative_co2_tonnes, 1),
                "cumulative_municipal_tax_saved_eur": round(cumulative_municipal_saved_eur, 0),
                "local_green_jobs_fte": round(final_m["active_drums"] / 12.0, 1),
                "federated_yield_gain_pct": final_m["federated_efficiency_boost_pct"],
            },
            "clamart_districts": districts_status,
            "centralized_vs_holarchic": centralized_comparison,
            "timeline": timeline,
        }
