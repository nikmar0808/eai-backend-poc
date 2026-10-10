# Origin of this repository

`eai-backend-poc` was created on 9 October 2026 as a fresh-history copy of
[`eai-azure-poc`](https://github.com/nikmar0808/eai-azure-poc), taken with `git archive` from tag `v1.0.0`
(commit `415c99ebc96370ee33dd34a3c2b1ffe5c8316281`). No commit of the original repository is reachable from this one (ADR-001, ADR-010).

## Carried across

| Path | Notes |
|---|---|
| `01-java-ingestion-service/`, `02-python-transformation-api/` | The two backend services, unchanged at the time of import. The Python service still contains its optional Azure Monitor tracing (Phase E), switched on only when `APPLICATIONINSIGHTS_CONNECTION_STRING` is set |
| `docker-compose.dev.yml` | The frontend services were removed |
| `.env.sample`, `.gitattributes`, `.trivyignore` | Unchanged |
| `.gitignore` | The Terraform entries were removed |
| `docs/adr/ADR-001` to `ADR-003` | Still apply |

## Rewritten

`.github/workflows/ci.yml` (Azure, Node and React jobs removed; the remaining jobs keep their names),
`README.md`, and the pull request template.

## Left behind, on purpose

The Node and React frontends, all Terraform (`infra/`), the Azure documents, ADR-008 and ADR-009, and the
Azure-only CI jobs. They remain in `eai-azure-poc`, which is frozen at `v1.0.0`.