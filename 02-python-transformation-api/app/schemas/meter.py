import re
from datetime import datetime
from typing import List, Optional

from pydantic import AwareDatetime, BaseModel, Field, field_validator

# One rule set, written in docs/api/README.md and enforced identically by the gateway (ADR-011, Stage 6).
# The timestamp rule is the same regular expression as the gateway's StrictOffsetDateTimeDeserializer and the
# contracts: RFC 3339, an offset is mandatory, within -14:00 and +14:00, at most six fractional digits.
# re.ASCII: \d means 0-9 only (in Python's default Unicode mode it would also accept other scripts' digits).
TIMESTAMP_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?(Z|[+-](0\d|1[0-3]):[0-5]\d|[+-]14:00)", re.ASCII
)
# Identifiers are printable ASCII (findings D39, D45): no control characters (PostgreSQL text cannot store NUL), and
# one character is one UTF-16 code unit, so the gateway's @Size, the contract and len() here agree on every length.
METER_ID_PATTERN = r"^[\x21-\x7E]+$"                      # no spaces
GRID_ZONE_PATTERN = r"^[\x20-\x7E]*[\x21-\x7E][\x20-\x7E]*$"   # spaces allowed, at least one visible character


class MeterReading(BaseModel):
    """One interval reading. The rules are those of docs/api/README.md."""

    timestamp: AwareDatetime = Field(
        description="RFC 3339 date-time string with a UTC offset within -14:00 and +14:00. A number is refused."
    )
    # strict=True: a JSON number only. Lax mode would turn the string "12.5" into 12.5 (finding D48); a JSON integer
    # such as 300 is still accepted, because strict floats accept integers.
    kwh_value: float = Field(
        strict=True, gt=0.0, le=1000000.0, description="Active energy consumption in kWh, above 0, at most 1e6."
    )
    voltage: Optional[float] = Field(
        default=None, strict=True, ge=100.0, le=300.0, description="Optional grid voltage, 100 to 300."
    )

    # mode="before": runs on the value as it arrived, BEFORE Pydantic converts it. Pydantic would otherwise turn the
    # number 0 into 1970-01-01 (finding D29) and accept offsets up to +-23:59 (finding D37).
    @field_validator("timestamp", mode="before")
    @classmethod
    def timestamp_must_be_an_rfc3339_string(cls, value: object) -> object:
        # A datetime object can only come from Python code (tests, other modules), never from JSON; it is let through.
        if isinstance(value, datetime):
            return value
        if not isinstance(value, str) or TIMESTAMP_PATTERN.fullmatch(value) is None:
            raise ValueError("timestamp must be an RFC 3339 date-time string with an offset between -14:00 and +14:00")
        return value


class SmartMeterPayload(BaseModel):
    """The bulk payload. The rules are those of docs/api/README.md."""

    meter_id: str = Field(
        min_length=5, max_length=20, pattern=METER_ID_PATTERN, description="Unique utility asset identifier."
    )
    grid_zone: str = Field(
        min_length=1, max_length=50, pattern=GRID_ZONE_PATTERN, description="Grid zone code; a visible character."
    )
    readings: List[MeterReading] = Field(min_length=1, max_length=1000, description="Between 1 and 1000 readings.")
