# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-07-30  
Фактическая вершина программы после merge этого пакета: **PR-67**  
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
- **PR-67:** acquisition-outcome coordinator and source handoff validation.

## PR-67 — read-only workflow coordinator v1

PR-67 exports `FinalDecisionReviewWorkflowCoordinatorV1`. It is an internal Python API and
adds no HTTP route, operationId, query parameter or request body.

### Canonical source evidence

Every coordination attempt contains exactly four unique slots:

- `purchase_gate`;
- `sell_gate`;
- `current_risk`;
- `pro_forma_risk`.

Each slot has status `available`, `missing` or `failed`. Evidence stores only UTC time,
safe provider/operation and a safe error code. Financial payloads, credentials and full
account data are not logged.

A complete bundle requires:

- exactly one directional gate available;
- the other directional gate missing;
- current risk available;
- pro-forma risk available;
- zero failed sources.

### Coordinator gates

Before invoking PR-66, coordinator verifies:

1. four canonical slots without duplicates;
2. exact evidence-to-artifact correspondence;
3. exactly one buy/sell direction;
4. source evidence timestamp equals artifact source timestamp;
5. age and future-tolerance bounds;
6. current/pro-forma/preview masked-account parity;
7. request side equals selected direction.

Missing, failed, stale, future-dated, account-mismatched or direction-mismatched bundles do
not call producer. The result is explicitly blocked and registry state is unchanged.

### Safety invariants

- no source acquisition or scheduling;
- no network calls;
- no broker SDK calls or writes;
- no source payload, credential or full-account logs;
- no trade authorization or order creation;
- no production OpenAPI changes;
- `trading_methods=false`.

## Remaining production boundary

PR-67 validates handoff correctness but does not acquire source artifacts. A future adapter
must call existing read-only calculators, construct evidence from actual outcomes and pass
only complete typed artifacts to coordinator. It must never mark absent or failed data as
available.

Until that adapter exists and is invoked:

- registry may remain empty after restart;
- exact positive route acceptance may return `503`;
- Render/GPT/rollback evidence remains `not_executed`;
- no autonomous trading is enabled.

## Production acceptance state

PR-64 still requires eight real evidence cases: Render commit, health, auth-negative,
exact-route-positive, GPT schema import, authenticated Preview, Action-list inspection and
rollback restore. None may be marked passed solely because PR-67 CI is green.

## Что остаётся до полного релиза

### Backend and release acceptance

- read-only source acquisition adapter for current risk, pro-forma risk and one buy/sell gate;
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

**PR-68 — read-only workflow source acquisition adapter v1**:

- определяет typed acquisition ports for one purchase/sell gate, current risk and pro-forma risk;
- converts actual load outcomes into PR-67 source evidence;
- never fabricates unavailable artifacts;
- separates missing, failed, stale and partial outcomes;
- invokes coordinator only with exact artifact/evidence correspondence;
- records only safe counts, provider/operation and error codes;
- adds timeout, source failure, stale, account mismatch and successful handoff tests;
- preserves 14 GET Actions, `app:app`, no broker writes and `trading_methods=false`;
- does not mark production acceptance complete before real deploy/GPT evidence.

## Запрет ложного завершения

Проект не считается полностью завершённым только потому, что отдельный PR слит или CI
зелёный. Финальная фраза завершения разрешена только после закрытия всех согласованных
пакетов, production acceptance и отдельной проверки полного Definition of Done.
