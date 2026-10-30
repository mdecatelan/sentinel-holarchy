"""
Holon 0: Metabolic Flux Analysis & Copolymer (PHB-co-3HV) Thermomechanical Modeling.
Models even-chain (Acetate C2, Butyrate C4 -> 3HB) vs odd-chain (Propionate C3, Valerate C5 -> 3HV)
assimilation pathways in Mixed Microbial Cultures (MMC), and predicts polymer physical properties.
"""

from dataclasses import dataclass
from typing import Dict
import math


@dataclass
class VFAProfile:
    """Concentration of individual Volatile Fatty Acids in g/L."""
    acetate_c2_g_l: float = 1.2      # Even-chain -> 3HB precursor
    propionate_c3_g_l: float = 0.4   # Odd-chain  -> 3HV precursor
    butyrate_c4_g_l: float = 0.6     # Even-chain -> 3HB precursor
    valerate_c5_g_l: float = 0.15    # Odd-chain  -> 3HV precursor

    @property
    def total_vfa_g_l(self) -> float:
        return (
            self.acetate_c2_g_l
            + self.propionate_c3_g_l
            + self.butyrate_c4_g_l
            + self.valerate_c5_g_l
        )

    @property
    def odd_chain_fraction(self) -> float:
        """Mass fraction of odd-chain VFAs (propionate + valerate) driving 3HV synthesis."""
        tot = self.total_vfa_g_l
        if tot <= 1e-6:
            return 0.0
        return (self.propionate_c3_g_l + self.valerate_c5_g_l) / tot


@dataclass
class CopolymerProperties:
    """Physical, thermal, and electro-active properties of synthesized PHBV."""
    hv_molar_fraction_pct: float
    melting_temp_c: float
    glass_transition_temp_c: float
    crystallinity_pct: float
    tensile_modulus_gpa: float
    elongation_at_break_pct: float
    piezoelectric_d33_pc_n: float
    recommended_application: str


class PHBVCopolymerModel:
    """
    Predicts PHBV (Poly(3-hydroxybutyrate-co-3-hydroxyvalerate)) properties
    using Flory-Huggins melting point depression and empirical structure-property relations.
    """

    # Pure PHB reference constants
    TM_PURE_PHB_K = 450.15       # 177.0 °C in Kelvin
    DELTA_H_M_J_MOL = 10900.0    # Enthalpy of fusion of pure PHB repeat unit (J/mol)
    GAS_CONSTANT_R = 8.314       # J/(mol·K)
    INTERACTION_PARAM_B = -1.2   # Cocrystallization parameter for PHBV

    @classmethod
    def predict_from_vfa_profile(cls, vfa: VFAProfile) -> CopolymerProperties:
        """
        Calculates 3HV molar fraction from VFA precursor ratios and derives
        thermal, mechanical, and piezoelectric properties.
        """
        # Molar conversion: Propionate (MW 74.08) + Valerate (MW 102.13) -> 3HV unit
        # Acetate (MW 60.05) + Butyrate (MW 88.11) -> 3HB unit
        moles_even = (vfa.acetate_c2_g_l / 60.05) * 0.5 + (vfa.butyrate_c4_g_l / 88.11) + (vfa.propionate_c3_g_l / 74.08) * 0.45
        moles_odd = (vfa.propionate_c3_g_l / 74.08) * 0.40 + (vfa.valerate_c5_g_l / 102.13) * 0.65

        total_monomer_moles = max(1e-6, moles_even + moles_odd)
        x_hv = min(0.45, max(0.0, moles_odd / total_monomer_moles))

        # Flory-Huggins melting point depression for isodimorphic PHBV:
        # 1/Tm - 1/Tm0 = -(R / dHm) * ln(1 - x_HV)
        inv_tm = (1.0 / cls.TM_PURE_PHB_K) - (cls.GAS_CONSTANT_R / cls.DELTA_H_M_J_MOL) * math.log(1.0 - x_hv)
        tm_k = 1.0 / inv_tm
        tm_c = round(tm_k - 273.15, 1)

        # Glass transition temperature (Fox equation approximation between PHB +4°C and PHV -15°C)
        tg_c = round(4.0 * (1.0 - x_hv) - 15.0 * x_hv, 1)

        # Crystallinity decreases from ~68% (pure PHB) to ~38% at 30 mol% 3HV
        crystallinity = round(max(32.0, 68.0 - 95.0 * x_hv), 1)

        # Young's Tensile Modulus (GPa): drops from 3.5 GPa (brittle PHB) to 0.9 GPa (tough PHBV)
        modulus_gpa = round(max(0.7, 3.5 * math.exp(-4.2 * x_hv)), 2)

        # Elongation at break (%): increases dramatically with 3HV incorporation
        elongation_pct = round(min(420.0, 5.0 + 950.0 * (x_hv ** 1.4)), 1)

        # Piezoelectric d33 coefficient (pC/N) for flexible bio-electronics/photonics
        # Peaks around 15-22 mol% 3HV due to optimal beta-phase dipole alignment
        d33 = round(3.2 + 14.5 * math.exp(-((x_hv - 0.18) / 0.10) ** 2), 2)

        hv_pct = round(x_hv * 100.0, 1)
        if hv_pct < 5.0:
            app = "Rigid 3D Printing Filament & Injection Molding (High Crystallinity PHB)"
        elif hv_pct < 15.0:
            app = "Tough Packaging Films & Agricultural Mulch / Clips (Balanced PHBV)"
        elif hv_pct < 28.0:
            app = "Flexible Piezoelectric Bio-Sensors, Photonics & Cosine Micro-Encapsulation"
        else:
            app = "Elastomeric Biomedical Scaffolds & Soft Robotics Actuators"

        return CopolymerProperties(
            hv_molar_fraction_pct=hv_pct,
            melting_temp_c=tm_c,
            glass_transition_temp_c=tg_c,
            crystallinity_pct=crystallinity,
            tensile_modulus_gpa=modulus_gpa,
            elongation_at_break_pct=elongation_pct,
            piezoelectric_d33_pc_n=d33,
            recommended_application=app
        )
