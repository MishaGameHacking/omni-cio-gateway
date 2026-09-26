# Master plan Omni-CIO

Эта папка хранит **owner-approved master programs, Program Locks, active amendments и audit trail** развития Omni-CIO. Завершённые программы и исторические WP-записи не являются очередью задач; активная программа определяется Program Lock + Current Status + accepted active amendments.

Documentation lifecycle: `../DOCUMENTATION_AUTHORITY_AND_LIFECYCLE.md`.

## Omni-CIO V10 Personal Autonomous Investment Platform — active feature program

OWNER approved the canonical V10 program and issued explicit **`START V10`** on 2026-08-05.

Canonical base artifacts:

- `OMNI_CIO_V10_MASTER_PLAN.md` — searchable base program for developers/AI/code review;
- `Omni-CIO_V10_Master_Plan_RU.pdf` — owner-readable synchronized copy;
- `OMNI_CIO_V10_MASTER_PLAN.sha256` — integrity manifest;
- `OMNI_CIO_V10_PROGRAM_LOCK.md` — scope/precedence/exclusivity lock; it intentionally does not maintain a second moving progress ledger;
- `OMNI_CIO_V10_PLAN_READINESS_AUDIT.md` — historical pre-development readiness audit;
- `OMNI_CIO_V10_START_RECORD.md` — historical explicit OWNER start/WP0 evidence.

Accepted amendment discovery:

- `OMNI_CIO_V10_AMENDMENTS_INDEX.md` — mandatory index of active/superseded amendments;
- `OMNI_CIO_V10_CONCRETE_EXECUTION_PLAN_AMENDMENT.md` — binding concrete data/AI/autonomy implementation decisions;
- `OMNI_CIO_V10_GITHUB_PRO_AND_MIGRATION_IMPLEMENTATION_AMENDMENT.md` — GitHub Pro, migration/parity and WP implementation discipline;
- `OMNI_CIO_V10_AUTONOMOUS_PORTFOLIO_GOVERNANCE_AND_COMMERCIAL_MODEL_AMENDMENT.md` — portfolio-governance and historical commercial direction, superseded for initial free launch where Amendment 10 conflicts;
- `OMNI_CIO_V10_IDENTITY_MULTI_TENANT_ACCOUNT_AND_AUTHENTICATION_AMENDMENT.md` — identity/tenant/authentication baseline;
- `OMNI_CIO_V10_PHONE_ONLY_ENGINEERING_AND_HEADLESS_NODE_OPERATIONS_AMENDMENT.md` — browser-only OWNER/headless Lenovo operations baseline, superseded where Amendment 10 forbids home/Lenovo public-production dependency;
- `OMNI_CIO_V10_ENGINEERING_QUALITY_AND_GREEN_MERGE_AMENDMENT.md` — accepted Pre-CI/all-green/failure-learning/OWNER-handoff discipline;
- `OMNI_CIO_V10_PRODUCT_USER_AND_ENGINEERING_AUTHORITY_BOUNDARY_AMENDMENT.md` — ordinary USER identity is separate from PROJECT OWNER engineering/business authority;
- `OMNI_CIO_V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_AMENDMENT.md` — public global browser product, managed-cloud production, no OWNER-home production dependency, free initial access and tenant-scoped broker credentials;
- `OMNI_CIO_V10_WP22A_TECHNICAL_CLOSEOUT_AND_PUBLIC_ACTIVATION_SEPARATION_AMENDMENT.md` — separates complete WP22A technical acceptance from later production activation;
- `OMNI_CIO_V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_AMENDMENT.md` — Amendment 12, Integrated System Update Execution Law; changes delivery granularity while preserving dependency order, safety and accepted-main progress semantics;
- `OMNI_CIO_V10_GREEN_CHECKPOINT_AND_TARGETED_CI_REPAIR_AMENDMENT.md` — Amendment 16, current Green Checkpoint / targeted CI repair cadence that supersedes conflicting wait-all/Single Remote Publication/batch-only defaults while preserving execution order and safety;
- `../architecture/V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_CONTRACT.json` — machine-readable execution-unit contract with Amendment-16 supersession fields;
- `../architecture/V10_GREEN_CHECKPOINT_TARGETED_CI_REPAIR_CONTRACT.json` — machine-readable Amendment-16 checkpoint/repair contract;
- `../operations/V10_GREEN_CHECKPOINT_CI_RUNBOOK.md` — operational checkpoint/targeted-repair runbook;
- `../architecture/V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_CONTRACT.json` — machine-readable public launch direction;
- `../architecture/V10_AI_CORTEX_CONTRACT.json` and other machine-readable companions — executable/validated policy where defined;
- `OMNI_CIO_V10_ACCOUNT_INDEPENDENCE_AMENDMENT.md` — historical owner-approved amendment already consolidated into the base plan and retained for provenance;
- `OMNI_CIO_V10_RU_PUBLIC_REGISTRATION_AND_RUSSIAN_INGRESS_AMENDMENT.md` — Amendment 18, current Timeweb-only infrastructure / Telegram-only human login authority;
- `OMNI_CIO_V10_TIMEWEB_NO_OWNER_LAPTOP_DEPENDENCY_AMENDMENT.md` — Amendment 19, current hosted-source boundary without OWNER-laptop runtime dependency;
- `OMNI_CIO_V10_V9_TO_V10_CONVERGENCE_AND_LEGACY_RETIREMENT_AMENDMENT.md` — Amendment 20, V9 migration-source convergence and proven legacy working-tree retirement inside PR #584.

