# Omni-CIO V10 — Regression Shield and Hybrid CI Protection Contract

Status: **ACTIVE CI / GOVERNANCE CONTRACT**  
Scope: GitHub Actions, repository protection, CI continuity and capacity-degraded routing  
Protected runtime: current V9 `app:app` remains unchanged until an owning later WP intentionally migrates it

## 1. Purpose

The repository uses layered CI so external GitHub-hosted capacity is never a single point of failure and so a capacity incident is never confused with a code defect.

The contract is:

1. **Fast PR Checks** provide deterministic repository/policy/frontend feedback. During the current OWNER-observed zero-budget hard stop they execute on Lenovo; when hosted capacity is later restored they may return to hosted acceleration through a reviewed GREEN CI change.
2. **V10 Toolchain Compatibility** owns disposable GitHub-hosted Python 3.14.6 / Node 24.18.0 compatibility evidence when hosted capacity exists. During the current hard stop it executes an explicit applicability/capacity contract on Lenovo and does **not** claim a clean-room PASS.
3. **Self-Hosted Windows CI** runs on the OWNER Lenovo. Its `V10 authoritative merge gate` is the mandatory merge-authority job and independently protects the production/runtime/security surface.
4. **Regression Shield** is the post-merge sentinel on `main`.
5. Missing hosted acceleration/clean-room evidence is classified truthfully. It is not a code failure, not a fake PASS, and not authority to merge around a RED check that was actually started.

A green fast or capacity-routing lane never substitutes for the authoritative self-hosted merge gate.

## 2. Non-negotiable invariants

- Every applicable exact-head merge check must actually execute and conclude `success`.
- `failure`, `cancelled`, `pending`, `queued`, `in_progress`, `neutral` and `skipped` are not V10 GREEN evidence for an applicable gate.
- Mandatory jobs may not use `continue-on-error: true` except the explicitly non-authoritative post-merge diagnostics artifact transport already allowlisted by the Regression Shield guard.
- External GitHub Actions are pinned to full commit SHA.
- Workflow permissions remain least-privilege; repository checkout does not persist credentials.
- Self-hosted PR jobs reject fork pull requests where authority/sensitive local execution is involved.
- CI must not receive broker/Telegram/AI/private-database secrets merely to run tests.
- A failing mandatory gate is repaired; it is not bypassed by deleting, renaming or softening the check.
- Current V9 money-path replay/idempotency and execution-safety tests remain protected.
- `app:app`, `trading_methods=false` and `REAL_TRADING_ENABLED=false` remain protected according to their owning V10 gates.
- Generated dependency/SBOM evidence may contain package metadata only, never portfolio/account/private runtime state.
- Known budget-blocked hosted jobs are not repeatedly started merely to rediscover the same infrastructure failure.

## 3. CI lanes

### 3.1 Fast PR Checks

Purpose: catch deterministic repository/source/frontend defects before or alongside the full authoritative gate.

Current capacity-degraded characteristics:

- `pull_request` + manual dispatch;
- exact reviewed head checkout;
- Lenovo `self-hosted, Windows, X64, omni-cio-ci` continuity runner;
- protected Python 3.12.10 bootstrap;
- no repository/environment secrets;
- repository/V10-boundary policy checks;
- CI/security policy self-check;
- engineering-governance and cost-control guards when present;
- selected V10 toolchain policy check;
- Python source compilation and focused policy/unit tests;
- path-routed frontend validation using the already accepted exact Node.js 24.18.0 / npm 11.16.0 installation;
- non-applicable frontend work is represented by an executed `NOT_APPLICABLE` routing step rather than a skipped job;
- `cancel-in-progress: true` per PR.

This lane is deterministic feedback, not disposable clean-room evidence.

### 3.2 V10 Toolchain Compatibility

Normal hosted-capacity target remains:

- disposable Windows compatibility;
- Python **3.14.6**;
- Node.js **24.18.0** / npm **11.16.0**;
- deterministic dependency projection;
- Ruff/format/mypy/test/audit/SBOM evidence;
- fresh hosted environment independent of Lenovo state.

Current state is `BLOCKED_OWNER_ZERO_BUDGET_HARD_STOP`. Therefore the workflow currently runs three successful self-hosted contract jobs:

1. changed-path/capacity classification;
2. Python clean-room applicability/capacity reporting;
3. Node clean-room applicability/capacity reporting.

The jobs report either:

- `NOT_APPLICABLE`; or
- `REQUIRED_BY_PATH but CURRENTLY_CAPACITY_BLOCKED`.

A successful capacity job **does not claim** that the disposable hosted compatibility test executed. Stable release provenance must not fabricate hosted compatibility evidence that does not exist.

When hosted capacity is restored, current account state must first be re-verified and the actual hosted clean-room jobs restored through a focused all-GREEN PR.

### 3.3 Self-Hosted Windows CI / authoritative merge gate

