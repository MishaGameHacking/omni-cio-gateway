# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-07-30  
Фактическая вершина программы после merge этого пакета: **PR-71**  
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
- **PR-71:** trusted typed scenario publication into the registered bounded store.

## PR-71 — trusted scenario source publication v1

PR-71 adds one internal publisher to the PR-70 production runtime. The publisher and PR-69
acquisition wiring share the same process-local bounded TTL store.

### Accepted source artifacts

A publication contains exactly:

1. one typed purchase or sell pre-trade gate;
2. one typed pro-forma risk evaluation;
3. one safe scenario ID;
4. safe provider and operation identifiers;
5. one timezone-aware publication timestamp.

Raw dictionaries, credentials, full account IDs and request bodies are rejected.

### Exact trust gates

Before mutating the store the publisher verifies:

- exactly one buy/sell direction;
- exact request-side consistency;
- unique expected instrument keys;
- exact preview coverage;
- one masked account across all broker previews;
- exact account parity with pro-forma risk;
- exact gate/risk timestamp equality;
- source freshness and future tolerance;
- non-executing gate flags;
- conservative risk policy with margin, shorts, derivatives and currency operations disabled.

Failure occurs before publication and leaves the store unchanged.

### Action compatibility

- Gateway version remains `3.10.0`;
- production OpenAPI remains exactly 14 authenticated GET Actions;
- no route, operation ID, query field or request body is added;
- no public scenario publication method exists;
- `app:app` remains stable.

### Safety invariants

- no startup broker call;
- no broker write method;
- no financial payload or internal source ID in publication metadata;
- no trade authorization or order creation;
- missing or invalid scenario data remains fail-closed;
- `trading_methods=false`.

## Remaining production boundary

PR-71 accepts already calculated typed artifacts but does not manufacture them. A trusted
calculator-owned handoff must build the exact directional gate and pro-forma risk from existing
read-only calculation outputs and invoke the publisher. Until that handoff and actual
production acceptance exist:

- the scenario store may remain empty after restart;
- exact acquisition may report missing scenario sources;
- the final-review route may return `503`;
- Render/GPT/rollback evidence remains `not_executed`;
- no autonomous trading is enabled.

## Production acceptance state

PR-64 still requires eight real evidence cases: Render commit, health, auth-negative,
exact-route-positive, GPT schema import, authenticated Preview, Action-list inspection and
rollback restore. None may be marked passed solely because PR-71 CI is green.

## Что остаётся до полного релиза

### Backend and release acceptance

- calculator-owned creation and handoff of exact directional gate and pro-forma risk;
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

**PR-72 — calculator-owned trusted scenario handoff v1**:

- accepts only outputs from approved read-only gate/risk builders;
- preserves exact gate and risk source timestamps;
- derives scenario context without accepting user-controlled raw payloads;
- invokes the PR-71 publisher through one internal service;
- records safe handoff provenance and counts only;
- proves blocked, stale, mismatch, restart and concurrency behavior;
- changes no HTTP route or production OpenAPI operation;
- preserves `app:app`, no broker writes and `trading_methods=false`.

## Запрет ложного завершения

Проект не считается полностью завершённым только потому, что отдельный PR слит или CI
зелёный. Финальная фраза завершения разрешена только после закрытия всех согласованных
пакетов, production acceptance и отдельной проверки полного Definition of Done.
