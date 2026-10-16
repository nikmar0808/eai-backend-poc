"""
What this file protects. `/health` is what Docker and the Java gateway read to decide whether the service is
ready; it must say `DOWN` with a 503 when the database does not answer (P39), and it must work with no token
(P40). The last test is an automated form of the by-eye comparison of Stage 1: the specification the
application *publishes* at `/openapi.json` must still carry the contract's rules, so a rule dropped from the
code is noticed (P41).

New idea: a hand-made fake (`BrokenEngine`). P39 needs the database to fail. A small class with the one
method the health route calls (`connect`) that raises is enough, and `monkeypatch.setattr(main_module,
"engine", BrokenEngine())` swaps it in for one test. Python needs no mocking library for this because
objects are matched by the methods they have, not by a declared type ("duck typing").

(The ideas shared by all three API files - the client and db_session fixtures, content= versus json=,
counting rows with the test's own session, documenting a known defect with a passing test - are explained at
the top of test_transform.py.)
"""
import pytest

pytestmark = pytest.mark.db


class BrokenEngine:
    """The one method the health route calls, and it fails like an unreachable database."""

    def connect(self):
        raise RuntimeError("database unreachable")


def test_the_root_route_describes_the_service_and_checks_nothing(client):                  # P37
    response = client.get("/")

    assert response.status_code == 200
    assert set(response.json()) == {"status", "engine", "version"}      # the set of keys, whatever the values


def test_health_is_up_when_the_database_answers(client):                                  # P38
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "UP", "database": "UP"}


def test_health_is_down_with_503_when_the_database_does_not_answer(client, monkeypatch):   # P39
    import app.main as main_module       # the module whose global name "engine" the health route uses

    monkeypatch.setattr(main_module, "engine", BrokenEngine())

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "DOWN", "database": "DOWN"}


def test_health_and_root_need_no_token(client):                                           # P40
    assert client.get("/health").status_code == 200
    assert client.get("/").status_code == 200


def test_the_generated_specification_carries_the_contract_rules(client):                  # P41
    # An automated form of the by-eye comparison of Stage 1, step 1.6: if a rule is dropped from the code, the
    # generated specification loses it and this test fails.
    spec = client.get("/openapi.json").json()
    schemas = spec["components"]["schemas"]

    readings = schemas["SmartMeterPayload"]["properties"]["readings"]
    assert (readings["minItems"], readings["maxItems"]) == (1, 1000)
    assert {"TransformResponse", "ReadingsResponse"} <= set(schemas)       # both response models are published
    assert set(spec["paths"]) >= {
        "/",
        "/health",
        "/api/v1/transform",
        "/api/v1/meters/{meter_id}/readings",
    }
