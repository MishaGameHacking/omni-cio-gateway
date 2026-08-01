# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-08-01  
Фактическая слитая функциональная вершина программы: **PR-98**  
Слитая инфраструктурная миграция CI: **GitHub PR #129**  
Активный незавершённый пакет: **PR-99 / GitHub PR #128**

## Назначение документа

Это оперативная карта программы. Код в `main` остаётся окончательным источником
истины; стратегические правила и Definition of Done определяются `AGENTS.md`,
`knowledge/00_PROJECT_MASTER_CONTEXT.md` и исходным master plan.

## Неизменяемые границы

- `trading_methods=false`;
- ровно 14 пользовательских GET Actions: 13 authenticated и public `/health`;
- Render entrypoint `app:app`;
- отсутствие создания, отправки, замены и отмены заявок;
- отсутствие переводов и вывода денег;
- отсутствие margin, short и derivatives execution;
- отдельная ветка и Pull Request для каждого пакета;
- squash merge только после полного Regression Shield на exact head.

## Завершённая release chain в `main`

- **PR-50…PR-63:** compact final review, exact identity, private GET route,
  trusted publication и end-to-end fail-closed orchestration;
- **PR-64:** production-acceptance evidence contract и offline collector;
- **PR-65…PR-83:** typed workflow bridge, producer, source acquisition,
  calculator handoff, approved owner installation and authenticated evidence;
- **PR-84…PR-88:** official CBR source, cache, safe observability, bounded alert
  policy and deterministic fired/recovered evidence lifecycle;
- **PR-89…PR-93:** official MOEX TQBR source, exact cache, safe observability,
  global operational alert policy and deterministic fired/recovered evidence;
- **PR-94…PR-98:** fixed official ACRA issuer-level national-RU source, bounded
  cache, privacy-safe telemetry, global alert policy and terminal evidence.

PR-99 не входит в завершённую функциональную цепочку до успешного CI и squash
merge.

## Текущая слитая функциональная вершина — PR-98

PR-98 предоставляет deterministic ACRA event → evaluation → bounded terminal
evidence lifecycle. Evidence хранит только `fired` и `recovered`, не содержит
issuer, rating, outlook, release, account, broker или financial payload и не
отправляется во внешние системы.

Финальный Regression Shield PR-98 прошёл на exact head:

- 1005 тестов, 0 failures/errors/skips;
- mypy: 178 source files;
- line coverage 66.3%, branch coverage 48.85%;
- compile, Ruff, formatting, stable `app:app`, 14-GET contract, dependency
  audit, SAST и secret scan прошли.

## Слитая инфраструктурная миграция — GitHub PR #129

GitHub-hosted jobs перестали получать runner allocation и завершались до первого
шага без logs и diagnostics artifact. Отдельный PR #129 перевёл Regression
Shield на repository-level self-hosted Windows runner `omni-cio-ci` без
ослабления gate.

Слитый CI-контур обеспечивает:

- exact labels `[self-hosted, Windows, X64, omni-cio-ci]`;
- same-repository guard для pull requests;
- `permissions: contents: read` и `persist-credentials: false`;
- официальный Python 3.12.10 с фиксированной SHA-256 проверкой;
- отдельный virtual environment в `RUNNER_TEMP` для каждого job;
- hash-locked Windows dependency projection с проверкой против canonical lock;
- compile, structure, Ruff, formatting, mypy, stable `app:app`, 14-GET contract,
  pytest/coverage, pip-audit, Bandit и detect-secrets;
- обязательную очистку workspace и временной среды.

PR #129 прошёл Regression Shield run #743 на exact head
`f8c7e4a950d2e5b4ae2ef1857591430449690acb`:

- 1012 тестов, 0 failures/errors/skips;
- mypy: 179 source files;
- line coverage 66.3%, branch coverage 48.85%;
- оба quality/security jobs зелёные;
- diagnostics artifact создан;
- Self-Hosted Windows Smoke run #41 зелёный.

Squash merge commit в `main`:
`16127b21f2cf194a0a56114ce7ad0277e5d1a0a4`.

Эта инфраструктурная миграция не меняет функциональную вершину программы,
OpenAPI, Render runtime, broker SDK или разрешённые Actions.

## Активный пакет — PR-99 Expert RA fixed issuer-action source

