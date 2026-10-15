from unittest.mock import MagicMock

import pytest

from app.database.models import SmartMeterIntervalRecord
from app.schemas.meter import SmartMeterPayload
from app.services.ingestion import store_readings


def two_readings() -> SmartMeterPayload:
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


def test_one_row_per_reading_is_added_and_committed_once():
    db = MagicMock()

    store_readings(db, two_readings())

    added = [call.args[0] for call in db.add.call_args_list]
    assert all(isinstance(record, SmartMeterIntervalRecord) for record in added)
    assert [(r.meter_id, r.grid_zone, r.kwh_value, r.voltage) for r in added] == [
        ("MTR-POC2-001", "ZONE-A", 1.5, 230.0),
        ("MTR-POC2-001", "ZONE-A", 2.5, None),
    ]
    db.commit.assert_called_once()


def test_the_summary_is_computed_from_the_readings():
    result = store_readings(MagicMock(), two_readings())

    assert result.metadata.intervals_saved == 2
    assert result.metadata.processed_asset == "MTR-POC2-001"
    assert result.analytics_summary.cumulative_kwh == 4.0
    assert result.analytics_summary.average_load_per_interval == 2.0


def test_a_failed_commit_propagates_and_rollback_is_the_callers_job():
    db = MagicMock()
    db.commit.side_effect = RuntimeError("commit failed")

    with pytest.raises(RuntimeError):
        store_readings(db, two_readings())

    db.rollback.assert_not_called()