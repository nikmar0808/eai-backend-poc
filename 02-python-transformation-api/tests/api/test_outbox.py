"""
What this file protects. The outbox is a promise to every consumer: one event for every batch that stored readings,
carrying exactly those readings, and nothing else. The faults that matter: an event for nothing (only duplicates, or a
repeated idempotency key), an event that lists a reading that was already there, an event without its readings or
readings without their event (the dual-write problem the outbox exists to prevent), and an event that breaks the
contract. Each test sends real requests through the application to the real migrated database.

New ideas used here.
- `db_session.scalars(select(OutboxRecord)...)` reads the outbox rows the route wrote. The route's commit() only
  released a savepoint (conftest.py), so the rows are visible to this session and are thrown away after the test.
- `monkeypatch.setattr("app.services.ingestion.readings_stored_event", ...)` makes building the event fail AFTER the
  readings INSERT has already run, to prove that the rollback takes the readings away as well.
"""
from datetime import datetime                  # to read the event's occurred_at text back into a moment

import pytest
from sqlalchemy import func, select            # select(...) builds a SELECT; func.count() is SQL's count(*)

from app.database.models import OutboxRecord, SmartMeterIntervalRecord
from tests.event_schema import contract_errors     # the Stage 1 contract, as a checking function

pytestmark = pytest.mark.db                    # every test here needs PostgreSQL (the "db" marker of pytest.ini)

URL = "/api/v1/transform"


def reading(at: str, kwh: float, voltage: float | None = None) -> dict:
    """One reading as a client sends it. With voltage=None the field is left out, as a client may do."""
    value: dict = {"timestamp": at, "kwh_value": kwh}
    if voltage is not None:
        value["voltage"] = voltage
    return value


def body(meter_id: str, *readings: dict) -> dict:
    """A request body. *readings collects any number of reading(...) arguments into one tuple."""
    return {"meter_id": meter_id, "grid_zone": "ZONE-A", "readings": list(readings)}


def events_for(db_session, meter_id: str) -> list[OutboxRecord]:
    """Every outbox row for one meter. Each test uses its own meter ID, so tests never see each other's rows."""
    return list(db_session.scalars(                # scalars(...): the OutboxRecord objects, not raw rows
        select(OutboxRecord).where(OutboxRecord.aggregateid == meter_id).order_by(OutboxRecord.created_at)
    ))


def reading_count(db_session, meter_id: str) -> int:
    """SELECT count(*) FROM smart_meter_intervals WHERE meter_id = :meter_id"""
    return db_session.scalar(
        select(func.count()).select_from(SmartMeterIntervalRecord).where(SmartMeterIntervalRecord.meter_id == meter_id)
    )


# The fixtures in each test's arguments come from conftest.py: client = the application in memory, auth_headers = the
# X-EAI-TOKEN header, db_session = the rolling-back session the application also uses, monkeypatch = pytest's own.

def test_a_stored_batch_writes_one_event_with_its_readings(client, auth_headers, db_session):
    response = client.post(URL, headers=auth_headers, json=body(
        "MTR-OUTBOX-01",
        reading("2026-11-25T05:30:00+05:30", 1.5, 231.0),       # India time: the event says 00:00Z
        reading("2026-11-25T00:15:00Z", 1.2),                   # no voltage: the event says null
    ))

    assert response.status_code == 200
    [event] = events_for(db_session, "MTR-OUTBOX-01")           # exactly one row, or this line fails
    assert (event.aggregatetype, event.type) == ("meter-readings", "ReadingsStored")
    assert event.payload["event_id"] == str(event.id)           # the row's key and the event's ID are one value
    assert event.payload["readings"] == [
        {"timestamp": "2026-11-25T00:00:00Z", "kwh_value": 1.5, "voltage": 231.0},
        {"timestamp": "2026-11-25T00:15:00Z", "kwh_value": 1.2, "voltage": None},
    ]
    assert contract_errors(event.payload) == []                 # the real event keeps the Stage 1 contract


