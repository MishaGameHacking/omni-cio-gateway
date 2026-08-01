# Project audit — 2026-08-01

## Audit mandate

This audit was started before continuing the functional roadmap. Its purpose is
to compare the repository, CI evidence, dependencies, documentation and open
work against the Omni-CIO master plan and the mandatory read-only boundaries.

The audit does not authorize trading, does not call production T-Invest or
Render, and does not treat a passing local or CI test as external production
acceptance.

## Immutable acceptance boundaries

- Render entrypoint: `app:app`;
- exactly 14 user-facing GET Actions total;
- `trading_methods=false`;
- no order create/replace/cancel, stop order, transfer or withdrawal method;
- no real broker payload or secret in GitHub;
- every package uses a separate branch and Pull Request;
- squash merge only after exact-head Regression Shield;
- external Render/Gateway/GPT acceptance remains separate.

## Evidence inspected

- `main` and recent merge history through functional PR-104 and infrastructure
  PR #130;
- open Pull Requests and issue #27;
- PR #130 diff, PowerShell source, tests, runbook, workflow runs and job logs;
- latest successful PR-104 and PR #130 Regression Shield evidence;
- `AGENTS.md`, README, project-memory/status files and dependency constraints;
- current Python and GitHub Actions Dependabot queue;
- official GitHub documentation for status checks, self-hosted runner service
  configuration and ephemeral-runner behavior.

## Current main verdict

Functional audit base:

`34708f82d20e054bdd420ac1e9993c6d117e12d7`

This was the squash merge of PR-104, the fixed NCR issuer rating-action source.
Its exact-head Regression Shield passed both blocking jobs with 1235 tests,
61.97% coverage, mypy over 188 files, lock verification, Ruff, formatting,
pip-audit, Bandit, secret scan, stable `app:app`, exactly 14 GET Actions and
`trading_methods=false`.

Current `main` after the infrastructure correction:

`52a818daa64f4290fd6f551fbbc7f77bea3a94b2`

This is the squash merge of PR #130. Its fresh merge-ref Regression Shield run
#810 passed both blocking jobs with 1241 tests, 61.97% coverage, mypy over 188
files, all release-contract and security gates, and a diagnostics artifact.

No failing repository code/security check was found at these accepted boundaries.
This does not prove every future input path or external production integration
is defect-free, and it does not close the production acceptance gap.

## Screenshot red-cross diagnosis

The red cross shown beside PR #130 was the aggregate status of checks for the
PR commit/merge-ref represented at that time. It was not a per-file error
indicator and did not mean that every changed file was broken.

Historical Regression Shield run #787 on old PR #130 head
`931d47e4d4954976fd2477f2d330310242027160` had this result:

- dependency/code/secret security job: passed;
- lock verification: passed;
- repository structure: passed;
- compile: passed;
- Ruff and formatting: passed;
- mypy: passed;
- stable `app:app`: passed;
- exact 14-GET read-only contract: passed;
- pytest: one failure, 1016 passed, 19 warnings.

The failed test was the ACRA evidence-retention deterministic-clock assertion.
That defect was subsequently fixed in PR #131 and merged to `main`. The old red
cross remained historical status evidence and could not be reused as acceptance
for a changed PR head.

## Real defects found in PR #130

The old CI failure was not the only concern. Manual source review found two
security/diagnostic contract defects in the PR itself:

1. `.service` was read without a byte bound or a dedicated typed parse failure;
2. raw `.service` content could be passed to `Get-Service -Name`, whose `Name`
   parameter supports wildcard patterns, contradicting the PR's exact-match
   boundary.

Additional gaps:

- no explicit missing/invalid/mismatched service-marker states;
- no Windows fixture tests for wildcard or oversized marker content;
- fallback wildcard-first service discovery could choose a service before exact
  identity was established.

## PR #130 corrections and acceptance

The PR was updated to:

- require `.service`;
- cap `.service` at 1 KiB and reject empty content;
- permit only bounded official-style service-name characters;
- reject wildcard, whitespace and filter/shell metacharacters before any query;
- require exact `.omni-cio-ci.service` suffix;
- enumerate service inventory and select only ordinal case-insensitive exact
  name equality;
- emit no raw marker, service name, path or machine-local value;
- add typed failures:
  - `RUNNER_SERVICE_MARKER_MISSING`;
  - `RUNNER_SERVICE_MARKER_INVALID`;
  - `RUNNER_SERVICE_MARKER_IDENTITY_MISMATCH`;
- add Windows-native tests for missing, wildcard, oversized, mismatched and
  valid-but-uninstalled marker cases;
- update the recovery runbook to use the exact validated `.service` value.

Final PR #130 head:

`d0c1d3a06e7d0f4f4ea5a2d85908d6c4bf5d1a6b`.

Regression Shield run #810:

- security job: success;
- quality/contracts/coverage job: success;
- 1241 tests passed;
- 19 warnings;
- coverage 61.97%, threshold >=60%;
- mypy: 188 source files, no issues;
- `app:app`, exactly 14 GET Actions, forbidden surface count 0 and
  `trading_methods=false` verified;
- pip-audit, Bandit and secret scan passed;
- diagnostics artifact ID `8817049137`.

