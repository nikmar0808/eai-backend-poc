# API contracts

| File | Describes | Source of truth for |
|---|---|---|
| [`gateway.openapi.yaml`](gateway.openapi.yaml) | `java-gateway`, the public API | Gateway validation, status codes, error bodies |
| [`validator.openapi.yaml`](validator.openapi.yaml) | `python-validator` | Transform and readings routes, authentication |

Both are written by hand and are the source of truth; the code conforms to them (ADR-004). OpenAPI 3.0.3.

## Validation rules (one rule set, applied by both services)

| Field | Rule |
|---|---|
| `meter_id` | string, 5 to 20 printable ASCII characters, no spaces |
| `grid_zone` | string, 1 to 50 printable ASCII characters, at least one of them visible |
| `readings` | 1 to 1000 items, none null |
| `readings[].timestamp` | an RFC 3339 date-time **string** with a UTC offset within -14:00 and +14:00, at most six fractional digits |
| `readings[].kwh_value` | a JSON **number** (not a string), greater than 0, at most 1000000 |
| `readings[].voltage` | optional, 100 to 300 inclusive |
| unknown properties | ignored |

## Error format

Every error response of both services is an RFC 9457 problem-details body, `Content-Type: application/problem+json`
(ADR-011):

| Member | Content |
|---|---|
| `type` | `about:blank` |
| `title` | The standard reason phrase of the status |
| `status` | The HTTP status |
| `detail` | A fixed explanation; never exception text, SQL or input values |
| `instance` | The request path |
| `errors` | Validation and type errors only: a list of `{field, message}`; `field` is the JSON path as sent, e.g. `readings[0].kwh_value` |

The gateway answers 400 for every rejected body and Python 422. At the gateway, a downstream rejection, failure, refused
connection or unreadable answer is 502; no answer in time, including a connection attempt that times out, is 504. A
header, URL or method refused by Spring Security's firewall is 400. Logs carry the status and field names, never the
request's values or a downstream body.

## Security

The gateway is an OAuth2 resource server (ADR-005). Callers are programs, so they obtain an access token from
Keycloak with the client-credentials grant and send it as `Authorization: Bearer <token>`. The gateway verifies the
token itself on every request; the Python service is still protected by the shared `X-EAI-TOKEN` header, which only
the gateway sends.

