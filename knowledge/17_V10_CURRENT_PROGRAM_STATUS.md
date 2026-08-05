# 17 — V10 CURRENT PROGRAM STATUS

Updated: 2026-08-05

## Executive state

Omni-CIO V10: **DEVELOPMENT STARTED / WP2 IN PROGRESS**.

Accepted implementation progress: **5%**.

Accepted completed work:

- Block A / WP0 — **COMPLETE (5%)**;
- Block B / WP1 — **COMPLETE as work package; Block B remains IN PROGRESS and its 9% block weight is not yet credited**.

Current authorized work package:

**WP2 — Toolchain and Dependency Baseline.**

WP3 and later remain blocked until WP2 Exit Gate is accepted on `main`.

Owner start command: **`START V10`** received 2026-08-05.

Starting or advancing V10 never expands broker/Real-money authority by itself.

## Canonical authority

- plan: `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`
- synchronized PDF: `docs/master-plan/Omni-CIO_V10_Master_Plan_RU.pdf`
- integrity manifest: `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.sha256`
- Program Lock: `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`
- system architecture: `docs/architecture/V10_SYSTEM_ARCHITECTURE.md`
- security boundaries: `docs/architecture/V10_SECURITY_BOUNDARIES.md`
- repository architecture: `docs/architecture/REPOSITORY_STRUCTURE.md`
- protected V9 baseline: `docs/architecture/V10_V9_BASELINE_FREEZE.md`
- WP2 toolchain authority under development: `docs/architecture/V10_TOOLCHAIN_BASELINE.md`

Protected production/recovery baseline remains:

**Omni-CIO v9.0.0 — COMPLETE / owner-accepted / controlled maintenance.**

## Progress

| Block | Planned weight | State |
|---|---:|---|
| A. Architecture and V9 protection | 5% | COMPLETE — WP0 |
| B. GitHub, dependencies and CI/CD | 9% | WP1 COMPLETE / WP2 IN PROGRESS |
| C. Lenovo Omni-CIO Node / infrastructure | 12% | NOT STARTED |
| D. V10 Core and data | 14% | NOT STARTED |
| E. Omni-CIO Web Platform | 14% | NOT STARTED |
| F. Telegram | 8% | NOT STARTED |
| G. AI Copilot / Research / GPT Migration | 18% | NOT STARTED |
| H. Guardian / Watchtower Loop | 8% | NOT STARTED |
| I. Personal Real Execution | 7% | NOT STARTED |
| J. Integration / hardening / recovery / release | 5% | NOT STARTED |
| **TOTAL** | **100% planned** | **5% ACCEPTED** |

No partial Block B percentage is credited. Its 9% weight becomes accepted only when all Block B work packages/Exit Gates are complete.

## Accepted WP0 evidence

WP0 PR #228 was squash-merged as:

`7c5de954eed10dd406e743c38f7bdef6b0634108`

It established the V10 architecture freeze without widening runtime or money authority.

## Accepted WP1 evidence

WP1 PR #229 passed final exact-head Regression Shield run #1364 on head:

`5cf0b9c4daace7d838fcd98c4a797f3427dcb8dc`

Both required jobs passed, the Windows smoke passed, unresolved review threads were zero, and PR #229 was squash-merged to `main` as:

`dbd459b280de84d3f571b458b46f1039880312ca`

WP1 established:

- canonical repository ownership;
- one deterministic `omni_cio/` Core;
- reserved future `apps/`, `ai/`, `infrastructure/` roots;
- explicit CODEOWNERS;
- permanent V10 repository-boundary guard;
- critical Core cycle detection;
- direct Real/plan-execution authority uniqueness;
- preservation of V9 `app:app` and controlled-maintenance recovery runtime.

## WP2 objective

Freeze one reproducible, supported development/toolchain baseline before Lenovo bootstrap or product UI implementation.

WP2 covers only:

- backend Python/FastAPI compatibility baseline;
- exact Python version policy;
- Node.js LTS + npm/package-manager baseline;
- React + TypeScript + Vite toolchain baseline without implementing product Web features;
- PostgreSQL supported stable branch selection;
- lockfile/update policy;
- dependency/SBOM/license policy;
- clean Windows/GitHub-hosted compatibility evidence.

## WP2 initial evidence and candidates

The repository currently proves a production-compatible backend on Python **3.12.10**, FastAPI **0.141.1**, Uvicorn **0.51.0** and the existing hash-locked Python dependency set.

Fresh official-source review performed at WP2 start found:

- Python 3.12.10 is the final 3.12 release with Windows binary installers; later 3.12 security releases are source-only, so WP2 must not silently call 3.12.10 a long-term V10 security baseline without evaluating a newer Python minor;
- Python 3.13.14 and 3.14.6 are current supported maintenance releases and are compatibility candidates;
- Node.js 24.18.0 is current LTS and bundles npm 11.16.0;
- React 19.2 is the current stable React line;
- Vite 8.1 is the current regular-patch stable line;
- PostgreSQL 18.4 is the current supported stable PostgreSQL 18 release;
- TypeScript 7.0 is stable, but because it is a new native compiler generation, WP2 must verify compatibility rather than select it only because it is newest.

Exact V10 pins are not accepted until the WP2 compatibility/build checks prove them.

## WP2 current branch

Focused branch:

`v10/wp2-toolchain-baseline`

The branch starts from accepted WP1 main:

`dbd459b280de84d3f571b458b46f1039880312ca`

## WP2 Exit Gate

WP2 may become COMPLETE only when:

1. one exact documented Python/Node/package-manager/frontend/PostgreSQL baseline is selected from evidence;
2. backend compatibility remains green and V9 `app:app` is preserved;
3. frontend toolchain has deterministic locked inputs and a clean non-product build smoke;
4. dependency/SBOM/license policy is machine-checkable;
5. clean GitHub-hosted Windows/toolchain checks are reproducible;
6. existing self-hosted Regression Shield/security remains green;
7. zero unresolved review blockers remain;
8. focused WP2 PR is squash-merged to `main`.

After WP2 acceptance, **WP3 — V10 Regression Shield / repository protection** becomes the next authorized work package. Overall accepted V10 progress remains 5% until Block B completes.

## Lenovo sequencing

Do not configure the V10 Lenovo runtime yet. Block C starts only after WP1–WP4 establish repository architecture, toolchain, CI and release/deployment contracts.

## Money/safety rule

GitHub access, AI output, Watchtower alert, Telegram message, `START V10`, or approval of a development work package is never broker-submit authorization. Current V9 execution boundaries and kill switches remain binding.
