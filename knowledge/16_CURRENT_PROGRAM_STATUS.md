# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-08-01  
Фактическая слитая функциональная вершина программы: **PR-102**  
Слитая инфраструктурная миграция CI: **GitHub PR #129**  
Активный незавершённый пакет: **PR-103 / Expert RA terminal evidence lifecycle v1**

## Назначение документа

Это оперативная карта программы. Код в `main` остаётся окончательным
источником истины. Стратегические требования и Definition of Done определяются
`AGENTS.md`, `knowledge/00_PROJECT_MASTER_CONTEXT.md` и canonical master plan
v9.

## Неизменяемые границы

- `trading_methods=false`;
- ровно 14 пользовательских GET Actions: 13 authenticated и public `/health`;
- Render entrypoint `app:app`;
- отсутствие создания, отправки, замены и отмены заявок;
- отсутствие переводов и вывода денег;
- отсутствие margin, short и derivatives execution;
- отдельная ветка и Pull Request для каждого пакета;
- squash merge только после полного Regression Shield на exact head;
- green CI не заменяет внешнюю Render/Gateway/GPT acceptance evidence.

## Завершённая release chain в `main`

- **PR-50…PR-83:** private read-only final-review production chain, acceptance
  collector, workflow/owner acquisition and authenticated evidence;
- **PR-84…PR-88:** official CBR source, cache, safe observability, bounded global
  alert policy and deterministic terminal evidence lifecycle;
- **PR-89…PR-93:** official MOEX TQBR source, exact cache, privacy-safe
  telemetry, global operational alert policy and terminal evidence;
- **PR-94…PR-98:** fixed official ACRA issuer-level national-RU source, bounded
  cache, privacy-safe telemetry, global alert policy and terminal evidence;
- **PR-99:** fixed official Expert RA issuer-level national-Russia source;
- **PR-100:** one-entry Expert RA cache with explicit
  fresh/stale/unavailable semantics, single-flight refresh and
  validator-bypass revalidation;
- **PR-101:** pure privacy-safe Expert RA source/cache observability with strict
  opaque trace IDs and no issuer/rating/action/release/publication payload;
- **PR-102:** bounded global-only Expert RA operational alert state machine with
  canonical-event validation, cooldown, recovery and no delivery transport.

## Текущая слитая функциональная вершина — PR-102

GitHub PR #134 `PR-102: Add global-only Expert RA alert policy v1`
squash-merged в `main` commit:

`6819899329b9902626f1a0ddb80f50b9d69dd01a`.

### PR-102 guarantees

- exactly four global operational kinds: source unavailable, cache unavailable,
  stale records exposed and refresh failed while fresh cache is used;
- fixed scope `global_expert_ra_rating_actions_feed`;
- strict PR-101 event/component/provider/operation/metric/state validation;
- canonical external-call profile including
  `circuit_breaker_state=not_applicable`;
- full policy and event Pydantic revalidation, including validator-bypassed
  objects;
- explicit `pending`, `fired`, `suppressed_cooldown`, `recovered` and
  `ignored` dispositions;
- bounded thresholds, cooldown, retention and exactly four global state slots;
- same-timestamp serialization and fail-closed decreasing-time handling;
- no issuer/rating/action/release/date/account/financial payload;
- no external notifications, broker writes, route, frontend field or startup
  task;
- `trading_methods=false`.

### Final PR-102 validation

Regression Shield run #799 / workflow `30690311867` passed on exact head
`94245e418ece1c84ec11360e190a6b078d27dae8`:

- quality/contracts/coverage: success;
- dependency/code/secret security: success;
- pytest: 1143 passed, 0 failed;
- total coverage: 61.97%, threshold >=60%;
- mypy: 185 source files, no issues;
- compile, Ruff and formatting: passed;
- stable `app:app`: passed;
- exactly 14 GET Actions and forbidden surface count 0: passed;
- `trading_methods=false`: passed;
- dependency audit, Bandit and detect-secrets: passed;
- diagnostics artifact ID `8815578140`;
- artifact SHA-256:
  `d49329a7370f5d4bb76979004ac7346b251914875cb40d22a022858c8b22f1c8`.

## Активный пакет — PR-103 Expert RA terminal evidence lifecycle v1

Рабочая ветка:

`agent/expert-ra-rating-actions-operations-lifecycle-v1`

Она создана точно от PR-102 merge commit
`6819899329b9902626f1a0ddb80f50b9d69dd01a`.

