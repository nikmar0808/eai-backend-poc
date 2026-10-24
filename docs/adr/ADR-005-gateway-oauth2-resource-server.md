# ADR-005: The gateway is an OAuth2 resource server, authenticated by Keycloak-issued JWTs

## Status

Accepted, 2026-10-17.

## Context

Until Stage 5 the Java gateway accepted any caller (recorded in Stage 4 as a known limitation). The gateway is the
only component meant to be reachable from outside; behind it, the Python service trusts a shared header token.
Callers of the ingest route are programs (meter-data systems), not people. The learner works on free tiers and
cannot rent a managed identity provider, but the design should transfer to one. In a cloud deployment the gateway
may sit behind an edge (CDN, WAF) or an API gateway product; those filter traffic and can check tokens coarsely,
but they are one path into the service, not the only one.

## Decision

1. The gateway is an OAuth2 **resource server**: it verifies JWT access tokens and does not issue them.
2. Tokens are issued by Keycloak, realm `eai`, using the **client-credentials** grant (machine to machine).
3. Authorisation uses a **scope**, `ingest.write`, required for `POST /api/v1/ingest/**`. Realm roles are not used.
4. The gateway checks, in this order: signature (keys from the JWKS endpoint), expiry, **issuer** and **audience**
   (`eai-gateway`) in a validator that has its own unit tests, then the scope. Failures of the first four are 401;
   a missing scope is 403.
5. `GET /health` and `GET /v3/api-docs/**` are open. Every other path requires authentication by default.
6. The issuer the gateway demands (Keycloak's published name, `KC_HOSTNAME`: `http://localhost:8180/realms/eai`) and
   the address from which it fetches keys (`http://keycloak:8080/...`) are separate settings, because inside Compose
   the published name and the internal address differ. Clients on the host call `127.0.0.1:8180`; the tokens they
   receive still carry the published name.
7. The gateway does not depend on Keycloak at start-up. Keys are fetched lazily and cached.
8. Keycloak runs from `docker-compose.security.yml`, layered over `docker-compose.dev.yml`, with the realm
   imported from `keycloak/eai-realm.json`; the secret comes from `.env`.
9. The gateway-to-Python hop is **unchanged** (shared `X-EAI-TOKEN` header).
10. The token checks stay in the service even if an edge or API gateway product is placed in front of it
    (defence in depth, zero trust; Stage 5, A7). Gateway offloading would be acceptable only with the service
    reachable through the gateway alone.

## Consequences

- An unauthenticated or unauthorised caller never reaches the validation or the database (tested at four levels).
- A wrong issuer or key address in a deployment is invisible to unit tests and caught only by the end-to-end suite.
- An identity-provider outage stops new tokens from being issued but does not stop callers that hold valid tokens;
  a gateway restarted during an outage cannot verify its first token.
- Tokens cannot be revoked before they expire (five minutes); the short lifetime is the control.
- The shared gateway-to-Python token remains a weakness; the production options are in Stage 5, Part D.
- The 401/403 bodies use the contract's ad hoc `ErrorResponse`; Stage 6 replaces them with `application/problem+json`.
- `/health` discloses internal status to anonymous callers (finding D27).
- Development secrets are shared among three clients and `sslRequired` is `none`; neither is acceptable in production.
