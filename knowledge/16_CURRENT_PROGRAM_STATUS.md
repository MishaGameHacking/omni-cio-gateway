# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-07-31  
Фактическая вершина программы после merge этого пакета: **PR-98**  
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
- **PR-94…PR-98:** fixed official ACRA issuer-level national-RU rating-action
  source, bounded freshness cache, privacy-safe telemetry, global operational
  alert policy and deterministic fired/recovered evidence lifecycle.

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

## PR-94…PR-98 ACRA lifecycle

### Source and cache

- fixed official ACRA press-release endpoint and source identity;
- issuer-level Russian national-scale assigned, affirmed, upgraded, downgraded
  and withdrawn actions only;
- no cross-agency scale conversion;
- canonical official release URLs and publication dates;
- unsupported issue-level, international-scale and multi-target titles skipped;
- malformed supported single-issuer actions fail closed;
- bounded HTML/XHTML transport with raw HTML/body/exception text excluded;
- one-entry fresh/stale/unavailable cache with 900-second fresh TTL and
  86,400-second stale retention;
- stale records hidden unless refresh failed and trusted `allow_stale=true`;
- no source/cache call at import or startup.

### Privacy-safe telemetry and global alert policy

PR-96 events contain operational status, optional latency, bounded record count,
cache-hit/refresh/stale/display flags, provider, operation, freshness and safe
error code only.

PR-97 accepts known event names only through a complete canonical gate:

- exact event name, component, provider and operation;
- exact metric set with duplicate metric names rejected;
- bounded record count and fixed source/scope flags;
- coherent outcome, severity, call-status, freshness and cache profile;
- no account, request/action identity, exception type or generic payload.

The alert scope is only `global_acra_rating_actions_feed`. Conditions are source
unavailable, cache unavailable, explicit stale exposure and failed refresh with
still-fresh fallback. State is bounded by thresholds, cooldown, retention,
capacity, recovery and out-of-order rejection.

### PR-98 bounded operations evidence

PR-98 composes the canonical PR-96 event and PR-97 evaluation under one internal
`RLock` and retains only terminal `fired` and `recovered` evidence.

Evidence contains:

- opaque evidence and correlation identifiers;
- UTC timestamp and canonical source event name;
- fixed global scope;
- operational kind, severity, occurrence count, threshold and safe error code;
- immutable false-valued privacy, delivery and trading flags.

Evidence excludes issuer, rating, outlook, action, release, publication date,
raw HTML, account, portfolio, broker payload, financial values and exception
text. Defaults are 86,400-second retention and capacity 64; both are bounded.
Oldest evidence is evicted at capacity, expired evidence is pruned, and `clear()`
resets evaluator plus evidence state. Process restart starts empty.

Optional event sink runs before evidence sinks for the same serialized call.
Sink exceptions are reduced to `sink_failure_count`; exception text is discarded
and already-recorded internal evidence is not erased.

## Compatibility and safety after PR-98

- `app:app` unchanged;
- 14 GET Actions unchanged: 13 authenticated and public health;
- no route, request body, public response field or frontend component;
- no dependency, database, secret or Render migration;
- no source/cache call, event emission, evaluation or sink invocation at startup;
- no webhook, email, Telegram, pager or external transport;
- no T-Invest call or broker write method;
- `trading_methods=false`.

## Frontend/owner discovery state

Repository search has not identified a registered existing frontend/dashboard
owner or production caller for the CBR/MOEX/ACRA fields. These packages do not
invent a duplicate UI, silently change an Action response or start network
calls. Exact owner discovery remains mandatory before production binding.

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

## Следующий пакет после PR-98

Следующий независимый безопасный пакет должен начинать второй фиксированный
контур российского кредитного рейтингового агентства только после проверки его
официального публичного endpoint и формата:

- один конкретный зарегистрированный CRA provider;
- один фиксированный HTTPS host/path и каноническая identity;
- issuer-level Russian national-scale actions only;
- отдельный agency-specific contract без сопоставления шкал с ACRA;
- bounded protected transport and fail-closed parsing;
- no generic caller-controlled URL, multi-agency adapter or hidden fallback;
- no route, Action, frontend field, startup call, external notification or
  broker method.

Если официальный стабильный источник не может быть подтверждён, пакет не должен
имитировать данные: блокируется реализация и фиксируется evidence о причине.

## Запрет ложного завершения

Проект не считается полностью завершённым только потому, что PR-98 слит и CI
зелёный. Полный релиз требует внешней Render/Gateway/GPT acceptance evidence,
точного production owner binding и завершения оставшихся master-plan блоков.
