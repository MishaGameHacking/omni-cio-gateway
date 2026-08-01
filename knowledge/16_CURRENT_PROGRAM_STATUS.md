# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-08-01  
Фактическая слитая функциональная вершина программы: **PR-100**  
Слитая инфраструктурная миграция CI: **GitHub PR #129**  
Активный незавершённый пакет: **PR-101 / Expert RA observability v1**

## Назначение документа

Это оперативная карта программы. Код в `main` остаётся окончательным источником
истины. Стратегические требования и Definition of Done определяются `AGENTS.md`,
`knowledge/00_PROJECT_MASTER_CONTEXT.md` и canonical master plan v9.

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
  alert policy and deterministic fired/recovered evidence lifecycle;
- **PR-89…PR-93:** official MOEX TQBR source, exact cache, privacy-safe telemetry,
  global operational alert policy and terminal evidence;
- **PR-94…PR-98:** fixed official ACRA issuer-level national-RU source, bounded
  cache, privacy-safe telemetry, global alert policy and terminal evidence;
- **PR-99:** fixed official Expert RA issuer-level national-Russia rating-action
  source with strict HTML/URL/date/grammar and unresolved-identity boundaries;
- **PR-100:** one-entry Expert RA cache with explicit fresh/stale/unavailable
  semantics, single-flight refresh and validator-bypass revalidation.

## Текущая слитая функциональная вершина — PR-100

GitHub PR #132 `PR-100: Add bounded Expert RA rating-action cache v1` squash-merged
в `main` commit:

`d05d34883a283bd0b10e41e2bc48c0a81a948d92`.

### PR-100 guarantees

- fixed provider `Expert RA` and source id `EXPERT_RA.home.rating_actions`;
- one process-local cache entry;
- fresh TTL 900 seconds;
- stale retention 86400 seconds;
- freshness derives only from `snapshot.retrieved_at`;
- publication date remains separate source evidence;
- stale data is hidden unless refresh failed and trusted caller explicitly sets
  `allow_stale=true`;
- fully expired data is pruned;
- `clear()` and restart-empty lifecycle;
- one `RLock` provides single-flight initial load/refresh;
- loader-returned typed objects are fully revalidated after serialization so
  `model_construct()` or non-validating copy paths cannot weaken URL/date,
  source, Literal, privacy or trading invariants;
- loader/validation exception text is never copied into cache output;
- no startup fetch, route, Action, DB, frontend binding or broker method.

### Final PR-100 validation

Regression Shield run #793 / workflow `30688586258` passed on exact head
`e76e561897e292e1e1db79dfca4d9edb341d5d66`:

- quality/contracts/coverage: success;
- dependency/code/secret security: success;
- pytest: 1109 passed, 0 failed;
- total coverage: 61.97%, threshold >=60%;
- mypy: 182 source files, no issues;
- compile, Ruff and formatting: passed;
- stable `app:app`: passed;
- exactly 14 GET Actions and forbidden surface count 0: passed;
- `trading_methods=false`: passed;
- dependency audit, Bandit and detect-secrets: passed;
- diagnostics artifact ID `8814880257`;
- artifact SHA-256:
  `2dddda71067ddc40f37e9df486f5d47671400554dbc7ce7035b9a7a34618cec7`.

## Активный пакет — PR-101 Expert RA observability v1

Рабочая ветка:

`agent/expert-ra-rating-actions-observability-v1`

Она создана точно от PR-100 merge commit
`d05d34883a283bd0b10e41e2bc48c0a81a948d92`.

PR-101 строит только pure observability builders поверх typed PR-99 source и
PR-100 cache. Он не является production emitter, route, scheduler или alert
policy.

### Allowed telemetry

Разрешены только фиксированные operational metadata/counts:

- provider `Expert RA`;
- operation `home.rating_actions`;
- source/cache availability and freshness state;
- fixed source/cache error code;
- optional finite non-negative duration;
- record count;
- cache hit;
- refresh attempted/succeeded;
- stale available/exposed;
- display allowed;
- fixed-official-source and issuer-scope flags;
- identity-resolution-required;
- cross-agency-identity-merged, ожидается только false.

### Forbidden telemetry

Запрещено переносить в event:

- issuer/subject/source-title text;
- rating, rating scale, outlook or action kind;
- release URL or release identity;
- publication date;
- raw title/HTML/upstream body;
- arbitrary exception text/type or traceback;
- account, portfolio, position, price, cash or broker payload;
- credential/cookie/Authorization/token;
- caller-selected source URL;
- investment recommendation or trade authorization.

### Extra PR-101 hardening

- source/cache models reserialize with Pydantic warnings treated as errors and
  fully revalidate before telemetry is derived;
- validator-bypassed privacy/trading flags fail closed;
- caller-supplied `correlation_id` is not free-form: accepted only as opaque
  `corr:` plus 32 `a..p` entropy characters, matching `new_trace_id("corr")`;
- omitted correlation id is generated by the existing safe-event builder;
- serialized-event tests prove issuer/rating/outlook/action/release/date markers
  are absent;
- module has no app/router/startup/emitter/webhook/email/Telegram/order surface.

PR-101 must remain unmerged until a draft Pull Request is opened and Regression
Shield passes both blocking jobs on the exact final head, diagnostics artifact is
present, review threads are clear and GitHub reports the PR mergeable.

## Слитая CI-инфраструктура

GitHub PR #129 moved Regression Shield to trusted repository-level self-hosted
Windows runner `omni-cio-ci` without weakening gates. The workflow uses:

- exact labels `[self-hosted, Windows, X64, omni-cio-ci]`;
- same-repository PR isolation;
- read-only contents permission and checkout without persisted credentials;
- pinned Python 3.12.10 bootstrap;
- isolated job virtual environments;
- hash-locked Windows dependency projections;
- compile/layout/Ruff/format/mypy/entrypoint/14-GET/pytest/coverage;
- pip-audit/Bandit/detect-secrets;
- workspace cleanup.

An independent draft PR #130 contains a read-only Windows runner diagnostic and
persistent-service runbook. It is infrastructure hardening, not a prerequisite
for changing the functional release top while the current persistent runner is
successfully processing both Regression Shield jobs.

## Frontend/owner discovery state

Repository work still has no approved production binding that would justify
creating a duplicate frontend or silently adding market-data fields to an Action.
The existing site/frontend must be located and reused before Web-cabinet work.

## Production acceptance state

PR-64 still requires eight external evidence cases before the project can be
called production accepted:

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

- finish PR-101 after exact-head Regression Shield;
- then separate **PR-102**: global-only Expert RA operational alert policy over
  PR-101 events, without issuer/rating/action identity, financial thresholds or
  outbound delivery;
- then separate **PR-103**: deterministic bounded Expert RA fired/recovered
  terminal evidence lifecycle;
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

Shadow, paper, preview and final-review components do not authorize live trading.
Any future real execution needs a separate owner-approved admission program with
confirm-before-trade, idempotency, confirmation TTL, kill switch, partial-fill
and timeout reconciliation. Autonomous execution remains disabled.

## Следующий безопасный пакет

Current package: **PR-101 Expert RA privacy-safe observability v1**.

Only after PR-101 passes exact-head CI and squash-merges may PR-102 start.

## Запрет ложного завершения

Проект не считается полностью завершённым после одного зелёного PR. Полный
релиз требует внешней production acceptance evidence, exact owner/frontend
binding, remaining market/news/RAG work and completion of the planned safety
stages. Until then the system remains read-only with `trading_methods=false`.
