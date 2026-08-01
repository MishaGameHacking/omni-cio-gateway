# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-08-01  
Фактическая слитая функциональная вершина программы: **PR-103**  
Слитая инфраструктурная миграция CI: **GitHub PR #129**  
Активный незавершённый пакет: **PR-104 / NCR issuer rating action source v1**

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
  canonical-event validation, cooldown, recovery and no delivery transport;
- **PR-103:** bounded deterministic Expert RA terminal evidence lifecycle with
  correlation-free retention, deduplication and safe sink handoff.

## Текущая слитая функциональная вершина — PR-103

GitHub PR #135 `PR-103: Add deterministic Expert RA terminal evidence lifecycle v1`
squash-merged в `main` commit:

`60131cf142be9b245eacc3326854cdab7a2abe1c`.

### PR-103 guarantees

- only typed Expert RA source snapshot or cache result inputs;
- canonical PR-101 event builders and the exact PR-102 evaluator;
- only `fired` and `recovered` evaluations become retained evidence;
- deterministic `expert-ra-evidence:` identifiers over allowlisted terminal
  fields;
- correlation ID and the full event payload excluded from retained evidence,
  returned batches and sink payloads;
- deduplication, collision rejection and new-record-only optional sink handoff;
- bounded retention/capacity, deterministic pruning, eviction and `clear()`;
- sink failures reduced to a count without exception text;
- no issuer/rating/action/release/date/account/financial payload, delivery
  transport, broker write, route, frontend field or startup task;
- `trading_methods=false`.

### Final PR-103 validation

Regression Shield run #804 / workflow `30691504256` passed on exact head
`af7a5fcaac9b050d1f93a6d6352d04ab65952b53`:

- quality/contracts/coverage: success;
- dependency/code/secret security: success;
- pytest: 1157 passed, 19 non-blocking warnings;
- total coverage: 61.97%, threshold >=60%;
- mypy: 186 source files, no issues;
- compile, Ruff, formatting baseline and lock verification: passed;
- stable `app:app`, exactly 14 GET Actions, forbidden surface count 0 and
  `trading_methods=false`: passed;
- pip-audit, Bandit and detect-secrets: passed;
- diagnostics artifact ID `8815898287`;
- artifact SHA-256:
  `94e473064e2e269999d5a75f2fd92dcce41ecff831bd9a1e3218a3713a9dbd3b`.

## Активный пакет — PR-104 NCR issuer rating action source v1

Рабочая ветка:

`agent/ncr-issuer-rating-action-source-v1`

Она создана точно от PR-103 merge commit
`60131cf142be9b245eacc3326854cdab7a2abe1c`.

PR-104 добавляет отдельный fixed official NCR source boundary. Он не создаёт
generic agency adapter, не объединяет шкалы или идентичности ACRA/Expert RA/NCR
и не меняет публичный Gateway surface.

### PR-104 source boundary

- fixed `https://ratings.ru/ratings/press-releases/` GET endpoint;
- exact provider/source id and canonical release identity;
- separate NCR issuer-action and snapshot contracts;
- singular assigned, affirmed, upgraded, downgraded and withdrawn actions only;
- closed NCR national-Russia scale from `AAA.ru` through `C.ru`, plus `D`;
- expected, issue-level, plural and mixed issuer/issue actions excluded;
- bounded NCR outlook grammar including uncertain/under-review wording;
- exact visible list headers, bounded row date association and URL/date match;
- isolated transport-only injection, no inherited auth/cookies/hooks,
  `trust_env=false`, no redirects and bounded timeout/response size;
- no raw title/HTML storage, redistribution authorization, entity merge,
  credentials, account identity, broker write or trading surface;
- no cache, observability, alert, evidence, route, GPT Action, frontend binding
  or startup task;
- `trading_methods=false`.

PR-104 must remain unmerged until its draft Pull Request is opened, Regression
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

- finish PR-104 after exact-head Regression Shield;
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

Current package: **PR-104 NCR issuer rating action source v1**.

Only after PR-104 passes exact-head CI and squash-merges may a separate NCR
cache, another independent fixed source or exact production owner binding
package start.

## Запрет ложного завершения

Проект не считается полностью завершённым после одного зелёного PR. Полный
релиз требует внешней production acceptance evidence, exact owner/frontend
binding, remaining market/news/RAG work and completion of the planned safety
stages. Until then the system remains read-only with
`trading_methods=false`.
