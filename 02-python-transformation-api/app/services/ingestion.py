from sqlalchemy.orm import Session

from app.database.models import SmartMeterIntervalRecord
from app.schemas.meter import SmartMeterPayload
from app.schemas.responses import AnalyticsSummary, TransformMetadata, TransformResponse


def store_readings(db: Session, payload: SmartMeterPayload) -> TransformResponse:
    """Stage one row per reading, commit them in a single transaction and summarise them.

    The caller owns error handling and rollback. The payload is already validated, so it holds at least one reading.
    """
    for reading in payload.readings:
        db.add(
            SmartMeterIntervalRecord(
                meter_id=payload.meter_id,
                grid_zone=payload.grid_zone,
                timestamp=reading.timestamp,
                kwh_value=reading.kwh_value,
                voltage=reading.voltage,
            )
        )
    db.commit()

    total_intervals = len(payload.readings)
    total_kwh = sum(reading.kwh_value for reading in payload.readings)
    return TransformResponse(
        message="Payload schema validated and saved successfully to grid warehouse",
        metadata=TransformMetadata(
            processed_asset=payload.meter_id,
            regional_zone=payload.grid_zone,
            intervals_saved=total_intervals,
        ),
        analytics_summary=AnalyticsSummary(
            cumulative_kwh=total_kwh,
            average_load_per_interval=total_kwh / total_intervals,
        ),
    )
