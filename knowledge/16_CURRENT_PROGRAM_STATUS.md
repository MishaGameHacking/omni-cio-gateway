# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-07-31  
Фактическая слитая вершина программы: **PR-98**  
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

PR-99 не входит в завершённую цепочку до успешного CI и squash merge.

## Текущая слитая вершина — PR-98

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

## Активный пакет — PR-99 Expert RA fixed issuer-action source

GitHub PR #128 открыт как draft на ветке
`agent/expert-ra-rating-actions-source-v1`. Он mergeable и не отстаёт от `main`,
но merge заблокирован отсутствием полноценного GitHub-hosted Regression Shield.

### Fixed identity

- endpoint: `https://raexpert.ru/`;
- provider: `Expert RA`;
- source id: `EXPERT_RA.home.rating_actions`;
- accepted release hosts: `raexpert.ru` и фиксированный alias
  `www.raexpert.ru`;
- stored canonical host: всегда `raexpert.ru`;
- release path: `/releases/{20xx}/{jan..dec}{valid day}[a-z]?`;
- source language: Russian.

Caller-controlled URLs, redirects for the owned client, English/secondary hosts,
query strings, fragments, unknown month tokens, calendar-invalid dates and
arbitrary release paths are запрещены.

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
поддерживаемой грамматики.

Bond/issue/series/tranche/structured-finance, ESG, plural, complex и unsupported
scale actions пропускаются. Malformed title, явно заявляющий поддерживаемое
singular issuer national-Russia действие, fail-closed отклоняется.

### Page and transport boundary

- extraction только между видимыми `Рейтинговые действия` и `Аналитика`;
- fixed HTTPS GET;
- redirects disabled;
- HTML/XHTML only;
- bounded declared и streamed bytes;
- UTF-8/UTF-8-BOM only;
- script/style/noscript content ignored;
- adjacent publication date required;
- future-date tolerance bounded одним календарным днём;
- release URL month/day calendar-valid;
- URL date обязана точно совпадать с `published_on`;
- available snapshot `retrieved_at` обязана совпадать с
  `source.retrieved_at`;
- every record обязана использовать exact snapshot source;
- duplicate conflicts fail closed;
- raw title, HTML, upstream body и exception text не сохраняются.

Contracts объявляют informational use only, no software-authorized
redistribution, not an investment recommendation, no credentials/full account
ID, no broker write, no order creation и `trading_methods=false`.

### Self-review fixes в активной ветке

- исправлена grammar outlook tails: `со ... прогнозом`, `и изменил ...`, comma
  form и bounded optional under-observation status;
- усилена canonical release URL validation против host/path/query/slash и path
  traversal bypasses;
- запрещены произвольные трёхбуквенные month tokens;
- добавлена calendar validation и URL date = publication date;
- добавлена publication/source retrieval tolerance;
- добавлена exact snapshot/source retrieval timestamp consistency;
- добавлены focused date-identity и timestamp-consistency tests.

### Текущая CI-блокировка

Последние Regression Shield runs завершают оба jobs до выделения первого шага:
`steps=null`, logs отсутствуют, diagnostics artifact отсутствует. GitHub Status
не показывает общий активный incident. Репозиторий private и использует
GitHub-hosted minutes/budget account policy.

Эти runs не классифицируются как code-test failures, но и не принимаются как
успешная валидация. PR-99 остаётся draft. Merge, ready-for-review и запуск PR-100
запрещены до нормального полного Regression Shield на exact final SHA.

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

- завершить PR-99 только после полного Regression Shield;
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
