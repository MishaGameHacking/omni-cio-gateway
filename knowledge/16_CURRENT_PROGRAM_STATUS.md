# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-07-30  
Фактическая вершина программы после merge этого пакета: **PR-90**  
Точная версия определяется текущей вершиной ветки `main`.

## Назначение документа

Это оперативная карта программы. Код в `main` остаётся окончательным источником
истины; стратегические правила и Definition of Done определяются `AGENTS.md`,
`knowledge/00_PROJECT_MASTER_CONTEXT.md` и исходным master plan.

## Неизменяемые границы

- `trading_methods=false`;
- пользовательские Gateway Actions только `GET`;
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
- **PR-65…PR-73:** typed workflow bridge, producer, acquisition, production
  source store, calculator handoff и exact capacity-intent gate;
- **PR-74…PR-80:** allowlisted invocation, fixed providers, existing owners,
  scenario routing, one-shot composition, acquisition и installation;
- **PR-81…PR-83:** authenticated context, typed owner snapshots, one PR-80
  invocation and bounded redacted evidence;
- **PR-84:** official Bank of Russia key-rate source with immutable Decimal
  contracts, bounded HTTPS streaming and protected XML parsing;
- **PR-85:** exact-range bounded cache with explicit fresh/stale/unavailable
  lifecycle, single-flight refresh and no-silent-stale policy;
- **PR-86:** allowlisted source/cache observability events without key-rate,
  date-range, XML, account or upstream exception payloads;
- **PR-87:** bounded CBR alert-policy evaluator with consecutive thresholds,
  deduplication, cooldown, recovery and retention/capacity guards;
- **PR-88:** deterministic typed source/cache event → evaluation → bounded
  fired/recovered evidence lifecycle with safe sink handoff;
- **PR-89:** fixed official public MOEX ISS TQBR quote source with strict
  JSON/identity/Decimal/time validation and delayed informational-feed flags;
- **PR-90:** exact TQBR+SECID bounded quote cache with two-clock freshness,
  single-flight refresh and explicit no-silent-stale policy.

## PR-81…PR-83 authenticated owner lifecycle

1. Existing Bearer auth and exact compact-response validation create one trusted
   server context.
2. One fresh typed Decision/intent/capacity/pro-forma/directional snapshot is
   selected by exact scenario, trusted correlation, operation and masked account.
3. Snapshot owner ports bind only to the fresh server-generated invocation.
4. PR-80 is invoked at most once.
5. Acquired/unavailable/redacted-failed evidence is retained in a bounded
   process-local store.

Startup performs no owner, calculator, portfolio, network or broker call.
Public response and OpenAPI remain unchanged.

## PR-84 official CBR key-rate source v1

PR-84 provides a trusted internal Bank of Russia `DailyInfo.KeyRateXML` source:

- fixed official endpoint, SOAPAction and source identity;
- typed `Decimal` effective-date observations;
- TLS verification, redirects disabled, bounded timeout/range/content type;
- `Content-Length` and streamed byte limits before parsing;
- protected `pyexpat` parser rejecting DTD/entity/external entities;
- nested and escaped XMLDocument support;
- fixed redacted network/HTTP/XML/range/duplicate error codes;
- no raw XML, upstream body, fault or exception storage.

The first draft parser was blocked by Bandit B314 and replaced rather than
suppressed. PR-84 added no route, Action, dependency or broker call.

## PR-85 CBR key-rate cache lifecycle v1

PR-85 adds an internal process-local lifecycle over the PR-84 typed source.

- exact `(requested_from, requested_to)` cache identity;
- default fresh TTL 3600 seconds, stale retention 86400 seconds and capacity 16;
- fully expired pruning, LRU-style oldest eviction and restart/clear behavior;
- lazy loader and single-flight refresh under a process-local `RLock`;
- explicit `fresh`, `stale`, `unavailable` result contract;
- stale display only after failed refresh and explicit trusted `allow_stale=true`;
- failed forced refresh while cached data is still fresh remains an explicit
  fresh-cache fallback with redacted refresh error metadata;
- wrong type/range/future source data and loader/source failures fail closed.

Only typed PR-84 snapshots are retained. No raw XML, credentials, full account
IDs or exception text enter the cache.

## PR-86 safe CBR observability v1

PR-86 maps PR-84/85 typed results to the existing immutable observability
contracts.

- available source: success/info with official provider and safe counts;
- unavailable source: failure/error with one fixed source error code;
- fresh cache hit: success/info and external call `not_called`;
- successful refresh: success/info and external call `success`;
- failed force refresh with still-fresh data: degraded/warning;
- explicit stale exposure: degraded/warning with freshness `stale`;
- unavailable: failure/error with no displayable value.

Metrics contain only safe counts/booleans. The key-rate value, date range, XML,
fault text, exception text and account context never enter telemetry.

## PR-87 bounded CBR alert policy v1

PR-87 evaluates only allowlisted PR-86 source/cache events.

- conditions: source unavailable, cache unavailable, explicit stale exposure and
  refresh failure while fresh cached data remains usable;
- immutable typed policy/evaluation contracts;
- consecutive status/count thresholds only, never financial thresholds;
- `pending`, `fired`, `suppressed_cooldown`, `recovered` and `ignored` states;
- pending state expires by retention;
- active state cannot be forgotten before cooldown ends;
- bounded process-local state, saturating counters and one `RLock`;
- out-of-order matching events fail closed;
- no webhook, email, Telegram, pager or external alert transport.

## PR-88 CBR operations evidence lifecycle v1

