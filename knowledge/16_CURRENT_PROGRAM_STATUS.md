# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-07-30  
Фактическая вершина программы после merge этого пакета: **PR-85**  
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
  lifecycle, single-flight refresh and no-silent-stale policy.

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

### Exact identity and lifecycle

- key: exact `(requested_from, requested_to)` range;
- default fresh TTL: 3600 seconds;
- default stale retention: 86400 seconds;
- default capacity: 16 ranges;
- fully expired entries are pruned and never returned;
- oldest ranges are evicted when capacity is exceeded;
- restart/`clear()` removes all entries;
- loader is lazy and startup performs no network call.

### Explicit status contract

`CbrKeyRateCacheResultV1` distinguishes:

- `fresh` — display permitted;
- `stale` — display permitted only after a failed refresh and explicit trusted
  `allow_stale=true`;
- `unavailable` — no snapshot or numeric display value.

Stale values are never silently presented as current. A failed forced refresh
while the existing entry is still fresh preserves an explicit fresh-cache
fallback with refresh failure metadata. Wrong type, wrong range, future source
time, unavailable source and loader exceptions fail closed with fixed codes.

### Single-flight and safety

A process-local `RLock` serializes lookup, refresh, publication, pruning and
eviction. Concurrent empty-cache reads perform one loader call. Only typed PR-84
snapshots are retained; raw XML, credentials, full account IDs and exception
text are absent.

- no FastAPI route, GPT Action or frontend field is added;
- no T-Invest call or broker write method is added;
- `app:app` and exactly 14 authenticated GET Actions remain unchanged;
- `trading_methods=false`.

## Frontend/owner discovery state

Repository search did not find a registered existing frontend/dashboard owner
for the key-rate field. PR-85 therefore does not invent a duplicate UI or
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

## Следующий пакет после PR-85

Ближайший безопасный шаг зависит от обнаружения существующего frontend/owner.
До этого нельзя создавать новый дублирующий кабинет или молча менять public
Action contract. Параллельно допустим следующий независимый production-source
пакет из master plan, если он сохраняет versioned contracts, provenance,
freshness, fail-closed behavior и read-only границы.

Production acceptance остаётся отдельным обязательным внешним блоком и не может
быть заменена локальными тестами.

## Запрет ложного завершения

Проект не считается полностью завершённым только потому, что PR-85 слит или CI
зелёный. Завершение разрешено объявлять только после всех согласованных пакетов,
production acceptance и отдельной проверки полного Definition of Done.
