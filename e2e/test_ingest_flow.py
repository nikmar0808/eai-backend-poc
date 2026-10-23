import pytest

from support import METER_PREFIX, valid_body


def row_count(db, meter_id: str) -> int:
    # fetchone() returns one row as a tuple; [0] is its only column, the count.
    return db.execute("SELECT count(*) FROM smart_meter_intervals WHERE meter_id = %s", (meter_id,)).fetchone()[0]


# E04
def test_both_health_endpoints_report_up(gateway, validator):
    assert gateway.get("/health").json() == {"status": "UP", "pythonValidator": "UP"}
    assert validator.get("/health").json() == {"status": "UP", "database": "UP"}


# E05
def test_a_valid_request_through_the_gateway_is_summarised_and_stored(gateway, validator, auth, db):
    meter = f"{METER_PREFIX}-A"

    # The `gateway` fixture adds the bearer token (Stage 5); this call needs no extra code for it.
    response = gateway.post("/api/v1/ingest/bulk", json=valid_body(meter))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {
        "message": "Payload schema validated and saved successfully to grid warehouse",
        "metadata": {"processed_asset": meter, "regional_zone": "ZONE-A", "intervals_saved": 2},
        "analytics_summary": {"cumulative_kwh": 30.0, "average_load_per_interval": 15.0},
    }

    # The row itself, read straight from the database (the independent witness of A4).
    rows = db.execute(
        "SELECT grid_zone, kwh_value, voltage FROM smart_meter_intervals WHERE meter_id = %s ORDER BY kwh_value",
        (meter,),
    ).fetchall()
    assert rows == [("ZONE-A", 10.0, 230.0), ("ZONE-A", 20.0, None)]     # None is SQL NULL: the 2nd reading had no voltage

    # Finding D14: the column has no time zone, so the stored wall-clock value depends on the database's time zone
    # (Asia/Kolkata in the compose file). The test therefore does not hard-code it; it asks the database to convert
    # the sent instant the same way and compares. (%s::timestamptz casts the text to a timestamp WITH time zone;
    # ::timestamp then drops the zone, exactly what the column definition does on insert.)
    matching = db.execute(
        "SELECT count(*) FROM smart_meter_intervals WHERE meter_id = %s AND timestamp = (%s::timestamptz)::timestamp",
        (meter, "2026-10-09T00:00:00Z"),
    ).fetchone()[0]
    assert matching == 1

    # And back out through the other service's read route, newest first.
    readings = validator.get(f"/api/v1/meters/{meter}/readings", headers=auth).json()
    assert readings["count"] == 2
    assert [reading["kwh_value"] for reading in readings["readings"]] == [20.0, 10.0]


CASES = [
    ("POST", "/api/v1/transform", {}),
    ("POST", "/api/v1/transform", {"X-EAI-TOKEN": "wrong"}),
    ("GET", "/api/v1/meters/MTR-E2E-0000/readings", {}),
]


# E06: ids= gives the three executions readable names in the report instead of "CASES0", "CASES1", "CASES2".
@pytest.mark.parametrize("method, path, headers", CASES, ids=["no token", "wrong token", "readings without token"])
def test_python_rejects_callers_without_the_token_and_stores_nothing(validator, db, method, path, headers):
    meter = f"{METER_PREFIX}-T"
    body = valid_body(meter) if method == "POST" else None

    response = validator.request(method, path, headers=headers, json=body)

    assert response.status_code == 401
    assert row_count(db, meter) == 0     # a rejected request must also leave no row


# E07
def test_documents_D8_the_same_request_posted_twice_is_stored_twice(gateway, db):
    # Finding D8: no unique constraint and no idempotency. POC 3 changes the expected count from 4 to 2.
    meter = f"{METER_PREFIX}-D"
    for _ in range(2):
        assert gateway.post("/api/v1/ingest/bulk", json=valid_body(meter)).status_code == 200

    assert row_count(db, meter) == 4