`.github/workflows/self-hosted-windows-smoke.yml` owns:

- `Windows runner smoke test` — focused service/bootstrap diagnostic;
- `V10 authoritative merge gate` — exact-head merge authority.

The authoritative gate must independently cover at minimum:

- runner OS/architecture identity;
- protected current Python **3.12.10** runtime bootstrap;
- isolated venv under runner temp;
- hash-lock projection/reproducibility;
- CI/security/repository/V10 authority guards;
- compile;
- Ruff lint and format;
- mypy;
- stable `app:app` and read-only release contracts;
- full pytest + branch coverage threshold;
- runtime dependency audit;
- Bandit SAST;
- detect-secrets scan;
- deterministic workspace cleanup.

It deliberately does not install Python 3.14 during the self-hosted job. A previous design that coupled the service account to runtime MSI installation was rejected as less deterministic. The installed Node toolchain is exercised by owning Web gates, but is not represented as a disposable clean VM.

The stable required server-side context remains:

`V10 authoritative merge gate`

### 3.4 Post-merge Regression Shield

`Regression Shield` runs on pushes to `main` and manual dispatch. It is self-hosted and repeats protected quality/security/coverage evidence after merge. A WP/amendment/status transition is not accepted merely because a PR merged; the required post-merge shield must be GREEN.

## 4. GitHub capacity policy

GitHub-hosted execution is acceleration/independent compatibility evidence, not the only source of correctness.

Current OWNER-controlled account observation is recorded in `docs/operations/V10_CI_COST_CONTROL_STANDARD.md`. While that hard stop remains current:

- do not increase budget/payment settings without explicit OWNER approval;
- do not start jobs known in advance to be billing-blocked;
- use Lenovo for semantically equivalent deterministic checks;
- preserve missing clean-room evidence as missing rather than lying about it;
- do not weaken the authoritative merge gate;
- do not publish a stable release whose provenance contract requires compatibility evidence that was not actually produced.

## 5. Frontend quality contract

The canonical product Web package must retain:

- deterministic install from committed lock;
- exact accepted Node/npm identity on the executing lane;
- TypeScript typecheck;
- lint;
- unit/component tests;
- production build;
- Playwright smoke/E2E for critical OWNER workflows;
- dependency audit;
- no secret/private data in browser test fixtures.

A Web package without required scripts/config/tests is a CI failure, not a reason to skip validation.

## 6. Capability-aware mandatory test contracts

When later V10 work introduces a capability, matching tests become mandatory in the same PR.

| Capability | Mandatory evidence once present |
|---|---|
| PostgreSQL migrations/schema | forward migration, clean bootstrap, rollback/recovery policy, migration version contract |
| Web/API schema | OpenAPI/schema validation, request/response contract tests, auth/authority boundary tests |
| Backup/restore | deterministic backup metadata + restore rehearsal/verification tests |
| Telegram ingress | identity/freshness/replay/secret validation and no broker-authority expansion |
| AI providers/tools | structured schema, unknown/abstain behavior, tool allowlist/authority-firewall tests |
| Web critical workflows | Playwright smoke/E2E using non-secret deterministic fixtures |

## 7. Money-path protection

CI/governance changes do not expand execution authority. Protected tests must continue to cover relevant Real/Sandbox/plan-execution semantics, including immutable proposal context, exact confirmation lifecycle, UUID/idempotency, no blind retry after ambiguous possible-submit, `submitted != filled` without broker evidence, and fail-closed stale/missing/contradictory inputs.

## 8. Anti-bypass policy

Repository guards fail when they detect material weakening such as:

- floating external Action refs;
- persisted checkout credentials;
- secret consumption in ordinary PR validation;
- removal of authoritative regression/security commands;
- removal of selected-toolchain policy checks;
- capability roots without required tests;
- Web package without required quality/E2E contracts;
- path filtering that can make a required workflow disappear;
- capacity-deferred jobs represented as skipped instead of executed routing contracts;
- a green capacity-routing job described as actual hosted clean-room compatibility;
- stable release evidence fabricated from a capacity-deferred job.

## 9. Server-side protection expectation

Private `main` remains protected. Normal delivery requires PR, exact-head required status, resolved blocking conversations, squash merge, deletion/force-push protection and no routine bypass.

Hosted/capacity workflows may be visible as additional checks, but the stable required merge-authority context remains `V10 authoritative merge gate` unless an explicit later governance change says otherwise.

## 10. Current delivery sequence

For every V10 package:

`pre-CI root-cause/blast-radius review -> focused checks -> exact-head PR checks -> all applicable checks SUCCESS -> zero unresolved blockers -> squash merge -> exact new main -> post-merge Regression Shield GREEN -> OWNER product acceptance if required -> status/next WP`.

Current hosted capacity does not change this sequence. It changes only where acceleration/clean-room evidence can actually execute and how the absence of that optional PR acceleration is represented truthfully.
