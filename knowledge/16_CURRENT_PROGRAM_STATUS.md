# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-07-30  
Фактическая вершина программы после merge этого пакета: **PR-84**  
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
- **PR-81:** authenticated route-context derivation и bounded capture;
- **PR-82:** exact typed owner snapshots и fresh invocation rebinding;
- **PR-83:** post-auth snapshot selection, one PR-80 invocation и bounded
  redacted internal evidence;
- **PR-84:** official Bank of Russia key-rate source v1 with immutable macro
  contracts, bounded HTTPS streaming and protected XML parsing.

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

PR-84 creates a trusted internal source for the key-rate block that previously
could remain unavailable or display dashes.

### Fixed source identity

- provider: Bank of Russia;
- service: `DailyInfo`;
- operation/source ID: `KeyRateXML` / `DailyInfo.KeyRateXML`;
- fixed HTTPS endpoint and SOAPAction;
- source authority: `official`.

Endpoint, operation and provider cannot be supplied from an Action, document,
environment variable or user payload.

### Typed contract

`CbrKeyRateSnapshotV1` retains only:

- requested date range and UTC retrieval time;
- `available`/`unavailable` status;
- official provenance when available;
- unique effective-date observations using exact `Decimal` rates;
- latest observation in the requested range;
- a bounded safe error code and warnings.

Available snapshots require an official source and exact latest-row parity.
Unavailable snapshots cannot retain source data or observations.

### Transport and XML security

- TLS verification and redirects disabled for owned transport;
- timeout and requested range bounded;
- XML/SOAP content type required;
- `Content-Length` and streamed decoded bytes checked before parsing;
- raw XML never enters the contract or repository;
- `DOCTYPE`, entity declarations and external entities rejected;
- parser uses a direct `pyexpat` tree builder with parameter entities disabled;
- nested and escaped XMLDocument forms supported;
- malformed XML, SOAP Fault, empty result, range mismatch and conflicting
  duplicate dates fail closed with fixed error codes;
- upstream body, fault and exception text are not exposed.

Draft CI originally rejected `ElementTree.fromstring` with Bandit B314. The
parser was replaced, not suppressed, and the repeated security run passed.

### Compatibility

- no FastAPI route, GPT Action or dashboard field is added in PR-84;
- no dependency or secret is added;
- no T-Invest call or broker write method is added;
- `app:app` and exactly 14 authenticated GET Actions remain unchanged;
- `trading_methods=false`.

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

- integrate the typed PR-84 snapshot into the exact existing macro/dashboard
  owner with explicit cache, freshness and unavailable-display semantics;
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

## Следующий пакет после PR-84

Ближайший доказанный backend gap — интеграция typed key-rate snapshot в один
точно выбранный существующий owner:

- bounded cache and freshness policy;
- explicit available/stale/unavailable presentation;
- no silent reuse of an expired value;
- no mixing with broker-account or market-price facts;
- no public Action change unless separately versioned and accepted.

Production acceptance остаётся параллельным обязательным внешним блоком и не
может быть заменена локальными тестами.

## Запрет ложного завершения

Проект не считается полностью завершённым только потому, что PR-84 слит или CI
зелёный. Завершение разрешено объявлять только после всех согласованных пакетов,
production acceptance и отдельной проверки полного Definition of Done.
