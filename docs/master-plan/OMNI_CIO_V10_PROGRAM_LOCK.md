# Omni-CIO V10 — Program Lock

Status: **OWNER-APPROVED PROGRAM / DEVELOPMENT NOT STARTED**  
Baseline: **Omni-CIO v9.0.0 — COMPLETE / PROTECTED**  
Searchable canonical plan: `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`  
Owner-readable PDF: `docs/master-plan/Omni-CIO_V10_Master_Plan_RU.pdf`  
Integrity manifest: `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.sha256`  
Mandatory portability amendment: `docs/master-plan/OMNI_CIO_V10_ACCOUNT_INDEPENDENCE_AMENDMENT.md`

## 1. Authority

The owner has approved Omni-CIO V10 as the next and only feature-development program after the completed V9 program.

The canonical detailed program is stored as a paired artifact:

- `OMNI_CIO_V10_MASTER_PLAN.md` is the searchable source for developers, AI agents, code review and future automation;
- `Omni-CIO_V10_Master_Plan_RU.pdf` is the rendered owner-readable copy of that approved program;
- `OMNI_CIO_V10_MASTER_PLAN.sha256` records integrity fingerprints for both files.

Owner-approved mandatory amendments recorded while V10 is still at 0% are part of the locked program when explicitly referenced by this Program Lock. The current mandatory portability amendment is:

- `OMNI_CIO_V10_ACCOUNT_INDEPENDENCE_AMENDMENT.md` — GitHub-controlled engineering source of truth, account independence, deployment portability, no UI-builder lock-in, reproducible development/deployment and strict separation between developer access and broker-secret/money authority.

The current PDF SHA-256 is:

`f9b7c0a00d277e6c6228fda47d3deb261b317bebf460ffe7d8c01fb4a19c0ec8`

The current Markdown SHA-256 is:

`e09d85310a26e9901d0c2d573398025ecfb15d9e294f4219cf8a0dbe1d65f852`

These hashes identify the current paired base-plan revision. The mandatory amendment is separately version-controlled and does not silently mutate the hashed base artifacts. **Before V10 feature implementation begins, all owner-approved mandatory amendments must be reconciled/consolidated into the next paired Master Plan Markdown/PDF revision and the integrity manifest must be regenerated.** No feature code may start while the canonical plan artifacts and the mandatory-amendment set disagree.

This file exists to make the program lock explicit and immediately searchable for every developer, AI agent, CI-maintenance session and future chat.

## 2. No implementation yet

Recording and approving the V10 program does **not** start V10 feature development. It only records the approved plan and locks future scope.

V10 implementation may begin only after a new explicit owner instruction to start V10 development.

Until that instruction, allowed repository work is limited to:

- preserving the accepted V9 baseline;
- security/critical maintenance required to keep V9 recoverable;
- dependency maintenance that passes the existing exact-head safety gates;
- documentation/recovery corrections and owner-approved plan amendments that do not broaden runtime authority.

## 3. Program exclusivity

Once V10 implementation starts, developers and AI agents must follow the canonical V10 plan sequentially.

Until V10 reaches its complete Definition of Done:

- do not start V11 or another competing version program;
- do not create a parallel frontend, Telegram architecture, AI stack, Gateway, execution stack or competing roadmap outside the approved V10 program;
- do not skip directly to Real execution, public/multi-user mode, billing or another later work package;
- do not reinterpret brainstormed chat ideas as approved scope if they are not in the canonical V10 program or an explicit mandatory amendment referenced by this Program Lock;
- new ideas go to a backlog/program-amendment proposal and require explicit owner approval before changing V10 scope;
- the owner-approved AI amendment is mandatory V10 scope: GPT Knowledge Migration -> Knowledge/RAG -> Tool Registry -> Omni-CIO AI Copilot/Agent Orchestrator -> shared Web/Telegram AI surface -> Autonomous Research Agent -> Custom GPT parity/decommission gate;
- the owner-approved account-independence amendment is mandatory V10 scope: GitHub is the engineering Control Plane/source of truth; Web/API/AI/Telegram/deployment must be rebuildable without the originating ChatGPT/developer/website-builder account; hosting/runtime must be replaceable; developer GitHub access must not reveal broker trading secrets;
- do not remove or decommission the existing Custom GPT/configuration before the parity gate and explicit owner acceptance.

