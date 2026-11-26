"""
What this file protects. `store_readings` was extracted from the route in Stage 1A precisely so that it can
be tested without HTTP. Without a key, it does four things: build one statement for the whole batch, write one outbox
event when readings were really stored (POC 4), commit once, and compute the summary. The collaborator it needs is a
database session; a unit test supplies a stand-in. What a key adds needs a real database, and is in
tests/api/test_idempotency.py; what the outbox row holds in a real database is in tests/api/test_outbox.py.

New ideas used here.
- `MagicMock()` (A5) makes an object that accepts any call. `db.execute.return_value.all.return_value` is what
  `db.execute(...).all()` will return: here, the rows the statement "inserted". `db.commit.assert_called_once()`
  fails unless `commit` was called exactly once; `db.commit.side_effect = RuntimeError(...)` makes the next call raise.
- `db.execute.call_args_list[0]` is the first call's arguments, `[1]` the second's. Since POC 4 a batch that stores
  something runs two statements, and each is checked on its own.
- Reading a statement without running it. `str(statement.compile(dialect=postgresql.dialect()))` is the SQL that
  SQLAlchemy would send, and `.params` holds the values.
- The responsibility split (P16). `store_readings` does not catch errors: the route does, and it calls
  `rollback`. The test pins that division, so a later well-meaning "improvement" that swallows the error
  inside the function is noticed.

Changed in POC 4, Stage 2. The stand-in's inserted rows now carry the columns RETURNING asks for (timestamp, kWh,
voltage, created_at), because the event is built from them. The first test used to say "execute is called exactly
once". That was a check of the old design, not of a behaviour anyone relies on: what it protected is "one statement
for the whole batch, not one per reading", and that is still checked, on the first call. The outbox insert is the
second call, and a new test checks that a batch of only duplicates runs no second statement.
"""
from datetime import datetime, timezone            # POC 4: the stand-in rows' created_at
from types import SimpleNamespace                  # POC 4: a plain object with named attributes, a stand-in row
from unittest.mock import MagicMock       # the standard library's mock object (A5): no extra package needed

import pytest
from sqlalchemy.dialects import postgresql         # to compile a statement to PostgreSQL's SQL without running it

from app.schemas.meter import SmartMeterPayload
from app.services.ingestion import store_readings

STORED_AT = datetime(2026, 10, 9, 6, 0, tzinfo=timezone.utc)     # what now() "returned" in the stand-in


def two_readings() -> SmartMeterPayload:
    """A validated payload with two readings, the second without a voltage."""
    return SmartMeterPayload.model_validate(
        {
            "meter_id": "MTR-POC2-001",
            "grid_zone": "ZONE-A",
            "readings": [
                {"timestamp": "2026-10-09T00:00:00Z", "kwh_value": 1.5, "voltage": 230.0},
                {"timestamp": "2026-10-09T00:30:00Z", "kwh_value": 2.5},
            ],
        }
    )


def session_inserting(rows: int) -> MagicMock:
    """A stand-in session whose INSERT reports that the first `rows` readings of two_readings() went in.

    Each reported row has the attributes of a real RETURNING row: timestamp, kwh_value, voltage, created_at.
    """
    db = MagicMock()
    # readings[:rows] is a slice: the first `rows` readings. 0 = everything was a repeat, 2 = everything was new.
    # Every call to db.execute(...).all() returns this list; the outbox insert's result is simply never used.
    db.execute.return_value.all.return_value = [
        SimpleNamespace(timestamp=r.timestamp, kwh_value=r.kwh_value, voltage=r.voltage, created_at=STORED_AT)
        for r in two_readings().readings[:rows]
    ]
    return db


def test_one_statement_holds_the_batch_and_one_more_writes_the_event():                   # P14
    db = session_inserting(2)

    store_readings(db, two_readings())

    assert db.execute.call_count == 2                    # the batch, then the event: not one statement per reading
    # call_args_list[0].args[0]: the first positional argument of the FIRST call to execute, i.e. the batch INSERT.
    batch = db.execute.call_args_list[0].args[0].compile(dialect=postgresql.dialect())
    assert "ON CONFLICT ON CONSTRAINT smart_meter_intervals_meter_time_uk DO NOTHING" in str(batch)
    assert batch.params["kwh_value_m0"] == 1.5           # _m0, _m1: SQLAlchemy's names for the values of row 0, row 1
    assert batch.params["kwh_value_m1"] == 2.5
    assert batch.params["voltage_m1"] is None            # a missing voltage is stored as NULL
    # The SECOND call: the outbox INSERT, and what it would write.
    event = db.execute.call_args_list[1].args[0].compile(dialect=postgresql.dialect())
    assert str(event).startswith("INSERT INTO outbox")
    assert event.params["aggregateid"] == "MTR-POC2-001"
    assert len(event.params["payload"]["readings"]) == 2    # the payload parameter is still the Python dict here
    db.commit.assert_called_once()                       # one transaction for the batch and its event


def test_nothing_stored_means_no_event():
    db = session_inserting(0)                            # every reading was already there

    store_readings(db, two_readings())

    db.execute.assert_called_once()                      # the batch only: no outbox statement
    db.commit.assert_called_once()


def test_the_summary_is_computed_from_the_readings():                                     # P15
    result = store_readings(session_inserting(2), two_readings())

    assert result.metadata.intervals_saved == 2
    assert result.metadata.duplicates_ignored == 0
    assert result.metadata.processed_asset == "MTR-POC2-001"
    assert result.analytics_summary.cumulative_kwh == 4.0        # 1.5 + 2.5
    assert result.analytics_summary.average_load_per_interval == 2.0   # 4.0 / 2


def test_readings_already_stored_are_counted_as_ignored():
    db = session_inserting(1)                            # only the first reading was new

    result = store_readings(db, two_readings())

    assert result.metadata.intervals_saved == 1
    assert result.metadata.duplicates_ignored == 1
    event = db.execute.call_args_list[1].args[0].compile(dialect=postgresql.dialect())
    assert len(event.params["payload"]["readings"]) == 1         # the event carries only the reading really stored


def test_a_failed_commit_propagates_and_rollback_is_the_callers_job():                    # P16
    db = session_inserting(2)
    db.commit.side_effect = RuntimeError("commit failed")      # the next call to commit() raises

    with pytest.raises(RuntimeError):
        store_readings(db, two_readings())

    db.rollback.assert_not_called()     # the function does not handle the error: the route does (transform.py)
