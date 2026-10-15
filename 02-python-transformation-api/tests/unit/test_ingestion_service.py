"""
What this file protects. `store_readings` was extracted from the route in Stage 1A precisely so that it can
be tested without HTTP. It does three things: stage one row per reading, commit once, and compute the
summary. The collaborator it needs is a database session; a unit test supplies a stand-in.

New ideas used here.
- `MagicMock()` (A5) makes an object that accepts any call. After the call, `db.add.call_args_list` is the
  list of every call to `add`, each with its `.args`; `db.commit.assert_called_once()` fails unless `commit`
  was called exactly once; `db.commit.side_effect = RuntimeError(...)` makes the next call raise.
- The responsibility split (P16). `store_readings` does not catch errors: the route does, and it calls
  `rollback`. The test pins that division, so a later well-meaning "improvement" that swallows the error
  inside the function is noticed.
"""
from unittest.mock import MagicMock       # the standard library's mock object (A5): no extra package needed

import pytest

from app.database.models import SmartMeterIntervalRecord   # the table class; building one needs no database
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


def test_one_row_per_reading_is_added_and_committed_once():                               # P14
    db = MagicMock()                       # stands in for the SQLAlchemy session

    store_readings(db, two_readings())

    # Each call to db.add(record) is recorded; call.args[0] is the record that was passed in.
    added = [call.args[0] for call in db.add.call_args_list]
    assert all(isinstance(record, SmartMeterIntervalRecord) for record in added)
    assert [(r.meter_id, r.grid_zone, r.kwh_value, r.voltage) for r in added] == [
        ("MTR-POC2-001", "ZONE-A", 1.5, 230.0),
        ("MTR-POC2-001", "ZONE-A", 2.5, None),          # a missing voltage is stored as NULL
    ]
    db.commit.assert_called_once()                       # one transaction for the whole batch


def test_the_summary_is_computed_from_the_readings():                                     # P15
    result = store_readings(MagicMock(), two_readings())

    assert result.metadata.intervals_saved == 2
    assert result.metadata.processed_asset == "MTR-POC2-001"
    assert result.analytics_summary.cumulative_kwh == 4.0        # 1.5 + 2.5
    assert result.analytics_summary.average_load_per_interval == 2.0   # 4.0 / 2


def test_a_failed_commit_propagates_and_rollback_is_the_callers_job():                    # P16
    db = MagicMock()
    db.commit.side_effect = RuntimeError("commit failed")      # the next call to commit() raises

    with pytest.raises(RuntimeError):
        store_readings(db, two_readings())

    db.rollback.assert_not_called()     # the function does not handle the error: the route does (transform.py)
