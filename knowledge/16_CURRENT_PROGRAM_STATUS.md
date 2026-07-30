# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-07-30  
Фактическая вершина программы после merge этого пакета: **PR-92**  
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
- **PR-65…PR-73:** typed workflow bridge, producer, acquisition, production
  source store, calculator handoff и exact capacity-intent gate;
- **PR-74…PR-80:** allowlisted invocation, fixed providers, existing owners,
  scenario routing, one-shot composition, acquisition и installation;
- **PR-81…PR-83:** authenticated context, typed owner snapshots, one PR-80
  invocation and bounded redacted evidence;
- **PR-84…PR-88:** official CBR source, cache, safe observability, bounded alert
  policy и deterministic fired/recovered evidence lifecycle;
- **PR-89:** official public MOEX ISS TQBR quote source;
- **PR-90:** exact TQBR+SECID bounded quote cache and two-clock freshness;
- **PR-91:** pure safe MOEX source/cache observability without market payload;
- **PR-92:** bounded global MOEX operational alert policy.

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

## PR-84…PR-88 CBR lifecycle

### Official source

PR-84 provides the fixed Bank of Russia `DailyInfo.KeyRateXML` source with typed
Decimal observations, protected XML parsing, bounded HTTPS streaming and
redacted failures. Raw XML, fault text and exception text are not retained.

### Cache and freshness

PR-85 provides exact-range process-local state with fresh/stale/unavailable
semantics, single-flight refresh, retention/capacity bounds and no-silent-stale
policy. Stale display requires explicit trusted `allow_stale=true`.

### Observability, alerts and evidence

PR-86 maps source/cache states to allowlisted operational events without rate,
date-range, XML, account or upstream payload. PR-87 evaluates only those events
with consecutive operational thresholds, cooldown, recovery and bounded state;
there are no financial thresholds or notification transports. PR-88 composes the
existing typed results into deterministic event/evaluation and bounded
fired/recovered evidence, without source fetch at import/startup.

## PR-89 official MOEX ISS TQBR quote source v1

PR-89 adds one fixed read-only public source for Moscow Exchange
`stock/shares/TQBR` data:

- fixed `https://iss.moex.com` host, engine, market, board and JSON endpoint;
- caller controls only a strict normalized `SECID`;
- exact allowlisted `securities` and `marketdata` columns;
- exact single-row `SECID + TQBR` identity;
- direct Decimal parsing, duplicate-key rejection and no NaN/infinity;
- `SUR`/`RUB` normalization to `RUB`;
- positive finite prices, at least one price and bid ≤ ask;
- Moscow `SYSTIME` conversion to UTC with future-skew rejection;
- bounded HTTPS streaming, redirects disabled and `trust_env=false`;
- redacted unavailable results for network/HTTP/content/schema/identity/time/
  price failures;
- no raw JSON, upstream body, credentials or exception text retention.

The snapshot permanently declares public unauthenticated, potentially delayed,
not guaranteed real-time and informational-only data. It does not replace broker
`getMarketSnapshot`; values are never silently averaged.

## PR-90 MOEX quote cache v1

- exact process-local key `(TQBR, normalized SECID)`;
- default fresh TTL 60 seconds, stale retention 900 seconds, capacity 64;
- cache TTL derives from `snapshot.retrieved_at`;
- user-visible market age derives from `snapshot.quote.as_of`;
- one `RLock` provides single-flight refresh and atomic prune/store/evict/clear;
- explicit fresh, stale and unavailable result contract;
- stale is exposed only after refresh failure and trusted `allow_stale=true`;
- wrong type/identity/future/source data fail closed;
- process state is empty after restart.

No network call occurs at import/startup. Only typed PR-89 snapshots are retained.

## PR-91 safe MOEX observability v1

PR-91 builds immutable events from already-produced PR-89/90 typed results.

Supported mappings:

- source available/unavailable;
- fresh cache hit with external call `not_called`;
- successful refresh;
- failed refresh while still-fresh cached data remains usable;
- explicit stale exposure;
- unavailable cache result.

