"""
Holon 0: Microbial Kinetics & Metabolic Modeling.
Simulates Mixed Microbial Cultures (MMC) for acidogenesis and feast/famine PHA biosynth
using Monod-Haldane inhibition kinetics, undissociated acid equilibria, and RK4 integration.
"""

from dataclasses import dataclass, field
from typing import Dict, Tuple
import math
from .metabolic_flux import VFAProfile, PHBVCopolymerModel, CopolymerProperties


@dataclass
class KineticParameters:
    # Acidogenesis (Monod + Haldane inhibition)
    mu_max_acid: float = 0.35      # h^-1 (max specific growth rate acidogens)
    k_s_carb: float = 2.5          # g/L (half-saturation constant carbohydrates)
    k_i_carb: float = 120.0        # g/L (Haldane substrate inhibition constant)
    k_i_hvfa: float = 1.8          # g/L (undissociated HVFA inhibition threshold)
    y_vfa_carb: float = 0.72       # g VFA / g carb (yield of volatile fatty acids)
    decay_acid: float = 0.015      # h^-1 (death rate acidogens)

    # Buffering & Carbonate Equilibrium
    caco3_dissolution_rate: float = 0.08  # g/(L*h) dissolution under acidic conditions
    target_buffer_ph: float = 5.8
    buffer_capacity: float = 0.15         # mol H+ absorbed per g CaCO3 dissolved
    pka_vfa: float = 4.76                 # Effective pKa of mixed VFAs

    # PHA Storage (Feast/Famine)
    q_pha_max: float = 0.40        # g PHA / (g active biomass * h)
    k_vfa: float = 0.50            # g/L (affinity constant for VFA)
    k_o2: float = 0.25             # mg/L (dissolved oxygen half-saturation)
    f_pha_max: float = 0.78        # max intracellular PHA fraction (78% DCW)
    y_pha_vfa: float = 0.65        # g PHA / g VFA consumed
    kla_aeration: float = 45.0     # h^-1 (volumetric oxygen transfer coefficient)
    do_sat: float = 8.2            # mg/L (dissolved oxygen saturation at 25°C)


@dataclass
class MicrobialState:
    time_h: float = 0.0
    carbohydrates_g_l: float = 35.0
    vfa_g_l: float = 2.0
    nitrogen_g_l: float = 1.2
    caco3_g_l: float = 12.0
    biomass_acid_g_l: float = 1.5
    biomass_pha_active_g_l: float = 0.8
    pha_stored_g_l: float = 0.05
    ph: float = 6.4
    dissolved_oxygen_mg_l: float = 7.5
    odd_vfa_ratio: float = 0.22    # Fraction of odd-chain VFAs (propionate/valerate)

    @property
    def total_pha_biomass_g_l(self) -> float:
        return self.biomass_pha_active_g_l + self.pha_stored_g_l

    @property
    def pha_fraction(self) -> float:
        total = self.total_pha_biomass_g_l
        return (self.pha_stored_g_l / total) if total > 0 else 0.0

    def get_vfa_profile(self) -> VFAProfile:
        """Splits total VFA into C2, C3, C4, C5 species based on odd_vfa_ratio."""
        odd = self.vfa_g_l * self.odd_vfa_ratio
        even = self.vfa_g_l * (1.0 - self.odd_vfa_ratio)
        return VFAProfile(
            acetate_c2_g_l=round(even * 0.68, 3),
            propionate_c3_g_l=round(odd * 0.75, 3),
            butyrate_c4_g_l=round(even * 0.32, 3),
            valerate_c5_g_l=round(odd * 0.25, 3)
        )

    def predict_copolymer_properties(self) -> CopolymerProperties:
        return PHBVCopolymerModel.predict_from_vfa_profile(self.get_vfa_profile())


