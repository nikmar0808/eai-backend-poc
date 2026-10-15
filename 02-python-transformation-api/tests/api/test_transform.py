import inspect
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.api.transform import validate_and_transform_payload
from app.database.models import SmartMeterIntervalRecord

pytestmark = pytest.mark.db

URL = "/api/v1/transform"
REQUESTS = Path(__file__).resolve().parents[3] / "docs" / "comprehension" / "requests"
JSON = {"Content-Type": "application/json"}

# The Python column of the baseline matrix (docs/comprehension/baseline-matrix.md, after Stage 1A).
EXPECTED_STATUS = {
    "01-valid.json": 200,
    "02-kwh-zero.json": 422,
    "03-voltage-too-low.json": 422,
    "04-timestamp-no-offset.json": 422,
    "05-empty-readings.json": 422,
    "06-blank-grid-zone.json": 422,
    "07-meter-id-too-short.json": 422,
    "08-malformed-json.json": 422,
    "09-missing-readings-field.json": 422,
}


def row_count(db_session, meter_id="MTR-POC2-001") -> int:
    return db_session.scalar(
        select(func.count()).select_from(SmartMeterIntervalRecord).where(SmartMeterIntervalRecord.meter_id == meter_id)
    )


def body(readings=1, **overrides) -> dict:
    data = {
        "meter_id": "MTR-POC2-001",
        "grid_zone": "ZONE-A",
        "readings": [
            {"timestamp": f"2026-10-09T{(i // 60) % 24:02d}:{i % 60:02d}:00Z", "kwh_value": 1.0, "voltage": 230.0}
            for i in range(readings)
        ],
    }
    data.update(overrides)
    return data


def test_every_request_file_has_an_expected_status():
    assert sorted(path.name for path in REQUESTS.glob("*.json")) == sorted(EXPECTED_STATUS)


@pytest.mark.parametrize("name, status", sorted(EXPECTED_STATUS.items()))
def test_the_baseline_requests(client, auth_headers, name, status):
    response = client.post(URL, content=(REQUESTS / name).read_bytes(), headers={**auth_headers, **JSON})
    assert response.status_code == status


def test_a_valid_request_is_summarised_and_stored(client, auth_headers, db_session):
    response = client.post(URL, json=body(readings=3), headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {
        "message": "Payload schema validated and saved successfully to grid warehouse",
        "metadata": {"processed_asset": "MTR-POC2-001", "regional_zone": "ZONE-A", "intervals_saved": 3},
        "analytics_summary": {"cumulative_kwh": 3.0, "average_load_per_interval": 1.0},
    }
    assert row_count(db_session) == 3


def test_the_largest_allowed_request_is_accepted_and_one_more_is_not(client, auth_headers, db_session):
    assert client.post(URL, json=body(readings=1000), headers=auth_headers).status_code == 200
    assert row_count(db_session) == 1000
    assert client.post(URL, json=body(readings=1001), headers=auth_headers).status_code == 422


@pytest.mark.parametrize("headers", [{}, {"X-EAI-TOKEN": "wrong"}], ids=["no token", "wrong token"])
def test_a_missing_or_wrong_token_gives_401_and_stores_nothing(client, db_session, headers):
    response = client.post(URL, json=body(), headers=headers)

    assert response.status_code == 401
    assert row_count(db_session) == 0


def test_a_rejected_payload_stores_nothing(client, auth_headers, db_session):
    assert client.post(URL, json=body(grid_zone=""), headers=auth_headers).status_code == 422
    assert row_count(db_session) == 0


def test_authentication_is_checked_before_validation(client):
    # An unauthenticated caller learns nothing about the payload rules.
    assert client.post(URL, json=body(grid_zone=""), headers={}).status_code == 401


def test_documents_D8_the_same_reading_posted_twice_is_stored_twice(client, auth_headers, db_session):
    # Finding D8: no unique constraint and no idempotency. POC 3 adds both and flips this assertion to 1.
    client.post(URL, json=body(), headers=auth_headers)
    client.post(URL, json=body(), headers=auth_headers)

    assert row_count(db_session) == 2


def test_documents_D6_a_failed_commit_returns_500_and_leaks_the_exception_text(
    client, auth_headers, db_session, monkeypatch
):
    # Finding D6: the exception text is echoed to the caller. Stage 6 removes it and flips the second assertion.
    def failing_commit():
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(db_session, "commit", failing_commit)

    response = client.post(URL, json=body(), headers=auth_headers)

    assert response.status_code == 500
    assert "disk on fire" in response.json()["detail"]


def test_the_write_route_is_a_plain_def_so_it_does_not_block_the_event_loop():
    # Finding D16: an async def route calling a synchronous database session would freeze every other request.
    assert not inspect.iscoroutinefunction(validate_and_transform_payload)