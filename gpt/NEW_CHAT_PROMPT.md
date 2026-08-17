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
8. docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md и все active amendments
9. docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md
10. knowledge/17_V10_CURRENT_PROGRAM_STATUS.md — единственный current V10 WP/progress authority
11. профильные architecture/domain/runbook/contracts по текущей задаче
12. gpt/SETUP_INDEX.md и связанные GPT recovery files только если задача затрагивает текущий Custom GPT/V9 recovery

Затем проверь фактическое состояние репозитория:
- exact main SHA;
- open Pull Requests и Issues;
- active private-main ruleset/protection;
- latest exact-head required CI/security и post-merge Regression Shield;
- текущий authorized WP только из knowledge/17_V10_CURRENT_PROGRAM_STATUS.md;
- production Render/Gateway contract, если задача затрагивает protected V9 runtime/deploy/GPT;
- любой in-flight PR не считать accepted implementation до merge + required post-merge GREEN.

Текущая программа определяется так:
- V10 — единственная active feature program; OWNER уже выдал START V10;
- V9.0.0 остаётся protected production/recovery baseline до ответственного V10 cutover;
- exact accepted progress/current-next WP НЕ брать из этого prompt, старого чата, screenshot, package-local PENDING/CURRENT/NEXT или stale PR description — читать только из accepted-main knowledge/17_V10_CURRENT_PROGRAM_STATUS.md;
- не начинать later WP раньше Exit Gate текущего WP.

Обязательные инженерные инварианты:
- один Omni-CIO product line, один canonical repo, один Core; не создавать duplicate Gateway/Web/Telegram/AI/execution stack;
- GitHub engineering access никогда не означает broker/trading authority;
- read-only, Sandbox и Real credentials изолированы; secret values/private portfolio payloads не сохранять в GitHub;
- AI не получает прямого broker-write/admin/GitHub-bypass/Real-money authority;
- Real execution остаётся exact-owner-confirmed, immutable, idempotent, fail-closed и broker-reconciled;
- no withdrawal/transfer, margin/short, MARKET/BESTPRICE, automatic retry after ambiguous possible-submit или autonomous recurring Real execution;
- stable protected V9 recovery entrypoint `app:app` сохранять до отдельного accepted V10 cutover;
- `trading_methods=false` и `REAL_TRADING_ENABLED=false` сохранять, пока owning accepted gate явно не меняет соответствующую authority;
- изменения делать только через focused branch + PR;
- сначала установить root cause/blast radius и выполнить applicable cheap/focused preflight; CI использовать как independent verifier, а не primary debugger;
- every applicable exact-head V10 check должен реально выполниться и conclude success; failure/cancelled/pending/neutral/skipped не считать GREEN evidence для applicable gate;
- merge только squash после exact-head GREEN, full-diff review и zero unresolved blocking review threads;
- после merge проверить exact new main и required post-merge Regression Shield/owning audits;
- OWNER product acceptance запрашивать только после implementation merge + required post-merge GREEN; pre-merge OWNER involvement только для genuinely non-delegable prerequisite;
- не ослаблять проверки ради зелёного CI;
- Dependabot PR — предложение, а не разрешение на изменение accepted V10 baseline;
- historical records сохранять как evidence, но не использовать как competing current-state ledger.

Repository/runtime ownership:
- one deterministic Core: omni_cio/;
- accepted V10 API/Web roots may already exist under apps/api/ and apps/web/ according to current status;
- accepted Personal-Node infrastructure may exist under infrastructure/;
- apps/telegram/ and ai/ остаются lifecycle-gated до owning authorized WPs;
- V10 Web/API/private state остаются на approved Lenovo/replacement Personal Node, если later OWNER-approved architecture amendment явно не изменит это;
- external-access provider — access/security transport, не второй authoritative private-state/application host;
- existing Render app:app — protected V9 production/recovery baseline, не новый V10 hosting target.

Перед изменениями кратко зафиксируй:
- current main SHA;
- текущий authorized WP;
- relevant open PR/issues;
- состояние required CI/protection;
- какие canonical files/contracts прочитаны;
- точный scope текущего WP/дефекта и что намеренно не входит в него;
- какие historical records были просмотрены только как evidence и не используются как current authority.
```

Для настройки самого существующего Custom GPT использовать `gpt/SETUP_INDEX.md` как главный recovery/setup источник.