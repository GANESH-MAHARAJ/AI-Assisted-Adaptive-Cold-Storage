from pydantic import BaseModel, Field, field_validator
from typing import Optional

from datetime import datetime, timezone

class TrayReading(BaseModel):
    temp: float
    humidity: float
    co2ppm: float
    ethyleneppm: float
    weight: float

class RackSnapshot(BaseModel):
    tray1: TrayReading
    tray2: TrayReading

    @field_validator("tray1", "tray2")
    @classmethod
    def sane(cls, v: TrayReading):
        # pass-through (we’ll clamp elsewhere if needed)
        return v

class ActuatorCommand(BaseModel):
    rackACvalve: int = Field(0, ge=0, le=1)
    rackHumidifiervalve: int = Field(0, ge=0, le=1)
    tray1fanspeed: int = Field(0, ge=0, le=255)
    tray2fanspeed: int = Field(0, ge=0, le=255)

class AgentDecision(BaseModel):
    actuators: ActuatorCommand
    rationale: Optional[str] = ""
