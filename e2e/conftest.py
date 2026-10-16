import os

import httpx
import psycopg
import pytest

from support import GATEWAY_URL, METER_PREFIX, VALIDATOR_URL, database_url, wait_for_health

REQUIRED_ENVIRONMENT = ("API_SECURITY_TOKEN", "POSTGRES_PASSWORD")


# A HOOK: pytest calls a function with exactly this name once, before collecting any test. It is how a conftest asks
# pytest to stop early with a clear message.
def pytest_sessionstart(session: pytest.Session) -> None:
    missing = [name for name in REQUIRED_ENVIRONMENT if not os.environ.get(name)]
    if missing:
        pytest.exit(
            f"Not set in this shell: {', '.join(missing)}. Load .env first (the loader of Stage 0B, section 0B.2).",
            returncode=3,
        )


# scope="session": built once for the whole run. autouse=True: applies to every test without being named.
@pytest.fixture(scope="session", autouse=True)
def stack() -> None:
    """Fail early, and clearly, if the stack is not up (layer 2 of A6)."""
    wait_for_health(f"{GATEWAY_URL}/health")
    wait_for_health(f"{VALIDATOR_URL}/health")


@pytest.fixture(scope="session", autouse=True)
def remove_test_rows(stack):       # naming `stack` makes pytest build it first
    yield                          # everything before yield is set-up (nothing); the tests run here; after it, tear-down
    # A new connection: the resilience tests stop PostgreSQL, which kills any connection opened earlier (A5).
    # autocommit=True makes the DELETE take effect at once, without an explicit commit.
    with psycopg.connect(database_url(), autocommit=True) as connection:
        connection.execute("DELETE FROM smart_meter_intervals WHERE meter_id LIKE %s", (METER_PREFIX + "%",))


@pytest.fixture(scope="session")
def gateway():
    # One client for the run: it reuses connections. base_url lets tests write only the path. timeout=15 is longer
    # than the gateway's own timeouts to Python (Stage 1A), so a slow downstream shows as the gateway's error, not as
    # this client giving up first.
    with httpx.Client(base_url=GATEWAY_URL, timeout=15.0) as client:
        yield client


@pytest.fixture(scope="session")
def validator():
    with httpx.Client(base_url=VALIDATOR_URL, timeout=15.0) as client:
        yield client


@pytest.fixture(scope="session")
def auth() -> dict[str, str]:
    # The header the Python service requires. The token is read from the environment and never written down.
    return {"X-EAI-TOKEN": os.environ["API_SECURITY_TOKEN"]}


@pytest.fixture()    # the default scope is "function": a fresh connection for every test that asks for `db`
def db():
    with psycopg.connect(database_url(), autocommit=True) as connection:
        yield connection
