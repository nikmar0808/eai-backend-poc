"""The ReadingsStored event, built from the readings really stored.

The event's shape is the contract in docs/api/events/readings-stored.schema.json (Stage 1). This module only builds
the dictionary; ingestion.py writes it to the outbox table. Building is kept apart from writing so that a test can
check the shape without a database.
"""

import uuid                                    # the type of the event's ID (uuid.UUID)
from collections.abc import Sequence           # a type hint: "an ordered collection", here the rows RETURNING gave back
from datetime import datetime, timezone        # timezone.utc is the UTC time zone object
from typing import Any                         # a type hint meaning "any type": the rows are SQLAlchemy Row objects

AGGREGATE_TYPE = "meter-readings"     # the outbox row's aggregatetype: Debezium turns it into the topic (Stage 3)
EVENT_TYPE = "ReadingsStored"         # the outbox row's type: Debezium turns it into the event's "type" header


def utc_text(moment: datetime) -> str:
    """An exact moment as RFC 3339 text in UTC, ending in Z: 2026-11-25T00:00:00Z.

    The database returns timestamptz values in its session time zone (Asia/Kolkata here), for example
    05:30:00+05:30. astimezone(timezone.utc) turns that into the same moment written in UTC.
    """
    # Three steps in one line:
    #   astimezone(timezone.utc)  the same moment, written in UTC:        2026-11-25 00:00:00+00:00
    #   isoformat()               as RFC 3339 text:                       2026-11-25T00:00:00+00:00
    #                             (microseconds are added only when there are any: ...00:00.123456+00:00)
    #   replace("+00:00", "Z")    the shorter way of writing UTC:          2026-11-25T00:00:00Z
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def readings_stored_event(
    event_id: uuid.UUID, occurred_at: datetime, meter_id: str, grid_zone: str, stored: Sequence[Any]
) -> dict[str, Any]:
    """The event for one batch. `stored` holds the rows the INSERT really added (its RETURNING rows).

    Each row has .timestamp, .kwh_value and .voltage. The readings are sorted by time, so the same batch always gives
    the same event whatever order the database returned the rows in. voltage is always present, None when there was
    none, because the schema requires the field (it may be null).

    A pure function: the ID and the time are passed in, never made here, so the same input always gives the same
    output and a test can write the expected event out in full.
    """
    # sorted(...) returns a new list ordered by each row's timestamp. "lambda row: row.timestamp" is a small unnamed
    # function: given a row, return its timestamp. SQL does not promise RETURNING's row order, hence the sort.
    readings = sorted(stored, key=lambda row: row.timestamp)
    return {                                             # a Python dict: becomes the JSON object of the contract
        "event_id": str(event_id),                       # str() of a UUID is lower-case, as the schema's pattern asks
        "occurred_at": utc_text(occurred_at),            # when the readings were stored, in UTC
        "meter_id": meter_id,
        "grid_zone": grid_zone,
        # A list comprehension: one small dict per stored row, in the sorted order.
        "readings": [
            {"timestamp": utc_text(row.timestamp), "kwh_value": row.kwh_value, "voltage": row.voltage}   # None -> null
            for row in readings
        ],
    }