GitHub PR #128 открыт как draft на ветке
`agent/expert-ra-rating-actions-source-v1`. Текущий exact head после финальной
волны self-review определяется вершиной PR и должен быть единственным SHA,
принимаемым для merge evidence. Ready-for-review и squash merge разрешены только
после зелёного Regression Shield на этом exact head.

Regression Shield run #751 на более раннем head дошёл до полного test suite:
lock/security/layout, compile, Ruff, formatting, mypy, stable `app:app`, 14 GET
Actions, dependency audit, Bandit, secret scan и coverage прошли; 1074 теста
прошли, один устаревший direct-contract fixture был корректно отклонён из-за
несовпадения даты release URL и `published_on`. Fixture исправлен без ослабления
production validation.

После этого self-review выявил и закрыл дополнительные fail-closed границы:

- publication date принимается только как immediately adjacent visible event;
  look-ahead через посторонний visible content удалён;
- unknown release month отклоняется как `URL_INVALID` на URL boundary;
- calendar-invalid release identity, например `feb31`, отклоняется до создания
  Pydantic record;
- direct Expert RA outlook допускает только stable, positive, negative,
  developing или absence; shared `under_revision` не является Expert RA outlook;
- `под наблюдением` остаётся отдельным source-title status, а не outlook;
- официальный withdrawal suffix `и снял статус «под наблюдением»` поддерживается
  как bounded grammar, но не сохраняется в `subject_name`;
- residual withdrawal control text `статус`/`прогноз` в разобранном subject
  fail-closed отклоняется;
- exact release slug сохраняет проверенный формат `{jan..dec}{valid day}[a-z]?`.

Текущие Regression Shield runs после изменений создаются корректно, но trusted
self-hosted Windows listener на момент этой записи не выделяет jobs: оба job
остаются `queued` с `steps=null`. Это infrastructure evidence, не code success и
не code failure. Merge остаётся заблокирован.

### Fixed identity

- endpoint: `https://raexpert.ru/`;
- provider: `Expert RA`;
- source id: `EXPERT_RA.home.rating_actions`;
- accepted release hosts: `raexpert.ru` и фиксированный alias
  `www.raexpert.ru`;
- stored canonical host: всегда `raexpert.ru`;
- release path: `/releases/{20xx}/{jan..dec}{valid day}[a-z]?`;
- source language: Russian.

Caller-controlled URLs, arbitrary hosts, query strings, fragments, unknown month
tokens, calendar-invalid dates и произвольные release paths запрещены.

### Supported data and grammar

PR-99 использует отдельные `ExpertRa...` contracts, не ACRA records и не общий
multi-agency adapter. Поддерживаются только singular issuer-level действия:

- assigned;
- affirmed;
- upgraded;
- downgraded;
- withdrawn.

Поддерживается агентская национальная шкала `ruAAA…ruD`. Визуально смешанные
Cyrillic/Latin A/B/C/R/D нормализуются только внутри rating token и проверяются
по закрытому allowlist. Outlook принимается только при точном совпадении
поддерживаемой грамматики: stable, positive, negative, developing или absence.
`Под наблюдением` не подменяет outlook.

Bond/issue/series/tranche/structured-finance, ESG, plural, complex и unsupported
scale actions пропускаются. Malformed title, явно заявляющий поддерживаемое
singular issuer national-Russia действие, fail-closed отклоняется.

Source-title issuer text не считается стабильной canonical identity:

- `subject_identity_resolved=false`;
- `stable_subject_id_present=false`;
- `subject_name_is_source_text=true`;
- `identity_resolution_required=true`;
- `cross_agency_identity_merged=false`.

### Page boundary

- scope открывается только plain visible `Рейтинговые действия`;
- navigation link с тем же текстом не может открыть scope;
- scope закрывается plain `Аналитика` либо exact official `/researches/` link;
- external host, другой path, query или fragment не могут закрыть scope;
- publication date должна быть immediately adjacent к action;
- linked date обязана canonicalize в тот же release, что и action;
- URL date обязана точно совпадать с `published_on`;
- `<a>` без `href` не может impersonate plain heading или boundary.

### Transport and parser boundary

