"""
What this file protects. A client that timed out cannot tell whether its request was saved, so it sends it again with
the same Idempotency-Key. It must get the first answer, and nothing may be stored twice. The faults that matter: a repeat
that does the work again, a key reused for a different request, and a failed attempt that leaves its key behind.

New idea: `monkeypatch` makes one internal step fail once, to prove what a failed attempt leaves behind.
"""
import pytest
from sqlalchemy import func, select

from app.database.models import IdempotencyKeyRecord, SmartMeterIntervalRecord

pytestmark = pytest.mark.db

URL = "/api/v1/transform"
PROBLEM_JSON = "application/problem+json"


def body(meter_id: str, kwh: float = 10.0) -> dict:
    return {
        "meter_id": meter_id,
        "grid_zone": "ZONE-A",
        "readings": [{"timestamp": "2026-10-09T00:00:00Z", "kwh_value": kwh, "voltage": 230.0}],
    }


def row_count(db_session, meter_id: str) -> int:
    return db_session.scalar(
        select(func.count()).select_from(SmartMeterIntervalRecord).where(SmartMeterIntervalRecord.meter_id == meter_id)
    )


def test_a_repeat_with_the_same_key_gets_the_first_answer(client, auth_headers, db_session):
    headers = {**auth_headers, "Idempotency-Key": "key-repeat-1"}

    first = client.post(URL, json=body("MTR-IDEM-001"), headers=headers)
    again = client.post(URL, json=body("MTR-IDEM-001"), headers=headers)

    assert first.status_code == again.status_code == 200
    assert first.json()["metadata"]["intervals_saved"] == 1
    assert again.json() == first.json()              # 1 saved, as first answered; not 0 saved, 1 ignored
    assert row_count(db_session, "MTR-IDEM-001") == 1


def test_without_a_key_a_repeat_stores_nothing_and_says_so(client, auth_headers, db_session):
    client.post(URL, json=body("MTR-IDEM-002"), headers=auth_headers)
    again = client.post(URL, json=body("MTR-IDEM-002"), headers=auth_headers)

    assert again.status_code == 200
    assert again.json()["metadata"]["intervals_saved"] == 0
    assert again.json()["metadata"]["duplicates_ignored"] == 1
    assert row_count(db_session, "MTR-IDEM-002") == 1


def test_the_same_key_with_a_different_request_gives_409(client, auth_headers, db_session):
    headers = {**auth_headers, "Idempotency-Key": "key-reused-1"}
    client.post(URL, json=body("MTR-IDEM-003"), headers=headers)

    response = client.post(URL, json=body("MTR-IDEM-004"), headers=headers)

    assert response.status_code == 409
    assert response.headers["content-type"].startswith(PROBLEM_JSON)
    assert response.json()["detail"] == "This Idempotency-Key was already used for a different request."
    assert row_count(db_session, "MTR-IDEM-004") == 0


def test_a_failed_attempt_leaves_no_key_behind(client, auth_headers, db_session, monkeypatch):
    headers = {**auth_headers, "Idempotency-Key": "key-failed-1"}

    def failing_store(db, payload):
        raise RuntimeError("the database went away")

    with monkeypatch.context() as patch:
        patch.setattr("app.services.ingestion._store", failing_store)
        assert client.post(URL, json=body("MTR-IDEM-005"), headers=headers).status_code == 500
    assert db_session.get(IdempotencyKeyRecord, "key-failed-1") is None    # rolled back with the rest

    retry = client.post(URL, json=body("MTR-IDEM-005"), headers=headers)

    assert retry.status_code == 200
    assert row_count(db_session, "MTR-IDEM-005") == 1


@pytest.mark.parametrize("key", ["", "has space", "x" * 65, "caf\u00e9"], ids=["empty", "space", "too long", "not ascii"])
def test_a_key_outside_the_rule_gives_422_naming_the_header(client, auth_headers, db_session, key):
    response = client.post(URL, json=body("MTR-IDEM-006"), headers={**auth_headers, "Idempotency-Key": key.encode("latin-1")})

    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "Idempotency-Key"
    assert row_count(db_session, "MTR-IDEM-006") == 0