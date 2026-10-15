from datetime import datetime, timedelta

import pytest

from app.database.models import SmartMeterIntervalRecord

pytestmark = pytest.mark.db

START = datetime(2026, 10, 9, 0, 0, 0)


def seed(db_session, meter_id: str, count: int, voltage=None) -> None:
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


def test_a_meter_with_no_rows_returns_an_empty_list(client, auth_headers):
    response = client.get(url("UNKNOWN-001"), headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {"meter_id": "UNKNOWN-001", "count": 0, "readings": []}


def test_readings_come_back_newest_first_in_the_documented_shape(client, auth_headers, db_session):
    seed(db_session, "MTR-READ-001", 3, voltage=230.0)

    body = client.get(url("MTR-READ-001"), headers=auth_headers).json()

    assert body["count"] == 3
    assert [r["kwh_value"] for r in body["readings"]] == [3.0, 2.0, 1.0]
    assert body["readings"][0] == {"timestamp": "2026-10-09T01:00:00", "kwh_value": 3.0, "voltage": 230.0}


def test_a_missing_voltage_is_returned_as_null(client, auth_headers, db_session):
    seed(db_session, "MTR-READ-001", 1)

    assert client.get(url("MTR-READ-001"), headers=auth_headers).json()["readings"][0]["voltage"] is None


def test_the_default_limit_is_twenty(client, auth_headers, db_session):
    seed(db_session, "MTR-READ-001", 25)

    assert client.get(url("MTR-READ-001"), headers=auth_headers).json()["count"] == 20


@pytest.mark.parametrize("limit, status", [(0, 422), (1, 200), (100, 200), (101, 422), ("abc", 422)])
def test_limit_is_between_1_and_100(client, auth_headers, limit, status):
    assert client.get(url("MTR-READ-001", f"?limit={limit}"), headers=auth_headers).status_code == status


def test_one_meter_never_sees_another_meters_rows(client, auth_headers, db_session):
    seed(db_session, "MTR-READ-001", 2)
    seed(db_session, "MTR-READ-002", 5)

    assert client.get(url("MTR-READ-001"), headers=auth_headers).json()["count"] == 2


@pytest.mark.parametrize("meter_id, status", [("M1", 422), ("M" * 4, 422), ("M" * 5, 200), ("M" * 20, 200), ("M" * 21, 422)])
def test_meter_id_is_five_to_twenty_characters(client, auth_headers, meter_id, status):
    assert client.get(url(meter_id), headers=auth_headers).status_code == status


@pytest.mark.parametrize("headers", [{}, {"X-EAI-TOKEN": "wrong"}], ids=["no token", "wrong token"])
def test_the_route_requires_the_token(client, headers):
    assert client.get(url("MTR-READ-001"), headers=headers).status_code == 401