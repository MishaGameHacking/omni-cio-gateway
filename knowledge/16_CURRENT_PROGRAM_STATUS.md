# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-07-30  
Фактическая вершина программы после merge этого пакета: **PR-86**  
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
  date-range, XML, account or upstream exception payloads.

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

### Source events

- available source: success/info with official provider, operation, optional
  latency, `fresh` status and safe observation/source-available counts;
- unavailable source: failure/error with one fixed source error code;
- no observation value, effective date, requested range, XML, fault text,
  exception text or account context.

### Cache events

- fresh cache hit: success/info and external call `not_called`;
- successful refresh: success/info and external call `success`;
- failed force refresh with still-fresh cached data: degraded/warning while
  freshness remains `fresh`;
- explicit stale exposure: degraded/warning with freshness `stale`;
- unavailable: failure/error with no displayable value.

Metrics are limited to safe counts/booleans: observation count, cache hit,
refresh attempted/succeeded, stale exposed and display allowed. The key-rate
value and date range are never metrics or event fields.

### Compatibility and safety

- builders are pure and do not emit automatically;
- existing `ObservabilityEventV1`, `ExternalCallTelemetryV1` and
  `build_safe_event` are reused;
- no HTTP route, GPT Action, request body or frontend field is added;
- no T-Invest call or broker write method is added;
- `app:app` and exactly 14 authenticated GET Actions remain unchanged;
- `trading_methods=false`.

## Frontend/owner discovery state

Repository search did not find a registered existing frontend/dashboard owner
for the key-rate field. PR-84…PR-86 therefore do not invent a duplicate UI or
silently change an Action response. The deployed frontend source must first be
located and registered before a UI binding package is safe.

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

These cases cannot be marked passed solely because CI is green. Current tool
access has not supplied all required Render/GPT evidence.

## Что остаётся до полного релиза

### Backend and operations

- define exact PR-84/85 telemetry emission points, bounded retention and
  rate-limited alert policy for repeated unavailable/stale outcomes;
- locate the exact existing macro/dashboard owner or frontend source, then bind
  the PR-85 cache result with explicit fresh/stale/unavailable presentation;
- production-grade quote, rating, news and corporate-event ingestion;
- actual Render/Gateway acceptance and evidence recording;
- actual GPT Editor import and authenticated Preview;
- external versioned RAG with freshness and citation controls;
- expanded observability, alerting and operational runbooks.

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

## Следующий пакет после PR-86

Ближайший независимый operations gap — bounded alert policy над typed PR-86
events:

- thresholds only from status/count windows, never financial values;
- deduplication, cooldown and bounded process-local state;
- no outbound webhook or external service until separately configured;
- safe alert evidence without account, XML or exception payload;
- no public Action change.

Frontend binding remains blocked until the existing source/owner is located.
Production acceptance remains a separate mandatory external block and cannot be
replaced by local tests.

## Запрет ложного завершения

Проект не считается полностью завершённым только потому, что PR-86 слит или CI
зелёный. Завершение разрешено объявлять только после всех согласованных пакетов,
production acceptance и отдельной проверки полного Definition of Done.
