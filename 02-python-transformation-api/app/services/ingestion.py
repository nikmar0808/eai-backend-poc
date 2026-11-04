import hashlib

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.database.models import READING_KEY, IdempotencyKeyRecord, SmartMeterIntervalRecord
from app.schemas.meter import SmartMeterPayload
from app.schemas.responses import AnalyticsSummary, TransformMetadata, TransformResponse


class IdempotencyConflict(Exception):
    """The key was already used, for a different request. Carries no message: the handler's sentence is fixed."""


def store_readings(db: Session, payload: SmartMeterPayload, idempotency_key: str | None = None) -> TransformResponse:
    """Store the batch in one transaction; with a key, a repeated request gets the first answer and changes nothing.

    The key, the readings and the answer are all written in one transaction, so they commit together or not at all.
    If the process dies midway, the key is gone too, and the client's retry simply does the work.
    """
    if idempotency_key is None:
        response = _store(db, payload)
        db.commit()
        return response

    request_hash = hashlib.sha256(payload.model_dump_json().encode()).hexdigest()
    # Try to claim the key. If another transaction is claiming the same key at this moment, this statement WAITS for
    # that transaction to finish, because of the primary key's index: that is what makes two simultaneous retries safe.
    claimed = db.execute(
        insert(IdempotencyKeyRecord)
        .values(key=idempotency_key, request_hash=request_hash)
        .on_conflict_do_nothing(index_elements=[IdempotencyKeyRecord.key])
        .returning(IdempotencyKeyRecord.key)
    ).first()
    if claimed is None:
        return _answer_of_the_first_request(db, idempotency_key, request_hash)

    response = _store(db, payload)
    db.execute(
        update(IdempotencyKeyRecord)
        .where(IdempotencyKeyRecord.key == idempotency_key)
        .values(response=response.model_dump())
    )
    db.commit()
    return response


def _answer_of_the_first_request(db: Session, idempotency_key: str, request_hash: str) -> TransformResponse:
    stored = db.execute(
        select(IdempotencyKeyRecord).where(IdempotencyKeyRecord.key == idempotency_key)
    ).scalar_one()
    if stored.request_hash != request_hash:
        raise IdempotencyConflict()
    # The row is committed by the first request, so it always holds its answer by the time it can be read here.
    return TransformResponse.model_validate(stored.response)


def _store(db: Session, payload: SmartMeterPayload) -> TransformResponse:
    """Insert the batch's new readings, and summarise the batch as it was received. Does not commit.

    A reading whose meter and moment are already stored is left as it is, whatever value it carries: the first value
    stands. ON CONFLICT DO NOTHING makes that safe when two requests arrive together, and RETURNING lists only the
    rows really inserted. The payload is already validated, so it holds at least one reading.
    """
    rows = [
        {
            "meter_id": payload.meter_id,
            "grid_zone": payload.grid_zone,
            "timestamp": reading.timestamp,
            "kwh_value": reading.kwh_value,
            "voltage": reading.voltage,
        }
        for reading in payload.readings
    ]
    statement = (
        insert(SmartMeterIntervalRecord)
        .values(rows)
        .on_conflict_do_nothing(constraint=READING_KEY)
        .returning(SmartMeterIntervalRecord.id)
    )
    saved = len(db.execute(statement).all())

    total_intervals = len(payload.readings)
    total_kwh = sum(reading.kwh_value for reading in payload.readings)
    return TransformResponse(
        message="Payload schema validated and saved successfully to grid warehouse",
        metadata=TransformMetadata(
            processed_asset=payload.meter_id,
            regional_zone=payload.grid_zone,
            intervals_saved=saved,
            duplicates_ignored=total_intervals - saved,
        ),
        analytics_summary=AnalyticsSummary(
            cumulative_kwh=total_kwh,
            average_load_per_interval=total_kwh / total_intervals,
        ),
    )