PR #130 was then squash-merged as
`52a818daa64f4290fd6f551fbbc7f77bea3a94b2`.

## Documentation and project-memory drift

The repository had contradictory current-state claims:

- `knowledge/16_CURRENT_PROGRAM_STATUS.md` described PR-104 as active and
  unmerged although PR-104 was already in `main`;
- `knowledge/00_PROJECT_MASTER_CONTEXT.md` retained a local section claiming
  PR-81 was the current functional top;
- issue #27 described an older release top and obsolete blocker state;
- README's detailed release narrative stopped before the actual PR-104 top.

This is operationally significant: a new agent following stale text could start
the wrong package, duplicate work or misclassify a closed blocker.

Corrective policy implemented in audit PR #137:

- current code in `main` wins over narrative documents;
- `knowledge/16_CURRENT_PROGRAM_STATUS.md` carries the current merged top and
  next safe candidate;
- long-lived master context does not hard-code a temporary active PR as an
  authoritative fact;
- issue #27 remains the live roadmap tracker and must be refreshed after merge;
- CI success, external acceptance and future master-plan goals remain distinct.

## Dependency audit

Current direct constraints remain exact and locks remain SHA-256 hash-locked.
The direct runtime pins inspected were:

- `fastapi==0.140.9`;
- `httpx==0.28.1`;
- `t-tech-investments==1.49.2`;
- `uvicorn==0.51.0`;
- `websockets==16.1.1`.

Current direct development/security pins included:

- `pytest==8.4.2`;
- `pytest-cov==7.1.0`;
- `ruff==0.16.0`;
- `mypy==2.3.0`;
- `pip-audit==2.10.1`;
- `bandit==1.9.4`;
- `detect-secrets==1.5.0`.

Open Dependabot PRs include FastAPI, pytest and major GitHub Action updates. A
green icon on an older branch is insufficient when the merge-ref predates the
latest `main`. Required treatment for each dependency PR:

1. regenerate a current merge-ref;
2. review official release notes and breaking changes;
3. regenerate all affected hash locks;
4. inspect every transitive change;
5. run the complete Regression Shield;
6. preserve full-SHA Action pins;
7. document rollback;
8. merge one logical compatibility package at a time.

The pytest major transition and GitHub Action runtime transitions are not safe
blind auto-merges.

## Warning debt

The latest green Regression Shield reports 19 non-blocking warnings:

- deprecated Starlette/FastAPI TestClient integration path using current HTTPX;
- deprecated T-Invest request identity fields based on `figi`;
- Pydantic serializer warnings in final-review tests;
- GitHub Action Node runtime, `punycode` and legacy URL API warnings.

These warnings did not fail the current release gate, but they are active debt.
Each class needs one of:

- a compatibility fix with tests;
- a documented upstream blocker and expiry/review date;
- an explicit proven-safe suppression scoped to the exact warning.

Global warning suppression is prohibited.

## Architecture and chain integration verdict

The audited release boundary remains internally consistent:

- user-facing Gateway remains read-only;
- market/rating sources added after PR-84 remain internal fixed-source packages;
- no public Action count increase was found;
- no startup fetch or broker write was introduced by PR-104 or PR #130;
- Telegram runtime remains retired;
- source/cache/observability/alert/evidence packages remain separated by agency
  and do not authorize execution;
- PR #130 changes only CI diagnostics, tests and documentation.

Remaining chain gaps from the master plan are incomplete program work, not
proof that already declared scopes are broken:

- production-grade news and corporate events;
- external versioned RAG with freshness and citations;
- exact production frontend/owner binding;
- SberInvestments HTML report import and cabinet archive/comparison;
- real Render/Gateway/GPT acceptance evidence;
- broader monitoring and incident operations;
- all live-trading admission stages, still disabled.

## External acceptance gap

The following cannot be proven from repository CI and remain open:

1. Render deploy commit identity;
2. cache-busted `/health` response;
3. production auth-negative result;
4. production exact-route positive result;
5. GPT Editor schema import;
6. authenticated GPT Preview;
7. complete GPT Action-list inspection;
8. rollback restore.

No repository document may mark these complete without real external evidence.

## Merge and continuation gates

Functional roadmap work remains paused until:

- audit PR #137 passes exact-head Regression Shield and merges;
- issue #27 agrees with the accepted `main` state;
- warning classes are registered and prioritized;
- every open dependency PR is classified as merge, revise, supersede or close;
- no unresolved review thread or required check remains red;
- the next package starts from the latest verified `main`.

After these gates, the next logical functional package is a separate NCR
rating-action cache with explicit fresh/stale/unavailable states, single-flight
refresh, bounded retention and no silent stale result. It must not add a route,
startup fetch, frontend field, cross-agency scale merge or trading method.

## Audit status

- latest merged `main`: functional PR-104 plus CI infrastructure PR #130;
- PR #130 source hardening: merged after full successful Regression Shield;
- current program status reconciliation: applied in audit PR #137;
- durable master context and README drift: corrected in audit PR #137;
- issue #27 stale references: pending synchronization after audit merge;
- dependency queue: classified, not blindly merged;
- warning debt: identified and registered;
- external acceptance: still open;
- live trading: disabled.
