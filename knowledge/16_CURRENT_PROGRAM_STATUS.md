# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-07-30  
Фактическая вершина программы после merge этого пакета: **PR-76**  
Точная версия определяется текущей вершиной ветки `main`.

## Назначение документа

Этот файл — краткая оперативная карта программы. Он имеет приоритет для определения
активного этапа, если master-context содержит более ранний номер PR. Стратегические правила
и Definition of Done продолжают определяться `AGENTS.md` и
`knowledge/00_PROJECT_MASTER_CONTEXT.md`. Код в `main` остаётся окончательным источником
истины.

## Неизменяемые границы

- `trading_methods=false`;
- пользовательские Gateway Actions только `GET`;
- Render entrypoint `app:app`;
- отсутствие создания, отправки, замены и отмены заявок;
- отсутствие переводов и вывода денег;
- отсутствие margin, short и derivatives execution;
- отдельная ветка и Pull Request для каждого пакета;
- squash merge только после полного Regression Shield.

## Завершённые контуры

### P0 — безопасность и воспроизводимость

В `main` находятся Telegram retirement, broker SDK read-only allowlist, запрет mutating
Actions, hash-locked dependencies, Ruff/formatting/mypy/coverage, dependency audit, SAST,
secret scan, стабильный `app:app`, GET-only release contract и маскирование счёта.

### P1 — аналитический backend

Реализованы versioned read-only слои для portfolio, cash, operations, broker-report
reconciliation, provenance, quality, analytics, concentration, stress, conservative risk,
market evidence, safe news, instrument assessments, technical evidence, Decision Engine,
threshold rebalancing, purchase/sell previews, shadow/paper workflows, encrypted paper
ledger, walk-forward/OOS stability и market-capacity gating.

### Final-review release chain

- **PR-50:** unified homogeneous buy/sell pre-trade review;
- **PR-51:** account-aware risk/pre-trade explanation envelope;
- **PR-52:** tamper-evident pro-forma risk/intention binding;
- **PR-53:** compact user-safe final response and shadow parity;
- **PR-54:** release eligibility and canonical response SHA-256;
- **PR-55:** private GET Action candidate and OpenAPI shadow;
- **PR-56:** exact eight-query input binding;
- **PR-57:** production-route readiness dossier;
- **PR-58:** implementation plan and 13-case acceptance matrix;
- **PR-59:** route-handler shadow and safe observability;
- **PR-60:** isolated FastAPI HTTP integration candidate;
- **PR-61:** production private `GET /decision/final-review` and bounded TTL registry;
- **PR-62:** trusted process-local publisher;
- **PR-63:** end-to-end internal composition and fail-closed publication;
- **PR-64:** production-acceptance evidence contract and offline collector;
- **PR-65:** production-importable typed workflow bridge;
- **PR-66:** live read-only workflow producer from buy/sell gates and risk evidence;
- **PR-67:** acquisition-outcome coordinator and source handoff validation;
- **PR-68:** typed source acquisition adapter with safe outcome mapping;
- **PR-69:** production-facing scenario store, live current-risk loader and PR-68 wiring;
- **PR-70:** lazy production registration of source store, producer, coordinator and wiring;
- **PR-71:** trusted typed scenario publication into the registered bounded store;
- **PR-72:** calculator-owned purchase/sell preview handoff into trusted publication;
- **PR-73:** calculator-owned construction of the exact capacity-intent gate before PR-72;
- **PR-74:** allowlisted, freshness-checked and replay-safe internal invocation boundary;
- **PR-75:** explicit calculator-provider registry with typed bundle and context gates;
- **PR-76:** typed adapters from existing read-only owners into fixed provider IDs.

## PR-76 — existing calculator provider adapters v1

PR-76 adds composition adapters from existing read-only calculation owners into the PR-75
provider bundle. The adapter does not duplicate or recompute financial values.

### Typed owner ports

The common owner set supplies:

1. one typed analytical decision;
2. one typed exact-intent request;
3. one or more typed capacity assessments;
4. one explicit typed pro-forma risk evaluation.

A directional owner supplies exactly one non-empty purchase or sell preview tuple. Purchase
and sell outputs are never mixed.

### Adapter gates

- exact invocation operation before any owner call;
- every configured owner must be callable;
- every owner is invoked exactly once per provider call;
- exception, raw mapping, wrong type, empty capacity or empty preview fails closed;
- pro-forma risk retrieval time is preserved as bundle build time;
- exact scenario and correlation IDs are copied from the approved request;
- fixed provider IDs only: `provider:existing:purchase-review` and
  `provider:existing:sell-review`;
- provider registration performs no owner, network or broker call.

### Compatibility and safety

- Gateway version remains `3.10.0`;
- production OpenAPI remains exactly 14 authenticated GET Actions;
- no route, operation ID, query field or request body is added;
- no dynamic import or user-selected provider name;
- no startup calculation or broker call;
- no broker write method;
- no trade authorization or order creation;
- `app:app` remains stable;
- `trading_methods=false`.

## Remaining production boundary

PR-76 defines and validates the adapters but production must still provide concrete read-only
owner callables around the existing Decision Engine, capacity assessment, purchase/sell
preview and pro-forma risk owners. Until those callables and actual acceptance exist:

- the provider registry may remain empty after startup;
- the scenario store may remain empty after restart;
- exact acquisition may report missing scenario sources;
- the final-review route may return `503`;
- Render/GPT/rollback evidence remains `not_executed`;
- no autonomous trading is enabled.

## Production acceptance state

PR-64 still requires eight real evidence cases: Render commit, health, auth-negative,
exact-route-positive, GPT schema import, authenticated Preview, Action-list inspection and
rollback restore. None may be marked passed solely because PR-76 CI is green.

## Что остаётся до полного релиза

### Backend and release acceptance

- concrete owner callable wiring for one approved purchase and sell provider;
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

Shadow, paper и preview инфраструктура не являются разрешением на реальную торговлю.
Confirm-before-trade, idempotency, TTL confirmation, kill switch, partial-fill и timeout
reconciliation требуют отдельной программы допуска и решения владельца. Полностью
автономная торговля без подтверждения не планируется.

## Следующий рекомендуемый пакет

**PR-77 — concrete production owner callable wiring v1**:

- wires only already existing read-only Decision Engine and capacity owners;
- consumes broker purchase/sell previews from their existing typed owners;
- requires an explicit typed pro-forma risk provider and never substitutes current risk;
- registers fixed PR-76 provider IDs without calling them at startup;
- validates account, timestamp and request identity across owner outputs;
- performs no HTTP route or production OpenAPI change;
- preserves `app:app`, no broker writes and `trading_methods=false`.

## Запрет ложного завершения

Проект не считается полностью завершённым только потому, что отдельный PR слит или CI
зелёный. Финальная фраза завершения разрешена только после закрытия всех согласованных
пакетов, production acceptance и отдельной проверки полного Definition of Done.