Current V10 progress authority:

`../../knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

Do **not** hard-code or infer the current WP/progress from historical PR text, a dated amendment, a package execution contract, branch Execution Ledger or this index. The status file on accepted `main` is the current-state authority.

The synchronized Master Plan Markdown/PDF pair must not be edited independently. New OWNER-approved implementation detail may be recorded by focused amendment; a later intentional consolidation must regenerate/review the synchronized pair and its integrity manifest together.

## V10 delivery sequence and lifecycle

The canonical dependency/Block/WP sequence remains defined by `OMNI_CIO_V10_MASTER_PLAN.md`. Amendment 12 changes **delivery granularity**, not dependency order. Amendment 16 changes verification cadence/publication/repair timing, not dependency order or accepted-main progress semantics.

Every material change uses exactly one execution unit:

- `FOCUSED_CHANGE` for an isolated defect/governance/maintenance/mandatory-split unit;
- `INTEGRATED_SYSTEM_UPDATE` for one coherent OWNER-authorized System Update with ordered member WP/increments.

For integrated work, member milestones retain their own scope/contracts/tests/internal Exit criteria but may be completed branch-locally before the single final integrated PR. Accepted percentage and next-major-update authority change only after complete squash merge plus required exact-main post-merge acceptance.

`INTEGRATION_READY` remains the final whole-update readiness state before final landing review. Earlier logical checkpoints may be published under Amendment 16, but every published checkpoint must become `CERTIFIED_GREEN` before the next functional checkpoint or dependent milestone begins.

Any applicable RED or material review finding immediately puts the branch in `RED_REPAIR_ONLY`. Diagnosis starts as soon as useful evidence exists; unchanged-source transient infrastructure failures may use specific-job same-SHA rerun, while repository-content repair requires a replacement SHA, targeted proof and full exact-SHA recertification. Temporary verifier commits/PRs and fake GREEN remain forbidden.

Every integrated update uses `../updates/INTEGRATED_SYSTEM_UPDATE_EXECUTION_LEDGER_TEMPLATE.md` and the repository System Update dashboard issue template. Those working records must say `BRANCH-LOCAL EXECUTION STATE — NOT ACCEPTED MAIN AUTHORITY`.

Historical package files may correctly say that an earlier WP was `CURRENT`, `PENDING` or `NEXT` at the time they were written. That wording is package evidence, not a live queue. Current authorization is always read from `../../knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

## Concrete V10 product lock

The accepted amendments clarify implementation without changing block weights/order:

