"""
Holon 1: Hardware Controller & Finite State Machine for Bio-Drum 60L.
Coordinates physical actuators: drum motor (mixing/centrifuge), aeration, heating, and valves.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any, Optional

class DrumState(str, Enum):
    IDLE = "IDLE"
    FEEDING_AND_MACERATION = "FEEDING_AND_MACERATION"
    ACIDOGENESIS_REST = "ACIDOGENESIS_REST"
    CENTRIFUGE_SEPARATION = "CENTRIFUGE_SEPARATION"
    AERATION_PHA_FEAST = "AERATION_PHA_FEAST"
    HARVEST_EXTRACTION = "HARVEST_EXTRACTION"
    FAULT = "FAULT"

@dataclass
class ActuatorSetpoints:
    drum_rpm: float = 0.0
    heating_target_c: float = 28.0
    aeration_pump_pct: float = 0.0
    vfa_transfer_valve: bool = False
    drain_valve: bool = False

class BioDrumStateMachine:
    """State machine managing transitions and actuator commands."""

    def __init__(self):
        self.state: DrumState = DrumState.IDLE
        self.setpoints = ActuatorSetpoints()
        self.time_in_state_h: float = 0.0
        self.fault_reason: Optional[str] = None

    def transition_to(self, new_state: DrumState):
        self.state = new_state
        self.time_in_state_h = 0.0

        if new_state == DrumState.IDLE:
            self.setpoints = ActuatorSetpoints(drum_rpm=0.0, heating_target_c=20.0, aeration_pump_pct=0.0)
        elif new_state == DrumState.FEEDING_AND_MACERATION:
            self.setpoints = ActuatorSetpoints(drum_rpm=45.0, heating_target_c=28.0, aeration_pump_pct=0.0)
        elif new_state == DrumState.ACIDOGENESIS_REST:
            self.setpoints = ActuatorSetpoints(drum_rpm=8.0, heating_target_c=30.0, aeration_pump_pct=0.0)
        elif new_state == DrumState.CENTRIFUGE_SEPARATION:
            self.setpoints = ActuatorSetpoints(drum_rpm=650.0, heating_target_c=25.0, aeration_pump_pct=0.0, vfa_transfer_valve=True)
        elif new_state == DrumState.AERATION_PHA_FEAST:
            self.setpoints = ActuatorSetpoints(drum_rpm=15.0, heating_target_c=26.0, aeration_pump_pct=100.0)
        elif new_state == DrumState.HARVEST_EXTRACTION:
            self.setpoints = ActuatorSetpoints(drum_rpm=800.0, heating_target_c=70.0, aeration_pump_pct=0.0, drain_valve=True)
        elif new_state == DrumState.FAULT:
            self.setpoints = ActuatorSetpoints(drum_rpm=0.0, heating_target_c=20.0, aeration_pump_pct=0.0)

    def update_from_telemetry(self, telemetry: Dict[str, Any], dt_h: float):
        """Monitors safety constraints and advances batch lifecycle."""
        self.time_in_state_h += dt_h

        # Safety trip
        temp = telemetry.get("temp_c", 25.0)
        if temp > 75.0 and self.state != DrumState.HARVEST_EXTRACTION:
            self.fault_reason = f"Over-temperature alarm: {temp}°C"
            self.transition_to(DrumState.FAULT)
            return

        ph = telemetry.get("ph", 6.0)
        if ph < 4.2:
            self.fault_reason = f"Severe acid shock: pH={ph}"
            self.transition_to(DrumState.FAULT)
            return

        # Normal sequence progression
        if self.state == DrumState.FEEDING_AND_MACERATION and self.time_in_state_h >= 2.0:
            self.transition_to(DrumState.ACIDOGENESIS_REST)
        elif self.state == DrumState.ACIDOGENESIS_REST and self.time_in_state_h >= 34.0:
            self.transition_to(DrumState.CENTRIFUGE_SEPARATION)
        elif self.state == DrumState.CENTRIFUGE_SEPARATION and self.time_in_state_h >= 0.5:
            self.transition_to(DrumState.AERATION_PHA_FEAST)
        elif self.state == DrumState.AERATION_PHA_FEAST and self.time_in_state_h >= 36.0:
            self.transition_to(DrumState.HARVEST_EXTRACTION)
        elif self.state == DrumState.HARVEST_EXTRACTION and self.time_in_state_h >= 1.0:
            self.transition_to(DrumState.IDLE)
