---
agent: speckit.constitution
---

<!--
SYNC IMPACT REPORT
==================
Version change: N/A → 1.0.0 (initial ratification)
Modified principles: N/A (initial)
Added sections: Overview, Principles (1–10), Governance
Removed sections: N/A
Templates requiring updates: N/A (no .specify templates present)
Follow-up TODOs: None
-->

# Historia Project Constitution

**Version:** 1.0.0
**Ratification date:** 2026-05-09
**Last amended:** 2026-05-09

---

## Overview

Historia is a Python command-line tool that backs up GitHub activity records
(issues, PRs, reviews, commits, comments) for a user or organization, so the
data can later power dashboard reports of work history.

This constitution defines the non-negotiable principles that govern all design,
implementation, testing, and documentation decisions in the Historia project.
Every `/speckit.specify`, `/speckit.plan`, and `/speckit.tasks` output MUST
comply with these principles. Any proposed feature that conflicts with them MUST
be flagged before work begins.

---

## Principles

### Principle 1 — CLI-first, library-backed

Every feature MUST be implemented as a function in the importable `historia`
package (`src/historia/`) and exposed through a thin CLI layer (`_cli.py`).
The CLI is a transport layer only; it parses arguments, calls library
functions, and formats output. Core logic MUST NOT reside in the CLI.

**Rationale:** Enables programmatic use, simplifies testing of core logic
independent of CLI parsing, and keeps the public API stable regardless of
CLI framework changes.

### Principle 2 — Local-first data ownership

Backups MUST be written to the local filesystem in plain, human-inspectable
formats: JSON for structured records, Markdown where narrative or human
readability is the primary goal. No remote services, external databases, or
cloud storage MAY be introduced. The user's GitHub token is the only external
dependency beyond the GitHub API itself.

**Rationale:** Guarantees that users own their data outright, that backups are
readable without tooling, and that the project has no operational
infrastructure to maintain.

### Principle 3 — Idempotent, resumable backups

Re-running a backup against the same target MUST be safe. Existing records MUST
be reconciled rather than duplicated. A long run that is interrupted MUST be
resumable without losing prior progress or re-fetching already-stored data.

**Rationale:** Backups fail; networks drop; rate limits hit. Idempotency turns
partial runs into a normal operating mode rather than an error state, and
prevents data corruption from accidental re-runs.

### Principle 4 — Respect GitHub API limits

All GitHub API access MUST go through a single rate-aware client. That client
MUST:
- Honor primary rate limits (X-RateLimit-* headers).
- Honor secondary rate limits (Retry-After on 403/429 responses).
- Paginate correctly through all multi-page responses.
- Use conditional requests (ETags / If-None-Match) wherever the GitHub API
  supports them.
- NEVER hot-loop on 403 or 429 responses.

**Rationale:** Violating GitHub's rate limits risks token suspension and
degrades the service for other users. Conditional requests reduce quota
consumption for unchanged data.

### Principle 5 — Deterministic, dashboard-ready output

The on-disk schema MUST be documented, versioned, and stable. Breaking schema
changes MUST be accompanied by a migration path and a CHANGELOG entry. The
current schema version is encoded in the output directory structure
(`version-<N>/`). Downstream dashboard tooling MUST be able to depend on the
layout without reading project source code.

**Rationale:** Historia's primary value is as a reliable data source for
downstream reporting. Unstable schemas destroy that value.

### Principle 6 — Test-driven, with layered verification

Every behavior MUST be covered by pytest tests before it is considered
complete. The test suite uses three complementary layers:

**a. Unit tests (mocks)**
Fast, deterministic coverage of business logic and edge cases. Mocks MUST
reflect real GitHub API payload shapes. When the API changes, mocks are
updated — not worked around.

**b. Integration tests (live GitHub account)**
Exercise real authentication, pagination, rate-limit handling, and end-to-end
backup flows that mocks cannot faithfully reproduce. Live tests MUST be gated
behind an opt-in marker or a separate CI job so that the default `pytest` run
remains fast and offline.

**c. Live fixture account as infrastructure**
The dedicated live GitHub account used for integration testing is treated as
project infrastructure. Its state (repos, issues, PRs used as fixtures) MUST
be documented. Destructive changes to that account require the same review
process as code changes.

**Coverage policy:** Codecov coverage MUST NOT regress. A feature is not
"done" until it has coverage at whichever layer(s) genuinely exercise it.
Adding a unit test purely to move the coverage number is discouraged and
subject to review rejection.

**Rationale:** Mocks alone miss integration-level failures; live tests alone
are slow and flaky. The layered approach balances speed, confidence, and
cost.

### Principle 7 — Typed, linted, pre-commit clean

All code MUST be fully type-annotated and MUST pass the project's pre-commit
hooks (black formatting, ruff linting, mypy or equivalent type checks) on
every commit. Use of `typing.Any` is permitted only at clearly justified
boundaries and MUST include a comment explaining the justification.

**Rationale:** Type annotations catch a class of bugs before tests run;
consistent formatting reduces review noise; pre-commit enforcement prevents
style drift.

### Principle 8 — Minimal dependencies

The standard library and a small set of well-known packages are preferred.
Adding a runtime dependency MUST be justified in the PR description with:
1. The problem the dependency solves.
2. Why the standard library or an existing dependency is insufficient.
3. A note on rejected alternatives.

**Rationale:** Each dependency is a surface area for security vulnerabilities,
breaking changes, and installation friction. Keeping the set small reduces
long-term maintenance burden.

### Principle 9 — Documentation as a deliverable

Every user-facing command, configuration option, and on-disk artifact MUST be
documented in the Sphinx docs (`docs/`) published at
`historia.readthedocs.io`. Undocumented behavior is, by project policy, a
bug and MUST be tracked as such in the issue tracker.

**Rationale:** Backup tooling is only useful if users understand what it
produces and how to invoke it. Documentation is part of the feature, not an
afterthought.

### Principle 10 — Semantic versioning and a maintained CHANGELOG

Historia MUST follow [Semantic Versioning 2.0.0](https://semver.org/).
All user-visible changes MUST be recorded in `CHANGELOG.md` under the
appropriate section before a release is cut.

**Rationale:** Users and downstream tooling depend on a predictable release
contract. The CHANGELOG provides an auditable history of decisions.

---

## Governance

### Amendment procedure

1. Open a GitHub issue or PR proposing the amendment, citing the principle(s)
   affected.
2. The proposal MUST include: the motivation, the exact wording change, and the
   version bump type (MAJOR / MINOR / PATCH) with reasoning.
3. At least one maintainer approval is required before merging.
4. Upon merge, update `Last amended` and `Version` in this document, and
   prepend a new entry to the Sync Impact Report comment at the top of this
   file.

### Versioning policy

- **MAJOR**: Backward-incompatible removal or redefinition of a principle.
- **MINOR**: Addition of a new principle or material expansion of guidance.
- **PATCH**: Clarification, wording improvement, or non-semantic refinement.

### Compliance review

Each PR that introduces a new feature or modifies existing behavior MUST
include a short compliance note confirming which principles apply and how the
change satisfies them. If a change cannot satisfy a principle, it MUST be
flagged in the PR description for explicit maintainer sign-off.

### Constitution vs. plan vs. spec precedence

In any conflict: **Constitution > Plan > Spec > Tasks**. Lower-level artifacts
MUST be updated to conform to the constitution, not the reverse.
