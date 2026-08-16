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
- `OMNI_CIO_V10_CONCRETE_EXECUTION_PLAN_AMENDMENT.md` — binding concrete data/AI/autonomy/Lenovo/subscription implementation decisions;
- `OMNI_CIO_V10_GITHUB_PRO_AND_MIGRATION_IMPLEMENTATION_AMENDMENT.md` — GitHub Pro, migration/parity and WP implementation discipline;
- `OMNI_CIO_V10_AUTONOMOUS_PORTFOLIO_GOVERNANCE_AND_COMMERCIAL_MODEL_AMENDMENT.md` — portfolio-governance/commercial/legal direction;
- `OMNI_CIO_V10_IDENTITY_MULTI_TENANT_ACCOUNT_AND_AUTHENTICATION_AMENDMENT.md` — identity/tenant/authentication direction;
- `OMNI_CIO_V10_PHONE_ONLY_ENGINEERING_AND_HEADLESS_NODE_OPERATIONS_AMENDMENT.md` — browser-only OWNER/headless Personal-Node operating model;
- `OMNI_CIO_V10_ENGINEERING_QUALITY_AND_GREEN_MERGE_AMENDMENT.md` — accepted Pre-CI/all-green/failure-learning/OWNER-handoff discipline;
- `../architecture/V10_AI_CORTEX_CONTRACT.json` and other machine-readable companions — executable/validated policy where defined;
- `OMNI_CIO_V10_ACCOUNT_INDEPENDENCE_AMENDMENT.md` — historical owner-approved amendment already consolidated into the base plan and retained for provenance.

Current V10 progress authority:

`../../knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

Do **not** hard-code or infer the current WP/progress from historical PR text, a dated amendment, a package execution contract or this index. The status file on accepted `main` is the current-state authority.

The synchronized Master Plan Markdown/PDF pair must not be edited independently. New OWNER-approved implementation detail may be recorded by focused amendment; a later intentional consolidation must regenerate/review the synchronized pair and its integrity manifest together.

## V10 delivery sequence and lifecycle

The canonical sequence remains defined by `OMNI_CIO_V10_MASTER_PLAN.md`. Each implementation package uses `OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md` and advances only after its Exit Gate.

Historical package files may correctly say that an earlier WP was `CURRENT`, `PENDING` or `NEXT` at the time they were written. That wording is package evidence, not a live queue. Current authorization is always read from `../../knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

The presence of accepted `apps/api/`, `apps/web/` and Personal-Node infrastructure in the repository reflects already accepted owning WPs; it does not unlock Telegram, AI, public multi-user, billing or Real-execution WPs early.

## Concrete V10 product lock

The accepted concrete amendments clarify implementation without changing block weights/order:

- Deterministic Core owns financial/accounting truth;
- V10 accounting target uses verified broker HTML reports; no photo/screenshot/OCR portfolio workflow;
- MOEX is current-market enrichment and stays distinct from broker period-end facts;
- local-first Omni-CIO Cortex baseline is Qwen3.5-4B via Ollama behind a replaceable provider;
- paid AI/search/hosted-agent SaaS is not required for V10 Definition of Done;
- System Policy + typed tools + RAG + evals precede QLoRA;
- 24/7 autonomy is event-driven/checkpointed;
- SearXNG-first research + bounded HTTP/Playwright retrieval + Evidence Store;
- AI has no direct broker-write/admin/GitHub-bypass/Real-money authority;
- OWNER local participation is minimized to genuinely non-delegable actions;
- CI is verifier rather than primary debugger, and every applicable exact-head merge gate must conclude SUCCESS;
- current V10 Web/API runtime remains on the approved Personal Node; external access providers are access/security transport rather than private-state application hosts.

Read the accepted amendments themselves for exact requirements and block-by-block elaboration.

## Omni-CIO v9 Portfolio Autopilot — completed protected runtime program

The accepted applied runtime is **Omni-CIO v9.0.0**.

Canonical completed program:

`OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`.

V9 WP0–WP15 repository delivery and owner external acceptance are complete. Current runtime mode remains **controlled maintenance** while V10 is developed. Protected v8.6.1 remains a recovery rollback baseline.

Current V9 applied/runtime status:

`../../knowledge/16_CURRENT_PROGRAM_STATUS.md`.

V9 remains the protected production/recovery baseline until a responsible later V10 WP explicitly replaces a boundary and passes its Exit Gate.

## Source-of-truth hierarchy

For current V10 development:

1. accepted `main`;
2. `../../AGENTS.md`;
3. `OMNI_CIO_V10_PROGRAM_LOCK.md`;
4. synchronized `OMNI_CIO_V10_MASTER_PLAN.md` + PDF + SHA manifest;
5. `OMNI_CIO_V10_AMENDMENTS_INDEX.md` + accepted active amendments;
6. machine-readable contracts;
7. `../../knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` for dynamic progress/current-next WP;
8. accepted V10 architecture/ADR/current-WP contracts;
9. exact-head PR/CI/runtime evidence;
10. historical records as historical evidence only.

## Permanent safety boundaries

V10 development does not silently remove V9 safety boundaries:

- production read-only credential remains isolated;
- Sandbox remains virtual and separately credentialed;
- Real execution remains exact-owner-confirmed, immutable, idempotent, fail-closed and broker-reconciled;
- AI has no direct broker-write authority;
- GitHub engineering access is never trading authorization;
- current `app:app` / GPT recovery behavior stays protected until an accepted V10 migration replaces it;
- no competing GPT/Gateway/Web/Telegram/AI/execution source of truth.

## Further-change rule

V10 work proceeds one current WP at a time through focused branch/PR, root-cause/blast-radius preflight, all applicable exact-head SUCCESS gates, zero blocking review threads, squash merge and required post-merge verification. New material scope is accepted only through the amendment process. V11/competing programs remain prohibited until V10 final acceptance.