import pytest

pytestmark = pytest.mark.db


class BrokenEngine:
    def connect(self):
        raise RuntimeError("database unreachable")


def test_the_root_route_describes_the_service_and_checks_nothing(client):
    response = client.get("/")

    assert response.status_code == 200
    assert set(response.json()) == {"status", "engine", "version"}


def test_health_is_up_when_the_database_answers(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "UP", "database": "UP"}


def test_health_is_down_with_503_when_the_database_does_not_answer(client, monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(main_module, "engine", BrokenEngine())

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "DOWN", "database": "DOWN"}


def test_health_and_root_need_no_token(client):
    assert client.get("/health").status_code == 200
    assert client.get("/").status_code == 200


def test_the_generated_specification_carries_the_contract_rules(client):
    # An automated form of the by-eye comparison of Stage 1, step 1.6: if a rule is dropped from the code, the
    # generated specification loses it and this test fails.
    spec = client.get("/openapi.json").json()
    schemas = spec["components"]["schemas"]

    readings = schemas["SmartMeterPayload"]["properties"]["readings"]
    assert (readings["minItems"], readings["maxItems"]) == (1, 1000)
    assert {"TransformResponse", "ReadingsResponse"} <= set(schemas)
    assert set(spec["paths"]) >= {
        "/",
        "/health",
        "/api/v1/transform",
        "/api/v1/meters/{meter_id}/readings",
    }