# 17 — V10 CURRENT PROGRAM STATUS

Updated: 2026-08-05

## Executive state

Omni-CIO V10: **DEVELOPMENT STARTED / WP1 IN PROGRESS**.

Accepted implementation progress: **5%**.

Accepted completed work:

- Block A / WP0 — **COMPLETE (5%)**.

Current authorized work package:

**WP1 — Repository Architecture and boundaries.**

WP2 and later remain blocked until WP1 Exit Gate is accepted on `main`.

Owner start command: **`START V10`** received 2026-08-05.

Starting or advancing V10 never expands broker/Real-money authority by itself.

## Canonical authority

- plan: `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`
- synchronized PDF: `docs/master-plan/Omni-CIO_V10_Master_Plan_RU.pdf`
- integrity manifest: `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.sha256`
- Program Lock: `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`
- readiness audit: `docs/master-plan/OMNI_CIO_V10_PLAN_READINESS_AUDIT.md`
- start record: `docs/master-plan/OMNI_CIO_V10_START_RECORD.md`
- system architecture: `docs/architecture/V10_SYSTEM_ARCHITECTURE.md`
- security boundaries: `docs/architecture/V10_SECURITY_BOUNDARIES.md`
- data flow: `docs/architecture/V10_DATA_FLOW.md`
- threat model: `docs/architecture/V10_THREAT_MODEL.md`
- recovery contract: `docs/architecture/V10_RECOVERY_CONTRACT.md`
- ADR process/registry: `docs/architecture/V10_ADR_PROCESS.md`, `docs/architecture/DECISIONS.md`
- protected V9 baseline freeze: `docs/architecture/V10_V9_BASELINE_FREEZE.md`
- repository architecture: `docs/architecture/REPOSITORY_STRUCTURE.md`

Protected runtime/recovery baseline remains:

**Omni-CIO v9.0.0 — COMPLETE / owner-accepted / controlled maintenance.**

## Progress

| Block | Planned weight | State |
|---|---:|---|
| A. Architecture and V9 protection | 5% | COMPLETE — WP0 |
| B. GitHub, dependencies and CI/CD | 9% | WP1 IN PROGRESS |
| C. Lenovo Omni-CIO Node / infrastructure | 12% | NOT STARTED |
| D. V10 Core and data | 14% | NOT STARTED |
| E. Omni-CIO Web Platform | 14% | NOT STARTED |
| F. Telegram | 8% | NOT STARTED |
| G. AI Copilot / Research / GPT Migration | 18% | NOT STARTED |
| H. Guardian / Watchtower Loop | 8% | NOT STARTED |
| I. Personal Real Execution | 7% | NOT STARTED |
| J. Integration / hardening / recovery / release | 5% | NOT STARTED |
| **TOTAL** | **100% planned** | **5% ACCEPTED** |

No partial Block B percentage is credited: the block weight is accepted only after its defined Exit Gates. Individual WP state is tracked separately.

## Accepted WP0 evidence

WP0 focused PR #228 was squash-merged to `main` as:

`7c5de954eed10dd406e743c38f7bdef6b0634108`

WP0 exact-head Regression Shield/security passed before merge. WP0 added architecture freeze, security/data/recovery/threat boundaries, ADR governance and protected V9 baseline evidence without introducing Web, Telegram, AI runtime, Lenovo bootstrap, Core refactor or new execution authority.

## WP1 objective

Prepare the repository for long-term V10 development without duplicate stacks or hidden account-owned configuration.

WP1 must establish:

- one canonical current/target repository structure;
- explicit ownership of Web/API/Telegram/AI/infrastructure/Core paths;
- permanent machine-checked repository/authority boundaries;
- critical Core import-cycle detection;
- protection against duplicate Real/plan-execution/application roots;
- preservation of V9 compatibility/recovery paths;
- developer/account portability from GitHub source of truth.

## WP1 current branch

Focused branch:

`v10/wp1-repository-architecture`

Current WP1 work is allowed to change repository architecture documentation, ownership metadata, static boundary guards/tests and CI wiring required by WP1.

It is **not** authorization to implement the Web, Telegram bot, AI runtime, Lenovo services, PostgreSQL runtime or new broker execution capability.

## WP1 Exit Gate

WP1 becomes accepted only when:

1. `AGENTS.md` + `REPOSITORY_STRUCTURE.md` make component ownership/authority unambiguous;
2. there is no competing implementation of a financial engine/application stack;
3. repository boundary guard runs permanently in Regression Shield;
4. critical package import graph/cycle check is green;
5. V9 compatibility and `app:app` remain green;
6. exact-head Regression Shield/security is green;
7. zero unresolved review blockers remain;
8. focused WP1 PR is squash-merged to `main`.

After WP1 acceptance:

- overall accepted V10 progress remains **5%** until Block B is completed according to the canonical block-weight rule;
- WP1 state becomes COMPLETE;
- **WP2 — Toolchain and Dependency Baseline** becomes the next authorized package.

## Lenovo sequencing

Do not perform the one-time Lenovo V10 setup yet.

Block C starts only after WP1–WP4 establish repository architecture, toolchain, CI and release/deployment contracts. This preserves the owner goal of configuring the Lenovo once from a stable, reproducible foundation.

## Money/safety rule

GitHub access, AI output, Watchtower alert, Telegram message, `START V10`, or approval of any development work package is never by itself authorization for a broker submit.

Current V9 execution boundaries and kill switches remain binding until a later V10 package intentionally replaces a boundary and passes its full acceptance gate.
