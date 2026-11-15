"""
Holon 0 / Multi-Molecule Biorefinery Engine (Clamart Digital Twin v2.0).

Implements the 4 metabolic & green-extraction programs from household urban biowaste,
governed by:
  1. Simple Compost Rule of Thumb at input (~1/3 Starchy/Brown Carbon + ~2/3 Green Peels/Coffee/Algae)
  2. Automatic HX711 load-cell water dosing & baseline salt conductivity tare EC0 at t = 0.5h
  3. Passive CaCO3 shell cartridge (250g eggshells/oyster shells, self-regulating pH >= 5.6)
  4. Product-driven stoichiometry: Delta_EC(t) = EC(t) - EC0, CO2 off-gas plateau, and DO Spike harvest.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Any, Optional
import math

from .kinetics import Holon0Engine, KineticParameters, MicrobialState
from sentinel_holarchy.holon1_hardware.auto_dosing import (
    BlindFeedstockInferencer,
    PassiveBufferCartridge,
    StoichiometricProductTracker,
)
from sentinel_holarchy.holon1_hardware.pid_controller import HydrodynamicShearModel
from sentinel_holarchy.holon1_hardware.soft_sensor import BioprocessEKFSoftSensor
from sentinel_holarchy.holon2_workshop.downstream_extraction import (
    ExtractionProtocolConfig,
    GreenPHAExtractor,
)
from sentinel_holarchy.holon5_paradigm.impact_metrics import SocietalImpactCalculator


class RefiningProgramId(str, Enum):
    PROG_1_PHBV_COSMETIC_PIEZO = "PROG_1_PHBV_COSMETIC_PIEZO"
    PROG_2_CHIRAL_R3HB_MONOMER = "PROG_2_CHIRAL_R3HB_MONOMER"
    PROG_3_CAPROIC_C6_OIL = "PROG_3_CAPROIC_C6_OIL"
    PROG_4_RHAMNOLIPIDS_COFFEE = "PROG_4_RHAMNOLIPIDS_COFFEE"


@dataclass(frozen=True)
class ProgramCatalogEntry:
    program_id: RefiningProgramId
    code: str
    title_fr: str
    primary_molecule_fr: str
    primary_unit: str
    price_range_eur_per_kg: str
    median_price_eur_per_kg: float
    secondary_molecule_fr: str
    secondary_price_eur_per_unit: float
    secondary_unit: str
    target_buyers_clamart_idf: str
    regulatory_driver: str
    process_summary_fr: str
    duration_h: float


PROGRAM_CATALOG: Dict[str, ProgramCatalogEntry] = {
    RefiningProgramId.PROG_1_PHBV_COSMETIC_PIEZO.value: ProgramCatalogEntry(
        program_id=RefiningProgramId.PROG_1_PHBV_COSMETIC_PIEZO,
        code="PROG-1",
        title_fr="Poudre Cosmétique PHBV (10–50 µm) & Copolymère Piézoélectrique",
        primary_molecule_fr="Copolymère PHBV purifié sans solvant",
        primary_unit="g",
        price_range_eur_per_kg="50 – 120 €/kg (Cosmétique) | 250 – 800 €/kg (Piézo 15–22% 3HV)",
        median_price_eur_per_kg=95.0,
        secondary_molecule_fr="Biostimulant Ca-Peptides UAB (Grade B)",
        secondary_price_eur_per_unit=4.50,
        secondary_unit="L",
        target_buyers_clamart_idf="Formulateurs cosmétiques (Cosmetic Valley / IDF), Medtech & capteurs souples",
        regulatory_driver="Règlement (UE) 2023/2055 (Interdiction des microplastiques cosmétiques)",
        process_summary_fr="Acidogenèse 30 °C (CaCO3) → Essorage 650 RPM → Gavage aérobie (DO Spike) → Lyse Na2CO3 70 °C (45 min)",
        duration_h=73.0,
    ),
    RefiningProgramId.PROG_2_CHIRAL_R3HB_MONOMER.value: ProgramCatalogEntry(
        program_id=RefiningProgramId.PROG_2_CHIRAL_R3HB_MONOMER,
        code="PROG-2",
        title_fr="Monomère Chiral Énantiopur (R)-3-Hydroxybutyrate (R-3HB)",
        primary_molecule_fr="Sel énantiopur (R)-3-Hydroxybutyrate (ee > 99%)",
        primary_unit="g",
        price_range_eur_per_kg="150 – 450 €/kg",
        median_price_eur_per_kg=240.0,
        secondary_molecule_fr="Hydrolysat d'acides aminés L libres (Grade B+)",
        secondary_price_eur_per_unit=6.00,
        secondary_unit="L",
        target_buyers_clamart_idf="Chimie fine pharmaceutique (synthons bêta-lactames), Nutraceutique cétones exogènes",
        regulatory_driver="Pharmacopée Européenne / Chimie verte chirale sans métaux lourds",
        process_summary_fr="Synthèse PHBV 72h → Dépolymérisation alcaline prolongée à 80 °C (3h) sans racémisation",
        duration_h=75.0,
    ),
    RefiningProgramId.PROG_3_CAPROIC_C6_OIL.value: ProgramCatalogEntry(
        program_id=RefiningProgramId.PROG_3_CAPROIC_C6_OIL,
        code="PROG-3",
        title_fr="Acides Caproïque (C6) & Caprylique (C8) Sans Huile de Palme",
        primary_molecule_fr="Huile d'acides carboxyliques moyens C6/C8 séparée par phase",
        primary_unit="g",
        price_range_eur_per_kg="18 – 35 €/kg (Haut rendement massique anaérobie)",
        median_price_eur_per_kg=26.0,
        secondary_molecule_fr="Bouillon Lactate/Succinate de Calcium chélaté",
        secondary_price_eur_per_unit=4.00,
        secondary_unit="L",
        target_buyers_clamart_idf="Chimie biosourcée (biolubrifiants, antimicrobiens clean-label, nutrition animale)",
        regulatory_driver="Règlement (UE) 2023/1115 (Zéro Déforestation / Substitution huile de palme & palmiste)",
        process_summary_fr="Élongation de chaîne anaérobie 72h à 32 °C (Clostridium kluyveri, éthanol endogène) → Décantation huile pH 4.9",
        duration_h=73.0,
    ),
    RefiningProgramId.PROG_4_RHAMNOLIPIDS_COFFEE.value: ProgramCatalogEntry(
        program_id=RefiningProgramId.PROG_4_RHAMNOLIPIDS_COFFEE,
        code="PROG-4",
        title_fr="Biosurfactants (Rhamnolipides) & Polyphénols (Marc de Café & Pelures)",
        primary_molecule_fr="Rhamnolipides tensioactifs biodégradables + Polyphénols",
        primary_unit="g",
        price_range_eur_per_kg="30 – 90 €/kg (Rhamnolipides) | 95 €/kg (Extrait Polyphénols)",
        median_price_eur_per_kg=58.0,
        secondary_molecule_fr="Substrat Marc Pasteurisé Premium Pleurotes (Grade C+)",
        secondary_price_eur_per_unit=1.60,
        secondary_unit="kg",
        target_buyers_clamart_idf="Détergence écologique française, Cosmétique sans sulfates, Champignonnières du Grand Paris",
        regulatory_driver="Écolabel Européen Détergents & Règlement Cosmétique (Substitution SLES pétrochimiques)",
        process_summary_fr="Infusion polyphénols 55 °C (4h) → Hydrolyse → Bioconversion micro-aérobie des lipides du marc (30–72h)",
        duration_h=73.0,
    ),
}


@dataclass
class BiorefineryBatchInput:
    program_id: str = RefiningProgramId.PROG_1_PHBV_COSMETIC_PIEZO.value
    hx711_waste_kg: float = 2.50          # Household / café biowaste thrown into drum (kg)
    brown_starch_ratio: float = 0.33      # Compost rule: ~1/3 bread/starch + ~2/3 green peels/coffee
    baseline_ec0_ms_cm: float = 4.20      # Initial conductivity tare at t=0.5h (includes kitchen NaCl)
    cartridge_caco3_g: float = 250.0      # Passive eggshell/oyster shell basket mass (g)
    coffee_grounds_fraction: float = 0.25 # Fraction of coffee grounds in green waste (boosts Prog 4)


class MultiMoleculeEngine:
    """
    Mechanistic Digital Twin engine simulating all 4 Clamart biorefinery programs
    with RK4 microbial kinetics, passive CaCO3 buffering, and product-driven telemetry.
    """

    def __init__(self, params: Optional[KineticParameters] = None):
        self.params = params or KineticParameters()

    @staticmethod
    def list_programs() -> List[Dict[str, Any]]:
        return [
            {
                "program_id": entry.program_id.value,
                "code": entry.code,
                "title_fr": entry.title_fr,
                "primary_molecule_fr": entry.primary_molecule_fr,
                "primary_unit": entry.primary_unit,
                "price_range_eur_per_kg": entry.price_range_eur_per_kg,
                "median_price_eur_per_kg": entry.median_price_eur_per_kg,
                "secondary_molecule_fr": entry.secondary_molecule_fr,
                "target_buyers_clamart_idf": entry.target_buyers_clamart_idf,
                "regulatory_driver": entry.regulatory_driver,
                "process_summary_fr": entry.process_summary_fr,
                "duration_h": entry.duration_h,
            }
            for entry in PROGRAM_CATALOG.values()
        ]

    @staticmethod
    def derive_compost_rule_feedstock(inp: BiorefineryBatchInput) -> Dict[str, float]:
        """
        Translates HX711 weighed waste + Compost Rule (~1/3 brown starch, ~2/3 green peels)
        into initial physical & biochemical states without requiring laboratory assays.
        """
        water_info = BlindFeedstockInferencer.auto_fill_water(inp.hx711_waste_kg, target_slurry_ratio=1.5)
        waste_kg = water_info["detected_waste_kg"]
        water_l = water_info["auto_water_injected_l"]

        brown = min(0.75, max(0.05, inp.brown_starch_ratio))
        dry_fraction = 0.16 + 0.34 * brown
        intrinsic_water_l = waste_kg * (1.0 - dry_fraction)
        effective_vol_l = max(0.8, water_l + intrinsic_water_l)

        dry_mass_g = waste_kg * dry_fraction * 1000.0
        fermentable_frac = 0.68 + 0.14 * brown
        insoluble_fiber_cake_wet_kg = (dry_mass_g * (1.0 - fermentable_frac) / 1000.0) * 2.6

        carbs_g_l = (dry_mass_g * fermentable_frac) / effective_vol_l
        cn_ratio = 18.0 + 30.0 * brown
        nitrogen_g_l = max(0.55, (carbs_g_l * 0.42) / cn_ratio)
        odd_vfa_ratio = min(0.36, max(0.11, 0.32 - 0.32 * brown))

        # Coffee lipid content (~15% of dry coffee grounds)
        coffee_frac = min(0.80, max(0.05, inp.coffee_grounds_fraction))
        lipids_g_l = (dry_mass_g * (1.0 - brown) * coffee_frac * 0.16) / effective_vol_l
        polyphenols_g_l = (dry_mass_g * (1.0 - brown) * (0.018 + 0.024 * coffee_frac)) / effective_vol_l

        return {
            "waste_kg": round(waste_kg, 2),
            "auto_water_injected_l": round(water_l, 2),
            "effective_volume_l": round(effective_vol_l, 2),
            "dry_matter_pct": round(dry_fraction * 100.0, 1),
            "carbohydrates_g_l": round(carbs_g_l, 2),
            "nitrogen_g_l": round(nitrogen_g_l, 2),
            "cn_ratio": round(cn_ratio, 1),
            "odd_vfa_ratio": round(odd_vfa_ratio, 3),
            "lipids_g_l": round(lipids_g_l, 2),
            "polyphenols_g_l": round(polyphenols_g_l, 2),
            "grade_c_wet_cake_kg": round(insoluble_fiber_cake_wet_kg, 2),
            "compost_rule_compliant": (20.0 <= cn_ratio <= 40.0),
        }

    def simulate_batch(
        self,
        inp: BiorefineryBatchInput,
        dt_h: float = 0.5,
    ) -> Dict[str, Any]:
        """Runs the complete biorefinery batch simulation for any of the 4 Clamart programs."""
        prog_key = inp.program_id if inp.program_id in PROGRAM_CATALOG else RefiningProgramId.PROG_1_PHBV_COSMETIC_PIEZO.value
        catalog = PROGRAM_CATALOG[prog_key]
        feed = self.derive_compost_rule_feedstock(inp)
        vol_l = feed["effective_volume_l"]

        engine = Holon0Engine(params=self.params)
        shear_model = HydrodynamicShearModel(liquid_volume_l=vol_l)
        ekf = BioprocessEKFSoftSensor(initial_vfa=1.0, initial_do=7.2)
        tracker = StoichiometricProductTracker(baseline_ec0_ms_cm=inp.baseline_ec0_ms_cm)

        caco3_init_g_l = inp.cartridge_caco3_g / vol_l
        state = MicrobialState(
            time_h=0.0,
            carbohydrates_g_l=feed["carbohydrates_g_l"],
            vfa_g_l=1.0,
            nitrogen_g_l=feed["nitrogen_g_l"],
            caco3_g_l=caco3_init_g_l,
            biomass_acid_g_l=1.35,
            biomass_pha_active_g_l=0.65,
            pha_stored_g_l=0.02,
            ph=6.75,
            dissolved_oxygen_mg_l=7.4,
            odd_vfa_ratio=feed["odd_vfa_ratio"],
        )

        # Auxiliary states for Prog 2, 3, 4
        r3hb_monomer_g_l = 0.0
        caproate_c6_g_l = 0.0
        lactate_succinate_g_l = 0.0
        rhamnolipid_g_l = 0.0
        polyphenol_extracted_g_l = 0.0
        available_lipids_g_l = max(2.2, feed["lipids_g_l"])

        total_h = catalog.duration_h
        steps = int(round(total_h / dt_h)) + 1
        trajectory: List[Dict[str, Any]] = []

        peak_vfa_g_l = 1.0
        plateau_first_h: Optional[float] = None
        do_spike_first_h: Optional[float] = None
        prev_do = state.dissolved_oxygen_mg_l
        total_energy_kwh = 0.0
        dewatering_done = False

        def integrate_substeps(s: MicrobialState, duration_h: float, is_aerated: bool) -> MicrobialState:
            n_sub = max(1, int(math.ceil(duration_h / 0.05)))
            h_sub = duration_h / n_sub
            cur = s
            for _ in range(n_sub):
                cur = engine.step(cur, dt_h=h_sub, aerated=is_aerated)
            return cur

        for i in range(steps):
            t = round(i * dt_h, 2)
            prev_carb = state.carbohydrates_g_l

            # --- Program-specific Finite State Machine (FSM) ---
            if prog_key in (
                RefiningProgramId.PROG_1_PHBV_COSMETIC_PIEZO.value,
                RefiningProgramId.PROG_2_CHIRAL_R3HB_MONOMER.value,
            ):
                if t < 2.0:
                    fsm_state = "1_MACERATION_TARE_HX711_EC0"
                    rpm, temp_c, aerated, power_w = 45.0, 28.0, False, 24.0
                elif t < 36.0:
                    fsm_state = "2_ACIDOGENESE_ANAEROBIE_CACO3"
                    rpm, temp_c, aerated, power_w = 8.0, 30.0, False, 18.0
                elif t < 36.5:
                    fsm_state = "3_ESSORAGE_650RPM_SEPARATION_GRADE_C"
                    rpm, temp_c, aerated, power_w = 650.0, 26.0, False, 165.0
                elif t < 72.0:
                    fsm_state = "4_GAVAGE_AEROBIE_FEAST_DO_SPIKE"
                    rpm, temp_c, aerated, power_w = 16.0, 26.0, True, 42.0
                else:
                    if prog_key == RefiningProgramId.PROG_1_PHBV_COSMETIC_PIEZO.value:
                        fsm_state = "5_LYSE_DOUCE_NA2CO3_70C_PHBV"
                        rpm, temp_c, aerated, power_w = 800.0, 70.0, False, 280.0
                    else:
                        fsm_state = "5_DEPOLYMERISATION_CHIRALE_80C_R3HB"
                        rpm, temp_c, aerated, power_w = 120.0, 80.0, False, 310.0

                if not dewatering_done and t >= 36.5:
                    # Solid removal & dilution shift to N-limited feast
                    state.nitrogen_g_l = max(0.06, state.nitrogen_g_l * 0.14)
                    state.biomass_pha_active_g_l = max(state.biomass_pha_active_g_l, 1.45)
                    dewatering_done = True

            elif prog_key == RefiningProgramId.PROG_3_CAPROIC_C6_OIL.value:
                if t < 2.0:
                    fsm_state = "1_MACERATION_TARE_HX711_EC0"
                    rpm, temp_c, aerated, power_w = 45.0, 28.0, False, 24.0
                elif t < 24.0:
                    fsm_state = "2_ACIDOGENESE_PRIMAIRE_ETHANOL_C2_C4"
                    rpm, temp_c, aerated, power_w = 10.0, 32.0, False, 22.0
                elif t < 71.0:
                    fsm_state = "3_ELONGATION_CHAINE_ANAEROBIE_C6_C8"
                    rpm, temp_c, aerated, power_w = 8.0, 32.0, False, 20.0
                else:
                    fsm_state = "4_DECANTATION_HUILE_HYDROPHOBE_C6"
                    rpm, temp_c, aerated, power_w = 750.0, 25.0, False, 175.0

            else:  # PROG_4_RHAMNOLIPIDS_COFFEE
                if t < 4.0:
                    fsm_state = "1_INFUSION_POLYPHENOLS_55C"
                    rpm, temp_c, aerated, power_w = 35.0, 55.0, False, 140.0
                elif t < 28.0:
                    fsm_state = "2_HYDROLYSE_SUCRES_MARC_PELURES"
                    rpm, temp_c, aerated, power_w = 10.0, 30.0, False, 18.0
                elif t < 71.5:
                    fsm_state = "3_BIOSYNTHESE_RHAMNOLIPIDES_MICROAEROBIE"
                    rpm, temp_c, aerated, power_w = 18.0, 28.0, True, 38.0
                else:
                    fsm_state = "4_ULTRAFILTRATION_PASTEURISATION_MARC"
                    rpm, temp_c, aerated, power_w = 700.0, 68.0, False, 210.0

            total_energy_kwh += (power_w / 1000.0) * dt_h

            # --- Target molecule concentrations & specialized pathway kinetics ---
            if prog_key == RefiningProgramId.PROG_1_PHBV_COSMETIC_PIEZO.value:
                target_mol_g_l = state.pha_stored_g_l
                secondary_mol_g_l = state.vfa_g_l * state.odd_vfa_ratio

            elif prog_key == RefiningProgramId.PROG_2_CHIRAL_R3HB_MONOMER.value:
                if t >= 72.0:
                    # Alkaline saponification of intracellular PHBV into enantiopure (R)-3HB salt
                    # Hydrolysis adds H2O across ester bond: 86.09 -> 104.10 g/mol (stoichiometric mass factor ~1.09 net)
                    hydrolysis_progress = 1.0 - math.exp(-1.15 * (t - 72.0))
                    r3hb_monomer_g_l = state.pha_stored_g_l * 1.08 * 0.92 * hydrolysis_progress
                target_mol_g_l = r3hb_monomer_g_l if t >= 72.0 else state.pha_stored_g_l
                secondary_mol_g_l = state.pha_stored_g_l * (1.0 - (1.0 - math.exp(-1.15 * max(0.0, t - 72.0)))) if t >= 72.0 else state.pha_stored_g_l

            elif prog_key == RefiningProgramId.PROG_3_CAPROIC_C6_OIL.value:
                # Reverse beta-oxidation: short VFAs + endogenous ethanol elongate into C6/C8
                if 18.0 <= t < 71.0 and state.vfa_g_l > 2.5:
                    r_elong = 0.058 * state.vfa_g_l * (state.vfa_g_l / (4.0 + state.vfa_g_l))
                    converted = min(state.vfa_g_l * 0.35, r_elong * dt_h)
                    state.vfa_g_l = max(0.8, state.vfa_g_l - converted)
                    caproate_c6_g_l += converted * 0.84
                    lactate_succinate_g_l += converted * 0.16
                if t >= 71.0:
                    state.ph = 4.92  # Mild pH shift for hydrophobic oil phase separation
                target_mol_g_l = caproate_c6_g_l
                secondary_mol_g_l = lactate_succinate_g_l

            else:  # PROG_4_RHAMNOLIPIDS_COFFEE
                if t < 4.0:
                    polyphenol_extracted_g_l = feed["polyphenols_g_l"] * (1.0 - math.exp(-0.85 * (t + 0.5)))
                else:
                    polyphenol_extracted_g_l = feed["polyphenols_g_l"] * 0.96
                if 28.0 <= t < 71.5:
                    # Micro-aerobic rhamnolipid secretion from coffee lipids + VFA/sugars
                    state.dissolved_oxygen_mg_l = min(state.dissolved_oxygen_mg_l, 3.8)
                    r_rhamno = (
                        0.26
                        * (available_lipids_g_l / (0.8 + available_lipids_g_l))
                        * ((state.vfa_g_l + 1.5) / (2.0 + state.vfa_g_l))
                    )
                    delta_rh = r_rhamno * dt_h
                    available_lipids_g_l = max(0.05, available_lipids_g_l - delta_rh * 0.62)
                    state.vfa_g_l = max(0.4, state.vfa_g_l - delta_rh * 0.45)
                    rhamnolipid_g_l += delta_rh
                target_mol_g_l = rhamnolipid_g_l
                secondary_mol_g_l = polyphenol_extracted_g_l

            peak_vfa_g_l = max(peak_vfa_g_l, state.vfa_g_l + caproate_c6_g_l * 0.6)

            # --- Physical Sensor Signals (EC, Delta_EC, CO2, ORP, DO, EKF) ---
            # Buffered carboxylates increase ionic conductivity by 1.0 mS/cm per 12.2 g/L
            ionic_carboxylates_g_l = state.vfa_g_l + 0.55 * caproate_c6_g_l + 0.75 * r3hb_monomer_g_l
            ec_ms = inp.baseline_ec0_ms_cm + (ionic_carboxylates_g_l / 12.2)

            # Next step preview to get exact carbohydrate consumption rate for CO2 evolution
            next_state = integrate_substeps(state, dt_h, aerated) if t < 72.0 else state
            carb_consumed_rate_g_l_h = max(0.0, (prev_carb - next_state.carbohydrates_g_l) / dt_h)
            co2_ml_min = round(carb_consumed_rate_g_l_h * vol_l * 16.5 + (3.2 if aerated else 0.4), 1)

            stoich = tracker.estimate_vfa_from_delta_ec(ec_ms, co2_rate_ml_min=co2_ml_min)
            if stoich["acidogenesis_plateau_reached"] and t >= 12.0 and plateau_first_h is None:
                plateau_first_h = t

            d_do_dt = (state.dissolved_oxygen_mg_l - prev_do) / dt_h if i > 0 else 0.0
            time_in_aeration = max(0.0, t - 36.5) if aerated else 0.0
            do_spike = tracker.detect_do_spike_harvest(
                do_mg_l=state.dissolved_oxygen_mg_l,
                d_do_dt=d_do_dt,
                time_in_aeration_h=time_in_aeration,
            )
            if do_spike and do_spike_first_h is None:
                do_spike_first_h = t

            # ORP Nernstian composite potential (mV)
            orp_mv = (
                120.0
                + 65.0 * math.log10(max(0.02, state.dissolved_oxygen_mg_l))
                - 59.16 * (state.ph - 7.0)
                - 6.2 * state.vfa_g_l
            )
            if not aerated and 2.0 <= t < 36.5:
                orp_mv = min(-165.0, orp_mv - 85.0)
            elif aerated:
                orp_mv = 148.0 + (7.0 - state.ph) * 22.0 + (state.dissolved_oxygen_mg_l - 6.0) * 12.0
            orp_mv = max(-340.0, min(240.0, orp_mv))

            ekf_res = ekf.step(
                measured_ph=state.ph,
                measured_orp_mv=orp_mv,
                dt_h=dt_h,
                aerated=aerated,
                caco3_g_l=state.caco3_g_l,
            )
            hydro = shear_model.evaluate_regime(rpm)

            # Live cumulative gross value (EUR)
            live_primary_kg = (target_mol_g_l * vol_l) / 1000.0
            live_val_eur = live_primary_kg * catalog.median_price_eur_per_kg

            trajectory.append(
                {
                    "t": t,
                    "fsm_state": fsm_state,
                    "carb": round(state.carbohydrates_g_l, 2),
                    "vfa": round(state.vfa_g_l, 2),
                    "target_mol_g_l": round(target_mol_g_l, 2),
                    "secondary_mol_g_l": round(secondary_mol_g_l, 2),
                    "pha_g_l": round(state.pha_stored_g_l, 2),
                    "pha_pct": round(state.pha_fraction * 100.0, 1),
                    "ph": round(state.ph, 2),
                    "orp_mv": round(orp_mv, 1),
                    "do_mg_l": round(state.dissolved_oxygen_mg_l, 2),
                    "ec0_ms": round(inp.baseline_ec0_ms_cm, 2),
                    "ec_ms": round(ec_ms, 2),
                    "delta_ec_ms": stoich["delta_ec_ms_cm"],
                    "stoich_vfa_g_l": stoich["stoichiometric_vfa_g_l"],
                    "co2_ml_min": co2_ml_min,
                    "caco3_g_l": round(state.caco3_g_l, 2),
                    "temp_c": round(temp_c, 1),
                    "rpm": round(rpm, 0),
                    "ekf_vfa": ekf_res["estimated_vfa_g_l"],
                    "ekf_do": ekf_res["estimated_do_mg_l"],
                    "rcf_g": hydro["rcf_g_force"],
                    "aerated": aerated,
                    "delta_ec_plateau": stoich["acidogenesis_plateau_reached"],
                    "do_spike": do_spike,
                    "live_value_eur": round(live_val_eur, 2),
                }
            )

            prev_do = state.dissolved_oxygen_mg_l
            state = next_state

        # --- Downstream Recovery, Unit Economics & ISO-14040 LCA ---
        cartridge = PassiveBufferCartridge(initial_mass_g=inp.cartridge_caco3_g, capacity_g=250.0)
        cartridge_status = cartridge.consume_for_batch(peak_vfa_g_l * vol_l)

        peak_state = MicrobialState(vfa_g_l=peak_vfa_g_l, odd_vfa_ratio=feed["odd_vfa_ratio"])
        copolymer = peak_state.predict_copolymer_properties()

        final_pt = trajectory[-1]
        grade_b_liters = round(vol_l * 0.78, 2)
        grade_c_kg = feed["grade_c_wet_cake_kg"]

        if prog_key == RefiningProgramId.PROG_1_PHBV_COSMETIC_PIEZO.value:
            extractor = GreenPHAExtractor(
                ExtractionProtocolConfig(lysis_temp_c=70.0, lysis_duration_min=45.0, na2co3_molarity=0.08)
            )
            total_biomass_g = (state.biomass_pha_active_g_l + state.pha_stored_g_l) * vol_l
            ext = extractor.simulate_extraction(total_biomass_g, state.pha_fraction)
            grade_a_g = ext["recovered_pha_g"]
            purity_pct = ext["final_purity_pct"]
            mw_kda = ext["final_mw_kda"]
            # Piezoelectric premium if 3HV in [15, 24] mol% and purity >= 88%
            is_piezo = 15.0 <= copolymer.hv_molar_fraction_pct <= 24.0 and purity_pct >= 88.0
            unit_price_eur_kg = 320.0 if is_piezo else 95.0
            grade_a_label = (
                f"PHBV Piézoélectrique ({copolymer.hv_molar_fraction_pct}% 3HV)"
                if is_piezo
                else f"Poudre Cosmétique PHBV 10–50 µm ({copolymer.hv_molar_fraction_pct}% 3HV)"
            )
            secondary_val_eur = grade_b_liters * 4.50 + grade_c_kg * 1.20

        elif prog_key == RefiningProgramId.PROG_2_CHIRAL_R3HB_MONOMER.value:
            grade_a_g = round(final_pt["target_mol_g_l"] * vol_l * 0.91, 2)
            purity_pct = 96.4
            mw_kda = 0.104  # Monomer MW = 104.1 g/mol
            unit_price_eur_kg = catalog.median_price_eur_per_kg
            grade_a_label = "Monomère Chiral (R)-3-Hydroxybutyrate (ee > 99.2%)"
            secondary_val_eur = grade_b_liters * 6.00 + grade_c_kg * 1.20

        elif prog_key == RefiningProgramId.PROG_3_CAPROIC_C6_OIL.value:
            grade_a_g = round(final_pt["target_mol_g_l"] * vol_l * 0.89, 2)
            purity_pct = 93.8
            mw_kda = 0.116  # Caproic acid MW = 116.16 g/mol
            unit_price_eur_kg = catalog.median_price_eur_per_kg
            grade_a_label = "Huile Acides Caproïque (C6) & Caprylique (C8) Sans Palme"
            secondary_val_eur = grade_b_liters * 4.00 + grade_c_kg * 1.20

        else:  # PROG_4_RHAMNOLIPIDS_COFFEE
            rhamno_g = final_pt["target_mol_g_l"] * vol_l * 0.88
            polyphenol_g = final_pt["secondary_mol_g_l"] * vol_l * 0.85
            grade_a_g = round(rhamno_g + polyphenol_g, 2)
            purity_pct = 91.5
            mw_kda = 0.650  # Di-rhamnolipid MW ~ 650 g/mol
            unit_price_eur_kg = round(
                (rhamno_g * 58.0 + polyphenol_g * 95.0) / max(1e-3, grade_a_g), 2
            )
            grade_a_label = f"Rhamnolipides ({rhamno_g:.1f} g) + Polyphénols ({polyphenol_g:.1f} g)"
            secondary_val_eur = grade_b_liters * 4.20 + grade_c_kg * 1.60

        grade_a_eur = (grade_a_g / 1000.0) * unit_price_eur_kg
        gross_revenue_eur = grade_a_eur + secondary_val_eur

        # OpEx: French grid electricity (~0.22 EUR/kWh) + tap water + Na2CO3/reagents (~0.18 EUR/batch)
        elec_cost_eur = total_energy_kwh * 0.22
        reagents_water_eur = 0.18 + (feed["auto_water_injected_l"] * 0.004)
        opex_eur = elec_cost_eur + reagents_water_eur
        net_margin_eur = gross_revenue_eur - opex_eur

        lca_calc = SocietalImpactCalculator()
        lca = lca_calc.compute_avoided_footprint(
            pha_produced_kg=grade_a_g / 1000.0,
            biostimulant_produced_L=grade_b_liters,
            biowaste_diverted_kg=feed["waste_kg"],
            electricity_consumed_kwh=total_energy_kwh,
        )

        # Annual Clamart projection (100 cycles/year per 73h drum)
        cycles_per_year = 100
        npv_metrics = lca_calc.compute_techno_economic_npv(
            unit_capex_eur=291.0,
            openraman_capex_eur=480.0,
            annual_gross_revenue_eur=gross_revenue_eur * cycles_per_year,
            annual_opex_eur=opex_eur * cycles_per_year,
        )

        return {
            "program": {
                "program_id": catalog.program_id.value,
                "code": catalog.code,
                "title_fr": catalog.title_fr,
                "target_buyers": catalog.target_buyers_clamart_idf,
                "regulatory_driver": catalog.regulatory_driver,
                "process_summary_fr": catalog.process_summary_fr,
            },
            "feedstock": feed,
            "cartridge_status": cartridge_status,
            "events": {
                "ec0_locked_ms_cm": round(inp.baseline_ec0_ms_cm, 2),
                "acidogenesis_plateau_h": plateau_first_h,
                "do_spike_harvest_h": do_spike_first_h,
                "peak_vfa_g_l": round(peak_vfa_g_l, 2),
            },
            "products": {
                "grade_a_label": grade_a_label,
                "grade_a_mass_g": round(grade_a_g, 2),
                "grade_a_purity_pct": round(purity_pct, 1),
                "grade_a_mw_kda": round(mw_kda, 2),
                "grade_a_unit_price_eur_kg": round(unit_price_eur_kg, 2),
                "grade_a_value_eur": round(grade_a_eur, 2),
                "hv_mol_pct": copolymer.hv_molar_fraction_pct,
                "crystallinity_pct": copolymer.crystallinity_pct,
                "d33_pc_n": copolymer.piezoelectric_d33_pc_n,
                "grade_b_biostimulant_l": grade_b_liters,
                "grade_c_substrate_kg": grade_c_kg,
                "secondary_co_products_eur": round(secondary_val_eur, 2),
            },
            "economics": {
                "energy_kwh": round(total_energy_kwh, 2),
                "opex_batch_eur": round(opex_eur, 2),
                "gross_revenue_batch_eur": round(gross_revenue_eur, 2),
                "net_margin_batch_eur": round(net_margin_eur, 2),
                "annual_net_cashflow_1drum_eur": npv_metrics["annual_net_cashflow_eur"],
                "payback_months": npv_metrics["payback_period_months"],
                "npv_10y_eur": npv_metrics["npv_10y_eur"],
            },
            "lca": lca,
            "parameters_used": {
                "mu_max_acid": round(self.params.mu_max_acid, 4),
                "y_vfa_carb": round(self.params.y_vfa_carb, 4),
                "caco3_dissolution_rate": round(self.params.caco3_dissolution_rate, 4),
                "q_pha_max": round(self.params.q_pha_max, 4),
                "y_pha_vfa": round(self.params.y_pha_vfa, 4),
            },
            "trajectory": trajectory,
        }
