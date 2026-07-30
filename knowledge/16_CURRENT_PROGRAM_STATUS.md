# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-07-30  
Фактическая вершина программы после merge этого пакета: **PR-69**  
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
- **PR-69:** production-facing scenario store, live current-risk loader and PR-68 wiring.

## PR-69 — production read-only source wiring v1

PR-69 exports `FinalDecisionReviewScenarioSourceStoreV1`,
`build_live_current_risk_loader` and `FinalDecisionReviewProductionSourceWiringV1`.
It adds no HTTP route, operationId, query parameter or request body.

### Live current-risk source

Current risk is built through the existing read-only chain:

1. portfolio market snapshot;
2. portfolio contract v1 adapter;
3. advanced portfolio analytics;
4. conservative risk-policy evaluation.

The loader preserves contract timestamps and never calls order placement, replacement or
cancellation methods.

### Atomic scenario bundle

Scenario-specific source data cannot be reconstructed from hashes or current portfolio state.
The internal bounded store therefore accepts one complete bundle:

- safe scenario ID;
- exactly one purchase or sell pre-trade gate;
- one already calculated pro-forma risk evaluation;
- stored and expiry timestamps.

Partial or mixed-direction bundles are rejected. Missing and expired bundles stay unavailable
and are never fabricated.

Default lifecycle:

- TTL: 900 seconds;
- capacity: 64 bundles;
- exact scenario replacement;
- oldest-entry eviction;
- empty state after process restart.

### Acquisition wiring

For one scenario PR-69 constructs the four PR-68 loader ports:

- selected purchase or sell gate from the atomic scenario bundle;
- unselected direction remains `missing/attempted=false`;
- current risk from the live read-only portfolio pipeline;
- pro-forma risk from the same exact scenario bundle.

PR-68 then maps actual outcomes and invokes PR-67. Loader exceptions, invalid types and
invalid timestamps remain safe failures.

### Safety invariants

- internal Python API only;
- no public source-publication surface;
- no production OpenAPI change;
- no broker write method;
- no credentials or full account in store metadata;
- no trade authorization or order creation;
- `trading_methods=false`.

## Remaining production boundary

PR-69 exports production-facing wiring but intentionally does not register it in `app.py`.
A separate package must instantiate the source store, producer/coordinator and current-risk
loader against the production bridge. Calculator-owned publication of purchase/sell gate and
pro-forma risk also remains explicit and internal.

Until registration and calculator publication exist:

- scenario store is not automatically populated;
- registry may remain empty after restart;
- exact positive final-review acceptance may return `503`;
- Render/GPT/rollback evidence remains `not_executed`;
- no autonomous trading is enabled.

## Production acceptance state

PR-64 still requires eight real evidence cases: Render commit, health, auth-negative,
exact-route-positive, GPT schema import, authenticated Preview, Action-list inspection and
rollback restore. None may be marked passed solely because PR-69 CI is green.

## Что остаётся до полного релиза

### Backend and release acceptance

- register PR-69 production source wiring in `app.py` without changing Action surface;
- connect trusted calculator-owned scenario publication;
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

**PR-70 — production source wiring registration v1**:

- instantiate one scenario source store in the production wrapper;
- instantiate PR-66 producer and PR-67 coordinator from the existing bridge;
- register PR-69 current-risk loader and acquisition wiring as internal objects;
- preserve startup laziness: no broker call until trusted internal acquisition is invoked;
- expose no public source-publication endpoint;
- prove production OpenAPI remains exactly 14 authenticated GET Actions;
- add restart, empty-store, mocked live-risk and exact-acquisition integration tests;
- preserve `app:app`, no broker writes and `trading_methods=false`.

## Запрет ложного завершения

Проект не считается полностью завершённым только потому, что отдельный PR слит или CI
зелёный. Финальная фраза завершения разрешена только после закрытия всех согласованных
пакетов, production acceptance и отдельной проверки полного Definition of Done.
