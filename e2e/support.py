import os
import subprocess
import time
import uuid
from pathlib import Path

import httpx

# Path(__file__) is this file; resolve() makes it absolute; parents[1] is the folder ABOVE e2e/, the repository root.
ROOT = Path(__file__).resolve().parents[1]
REQUEST_DIR = ROOT / "docs" / "comprehension" / "requests"   # the nine request files of Stage 0B
COMPOSE_FILE = ROOT / "docker-compose.dev.yml"

# Overridable from the shell, so that the same suite can aim at a stack on other ports (the compose file has
# commented-out variables for host ports that collide). The defaults are the compose file's published ports.
# 127.0.0.1, not "localhost". On Windows with Docker Desktop, a Python HTTP client given "localhost" tries the IPv6
# address ::1 first and loses time on every new connection before it reaches 127.0.0.1. Measured on 16 October 2026:
# the 25 non-resilience tests took 622 s through localhost and 0.65 s through 127.0.0.1. Same symptom as the database
# stall of Stage 3 (finding D32). curl hides it because it tries both addresses at once.
GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://127.0.0.1:8081")
VALIDATOR_URL = os.environ.get("VALIDATOR_URL", "http://127.0.0.1:8082")
POSTGRES_PORT = os.environ.get("POSTGRES_HOST_PORT", "5432")

JSON_HEADERS = {"Content-Type": "application/json"}

# One id per test run (A5). The contract allows a meter id of 5 to 20 characters; "MTR-E2E-" plus 8 hex digits is 16,
# and the tests add at most a 2-character suffix ("-A"), which makes 18. Everything the suite writes starts with
# METER_PREFIX, so one DELETE ... LIKE removes it all.
RUN_ID = uuid.uuid4().hex[:8]
METER_PREFIX = f"MTR-E2E-{RUN_ID}"
METER_ID = METER_PREFIX


def database_url() -> str:
    # The suite connects from the HOST to the published port of postgres-db (5432), as the credentials of the compose
    # file. The password comes from the shell (loaded from .env), never from a literal in the repository.
    # The host is 127.0.0.1 and not "localhost": on Windows with Docker Desktop a PostgreSQL connection through
    # "localhost" can stall for minutes before the first query (Stage 3, section 3.3); the numeric address cannot.
    return (
        f"postgresql://smart_meter_admin:{os.environ['POSTGRES_PASSWORD']}"
        f"@127.0.0.1:{POSTGRES_PORT}/smart_meter_warehouse"
    )


def valid_body(meter_id: str = METER_ID) -> dict:
    """Two readings: 10 and 20 kWh, so the summary is 30 in total and 15 on average. Only the first has a voltage."""
    return {
        "meter_id": meter_id,
        "grid_zone": "ZONE-A",
        "readings": [
            {"timestamp": "2026-10-09T00:00:00Z", "kwh_value": 10.0, "voltage": 230.0},
            {"timestamp": "2026-10-09T00:30:00Z", "kwh_value": 20.0},
        ],
    }


def wait_for_health(url: str, expected_status: int = 200, timeout: float = 120.0) -> httpx.Response:
    """Poll a health URL until it answers the expected status; fail with the last observation if it never does (A6)."""
    # time.monotonic() only moves forward, unlike the wall clock, which can jump (daylight saving, clock correction).
    deadline = time.monotonic() + timeout
    last = "no response"
    while time.monotonic() < deadline:
        try:
            response = httpx.get(url, timeout=3.0)
            if response.status_code == expected_status:
                return response
            last = f"HTTP {response.status_code}: {response.text[:200]}"
        except httpx.HTTPError as error:       # connection refused, timeout, reset: the service is not there (yet)
            last = repr(error)
        time.sleep(2)                           # a poll interval, not a guess at start-up time
    raise AssertionError(f"{url} did not answer HTTP {expected_status} within {timeout:.0f}s. Last: {last}")


def compose(*args: str) -> None:
    """Run `docker compose -f docker-compose.dev.yml <args>` from the repository root."""
    result = subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), *args],
        cwd=ROOT, capture_output=True, text=True,     # capture stdout and stderr as text, so a failure can print them
    )
    if result.returncode != 0:
        raise AssertionError(f"docker compose {' '.join(args)} failed:\n{result.stdout}\n{result.stderr}")
