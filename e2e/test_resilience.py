import pytest

from support import GATEWAY_URL, METER_PREFIX, compose, valid_body, wait_for_health

# pytestmark applied to the module marks EVERY test in it, so -m "not resilience" deselects the whole file.
pytestmark = pytest.mark.resilience


@pytest.fixture()
def restore_stack():
    """Whatever the test did, the stack is started again and must be healthy before the next test."""
    yield                                           # the test body runs here, even if it fails afterwards
    compose("start", "postgres-db", "python-validator")   # starting a running container is harmless
    wait_for_health(f"{GATEWAY_URL}/health", 200, timeout=120)


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
def test_documents_D3_a_stopped_downstream_gives_the_client_a_generic_500(gateway, restore_stack):
    # Finding D3 (downstream half). The contract says 502; Stage 6 implements it and flips this assertion.
    compose("stop", "python-validator")
    wait_for_health(f"{GATEWAY_URL}/health", 503, timeout=60)

    response = gateway.post("/api/v1/ingest/bulk", json=valid_body(f"{METER_PREFIX}-X"))

    assert response.status_code == 500