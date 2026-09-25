# Стартовый запрос для нового рабочего чата Omni-CIO

> **CURRENT AMENDMENT-21 TIMEWEB DELIVERY OVERRIDE (2026-09-24):** target active service model is **ChatGPT + GitHub + Timeweb Cloud + Telegram Login**. Current next System Update is **TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED**. Cloudflare, Neon, Render, Cloud.ru and VK ID are retirement targets and receive no new feature authority. Historical references remain evidence only. Timeweb cutover/decommission must preserve exact-SHA, tenant/RLS, security and recovery gates. WEB-VISUAL and WP23+ remain paused during this consolidation.


Использовать, когда нужно продолжить разработку/обслуживание проекта в новом чате после подключения GitHub.

Этот prompt намеренно **не хранит собственный V10 percentage/NEXT authority**. Dynamic progress/current-next execution unit всегда читается из `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` на accepted `main`. Documentation lifecycle: `docs/DOCUMENTATION_AUTHORITY_AND_LIFECYCLE.md`.

```text
Подключись к GitHub-репозиторию MishaGameHacking/omni-cio-gateway.

Сначала прочитай и соблюдай authority order из AGENTS.md. Минимально обязательно прочитай:
1. AGENTS.md
2. README.md
3. docs/DOCUMENTATION_AUTHORITY_AND_LIFECYCLE.md
4. knowledge/00_PROJECT_MASTER_CONTEXT.md
5. knowledge/16_CURRENT_PROGRAM_STATUS.md — protected V9 runtime baseline only
6. docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md
7. docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md
8. docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md и все active amendments, особенно Amendment 18 Timeweb-Only Platform Consolidation & Telegram-Only Login Authority, Amendment 20 V9-to-V10 Convergence, Amendment 21 Timeweb Full Production Delivery, Product User / Engineering Authority, Public Free Multi-User Hosted Runtime, WP22A Technical Closeout, Integrated System Update Execution Law и Green Checkpoint & Targeted CI Repair Law
9. docs/architecture/V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_CONTRACT.json
10. docs/architecture/V10_GREEN_CHECKPOINT_TARGETED_CI_REPAIR_CONTRACT.json and docs/operations/V10_GREEN_CHECKPOINT_CI_RUNBOOK.md when Amendment 16 is accepted
11. docs/architecture/V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_CONTRACT.json
12. docs/architecture/V10_RU_PUBLIC_REGISTRATION_INGRESS_CONTRACT.json
13. docs/architecture/V10_RU_POSTGRES_TIMEWEB_CONTROL_PLANE_CONTRACT.json
14. docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md
15. knowledge/17_V10_CURRENT_PROGRAM_STATUS.md — единственный current V10 WP/progress/execution authority
16. профильные architecture/domain/runbook/contracts/Execution Ledger по текущей задаче
17. Historical Cloudflare/Neon/Render/VK contracts/amendments — только если текущая задача требует recovery, compatibility или provenance review; не использовать их как current implementation templates
18. gpt/SETUP_INDEX.md и связанные GPT recovery files только если задача затрагивает current Custom GPT/V9 recovery

Затем проверь:
- exact main SHA;
- open Pull Requests/Issues;
- applicable exact-head CI/security и post-merge Regression Shield;
- authorized current execution unit только из current status;
- любой in-flight/unmerged PR не считать accepted authority.

Current target after Amendment 18 acceptance:
- active service model = ChatGPT + GitHub + Timeweb Cloud + Telegram Login;
- GitHub = engineering/source/review/CI/exact-SHA provenance authority;
- Timeweb Cloud = selected application/runtime/PostgreSQL/domain/DNS/TLS/network/backup/monitoring platform;
- Telegram Login = only human product login provider;
- current System Update = `TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED`;
- initial TW-A branch `system/timeweb-platform-consolidation` is merged via PR #583; current TW-B continuation branch = `system/timeweb-platform-consolidation-tw-b`;
- milestones = TW-A inventory/authority -> TW-B source/runtime -> TW-C Timeweb candidate -> TW-D PostgreSQL cutover -> TW-E DNS/no-VPN ingress -> TW-F Telegram public activation -> TW-G external-provider decommission;
- Cloudflare, Neon, Render, Cloud.ru and VK ID are historical/retirement targets, not new feature authority;
- Amendments 20 and 21 govern the single PR #584 integrated delivery: migrate useful V9 semantics, prove parity/zero current consumers/recovery, retire obsolete provider authority, and implement the fail-closed Timeweb production-delivery chain;
- current branch checkpoint = `V9C-F / WHOLE_TREE_LEGACY_ABSENCE_PROOF`; V9C-D is branch-local `CERTIFIED_GREEN` on exact head `80fec000845f93929e204144ce6d4b22db29bcc0`; V9C-E/V9C-F implementation is verification-pending on the replacement head and P2 must not start before GREEN;
- historical files may be touched only when a compatibility/governance check must acknowledge the new current authority;
- retired provider resources/secrets/workflow actions are disabled/revoked only after replacement/cutover/recovery evidence;
- GitHub-native checks are the active quality/security authority; external CI/review SaaS is historical and must not be required by current/future workflows;
- WEB-VISUAL and WP23+ remain paused/locked during consolidation;
- public multi-user remains disabled until Timeweb + Telegram + privacy/legal/capacity gates pass;
- broker write / Real execution remain disabled.

Mandatory current-provider rule:
- do not introduce new Cloudflare/Neon/Render/Cloud.ru/VK dependencies;
- do not use legacy provider docs as implementation templates;
- do not delete historical repository files merely to simplify searches;
- keep product core provider-neutral;
- Timeweb deployment must use an accepted GitHub exact SHA;
- Telegram identity never selects tenant or infrastructure authority.

Integrated System Update Execution Law:
- every material change is FOCUSED_CHANGE or INTEGRATED_SYSTEM_UPDATE;
- FOCUSED_CHANGE = isolated defect/governance/maintenance/mandatory split;
- INTEGRATED_SYSTEM_UPDATE = one coherent OWNER-authorized outcome with ordered member WP/increments;
- integrated update uses one branch and one final PR by default; member milestones are branch-local and sequential;
- accepted progress changes only after complete squash merge + exact-main post-merge acceptance;
- integrated work requires branch Execution Ledger + GitHub dashboard marked BRANCH-LOCAL EXECUTION STATE — NOT ACCEPTED MAIN AUTHORITY;
- `INTEGRATION_READY` remains the final whole-update readiness state before final landing review, not a ban on earlier checkpoint certification;
- mandatory split triggers remain migration ordering, security/authority transition, dependency/toolchain boundary, OWNER/provider action, live/temporal evidence, production cutover, Real-money authority and reviewability limit.

Green Checkpoint & Targeted CI Repair Law / Amendment 16:
- canonical flow: WRITE -> focused preflight -> CHECKPOINT SHA -> GitHub-native CI/security + independent review -> CERTIFIED_GREEN -> NEXT CHECKPOINT;
- do not start the next functional checkpoint or dependent milestone until the current checkpoint is CERTIFIED_GREEN;
- any applicable RED or material review finding immediately moves the branch to RED_REPAIR_ONLY and stops unrelated feature work;
- begin root-cause/blast-radius diagnosis as soon as useful RED evidence exists; do not wait for all independent jobs merely to begin repair;
- still inspect relevant findings that arrive from other jobs before finalizing the corrected checkpoint;
- unchanged source/config + proved transient/infrastructure-only failure -> prefer rerun of only the specific failed job on the same SHA;
- repeated identical transient failure is a workflow/infrastructure defect, not a reason to retry until lucky GREEN;
- any source/config/test/governance change requires a replacement SHA and invalidates prior final evidence;
- targeted proof answers whether the reported defect is fixed; full applicable certification of the replacement exact SHA is still required before new functional work;
- GitHub-native lint/type/test/coverage/dependency/SAST/secret/security checks PASS when applicable; unresolved material correctness/security/maintainability findings are not GREEN;
- inspect GitHub-native SAST/security/dependency/secret checks, check annotations and review threads; bot approval is supporting evidence only;
- safety abort overrides diagnostic completeness for secrets/private data, broker/Real reachability, destructive migration/provider mutation, uncontrolled spend or cross-tenant risk;
- only success is GREEN for an applicable Omni-CIO project gate; failure/cancelled/queued/pending/in_progress/timed_out/action_required/stale/neutral/skipped are not GREEN;
- post-merge applicable RED on current main = MAIN_RED_STOP; pause ordinary feature work and repair via focused branch;
- protected main is never amended or force-rewritten.

Engineering invariants:
- one canonical repo/Core/product line; no duplicate stacks;
- never develop directly in main;
- restore accepted main/current authority before substantive work;
- root cause/blast radius before material fix;
- focused preflight before publishing each checkpoint;
- CI is independent verifier and active checkpoint certifier, not a substitute for engineering judgment;
- every applicable exact-head check must really run and conclude success under project policy;
- full diff + zero blockers + squash merge;
- DRAFT→READY with unchanged SHA does not automatically invalidate certification unless an applicable state-dependent workflow/ruleset requires a fresh run;
- any content-changing commit invalidates previous final exact-head evidence;
- exact new main + required post-merge Regression Shield before status/acceptance;
- OWNER product acceptance only after merge/post-merge GREEN except genuine non-delegable prerequisite;
- do not weaken tests/security/Regression Shield;
- later major System Updates remain locked until current integrated acceptance;
- V10 is migration/productization; prefer REUSE_AS_IS > WRAP_ADAPTER > EXTRACT_TO_CORE > REWRITE_REQUIRED > RETIRE.

Broker/money invariants:
- tenant-scoped READ/optional TRADE credentials;
- same-tenant VERIFIED_READ_ACCOUNTS ∩ VERIFIED_TRADE_ACCOUNTS for execution eligibility;
- immutable plan + authenticated USER confirmation for own tenant + preflight + idempotency/reconciliation;
- no AI broker-write authority;
- no withdrawal/transfer/margin/leverage/uncovered-short/autonomous recurring Real execution.

Before changes, briefly report exact main, current execution unit, relevant PR/issues, required CI/protection, canonical files read, exact current scope/non-goals, and historical records used only as evidence.
```

Для настройки самого существующего Custom GPT использовать `gpt/SETUP_INDEX.md` как главный recovery/setup источник.
