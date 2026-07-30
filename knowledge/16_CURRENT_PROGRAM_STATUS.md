# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-07-30  
Фактическая вершина программы после merge этого пакета: **PR-93**  
Точная версия определяется текущей вершиной ветки `main`.

## Назначение документа

Это оперативная карта программы. Код в `main` остаётся окончательным источником
истины; стратегические правила и Definition of Done определяются `AGENTS.md`,
`knowledge/00_PROJECT_MASTER_CONTEXT.md` и исходным master plan.

## Неизменяемые границы

- `trading_methods=false`;
- пользовательские Gateway Actions только `GET`;
- ровно 14 authenticated Actions;
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
- **PR-89:** official public MOEX ISS TQBR quote source;
- **PR-90:** exact TQBR+SECID bounded quote cache and two-clock freshness;
- **PR-91:** pure safe MOEX source/cache observability without market payload;
- **PR-92:** bounded global MOEX operational alert policy;
- **PR-93:** deterministic bounded global MOEX operations evidence lifecycle.

## PR-81…PR-83 authenticated owner lifecycle

Existing Bearer auth and exact compact-response validation create a trusted
server context. A fresh typed Decision/intent/capacity/pro-forma snapshot is
selected by exact scenario, correlation, operation and masked account, rebound
to existing owner ports and invoked at most once. Bounded redacted evidence is
retained. Startup performs no owner, calculator, portfolio, network or broker
call. Public response and OpenAPI remain unchanged.

## PR-84…PR-88 CBR lifecycle

PR-84 provides the fixed Bank of Russia `DailyInfo.KeyRateXML` source with typed
Decimal observations, protected XML parsing, bounded HTTPS streaming and
redacted failures. PR-85 adds exact-range fresh/stale/unavailable cache state,
single-flight refresh and no-silent-stale policy. PR-86 emits allowlisted
operational metadata without rate, date range, XML, account or upstream text.
PR-87 evaluates operational conditions only with bounded thresholds, cooldown
and recovery. PR-88 deterministically retains fired/recovered evidence without
source fetch at import/startup.

## PR-89 MOEX ISS TQBR source

PR-89 adds one fixed read-only public Moscow Exchange source for
`stock/shares/TQBR`:

- fixed official HTTPS host, engine, market, board and endpoint;
- strict normalized SECID before network access;
- allowlisted `securities` and `marketdata` table shapes;
- exact SECID/TQBR identity;
- Decimal parsing, duplicate-key rejection and no NaN/infinity;
- SUR/RUB normalization, positive finite prices and bid ≤ ask;
- Moscow `SYSTIME` to UTC with future-skew rejection;
- bounded streaming and redacted unavailable results;
- no raw JSON, credentials, upstream body or exception text retention.

The snapshot permanently marks the public feed as unauthenticated, potentially
delayed, not guaranteed real-time and informational-only. Broker
`getMarketSnapshot` remains primary for execution-style calculations.

## PR-90 MOEX cache

- exact process-local key `(TQBR, normalized SECID)`;
- fresh TTL 60 seconds, stale retention 900 seconds, capacity 64;
- cache TTL derives from retrieval time;
- displayed market age derives from `quote.as_of`;
- single-flight refresh under one `RLock`;
- stale exposure only after refresh failure and explicit trusted policy;
- wrong type/identity/future data fail closed;
- restart starts empty and import performs no network call.

## PR-91 safe MOEX observability

PR-91 maps already-produced source/cache results to immutable operational events:
source available/unavailable, fresh hit, successful refresh, failed refresh with
fresh fallback, explicit stale and unavailable cache.

Events contain safe status, latency, freshness, refresh and boolean/count metadata
only. They contain no price, bid, ask, spread, currency, SECID, short name,
instrument key, lot metadata, market timestamp, age, account value, cash, raw
JSON, credentials, exception type or exception text. Builders are pure and do
not emit, fetch, register routes or call a broker.

## PR-92 global MOEX alert policy

The immutable scope is `global_moex_tqbr_feed`. PR-91 deliberately excludes
SECID/account identity, so PR-92 cannot represent per-instrument alerts or
reconstruct identity from correlation IDs, logs, error text or hidden state.

Known PR-91 event names pass only through a full canonical gate: exact component,
provider, operation, safe metric set, feed flags and allowed status profile. A
forged same-name event fails closed.

Operational conditions:

- source unavailable;
- cache unavailable;
- stale value explicitly exposed;
- refresh failed while fresh cached data remains usable.

State is bounded to four global kinds with consecutive thresholds, pending,
fired, cooldown suppression and recovery. Out-of-order matching events fail
closed. There are no financial thresholds, evidence store or external
notification transport in PR-92.

Regression Shield #584 on the exact PR-92 final head passed:

- 925 tests, 0 failures/errors/skips;
- mypy: 170 source files;
- line coverage 66.3%, branch coverage 48.85%;
- compile, Ruff, formatting, stable entrypoint, 14-GET release contract,
  dependency audit, SAST and secret scan passed.

## PR-93 MOEX operations evidence lifecycle

### Deterministic composition

For one typed PR-89 source snapshot or PR-90 cache result:

1. build one canonical PR-91 event;
2. evaluate it with PR-92;
3. retain only `fired` and `recovered` evaluations;
4. invoke the event sink first and evidence sinks second;
5. return one immutable batch with redacted sink-failure count.

One lifecycle `RLock` covers pruning, alert-state mutation, evidence recording
and sink invocation, so concurrent calls cannot emit evidence before its event.

### Evidence boundary

Evidence stores only opaque IDs, recorded timestamp, canonical event name, fixed
global scope, operational kind/severity/disposition, counters, threshold and
safe error code. Pending, ignored and cooldown-suppressed state cannot be stored.

Evidence cannot represent SECID, instrument/board/lot identity, price, bid, ask,
spread, currency, market timestamp, age, account, position, cash, raw JSON,
credential, exception payload, trading authorization or notification state.

### Retention and sinks

- default retention 86400 seconds, allowed 60…604800;
- default capacity 64, allowed 1…256;
- prune on read/observe, oldest eviction, restart-empty and clear behavior;
- optional typed event/evidence sinks;
- sink errors become only `sink_failure_count`;
- no automatic retry or external transport.

## Compatibility and safety after PR-93

- `app:app` unchanged;
- exactly 14 authenticated GET Actions unchanged;
- no route, request body, public response field or frontend component;
- no dependency, database, secret or Render migration;
- no source/cache call at import/startup;
- no T-Invest call or broker write method;
- `trading_methods=false`.

## Frontend/owner discovery state

Repository search did not find a registered existing frontend/dashboard owner or
production caller for the CBR/MOEX fields. PR-84…PR-93 therefore do not invent a
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

- locate the exact existing CBR/MOEX caller and bind lifecycles lazily;
- define operator-facing retention/acceptance and any later external routing;
- build production-grade official ratings, news and corporate-event ingestion;
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

## Следующий пакет после PR-93

Ближайший независимый безопасный пакет — official credit-rating source boundary
v1 из master plan:

- fixed allowlisted official/recognized rating sources;
- typed issuer/rating/action/outlook/source-date contracts;
- strict identity and freshness semantics;
- bounded transport and fail-closed parsing;
- no generic URL, user-supplied host or free-form instructions;
- no route, Action, frontend field, startup call or broker method until an exact
  owner is identified.

## Запрет ложного завершения

Проект не считается полностью завершённым только потому, что PR-93 слит и CI
зелёный. Полный релиз требует внешней Render/Gateway/GPT acceptance evidence,
точного production owner binding и завершения оставшихся master-plan блоков.
