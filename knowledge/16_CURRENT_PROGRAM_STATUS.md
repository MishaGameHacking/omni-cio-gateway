# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-07-30  
Фактическая вершина программы после merge этого пакета: **PR-83**  
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

- **PR-50:** unified homogeneous buy/sell pre-trade review;
- **PR-51:** account-aware risk/pre-trade explanation envelope;
- **PR-52:** tamper-evident pro-forma risk/intention binding;
- **PR-53:** compact user-safe final response and shadow parity;
- **PR-54:** release eligibility and canonical response SHA-256;
- **PR-55:** private GET Action candidate and OpenAPI shadow;
- **PR-56:** exact eight-query input binding;
- **PR-57:** production-route readiness dossier;
- **PR-58:** implementation plan and acceptance matrix;
- **PR-59:** route-handler shadow and safe observability;
- **PR-60:** isolated FastAPI HTTP integration candidate;
- **PR-61:** production private `GET /decision/final-review` and bounded registry;
- **PR-62:** trusted process-local publisher;
- **PR-63:** end-to-end internal composition and fail-closed publication;
- **PR-64:** production-acceptance evidence contract and offline collector;
- **PR-65:** production-importable typed workflow bridge;
- **PR-66:** live read-only workflow producer;
- **PR-67:** acquisition-outcome coordinator;
- **PR-68:** typed source acquisition adapter;
- **PR-69:** production scenario store and live current-risk wiring;
- **PR-70:** lazy production registration;
- **PR-71:** trusted typed scenario publication;
- **PR-72:** calculator-owned purchase/sell preview handoff;
- **PR-73:** exact capacity-intent gate construction;
- **PR-74:** allowlisted, freshness/replay-safe invocation boundary;
- **PR-75:** fixed typed calculator-provider registry;
- **PR-76:** adapters from existing read-only calculator owners;
- **PR-77:** scenario-scoped production owner routing;
- **PR-78:** trusted one-shot owner composition and cleanup;
- **PR-79:** approved server-context acquisition of exact fresh owner leases;
- **PR-80:** one-shot installation of typed owners into PR-79;
- **PR-81:** authenticated route-context derivation and bounded capture;
- **PR-82:** exact typed owner snapshots and fresh invocation rebinding;
- **PR-83:** post-auth snapshot selection, one PR-80 invocation and bounded internal evidence.

## PR-78…PR-80 owner boundary

PR-78 materializes Decision, intent, capacity, explicit pro-forma scenario and
one directional preview set exactly once. It revalidates masked account,
scenario, correlation, option, direction, intent fingerprint, request coverage,
freshness and conservative no-margin/no-short/no-derivatives policy.

PR-79 obtains these owners only through server-owned typed loaders and maps
missing, failed, stale or mismatched evidence to `unavailable` with the existing
safe handler enums. PR-80 installs one typed purchase or sell owner bundle into
one PR-79 call; the opposite direction remains uninstalled.

## PR-81 authenticated context

A context is created only after existing Bearer auth, exact registry lookup and
successful compact-response validation. Identity is retained from trusted
publication, not reconstructed from query values:

- exact scenario ID;
- trusted correlation ID;
- purchase/sell operation;
- masked account;
- server-generated invocation ID and timestamp.

Context capture is process-local, bounded and limited to 300 seconds. Startup
context count is zero.

## PR-82 exact owner snapshots

Snapshot is created only after successful allowlisted calculator invocation and
trusted scenario publication. It retains typed `DecisionSetV1`, exact intent,
capacity assessments, explicit `ProFormaRiskScenarioV1` and one directional
preview set.

Selection key:

```text
scenario_id + trusted correlation_id + operation + masked account
```

The old calculator invocation ID is never reused. Owner ports are rebound to
the fresh authenticated `context.invocation_request()` and reject any other
request. Missing, expired, stale or mismatched snapshots do not fabricate
owners.

## PR-83 authenticated owner installation

PR-83 completes the internal backend connection between PR-81, PR-82 and PR-80:

1. authenticated context is captured;
2. one exact fresh snapshot is selected;
3. purchase or sell is selected only from typed context operation;
4. PR-80 is invoked at most once;
5. acquired/unavailable/redacted-failed outcome is saved in a bounded evidence store.

The evidence store retains only server-derived identifiers, typed status/error
enums and safety flags. It does not retain credentials, full account IDs, raw
Action payloads or exception text.

### Runtime behavior

- context and evidence TTL: 300 seconds;
- default capacity: 64;
- restart clears context, snapshot and evidence stores;
- production registration is idempotent for the exact bridge/runtime;
- startup performs zero snapshot selection, installation, acquisition,
  calculator, portfolio, network or broker calls;
- compact final-review response and OpenAPI are unchanged;
- `app:app` and exactly 14 authenticated GET Actions remain unchanged;
- no broker write methods are introduced;
- `trading_methods=false`.

## Production acceptance state

PR-64 still requires eight real external evidence cases:

1. Render commit;
2. health;
3. auth-negative;
4. exact-route-positive;
5. GPT schema import;
6. authenticated Preview;
7. Action-list inspection;
8. rollback restore.

These cases cannot be marked passed solely because CI is green.

## Что остаётся до полного релиза

### Backend and operations

- actual Render/Gateway acceptance and evidence recording;
- actual GPT Editor import and authenticated Preview;
- production-grade live ingestion for market, ratings, news and corporate events;
- external versioned RAG index with freshness and citation controls;
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

## Следующий пакет после PR-83

Ближайший обязательный блок — PR-64 production acceptance на реальном Render,
Gateway и GPT Editor. Если внешний доступ не позволяет собрать доказательства,
следующий backend-пакет выбирается только из актуального master plan и не должен
изображать production acceptance локальными тестами.

## Запрет ложного завершения

Проект не считается полностью завершённым только потому, что PR-83 слит или CI
зелёный. Завершение разрешено объявлять только после всех согласованных пакетов,
production acceptance и отдельной проверки полного Definition of Done.
