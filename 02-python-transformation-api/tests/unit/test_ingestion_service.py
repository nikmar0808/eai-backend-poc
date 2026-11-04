"""
What this file protects. `store_readings` was extracted from the route in Stage 1A precisely so that it can
be tested without HTTP. It does three things: build one statement for the whole batch, commit once, and compute
the summary. The collaborator it needs is a database session; a unit test supplies a stand-in.

New ideas used here.
- `MagicMock()` (A5) makes an object that accepts any call. `db.execute.return_value.all.return_value` is what
  `db.execute(...).all()` will return: here, the rows the statement "inserted". `db.commit.assert_called_once()`
  fails unless `commit` was called exactly once; `db.commit.side_effect = RuntimeError(...)` makes the next call raise.
- Reading a statement without running it. `str(statement.compile(dialect=postgresql.dialect()))` is the SQL that
  SQLAlchemy would send, and `.params` holds the values.
- The responsibility split (P16). `store_readings` does not catch errors: the route does, and it calls
  `rollback`. The test pins that division, so a later well-meaning "improvement" that swallows the error
  inside the function is noticed.
"""
from unittest.mock import MagicMock       # the standard library's mock object (A5): no extra package needed

import pytest
from sqlalchemy.dialects import postgresql

from app.schemas.meter import SmartMeterPayload
from app.services.ingestion import store_readings


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
    """A stand-in session whose INSERT reports that this many rows went in."""
    db = MagicMock()
    db.execute.return_value.all.return_value = [(i,) for i in range(rows)]
    return db


def test_one_statement_holds_the_batch_and_is_committed_once():                           # P14
    db = session_inserting(2)

    store_readings(db, two_readings())

    db.execute.assert_called_once()                      # one statement, not one per reading
    compiled = db.execute.call_args.args[0].compile(dialect=postgresql.dialect())
    assert "ON CONFLICT ON CONSTRAINT smart_meter_intervals_meter_time_uk DO NOTHING" in str(compiled)
    assert compiled.params["kwh_value_m0"] == 1.5
    assert compiled.params["kwh_value_m1"] == 2.5
    assert compiled.params["voltage_m1"] is None         # a missing voltage is stored as NULL
    db.commit.assert_called_once()                       # one transaction for the whole batch


def test_the_summary_is_computed_from_the_readings():                                     # P15
    result = store_readings(session_inserting(2), two_readings())

    assert result.metadata.intervals_saved == 2
    assert result.metadata.duplicates_ignored == 0
    assert result.metadata.processed_asset == "MTR-POC2-001"
    assert result.analytics_summary.cumulative_kwh == 4.0        # 1.5 + 2.5
    assert result.analytics_summary.average_load_per_interval == 2.0   # 4.0 / 2


def test_readings_already_stored_are_counted_as_ignored():
    result = store_readings(session_inserting(1), two_readings())

    assert result.metadata.intervals_saved == 1
    assert result.metadata.duplicates_ignored == 1


def test_a_failed_commit_propagates_and_rollback_is_the_callers_job():                    # P16
    db = session_inserting(2)
    db.commit.side_effect = RuntimeError("commit failed")      # the next call to commit() raises

    with pytest.raises(RuntimeError):
        store_readings(db, two_readings())

    db.rollback.assert_not_called()     # the function does not handle the error: the route does (transform.py)