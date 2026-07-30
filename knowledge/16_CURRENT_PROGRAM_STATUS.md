# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-07-30  
Фактическая вершина программы после merge этого пакета: **PR-65**  
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
- **PR-65:** production-importable typed workflow bridge into PR-63.

## PR-65 — final-review workflow bridge v1

PR-65 registers one internal object in `app.py`:

```python
final_decision_review_workflow_bridge = FinalDecisionReviewWorkflowBridgeV1(
    registry=final_decision_review_registry,
    openapi_provider=lambda: app.openapi(),
    expected_app_version=APP_VERSION,
)
```

No HTTP decorator, path, operationId, query parameter or request body is added.

### Typed inputs

Bridge accepts only:

- `RiskPreTradeExplanationEnvelopeV1`;
- ordered `CapacityOrderRequestV1` set;
- already calculated pro-forma `RiskPolicyEvaluationV1`;
- safe scenario/correlation/request identifiers;
- timezone-aware bridge timestamp.

It does not accept credentials, full account ID, raw JSON body, confirmation or execution
controls.

### Pipeline

1. Build exact `ProFormaRiskScenarioV1` from supplied risk metadata.
2. Bind scenario to the current reviewed intent.
3. Invoke PR-63 response → eligibility → Action shadow → input → readiness → plan chain.
4. Publish through PR-62 into PR-61 registry.
5. Existing authenticated GET returns the compact response.

The pro-forma timestamp comes from `risk_evaluation.metadata.retrieved_at`, while bridge time
is used for freshness and publication.

### Fail-closed behavior

- structurally invalid scenario → blocked at `scenario`;
- invalid binding → blocked at `binding`;
- missing HTTPS server, OpenAPI drift or invalid trace → blocked at `orchestration`;
- substituted quantity/instrument/intent → safe no-action binding and response;
- blocked publication leaves registry unchanged;
- all result safety flags remain false and `trading_methods=false`.

### Concurrency and lifecycle

- one bridge-level lock serializes scenario through publication;
- exact concurrent calls use PR-62 `published/replaced` semantics;
- PR-61 TTL, capacity and eviction rules remain unchanged;
- restart creates an empty registry;
- a validated caller must invoke the bridge after restart.

## Remaining production gap

Repository search confirmed that `bind_pro_forma_risk_to_intent()` still has no live
production caller outside its own module and tests. PR-65 exposes the correct production
boundary, but it does not invent upstream risk evidence or auto-run on startup.

Therefore after deploy:

- registry may remain empty until a validated decision workflow calls the bridge;
- exact positive route acceptance may still return `503` before that call;
- Render/GPT/rollback evidence remains `not_executed`;
- no autonomous trading is enabled.

## Production acceptance state

PR-64 requires eight actual evidence case:

1. Render source commit;
2. cache-busted health contract;
3. private auth negative;
4. exact route positive;
5. GPT schema import;
6. authenticated GPT Preview;
7. GPT Action-list inspection;
8. rollback restore.

None may be marked passed solely because PR-65 CI is green.

## Что остаётся до полного релиза

### Backend and release acceptance

- live read-only decision workflow that produces current explanation and pro-forma risk,
  then invokes the PR-65 bridge;
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

**PR-66 — live read-only decision workflow producer v1**:

- определяет минимальный typed input bundle для current risk/pre-trade explanation and
  pro-forma risk;
- использует существующие read-only contracts and calculators;
- вызывает PR-65 bridge только после source authority, freshness, account and intent gates;
- не принимает credentials or execution controls;
- не создаёт broker-write method;
- добавляет no-action, stale, partial, restart and exact-source tests;
- сохраняет GET-only OpenAPI, `app:app` и `trading_methods=false`;
- не считает production acceptance выполненной до реального deploy/GPT evidence.

## Запрет ложного завершения

Проект не считается полностью завершённым только потому, что отдельный PR слит или CI
зелёный. Финальная фраза завершения разрешена только после закрытия всех согласованных
пакетов, production acceptance и отдельной проверки полного Definition of Done.