PR-88 composes already-produced PR-84/85 results with PR-86 and PR-87. It does
not fetch the source or refresh the cache at import/startup.

1. accept one typed source snapshot or cache result;
2. build one allowlisted event;
3. evaluate it using PR-87;
4. persist only `fired` and `recovered` evidence;
5. call the safe event sink first and evidence sinks second;
6. return an immutable batch with a redacted sink-failure count.

A lifecycle `RLock` prevents concurrent event/evidence reordering. Evidence is
bounded, process-local and contains no rate, dates, XML, account, money, broker
payload, secret, exception text or trading authorization.

## PR-89 official MOEX ISS TQBR quote source v1

PR-89 adds one internal source for public Moscow Exchange ISS data on the fixed
`stock/shares/TQBR` board.

### Source and schema boundary

- fixed `https://iss.moex.com` host, engine, market, board and JSON endpoint;
- caller controls only a strict validated `SECID`;
- exact allowlisted `securities` and `marketdata` columns;
- exact single-row `SECID + TQBR` identity in both tables;
- direct JSON Decimal parsing, duplicate-key rejection and no NaN/infinity;
- `SUR`/`RUB` normalization to `RUB`;
- positive finite `LAST`/`BID`/`OFFER`, at least one price and bid ≤ ask;
- Moscow `SYSTIME` conversion to UTC with future-skew rejection;
- existing `MarketSourceV1` and `MarketQuoteV1` contracts reused.

### Transport and failure behavior

- HTTPS/TLS verification, redirects disabled and `trust_env=false`;
- no Authorization/Cookie headers or broker credentials;
- bounded timeout, `Content-Length` and streamed response size;
- only JSON content types accepted;
- network/HTTP/content/schema/identity/time/price failures return one redacted
  unavailable snapshot;
- raw JSON, upstream body and exception text are never retained.

The snapshot permanently declares public unauthenticated, potentially delayed,
not guaranteed real-time and informational-only data. It does not replace broker
`getMarketSnapshot`; values from the two sources are never silently averaged.

## PR-90 MOEX ISS TQBR quote cache v1

PR-90 adds one internal bounded lifecycle over PR-89.

### Identity and defaults

- exact process-local key `(TQBR, normalized SECID)`;
- default fresh TTL 60 seconds;
- stale retention 900 seconds;
- capacity 64 exact identities;
- future tolerance 30 seconds;
- bounded configuration and restart-clear state.

### Two-clock freshness

- `fresh_until` and `stale_until` are derived from `snapshot.retrieved_at` and
  control source-request frequency/retention;
- `age_seconds` is derived from `snapshot.quote.as_of` and represents actual
  market-observation age;
- a newly retrieved HTTP response therefore cannot hide old market data;
- delayed/non-realtime/informational source flags remain immutable.

### State behavior

- `fresh`: successful refresh, ordinary cache hit, or explicit still-fresh
  fallback after failed force refresh;
- `stale`: only after refresh failure and trusted `allow_stale=true`;
- `unavailable`: no snapshot is exposed when cache is empty/expired, stale is not
  allowed, or type/identity/future/source validation fails;
- stale is never shown silently;
- newly loaded already-old data follows the same stale policy;
- one `RLock` provides single-flight refresh and atomic prune/store/evict/clear;
- oldest entries are evicted and fully expired entries are removed.

The typed result contract rejects impossible time/state/refresh combinations.
Only typed PR-89 snapshots are retained; no raw JSON, credentials, account data
or exception text enter the cache.

### Compatibility and safety

- `app:app` remains unchanged;
- exactly 14 authenticated GET Actions remain unchanged;
- no route, request body, public response field or frontend component is added;
- no network call occurs at import/startup;
- no dependency, secret, database or Render migration is required;
- no T-Invest call or broker write method is added;
- `trading_methods=false`.

## Frontend/owner discovery state

Repository search did not find a registered existing frontend/dashboard owner
or production caller for the CBR or MOEX fields. PR-84…PR-90 therefore do not
invent a duplicate UI, silently change an Action response or start network calls.
The exact existing source/caller must be located before production binding.

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

Green CI cannot mark these cases passed. Current tool access has not supplied all
required Render/GPT evidence.

## Что остаётся до полного релиза

### Backend and operations

- add safe MOEX source/cache observability without price values;
- locate the exact existing CBR caller/owner and register PR-88 lazily without a
  startup fetch or public API change;
- define operator-facing retention/acceptance for CBR fired/recovered evidence;
- locate the exact existing macro/dashboard owner, then bind CBR/MOEX results
  with explicit freshness and source presentation;
- production-grade rating, news and corporate-event ingestion;
- actual Render/Gateway acceptance and evidence recording;
- actual GPT Editor import and authenticated Preview;
- external versioned RAG with freshness and citation controls;
- expanded operational runbooks and production monitoring acceptance.

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

## Следующий пакет после PR-90

Ближайший независимый безопасный пакет — MOEX source/cache observability v1:

- allowlisted status, latency, refresh and freshness metadata only;
- market price values and raw JSON never enter telemetry;
- explicit public/delayed/non-realtime source flags;
- safe source/cache error codes and count metrics;
- no route, Action, frontend field, startup network call or broker method.

Production acceptance remains a separate mandatory external block and cannot be
replaced by local tests.

## Запрет ложного завершения

Проект не считается полностью завершённым только потому, что PR-90 слит или CI
зелёный. Завершение разрешено объявлять только после всех согласованных пакетов,
production acceptance и отдельной проверки полного Definition of Done.
