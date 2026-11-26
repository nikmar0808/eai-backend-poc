"""
What this file protects. The event is a contract other teams build on (Stage 1). Whatever the database hands back,
the dictionary that goes into the outbox must match docs/api/events/readings-stored.schema.json: times in UTC, voltage
always present, readings in time order, a lower-case UUID. A unit test can check all of this without a database,
because building the event is a pure function: same input, same output, nothing else touched.

New ideas used here.
- `SimpleNamespace(timestamp=..., kwh_value=...)` is a plain object with those attributes. It stands in for a row of
  the INSERT's RETURNING result, which has the same attributes.
- A fixed `uuid.UUID(...)` instead of a random one, so the expected event can be written out in full.
"""
import json                                          # to read the contract's example file
import uuid
from datetime import datetime, timedelta, timezone   # timedelta builds a fixed offset such as +05:30
from types import SimpleNamespace                    # a plain object with named attributes: a stand-in database row

# The code under test, and the contract helper of tests/event_schema.py.
from app.services.events import readings_stored_event, utc_text
from tests.event_schema import EXAMPLE_FILE, contract_errors

INDIA = timezone(timedelta(hours=5, minutes=30))     # the database session's time zone in this project
# Written in upper case on purpose: the event must still carry it in lower case.
EVENT_ID = uuid.UUID("6F1C2D4E-8A7B-4C3D-9E1F-2A3B4C5D6E7F")


def row(timestamp: datetime, kwh: float, voltage: float | None) -> SimpleNamespace:
    """One stand-in RETURNING row, with the three attributes readings_stored_event reads."""
    return SimpleNamespace(timestamp=timestamp, kwh_value=kwh, voltage=voltage)


def test_the_event_is_built_exactly_as_the_contract_shows():
    # Arrange: two rows as the database might return them, out of time order and in India time.
    stored = [
        row(datetime(2026, 11, 25, 5, 45, tzinfo=INDIA), 1.2, None),     # returned first, but the later reading
        row(datetime(2026, 11, 25, 5, 30, tzinfo=INDIA), 1.5, 231.0),
    ]

    # Act: datetime(..., 345000, ...) is 10:00:12.345 India time (the 7th argument is microseconds).
    event = readings_stored_event(EVENT_ID, datetime(2026, 11, 25, 10, 0, 12, 345000, tzinfo=INDIA), "MTR-0001", "SOUTH-01", stored)

    # Assert: the whole event, field by field. == on two dicts compares every key and value.
    assert event == {
        "event_id": "6f1c2d4e-8a7b-4c3d-9e1f-2a3b4c5d6e7f",              # lower case, as the schema's pattern asks
        "occurred_at": "2026-11-25T04:30:12.345000Z",                     # 10:00:12.345 India time, written in UTC
        "meter_id": "MTR-0001",
        "grid_zone": "SOUTH-01",
        "readings": [                                                     # sorted by time
            {"timestamp": "2026-11-25T00:00:00Z", "kwh_value": 1.5, "voltage": 231.0},
            {"timestamp": "2026-11-25T00:15:00Z", "kwh_value": 1.2, "voltage": None},   # None becomes JSON null
        ],
    }
    assert contract_errors(event) == []                                  # and the contract accepts it


def test_the_event_has_the_same_fields_as_the_contracts_own_example():
    example = json.loads(EXAMPLE_FILE.read_text(encoding="utf-8"))
    event = readings_stored_event(EVENT_ID, datetime.now(timezone.utc), "MTR-0001", "SOUTH-01",
                                  [row(datetime.now(timezone.utc), 1.0, 230.0)])

    # .keys() compares the sets of field names, ignoring order: a renamed or added field on either side fails here.
    assert event.keys() == example.keys()
    assert event["readings"][0].keys() == example["readings"][0].keys()


def test_utc_text_writes_the_same_moment_in_utc():
    assert utc_text(datetime(2026, 11, 25, 0, 0, tzinfo=INDIA)) == "2026-11-24T18:30:00Z"   # India midnight
    assert utc_text(datetime(2026, 11, 25, 0, 0, tzinfo=timezone.utc)) == "2026-11-25T00:00:00Z"
    # Microseconds are kept when there are any.
    assert utc_text(datetime(2026, 11, 25, 0, 0, 0, 123456, tzinfo=timezone.utc)) == "2026-11-25T00:00:00.123456Z"


def test_a_broken_event_is_caught_by_the_contract_check():
    """The check itself is proved, with an event that must fail (Stage 1: prove every check with a failing example)."""
    event = readings_stored_event(EVENT_ID, datetime.now(timezone.utc), "MTR-0001", "SOUTH-01",
                                  [row(datetime.now(timezone.utc), 1.0, None)])
    del event["readings"][0]["voltage"]              # break it on purpose: the schema requires the field

    # The exact message, so a check that silently stopped working would also fail this test.
    assert contract_errors(event) == ["readings/0: 'voltage' is a required property"]
