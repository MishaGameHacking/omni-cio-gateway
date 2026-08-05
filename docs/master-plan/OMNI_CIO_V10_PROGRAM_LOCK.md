# Omni-CIO V10 — Program Lock

Status: **OWNER-APPROVED PROGRAM / DEVELOPMENT STARTED / WP1 COMPLETE ON ACCEPTED MAIN / WP2 NEXT**  
Baseline: **Omni-CIO v9.0.0 — COMPLETE / PROTECTED / controlled maintenance**  
Searchable canonical plan: `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`  
Owner-readable PDF: `docs/master-plan/Omni-CIO_V10_Master_Plan_RU.pdf`  
Integrity manifest: `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.sha256`  
Plan-readiness audit: `docs/master-plan/OMNI_CIO_V10_PLAN_READINESS_AUDIT.md`  
Start/WP0 record: `docs/master-plan/OMNI_CIO_V10_START_RECORD.md`  
Current progress authority: `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`

> Authority note: `WP1 COMPLETE / WP2 NEXT` is effective only when this file is present on accepted `main` after the focused WP1 PR passes final exact-head CI/security and is squash-merged. In an unmerged PR it is the acceptance candidate, not accepted project state.

## 1. Authority

The owner approved Omni-CIO V10 as the next and only feature-development program after completed V9 and explicitly issued **`START V10`** on 2026-08-05.

The canonical detailed program is stored as one synchronized pair:

- `OMNI_CIO_V10_MASTER_PLAN.md` — searchable source for developers, AI agents, code review and automation;
- `Omni-CIO_V10_Master_Plan_RU.pdf` — owner-readable synchronized copy;
- `OMNI_CIO_V10_MASTER_PLAN.sha256` — integrity fingerprints.

Current canonical SHA-256 values:

- PDF: `afb165183594d59c6218a419341f67fe5496f9567221efcf7521378914b6f106`
- Markdown: `80df1efd750d1f56bf3a1b097e0c8fef4414b9bb65aced503c669313dd55be25`

If the manifest diverges from either canonical plan artifact, or Markdown/PDF diverge substantively, V10 feature work stops until owner-reviewed correction restores one canonical program.

## 2. Program state and sequence

Planning was accepted by squash-merged PR #227 on start baseline:

`159316c5b211977b0d9125dffb86210316ae10d3`

Post-merge Regression Shield run #1332 succeeded on that exact SHA.

WP0 architecture freeze was accepted by squash-merged PR #228 as:

`7c5de954eed10dd406e743c38f7bdef6b0634108`

That acceptance closed Block A at **5%** and authorized WP1.

WP1 repository architecture/boundaries are delivered by focused PR #229. Once its final exact-head Regression Shield/security is green, review blockers are zero and the PR is squash-merged to `main`:

- WP1 becomes **COMPLETE**;
- overall accepted V10 progress remains **5%** because Block B carries one 9% block weight and is not credited piecemeal;
- next authorized package becomes **WP2 — Toolchain and Dependency Baseline**.

WP3 and later remain blocked until predecessor Exit Gates are accepted. Lenovo one-time setup remains Block C after WP1–WP4.

## 3. Frozen architecture and repository authority

WP0 establishes these architecture sources:

- `docs/architecture/V10_SYSTEM_ARCHITECTURE.md`;
- `docs/architecture/V10_SECURITY_BOUNDARIES.md`;
- `docs/architecture/V10_DATA_FLOW.md`;
- `docs/architecture/V10_THREAT_MODEL.md`;
- `docs/architecture/V10_RECOVERY_CONTRACT.md`;
- `docs/architecture/V10_ADR_PROCESS.md`;
- `docs/architecture/V10_V9_BASELINE_FREEZE.md`;
- ADR-019 in `docs/architecture/DECISIONS.md`.

WP1 adds the repository architecture authority:

- `docs/architecture/REPOSITORY_STRUCTURE.md`;
- `.github/CODEOWNERS`;
- `scripts/check_v10_repository_boundaries.py`;
- focused tests in `tests/test_v10_repository_boundaries.py`;
- permanent Regression Shield wiring for the V10 boundary guard.

These documents/checks implement the Master Plan; they do not override it. A material architecture/scope change requires an ADR and, when scope/authority changes, an owner-approved program amendment.

