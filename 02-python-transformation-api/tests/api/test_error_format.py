"""Every error of the Python service is application/problem+json, and none carries internals (P46 to P51; P48 replaces
P25 of test_transform.py).

New ideas: a planted secret (a recognisable string inside the simulated failure) proves by its absence that nothing
of the exception reaches the client; monkeypatch replaces one function for one test only.
"""

import pytest

pytestmark = pytest.mark.db          # the client fixture opens a database session

PROBLEM_JSON = "application/problem+json"
TRANSFORM = "/api/v1/transform"


def valid_body() -> dict[str, object]:
    return {
        "meter_id": "MTR-POC2-001",
        "grid_zone": "ZONE-A",
        "readings": [{"timestamp": "2026-10-09T00:00:00Z", "kwh_value": 12.5}],
    }


def test_a_422_is_problem_json_naming_the_field(client, auth_headers):                 # P46
    body = valid_body()
    body["readings"] = [{"timestamp": "2026-10-09T00:00:00Z", "kwh_value": 0}]

    response = client.post(TRANSFORM, json=body, headers=auth_headers)

    assert response.status_code == 422
    assert response.headers["content-type"].startswith(PROBLEM_JSON)
    problem = response.json()
    assert problem["title"] in ("Unprocessable Content", "Unprocessable Entity")
    assert problem["instance"] == TRANSFORM
    assert "readings[0].kwh_value" in [error["field"] for error in problem["errors"]]
    assert all("input" not in error for error in problem["errors"])     # the client's value is not echoed


def test_a_401_is_problem_json(client):                                                 # P47
    response = client.post(TRANSFORM, json=valid_body())

    assert response.status_code == 401
    assert response.headers["content-type"].startswith(PROBLEM_JSON)
    assert response.json()["detail"] == "Access Denied: Invalid Security Credentials."


def test_a_database_failure_gives_500_without_internals(client, auth_headers, monkeypatch):   # P48 (was P25), D6
    def failing_store(db, payload):
        # What a real psycopg error's text looks like: SQL, table, column names and a value.
        raise RuntimeError("[SQL: INSERT INTO smart_meter_intervals (meter_id) VALUES (%(m)s)] [parameters: SECRET-42]")

    # The route calls the name store_readings in ITS OWN module (transform.py imported it), so that is where it is
    # replaced.
    monkeypatch.setattr("app.api.transform.store_readings", failing_store)

    response = client.post(TRANSFORM, json=valid_body(), headers=auth_headers)

    assert response.status_code == 500
    assert response.headers["content-type"].startswith(PROBLEM_JSON)
    assert response.json()["detail"] == "The readings could not be stored."
    for secret in ("INSERT", "smart_meter_intervals", "SECRET-42"):
        assert secret not in response.text


def test_an_undecodable_body_gives_400_problem_json(client, auth_headers):             # P49, D30
    # Bytes that are not UTF-8 under a JSON content type: FastAPI cannot even decode them.
    headers = {**auth_headers, "Content-Type": "application/json"}
    response = client.post(TRANSFORM, content=b'{"meter_id": "\xff\xfe"}', headers=headers)

    assert response.status_code == 400
    assert response.headers["content-type"].startswith(PROBLEM_JSON)


def test_an_unknown_route_gives_404_problem_json(client):                              # P50
    response = client.get("/api/v1/no-such-route")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith(PROBLEM_JSON)


def test_malformed_json_gives_422_without_a_field_list(client, auth_headers):          # P51
    # Stage 4's lesson (D35): a status-only assertion hid a broken body. Here the body is checked too.
    headers = {**auth_headers, "Content-Type": "application/json"}
    response = client.post(TRANSFORM, content=b'{"meter_id": ', headers=headers)

    assert response.status_code == 422
    assert response.headers["content-type"].startswith(PROBLEM_JSON)
    assert response.json()["detail"] == "The request body is not well-formed JSON."
    assert "errors" not in response.json()
