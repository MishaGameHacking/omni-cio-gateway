# Omni-CIO — Documentation Authority and Lifecycle

Status: **ACTIVE DOCUMENTATION GOVERNANCE**  
Applies to: repository-visible informational pages, engineering guidance, V10/V9 program records, architecture/contracts, runbooks and acceptance evidence.

## Purpose

Omni-CIO keeps historical evidence without allowing old wording to become a second current-state ledger. This document defines which files answer **what is true now**, which files define stable contracts, and which files are historical snapshots from the time a Work Package or acceptance event was executed.

The rule is simple:

> A dated or package-local record may remain historically correct without being current program authority. Current V10 progress and the authorized next Work Package are read only from `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` on accepted `main`.

## 1. Live current-authority layer

These files are expected to remain readable and non-contradictory for a developer, AI agent or OWNER opening the repository today:

- `README.md` — repository front door and concise current snapshot;
- `AGENTS.md` — mandatory engineering/safety rules;
- `CONTRIBUTING.md` — contributor workflow;
- `CHANGELOG.md` — milestone history whose `Unreleased` section must not maintain a competing current-WP ledger;
- `docs/README.md` — documentation navigation;
- `docs/master-plan/README.md` — master-plan navigation;
- `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md` — scope, exclusivity and precedence lock;
- `docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md` — accepted amendment discovery;
- `knowledge/00_PROJECT_MASTER_CONTEXT.md` — long-lived product context without a competing progress ledger;
- `knowledge/16_CURRENT_PROGRAM_STATUS.md` — protected V9 applied/runtime state only;
- `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` — **only current V10 progress/current-next-WP ledger**;
- `gpt/PROJECT_INSTRUCTIONS.md`, `gpt/NEW_CHAT_PROMPT.md` and `.github/copilot-instructions.md` — agent/chat entry guidance that must delegate dynamic state to the V10 status file.

Live guidance must not hard-code an obsolete `NEXT`, obsolete implementation percentage, or an already-passed prerequisite as though it were still pending.

Transient branch-local checkpoint identifiers (`P*`, `V9C-*`) and numbered "CURRENT AMENDMENT-N" banners are not live-guidance state. Live entry documents must delegate those mutable details to `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`, the Amendments Index and exact PR Actions evidence.

## 2. Stable program and architecture contracts

These define requirements or semantics and normally change only through their owning governance process:

- synchronized V10 Master Plan Markdown/PDF plus SHA manifest;
- accepted active amendments;
- system/security/data-flow/threat/recovery architecture;
- ADRs and `DECISIONS.md`;
- machine-readable policy/contracts/schemas;
- repository/toolchain/release/identity/security contracts.

A stable contract may contain language describing the state at the time it was selected or accepted. Such historical context does not override `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

## 3. Work-Package execution and runbook records

Files such as `V10_WP*_EXECUTION_CONTRACT*`, package-specific runbooks, acceptance-state files and package audit evidence are **package-scoped records**. Their status headings describe the lifecycle point for that package and may intentionally say `PENDING`, `CURRENT WORK PACKAGE`, or similar wording from that time.

After a later package is accepted, those records remain useful for reproducibility, rollback and audit. They are not rewritten merely to make every historical sentence sound current, and they never authorize a later WP by themselves.

## 4. Historical audit/start/acceptance records

Examples include:

- `docs/master-plan/OMNI_CIO_V10_START_RECORD.md`;
- `docs/master-plan/OMNI_CIO_V10_PLAN_READINESS_AUDIT.md`;
- completed acceptance records;
- original planning checklists whose checkbox state is frozen as planning evidence;
- V9 completed program documents;
- merged PR descriptions, closed issues and old comments.

These are immutable-in-meaning historical evidence. A prominent lifecycle note should be added when a heading such as `Current work package`, `0% / NOT STARTED` or an unchecked old planning list could otherwise be mistaken for present state.

## 5. Applied V9 recovery/configuration records

`gpt/`, current V9 architecture/runbooks and `knowledge/16_CURRENT_PROGRAM_STATUS.md` remain protected production/recovery material until the responsible V10 parity/decommission gate explicitly retires them.

V9 documentation is not stale merely because V10 exists. It becomes obsolete only when the responsible V10 cutover is accepted and the recovery contract says it may be retired.

`knowledge/16_CURRENT_PROGRAM_STATUS.md` is intentionally scoped to **V9 runtime**, not the entire repository program. The active V10 feature state lives separately in `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

## 6. Precedence when two files look inconsistent

For current V10 development use this order:

1. accepted `main`;
2. `AGENTS.md`;
3. `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`;
4. synchronized V10 Master Plan + accepted amendments;
5. machine-readable contracts;
6. `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` for dynamic progress/current-next WP;
7. accepted current-WP architecture/runbook/evidence;
8. historical records only as evidence of what was true at their recorded time.

If a live-guidance file conflicts with the current-status file, the conflict is a documentation defect and must be corrected through a focused PR. Do not solve it by inventing a new status file.

## 7. Current repository presentation rule

The root `README.md` is the OWNER/developer front door. It must show a concise current-state box sourced from the canonical status file and then point to the detailed authorities. It must not duplicate the entire status ledger.

`docs/README.md` and `docs/master-plan/README.md` are navigation pages. They should describe document classes and current ownership, not maintain their own independent WP queue.

`CHANGELOG.md` may record release/program milestones, but its `Unreleased` section must delegate exact V10 current-next/progress to the canonical status file.

`gpt/PROJECT_INSTRUCTIONS.md` and `gpt/NEW_CHAT_PROMPT.md` are handoff helpers, not program-state databases. They must instruct a new session to re-read accepted `main` rather than embedding an old `NEXT`.

## 8. Historical wording rule

Do not erase historical evidence merely because the program advanced. Instead:

- change misleading labels such as `Current work package` to `Work package at record creation` when safe;
- add `HISTORICAL SNAPSHOT — NOT CURRENT-STATE AUTHORITY` to dated start/readiness records that can be opened out of context;
- label old implementation checklists as historical planning records if unchecked boxes can be mistaken for missing current work;
- preserve exact old evidence, hashes, run IDs, findings and acceptance meaning;
- link back to `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` for present state.

## 9. Permanent automated guard

`scripts/check_v10_documentation_consistency.py` verifies the live-guidance layer and high-risk historical headers. The guard checks, among other things:

- one canonical V10 current-status file;
- readable current snapshots in the root README, `AGENTS.md` and `knowledge/00_PROJECT_MASTER_CONTEXT.md` agree with the canonical status percentage/current WP;
- live guidance delegates dynamic state to `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;
- live guidance does not freeze transient branch-local `P*`/`V9C-*` checkpoints or numbered current-amendment banners;
- known stale WP4/5%/pre-WP2 wording is absent from live guidance;
- Program Lock does not maintain a competing progress ledger;
- WP2 toolchain baseline is labeled accepted rather than pending;
- start/readiness records are explicitly historical;
- the Engineering Quality amendment/contract are labeled accepted/active after their accepted merge;
- current accepted repository roots are not described as wholly future/reserved.

The Engineering Governance workflow runs this guard so the same documentation-confusion class is harder to reintroduce.

## 10. Safety and privacy

Documentation cleanup must never add real broker/Telegram/VK tokens, encryption/recovery keys, full account IDs, private portfolio payloads or secret-bearing screenshots. It must preserve:

- `app:app`;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- protected V9 rollback;
- current broker authority boundaries;
- Master Plan sequence and Exit Gates.

Documentation clarity may describe accepted evidence; it may not fabricate missing runtime/OWNER evidence or turn a pending WP into `COMPLETE`.
