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

## Conformance findings (Stage 3)

| # | Reproduction | Verdict | Closing Stage |
|---|---|---|---|
| 1	| POST /api/v1/transform with "timestamp": 0 (a number) answers 200	| Code is wrong (the contract says string) | Open: Stage 6 |
| 2 | kwh_value values near 1e308 give an infinite sum; the response carries null in cumulative_kwh and average_load_per_interval, which the contract says are numbers | Contract is wrong (no upper bound) and the code is wrong (it accepts and does not guard) | Closed: maximum: 1000000 in both contracts; enforced by le=1000000.0 (Python) and @DecimalMax (Java); proved by P06b, T12b and a clean Schemathesis re-run |
| 3	| A body that cannot be decoded gets an undocumented 400	| Contract incomplete | Open: Stage 6 (with problem+json) Seed: 184592246219682254443862945054262018044 |
