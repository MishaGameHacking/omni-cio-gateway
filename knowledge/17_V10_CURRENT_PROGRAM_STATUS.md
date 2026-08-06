# 17 — V10 CURRENT PROGRAM STATUS

Updated: 2026-08-06

## Executive state

Omni-CIO V10: **WP2 COMPLETE CANDIDATE / ACCEPTANCE MERGE PENDING / WP3 NEXT AFTER ACCEPTANCE**.

Accepted implementation progress: **5%**.

Accepted completed work:

- Block A / WP0 — **COMPLETE (5%)**;
- Block B / WP1 — **COMPLETE as work package; Block B remains IN PROGRESS and its 9% block weight is not yet credited**.

Current authorized work package until the focused WP2 PR is accepted on `main`:

**WP2 — Toolchain and Dependency Baseline.**

WP2 implementation and pre-handoff Exit Gate evidence are complete on PR #230 head `f122cd7c2a79d58783189f365c9129c14a681cd5`. This status handoff commit intentionally changes the PR head, so the same exact-head Regression Shield/security/toolchain gates must pass again before squash merge.

After that exact-head rerun and squash merge, **WP2 becomes accepted COMPLETE and WP3 — V10 Regression Shield / repository protection becomes NEXT**. WP3 implementation must not start before WP2 acceptance on `main`.

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
- WP2 selected toolchain authority: `docs/architecture/V10_TOOLCHAIN_BASELINE.md`
- machine-readable WP2 authority: `docs/architecture/V10_TOOLCHAIN_BASELINE.json`

Protected production/recovery baseline remains:

**Omni-CIO v9.0.0 — COMPLETE / owner-accepted / controlled maintenance.**

## Progress

| Block | Planned weight | State |
|---|---:|---|
| A. Architecture and V9 protection | 5% | COMPLETE — WP0 |
| B. GitHub, dependencies and CI/CD | 9% | WP1 COMPLETE / WP2 COMPLETE CANDIDATE — ACCEPTANCE MERGE PENDING |
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

## WP2 selected baseline

The evidence-selected V10 development baseline is:

- Python **3.14.6**;
- FastAPI **0.141.1**;
- Uvicorn **0.51.0**;
- Node.js **24.18.0 LTS**;
- npm **11.16.0** with package-lock v3;
- React **19.2.8**;
- React DOM **19.2.8**;
- Vite **8.1.5**;
- TypeScript **7.0.2**;
- PostgreSQL **18 / reviewed patch baseline 18.4**.

Python remains governed by exact direct `.in` sources and SHA-256 hash-locked generated locks. The non-product frontend toolchain fixture uses exact direct versions plus committed deterministic `package-lock.json`. Machine-readable authority is `docs/architecture/V10_TOOLCHAIN_BASELINE.json` and the permanent policy guard is `scripts/check_v10_toolchain_baseline.py`.

WP2 does **not** migrate the current Render/V9 runtime interpreter or install PostgreSQL. Those runtime boundaries remain owned by later work packages.

## WP2 compatibility and defect evidence

Clean GitHub-hosted Windows candidate evaluation proved Python 3.12.10, 3.13.14 and 3.14.6 against the protected application/test surface. Python 3.14.6 was selected after all candidates passed.

During that evaluation, two concurrency tests were found to rely on scheduler ordering rather than the intended temporal contract. Only those tests were corrected to use equal timestamps for serialization/fire-once evidence; separate explicit out-of-order fail-closed tests remain. Production ACRA/MOEX policy logic was not weakened.

The selected frontend baseline proves deterministic `npm ci`, typecheck, Vite build, npm audit and CycloneDX SBOM generation without implementing the Omni-CIO Web product.

## WP2 pre-handoff Exit Gate evidence

Focused PR:

`#230 — V10 WP2: establish reproducible toolchain baseline`

Pre-handoff exact head:

`f122cd7c2a79d58783189f365c9129c14a681cd5`

On that exact head:

- Regression Shield run **#1391** / Actions run `31052381836` — **SUCCESS**;
  - Quality, contracts and coverage — **SUCCESS**;
  - Dependency, code and secret security — **SUCCESS**;
- Self-Hosted Windows Smoke run **#86** / Actions run `31052378965` — **SUCCESS**;
- V10 Toolchain Compatibility run **#26** / Actions run `31052378987` — **SUCCESS**;
  - Python 3.14.6 V10 baseline — **SUCCESS**;
  - Node 24.18.0 / React-Vite-TypeScript baseline — **SUCCESS**;
- exact selected-toolchain policy, lock reproducibility, full deterministic tests, dependency audit, SAST, secret scan and both Python/frontend CycloneDX SBOM paths are green;
- unresolved PR review threads — **0**;
- PR is mergeable.

This pre-handoff head satisfies the substantive WP2 implementation gate. The present status handoff commit deliberately requires one final exact-head rerun before merge so status/documentation cannot bypass the same protection.

## WP2 Exit Gate

WP2 may become accepted COMPLETE only when:

1. one exact documented Python/Node/package-manager/frontend/PostgreSQL baseline is selected from evidence — **SATISFIED**;
2. backend compatibility remains green and V9 `app:app` is preserved — **SATISFIED on pre-handoff head**;
3. frontend toolchain has deterministic locked inputs and a clean non-product build smoke — **SATISFIED**;
4. dependency/SBOM/license policy is machine-checkable — **SATISFIED**;
5. clean GitHub-hosted Windows/toolchain checks are reproducible — **SATISFIED on pre-handoff head**;
6. existing self-hosted Regression Shield/security remains green — **SATISFIED on pre-handoff head; MUST RE-RUN ON STATUS-HANDOFF HEAD**;
7. zero unresolved review blockers remain — **SATISFIED**;
8. focused WP2 PR is squash-merged to `main` — **PENDING**.

Final acceptance sequence:

`status handoff -> exact-head Regression Shield + toolchain + Windows smoke green -> zero blockers -> squash merge PR #230 -> WP2 COMPLETE on main -> WP3 NEXT`.

After WP2 acceptance, **WP3 — V10 Regression Shield / repository protection** becomes the next authorized work package. Overall accepted V10 progress remains 5% until all of Block B is complete.

## Lenovo sequencing

Do not configure the V10 Lenovo runtime yet. Block C starts only after WP1–WP4 establish repository architecture, toolchain, CI and release/deployment contracts.

## Money/safety rule

GitHub access, AI output, Watchtower alert, Telegram message, `START V10`, or approval of a development work package is never broker-submit authorization. Current V9 execution boundaries and kill switches remain binding.
