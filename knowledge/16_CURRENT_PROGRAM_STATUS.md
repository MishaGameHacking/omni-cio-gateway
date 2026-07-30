# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-07-30  
Фактическая вершина программы после merge этого пакета: **PR-66**  
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
- **PR-66:** live read-only workflow producer from buy/sell gates and risk evidence.

## PR-66 — live read-only decision workflow producer v1

PR-66 exports `FinalDecisionReviewWorkflowProducerV1`. It is an internal Python API and
adds no HTTP route, operationId, query parameter or request body.

### Typed inputs

Producer accepts:

- exactly one `CapacityPreTradeDecisionGateV1` or
  `CapacitySellPreTradeDecisionGateV1`;
- current `RiskPolicyEvaluationV1`;
- already calculated pro-forma `RiskPolicyEvaluationV1`;
- safe scenario/correlation/request identifiers;
- timezone-aware production timestamp.

Credentials, full account ID, raw JSON payload, order confirmation and execution controls
are not inputs.

### Exact source pipeline

1. Existing directional builder confirms one homogeneous buy/sell source, coverage and
   exact intent binding.
2. Existing explanation builder rechecks masked account, current-risk freshness/readiness,
   directional freshness, capacity and broker-preview layers.
3. Expected capacity requests are read only from retained source gate intent; caller cannot
   inject a second conflicting request set.
4. PR-65 builds pro-forma scenario and binding.
5. PR-63/PR-62 publish exact review or safe no-action response into PR-61 registry.

Producer does not fetch broker data and does not recompute previews or risk. Source authority
remains with the typed source contracts.

### Fail-closed and no-action behavior

- zero or two directional gates → structural block before explanation;
- malformed source → structural block;
- stale current risk, account mismatch, incomplete coverage or intent mismatch →
  auditable `WAIT_FOR_DATA`/no-action;
- invalid trace → downstream publication block with empty registry;
- no blocked state is upgraded to ready;
- all safety flags remain false and `trading_methods=false`.

### Concurrency and lifecycle

- producer-level lock serializes directional review through bridge;
- downstream bridge/publisher locks preserve exact replacement semantics;
- concurrent exact workflows yield one initial publication and replacements;
- PR-61 TTL, capacity, eviction and restart-empty behavior remain unchanged.

## Remaining production boundary

PR-66 is the first complete typed producer from retained pre-trade/risk artifacts to the
final-review registry. It deliberately does not fetch, schedule or persist those artifacts
and does not auto-run at startup.

A runtime coordinator is still required to obtain fresh typed purchase/sell gate, current
risk and pro-forma risk from the existing read-only calculations and invoke the producer.
Until then:

- registry may remain empty after restart;
- exact positive route acceptance may return `503` before producer invocation;
- Render/GPT/rollback evidence remains `not_executed`;
- no autonomous trading is enabled.

## Production acceptance state

PR-64 still requires eight real evidence cases: Render commit, health, auth-negative,
exact-route-positive, GPT schema import, authenticated Preview, Action-list inspection and
rollback restore. None may be marked passed solely because PR-66 CI is green.

## Что остаётся до полного релиза

### Backend and release acceptance

- runtime coordinator for obtaining fresh typed source artifacts and calling PR-66;
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

**PR-67 — read-only decision workflow coordinator contract v1**:

- определяет typed handoff from existing read-only calculators to PR-66;
- требует authority, freshness, masked-account and exact-intent evidence for every input;
- records source acquisition outcomes without credentials or financial payload logs;
- never fabricates missing purchase/sell gate or pro-forma risk;
- invokes producer only when a complete bundle exists;
- returns explicit no-action/blocked result otherwise;
- adds restart, partial, stale, account mismatch and source failure tests;
- preserves 14 GET Actions, `app:app`, no broker writes and `trading_methods=false`;
- does not mark production acceptance complete before real deploy/GPT evidence.

## Запрет ложного завершения

Проект не считается полностью завершённым только потому, что отдельный PR слит или CI
зелёный. Финальная фраза завершения разрешена только после закрытия всех согласованных
пакетов, production acceptance и отдельной проверки полного Definition of Done.