class Holon0Engine:
    """Core kinetic engine integrating acidogenesis and PHA accumulation via RK4."""

    def __init__(self, params: KineticParameters = None):
        self.params = params or KineticParameters()

    def calculate_undissociated_vfa(self, vfa_tot: float, ph: float) -> float:
        """Calculates protonated (undissociated) HVFA concentration causing membrane uncoupling."""
        h_plus = 10.0 ** (-ph)
        ka = 10.0 ** (-self.params.pka_vfa)
        return vfa_tot * (h_plus / (h_plus + ka))

    def calculate_ph(self, vfa: float, caco3: float) -> float:
        """Estimates slurry pH based on free VFA concentration and CaCO3 buffer."""
        base_vfa_log = math.log10(max(vfa, 0.05) / 60.0)
        buffer_shift = min(caco3 * 0.12, 1.8)
        raw_ph = self.params.pka_vfa - base_vfa_log * 0.45 + buffer_shift
        return max(4.5, min(raw_ph, 7.8))

    def _derivatives(self, state: MicrobialState, aerated: bool) -> Dict[str, float]:
        """Computes instantaneous time derivatives dY/dt for RK4 integration."""
        p = self.params
        s_carb = max(0.0, state.carbohydrates_g_l)
        vfa = max(0.0, state.vfa_g_l)
        do = max(0.0, state.dissolved_oxygen_mg_l)

        # Undissociated acid inhibition factor
        hvfa = self.calculate_undissociated_vfa(vfa, state.ph)
        inhib_hvfa = p.k_i_hvfa / (p.k_i_hvfa + hvfa)

        # Haldane carbohydrate kinetics
        denom_carb = p.k_s_carb + s_carb + (s_carb ** 2) / p.k_i_carb
        mu_acid = p.mu_max_acid * (s_carb / max(1e-6, denom_carb)) * inhib_hvfa
        if state.ph < 5.0:
            mu_acid *= max(0.0, (state.ph - 4.2) / 0.8)

        r_carb = mu_acid * state.biomass_acid_g_l
        r_vfa_prod = r_carb * p.y_vfa_carb
        r_biomass_acid = (mu_acid - p.decay_acid) * state.biomass_acid_g_l

        # CaCO3 dissolution rate
        r_caco3 = 0.0
        if state.ph < p.target_buffer_ph and state.caco3_g_l > 0:
            r_caco3 = p.caco3_dissolution_rate * ((p.target_buffer_ph - state.ph) / 0.8)

        # Phase 2: Aerobic PHA synthesis / growth
        r_vfa_cons = 0.0
        r_pha_stored = 0.0
        r_biomass_pha = 0.0
        r_do = 0.0

        if aerated:
            monod_o2 = do / (p.k_o2 + do)
            space_factor = max(0.0, 1.0 - (state.pha_fraction / p.f_pha_max))
            q_pha = p.q_pha_max * (vfa / (p.k_vfa + vfa)) * monod_o2 * space_factor

            if state.nitrogen_g_l < 0.5:
                # Feast storage regime under nitrogen limitation
                r_pha_stored = q_pha * state.biomass_pha_active_g_l
                r_vfa_cons = r_pha_stored / p.y_pha_vfa
            else:
                # Combined growth + basal storage regime
                mu_growth = 0.18 * (vfa / (p.k_vfa + vfa)) * monod_o2
                r_biomass_pha = mu_growth * state.biomass_pha_active_g_l
                r_pha_stored = 0.25 * q_pha * state.biomass_pha_active_g_l
                r_vfa_cons = (r_biomass_pha / 0.45) + (r_pha_stored / p.y_pha_vfa)

            r_do = p.kla_aeration * (p.do_sat - do) - (r_vfa_cons * 1.15)
        else:
            r_do = -0.5 * (do / (0.1 + do))

        return {
            "d_carb": -r_carb,
            "d_vfa": r_vfa_prod - r_vfa_cons,
            "d_n": (-0.015 * state.nitrogen_g_l) if aerated else 0.0,
            "d_caco3": -r_caco3,
            "d_x_acid": r_biomass_acid,
            "d_x_pha": r_biomass_pha,
            "d_pha": r_pha_stored,
            "d_do": r_do
        }

    def _apply_delta(self, s: MicrobialState, deriv: Dict[str, float], scale: float) -> MicrobialState:
        new_vfa = max(0.0, s.vfa_g_l + deriv["d_vfa"] * scale)
        new_caco3 = max(0.0, s.caco3_g_l + deriv["d_caco3"] * scale)
        return MicrobialState(
            time_h=s.time_h + scale,
            carbohydrates_g_l=max(0.0, s.carbohydrates_g_l + deriv["d_carb"] * scale),
            vfa_g_l=new_vfa,
            nitrogen_g_l=max(0.0, s.nitrogen_g_l + deriv["d_n"] * scale),
            caco3_g_l=new_caco3,
            biomass_acid_g_l=max(0.1, s.biomass_acid_g_l + deriv["d_x_acid"] * scale),
            biomass_pha_active_g_l=max(0.1, s.biomass_pha_active_g_l + deriv["d_x_pha"] * scale),
            pha_stored_g_l=max(0.0, s.pha_stored_g_l + deriv["d_pha"] * scale),
            ph=self.calculate_ph(new_vfa, new_caco3),
            dissolved_oxygen_mg_l=max(0.1, min(self.params.do_sat, s.dissolved_oxygen_mg_l + deriv["d_do"] * scale)),
            odd_vfa_ratio=s.odd_vfa_ratio
        )

    def step(self, state: MicrobialState, dt_h: float, aerated: bool = False) -> MicrobialState:
        """Advances microbial state by dt_h using 4th-order Runge-Kutta (RK4) integration."""
        k1 = self._derivatives(state, aerated)
        s2 = self._apply_delta(state, k1, dt_h * 0.5)
        k2 = self._derivatives(s2, aerated)
        s3 = self._apply_delta(state, k2, dt_h * 0.5)
        k3 = self._derivatives(s3, aerated)
        s4 = self._apply_delta(state, k3, dt_h)
        k4 = self._derivatives(s4, aerated)

        rk4_deriv = {
            key: (k1[key] + 2.0 * k2[key] + 2.0 * k3[key] + k4[key]) / 6.0
            for key in k1
        }
        return self._apply_delta(state, rk4_deriv, dt_h)
