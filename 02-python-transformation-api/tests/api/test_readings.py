"""
What this file protects. The read route returns the newest rows of one meter, bounded. The faults that
matter: wrong order, rows of another meter leaking in, an unbounded `limit`, and a route open to anyone.
Rows are *seeded* by adding records through the test's session and calling `flush()`, which sends the
statements to the database without committing, so the route (same session) sees them and the rollback
removes them.

(The ideas shared by all three API files - the client and db_session fixtures, content= versus json=,
counting rows with the test's own session, documenting a known defect with a passing test - are explained at
the top of test_transform.py.)
"""
from datetime import datetime, timedelta

import pytest

from app.database.models import SmartMeterIntervalRecord

pytestmark = pytest.mark.db

START = datetime(2026, 10, 9, 0, 0, 0)       # naive on purpose: the column is a naive DateTime (finding D14)


def seed(db_session, meter_id: str, count: int, voltage=None) -> None:
    """Insert `count` rows for a meter, 30 minutes apart, with kWh 1.0, 2.0, 3.0 ..."""
    for i in range(count):
        db_session.add(
            SmartMeterIntervalRecord(
                meter_id=meter_id,
                grid_zone="ZONE-A",
                timestamp=START + timedelta(minutes=30 * i),
                kwh_value=float(i + 1),
                voltage=voltage,
            )
        )
    db_session.flush()  # visible to the route, which shares this session, but never committed


def url(meter_id: str, query: str = "") -> str:
    return f"/api/v1/meters/{meter_id}/readings{query}"


def test_a_meter_with_no_rows_returns_an_empty_list(client, auth_headers):                # P29
    response = client.get(url("UNKNOWN-001"), headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {"meter_id": "UNKNOWN-001", "count": 0, "readings": []}


def test_readings_come_back_newest_first_in_the_documented_shape(client, auth_headers, db_session):   # P30
    seed(db_session, "MTR-READ-001", 3, voltage=230.0)

    body = client.get(url("MTR-READ-001"), headers=auth_headers).json()

    assert body["count"] == 3
    assert [r["kwh_value"] for r in body["readings"]] == [3.0, 2.0, 1.0]       # newest (kWh 3.0) first
    assert body["readings"][0] == {"timestamp": "2026-10-09T01:00:00", "kwh_value": 3.0, "voltage": 230.0}


def test_a_missing_voltage_is_returned_as_null(client, auth_headers, db_session):         # P31
    seed(db_session, "MTR-READ-001", 1)

    assert client.get(url("MTR-READ-001"), headers=auth_headers).json()["readings"][0]["voltage"] is None


def test_the_default_limit_is_twenty(client, auth_headers, db_session):                   # P32
    seed(db_session, "MTR-READ-001", 25)

    assert client.get(url("MTR-READ-001"), headers=auth_headers).json()["count"] == 20


@pytest.mark.parametrize("limit, status", [(0, 422), (1, 200), (100, 200), (101, 422), ("abc", 422)])   # P33: 5 runs
def test_limit_is_between_1_and_100(client, auth_headers, limit, status):
    assert client.get(url("MTR-READ-001", f"?limit={limit}"), headers=auth_headers).status_code == status


def test_one_meter_never_sees_another_meters_rows(client, auth_headers, db_session):      # P34
    seed(db_session, "MTR-READ-001", 2)
    seed(db_session, "MTR-READ-002", 5)

    assert client.get(url("MTR-READ-001"), headers=auth_headers).json()["count"] == 2


@pytest.mark.parametrize("meter_id, status", [("M1", 422), ("M" * 4, 422), ("M" * 5, 200), ("M" * 20, 200), ("M" * 21, 422)])   # P35: 5 runs
def test_meter_id_is_five_to_twenty_characters(client, auth_headers, meter_id, status):
    assert client.get(url(meter_id), headers=auth_headers).status_code == status


@pytest.mark.parametrize("headers", [{}, {"X-EAI-TOKEN": "wrong"}], ids=["no token", "wrong token"])   # P36: 2 runs
def test_the_route_requires_the_token(client, headers):
    assert client.get(url("MTR-READ-001"), headers=headers).status_code == 401
