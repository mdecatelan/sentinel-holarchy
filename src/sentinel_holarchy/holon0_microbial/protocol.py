"""
Holon 0: Execution Protocol Runner.
Orchestrates the 72h bio-conversion cycle: Acidogenesis -> Separation -> Feast/Famine PHA -> Harvest.
"""

from typing import Dict, List, Any
from .kinetics import Holon0Engine, MicrobialState, KineticParameters
from .biomass import HouseholdSubstrateFormulator

class BatchCycleRunner:
    """Executes the 72h bioprocess cycle step-by-step."""

    def __init__(self, formulator: HouseholdSubstrateFormulator = None, engine: Holon0Engine = None):
        self.formulator = formulator or HouseholdSubstrateFormulator()
        if not self.formulator.ingredients:
            self.formulator.load_default_clamart_batch()
        self.engine = engine or Holon0Engine()

    def run_cycle(self, total_hours: float = 72.0, dt_h: float = 1.0) -> Dict[str, Any]:
        props = self.formulator.compute_mixture_properties()

        # Initial state setup
        state = MicrobialState(
            time_h=0.0,
            carbohydrates_g_l=props["carbohydrates_g_L"],
            vfa_g_l=1.0,
            nitrogen_g_l=props["nitrogen_g_L"],
            caco3_g_l=props["caco3_g_L"],
            biomass_acid_g_l=1.2,
            biomass_pha_active_g_l=0.5,
            pha_stored_g_l=0.02,
            ph=6.5,
            dissolved_oxygen_mg_l=7.0
        )

        history: List[Dict[str, float]] = []
        phase = "PHASE_1_ACIDOGENESIS"

        current_t = 0.0
        while current_t < total_hours:
            # At 36h: Transition from acidogenesis to Feast/Famine PHA accumulation
            # In physical reality: Solids are filtered (Grade C), liquid is transferred to PHA tank and aerated
            if current_t >= 36.0 and phase == "PHASE_1_ACIDOGENESIS":
                phase = "PHASE_2_FEAST_FAMINE_PHA"
                # Dilution / inoculation adjustment
                state.nitrogen_g_l = max(0.05, state.nitrogen_g_l * 0.15) # Nitrogen limited
                state.biomass_pha_active_g_l = max(state.biomass_pha_active_g_l, 1.2) # Inoculum added

            aerated = (phase == "PHASE_2_FEAST_FAMINE_PHA")
            state = self.engine.step(state, dt_h, aerated=aerated)
            current_t += dt_h

            history.append({
                "time_h": round(state.time_h, 1),
                "phase": phase,
                "carbohydrates_g_l": round(state.carbohydrates_g_l, 2),
                "vfa_g_l": round(state.vfa_g_l, 2),
                "pha_stored_g_l": round(state.pha_stored_g_l, 3),
                "pha_fraction_pct": round(state.pha_fraction * 100.0, 1),
                "ph": round(state.ph, 2),
                "dissolved_oxygen_mg_l": round(state.dissolved_oxygen_mg_l, 2)
            })

        # Calculate yields for the batch volume
        vol_L = props["liquid_volume_L"]
        yield_pha_g = round(state.pha_stored_g_l * vol_L, 1)
        yield_biostimulant_L = round(vol_L * 0.85, 2)
        yield_compost_solid_g = round(props["inert_fibers_g_L"] * vol_L + 150.0, 1)

        return {
            "volume_L": vol_L,
            "final_pha_g": yield_pha_g,
            "final_pha_fraction_pct": round(state.pha_fraction * 100.0, 1),
            "final_biostimulant_L": yield_biostimulant_L,
            "final_compost_solid_g": yield_compost_solid_g,
            "final_ph": round(state.ph, 2),
            "history": history
        }