- fixed HTTPS GET;
- всегда создаётся отдельный isolated `httpx.Client`;
- dependency injection только `httpx.BaseTransport`, shared client запрещён;
- нет inherited auth, cookies, headers или request hooks;
- `trust_env=false`, redirects disabled;
- explicit allowlisted `Accept` и `User-Agent`;
- caller может только уменьшать default timeout/response budget;
- `NaN`, infinities, huge values и expanded budgets отклоняются до I/O;
- HTML/XHTML only;
- bounded declared и streamed bytes;
- UTF-8/UTF-8-BOM only;
- script/style/noscript content ignored;
- unclosed или mismatched anchor/script/style/noscript fail closed;
- future-date tolerance bounded одним календарным днём;
- release URL month/day calendar-valid до canonicalization;
- available snapshot `retrieved_at` обязана совпадать с
  `source.retrieved_at`;
- every record обязана использовать exact snapshot source;
- snapshot ограничен 30 records и deterministic newest-first ordering;
- duplicate conflicts fail closed;
- raw title, HTML, upstream body и exception text не сохраняются.

Contracts экспортируются через direct module и общий `omni_cio.contracts.v1` и
объявляют informational use only, no software-authorized redistribution, not an
investment recommendation, no credentials/full account ID, no broker write, no
order creation и `trading_methods=false`.

## Compatibility и safety активной ветки

- `app:app` не изменён;
- 14 GET Actions не изменены;
- нет route, request body, public response field или frontend component;
- нет dependency, database, secret или Render migration;
- нет source fetch при import/startup;
- нет cache, observability, alert или evidence для Expert RA;
- нет webhook, email, Telegram, pager или внешней доставки;
- нет T-Invest call или broker write method;
- `trading_methods=false`.

## Frontend/owner discovery state

Repository search не выявил зарегистрированный существующий frontend/dashboard
owner или production caller для CBR/MOEX/ACRA/Expert RA полей. Пакеты не создают
дубликат UI, не меняют Action response и не запускают network calls. Exact owner
discovery остаётся обязательным до production binding.

## Production acceptance state

PR-64 всё ещё требует восемь внешних evidence cases:

1. Render commit;
2. cache-busted health;
3. auth-negative;
4. exact-route-positive;
5. GPT schema import;
6. authenticated Preview;
7. Action-list inspection;
8. rollback restore.

Green CI не может отметить эти внешние проверки выполненными.

## Что остаётся до полного релиза

### Backend and operations

- завершить PR-99 только после полного Regression Shield на exact final SHA;
- после merge PR-99 отдельными пакетами добавить Expert RA cache, telemetry,
  global alert policy и terminal evidence lifecycle;
- добавлять другие CRA только отдельными fixed contracts;
- найти exact market-data callers и bind lifecycles lazily;
- построить production-grade news и corporate-event ingestion;
- выполнить real Render/Gateway/GPT acceptance и записать evidence;
- добавить external versioned RAG с freshness и citation controls;
- расширить operational runbooks и monitoring acceptance.

### Web cabinet

- найти и зарегистрировать исходный frontend существующего сайта;
- не создавать дубликат frontend;
- реализовать безопасный HTML-импорт СберИнвестиций без OCR;
- архив, сравнение периодов, расхождения, мобильный UI и обе темы;
- проверить production site и интерактивные элементы.

### Trading stages

Shadow, paper, preview и final-review инфраструктура не являются разрешением на
реальную торговлю. Confirm-before-trade, idempotency, TTL confirmation, kill
switch, partial-fill и timeout reconciliation требуют отдельной программы
допуска и решения владельца. Автономная торговля без подтверждения не включена.

## Следующий пакет после успешного PR-99

Только после CI и merge PR-99 разрешён one-entry bounded Expert RA cache v1:

- typed PR-99 snapshots with exact provider/source identity;
- fresh, stale и unavailable states;
- retrieval freshness только из `snapshot.retrieved_at`;
- publication dates как отдельное source evidence;
- single-flight refresh under one lock;
- stale hidden unless refresh failed and trusted `allow_stale=true`;
- fully expired state pruned;
- bounded controls, restart-empty и explicit clear;
- no source fetch at import/startup;
- no route, Action, frontend, external notification или broker method.

## Запрет ложного завершения

Проект не считается полностью завершённым после одного зелёного PR. Полный релиз
требует внешней Render/Gateway/GPT acceptance evidence, точного production owner
binding и завершения оставшихся master-plan блоков.