| Route | Who may call it | Without a valid token | Valid token, scope missing |
|---|---|---|---|
| `GET /health` | Anyone (Docker's health check carries no token) | 200 or 503 | 200 or 503 |
| `POST /api/v1/ingest/bulk` | A token with the scope `ingest.write` | 401 | 403 |
| Any other path | Any valid token (closed by default) | 401 | as the route decides |

What the gateway checks, in this order:

| Check | Expected value | Failure |
|---|---|---|
| Signature | RS256, verified with Keycloak's public keys (`/realms/eai/protocol/openid-connect/certs`) | 401 |
| Expiry | `exp` in the future (60 s clock tolerance); tokens live 300 s | 401 |
| Issuer (`iss`) | `http://localhost:8180/realms/eai`, character for character | 401 |
| Audience (`aud`) | contains `eai-gateway` | 401 |
| Scope | contains `ingest.write` (for the ingest route) | 403 |

Authentication is checked before validation: an invalid body without a token is answered 401, not 400.

Error bodies: a 401 carries the header `WWW-Authenticate: Bearer` (with `error="invalid_token"` when a token was sent
and rejected); a 403 carries `WWW-Authenticate: Bearer error="insufficient_scope"`. Both bodies are problem details
(see *Error format*).

Known limits: `/health` tells an anonymous caller whether the gateway and Python are up (D27); the gateway-to-Python
hop still uses the shared token.

## Versioning policy

- `info.version` follows semantic versioning and is `0.x` until the contract is declared stable.
- The URL prefix `/api/v1` stays until a change cannot be made compatibly; then `/api/v2` is introduced beside it.
- A breaking change (removing or renaming a response field, making an optional request field required, tightening a
  limit, changing an error body) must be made on purpose: the version in `info.version` is raised in the same pull
  request, and the breaking-change check (oasdiff, Stage 7) is acknowledged in the pull request description.

## Known deviations (the contract is ahead of the code)

| # | Contract says | Code does today | Closed in |
|---|---|---|---|
| 1 | ~~Gateway rejects `voltage` outside 100 to 300~~ | Not checked | Stage 1A |
| 2 | ~~Gateway rejects `grid_zone` longer than 50 and `readings` longer than 1000~~ | Not checked | Stage 1A |
| 3 | ~~Python rejects a naive timestamp, an empty `readings`, a blank or over-long `grid_zone`, more than 1000 readings~~ | Accepts them | Stage 1A |
| 4 | ~~Gateway `/health` reports `status: DOWN` with HTTP 503 when the downstream is down~~ | Reports `status: UP` with HTTP 503 | Stage 1A |
| 5 | ~~Gateway `/health` reflects the database through Python's `/health`~~ | Probes Python's `/`, which checks nothing downstream | Stage 1A |
| 6 | ~~Readings route rejects a `meter_id` outside 5 to 20 characters (422)~~ | Accepts any string | Stage 1A |
| 7 | ~~Gateway answers 502 or 504 when the downstream rejects, fails, is unreachable or times out~~ | Answers a generic 500 | Stage 6 |
| 8 | Readings `timestamp` is a local date-time without offset | Same (documented as it is) | POC 3 (`timestamptz`) |
| 9 | ~~`details` keys are field names~~ | The keys are Java property names (meterId) — D22 | Stage 6 |

## Conformance findings (Stage 4)

Schemathesis 4.31.1 (image `schemathesis/schemathesis:4.31.1`), run on 16 October 2026 against the running Compose
stack, with both hand-written contracts and `--continue-on-failure` (without it, the first failure stopped the
gateway's ingest route after 15 cases at 3.4% keyword coverage; with it, 198 cases at 100%). Findings 5 and 6 were also
reproduced by hand with a single clean request.

| # | Service | Finding | Verdict | Status |
|---|---|---|---|---|
| 1 | Both | `timestamp: 0` (a number) is accepted: Pydantic and Jackson both convert a number to a date | Code wrong in both | Closed (Stage 6, D29) |
| 2 | Python | A body that cannot be decoded gets FastAPI's own 400, which the contract does not document | Contract incomplete; the body is not ours | Closed (Stage 6, D30) |
| 3 | Gateway | `Content-Type: multipart/form-data` without a boundary answers 500, on `/health` and on the ingest route | Code wrong: a malformed request is a 400 | Closed (Stage 6, D34) |
| 4 | Gateway | A missing or unparseable body gets 400 with Spring's default body (no `details`), not the contract's `ErrorResponse`; `08-malformed-json.json` takes the same path | Code wrong: no handler for `HttpMessageNotReadableException` | Closed (Stage 6, D35) |
| 5 | Gateway | `readings: [null]` passes the gateway's rules; Python rejects it (422); the gateway answers a generic 500 (D3) | Code wrong: elements are not required to be non-null; the services disagree | Closed (Stage 6, D36) |
| 6 | Both | A time-zone offset beyond ±18:00 (allowed by RFC 3339) cannot be parsed by the gateway (400, default body) and is accepted by Python | Contract too loose; the services disagree | Closed (Stage 6, D37) |
| 7 | Python | A `grid_zone` or `meter_id` containing the NUL character (`\u0000`) passes validation and fails at the `INSERT` (PostgreSQL text cannot hold NUL): 500, and the body echoes the database error, the full SQL statement and the request's values | Contract too loose and code wrong (should be 422); the 500 body leaks internals | Closed (Stage 6, D39; D6) |

Accepted by design (Stage 6): the timestamp pattern is stricter than RFC 3339 (no lower-case `t` or `z`, at most six
fractional digits), so Schemathesis may report a generated date-time as "rejected although schema-compliant".

## Conformance findings (Stage 6)

Schemathesis 4.31.1 against the gateway after Stage 6A (25 October 2026), in CI and locally.

| # | Finding | Status |
|---|---|---|
| D44 | A header, URL or method refused by Spring Security's firewall answered 500 | Closed (Stage 6): 400 problem details |
| D45 | Java counted identifier length in UTF-16 code units, the contract and Python in characters | Closed (Stage 6): identifiers are printable ASCII |
| D46 | The contract constrained an `Idempotency-Key` header the gateway ignored | Closed (Stage 6): header removed until POC 3 implements it (D8) |
| D47 | `TRACE` answers 400 problem details, not 405: Tomcat refuses the method before Spring runs | Accepted by design; production edges block `TRACE` |
| D48 | A JSON boolean or number was accepted as a string, and a string as a number | Closed (Stage 6): strict JSON types in both services |