Events contain safe status, latency, freshness, refresh and boolean/count metadata
only. They contain no price, bid, ask, spread, currency, SECID, short name,
instrument key, lot metadata, market timestamp, age, account value, cash, raw
JSON, credentials, exception type or exception text.

Builders are pure: no automatic emission, logger/sink registration, route,
startup fetch or broker call.

Regression Shield #575 on the exact PR-91 final head passed:

- 912 tests, 0 failures/errors/skips;
- mypy: 168 source files;
- line coverage 66.3%, branch coverage 48.85%;
- compile, Ruff, formatting, stable entrypoint, 14-GET release contract,
  dependency audit, SAST and secret scan passed.

## PR-92 global MOEX operational alert policy v1

### Identity boundary

The immutable scope is `global_moex_tqbr_feed`. PR-91 deliberately excludes
SECID and account identity, so PR-92 cannot represent per-instrument alerts and
cannot reconstruct identity from correlation IDs, errors, logs or hidden state.

### Canonical event gate

Known PR-91 event names are accepted only when the full allowlisted shape matches:

- exact event/component/provider/operation;
- exact safe metric-name set;
- fixed public/delayed/non-realtime/informational flags;
- allowed outcome/severity/external-call/freshness profile;
- no account, request/action identity, quality/completeness or exception payload.

A forged same-name event fails closed with `MOEX_ALERT_EVENT_CONTRACT_INVALID`.
Unrelated event names are ignored without state.

### Conditions and state

Operational conditions only:

- source unavailable;
- cache unavailable;
- stale value explicitly exposed;
- refresh failed while fresh cached data remains displayable.

Defaults:

- thresholds: 3 / 2 / 2 / 3 consecutive occurrences;
- cooldown 900 seconds;
- retention 86400 seconds;
- capacity exactly four global alert kinds;
- saturating counters and one process-local `RLock`.

Dispositions are `ignored`, `pending`, `fired`, `suppressed_cooldown` and
`recovered`. Out-of-order matching events fail closed. Pending state expires by
retention; active state is preserved through cooldown; restart starts empty.

There are no price, spread, return, volatility, volume, liquidity or portfolio
thresholds. There is no webhook, email, Telegram, pager, external notification,
evidence store or automatic emission.

## Compatibility and safety after PR-92

- `app:app` unchanged;
- exactly 14 authenticated GET Actions unchanged;
- no route, request body, public response field or frontend component added;
- no dependency, secret, database or Render migration required;
- no source/cache call at import/startup;
- no T-Invest call or broker write method added;
- `trading_methods=false`.

## Frontend/owner discovery state

Repository search did not find a registered existing frontend/dashboard owner or
production caller for the CBR/MOEX fields. PR-84…PR-92 therefore do not invent a
duplicate UI, silently change an Action response or start network calls. The exact
existing caller/owner must be located before production binding.

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

- build bounded MOEX fired/recovered evidence lifecycle over PR-91/92;
- locate the exact existing CBR/MOEX caller/owner and register lifecycle lazily
  without startup fetch or public API change;
- define operator-facing retention/acceptance and any later external routing;
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

## Следующий пакет после PR-92

Ближайший независимый безопасный пакет — bounded MOEX operations evidence
lifecycle v1:

- compose already-produced typed source/cache result → PR-91 event → PR-92
  evaluation;
- persist only fired/recovered global operational evidence;
- deterministic event-sink then evidence-sink ordering;
- bounded retention/capacity, pruning, eviction and restart-clear behavior;
- no SECID, price, account, raw payload or exception text;
- no external notification transport, route, Action, startup source call or
  broker method.

Production acceptance remains a separate mandatory external block and cannot be
replaced by local tests.

## Запрет ложного завершения

Проект не считается полностью завершённым только потому, что PR-92 слит и CI
зелёный. Полный релиз требует внешней Render/Gateway/GPT acceptance evidence,
точного production owner binding и завершения оставшихся master-plan блоков.
