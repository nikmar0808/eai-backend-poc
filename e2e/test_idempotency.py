"""An Idempotency-Key across both services, against the real stack (POC 3, Stage 8)."""
import uuid
from concurrent.futures import ThreadPoolExecutor

from support import METER_PREFIX, valid_body

URL = "/api/v1/ingest/bulk"


def key() -> str:
    return f"e2e-{uuid.uuid4().hex}"


def row_count(db, meter_id: str) -> int:
    return db.execute("SELECT count(*) FROM smart_meter_intervals WHERE meter_id = %s", (meter_id,)).fetchone()[0]


# E17
def test_a_repeat_through_the_gateway_gets_the_first_answer(gateway, db):
    meter = f"{METER_PREFIX}-I1"
    headers = {"Idempotency-Key": key()}

    first = gateway.post(URL, json=valid_body(meter), headers=headers)
    again = gateway.post(URL, json=valid_body(meter), headers=headers)

    assert first.status_code == again.status_code == 200
    assert again.json() == first.json()
    assert again.json()["metadata"]["intervals_saved"] == 2
    assert row_count(db, meter) == 2


# E18
def test_two_requests_with_one_key_at_the_same_moment_store_once(gateway, db):
    meter = f"{METER_PREFIX}-I2"
    headers = {"Idempotency-Key": key()}

    # Both requests are in flight together: the second transaction waits on the key's index until the first commits.
    with ThreadPoolExecutor(max_workers=2) as pool:
        answers = list(pool.map(lambda _: gateway.post(URL, json=valid_body(meter), headers=headers), range(2)))

    assert [answer.status_code for answer in answers] == [200, 200]
    assert answers[0].json() == answers[1].json()
    assert row_count(db, meter) == 2


# E19
def test_a_key_reused_for_another_request_gives_409_through_the_gateway(gateway, db):
    headers = {"Idempotency-Key": key()}
    assert gateway.post(URL, json=valid_body(f"{METER_PREFIX}-I3"), headers=headers).status_code == 200

    response = gateway.post(URL, json=valid_body(f"{METER_PREFIX}-I4"), headers=headers)

    assert response.status_code == 409
    assert response.headers["content-type"].startswith("application/problem+json")
    assert row_count(db, f"{METER_PREFIX}-I4") == 0


# E20
def test_a_key_outside_the_rule_gives_400_at_the_gateway(gateway, db):
    meter = f"{METER_PREFIX}-I5"

    response = gateway.post(URL, json=valid_body(meter), headers={"Idempotency-Key": "has space"})

    assert response.status_code == 400
    assert response.json()["errors"][0]["field"] == "Idempotency-Key"
    assert row_count(db, meter) == 0


# E21
def test_the_stored_moment_is_exact_whatever_offset_was_sent(gateway, validator, auth, db):
    meter = f"{METER_PREFIX}-I6"
    body = valid_body(meter)
    body["readings"] = [{"timestamp": "2026-10-09T05:30:00+05:30", "kwh_value": 10.0}]
    assert gateway.post(URL, json=body).status_code == 200

    # The same moment, written in UTC, is a duplicate of it.
    body["readings"] = [{"timestamp": "2026-10-09T00:00:00Z", "kwh_value": 99.0}]
    again = gateway.post(URL, json=body)

    assert again.json()["metadata"] == {"processed_asset": meter, "regional_zone": "ZONE-A", "intervals_saved": 0, "duplicates_ignored": 1}
    assert validator.get(f"/api/v1/meters/{meter}/readings", headers=auth).json()["readings"] == [
        {"timestamp": "2026-10-09T00:00:00Z", "kwh_value": 10.0, "voltage": None}
    ]