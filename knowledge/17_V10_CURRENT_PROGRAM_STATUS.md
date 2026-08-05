# 17 — V10 CURRENT PROGRAM STATUS

Updated: 2026-08-05

## Executive state

Omni-CIO V10: **DEVELOPMENT STARTED / WP1 COMPLETE ON ACCEPTED MAIN / WP2 NEXT**.

Accepted implementation progress: **5%**.

Accepted completed work:

- Block A / WP0 — **COMPLETE (5%)**;
- Block B / WP1 — **COMPLETE as work package; Block B remains IN PROGRESS and its 9% block weight is not yet credited**.

Next authorized work package after WP1 acceptance:

**WP2 — Toolchain and Dependency Baseline.**

> Authority note: while this file is viewed inside the unmerged WP1 PR, `WP1 COMPLETE / WP2 NEXT` is the acceptance candidate. It becomes authoritative only after final exact-head Regression Shield/security is green, review blockers are zero and PR #229 is squash-merged to `main`.

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
- repository boundary guard: `scripts/check_v10_repository_boundaries.py`

Protected runtime/recovery baseline remains:

**Omni-CIO v9.0.0 — COMPLETE / owner-accepted / controlled maintenance.**

## Progress

| Block | Planned weight | State |
|---|---:|---|
| A. Architecture and V9 protection | 5% | COMPLETE — WP0 |
| B. GitHub, dependencies and CI/CD | 9% | WP1 COMPLETE / WP2 NEXT |
| C. Lenovo Omni-CIO Node / infrastructure | 12% | NOT STARTED |
| D. V10 Core and data | 14% | NOT STARTED |
| E. Omni-CIO Web Platform | 14% | NOT STARTED |
| F. Telegram | 8% | NOT STARTED |
| G. AI Copilot / Research / GPT Migration | 18% | NOT STARTED |
| H. Guardian / Watchtower Loop | 8% | NOT STARTED |
| I. Personal Real Execution | 7% | NOT STARTED |
| J. Integration / hardening / recovery / release | 5% | NOT STARTED |
| **TOTAL** | **100% planned** | **5% ACCEPTED** |

No partial Block B percentage is credited: the 9% block weight becomes accepted only after all Block B Exit Gates are complete. Individual WP completion is tracked separately.

## Accepted WP0 evidence

WP0 focused PR #228 was squash-merged to `main` as:

`7c5de954eed10dd406e743c38f7bdef6b0634108`

WP0 exact-head Regression Shield/security passed before merge. WP0 added architecture freeze, security/data/recovery/threat boundaries, ADR governance and protected V9 baseline evidence without introducing Web, Telegram, AI runtime, Lenovo bootstrap, Core refactor or new execution authority.

## WP1 delivered scope

WP1 prepares the repository for long-term V10 development without duplicate stacks or hidden account-owned configuration.

Delivered in focused PR #229:

- one canonical current/target repository structure in `docs/architecture/REPOSITORY_STRUCTURE.md`;
- explicit CODEOWNERS for Core, future Web/API/Telegram/AI/infrastructure, docs, knowledge, tests and CI;
- `omni_cio/` retained as the one deterministic financial Core instead of a cosmetic high-risk wholesale move;
- future `apps/`, `ai/` and `infrastructure/` roots reserved but not implemented out of sequence;
- permanent `scripts/check_v10_repository_boundaries.py`;
- focused repository-boundary tests;
- direct Real authority and plan-execution authority kept unique;
- future Web/Telegram/AI prevented from importing low-level Real authority directly;
- critical Core package dependency graph checked for circular dependency;
- V9 compatibility paths and stable `app:app` preserved;
- developer/account portability documented from GitHub + locks + safe repository configuration/examples;
- stale navigation sources synchronized so V10 is the active feature program while V9 remains controlled-maintenance production/recovery runtime.

No Web, Telegram runtime, AI runtime, Lenovo bootstrap, PostgreSQL runtime or new broker execution authority is introduced by WP1.

## WP1 verification evidence

During WP1 development, Regression Shield run #1355 on head `d7fe2ccd54e43c171e62670f73464ccbec67472e` passed both jobs after the initial navigation-contract regression was corrected:

- Dependency, code and secret security — **SUCCESS**;
- Quality, contracts and coverage — **SUCCESS**;
- Windows runner smoke — **SUCCESS**.

That run proved the substantive repository-boundary implementation. Because status/navigation handoff commits follow it, the **final PR head must run the same exact-head gates again before merge**.

The original failing run identified one existing repository-hygiene contract: `.github/copilot-instructions.md` had lost the literal V9 `controlled maintenance` marker. The fix restored that protected V9 description without reverting the V10 architecture changes. Final tests then passed.

## WP1 Exit Gate

WP1 is accepted only when all of the following are true on the final PR head:

1. `AGENTS.md` + `REPOSITORY_STRUCTURE.md` make component ownership/authority unambiguous;
2. there is no competing implementation of a financial engine/application stack;
3. repository boundary guard runs permanently in Regression Shield;
4. critical package import graph/cycle check is green;
5. V9 compatibility and `app:app` remain green;
6. exact-head Regression Shield/security is green;
7. zero unresolved review blockers remain;
8. focused WP1 PR #229 is squash-merged to `main`.

After that merge:

- WP1 state = **COMPLETE**;
- overall accepted V10 progress = **5%**;
- Block B remains active;
- **WP2 — Toolchain and Dependency Baseline** becomes the current authorized package;
- WP3 and later remain blocked by sequence.

## WP2 scope boundary

WP2 may establish the supported/reproducible development stack only after WP1 acceptance. According to the canonical plan it covers Python/FastAPI compatibility, React + TypeScript + Vite frontend baseline, PostgreSQL stable branch selection, exact Python/Node/package-manager/lock formats, dependency/SBOM/license policy and reproducible clean Windows/CI builds.

WP2 is **not** permission to start the Web product, Lenovo services, Telegram, AI runtime or Real V10 execution.

## Lenovo sequencing

Do not perform the one-time Lenovo V10 runtime setup yet.

Block C starts only after WP1–WP4 establish repository architecture, toolchain, CI and release/deployment contracts. This preserves the owner goal of configuring the Lenovo once from a stable, reproducible foundation.

## Money/safety rule

GitHub access, AI output, Watchtower alert, Telegram message, `START V10`, or approval of any development work package is never by itself authorization for a broker submit.

Current V9 execution boundaries and kill switches remain binding until a later V10 package intentionally replaces a boundary and passes its full acceptance gate.
