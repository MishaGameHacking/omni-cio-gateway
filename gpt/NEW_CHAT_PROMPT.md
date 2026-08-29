# Стартовый запрос для нового рабочего чата Omni-CIO

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
8. docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md и все active amendments, особенно Product User / Engineering Authority, Public Free Multi-User Hosted Runtime, WP22A Technical Closeout, Integrated System Update Execution Law, Cloudflare Platform Authority и Cloudflare Public Product Integrated Delivery
9. docs/architecture/V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_CONTRACT.json
10. docs/architecture/V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_CONTRACT.json
11. docs/architecture/V10_CLOUDFLARE_PLATFORM_AUTHORITY_CONTRACT.json
12. docs/architecture/V10_CLOUDFLARE_PUBLIC_PRODUCT_INTEGRATED_CONTRACT.json when accepted
13. docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md
14. knowledge/17_V10_CURRENT_PROGRAM_STATUS.md — единственный current V10 WP/progress/execution authority
15. профильные architecture/domain/runbook/contracts/Execution Ledger по текущей задаче
16. gpt/SETUP_INDEX.md и связанные GPT recovery files только если задача затрагивает current Custom GPT/V9 recovery

Затем проверь:
- exact main SHA;
- open Pull Requests/Issues;
- required exact-head CI/security и post-merge Regression Shield;
- authorized current execution unit только из current status;
- любой in-flight/unmerged PR не считать accepted authority.

Current target after Amendments 14/15 are accepted:
- один public modern multi-user Omni-CIO Web product для обычных Internet-connected phone/desktop browsers;
- GitHub = engineering/source/review/provenance authority rank 1;
- Cloudflare Workers Paid = selected new-V10 application/edge/build platform rank 2;
- current Cloudflare implementation update = `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED` on default branch `system/cloudflare-public-product`;
- ordered internal milestones = `CF-A / CLOUDFLARE-BUILDS-VERIFIER-INTEGRATION -> CF-B / CLOUDFLARE-RUNTIME-COMPATIBILITY -> CF-C / CLOUDFLARE-CANDIDATE-DEPLOYMENT -> CF-D / CLOUDFLARE-PUBLIC-CUTOVER`;
- one final PR is default, but each milestone must pass its branch-local Exit Gate before dependent work;
- separate main merge between CF-A…CF-D is not required after Amendment 15 acceptance; a real mandatory split trigger still forces stop/split;
- final production НЕ зависит от PROJECT OWNER home IP, Wi-Fi/router/LAN, home Internet/power или Lenovo;
- Lenovo = engineering/self-hosted CI/controlled acceptance/recovery/rollback, не public production origin;
- Cloud.ru Evolution is no longer selected for new V10;
- Render is retired from active new-V10 deployment/attestation/release-alignment; historical WP22A Render/Neon evidence and protected V9 Render `app:app` remain preserved;
- Cloudflare-first services are used only when semantically equivalent and justified; existing React/Vite targets Workers Static Assets, Python Workers require compatibility proof, Containers may be used for a proven full-Linux/native runtime need, and PostgreSQL/Neon 18/RLS remains until an explicit equivalent migration is proved;
- D1 is not automatic financial/tenant truth replacement and Hyperdrive PG18 is not assumed compatible;
- PROJECT OWNER не special product role; OWNER использует тот же OmniCIOUserAccount -> Tenant -> Session path, что и любой USER;
- Telegram Login/VK ID = product auth; GitHub/cloud-provider/Windows = engineering authority;
- public multi-user = approved target, но `PUBLIC_MULTI_USER_ENABLED=false` до CF-D + required capability gates;
- initial USER access fully free: BILLING_ENABLED=false, TRIAL_ENABLED=false, SUBSCRIPTION_ENFORCEMENT=false, PREMIUM_FEATURE_GATING=false; future monetization DEFERRED_OPTIONAL;
- each USER owns only tenant-scoped BrokerConnection READ/optional TRADE credentials; no global/shared user broker token;
- raw credentials never return to browser storage and never enter GitHub/CI/artifacts;
- T-Invest public connector remains separate fail-closed broker-terms gate;
- `app:app` protected V9 baseline, `trading_methods=false`, `REAL_TRADING_ENABLED=false`, no transfer/withdrawal/margin/leverage/uncovered-short remain preserved.

WEB VISUAL lock:
- `WEB-VISUAL-INTEGRATED` remains prepared and separate from the Cloudflare public-product update;
- do not create or implement its visual-refresh source until the exact OWNER command `START V10 WEB VISUAL SYSTEM UPDATE` exists.

Integrated System Update Execution Law:
- every material change is FOCUSED_CHANGE or INTEGRATED_SYSTEM_UPDATE;
- FOCUSED_CHANGE = isolated defect/governance/maintenance/mandatory split;
- INTEGRATED_SYSTEM_UPDATE = one coherent OWNER-authorized outcome with ordered member WP/increments;
- integrated update uses one branch and one final PR by default; member milestones are branch-local and sequential;
- accepted progress changes only after complete squash merge + exact-main post-merge acceptance;
- integrated work requires branch Execution Ledger + GitHub dashboard marked BRANCH-LOCAL EXECUTION STATE — NOT ACCEPTED MAIN AUTHORITY;
- do not publish final implementation for external verification before INTEGRATION_READY;
- mandatory split triggers remain migration ordering, security/authority transition, dependency/toolchain boundary, OWNER/provider action, live/temporal evidence, production cutover, Real-money authority and reviewability limit.

HEAD FREEZE:
- after publishing a verification SHA, do not immediately push the first symptom fix;
- where safe, let independent applicable checks reach terminal state;
- collect Actions/Windows/Sonar/Gitar/SAST/browser/owning-gate findings into one inventory;
- Quality Gate success is insufficient if Sonar still has new issues, annotations or security hotspots; inspect and disposition each finding;
- group by root cause/defect class, inspect blast radius/analogous patterns/coupled surfaces/adjacent failure modes;
- add permanent guards and publish one coherent correction batch only after focused/local preflight;
- safety abort overrides diagnostic completeness for secrets/private data, broker/Real reachability, destructive migration/provider mutation, uncontrolled spend or cross-tenant risk;
- new commits invalidate previous final exact-head evidence;
- continue-on-error must not create fake GREEN.

Engineering invariants:
- one canonical repo/Core/product line; no duplicate stacks;
- never develop directly in main;
- restore accepted main/current authority before substantive work;
- root cause/blast radius before material fix;
- cheap/focused preflight before expensive CI;
- every applicable exact-head check must really run and conclude success; RED/skipped/queued/pending/neutral is not GREEN;
- full diff + zero blockers + squash merge;
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