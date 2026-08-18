# Стартовый запрос для нового рабочего чата Omni-CIO

Использовать, когда нужно продолжить разработку/обслуживание проекта в новом чате после подключения GitHub.

Этот prompt намеренно **не хранит собственный V10 percentage/NEXT**. Dynamic progress/current-next WP всегда читается из `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` на accepted `main`. Documentation lifecycle: `docs/DOCUMENTATION_AUTHORITY_AND_LIFECYCLE.md`.

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
8. docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md и все active amendments, особенно Product User / Engineering Authority и Public Free Multi-User Hosted Runtime
9. docs/architecture/V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_CONTRACT.json
10. docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md
11. knowledge/17_V10_CURRENT_PROGRAM_STATUS.md — единственный current V10 WP/progress authority
12. профильные architecture/domain/runbook/contracts по текущей задаче
13. gpt/SETUP_INDEX.md и связанные GPT recovery files только если задача затрагивает current Custom GPT/V9 recovery

Затем проверь:
- exact main SHA;
- open Pull Requests/Issues;
- required exact-head CI/security и post-merge Regression Shield;
- authorized current WP только из current status;
- любой in-flight/unmerged PR не считать accepted authority.

Current target:
- один public modern multi-user Omni-CIO Web product для обычных Internet-connected phone/desktop browsers;
- final production НЕ зависит от PROJECT OWNER home IP, Wi-Fi/router/LAN, home Internet/power или Lenovo;
- Lenovo = engineering/self-hosted CI/controlled acceptance/recovery/rollback, не public production origin;
- final public Web/API/private state = approved managed-cloud production architecture selected by owning WP22A service/security/recovery gate;
- PROJECT OWNER не special product role; OWNER использует тот же OmniCIOUserAccount -> Tenant -> Session path, что и любой USER;
- Telegram Login/VK ID = product auth; GitHub/cloud-provider/Windows = engineering authority;
- public multi-user = approved target, но PUBLIC_MULTI_USER_ENABLED=false до required gates;
- initial USER access fully free: BILLING_ENABLED=false, TRIAL_ENABLED=false, SUBSCRIPTION_ENFORCEMENT=false, PREMIUM_FEATURE_GATING=false; future monetization DEFERRED_OPTIONAL;
- each USER owns only tenant-scoped BrokerConnection READ/optional TRADE credentials; no global/shared user broker token;
- raw credentials never return to browser storage and never enter GitHub/CI/artifacts;
- T-Invest public connector remains separate fail-closed broker-terms gate;
- app:app protected V9 baseline, trading_methods=false, REAL_TRADING_ENABLED=false, no transfer/withdrawal/margin/short remain preserved.

Do not activate public production merely because it is target architecture. Corrected WP22A plus tenant isolation, session/abuse, secrets/recovery, privacy/personal-data, broker/legal/regulatory, capacity/incident gates must pass first.

Engineering invariants:
- one canonical repo/Core/product line; no duplicate stacks;
- focused branch + PR only;
- root cause/blast radius before material fix;
- cheap/focused preflight before expensive CI;
- every applicable exact-head check must really run and conclude success; RED/skipped/queued/pending is not GREEN;
- any commit invalidates prior final GREEN;
- full diff + zero blockers + squash merge;
- exact new main + required post-merge Regression Shield before status/acceptance;
- OWNER product acceptance only after merge/post-merge GREEN except genuine non-delegable prerequisite;
- do not weaken tests/security/Regression Shield;
- later WPs remain locked until current Exit Gate.

The Product USER / Engineering Authority + Public Free Multi-User Hosted Runtime planning correction is already accepted through PR #329 merged to exact main `5f535c0ced9514866bd3680042f3ba0bb012f866` with post-merge Regression Shield #1503 / run `32129304332` SUCCESS. Do not reintroduce the superseded planning freeze or OWNER/home-production assumptions. Read the latest accepted `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`; corrected WP22A is the current functional package and its first implementation phase is the service/hosting architecture decision under the current execution/service-selection contracts. Planning acceptance does not authorize public activation, paid-provider purchase, privileged provider mutation, broker-write expansion or WP23 work.

Broker/money invariants:
- tenant-scoped READ/optional TRADE credentials;
- same-tenant VERIFIED_READ_ACCOUNTS ∩ VERIFIED_TRADE_ACCOUNTS for execution eligibility;
- immutable plan + authenticated USER confirmation for own tenant + preflight + idempotency/reconciliation;
- no AI broker-write authority;
- no withdrawal/transfer/margin/short/autonomous recurring Real execution.

Before changes, briefly report exact main, current WP, relevant PR/issues, required CI/protection, canonical files read, exact current scope/non-goals, and historical records used only as evidence.
```

Для настройки самого существующего Custom GPT использовать `gpt/SETUP_INDEX.md` как главный recovery/setup источник.