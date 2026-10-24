import httpx
import pytest

from support import (
    GATEWAY_URL, ISSUER, METER_PREFIX, ClientCredentials, fetch_token, token_claims, valid_body,
)

INGEST = "/api/v1/ingest/bulk"


def stored_rows(db, meter_id: str) -> int:
    return db.execute("SELECT count(*) FROM smart_meter_intervals WHERE meter_id = %s", (meter_id,)).fetchone()[0]


def client_for(client_id: str) -> httpx.Client:
    """A gateway client that logs in as one of the realm's three clients (5.3)."""
    return httpx.Client(base_url=GATEWAY_URL, timeout=15.0, auth=ClientCredentials(client_id))


# E10
def test_no_token_gives_401_and_stores_nothing(anonymous_gateway, db):
    meter = f"{METER_PREFIX}-S1"
    response = anonymous_gateway.post(INGEST, json=valid_body(meter))

    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith("Bearer")
    assert response.json()["status"] == 401
    # The independent witness (Stage 4, A4): the database confirms that the refused request wrote nothing.
    assert stored_rows(db, meter) == 0


# E11
def test_a_garbage_token_gives_401(anonymous_gateway):
    response = anonymous_gateway.post(
        INGEST, json=valid_body(f"{METER_PREFIX}-S2"), headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


# E12
def test_a_valid_token_without_the_scope_gives_403(db):
    meter = f"{METER_PREFIX}-S3"
    # readonly-client is real, correctly signed, has the right audience, and lacks ingest.write (realm file, 5.3).
    with client_for("readonly-client") as client:
        response = client.post(INGEST, json=valid_body(meter))

    assert response.status_code == 403
    assert response.json()["status"] == 403
    assert stored_rows(db, meter) == 0


# E13
def test_a_token_for_another_audience_gives_401(db):
    meter = f"{METER_PREFIX}-S4"
    # outsider-client HAS the scope ingest.write, but its tokens are not meant for eai-gateway (no audience mapper).
    # The scope alone would let it in; the audience check is what keeps it out.
    with client_for("outsider-client") as client:
        response = client.post(INGEST, json=valid_body(meter))

    assert response.status_code == 401
    assert stored_rows(db, meter) == 0


# E14
def test_the_realm_issues_the_claims_the_gateway_expects():
    # The token is fetched through 127.0.0.1 (support.KEYCLOAK_URL); its issuer is still the published name (A4).
    token, lifetime = fetch_token("ingest-client")
    claims = token_claims(token)

    assert claims["iss"] == ISSUER
    audiences = [claims["aud"]] if isinstance(claims["aud"], str) else claims["aud"]    # one value is a string
    assert "eai-gateway" in audiences
    assert "ingest.write" in claims["scope"].split()
    assert lifetime <= 300                                   # short-lived by design (A5)
    assert claims["exp"] - claims["iat"] <= 300


# E15
def test_health_is_open_and_the_ingest_route_is_not(anonymous_gateway):
    health = anonymous_gateway.get("/health")
    assert health.status_code == 200                         # open: Docker's probe carries no token
    assert health.json() == {"status": "UP", "pythonValidator": "UP"}

    assert anonymous_gateway.post(INGEST, json=valid_body(f"{METER_PREFIX}-S5")).status_code == 401
