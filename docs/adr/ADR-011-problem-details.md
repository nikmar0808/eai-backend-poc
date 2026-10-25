# ADR-011: One error format, RFC 9457 problem details, in both services

## Status

Accepted, 2026-10-25.

## Context

Until Stage 6 the two services answered errors in five shapes: the gateway's validation body, its 401/403 body,
Spring's default 400, a bare 500 for every downstream failure, and FastAPI's bodies, one of which echoed database
errors with SQL and input values. Contract runs (Stages 3 and 4) found ten defects in these paths.

## Decision

1. Every error response of both services is `application/problem+json` with `type`, `title`, `status`, `detail` and
   `instance`; validation and type errors add `errors`, a list of `{field, message}` with the JSON path as sent.
2. `type` is `about:blank`; `title` is the status's reason phrase; `detail` is a fixed sentence chosen by the code.
3. The gateway maps downstream rejections, failures, refused connections and unreadable answers to 502, and no answer
   in time (including a connection attempt that times out) to 504, and logs the downstream status only. A request
   refused by Spring Security's firewall is 400.
4. No response contains exception text, SQL, table or column names, or input values; logs carry exception class names.
5. Python keeps 422 for validation errors; the gateway uses 400. The services must agree on accept or reject.
6. The input rules are strict: the timestamp is a string matching one regular expression (offset within +-14:00),
   identifiers are printable ASCII, readings are not null, a JSON value of the wrong type is refused (no boolean or
   number for a string, no string for a number); enforced by both services and both contracts.
7. Both contracts are 0.2.0.

## Consequences

- A client handles one error shape; monitoring can count by status and title.
- New endpoints inherit the format (Spring's base handler, FastAPI's registered handlers).
- Typed problem URIs with documentation pages are a later step for a public API.
- Every error test of earlier stages was adapted once; the e2e matrix guards the shared rules.