## 4. Program exclusivity

Until V10 reaches full Definition of Done and owner acceptance:

- do not start V11 or another competing version program;
- do not create a parallel frontend, Telegram architecture, AI stack, Gateway, broker/execution stack or competing roadmap;
- do not skip directly to public/multi-user, billing or Real execution;
- brainstormed chat ideas are not approved scope unless incorporated through the program-amendment process;
- the mandatory AI sequence remains: GPT Knowledge Migration -> Knowledge/RAG -> Tool Registry/authority firewall -> Omni-CIO AI Copilot/Agent Orchestrator -> shared Web/Telegram AI -> bounded Autonomous Research Agent -> Custom GPT parity/decommission gate;
- current Custom GPT cannot be removed before parity evidence and explicit owner acceptance;
- Account Independence / Deployment Portability remains binding throughout every block.

## 5. Account Independence / Deployment Portability invariant

- no personal ChatGPT, website-builder, IDE, hosting account, developer workstation or single runtime node may become the unique engineering source of truth;
- Web/API/AI/Telegram source, configuration schemas/defaults, DB migrations, tests, CI, deployment/bootstrap/recovery contracts and mandatory AI policies are repository-controlled where technically reasonable;
- primary Web is source-controlled application code, not proprietary UI-builder state;
- Lenovo is the first Personal runtime node, not the architectural owner; accepted V10 releases must be portable to another approved node;
- broker/Telegram/encryption secrets and private portfolio/runtime state remain outside GitHub;
- GitHub engineering access never implies broker trading authority;
- final V10 acceptance requires clean-room recovery/portability from GitHub + documented bootstrap + authorized backup + separately restored runtime secrets.

WP1 specifically fixes repository ownership for future `apps/`, `ai/` and `infrastructure/` artifacts and prohibits account-only authoritative application settings where repository-controlled representation is technically possible.

## 6. Sequential delivery rule

Default discipline:

`restore context -> identify exactly one current WP -> focused branch -> implementation + tests -> security/boundary review -> exact-head Regression Shield -> resolve review threads -> squash merge -> update V10 status -> next WP`

A WP is not complete because files/UI exist. Completion requires its Exit Gate and required integration/recovery evidence.

## 7. Money and safety boundary

The completed V9 money/safety invariants remain binding unless a later V10 WP explicitly replaces a boundary and passes all acceptance gates:

- production READ, Sandbox and Real credentials remain isolated;
- Real uses a separate account-scoped trading credential without transfer authority;
- no autonomous unconfirmed real-money execution;
- immutable plan before submit;
- confirmation remains short-lived and bound to exact plan hash;
- one possible broker submit per idempotent identity;
- ambiguous possible-submit is never automatically retried;
- `submitted` is not `filled` without broker evidence;
- no withdrawal/transfer, margin/short or hidden authority expansion;
- AI has no direct broker-write authority;
- developer/repository access is never trading authorization;
- unhealthy time sync, durable state, audit persistence or external approval-auth gate blocks Real submit as defined by the canonical plan.

Existing master rollback remains:

`REAL_TRADING_ENABLED=false`.

## 8. Source-of-truth order during V10

1. accepted `main`;
2. `AGENTS.md`;
3. this Program Lock;
4. paired canonical V10 Master Plan Markdown/PDF + integrity manifest;
5. `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;
6. accepted current V10 architecture/ADR/runbook files;
7. current PR/CI/runtime acceptance evidence;
8. historical amendments/audits only as trace evidence.

If canonical sources conflict, feature development stops until conflict is resolved by owner-reviewed change.

## 9. Branch / CI protection rule

At WP0 start GitHub reported `main` without server-side branch protection. This does not authorize direct pushes.

Until WP3 evaluates/configures the strongest protection available for this private repository, the mandatory process is manually enforced:

`focused branch -> PR -> exact-head Regression Shield/security -> zero unresolved review blockers -> squash merge`.

WP3 must explicitly evaluate required status checks/conversation resolution/restrictions available for the owner's GitHub plan. Unsupported paid/platform controls require documented compensating controls rather than silent omission.

## 10. Completion rule

V10 is not complete until the canonical program reaches 100%, final capability evidence matrix is complete, clean-room recovery/portability and final security/reliability gates pass, and the owner accepts the final release.

Until then no successor version is authorized.
