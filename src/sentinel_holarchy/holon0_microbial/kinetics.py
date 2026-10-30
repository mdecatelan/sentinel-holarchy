"""
Holon 0: Microbial Kinetics & Metabolic Modeling.
Simulates Mixed Microbial Cultures (MMC) for acidogenesis and feast/famine PHA biosynth.
"""

from dataclasses import dataclass
from typing import Dict, Tuple
import math

@dataclass
class KineticParameters:
    # Acidogenesis
    mu_max_acid: float = 0.35      # h^-1 (max specific growth rate acidogens)
    k_s_carb: float = 2.5          # g/L (half-saturation constant carbohydrates)
    y_vfa_carb: float = 0.72       # g VFA / g carb (yield of volatile fatty acids)
    decay_acid: float = 0.015      # h^-1 (death rate acidogens)

    # Buffering
    caco3_dissolution_rate: float = 0.08  # g/(L*h) dissolution under acidic conditions
    target_buffer_ph: float = 5.8
    buffer_capacity: float = 0.15         # mol H+ absorbed per g CaCO3 dissolved

    # PHA Storage (Feast/Famine)
    q_pha_max: float = 0.40        # g PHA / (g active biomass * h)
    k_vfa: float = 0.50            # g/L (affinity constant for VFA)
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

    @property
    def total_pha_biomass_g_l(self) -> float:
        return self.biomass_pha_active_g_l + self.pha_stored_g_l

    @property
    def pha_fraction(self) -> float:
        total = self.total_pha_biomass_g_l
        return (self.pha_stored_g_l / total) if total > 0 else 0.0

class Holon0Engine:
    """Core kinetic engine integrating acidogenesis and PHA accumulation."""

    def __init__(self, params: KineticParameters = None):
        self.params = params or KineticParameters()

    def calculate_ph(self, vfa: float, caco3: float) -> float:
        """Estimate slurry pH based on free VFA concentration and CaCO3 buffer."""
        # Simple Henderson-Hasselbalch proxy for organic acids + carbonate buffer
        # pKa of acetic acid ~ 4.76
        base_vfa_log = math.log10(max(vfa, 0.05) / 60.0) # approx acetic acid molarity
        buffer_shift = min(caco3 * 0.12, 1.8)
        raw_ph = 4.76 - base_vfa_log * 0.45 + buffer_shift
        return max(4.5, min(raw_ph, 7.8))

    def step(self, state: MicrobialState, dt_h: float, aerated: bool = False) -> MicrobialState:
        """Advance microbial state by time step dt_h."""
        p = self.params

        # Phase 1: Acidogenesis (Carbs -> VFA)
        mu_acid = p.mu_max_acid * (state.carbohydrates_g_l / (p.k_s_carb + state.carbohydrates_g_l))
        # pH inhibition of acidogenesis if pH < 5.0
        if state.ph < 5.0:
            mu_acid *= max(0.0, (state.ph - 4.2) / 0.8)

        carb_consumed = mu_acid * state.biomass_acid_g_l * dt_h
        carb_consumed = min(carb_consumed, state.carbohydrates_g_l)

        vfa_produced = carb_consumed * p.y_vfa_carb
        d_biomass_acid = (mu_acid - p.decay_acid) * state.biomass_acid_g_l * dt_h

        # Buffer dissolution if acidic
        caco3_consumed = 0.0
        if state.ph < p.target_buffer_ph and state.caco3_g_l > 0:
            caco3_consumed = min(p.caco3_dissolution_rate * dt_h, state.caco3_g_l)

        # Phase 2: PHA Storage (Feast under aeration and nitrogen limitation)
        vfa_consumed = 0.0
        d_pha_stored = 0.0
        d_biomass_pha = 0.0
        new_do = state.dissolved_oxygen_mg_l

        if aerated:
            # Oxygen transfer
            do_deficit = p.do_sat - state.dissolved_oxygen_mg_l
            new_do = state.dissolved_oxygen_mg_l + p.kla_aeration * do_deficit * dt_h

            current_f_pha = state.pha_fraction
            space_factor = max(0.0, 1.0 - (current_f_pha / p.f_pha_max))

            # Specific storage rate
            q_pha = p.q_pha_max * (state.vfa_g_l / (p.k_vfa + state.vfa_g_l)) * space_factor
            
            # Nitrogen limitation check
            if state.nitrogen_g_l < 0.2:
                # Strong feast storage mode
                d_pha_stored = q_pha * state.biomass_pha_active_g_l * dt_h
                vfa_consumed = d_pha_stored / p.y_pha_vfa
            else:
                # Biomass growth mode
                mu_growth = 0.18 * (state.vfa_g_l / (p.k_vfa + state.vfa_g_l))
                d_biomass_pha = mu_growth * state.biomass_pha_active_g_l * dt_h
                vfa_consumed = (d_biomass_pha / 0.45)
            
            vfa_consumed = min(vfa_consumed, state.vfa_g_l)
            d_pha_stored = min(d_pha_stored, vfa_consumed * p.y_pha_vfa)
            new_do = max(0.5, new_do - (vfa_consumed * 1.2))
        else:
            new_do = max(0.1, state.dissolved_oxygen_mg_l - 0.5 * dt_h)

        new_carbs = max(0.0, state.carbohydrates_g_l - carb_consumed)
        new_vfa = max(0.0, state.vfa_g_l + vfa_produced - vfa_consumed)
        new_caco3 = max(0.0, state.caco3_g_l - caco3_consumed)
        new_ph = self.calculate_ph(new_vfa, new_caco3)

        return MicrobialState(
            time_h=state.time_h + dt_h,
            carbohydrates_g_l=new_carbs,
            vfa_g_l=new_vfa,
            nitrogen_g_l=max(0.0, state.nitrogen_g_l - (0.01 * dt_h if aerated else 0.0)),
            caco3_g_l=new_caco3,
            biomass_acid_g_l=max(0.1, state.biomass_acid_g_l + d_biomass_acid),
            biomass_pha_active_g_l=max(0.1, state.biomass_pha_active_g_l + d_biomass_pha),
            pha_stored_g_l=max(0.0, state.pha_stored_g_l + d_pha_stored),
            ph=new_ph,
            dissolved_oxygen_mg_l=new_do
        )
