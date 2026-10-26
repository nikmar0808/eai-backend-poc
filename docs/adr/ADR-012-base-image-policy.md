# ADR-012: Base images by version tag, updated at build time, scanned every night, proposed by Dependabot

## Status

Accepted, 2026-10-26.

## Context

Both images start from public base images named by tag: `maven:3.9.6-eclipse-temurin-21-alpine` and
`eclipse-temurin:21-jre-alpine` for the gateway, `python:3.14-slim` for the Python service. A tag is a name the
publisher moves to each rebuild, which is how security fixes arrive, and also why one commit built on two days can
give two different images. A scan's result therefore depends on the day: in Stage 5 an advisory published while a
branch was open failed one pull request (D41), and a fix that Alpine had published but the base image did not yet
carry failed the promotion (D42, fixed with `apk upgrade`). In March 2026 the Trivy project's own release tags and
images (Trivy 0.69.4 to 0.69.6, trivy-action up to 0.34.2) were replaced by compromised content (GHSA-69fq-xp46-6x23):
a tag, of an image or of an action, is a promise by its publisher, not a guarantee. This repository was not affected
because `ci.yml` pins `trivy-action@0.35.0`.

## Decision

1. Base images are named by the most specific tag that still receives security rebuilds (`21-jre-alpine`,
   `3.14-slim`), never `latest`.
2. A runtime stage applies its distribution's security updates at build time where a scan has needed it (the
   gateway's `apk upgrade --no-cache`, D42). The Python image gets the Debian equivalent the first time a fixable
   Debian advisory fails `image-scan`.
3. Every pull request builds and scans both images (`image-scan`, ci.yml); `nightly-scan.yml` rebuilds them from
   `main` with `--pull` and scans them every night with the same rules, so an advisory is seen within a day even when
   nobody opens a pull request.
4. Dependabot proposes minor and patch updates of base-image tags, Maven and pip dependencies and actions weekly, as
   pull requests into `develop` that pass the same gates as any other change. Major versions are not proposed (each
   is a decision with its own work item), and two sets are updated by hand: the Azure Monitor tracing packages, which
   must move together, and the Maven build image, whose tag carries the Java version after Maven's (D53, Stage 7).
5. An accepted finding is an entry in `.trivyignore` with an expiry date and a comment naming the package. The file is
   re-triaged when an entry expires and at the end of each POC (D21, Stage 7).

## Consequences

- Builds are not bit-for-bit reproducible: the same commit built on another day can give another image. The nightly
  scan is what makes that visible.
- Images and actions that a step starts with `docker run` (Gitleaks, Schemathesis, oasdiff) are invisible to
  Dependabot and are pinned by hand; Gitleaks still runs as `latest` (D50).
- Production alternative: pin every base image by digest (`FROM eclipse-temurin:21-jre-alpine@sha256:...`) and every
  action by commit SHA, and let Dependabot or Renovate move the pins; build an image once and promote the same digest
  through the environments (as `enterprise-integration-azure` does with immutable tags); start from hardened or
  minimal images (distroless, Chainguard, Docker Hardened Images); sign images and verify signatures before deployment
  (Sigstore cosign); scan in the registry as well as in CI.