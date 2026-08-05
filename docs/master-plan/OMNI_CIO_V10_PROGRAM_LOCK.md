# Omni-CIO V10 — Program Lock

Status: **OWNER-APPROVED PROGRAM / DEVELOPMENT NOT STARTED**  
Baseline: **Omni-CIO v9.0.0 — COMPLETE / PROTECTED**  
Searchable canonical plan: `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`  
Owner-readable PDF: `docs/master-plan/Omni-CIO_V10_Master_Plan_RU.pdf`  
Integrity manifest: `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.sha256`

## 1. Authority

The owner has approved Omni-CIO V10 as the next and only feature-development program after the completed V9 program.

The canonical detailed program is stored as a paired artifact:

- `OMNI_CIO_V10_MASTER_PLAN.md` is the searchable source for developers, AI agents, code review and future automation;
- `Omni-CIO_V10_Master_Plan_RU.pdf` is the rendered owner-readable copy of that approved program;
- `OMNI_CIO_V10_MASTER_PLAN.sha256` records integrity fingerprints for both files.

The current PDF SHA-256 is:

`cb6018fa4816850e86509de9470b9cd45308216d7d8b910bb4036cacbb017b84`

The current Markdown SHA-256 is:

`2bb63791e7564b2df32563f23d5bf425d3ede7a67f645e7420f24aaf53078c0c`

This file exists to make the program lock explicit and immediately searchable for every developer, AI agent, CI-maintenance session and future chat.

## 2. No implementation yet

Recording and approving the V10 program does **not** start V10 feature development. It only records the approved plan and locks future scope.

V10 implementation may begin only after a new explicit owner instruction to start V10 development.

Until that instruction, allowed repository work is limited to:

- preserving the accepted V9 baseline;
- security/critical maintenance required to keep V9 recoverable;
- dependency maintenance that passes the existing exact-head safety gates;
- documentation/recovery corrections that do not broaden runtime authority.

## 3. Program exclusivity

Once V10 implementation starts, developers and AI agents must follow the canonical V10 plan sequentially.

Until V10 reaches its complete Definition of Done:

- do not start V11 or another competing version program;
- do not create a parallel frontend, Telegram architecture, AI stack, Gateway, execution stack or competing roadmap outside the approved V10 program;
- do not skip directly to Real execution, public/multi-user mode, billing or another later work package;
- do not reinterpret brainstormed chat ideas as approved scope if they are not in the canonical V10 program;
- new ideas go to a backlog/program-amendment proposal and require explicit owner approval before changing V10 scope;
- the owner-approved AI amendment is mandatory V10 scope: GPT Knowledge Migration -> Knowledge/RAG -> Tool Registry -> Omni-CIO AI Copilot/Agent Orchestrator -> shared Web/Telegram AI surface -> Autonomous Research Agent -> Custom GPT parity/decommission gate;
- do not remove or decommission the existing Custom GPT/configuration before the parity gate and explicit owner acceptance.

## 4. Sequential delivery rule

Future V10 work must use the program work-package order and exit gates.

Default discipline:

`restore context → identify current WP → focused branch → implementation + tests → security/boundary review → exact-head Regression Shield → resolve review threads → squash merge → update V10 status → next WP`

A later WP must not be treated as complete merely because code exists. Completion requires its defined exit gate and required integration evidence.

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
- secrets/private portfolio payloads never enter GitHub.

## 6. Source-of-truth order during V10

When V10 implementation begins, use this authority order:

1. accepted `main`;
2. `AGENTS.md`;
3. this program-lock file;
4. the paired canonical V10 program: `OMNI_CIO_V10_MASTER_PLAN.md` + `Omni-CIO_V10_Master_Plan_RU.pdf`;
5. `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;
6. relevant V10 architecture/runbook files created by the current work package;
7. current PR/CI evidence.

If the Markdown and PDF ever differ in substantive program content, V10 feature development must stop until the discrepancy is resolved through an owner-reviewed documentation PR. Neither artifact may be silently edited to change scope.

Historical V9 issues, PRs and old chat remain audit/context evidence and cannot override the accepted V10 program.

## 7. Completion rule

V10 is not complete until the canonical program reaches **100%** and the final V10 Definition of Done is satisfied and owner-accepted.

Until then, no successor version is authorized.