PR-103 строит только bounded process-local terminal evidence поверх canonical
PR-101 builders и PR-102 evaluator. Он не выполняет source/cache I/O, delivery
или broker operation.

### PR-103 evidence boundary

- only typed Expert RA source snapshot or cache result inputs;
- event creation delegated to PR-101 canonical builders;
- global alert state delegated to the exact PR-102 evaluator type;
- one `RLock` serializes evaluation, evidence mutation and sink handoff;
- only `fired` and `recovered` evaluations become evidence;
- terminal evaluation is Pydantic-revalidated and bound to the exact event name
  and UTC timestamp before recording;
- deterministic ID is `expert-ra-evidence:` plus 64 `a..p` characters
  derived from SHA-256 of allowlisted terminal fields;
- correlation ID is excluded from the digest, retained evidence, returned batch
  and sink payload;
- full event payload is not retained or returned;
- identical evidence is deduplicated and handed to the optional sink only once;
- same-ID/different-content collision fails closed;
- fired error codes are restricted to canonical credit-rating source/cache and
  fixed Expert RA operational codes;
- sink exceptions are reduced to a count without exception text;
- retention defaults to 86,400 seconds and capacity to 64 records, with strict
  configuration bounds, pruning, oldest-first eviction and `clear()`;
- all issuer/rating/action/release/publication/raw payload/financial/threshold,
  delivery, broker-write and trading flags remain false;
- no route, GPT Action, frontend binding, startup task, logger, event sink,
  webhook, email, Telegram or broker method.

PR-103 must remain unmerged until its draft Pull Request is opened, Regression
Shield passes both blocking jobs on the exact final head, the diagnostics
artifact is present, review threads are clear and GitHub reports the PR
mergeable.

## Слитая CI-инфраструктура

GitHub PR #129 moved Regression Shield to trusted repository-level self-hosted
Windows runner `omni-cio-ci` without weakening gates. The workflow verifies
hash-locked dependencies, repository/security policy, compile, Ruff, formatting,
mypy, stable `app:app`, exact 14-GET release contract, pytest/coverage,
pip-audit, Bandit, detect-secrets and workspace cleanup.

Independent draft PR #130 remains infrastructure hardening for read-only runner
service diagnostics. It does not block the functional roadmap while the current
persistent runner completes both Regression Shield jobs normally.

## Frontend/owner discovery state

No approved production binding justifies creating a duplicate frontend or
silently adding these market-data states to a public Action. The existing
site/frontend must be located and reused before Web-cabinet work.

## Production acceptance state

PR-64 still requires eight external evidence cases:

1. Render commit;
2. cache-busted health;
3. auth-negative;
4. exact-route-positive;
5. GPT schema import;
6. authenticated Preview;
7. Action-list inspection;
8. rollback restore.

CI cannot mark these external checks complete.

## Что остаётся до полного релиза

### Backend and operations

- finish PR-103 after exact-head Regression Shield;
- add other credit-rating agencies only as independent fixed reviewed sources;
- identify exact production market-data callers and bind lifecycles lazily;
- build production-grade news and corporate-event ingestion;
- execute real Render/Gateway/GPT acceptance and persist evidence;
- add versioned external RAG with freshness/citation controls;
- expand operational monitoring/runbooks.

### Web cabinet

- locate and register the existing frontend source; do not create a duplicate;
- implement safe official SberInvestments HTML report import without OCR;
- archive reports, compare periods and surface reconciled discrepancies;
- finish mobile layout and light/dark themes;
- validate all interactive controls on the production site.

### Trading stages

Shadow, paper, preview and final-review components do not authorize live
trading. Any future real execution needs a separate owner-approved admission
program with confirm-before-trade, idempotency, confirmation TTL, kill switch,
partial-fill and timeout reconciliation. Autonomous execution remains disabled.

## Следующий безопасный пакет

Current package: **PR-103 Expert RA deterministic terminal evidence
lifecycle v1**.

Only after PR-103 passes exact-head CI and squash-merges may the next independent
fixed source or exact production owner binding package start.

## Запрет ложного завершения

Проект не считается полностью завершённым после одного зелёного PR. Полный
релиз требует внешней production acceptance evidence, exact owner/frontend
binding, remaining market/news/RAG work and completion of the planned safety
stages. Until then the system remains read-only with
`trading_methods=false`.
