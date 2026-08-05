# Omni-CIO V10 — Program Lock

Status: **OWNER-APPROVED PROGRAM / PLAN FINALIZED / DEVELOPMENT NOT STARTED**  
Baseline: **Omni-CIO v9.0.0 — COMPLETE / PROTECTED**  
Searchable canonical plan: `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`  
Owner-readable PDF: `docs/master-plan/Omni-CIO_V10_Master_Plan_RU.pdf`  
Integrity manifest: `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.sha256`  
Plan-readiness audit: `docs/master-plan/OMNI_CIO_V10_PLAN_READINESS_AUDIT.md`  
Account-independence audit trail: `docs/master-plan/OMNI_CIO_V10_ACCOUNT_INDEPENDENCE_AMENDMENT.md`

## 1. Authority

The owner has approved Omni-CIO V10 as the next and only feature-development program after the completed V9 program.

The canonical detailed program is stored as one synchronized pair:

- `OMNI_CIO_V10_MASTER_PLAN.md` — searchable source for developers, AI agents, code review and future automation;
- `Omni-CIO_V10_Master_Plan_RU.pdf` — rendered owner-readable copy of the same approved program;
- `OMNI_CIO_V10_MASTER_PLAN.sha256` — integrity fingerprints for both canonical files.

The owner-approved AI/GPT migration requirements and Account Independence / Deployment Portability requirements are already consolidated into the canonical Master Plan. `OMNI_CIO_V10_ACCOUNT_INDEPENDENCE_AMENDMENT.md` remains historical audit evidence, not a competing source of truth.

Current canonical SHA-256 values:

- PDF: `afb165183594d59c6218a419341f67fe5496f9567221efcf7521378914b6f106`
- Markdown: `80df1efd750d1f56bf3a1b097e0c8fef4414b9bb65aced503c669313dd55be25`

If these values ever differ from `OMNI_CIO_V10_MASTER_PLAN.sha256`, or if Markdown/PDF diverge substantively, V10 feature work must stop until an owner-reviewed documentation PR restores one synchronized canonical program and regenerates the manifest.

## 2. No implementation yet

Finalizing/merging this program does **not** start V10 implementation and does not broaden V9 runtime or broker authority.

V10 implementation begins only after a separate explicit owner command `START V10` after the finalized plan exists on accepted `main` with green exact-head CI/security.

Until that command, allowed work remains limited to V9 security/critical maintenance, dependency/recovery maintenance and documentation correctness that do not broaden runtime authority.

## 3. Program exclusivity

Once V10 implementation starts, all developers/AI agents must follow the canonical work-package sequence and exit gates.

Until V10 reaches full Definition of Done and owner acceptance:

- do not start V11 or another competing version program;
- do not create a parallel frontend, Telegram architecture, AI stack, Gateway, broker/execution stack or competing roadmap;
- do not skip directly to public/multi-user, billing or Real execution;
- brainstormed chat ideas are not scope unless incorporated through owner-approved program amendment;
- the mandatory AI sequence remains: GPT Knowledge Migration -> Knowledge/RAG -> Tool Registry/authority firewall -> Omni-CIO AI Copilot/Agent Orchestrator -> shared Web/Telegram AI -> bounded Autonomous Research Agent -> Custom GPT parity/decommission gate;
- the current Custom GPT cannot be removed before parity evidence and explicit owner acceptance;
- Account Independence / Deployment Portability remains binding throughout every block.

### 3.1 Account Independence / Deployment Portability invariant

- no personal ChatGPT, website-builder, IDE, hosting account, developer workstation or single runtime node may become the unique engineering source of truth;
- Web/API/AI/Telegram source, configuration schemas/defaults, DB migrations, tests, CI, deployment/bootstrap/recovery contracts and mandatory AI policies are repository-controlled where technically reasonable;
- primary Web is source-controlled application code, not proprietary UI-builder state;
- Lenovo is the first Personal runtime node, not the architectural owner; accepted V10 releases must be portable to another approved node;
- broker/Telegram/encryption secrets and private portfolio/runtime state remain outside GitHub;
- GitHub engineering access never implies broker trading authority;
- final V10 acceptance requires clean-room recovery/portability from GitHub + documented bootstrap + authorized backup + separately restored runtime secrets.

## 4. Sequential delivery rule

Default discipline:

`restore context -> identify current WP -> focused branch -> implementation + tests -> security/boundary review -> exact-head Regression Shield -> resolve review threads -> squash merge -> update V10 status -> next WP`

A WP is not complete because files/UI exist. Completion requires its defined Exit Gate and required integration/recovery evidence.

The first implementation work package after `START V10` is WP0. Later work packages cannot be treated as substitutes for an incomplete earlier gate.

## 5. Money and safety boundary

The completed V9 money/safety invariants remain binding unless a later V10 WP explicitly replaces a boundary and passes all acceptance gates:

- production read-only, Sandbox and Real credentials remain isolated;
- Real uses a separate account-scoped trading credential without transfer authority;
- no autonomous unconfirmed real-money execution;
- immutable plan before submit;
- confirmation remains short-lived and bound to the exact plan hash;
- one possible broker submit per idempotent identity;
- ambiguous possible-submit is never automatically retried;
- `submitted` is not `filled` without broker evidence;
- no withdrawal/transfer, margin/short or hidden authority expansion;
- AI has no direct broker-write authority;
- developer/repository access is never trading authorization;
- unhealthy time sync, durable state, audit persistence or external approval-auth gate blocks Real submit as defined by the canonical plan.

## 6. Source-of-truth order during V10

When V10 implementation begins, use this authority order:

1. accepted `main`;
2. `AGENTS.md`;
3. this Program Lock;
4. paired canonical program `OMNI_CIO_V10_MASTER_PLAN.md` + `Omni-CIO_V10_Master_Plan_RU.pdf` and integrity manifest;
5. `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;
6. relevant V10 architecture/ADR/runbook files accepted by the current WP;
7. current PR/CI/runtime acceptance evidence;
8. historical planning amendments/audits only as trace evidence, never to override the accepted canonical program.

If canonical sources conflict, feature development stops until the conflict is resolved by an owner-reviewed documentation change.

## 7. Final planning-readiness invariant

Before the owner may issue `START V10`, accepted `main` must prove:

- canonical Markdown/PDF are synchronized and SHA-256 tracked;
- weights A-J are exactly `5/9/12/14/14/8/18/8/7/5 = 100%`;
- AI/GPT migration and Account Independence are inside the canonical plan;
- data-at-rest, RPO/RTO, Web TLS/OWNER auth, runtime update, time-sync and logging/privacy requirements are explicit;
- temporary plan-generation tooling is absent;
- `OMNI_CIO_V10_PLAN_READINESS_AUDIT.md` has no substantive planning blocker;
- exact-head Regression Shield/security is green;
- zero unresolved PR review blockers remain;
- the plan is squash-merged into `main` while V10 implementation progress remains `0% / NOT STARTED`.

After those gates the planning state is **READY — WAITING FOR OWNER `START V10` COMMAND**.

## 8. Completion rule

V10 itself is not complete until the canonical program reaches 100%, the final evidence matrix is complete, clean-room recovery/portability and all final security/reliability gates pass, and the owner accepts the final release.

Until then no successor version is authorized.
