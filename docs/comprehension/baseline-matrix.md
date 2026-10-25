# Baseline matrix

## Observed behaviour before any POC 2 change

Taken on 2026-10-09 from commit `short SHA of develop - 415c99ebc96370ee33dd34a3c2b1ffe5c8316281` with `scripts/replay-requests.ps1`.
Any later change in this table is either an intended contract change (recorded in the stage that made it)
or a regression.

| Request | Java gateway | Python direct | Why (to be confirmed in 0B.6) |
|---|---|---|---|
| 01-valid | **500** | 200 | Python accepts; the gateway's call to Python fails (D23), so the gateway answers a generic 500. Becomes 200 when D23 is fixed in Stage 1A |
| 02-kwh-zero | 400 | 422 | Java `@Positive` and Python `gt=0.0` agree on rejecting; the status codes differ |
| 03-voltage-too-low | **500** | 422 | Java has no voltage rule, so it forwards. Today the call fails at D23 before Python validates; once D23 is fixed it reaches Python, which rejects with 422. Either way the gateway has no handler for a downstream failure and answers a generic 500 (D3, D19) |
| 04-timestamp-no-offset | 400 | **200** | Java requires an offset (`OffsetDateTime`); Python accepts a naive `datetime` (D19) |
| 05-empty-readings | 400 | **200** | Java `@NotEmpty`; Python has no minimum (D19) |
| 06-blank-grid-zone | 400 | **200** | Java `@NotBlank`; Python has no minimum length (D19) |
| 07-meter-id-too-short | 400 | 422 | Both enforce 5 to 20 characters |
| 08-malformed-json | 400 | 422 | Both reject; again the codes differ |
| 09-missing-readings-field | 400 | 422 | Both reject |

Confirmed using:

| Hop | File | What to note |
|---|---|---|
| Client → gateway | `api/IngestionController.java` | Route `POST /api/v1/ingest/bulk`; `@Valid` on `BulkIngestionRequest`; the return type is a typed `TransformationResponse` |
| Validation rules (Java) | `api/dto/BulkIngestionRequest.java`, `api/dto/MeterReadingRequest.java` | Meter ID 5 to 20 characters; blank zone rejected; readings non-empty; `kwhValue` `@Positive`; `timestamp` is an `OffsetDateTime`; **`voltage` has no annotation** |
| Validation failures (Java) | `api/ApiExceptionHandler.java` | Handles `MethodArgumentNotValidException` only. Which exceptions are *not* handled? |
| Orchestration | `service/IngestionService.java` | One line of logic. What does the layer add? |
| Gateway → Python | `client/TransformationClient.java` | `POST /api/v1/transform`; header `X-EAI-TOKEN` set once in the constructor; **no timeout**; one call, no retry |
| Configuration (Java) | `configuration/IntegrationProperties.java`, `AppConfiguration.java`, `src/main/resources/application.properties` | `@Validated` and `@NotBlank` make startup fail if the base URL or token is empty. Which environment-variable spelling does `application.properties` use? (question 12) |
| Health (Java) | `api/HealthController.java` | Builds its own `RestClient` with a 2-second timeout; probes Python's `/`; `"UP"` plus HTTP 503 when the downstream is down |
| Authentication (Python) | `app/api/authenticator.py` | Header `X-EAI-TOKEN`; plain `==` comparison (D7); warning logged on failure |
| Validation (Python) | `app/schemas/meter.py` | `kwh_value` `gt=0`; `voltage` 100 to 300; `timestamp` is a plain `datetime`; no minimum lengths on `grid_zone` or `readings` |
| Write route | `app/api/transform.py` | Declared `async def`; synchronous `Session`; loop adds one `SmartMeterIntervalRecord` per reading; one `commit()`; `except Exception` echoes the exception text (D6); long commented-out block (D17) |
| Read route | `app/api/readings.py` | Plain `def`; `limit` bounded 1 to 100; ordered by `timestamp` descending; returns a plain `dict` |
| Persistence | `app/database/models.py`, `connection.py` | Naive `DateTime`; `utcnow` default; engine pool `pool_size=10`, `max_overflow=20` |
| Startup and health | `app/main.py` | `create_all` at import (D9); `lifespan`; `/` and `/health` |
| Configuration (Python) | `app/config.py` | `API_SECURITY_TOKEN` has no default, so import fails without it; `connection.py` uses `os.environ["DATABASE_URL"]`, which raises `KeyError` |
| Unreferenced code | `app/services/transformer.py` | Is `LegacyXMLTransformer` imported anywhere? |

## After Stage 1A
Taken on 2026-10-11 from commit `short SHA of develop - 7182d35a377c5cbdac928e578daecf00dae9a0aa` with scripts/replay-requests.ps1.

| Request | Java gateway | Python direct |
| --- | --- | --- |
| 01-valid.json                  | 200  | 200 |
| 02-kwh-zero.json               | 400  | 422 |
| 03-voltage-too-low.json        | 400  | 422 |
| 04-timestamp-no-offset.json    | 400  | 422 |
| 05-empty-readings.json         | 400  | 422 |
| 06-blank-grid-zone.json        | 400  | 422 |
| 07-meter-id-too-short.json     | 400  | 422 |
| 08-malformed-json.json         | 400  | 422 |
| 09-missing-readings-field.json | 400  | 422 |

Intended changes against the baseline: row 03 Java 500 to 400 (Java now enforces the voltage range); rows 04 to 06
Python 200 to 422 (Python now enforces the offset, the minimum number of readings and the non-blank zone). The two
services now agree on accept or reject for every row; the status codes differ by design until Stage 6.

## After Stage 6 (25 October 2026)

Statuses with both services after Stage 6. Rows 01 to 09 are unchanged; rows 10 to 13 are new and each guards one rule
that both services now enforce. The gateway answers 400 and Python 422 for every rejection; both bodies are
`application/problem+json`.

| File | Gateway | Python | Rule |
|---|---|---|---|
| 01-valid.json | 200 | 200 | — |
| 02-kwh-zero.json | 400 | 422 | kwh_value above 0 |
| 03-voltage-too-low.json | 400 | 422 | voltage 100 to 300 |
| 04-timestamp-no-offset.json | 400 | 422 | offset mandatory |
| 05-empty-readings.json | 400 | 422 | 1 to 1000 readings |
| 06-blank-grid-zone.json | 400 | 422 | a visible character |
| 07-meter-id-too-short.json | 400 | 422 | 5 to 20 characters |
| 08-malformed-json.json | 400 | 422 | well-formed JSON |
| 09-missing-readings-field.json | 400 | 422 | readings required |
| 10-timestamp-as-number.json | 400 | 422 | timestamp is a string (D29) |
| 11-offset-beyond-14-hours.json | 400 | 422 | offset within +-14:00 (D37) |
| 12-null-reading.json | 400 | 422 | no null reading (D36) |
| 13-control-character-in-grid-zone.json | 400 | 422 | no control characters (D39) |