- Deterministic Core owns financial/accounting truth;
- V10 accounting target uses verified broker HTML reports; no photo/screenshot/OCR portfolio workflow;
- MOEX is current-market enrichment and stays distinct from broker period-end facts;
- local-first AI assumptions remain gated by the owning AI WP and later hosting decisions;
- paid AI/search/hosted-agent SaaS is not required for V10 Definition of Done unless a later owning gate proves it necessary;
- System Policy + typed tools + RAG + evals precede QLoRA;
- 24/7 autonomy is event-driven/checkpointed;
- bounded research + Evidence Store and provenance/freshness discipline remain mandatory;
- AI has no direct broker-write/admin/GitHub-bypass/Real-money authority;
- OWNER local participation is minimized to genuinely non-delegable actions;
- PROJECT OWNER is not a special product role; OWNER is an ordinary USER on the same account/tenant/session path;
- final public V10 production must be hosted independently of OWNER home infrastructure; Lenovo remains engineering/CI/recovery;
- initial public USER access is free; future monetization is deferred optional scope;
- broker READ/optional TRADE credentials belong only to the authenticated tenant's `BrokerConnection`;
- CI is an independent verifier and active checkpoint certifier; focused preflight remains mandatory and every applicable exact-head project gate must conclude SUCCESS;
- Amendment 16 requires `CERTIFIED_GREEN` before the next functional checkpoint and does not weaken exact-head, squash, recovery, public-production, broker or Real-money gates.

## Prepared visual System Update

When current accepted status authorizes it and exact OWNER START is issued, Amendment 12 groups the approved visual refresh as:

`WEB-VISUAL-A -> B -> C -> D -> E -> F -> G`

inside `WEB-VISUAL-INTEGRATED` by default. The content/dependency order remains binding even though separate PR-per-increment delivery is no longer mandatory.

Acceptance of Amendment 12 itself keeps **PRODUCT IMPLEMENTATION PAUSED**. Exact command required before product source work:

`START V10 WEB VISUAL SYSTEM UPDATE`

## Omni-CIO v9 Portfolio Autopilot — completed historical program / V9 migration source

The accepted V9 program is completed historical evidence and a **V9 migration source** for the single forward V10/Timeweb runtime.

Canonical completed program:

`OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`.

V9 WP0–WP15 repository delivery and owner external acceptance are complete. Amendment 20 supersedes the old parallel controlled-maintenance framing for forward development: useful behavior is migrated/reused in V10, obsolete working-tree paths retire after proof, and Git history retains the historical record.

Current V9 applied/runtime status:

`../../knowledge/16_CURRENT_PROGRAM_STATUS.md`.

`app:app` and other remaining compatibility paths persist only until their owning V9C replacement/parity/recovery gate passes; they are not permanent forward-runtime authority.

## Source-of-truth hierarchy

For current V10 development:

1. accepted `main`;
2. `../../AGENTS.md`;
3. `OMNI_CIO_V10_PROGRAM_LOCK.md`;
4. synchronized `OMNI_CIO_V10_MASTER_PLAN.md` + PDF + SHA manifest;
5. `OMNI_CIO_V10_AMENDMENTS_INDEX.md` + accepted active amendments, with later explicit amendments controlling conflicts;
6. machine-readable contracts;
7. `../../knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` for dynamic progress/current-next execution authority;
8. accepted V10 architecture/ADR/current execution-unit contracts;
9. branch Ledger/dashboard as non-authoritative working state when an integrated update is active;
10. exact-head PR/CI/runtime evidence;
11. historical records as historical evidence only.

## Permanent safety boundaries

V10 development does not silently remove V9 safety boundaries:

- production read-only credential remains isolated;
- Sandbox remains virtual and separately credentialed;
- Real execution remains exact-USER-confirmed for that USER's own tenant, immutable, idempotent, fail-closed and broker-reconciled;
- AI has no direct broker-write authority;
- GitHub engineering access is never trading authorization;
- current `app:app` / GPT recovery behavior remains only until the owning V9C migration/recovery gate proves replacement and retirement;
- `PUBLIC_MULTI_USER_ENABLED=false`, `trading_methods=false` and `REAL_TRADING_ENABLED=false` remain fail-closed until their own accepted gates;
- no competing GPT/Gateway/Web/Telegram/AI/execution source of truth.

## Further-change rule

V10 work proceeds through the execution unit authorized by current status. `FOCUSED_CHANGE` remains focused and reviewable. `INTEGRATED_SYSTEM_UPDATE` keeps ordered internal milestones, focused preflight, final `INTEGRATION_READY`, Green Checkpoint certification before dependent work, immediate `RED_REPAIR_ONLY` on material failure, targeted repair proof, full exact-SHA recertification, all applicable exact-head SUCCESS, zero blocking review threads, squash merge and required post-merge verification.

New material scope is accepted only through the amendment process. V11/competing programs remain prohibited until V10 final acceptance.
