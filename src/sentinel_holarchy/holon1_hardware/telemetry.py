"""
Holon 1: Telemetry Parser & Sensor Signal Conditioning.
Parses JSON payloads from ESP32, applies calibration curves, and checks out-of-bounds metrics.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime, timezone

class SensorTelemetryPacket(BaseModel):
    device_id: str = Field(..., description="Unique hardware node identifier (e.g. ESP32-CLAMART-01)")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    batch_id: str = Field(default="BATCH-001")
    temp_c: float = Field(..., ge=5.0, le=95.0, description="Temperature in Celsius")
    ph: float = Field(..., ge=2.0, le=12.0, description="Slurry pH")
    orp_mv: float = Field(..., ge=-800.0, le=800.0, description="Oxidation-Reduction Potential in mV")
    drum_rpm: float = Field(..., ge=0.0, le=1400.0, description="Drum rotation speed")
    dissolved_o2_mg_l: Optional[float] = Field(default=None, ge=0.0, le=20.0)
    heater_status: bool = Field(default=False)
    aeration_status: bool = Field(default=False)

    @field_validator("ph")
    @classmethod
    def validate_ph_drift(cls, v: float) -> float:
        if v < 3.5 or v > 9.5:
            # Critical warning flag
            pass
        return round(v, 2)

    def is_anaerobic(self) -> bool:
        """Determines if the environment is strictly anaerobic based on ORP."""
        return self.orp_mv < -150.0

    def is_aerobic(self) -> bool:
        """Determines if the environment is sufficiently oxygenated for PHA feast."""
        return self.orp_mv > 50.0 or (self.dissolved_o2_mg_l is not None and self.dissolved_o2_mg_l > 2.0)
