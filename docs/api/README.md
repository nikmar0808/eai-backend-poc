# API contracts

| File | Describes | Source of truth for |
|---|---|---|
| [`gateway.openapi.yaml`](gateway.openapi.yaml) | `java-gateway`, the public API | Gateway validation, status codes, error bodies |
| [`validator.openapi.yaml`](validator.openapi.yaml) | `python-validator` | Transform and readings routes, authentication |

Both are written by hand and are the source of truth; the code conforms to them (ADR-004). OpenAPI 3.0.3.

## Validation rules (one rule set, applied by both services)

| Field | Rule |
|---|---|
| `meter_id` | string, 5 to 20 characters |
| `grid_zone` | string, 1 to 50 characters, not blank |
| `readings` | 1 to 1000 items |
| `readings[].timestamp` | RFC 3339 date-time with a UTC offset |
| `readings[].kwh_value` | number, greater than 0 |
| `readings[].voltage` | optional, 100 to 300 inclusive |
| unknown properties | ignored |

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
| 7 | Gateway answers 502 or 504 when the downstream rejects, fails, is unreachable or times out | Answers a generic 500 | Stage 6 (*timeout half closed (configuration in Stage 1A, proved in Stage 2); the 502/504 mapping remains for Stage 6*) |
| 8 | Readings `timestamp` is a local date-time without offset | Same (documented as it is) | POC 3 (`timestamptz`) |
| 9 | `details` keys are field names | The keys are Java property names (meterId) — D22 | Stage 6 |

## Conformance findings (Stage 4)

Schemathesis 4.31.1 (image `schemathesis/schemathesis:4.31.1`), run on 16 October 2026 against the running Compose
stack, with both hand-written contracts and `--continue-on-failure` (without it, the first failure stopped the
gateway's ingest route after 15 cases at 3.4% keyword coverage; with it, 198 cases at 100%). Findings 5 and 6 were also
reproduced by hand with a single clean request.

| # | Service | Finding | Verdict | Status |
|---|---|---|---|---|
| 1 | Both | `timestamp: 0` (a number) is accepted: Pydantic and Jackson both convert a number to a date | Code wrong in both | Open, Stage 6 (D29, Stage 3 finding 1, widened to the gateway) |
| 2 | Python | A body that cannot be decoded gets FastAPI's own 400, which the contract does not document | Contract incomplete; the body is not ours | Open, Stage 6 (D30, Stage 3 finding 3) |
| 3 | Gateway | `Content-Type: multipart/form-data` without a boundary answers 500, on `/health` and on the ingest route | Code wrong: a malformed request is a 400 | Open, Stage 6 (D34) |
| 4 | Gateway | A missing or unparseable body gets 400 with Spring's default body (no `details`), not the contract's `ErrorResponse`; `08-malformed-json.json` takes the same path | Code wrong: no handler for `HttpMessageNotReadableException` | Open, Stage 6 (D35) |
| 5 | Gateway | `readings: [null]` passes the gateway's rules; Python rejects it (422); the gateway answers a generic 500 (D3) | Code wrong: elements are not required to be non-null; the services disagree | Open, Stage 6 (D36) |
| 6 | Both | A time-zone offset beyond ±18:00 (allowed by RFC 3339) cannot be parsed by the gateway (400, default body) and is accepted by Python | Contract too loose; the services disagree | Open, Stage 6 (D37): the contract gains an offset pattern up to ±14:00, and both services enforce it |
| 7 | Python | A `grid_zone` or `meter_id` containing the NUL character (`\u0000`) passes validation and fails at the `INSERT` (PostgreSQL text cannot hold NUL): 500, and the body echoes the database error, the full SQL statement and the request's values | Contract too loose and code wrong (should be 422); the 500 body leaks internals | Open, Stage 6 (D39; D6 widened: the echoed text includes SQL and input values) |
