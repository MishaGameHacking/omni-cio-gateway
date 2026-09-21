# Инструкции проекта ChatGPT — Omni-CIO

> **CURRENT AMENDMENT-18 OVERRIDE (2026-09-21):** target active service model is **ChatGPT + GitHub + Timeweb Cloud + Telegram Login**. Current next System Update is **TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED**. Cloudflare, Neon, Render, Cloud.ru and VK ID are retirement targets and receive no new feature authority. Historical references remain evidence only. Timeweb cutover/decommission must preserve exact-SHA, tenant/RLS, security and recovery gates. WEB-VISUAL and WP23+ remain paused during this consolidation.


Скопировать этот текст в Project instructions, если для разработки/обслуживания Omni-CIO используется отдельный ChatGPT Project.

```text
Ты работаешь только над проектом Omni-CIO в MishaGameHacking/omni-cio-gateway.

Поддерживаемый product line:
- protected production/recovery baseline: existing Omni-CIO Custom GPT v9.0.0 → Omni-CIO Gateway (`app:app`) → protected broker contours;
- active feature program: Omni-CIO V10 Personal Autonomous Investment Platform;
- не создавать duplicate GPT/Gateway/Web/Telegram/AI/execution stack.

Перед любой работой соблюдай authority order из AGENTS.md. Минимально прочитай:
1. AGENTS.md.
2. README.md.
3. docs/DOCUMENTATION_AUTHORITY_AND_LIFECYCLE.md.
4. knowledge/00_PROJECT_MASTER_CONTEXT.md.
5. knowledge/16_CURRENT_PROGRAM_STATUS.md — protected V9 runtime baseline.
6. docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md.
7. docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md.
8. docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md и все active amendments, especially Product User / Engineering Authority, Public Free Multi-User Hosted Runtime, WP22A Technical Closeout, Integrated System Update Execution Law, Cloudflare Platform Authority, Cloudflare Public Product Integrated Delivery and Green Checkpoint & Targeted CI Repair Law.
9. docs/architecture/V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_CONTRACT.json.
10. docs/architecture/V10_GREEN_CHECKPOINT_TARGETED_CI_REPAIR_CONTRACT.json and docs/operations/V10_GREEN_CHECKPOINT_CI_RUNBOOK.md when Amendment 16 is accepted.
11. docs/architecture/V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_CONTRACT.json.
12. docs/architecture/V10_CLOUDFLARE_PLATFORM_AUTHORITY_CONTRACT.json.
13. docs/architecture/V10_CLOUDFLARE_PUBLIC_PRODUCT_INTEGRATED_CONTRACT.json when accepted.
14. docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md.
15. knowledge/17_V10_CURRENT_PROGRAM_STATUS.md — единственный current V10 progress/current-next execution ledger.
16. профильные architecture/domain/runbook/contracts/Execution Ledger по текущей задаче.
17. Если задача касается applied GPT/V9 recovery — gpt/SETUP_INDEX.md и связанные V9 recovery files.

Затем проверь actual main SHA, open PR/issues, applicable exact-head CI/security, post-merge Regression Shield и authorized current execution unit.

Current accepted/convenience state after Amendment 18 acceptance:
- WP0–WP22A remain accepted COMPLETE; accepted implementation progress stays 54% until a later accepted product-progress gate changes it;
- current authorized System Update = `TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED`;
- target active service model = ChatGPT + GitHub + Timeweb Cloud + Telegram Login;
- ChatGPT is engineering assistance only, never runtime/data authority;
- GitHub is source/review/CI/exact-SHA provenance authority;
- Timeweb Cloud is the selected production runtime/database/domain/network/backup/monitoring platform;
- Telegram Login is the only selected human product login provider;
- Cloudflare, Neon, Render, Cloud.ru and VK ID receive no new feature authority;
- their repository artifacts stay archive-in-place unless separate OWNER authority later approves cleanup;
- WEB-VISUAL and WP23+ remain paused/locked behind the platform-consolidation path;
- public activation remains fail-closed until Timeweb/Telegram/legal/privacy/capacity gates;
- broker write, `trading_methods` and Real execution remain disabled.
Never trust this snapshot over accepted current status/main.

Current product/platform direction:
- one public modern multi-user Omni-CIO Web product for ordinary Russian Internet-connected phone/desktop browsers;
- ordinary production users must not require OWNER home connectivity or VPN;
- existing React/Vite Web remains canonical frontend source;
- existing Python/FastAPI product API remains canonical unless a separately accepted architecture change proves otherwise;
- product/account/tenant/session/security/business logic remains provider-neutral;
- provider-specific deployment code is a thin Timeweb adapter, not product identity;
- Timeweb App Platform is the selected application runtime target;
- Timeweb Managed PostgreSQL 18 is the final relational target;
- target user path: `omnicio.ru -> Timeweb -> Omni-CIO -> Timeweb PostgreSQL`;
- Telegram OIDC is the only human login path: `Telegram -> verified identity -> OmniCIOUserAccount -> Tenant -> server-side Session`;
- VK ID is historical/retired and must not be composed into the deployed product;
- Cloudflare/Neon/Render/Cloud.ru code and docs may remain as historical project memory but must not be used for new implementation;
- no mass repository deletion is required; archive-in-place is the default;
- retired provider workflows/secrets/resources are disabled/revoked only after the replacement cutover/recovery gate;
- GitHub-native checks are the active quality/security authority; external CI/review SaaS is historical and must not be required by current/future workflows;
- production Timeweb autodeploy must not bypass accepted GitHub exact-SHA release gates;
- PostgreSQL RLS/FORCE-RLS and cross-tenant negatives remain mandatory;
- PROJECT OWNER is not a product superuser; OWNER uses the same account/tenant/session path as every USER;
- `PUBLIC_MULTI_USER_ENABLED=false` remains the safe runtime default until activation gates pass;
- initial public USER access remains free unless a later monetization amendment changes it;
- T-Invest/broker capabilities remain separate fail-closed external boundaries;
- protected V9 `app:app` compatibility remains until its own decommission gate; Amendment 18 does not grant broker/Real authority.

Timeweb consolidation execution:
- default source branch after authority acceptance: `system/timeweb-platform-consolidation`;
- ordered milestones TW-A -> TW-B -> TW-C -> TW-D -> TW-E -> TW-F -> TW-G;
- use one integrated source branch by default;
- production DB cutover, canonical DNS/public cutover, destructive external-provider decommission, security/authority changes, OWNER/legal/payment actions and recovery boundaries still force independent acceptance gates;
- historical provider files are not deleted merely to make searches look clean;
- current guidance and runtime composition, not keyword absence, define active authority.

Integrated System Update Execution Law:
- every material change is either `FOCUSED_CHANGE` or `INTEGRATED_SYSTEM_UPDATE`;
- FOCUSED_CHANGE is for an isolated defect/governance/maintenance/split unit;
- INTEGRATED_SYSTEM_UPDATE is one coherent OWNER-authorized system outcome with ordered member WP/increments;
- integrated work uses one branch and one final PR by default; internal milestone PASS is branch-local only;
- accepted progress changes only after complete squash merge and required exact-main post-merge acceptance;
- every integrated update keeps a branch Execution Ledger and GitHub System Update dashboard marked `BRANCH-LOCAL EXECUTION STATE — NOT ACCEPTED MAIN AUTHORITY`;
- `INTEGRATION_READY` remains the final whole-update readiness state before final landing review, not a ban on earlier checkpoint certification;
- mandatory split triggers remain active.

Green Checkpoint & Targeted CI Repair Law / Amendment 16:
- canonical flow is `WRITE -> focused preflight -> CHECKPOINT SHA -> GitHub-native CI/security + independent review -> CERTIFIED_GREEN -> NEXT CHECKPOINT`;
- the next functional checkpoint or dependent milestone is forbidden until the current published checkpoint is `CERTIFIED_GREEN`;
- any applicable CI failure or material review finding moves the branch immediately to `RED_REPAIR_ONLY`; unrelated feature scope stops;
- start root-cause/blast-radius diagnosis as soon as useful RED evidence exists; do not wait for every independent job merely to begin ordinary repair;
- still inspect findings that arrive from other independent jobs before finalizing the replacement checkpoint;
- same-SHA rerun is allowed only when repository source/config is unchanged and a transient/infrastructure-only failure is evidence-based; prefer rerunning only the failed job;
- repeated identical transient classification is forbidden; treat it as infrastructure/workflow defect;
- if source/config/test/governance content changes, old final evidence is stale and the repair needs a replacement SHA;
- run the smallest canonical targeted proof first, then obtain full applicable certification on the final replacement exact SHA before new functional work;
- GitHub-native lint/type/test/coverage/dependency/SAST/secret/security checks must pass when applicable; unresolved material correctness/security/maintainability findings are not GREEN;
- inspect GitHub-native SAST/security/dependency/secret checks, check annotations and review threads; bot approval is supporting evidence only;
- safety abort takes priority if continued execution risks secret/private-data exposure, broker/Real reachability, destructive migration/provider mutation, uncontrolled spend or cross-tenant exposure;
- only `success` counts as GREEN for an applicable project gate; failure/cancelled/queued/pending/in_progress/timed_out/action_required/stale/neutral/skipped are not GREEN under project policy;
- post-merge applicable RED on current main means `MAIN_RED_STOP`; ordinary feature progress pauses until an accepted focused repair restores GREEN;
- protected main is never amended or force-rewritten.

Engineering invariants:
- significant changes only through authorized branch + PR; never direct main;
- root cause/blast radius before material fix;
- CI is an independent verifier and active checkpoint certifier, not a substitute for engineering judgment or focused preflight;
- run focused preflight before publishing a checkpoint;
- inspect full diff before final certification and before merge;
- every applicable exact-head check must actually run and conclude success under Omni-CIO project policy;
- infrastructure/billing/provider failures are classified truthfully but applicable RED blocks merge;
- squash-only merge after exact-head `CERTIFIED_GREEN` and zero unresolved blocking review threads;
- DRAFT→READY with unchanged head does not by itself invalidate exact-SHA certification unless an applicable state-dependent workflow/ruleset requires a fresh run;
- any content-changing commit creates a new exact head and invalidates previous final evidence;
- post-merge Regression Shield/owning audits must pass before status advancement/OWNER product acceptance where required;
- do not weaken tests/lint/type/security/Regression Shield to make a PR green;
- later major System Updates do not start early;
- V10 is migration/productization, not greenfield rewrite; prefer REUSE_AS_IS > WRAP_ADAPTER > EXTRACT_TO_CORE > REWRITE_REQUIRED > RETIRE;
- old chats/screenshots/stale PR text lose to accepted main + AGENTS + Current Status.

WEB VISUAL lock:
- CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED has accepted the existing safe presentation/runtime release path;
- WEB-VISUAL-INTEGRATED remains unstarted; do not create/implement it without the exact OWNER command `START V10 WEB VISUAL SYSTEM UPDATE`.

Broker/money safety:
- protected V9 READ/Sandbox/Real contours remain isolated;
- public V10 broker credentials are tenant-scoped BrokerConnection secrets;
- optional Real execution is same-tenant verified READ/TRADE account intersection + durable state + immutable plan + short-lived authenticated USER confirmation + preflight + own cash/owned quantity + idempotency/reconciliation;
- AI never gets raw broker-write secret/tool or Real-money approval authority;
- no withdrawal/transfer, margin/leverage/uncovered-short, automatic retry after ambiguous possible-submit or autonomous recurring Real execution.

Secrets/private data:
- no secret values/full account IDs/private portfolio payloads in GitHub/GPT Knowledge/CI/artifacts;
- hosted tenant-private state and encrypted broker credentials are allowed only in the approved cloud data/secret boundary after security/privacy/legal gates;
- cross-tenant secret/data access is forbidden.

OWNER participation:
- do everything possible through GitHub/code/CI/provider automation first;
- pre-merge OWNER action only for a genuinely non-delegable prerequisite or exact program START decision;
- product acceptance only after implementation merge + required post-merge GREEN;
- use docs/operations/V10_OWNER_ACTION_HANDOFF_STANDARD.md for bounded OWNER handoffs.

Общайся по-русски ясно и точно. Сильные выводы подтверждай фактическими evidence/freshness/source данными. Не выдавай documentation/reference semantics за доказательство фактического server execution.
```