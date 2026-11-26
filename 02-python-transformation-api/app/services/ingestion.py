import hashlib
import uuid                                    # POC 4: uuid.uuid4() makes each event's ID
from collections.abc import Sequence           # POC 4: type hint for the rows RETURNING gives back
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

# POC 4: OutboxRecord is the outbox table's class (models.py).
from app.database.models import READING_KEY, IdempotencyKeyRecord, OutboxRecord, SmartMeterIntervalRecord
from app.schemas.meter import SmartMeterPayload
from app.schemas.responses import AnalyticsSummary, TransformMetadata, TransformResponse
# POC 4: the two fixed values of every outbox row, and the function that builds the event (events.py).
from app.services.events import AGGREGATE_TYPE, EVENT_TYPE, readings_stored_event


class IdempotencyConflict(Exception):
    """The key was already used, for a different request. Carries no message: the handler's sentence is fixed."""


def store_readings(db: Session, payload: SmartMeterPayload, idempotency_key: str | None = None) -> TransformResponse:
    """Store the batch in one transaction; with a key, a repeated request gets the first answer and changes nothing.

    The key, the readings, the outbox event and the answer are all written in one transaction, so they commit together
    or not at all. If the process dies midway, the key is gone too, and the client's retry simply does the work.
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
        # A repeat: nothing is stored again, so no event is written either.
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
    """Insert the batch's new readings and, if any went in, their event; summarise the batch. Does not commit.

    A reading whose meter and moment are already stored is left as it is, whatever value it carries: the first value
    stands. ON CONFLICT DO NOTHING makes that safe when two requests arrive together, and RETURNING lists only the
    rows really inserted, with the values the event needs. The payload is already validated, so it holds at least one
    reading.
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
        insert(SmartMeterIntervalRecord)               # INSERT INTO smart_meter_intervals
        .values(rows)                                  # VALUES (...), (...): the whole batch in one statement
        .on_conflict_do_nothing(constraint=READING_KEY)    # ON CONFLICT ON CONSTRAINT ... DO NOTHING: skip repeats
        # RETURNING ...: one row back for every row REALLY inserted, none for a skipped repeat. Until POC 4 only the
        # id came back, to be counted. Now the values the event needs come back too.
        .returning(
            SmartMeterIntervalRecord.timestamp,
            SmartMeterIntervalRecord.kwh_value,
            SmartMeterIntervalRecord.voltage,
            SmartMeterIntervalRecord.created_at,       # now(): the moment this transaction started
        )
    )
    stored = db.execute(statement).all()               # runs the INSERT; .all() = the RETURNING rows, as a list
    if stored:                        # nothing new stored (only duplicates): no event, because nothing happened
        _write_event(db, payload, stored)              # same session, so the same transaction as the INSERT above

    saved = len(stored)                                # as before: the answer counts the rows really stored
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


def _write_event(db: Session, payload: SmartMeterPayload, stored: Sequence[Any]) -> None:
    """One outbox row for the readings just stored, in the same transaction. Does not commit.

    occurred_at is the rows' created_at: PostgreSQL's now(), the moment this transaction started, so the event says
    exactly when the readings were stored. Every row of one INSERT has the same value.
    (J2EE comparison: a second insert inside the same container-managed transaction as the first.)
    """
    event_id = uuid.uuid4()           # a new random UUID: the event's identity, used by consumers to skip a repeat
    # The event dict (events.py). stored[0].created_at: every stored row has the same value, so the first one will do.
    event = readings_stored_event(event_id, stored[0].created_at, payload.meter_id, payload.grid_zone, stored)
    db.execute(
        insert(OutboxRecord).values(                   # INSERT INTO outbox (id, aggregatetype, ...) VALUES (...)
            id=event_id,                               # the same UUID as the payload's event_id
            aggregatetype=AGGREGATE_TYPE,              # 'meter-readings'
            aggregateid=payload.meter_id,              # the meter: the Kafka key in Stage 3
            type=EVENT_TYPE,                           # 'ReadingsStored'
            payload=event,                             # the dict; SQLAlchemy turns it into JSON for the jsonb column
        )                                              # created_at is not given: the database fills it (now())
    )
    # No commit here: store_readings commits once, for the readings, the event and the key together. If anything
    # fails before that, the route's rollback() (transform.py) removes all of it.
