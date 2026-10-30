"""Tests for Holon 1: Hardware Controller & Telemetry Handling."""

import pytest
from sentinel_holarchy.holon1_hardware.controller import BioDrumStateMachine, DrumState
from sentinel_holarchy.holon1_hardware.telemetry import SensorTelemetryPacket

def test_state_machine_nominal_flow():
    fsm = BioDrumStateMachine()
    assert fsm.state == DrumState.IDLE

    # Transition to feeding
    fsm.transition_to(DrumState.FEEDING_AND_MACERATION)
    assert fsm.setpoints.drum_rpm == 45.0
    assert fsm.setpoints.aeration_pump_pct == 0.0

    # Advance 2 hours -> should transition to ACIDOGENESIS_REST
    telemetry = {"temp_c": 28.0, "ph": 6.2}
    fsm.update_from_telemetry(telemetry, dt_h=2.1)
    assert fsm.state == DrumState.ACIDOGENESIS_REST
    assert fsm.setpoints.drum_rpm == 8.0

def test_state_machine_thermal_safety_trip():
    fsm = BioDrumStateMachine()
    fsm.transition_to(DrumState.ACIDOGENESIS_REST)

    # Trigger dangerous overtemp
    telemetry = {"temp_c": 82.0, "ph": 5.8}
    fsm.update_from_telemetry(telemetry, dt_h=0.1)

    assert fsm.state == DrumState.FAULT
    assert "Over-temperature alarm" in fsm.fault_reason
    assert fsm.setpoints.drum_rpm == 0.0

def test_telemetry_packet_validation():
    packet = SensorTelemetryPacket(
        device_id="ESP32-TEST",
        temp_c=28.5,
        ph=5.85,
        orp_mv=-220.0,
        drum_rpm=12.0
    )
    assert packet.is_anaerobic() is True
    assert packet.is_aerobic() is False

    # Out of bounds pH should raise validation error
    with pytest.raises(Exception):
        SensorTelemetryPacket(
            device_id="ESP32-TEST",
            temp_c=25.0,
            ph=14.5,
            orp_mv=0.0,
            drum_rpm=0.0
        )
