# Стартовый запрос для нового рабочего чата Omni-CIO

Использовать, когда нужно продолжить разработку/обслуживание проекта в новом чате после подключения GitHub.

```text
Подключись к GitHub-репозиторию MishaGameHacking/omni-cio-gateway.

Сначала прочитай и соблюдай authority order из AGENTS.md. Минимально обязательно прочитай:
1. AGENTS.md
2. README.md
3. knowledge/00_PROJECT_MASTER_CONTEXT.md
4. knowledge/16_CURRENT_PROGRAM_STATUS.md — protected V9 runtime baseline
5. docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md
6. docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md
7. docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md и все active amendments
8. docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md
9. knowledge/17_V10_CURRENT_PROGRAM_STATUS.md — текущий V10 WP/progress authority
10. профильные architecture/domain/runbook/contracts по текущей задаче
11. gpt/SETUP_INDEX.md и связанные GPT recovery files только если задача затрагивает текущий Custom GPT/V9 recovery

Затем проверь фактическое состояние репозитория:
- main SHA;
- open Pull Requests и Issues;
- active private-main ruleset/protection;
- latest exact-head required CI/security и post-merge Regression Shield;
- текущий authorized WP из knowledge/17_V10_CURRENT_PROGRAM_STATUS.md;
- production Render/Gateway contract, если задача затрагивает V9 runtime/deploy/GPT.

Текущая программа:
- V10 — единственная active feature program; OWNER уже выдал START V10;
- V9.0.0 остаётся protected production/recovery baseline до ответственного V10 cutover;
- WP0–WP3 приняты; accepted progress = 5%; WP4 — следующий work package, пока Current Status не скажет иначе;
- не начинать later WP раньше Exit Gate текущего WP.

Обязательные инварианты:
- один Omni-CIO product line, один canonical repo, один Core; не создавать duplicate Gateway/Web/Telegram/AI/execution stack;
- GitHub engineering access никогда не означает broker/trading authority;
- read-only, Sandbox и Real credentials изолированы; secret values/private portfolio payloads не сохранять в GitHub;
- AI не получает прямого broker-write/admin/GitHub-bypass/Real-money authority;
- Real execution остаётся exact-owner-confirmed, immutable, idempotent, fail-closed и broker-reconciled;
- no withdrawal/transfer, margin/short, MARKET/BESTPRICE, automatic retry after ambiguous possible-submit или autonomous recurring Real execution;
- stable V9 recovery entrypoint `app:app` сохранять до отдельного accepted V10 cutover;
- изменения делать только через focused branch + PR;
- merge только squash после current-head `V10 authoritative merge gate`, required security/CI и zero unresolved review threads;
- не ослаблять проверки ради зелёного CI;
- Dependabot PR — предложение, а не разрешение на изменение выбранного V10 baseline;
- old chat/screenshot/stale PR text не является authority при конфликте с accepted main + AGENTS + Current Status.

Перед изменениями кратко зафиксируй:
- current main SHA;
- текущий authorized WP;
- relevant open PR/issues;
- состояние required CI/protection;
- какие canonical files/contracts прочитаны;
- точный scope текущего WP/дефекта и что намеренно не входит в него.
```

Для настройки самого существующего Custom GPT использовать `gpt/SETUP_INDEX.md` как главный recovery/setup источник.
