"""
What this file protects, and the most useful test of the stage. The nine request files and expected statuses
of Stage 0B become a regression test (P17, P18): the replay script stays as a quick manual tool, and this
test is what CI runs. Around it are the behaviours that only a route with a database behind it can show:
what is stored, what is not stored, and the order of the checks (A7).

New ideas used by all three files.
- `client` and `db_session` fixtures (3.4): a test names them as parameters and receives a client wired to a
  session that is rolled back at the end.
- `client.post(URL, json=payload, headers=...)` serialises a dictionary to JSON and sets the content type.
  `content=<bytes>` sends raw bytes instead, which is how the baseline files are sent exactly as they are on
  disk (including the deliberately malformed one).
- Counting rows with the test's own session.
  `db_session.scalar(select(func.count()).select_from(Table).where(...))` runs `SELECT count(*) ...` and
  returns the number. Because the route shares the same session, the count sees what the route staged and
  committed (to a savepoint), and nothing outside the test can see it.
- Documenting a known defect with a passing test (P24, P25): the test asserts today's wrong behaviour, names
  the finding and says which stage flips it. When the defect is fixed the test fails, which is the signal to
  rewrite it.
"""
import inspect
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.api.transform import validate_and_transform_payload      # the route function itself (for P26)
from app.database.models import SmartMeterIntervalRecord

pytestmark = pytest.mark.db          # every test in this file needs the database (A4: markers)

URL = "/api/v1/transform"
# parents[3] climbs from tests/api/test_transform.py to the repository root:
# [0]=api, [1]=tests, [2]=02-python-transformation-api, [3]=repository root.
REQUESTS = Path(__file__).resolve().parents[3] / "docs" / "comprehension" / "requests"
JSON = {"Content-Type": "application/json"}

# The Python column of the baseline matrix (docs/comprehension/baseline-matrix.md, after Stage 1A).
# Eight of the nine files are invalid in a different way and all get 422.
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
    """How many rows the table holds for a meter, seen through the test's own session."""
    return db_session.scalar(
        select(func.count()).select_from(SmartMeterIntervalRecord).where(SmartMeterIntervalRecord.meter_id == meter_id)
    )


def body(readings=1, **overrides) -> dict:
    """A valid request body with `readings` readings 1 minute apart; a test overrides one field."""
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


def test_every_request_file_has_an_expected_status():                                      # P17
    # Guards the guard: a request file added to the folder without an expectation (or the reverse) fails here,
    # instead of being silently left out of the parametrised test below.
    assert sorted(path.name for path in REQUESTS.glob("*.json")) == sorted(EXPECTED_STATUS)


@pytest.mark.parametrize("name, status", sorted(EXPECTED_STATUS.items()))                  # P18: 9 runs
def test_the_baseline_requests(client, auth_headers, name, status):
    # The file is sent byte for byte, with a valid token, so only the CONTENT decides the status.
    response = client.post(URL, content=(REQUESTS / name).read_bytes(), headers={**auth_headers, **JSON})
    assert response.status_code == status


