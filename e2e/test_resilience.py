import pytest

import httpx
import pytest

from support import (
    DISCOVERY_URL, GATEWAY_URL, METER_PREFIX, compose, fetch_token, valid_body, wait_for_health,
)


# pytestmark applied to the module marks EVERY test in it, so -m "not resilience" deselects the whole file.
pytestmark = pytest.mark.resilience


@pytest.fixture()
def restore_stack():
    """Whatever the test did, the stack is started again and must be healthy before the next test."""
    yield                                           # the test body runs here, even if it fails afterwards
    compose("start", "postgres-db", "python-validator", "keycloak")     # starting a running container is harmless
    wait_for_health(f"{GATEWAY_URL}/health", 200, timeout=120)
    wait_for_health(DISCOVERY_URL, 200, timeout=120)    # Keycloak needs longer than the others to be live again


# E08: runs twice, once stopping each dependency.
@pytest.mark.parametrize("service", ["python-validator", "postgres-db"])
def test_the_gateway_reports_down_while_a_dependency_is_stopped_and_recovers(restore_stack, service):
    compose("stop", service)

    down = wait_for_health(f"{GATEWAY_URL}/health", 503, timeout=60)
    # When Python is down, or the database behind it is, the gateway reports DOWN for the Python dependency.
    assert down.json() == {"status": "DOWN", "pythonValidator": "DOWN"}

    compose("start", service)
    # Up to about 30 seconds of this wait can be the JVM's own DNS cache holding the old address of a restarted
    # container (A6), so the limit is generous.
    up = wait_for_health(f"{GATEWAY_URL}/health", 200, timeout=120)
    assert up.json() == {"status": "UP", "pythonValidator": "UP"}


# E09
def test_a_stopped_downstream_gives_the_client_502_as_problem_details(gateway, restore_stack):
    # Finding D3 closed in Stage 6: the gateway answers for its downstream with 502, in the one error format.
    compose("stop", "python-validator")
    wait_for_health(f"{GATEWAY_URL}/health", 503, timeout=60)

    response = gateway.post("/api/v1/ingest/bulk", json=valid_body(f"{METER_PREFIX}-X"))

    # A stopped container is refused (502), unknown (502) or silent until the connect timeout (504), depending on the
    # network and on the JVM's DNS cache: on Docker Desktop for Windows the gateway still holds the old address and
    # its connection attempt times out. Either answer is the gateway answering for its downstream; 500 is not.
    assert response.status_code in (502, 504)
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["title"] in ("Bad Gateway", "Gateway Timeout")


# E16
def test_documents_that_tokens_still_validate_while_keycloak_is_down(restore_stack):
    # Why a token fetched HERE, with a plain header, and not the `gateway` fixture: that client renews its token on
    # its own, and a renewal while Keycloak is stopped would fail for a reason this test is not about.
    token, _ = fetch_token("ingest-client")
    headers = {"Authorization": f"Bearer {token}"}

    with httpx.Client(base_url=GATEWAY_URL, timeout=15.0, headers=headers) as client:
        # 1. Warm the gateway's cache of Keycloak's public keys: the first token makes it fetch them.
        assert client.post("/api/v1/ingest/bulk", json=valid_body(f"{METER_PREFIX}-K1")).status_code == 200

        compose("stop", "keycloak")

        # 2. Keycloak is gone. The gateway verifies this token with keys it already holds, so nothing changes.
        assert client.post("/api/v1/ingest/bulk", json=valid_body(f"{METER_PREFIX}-K2")).status_code == 200
        assert client.get("/health").status_code == 200       # and the gateway is still healthy (no dependency, 5.11)
