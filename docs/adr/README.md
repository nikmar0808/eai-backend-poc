# Architecture decision records

| ADR | Title | Status |
|---|---|---|
| [001](ADR-001-fresh-history-copies.md) | POC repositories are fresh-history copies | Accepted |
| [002](ADR-002-branching-model.md) | Branching model and merge methods | Accepted |
| [003](ADR-003-repository-visibility.md) | Repository visibility | Accepted |
| [004](ADR-004-contract-first-openapi.md) | contract-first APIs | Accepted |
| [005](ADR-005-gateway-oauth2-resource-server.md) | Gateway is an OAuth2 resource server, authenticated by Keycloak-issued JWTs | Accepted |
| [010](ADR-010-poc2-separate-repository.md) | POC 2 is carried out in a separate repository | Accepted |
| [011](ADR-011-problem-details.md) | One error format, RFC 9457 problem details, in both services | Accepted |
| [012](ADR-012-base-image-policy.md) | Base images by version tag, updated at build time, scanned every night, proposed by Dependabot | Accepted |

Numbers 006 and 007 are reserved for the data layer (migration tool, audit store). Numbers 008 and 009 belong to
`eai-azure-poc` (edge layer, Azure delivery pipeline) and are not copied here.
