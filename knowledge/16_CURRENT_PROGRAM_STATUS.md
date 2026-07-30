# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-07-30  
Фактическая вершина программы после merge этого пакета: **PR-88**  
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
  fired/recovered evidence lifecycle with safe sink handoff.

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

## PR-87 bounded CBR alert policy v1

PR-87 evaluates only the allowlisted PR-86 source/cache events. It does not
inspect the key-rate value and does not send notifications.

- conditions: source unavailable, cache unavailable, explicit stale exposure and
  refresh failure while fresh cached data remains usable;
- immutable typed policy/evaluation contracts;
- consecutive status/count thresholds only, never financial thresholds;
- `pending`, `fired`, `suppressed_cooldown`, `recovered` and `ignored` states;
- default cooldown 900 seconds and retention 86400 seconds;
- pending state expires by retention;
- active state cannot be forgotten before cooldown ends;
- bounded process-local state with capacity 4 and saturating counters;
- one `RLock` protects evaluation, pruning, recovery and clear;
- out-of-order matching events fail closed;
- no webhook, email, Telegram, pager or external alert transport.

Alert evaluations contain no rate, date range, XML, account, exception text,
broker payload or trading authorization. `trading_methods=false` is immutable.

## PR-88 CBR operations evidence lifecycle v1

PR-88 composes already-produced typed PR-84/85 results with PR-86 and PR-87. It
does not fetch the source or refresh the cache at import/startup.

### Deterministic lifecycle

1. accept one typed source snapshot or cache result;
2. build one allowlisted PR-86 event;
3. evaluate it using PR-87;
4. persist only `fired` and `recovered` evidence;
5. call the safe event sink first and evidence sinks second;
6. return one immutable internal batch with a redacted sink-failure count.

One lifecycle `RLock` is retained through state mutation and sink invocation so
concurrent calls cannot reorder event/evidence emission relative to alert-state
evaluation.

### Evidence boundary

`CbrKeyRateAlertEvidenceV1` stores only opaque IDs, timestamp, source event name,
kind, severity, fired/recovered disposition, counters, threshold and safe error
code. It cannot represent pending, ignored or cooldown-suppressed state.

Defaults and bounds:

- evidence retention 86400 seconds, allowed 60…604800;
- evidence capacity 64, allowed 1…256;
- oldest eviction, read/observe pruning and restart/clear behavior;
- optional typed event/evidence sinks;
- sink exceptions become only `sink_failure_count`, never exception text.

No rate, date range, XML, account, money, broker payload, secret, exception text
or trading authorization enters evidence. There is no automatic retry or
outbound notification transport.

### Compatibility and safety

- `app:app` remains unchanged;
- exactly 14 authenticated GET Actions remain unchanged;
- no route, request body, public response field or frontend component is added;
- no source fetch/cache refresh during module import or application startup;
- no T-Invest call or broker write method is added;
- no dependency, secret, database or Render migration is required;
- `trading_methods=false`.

## Frontend/owner discovery state

Repository search did not find a registered existing frontend/dashboard owner
or production caller for the key-rate field. PR-84…PR-88 therefore do not invent
a duplicate UI, silently change an Action response or start network calls. The
existing source/caller must first be located and registered before production
binding is safe.

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

- locate the exact existing CBR caller/owner and register PR-88 lazily without a
  startup fetch or public API change;
- define operator-facing runbook/retention acceptance for fired/recovered
  evidence and any later external routing;
- locate the exact existing macro/dashboard owner or frontend source, then bind
  the PR-85 result with explicit fresh/stale/unavailable presentation;
- production-grade quote, rating, news and corporate-event ingestion;
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

## Следующий пакет после PR-88

Production registration PR-88 разрешена только после обнаружения точного
существующего CBR caller/owner. До этого ближайшие независимые безопасные блоки:

- production-grade MOEX quote source with provenance/freshness/fail-closed
  contracts, without changing Actions;
- operator runbook for PR-84…PR-88 evidence and recovery semantics;
- continued frontend source discovery without creating a duplicate site.

Production acceptance remains a separate mandatory external block and cannot be
replaced by local tests.

## Запрет ложного завершения

Проект не считается полностью завершённым только потому, что PR-88 слит или CI
зелёный. Завершение разрешено объявлять только после всех согласованных пакетов,
production acceptance и отдельной проверки полного Definition of Done.
