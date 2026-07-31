# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-07-31  
Фактическая вершина программы после merge этого пакета: **PR-97**  
Точная версия определяется текущей вершиной ветки `main`.

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
- squash merge только после полного Regression Shield.

## Завершённая release chain

- **PR-50…PR-63:** compact final review, exact identity, private GET route,
  trusted publication и end-to-end fail-closed orchestration;
- **PR-64:** production-acceptance evidence contract и offline collector;
- **PR-65…PR-83:** typed workflow bridge, producer, source acquisition,
  calculator handoff, approved owner installation and authenticated evidence;
- **PR-84…PR-88:** official CBR source, cache, safe observability, bounded alert
  policy and deterministic fired/recovered evidence lifecycle;
- **PR-89…PR-93:** official MOEX TQBR source, exact cache, safe observability,
  global operational alert policy and deterministic fired/recovered evidence;
- **PR-94…PR-97:** fixed official ACRA issuer-level national-RU rating-action
  source, bounded freshness cache, privacy-safe telemetry and global operational
  alert policy.

## PR-81…PR-83 authenticated owner lifecycle

Existing Bearer auth and exact compact-response validation create a trusted
server context. A fresh typed Decision/intent/capacity/pro-forma snapshot is
selected by exact scenario, correlation, operation and masked account, rebound
to existing owner ports and invoked at most once. Bounded redacted evidence is
retained. Startup performs no owner, calculator, portfolio, network or broker
call. Public response and OpenAPI remain unchanged.

## PR-84…PR-88 CBR lifecycle

The fixed Bank of Russia source provides typed Decimal observations, protected
XML parsing, bounded HTTPS streaming and redacted failures. The exact-range
cache exposes explicit fresh/stale/unavailable state, single-flight refresh and
no-silent-stale behavior. Observability contains operational metadata only.
Alerting uses bounded operational thresholds, cooldown and recovery; the final
lifecycle retains only bounded fired/recovered evidence without startup fetch.

## PR-89…PR-93 MOEX lifecycle

- fixed official public `stock/shares/TQBR` endpoint and strict SECID identity;
- allowlisted JSON tables, Decimal prices and Moscow time normalization;
- public feed marked potentially delayed, non-realtime and informational-only;
- exact `(TQBR, normalized SECID)` cache with separate retrieval TTL and market
  age derived from `quote.as_of`;
- stale exposure only after refresh failure and explicit trusted policy;
- status/freshness telemetry without price, SECID, account or raw JSON;
- global-only operational alert policy with forged-event rejection;
- deterministic event -> evaluation -> bounded fired/recovered evidence;
- no external notification transport and no startup network call.

Broker `getMarketSnapshot` remains primary for execution-style calculations.
MOEX and broker values are never silently averaged.

## PR-94 official ACRA issuer rating-action source

- fixed endpoint `https://www.acra-ratings.ru/press-releases/?count=30&lang=en`;
- provider `ACRA` and fixed source identity;
- issuer-level assigned, affirmed, upgraded, downgraded and withdrawn actions;
- agency-specific national-Russia rating strings without scale conversion;
- canonical numeric official release URLs and publication dates;
- issue-level, international-scale and multi-target documents skipped as
  unsupported scope;
- malformed supported single issuer actions fail closed;
- bounded HTML/XHTML transport with raw HTML/body/exception text excluded;
- no source call at import or startup.

## PR-95 bounded ACRA cache

- one fixed-source process-local entry;
- fresh TTL 900 seconds and stale retention 86400 seconds;
- retrieval freshness derives from `snapshot.retrieved_at`;
- record `published_on` dates remain separate source evidence;
- one `RLock` provides single-flight refresh;
- stale records remain hidden unless refresh failed and trusted
  `allow_stale=true` was supplied;
- wrong type, identity, future timestamp and unavailable source fail closed;
- only typed PR-94 snapshots are retained; restart starts empty.

## PR-96 privacy-safe ACRA observability

PR-96 maps typed PR-94/95 results to immutable `ObservabilityEventV1` with:

- source and cache operational status;
- optional validated latency and safe record count;
- cache hit, refresh attempted/succeeded, stale available/exposed and display
  allowed flags;
- provider, fixed operation, freshness and safe error code.

Events exclude issuer name, rating value/scale, outlook, action, release URL/id,
publication date, raw HTML/title, account, portfolio, broker payload and upstream
exception/body. Builders are pure and perform no automatic emission or fetch.

