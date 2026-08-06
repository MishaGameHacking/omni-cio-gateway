# 17 — V10 CURRENT PROGRAM STATUS

Updated: 2026-08-06

## Executive state

Omni-CIO V10: **DEVELOPMENT STARTED / WP3 IMPLEMENTATION COMPLETE CANDIDATE / ACCEPTANCE BLOCKED**.

Accepted implementation progress: **5%**.

Accepted completed work:

- Block A / WP0 — **COMPLETE (5%)**;
- Block B / WP1 — **COMPLETE**;
- Block B / WP2 — **COMPLETE**;
- Block B remains **IN PROGRESS** and its 9% block weight is not yet credited.

Current authorized work package:

**WP3 — V10 Regression Shield / repository protection.**

WP3 repository-controlled implementation is complete as a candidate. Acceptance is intentionally blocked until all final exact-head gates pass and GitHub server-side merge protection for private `main` is proven. PR #236 must remain unmerged until then. WP4 and later remain blocked.

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
- accepted toolchain authority: `docs/architecture/V10_TOOLCHAIN_BASELINE.md`
- machine-readable toolchain authority: `docs/architecture/V10_TOOLCHAIN_BASELINE.json`
- WP3 CI/protection authority: `docs/architecture/V10_REGRESSION_SHIELD.md`

Protected production/recovery baseline remains:

**Omni-CIO v9.0.0 — COMPLETE / owner-accepted / controlled maintenance.**

## Progress

| Block | Planned weight | State |
|---|---:|---|
| A. Architecture and V9 protection | 5% | COMPLETE — WP0 |
| B. GitHub, dependencies and CI/CD | 9% | WP1 COMPLETE / WP2 COMPLETE / WP3 COMPLETE CANDIDATE — ACCEPTANCE BLOCKED |
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

WP1 PR #229 passed its final exact-head gates and was squash-merged to `main` as:

`dbd459b280de84d3f571b458b46f1039880312ca`

WP1 established canonical repository ownership, one deterministic `omni_cio/` Core, reserved future V10 roots, CODEOWNERS, permanent repository-boundary guards and preserved V9 `app:app` compatibility.

## Accepted WP2 evidence

WP2 PR #230 selected and froze the reproducible V10 development/toolchain baseline:

- Python **3.14.6**;
- FastAPI **0.141.1**;
- Uvicorn **0.51.0**;
- Node.js **24.18.0 LTS**;
- npm **11.16.0** / package-lock v3;
- React / React DOM **19.2.8**;
- Vite **8.1.5**;
- TypeScript **7.0.2**;
- PostgreSQL **18**, reviewed patch baseline **18.4**.

Final exact-head acceptance was performed on:

`9fc0eb8e12f5aaa1e4cd2cabd509ecbde755ac99`

Mandatory final evidence:

- Regression Shield **#1393** / Actions run `31072106594` — **SUCCESS**;
  - Quality, contracts and coverage — **SUCCESS**;
  - Dependency, code and secret security — **SUCCESS**;
- V10 Toolchain Compatibility **#28** / Actions run `31072106592` — **SUCCESS**;
  - Python 3.14.6 baseline — **SUCCESS**;
  - Node 24.18.0 / React-Vite-TypeScript baseline — **SUCCESS**;
- Self-Hosted Windows Smoke **#88** / Actions run `31072106591` — **SUCCESS**;
- unresolved review threads — **0**;
- PR head unchanged between final green evidence and merge.

PR #230 was squash-merged to `main` as:

`3e3a89791d7f1594e4e1ba52125f8361708ae29d`

WP2 did not migrate the current Render/V9 runtime interpreter, install PostgreSQL, implement Web/Telegram/AI, or expand broker/Real-money authority.

## WP3 objective

Make CI the primary barrier against hidden defects before runtime while preserving all accepted V9 and WP2 gates.

Canonical WP3 deliverables:

