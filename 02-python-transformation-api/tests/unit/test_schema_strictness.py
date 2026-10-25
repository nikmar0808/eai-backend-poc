r"""Stage 6 rules of the payload model, at unit level (P42 to P45, P52).

New ideas: a "before" validator sees the value as it arrived (a number stays a number), so it can refuse what Pydantic
would otherwise convert; one rule is written once and tested at its boundary (+14:00 accepted, +14:30 refused);
exactly one control character is placed in an identifier, which is what a loose pattern (\S for "visible") lets through.
"""

import pytest
from pydantic import ValidationError

from app.schemas.meter import SmartMeterPayload


def payload(timestamp: object = "2026-10-09T00:00:00Z", **fields: object) -> dict[str, object]:
    body: dict[str, object] = {
        "meter_id": "MTR-POC2-001",
        "grid_zone": "ZONE-A",
        "readings": [{"timestamp": timestamp, "kwh_value": 12.5}],
    }
    body.update(fields)
    return body


def failing_locations(body: dict[str, object]) -> set[tuple[object, ...]]:
    with pytest.raises(ValidationError) as caught:
        SmartMeterPayload.model_validate(body)
    return {tuple(error["loc"]) for error in caught.value.errors()}


@pytest.mark.parametrize("value", [0, 1760000000])
def test_a_number_is_refused_as_a_timestamp(value):                                   # P42, D29 (2)
    assert ("readings", 0, "timestamp") in failing_locations(payload(timestamp=value))


@pytest.mark.parametrize("offset", ["+14:30", "-15:00"])
def test_an_offset_beyond_fourteen_hours_is_refused(offset):                          # P43, D37 (2)
    assert ("readings", 0, "timestamp") in failing_locations(payload(timestamp="2026-10-09T00:00:00" + offset))


def test_an_offset_of_exactly_fourteen_hours_is_accepted():                           # P44, boundary
    SmartMeterPayload.model_validate(payload(timestamp="2026-10-09T00:00:00+14:00"))


@pytest.mark.parametrize(
    "field, value",
    [("grid_zone", "ZONE\x00A"), ("meter_id", "MTR\x01POC2"), ("meter_id", "MTR-\U0001F600-01")],
    ids=["NUL in grid_zone", "U+0001 in meter_id", "a character above U+FFFF in meter_id"],
)
def test_a_control_character_in_an_identifier_is_refused(field, value):               # P45, D39, D45 (3)
    # The third case is one character for len() and two UTF-16 code units for the gateway's @Size; identifiers are
    # printable ASCII, so both services refuse it.
    assert (field,) in failing_locations(payload(**{field: value}))


@pytest.mark.parametrize("field", ["kwh_value", "voltage"])
def test_a_number_sent_as_a_string_is_refused(field):                                 # P52, D48 (2)
    body = payload()
    body["readings"] = [{"timestamp": "2026-10-09T00:00:00Z", "kwh_value": 12.5, field: "230"}]
    assert ("readings", 0, field) in failing_locations(body)