## PR-97 bounded global ACRA alert policy

### Immutable scope

The only scope is `global_acra_rating_actions_feed`. PR-97 cannot represent an
issuer, instrument, rating level, outlook, action, release or publication date.
It evaluates operational health only.

### Supported conditions

- source unavailable;
- cache unavailable, including hidden stale records not allowed for display;
- stale records explicitly exposed;
- refresh failed while a still-fresh cached snapshot remains usable.

### Canonical event gate

Known PR-96 event names pass only when all fields are canonical:

- exact event name, component, provider and operation;
- exact metric set with duplicate metric names rejected;
- record count bounded 0…30;
- fixed official-source and issuer-scope flags;
- exact outcome/severity/call-status/freshness profile;
- coherent cache-hit, refresh, stale and display flags;
- no account, request/action identity, exception type or generic payload.

A forged same-name event fails closed before state changes. Unknown event names
are ignored without creating state.

### State lifecycle

- dispositions: ignored, pending, fired, suppressed cooldown and recovered;
- bounded consecutive thresholds and saturating counters;
- fixed capacity four, retention and explicit clear/restart-empty behavior;
- sibling recovery when one cache failure mode replaces another;
- out-of-order rejection;
- one `RLock` serializes state transitions;
- no webhook, email, Telegram, pager or external delivery.

Evaluation serialization contains global operational kind, counters, threshold,
severity, disposition, event name, safe error code and false-valued privacy
flags only. No rating or issuer payload is retained.

## Compatibility and safety after PR-97

- `app:app` unchanged;
- 14 GET Actions unchanged: 13 authenticated and public health;
- no route, request body, public response field or frontend component;
- no dependency, database, secret or Render migration;
- no source/cache call, event emission or alert evaluation at import/startup;
- no T-Invest call or broker write method;
- `trading_methods=false`.

## Frontend/owner discovery state

Repository search did not find a registered existing frontend/dashboard owner or
production caller for the CBR/MOEX/ACRA fields. These packages do not invent a
duplicate UI, silently change an Action response or start network calls. Exact
owner discovery remains mandatory before production binding.

## Production acceptance state

PR-64 still requires eight real external evidence cases:

1. Render commit;
2. cache-busted health;
3. auth-negative;
4. exact-route-positive;
5. GPT schema import;
6. authenticated Preview;
7. Action-list inspection;
8. rollback restore.

Green CI cannot mark these external cases passed.

## Что остаётся до полного релиза

### Backend and operations

- compose PR-96 event -> PR-97 evaluation and retain only bounded global
  fired/recovered evidence;
- add other recognized rating agencies only through separate fixed contracts;
- locate exact CBR/MOEX/ACRA callers and bind lifecycles lazily;
- build production-grade news and corporate-event ingestion;
- execute real Render/Gateway/GPT acceptance and record evidence;
- add external versioned RAG with freshness and citation controls;
- expand operational runbooks and monitoring acceptance.

### Web cabinet

- найти и зарегистрировать исходный frontend существующего сайта;
- не создавать дубликат frontend;
- реализовать безопасный HTML-импорт СберИнвестиций без OCR;
- архив, сравнение периодов, расхождения, мобильный UI и обе темы;
- проверить production site и интерактивные элементы.

### Торговые этапы

Shadow, paper, preview и final-review инфраструктура не являются разрешением на
реальную торговлю. Confirm-before-trade, idempotency, TTL confirmation, kill
switch, partial-fill и timeout reconciliation требуют отдельной программы
допуска и решения владельца. Автономная торговля без подтверждения не включена.

## Следующий пакет после PR-97

Ближайший независимый безопасный пакет — bounded ACRA operations evidence
lifecycle v1:

- compose already-produced PR-96 event and PR-97 evaluation;
- retain only fired and recovered global evidence;
- deterministic event-sink then evidence-sink ordering;
- bounded retention/capacity, pruning, eviction and restart-clear behavior;
- no issuer/rating/release/publication payload;
- no external notification transport, route, Action, frontend field, startup
  source call or broker method.

## Запрет ложного завершения

Проект не считается полностью завершённым только потому, что PR-97 слит и CI
зелёный. Полный релиз требует внешней Render/Gateway/GPT acceptance evidence,
точного production owner binding и завершения оставшихся master-plan блоков.