def test_only_the_new_readings_are_in_the_event(client, auth_headers, db_session):
    first = reading("2026-11-25T00:00:00Z", 1.0, 230.0)
    client.post(URL, headers=auth_headers, json=body("MTR-OUTBOX-02", first))       # stores 00:00

    # The same 00:00 reading again (a repeat) plus a new 00:15 one.
    client.post(URL, headers=auth_headers, json=body("MTR-OUTBOX-02", first, reading("2026-11-25T00:15:00Z", 2.0, 229.0)))

    # Both requests ran inside one test transaction, so both rows have the same created_at: compare as a set.
    # For each event, the list of its readings' times; then the two lists sorted, so their order does not matter.
    times = sorted([r["timestamp"] for r in event.payload["readings"]] for event in events_for(db_session, "MTR-OUTBOX-02"))
    assert times == [["2026-11-25T00:00:00Z"], ["2026-11-25T00:15:00Z"]]     # the second event: only the new one


def test_a_batch_of_only_duplicates_writes_no_event(client, auth_headers, db_session):
    same = body("MTR-OUTBOX-03", reading("2026-11-25T00:00:00Z", 1.0))
    client.post(URL, headers=auth_headers, json=same)

    again = client.post(URL, headers=auth_headers, json=same)    # no key: the readings table itself skips the repeat

    assert again.json()["metadata"]["duplicates_ignored"] == 1
    assert len(events_for(db_session, "MTR-OUTBOX-03")) == 1    # still only the first batch's event


def test_a_repeat_with_the_same_key_writes_no_second_event(client, auth_headers, db_session):
    # {**auth_headers, ...}: a new dict with every entry of auth_headers plus one more.
    headers = {**auth_headers, "Idempotency-Key": "key-outbox-1"}
    same = body("MTR-OUTBOX-04", reading("2026-11-25T00:00:00Z", 1.0))

    client.post(URL, headers=headers, json=same)
    client.post(URL, headers=headers, json=same)                # the key is found: the first answer, nothing stored

    assert len(events_for(db_session, "MTR-OUTBOX-04")) == 1


def test_a_failure_after_storing_leaves_neither_readings_nor_event(client, auth_headers, db_session, monkeypatch):
    def failing_event(*args, **kwargs):            # accepts any arguments, so it can stand in for the real function
        raise RuntimeError("could not build the event")

    # Inside the with-block, ingestion.py's name readings_stored_event points to failing_event; after it, to the real
    # one again. It is patched where it is USED (app.services.ingestion), because ingestion.py imported the name.
    with monkeypatch.context() as patch:
        patch.setattr("app.services.ingestion.readings_stored_event", failing_event)
        response = client.post(URL, headers=auth_headers, json=body("MTR-OUTBOX-05", reading("2026-11-25T00:00:00Z", 1.0)))

    assert response.status_code == 500                          # the route caught it, rolled back, answered 500
    assert reading_count(db_session, "MTR-OUTBOX-05") == 0      # the INSERT had run, and was rolled back
    assert events_for(db_session, "MTR-OUTBOX-05") == []


def test_occurred_at_is_the_moment_the_readings_were_stored(client, auth_headers, db_session):
    client.post(URL, headers=auth_headers, json=body("MTR-OUTBOX-06", reading("2026-11-25T00:00:00Z", 1.0)))

    [event] = events_for(db_session, "MTR-OUTBOX-06")
    stored_at = db_session.scalar(                              # the reading's created_at, as the database holds it
        select(SmartMeterIntervalRecord.created_at).where(SmartMeterIntervalRecord.meter_id == "MTR-OUTBOX-06")
    )
    # fromisoformat reads "...Z" back into a moment; == compares moments, whatever zone each is written in.
    assert datetime.fromisoformat(event.payload["occurred_at"]) == stored_at   # one moment: the transaction's now()