def test_a_valid_request_is_summarised_and_stored(client, auth_headers, db_session):      # P19
    response = client.post(URL, json=body(readings=3), headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {
        "message": "Payload schema validated and saved successfully to grid warehouse",
        "metadata": {"processed_asset": "MTR-POC2-001", "regional_zone": "ZONE-A", "intervals_saved": 3},
        "analytics_summary": {"cumulative_kwh": 3.0, "average_load_per_interval": 1.0},
    }
    assert row_count(db_session) == 3          # the answer is not enough: the rows must really be there


def test_the_largest_allowed_request_is_accepted_and_one_more_is_not(client, auth_headers, db_session):   # P20
    assert client.post(URL, json=body(readings=1000), headers=auth_headers).status_code == 200
    assert row_count(db_session) == 1000
    assert client.post(URL, json=body(readings=1001), headers=auth_headers).status_code == 422


@pytest.mark.parametrize("headers", [{}, {"X-EAI-TOKEN": "wrong"}], ids=["no token", "wrong token"])   # P21: 2 runs
def test_a_missing_or_wrong_token_gives_401_and_stores_nothing(client, db_session, headers):
    response = client.post(URL, json=body(), headers=headers)

    assert response.status_code == 401
    assert response.json()["detail"] == "Access Denied: Invalid Security Credentials."   # ported from the old file
    assert row_count(db_session) == 0


def test_a_rejected_payload_stores_nothing(client, auth_headers, db_session):             # P22
    assert client.post(URL, json=body(grid_zone=""), headers=auth_headers).status_code == 422
    assert row_count(db_session) == 0


def test_authentication_is_checked_before_validation(client):                             # P23
    # An unauthenticated caller learns nothing about the payload rules: the body here is invalid AND the token
    # is missing, and the answer is 401, not 422 (A7: dependencies run before the body is validated).
    assert client.post(URL, json=body(grid_zone=""), headers={}).status_code == 401


def test_documents_D8_the_same_reading_posted_twice_is_stored_twice(client, auth_headers, db_session):   # P24
    # Finding D8: no unique constraint and no idempotency. POC 3 adds both and flips this assertion to 1.
    client.post(URL, json=body(), headers=auth_headers)
    client.post(URL, json=body(), headers=auth_headers)

    assert row_count(db_session) == 2


def test_documents_D6_a_failed_commit_returns_500_and_leaks_the_exception_text(           # P25
    client, auth_headers, db_session, monkeypatch
):
    # Finding D6: the exception text is echoed to the caller. Stage 6 removes it and flips the second assertion.
    def failing_commit():
        raise RuntimeError("disk on fire")

    # Replace commit() on THIS session object for this test only. The route receives the same object (via
    # dependency_overrides), so its db.commit() now raises, and its except-block runs.
    monkeypatch.setattr(db_session, "commit", failing_commit)

    response = client.post(URL, json=body(), headers=auth_headers)

    assert response.status_code == 500
    assert "disk on fire" in response.json()["detail"]


def test_the_write_route_is_a_plain_def_so_it_does_not_block_the_event_loop():            # P26
    # Finding D16: an async def route calling a synchronous database session would freeze every other request.
    # FastAPI runs a plain def on a worker thread; an async def runs on the event loop itself.
    assert not inspect.iscoroutinefunction(validate_and_transform_payload)


def test_fractional_readings_are_summed_and_stored(client, auth_headers, db_session):     # P27 (ported)
    # From the old test_integration.py: 10.50 + 15.50 gives a total of 26.0 and an average of 13.0.
    payload = {
        "meter_id": "MTR-2026-TEST",
        "grid_zone": "WEST-ZONE-ALPHA",
        "readings": [
            {"timestamp": "2026-07-28T12:00:00Z", "kwh_value": 10.50, "voltage": 220.0},
            {"timestamp": "2026-07-28T12:15:00Z", "kwh_value": 15.50, "voltage": 218.5},
        ],
    }

    response = client.post(URL, json=payload, headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["metadata"]["processed_asset"] == "MTR-2026-TEST"
    assert response.json()["analytics_summary"] == {"cumulative_kwh": 26.0, "average_load_per_interval": 13.0}
    assert row_count(db_session, "MTR-2026-TEST") == 2


def test_a_negative_consumption_value_is_rejected_and_stores_nothing(client, auth_headers, db_session):   # P28 (ported)
    # From the old test_integration.py: the rule is kwh_value > 0, so a negative value must fail as well as zero.
    payload = body(meter_id="MTR-2026-TEST")
    payload["readings"][0]["kwh_value"] = -5.0

    assert client.post(URL, json=payload, headers=auth_headers).status_code == 422
    assert row_count(db_session, "MTR-2026-TEST") == 0