### 3.1 Account Independence / Deployment Portability invariant

The following is binding throughout V10:

- no personal ChatGPT account, website-builder account, IDE account, hosting account, developer workstation or single physical runtime may become the unique source of truth for the product;
- application code, configuration schemas/defaults, migrations, AI System Policy/RAG/Tool Registry, deployment definitions, tests, bootstrap and recovery documentation are repository-controlled wherever technically reasonable;
- the primary Web application is source-controlled code and must not depend on proprietary UI-builder state that cannot be rebuilt from GitHub;
- Lenovo is the first Personal V10 runtime, not the architectural owner of the project; another approved node must be able to run an accepted release using documented prerequisites;
- actual broker/Telegram/encryption secrets and private portfolio/runtime state remain outside GitHub;
- granting a developer GitHub engineering role never implicitly grants real-money authority;
- V10 final acceptance requires a clean-room portability/recovery rehearsal from GitHub + documented bootstrap + authorized backup + separately restored runtime secrets.

Detailed acceptance criteria are defined in `OMNI_CIO_V10_ACCOUNT_INDEPENDENCE_AMENDMENT.md`.

## 4. Sequential delivery rule

Future V10 work must use the program work-package order and exit gates.

Default discipline:

`restore context → identify current WP → focused branch → implementation + tests → security/boundary review → exact-head Regression Shield → resolve review threads → squash merge → update V10 status → next WP`

A later WP must not be treated as complete merely because code exists. Completion requires its defined exit gate and required integration evidence.

Before the first feature-development WP starts, the owner-approved mandatory amendments recorded during the 0% planning phase must be consolidated into the canonical paired Master Plan artifacts and their hashes regenerated.

## 5. Money and safety boundary

The completed V9 safety invariants remain binding throughout V10:

- production read-only, Sandbox and Real authority remain isolated;
- real execution uses a separate account-scoped trading credential without transfer authority;
- no autonomous unconfirmed real-money execution;
- immutable plan/proposal before submit;
- owner confirmation remains plan-bound and short-lived;
- one possible broker submit per idempotent identity;
- ambiguous possible-submit is never automatically retried;
- `submitted` is not `filled` without broker evidence;
- no withdrawal/transfer, margin/short or hidden expansion of broker authority;
- secrets/private portfolio payloads never enter GitHub;
- repository/developer access is never treated as trading-secret authorization.

## 6. Source-of-truth order during V10

When V10 implementation begins, use this authority order:

1. accepted `main`;
2. `AGENTS.md`;
3. this program-lock file;
4. owner-approved mandatory V10 amendments referenced by this Program Lock, currently including `OMNI_CIO_V10_ACCOUNT_INDEPENDENCE_AMENDMENT.md`;
5. the paired canonical V10 program: `OMNI_CIO_V10_MASTER_PLAN.md` + `Omni-CIO_V10_Master_Plan_RU.pdf` after mandatory-amendment consolidation;
6. `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;
7. relevant V10 architecture/runbook files created by the current work package;
8. current PR/CI evidence.

If the Markdown and PDF ever differ in substantive program content, or a mandatory amendment has not yet been consolidated before feature implementation, V10 feature development must stop until the discrepancy is resolved through an owner-reviewed documentation PR. Neither artifact may be silently edited to change scope.

Historical V9 issues, PRs and old chat remain audit/context evidence and cannot override the accepted V10 program.

## 7. Completion rule

V10 is not complete until the canonical program reaches **100%** and the final V10 Definition of Done is satisfied and owner-accepted.

In addition to the existing Definition of Done, final V10 acceptance requires proof that:

- the Web application and supported development environment are reproducible from repository-controlled source/configuration contracts;
- an accepted V10 release can be deployed to a fresh approved runtime without the originating ChatGPT/developer account;
- private state and secrets are restored through documented separate recovery paths rather than Git history;
- the deployed runtime identifies the expected reviewed release/Git SHA;
- engineering access can be granted without disclosing OWNER broker trading credentials;
- the account-independence/portability rehearsal defined by the mandatory amendment is green.

Until then, no successor version is authorized.
