# ADR-004: Contract-first OpenAPI, with hand-written contracts as the source of truth

## Status
Accepted — 2026-10-10

## Context
The Java gateway and the Python service were written independently and disagreed on what a valid request is (finding D19):
voltage range, time-zone offset, empty readings and blank zone were each enforced by one service only. Generating the
OpenAPI document from the code would only have documented the disagreement.

## Decision
The OpenAPI documents in `docs/api/` are written by hand and are the source of truth. Both services are made to conform
to one rule set stated in `docs/api/README.md`; where they differ, the stricter rule wins. The documents are linted in CI
(Spectral, warnings fail the job), and a breaking-change check (oasdiff) is added to CI in Stage 7. Deviations of the
code from the contract are listed, with the stage that closes each, in `docs/api/README.md`.

## Consequences
- A contract change is a deliberate act, visible in a pull request, and a version change when it can break a client.
- The contract can run ahead of the code, so a deviations table has to be kept honest.
- The generated specifications (springdoc, FastAPI) are used to check the contract, never the other way round.
- The two contracts repeat shared schemas, because the tools need each file to stand alone; a comparison keeps them equal.