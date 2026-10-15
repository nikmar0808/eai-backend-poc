import pytest
from pydantic import ValidationError

from app.schemas.meter import SmartMeterPayload


def payload(**overrides):
    data = {
        "meter_id": "MTR-POC2-001",
        "grid_zone": "ZONE-A",
        "readings": [{"timestamp": "2026-10-09T00:00:00Z", "kwh_value": 12.5, "voltage": 230.0}],
    }
    data.update(overrides)
    return data


def reading(**overrides):
    data = {"timestamp": "2026-10-09T00:00:00Z", "kwh_value": 12.5, "voltage": 230.0}
    data.update(overrides)
    return data


def violations(data) -> set[tuple]:
    """The locations of every rule the payload breaks; empty when it is valid."""
    try:
        SmartMeterPayload.model_validate(data)
    except ValidationError as error:
        return {tuple(item["loc"]) for item in error.errors()}
    return set()


def test_a_valid_payload_is_accepted():
    parsed = SmartMeterPayload.model_validate(payload())
    assert parsed.readings[0].timestamp.utcoffset() is not None


def test_unknown_properties_are_ignored():
    assert violations(payload(unexpected="x")) == set()


@pytest.mark.parametrize("length, rejected", [(4, True), (5, False), (20, False), (21, True)])
def test_meter_id_is_five_to_twenty_characters(length, rejected):
    assert (("meter_id",) in violations(payload(meter_id="M" * length))) is rejected


@pytest.mark.parametrize(
    "zone, rejected",
    [("", True), (" ", True), ("   ", True), ("Z", False), ("  ZONE  ", False), ("Z" * 50, False), ("Z" * 51, True)],
    ids=["empty", "one space", "spaces", "one char", "padded", "50 chars", "51 chars"],
)
def test_grid_zone_is_non_blank_and_at_most_fifty_characters(zone, rejected):
    assert (("grid_zone",) in violations(payload(grid_zone=zone))) is rejected


@pytest.mark.parametrize("count, rejected", [(0, True), (1, False), (1000, False), (1001, True)])
def test_readings_hold_one_to_one_thousand_items(count, rejected):
    assert (("readings",) in violations(payload(readings=[reading()] * count))) is rejected


@pytest.mark.parametrize("kwh, rejected", [(-1, True), (0, True), (0.001, False)])
def test_kwh_value_is_strictly_positive(kwh, rejected):
    assert (("readings", 0, "kwh_value") in violations(payload(readings=[reading(kwh_value=kwh)]))) is rejected


@pytest.mark.parametrize(
    "voltage, rejected", [(None, False), (99.99, True), (100, False), (300, False), (300.01, True)]
)
def test_voltage_is_optional_but_between_100_and_300(voltage, rejected):
    assert (("readings", 0, "voltage") in violations(payload(readings=[reading(voltage=voltage)]))) is rejected


@pytest.mark.parametrize(
    "timestamp, rejected",
    [
        ("2026-10-09T00:00:00Z", False),
        ("2026-10-09T05:30:00+05:30", False),
        ("2026-10-09T00:00:00", True),
        ("2026-10-09", True),
        ("not a date", True),
    ],
)
def test_timestamp_needs_a_utc_offset(timestamp, rejected):
    assert (("readings", 0, "timestamp") in violations(payload(readings=[reading(timestamp=timestamp)]))) is rejected


def test_missing_required_fields_are_all_reported():
    assert violations({}) >= {("meter_id",), ("grid_zone",), ("readings",)}
