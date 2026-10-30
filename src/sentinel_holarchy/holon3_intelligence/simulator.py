"""
Holon 3: Mechanistic Digital Twin Simulator.
White-box biophysical model computing batch kinetics, heat transfer, shear drag, and economics.
"""

import math
from typing import Dict, Any, List
from .knowledge_ledger import KnowledgeLedgerManager

class DigitalTwinSimulator:
    """Core physics and biology simulation engine."""

    def __init__(self, intrant_type: str = "organique", ledger_file: str = "knowledge_ledger.json"):
        self.intrant_type = intrant_type.lower()
        self.ledger = KnowledgeLedgerManager(ledger_file)
        self.reset_state()

    def reset_state(self):
        self.t = 0.0
        self.t_total = 72.0
        self.step_hours = 1.0
        self.is_running = False

        # Physical constants
        self.N_rpm = 15.0
        self.T_amb = 20.0
        self.theta = 45.0
        self.T_current = 20.0

        # State Variables
        self.V_biomass = 1000.0  # g initial biomass/feedstock
        self.V_liquid = 45.0     # L liquid volume
        self.VFA = 2.0           # g/L
        self.GradeA_PHA = 0.0    # g accumulated PHA
        self.GradeB_Bio = 0.0    # L biostimulant
        self.GradeC_Comp = 0.0   # kg solid compost

        # Environmental & Economic tracking
        self.C_capital = 2500.0
        self.P_env = 0.0

    def step(self, dt_h: float = 1.0) -> Dict[str, Any]:
        """Calculates 1 step of biophysical evolution."""
        self.t += dt_h

        # Experience factor from ledger
        exp_factor = self.ledger.calculate_experience_factor(self.intrant_type)

        # Thermal dynamics
        q_shear = 0.001 * (self.N_rpm ** 1.8)
        self.T_current += (q_shear - 0.05 * (self.T_current - self.T_amb)) * dt_h
        self.T_current = max(18.0, min(self.T_current, 38.0))

        # Two-phase kinetics
        if self.t <= 36.0:
            # Acidogenesis: Biomass -> VFA
            rate_hydrolysis = 0.025 * exp_factor * (self.T_current / 25.0)
            converted = min(self.V_biomass, self.V_biomass * rate_hydrolysis * dt_h)
            self.V_biomass -= converted
            self.VFA += (converted * 0.65) / self.V_liquid
            self.GradeC_Comp += (converted * 0.20) / 1000.0
        else:
            # PHA Storage under aeration
            rate_pha = 0.045 * exp_factor * min(self.VFA, 5.0)
            pha_formed = rate_pha * dt_h * (self.V_liquid / 10.0)
            self.GradeA_PHA += pha_formed
            self.VFA = max(0.2, self.VFA - pha_formed * 1.4 / self.V_liquid)
            self.GradeB_Bio = round(self.V_liquid * 0.88, 2)

        return self.get_telemetry()

    def get_telemetry(self) -> Dict[str, Any]:
        return {
            "time_h": round(self.t, 1),
            "temp_c": round(self.T_current, 2),
            "drum_rpm": self.N_rpm,
            "vfa_g_l": round(self.VFA, 2),
            "grade_a_pha_g": round(self.GradeA_PHA, 2),
            "grade_b_biostimulant_l": round(self.GradeB_Bio, 2),
            "grade_c_compost_kg": round(self.GradeC_Comp, 3),
            "capital_eur": round(self.C_capital, 2),
            "progress_pct": round(min(100.0, (self.t / self.t_total) * 100.0), 1)
        }
