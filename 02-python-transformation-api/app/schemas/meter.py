from typing import List, Optional

from pydantic import AwareDatetime, BaseModel, Field

# By inheriting from Pydantic's BaseModel, we are telling Python: "This isn't just a regular class. This is a strict enterprise data contract."
class MeterReading(BaseModel):
    """
    Validates individual smart-meter telemetry metrics intervals.
    One interval reading. The rules are those of docs/api/README.md.
    """
    timestamp: AwareDatetime = Field(description="RFC 3339 date-time with a UTC offset. A naive time is rejected.")
    kwh_value: float = Field(gt=0.0, le=1000000.0, description="Active energy consumption in kWh. Strictly greater than zero, and at most 1000000 kWh.")
    voltage: Optional[float] = Field(default=None, ge=100.0, le=300.0, description="Optional grid voltage, 100 to 300.")


class SmartMeterPayload(BaseModel):
    """
    Defines the structural boundary contract for raw bulk grid transmissions.
    The bulk payload. The rules are those of docs/api/README.md.
    """
    meter_id: str = Field(min_length=5, max_length=20, description="Unique utility asset identifier.")
    grid_zone: str = Field(
        min_length=1, max_length=50, pattern=r"\S", description="Grid zone code; must contain a non-space character."
    )
    readings: List[MeterReading] = Field(min_length=1, max_length=1000, description="Between 1 and 1000 readings.")
