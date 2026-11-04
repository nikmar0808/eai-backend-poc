# Retrospective

What the author set out to do here, what happened, and what would be done differently. It covers this repository and
[`db-lab`](https://github.com/nikmar0808/db-lab), from 9 October to 4 November 2026.

## The goal

To bring an enterprise integration background of about 20 years, last hands-on with code around 2013, up to date with how
backends are built and tested today. The method was a series of working proofs of concept, using only free-tier tools.
The code and the documents behind each step were produced with AI assistance. The author ran every step, read every
result, and took the decisions. None of this has run in production.

## What went well

- **The gates found real faults, including in code that nobody had just changed.** A blocking Schemathesis run found that
  an empty string passed as a missing voltage, on a pull request that had not caused it. A nightly scan found two fixable
  vulnerabilities on an unchanged branch.
- **Deliberate failures proved the gates.** Each gate was shown blocking a pull request with a planted fault, so its
  green result means something.
- **A recorded baseline made refactoring safe,** before any test suite existed.
- **Building one feature several ways made the differences visible:** the same task in plain JDBC, `JdbcClient`, JPA and a
  database function, and the same audit record in PostgreSQL and MongoDB, with measured results.
- **Pre-checking each document's code on the real machine, before the steps were written,** cut the corrections found
  during a run from 28 and 13 in the last two stages without it to between zero and three in each stage with it.

## What did not go well

- **Time.** Later POC 2 stages took up to twice their estimate. One 4-hour stage took a full day.
- **Understanding lagged behind execution in the early testing stages.** Following exact steps produced a green build
  faster than it produced the ability to design such a suite from nothing. Later documents were rewritten to teach one idea
  at a time, starting from what the author had actually used before.
- **A dependency bot looks at one package at a time.** Its first run opened eight pull requests, four of which could not
  pass. Rules were needed for major versions and for packages that must move together.
- **Windows surprises cost hours:** `localhost` against `127.0.0.1` took one test run from under a second to ten minutes,
  and a file saved as UTF-16 silently disabled a `.gitignore`.

## What would be done differently

- Start with the data layer's design: a migration tool from the first day, `timestamptz`, and uniqueness rules. Fixing
  them later needed conversions and a short outage.
- Write the idempotency rule into the first contract. A client's retry is normal, not an edge case.
- Teach before executing, and pre-check before writing, from the first stage.

## What remains

The limitations are listed in the [README](../README.md#known-limitations). The next steps are practice at designing test
suites without a guide, an upgrade to Spring Boot 4, and experience on real projects.