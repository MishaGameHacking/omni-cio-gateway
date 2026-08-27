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
8. docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md и все active amendments, особенно Product User / Engineering Authority, Public Free Multi-User Hosted Runtime, WP22A Technical Closeout и Integrated System Update Execution Law
9. docs/architecture/V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_CONTRACT.json
10. docs/architecture/V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_CONTRACT.json
11. docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md
12. knowledge/17_V10_CURRENT_PROGRAM_STATUS.md — единственный current V10 WP/progress/execution authority
13. профильные architecture/domain/runbook/contracts/Execution Ledger по текущей задаче
14. gpt/SETUP_INDEX.md и связанные GPT recovery files только если задача затрагивает current Custom GPT/V9 recovery

Затем проверь:
- exact main SHA;
- open Pull Requests/Issues;
- required exact-head CI/security и post-merge Regression Shield;
- authorized current execution unit только из current status;
- любой in-flight/unmerged PR не считать accepted authority.

Если accepted current status показывает Amendment-12 post-acceptance состояние, ожидай:
- WP0–WP22A COMPLETE;
- accepted progress 54%;
- PRODUCT IMPLEMENTATION PAUSED;
- next prepared update WEB-VISUAL-INTEGRATED with ordered WEB-VISUAL-A -> B -> C -> D -> E -> F -> G milestones;
- OWNER START REQUIRED before product work, exact command `START V10 WEB VISUAL SYSTEM UPDATE`;
- WP23+, public production activation, broker write and Real execution locked.
Но не доверяй этому snapshot без проверки accepted current status/main.

Current target:
- один public modern multi-user Omni-CIO Web product для обычных Internet-connected phone/desktop browsers;
- final production НЕ зависит от PROJECT OWNER home IP, Wi-Fi/router/LAN, home Internet/power или Lenovo;
- Lenovo = engineering/self-hosted CI/controlled acceptance/recovery/rollback, не public production origin;
- final public Web/API/private state = approved managed-cloud production architecture selected by owning gate; Cloud.ru Evolution remains the selected final provider until accepted authority changes it;
- PROJECT OWNER не special product role; OWNER использует тот же OmniCIOUserAccount -> Tenant -> Session path, что и любой USER;
- Telegram Login/VK ID = product auth; GitHub/cloud-provider/Windows = engineering authority;
- public multi-user = approved target, но PUBLIC_MULTI_USER_ENABLED=false до required gates;
- initial USER access fully free: BILLING_ENABLED=false, TRIAL_ENABLED=false, SUBSCRIPTION_ENFORCEMENT=false, PREMIUM_FEATURE_GATING=false; future monetization DEFERRED_OPTIONAL;
- each USER owns only tenant-scoped BrokerConnection READ/optional TRADE credentials; no global/shared user broker token;
- raw credentials never return to browser storage and never enter GitHub/CI/artifacts;
- T-Invest public connector remains separate fail-closed broker-terms gate;
- app:app protected V9 baseline, trading_methods=false, REAL_TRADING_ENABLED=false, no transfer/withdrawal/margin/leverage/uncovered-short remain preserved.

Integrated System Update Execution Law:
- every material change is FOCUSED_CHANGE or INTEGRATED_SYSTEM_UPDATE;
- FOCUSED_CHANGE = isolated defect/governance/maintenance/mandatory split;
- INTEGRATED_SYSTEM_UPDATE = one coherent OWNER-authorized outcome with ordered member WP/increments;
- integrated update uses one branch and one final PR by default; member milestones are branch-local and sequential;
- accepted progress changes only after complete squash merge + exact-main post-merge acceptance;
- integrated work requires branch Execution Ledger + GitHub dashboard marked BRANCH-LOCAL EXECUTION STATE — NOT ACCEPTED MAIN AUTHORITY;
- do not publish implementation for external verification before INTEGRATION_READY;
- mandatory split triggers: migration ordering, security/authority transition, dependency/toolchain boundary, OWNER/provider action, live/temporal evidence, production cutover, Real-money authority, reviewability limit.

HEAD FREEZE:
- after publishing a verification SHA, do not immediately push the first symptom fix;
- where safe, let independent applicable checks reach terminal state;
- collect Actions/Windows/Sonar/Gitar/SAST/browser/owning-gate findings into one inventory;
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
