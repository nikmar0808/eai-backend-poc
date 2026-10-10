# ADR-010: POC 2 is carried out in a separate repository created from eai-azure-poc

## Status
Accepted — 2026-10-09

## Context
`eai-azure-poc` is published as a finished Azure Container Apps delivery. Its pipeline contains jobs that need an
Azure subscription and a gated GitHub Environment, and that subscription is temporary. Backend modernisation and
testing needs none of the Azure content, and would otherwise run beside it, on the same branches, through the same
pipeline.

## Decision
POC 2 and POC 3 are carried out in `eai-backend-poc`, created from `eai-azure-poc` at tag `v1.0.0` with a fresh
history (the technique of ADR-001). Only the backend paths are carried across. `eai-azure-poc` is frozen at that tag.
The existing `ci.yml` jobs are kept with their names, and the Azure, Node and React jobs are removed.

## Consequences
- `eai-azure-poc` remains a stable, finished artefact. Its only later change is a status banner.
- The new repository's CI runs only what it needs, and its required status checks stay meaningful.
- The two repositories share no history. `docs/ORIGIN.md` is the link between them.
- Programme ADR numbers stay global: 004 and 005 are planned here, 006 and 007 are reserved for the data layer,
  and 008 and 009 belong to `eai-azure-poc` only.