"""
What this file protects, and why a table of values. The models carry the contract's rules as constraints. A
constraint is easy to get subtly wrong (`min_length=6` instead of 5, `ge` instead of `gt`) and nothing fails
until a real client sends a boundary value. The cheapest test asks the model itself, with no server and no
database, and asks it *at the boundaries* (A9 question 4): for "5 to 20 characters" the values that matter
are 4, 5, 20 and 21.

New ideas used here.
- `model_validate(data)` builds the model from a dictionary and raises `ValidationError` if any rule is
  broken. `error.errors()` lists every broken rule with its `loc` (A7).
- A helper that returns the set of broken locations (`violations`) lets each test ask a precise question:
  "is `("meter_id",)` among them?". One bad field cannot hide behind another.
- `@pytest.mark.parametrize` (A4): one function, many rows. `ids=[...]` gives rows readable labels.
- `assert (x in y) is rejected`: comparing with `is` against the expected boolean makes both directions of
  the table (must be rejected, must be accepted) one line.
"""
import pytest
from pydantic import ValidationError          # raised by model_validate when any rule is broken

from app.schemas.meter import SmartMeterPayload   # the model under test; MeterReading is reached through it


def payload(**overrides):
    """A valid payload; a test overrides only the field it is about. Keeping the rest valid means a failure
    can only come from the field under test."""
    data = {
        "meter_id": "MTR-POC2-001",
        "grid_zone": "ZONE-A",
        "readings": [{"timestamp": "2026-10-09T00:00:00Z", "kwh_value": 12.5, "voltage": 230.0}],
    }
    data.update(overrides)
    return data


def reading(**overrides):
    """One valid reading, with overrides."""
    data = {"timestamp": "2026-10-09T00:00:00Z", "kwh_value": 12.5, "voltage": 230.0}
    data.update(overrides)
    return data


def violations(data) -> set[tuple]:
    """The locations of every rule the payload breaks; an empty set when it is valid.

    A 'loc' is a tuple such as ("readings", 0, "kwh_value"): the 0 is the index in the list (A7)."""
    try:
        SmartMeterPayload.model_validate(data)
    except ValidationError as error:
        return {tuple(item["loc"]) for item in error.errors()}
    return set()


def test_a_valid_payload_is_accepted():                                                   # P01
    parsed = SmartMeterPayload.model_validate(payload())
    assert parsed.readings[0].timestamp.utcoffset() is not None     # the parsed time still knows its offset


def test_unknown_properties_are_ignored():                                                # P02
    # Pydantic's default is to ignore extra keys; the contract does not forbid them. If the model is ever set to
    # reject them, this test fails and the contract must be changed in the same pull request.
    assert violations(payload(unexpected="x")) == set()


# Each tuple is (the parameter values for one run). "rejected" is the EXPECTED outcome for that value.
@pytest.mark.parametrize("length, rejected", [(4, True), (5, False), (20, False), (21, True)])   # P03: 4 runs
def test_meter_id_is_five_to_twenty_characters(length, rejected):
    assert (("meter_id",) in violations(payload(meter_id="M" * length))) is rejected


@pytest.mark.parametrize(                                                                 # P04: 7 runs
    "zone, rejected",
    [("", True), (" ", True), ("   ", True), ("Z", False), ("  ZONE  ", False), ("Z" * 50, False), ("Z" * 51, True)],
    ids=["empty", "one space", "spaces", "one char", "padded", "50 chars", "51 chars"],
)
def test_grid_zone_is_non_blank_and_at_most_fifty_characters(zone, rejected):
    assert (("grid_zone",) in violations(payload(grid_zone=zone))) is rejected


@pytest.mark.parametrize("count, rejected", [(0, True), (1, False), (1000, False), (1001, True)])   # P05: 4 runs
def test_readings_hold_one_to_one_thousand_items(count, rejected):
    assert (("readings",) in violations(payload(readings=[reading()] * count))) is rejected


@pytest.mark.parametrize("kwh, rejected", [(-1, True), (0, True), (0.001, False)])        # P06: 3 runs
def test_kwh_value_is_strictly_positive(kwh, rejected):
    assert (("readings", 0, "kwh_value") in violations(payload(readings=[reading(kwh_value=kwh)]))) is rejected


@pytest.mark.parametrize("kwh, rejected", [(1000000.0, False), (1000000.01, True)])     # P06b: 2 runs
def test_kwh_value_has_an_upper_bound(kwh, rejected):
    assert (("readings", 0, "kwh_value") in violations(payload(readings=[reading(kwh_value=kwh)]))) is rejected


@pytest.mark.parametrize(                                                                 # P07: 5 runs
    "voltage, rejected", [(None, False), (99.99, True), (100, False), (300, False), (300.01, True)]
)
def test_voltage_is_optional_but_between_100_and_300(voltage, rejected):
    assert (("readings", 0, "voltage") in violations(payload(readings=[reading(voltage=voltage)]))) is rejected


@pytest.mark.parametrize(                                                                 # P08: 5 runs
    "timestamp, rejected",
    [
        ("2026-10-09T00:00:00Z", False),          # "Z" = UTC
        ("2026-10-09T05:30:00+05:30", False),     # an explicit offset
        ("2026-10-09T00:00:00", True),            # no offset: a naive time is rejected (AwareDatetime)
        ("2026-10-09", True),                     # a date only
        ("not a date", True),
    ],
)
def test_timestamp_needs_a_utc_offset(timestamp, rejected):
    assert (("readings", 0, "timestamp") in violations(payload(readings=[reading(timestamp=timestamp)]))) is rejected


def test_missing_required_fields_are_all_reported():                                      # P09
    # ">=" on sets means "contains at least these": every missing field is reported at once, not one per attempt.
    assert violations({}) >= {("meter_id",), ("grid_zone",), ("readings",)}