- preserve V9 compile/Ruff/format/mypy/pytest/coverage/security gates;
- add frontend TypeScript/lint/unit/E2E gate architecture;
- establish DB migration, API schema/contract, authority, backup/restore, Telegram signature and AI schema test contracts for the work packages that will introduce those capabilities;
- require Playwright smoke/E2E for critical Web workflows when the Web product surface exists;
- separate fast PR feedback from the full exact-head regression/security acceptance gate;
- keep critical money-path replay/idempotency checks mandatory;
- prevent CI failures from being bypassed by disabling or softening mandatory checks.

## WP3 implementation candidate

Focused branch:

`v10/wp3-regression-shield`

Focused PR:

`#236 — V10 WP3: harden Regression Shield and PR gates`

Starting point:

`3e3a89791d7f1594e4e1ba52125f8361708ae29d`

Repository-controlled implementation now includes:

- GitHub-hosted `V10 Fast PR Checks` with no secrets, no self-hosted dependency and no PR path filtering;
- exact-head `V10 Toolchain Compatibility` on every PR with Python 3.14.6 and Node 24.18.0;
- hosted Ruff/format/mypy plus the full deterministic Python suite and audits/SBOM;
- deterministic frontend typecheck/lint/unit/build/audit/SBOM on the non-product WP2 fixture;
- permanent `scripts/check_v10_regression_shield.py` anti-bypass guard;
- self-protection through the pre-existing CI/security baseline;
- fail-closed future contracts for Web Playwright/E2E, DB migrations, API schemas, authority, backup/restore, Telegram signatures and AI schemas when their owning capabilities appear;
- protected Real/Sandbox/plan-execution test families;
- preserved V9 `app:app`, current execution authority and recovery boundaries.

No Web product, PostgreSQL runtime/schema, Telegram runtime, AI runtime, Lenovo bootstrap or new broker-write authority was introduced by WP3.

## Verified WP3 acceptance blockers

### 1. GitHub server-side merge protection

The repository is private. On 2026-08-06 GitHub's rulesets API reported that private-repository rulesets are unavailable on the current account plan and require an eligible paid plan. The branch-protection endpoint is not readable through the installed integration, so no equivalent server-side required-check enforcement on `main` can currently be proven.

The repository must remain private. Making it public is not an acceptable workaround.

WP3 therefore cannot be accepted or merged until the OWNER account uses a GitHub plan supporting protected branches/rulesets for private repositories and `main` is configured to require the mandatory V10 checks without bypass.

### 2. Final exact-head self-hosted gates

The final PR head must also complete the dedicated self-hosted `Regression Shield` and Windows smoke checks successfully. A queued or unavailable self-hosted runner is an infrastructure wait state, not permission to substitute a weaker hosted gate.

## WP3 Exit Gate

WP3 may become COMPLETE only when all of the following are true on one unchanged final PR head:

1. existing V9 quality/security gates remain mandatory and green;
2. fast PR checks are distinct from the full exact-head regression/security acceptance gate;
3. frontend baseline has deterministic type/lint/unit test coverage and an enforced future E2E/Playwright contract without creating the product Web app early;
4. capability-aware contracts require DB migration/API schema/authority/backup-restore/Telegram-signature/AI-schema tests when those capabilities appear;
5. critical money-path replay/idempotency tests remain explicitly protected;
6. mandatory workflows cannot use `continue-on-error`, floating external Actions, PR path-filter bypasses or unsafe self-hosted fork execution;
7. exact-head Fast PR Checks and V10 Toolchain Compatibility are green;
8. exact-head self-hosted Regression Shield/security and Windows smoke are green;
9. GitHub server-side protection for private `main` requires the mandatory checks and prevents bypass;
10. zero unresolved review blockers remain;
11. focused WP3 PR #236 is squash-merged to `main`.

After WP3 acceptance, **WP4 — Release, build provenance and deployment contract** becomes the next authorized work package. Overall accepted V10 progress remains 5% until Block B completes.

## Lenovo sequencing

Do not configure the V10 Lenovo runtime yet. Block C starts only after WP1–WP4 establish repository architecture, toolchain, CI and release/deployment contracts.

## Money/safety rule

GitHub access, AI output, Watchtower alert, Telegram message, `START V10`, or approval of any development work package is never broker-submit authorization. Current V9 execution boundaries and kill switches remain binding.
