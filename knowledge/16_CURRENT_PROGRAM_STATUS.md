# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-07-30  
Фактическая вершина программы после merge этого пакета: **PR-68**  
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
- **PR-68:** typed source acquisition adapter with safe outcome mapping.

## PR-68 — read-only source acquisition adapter v1

PR-68 exports `FinalDecisionReviewSourceAcquisitionAdapterV1`. It adds no HTTP route,
operationId, query parameter or request body.

### Loader ports

Adapter requires exactly four typed ports:

- purchase pre-trade gate;
- sell pre-trade gate;
- current risk;
- pro-forma risk.

For one request, only the selected buy/sell gate and both risk ports are attempted. The
unselected direction is not called and is recorded as `missing/attempted=false`.

### Outcome mapping

- valid typed artifact + aware source timestamp → `available`;
- loader returns `None` → `missing/attempted=true`;
- unselected direction → `missing/attempted=false`;
- timeout → `failed/SOURCE_TIMEOUT`;
- exception → `failed/SOURCE_LOAD_FAILED`;
- wrong artifact type → `failed/SOURCE_TYPE_INVALID`;
- absent or naïve timestamp → `failed/SOURCE_TIMESTAMP_INVALID`.

Raw exception text, traceback, source payloads, credentials and full account data are not
logged.

### Exact coordinator handoff

Adapter creates all four canonical PR-67 evidence slots and passes the exact loaded objects.
Artifact presence must equal evidence availability. Missing or failed data is never
fabricated or promoted to available.

PR-67 then performs freshness, account and direction checks before invoking PR-66.

### Safety invariants

- injected read-only loader ports only;
- no public publication surface;
- no production OpenAPI change;
- no broker write method;
- no exception/payload/credential/full-account logging;
- no trade authorization or order creation;
- `trading_methods=false`.

## Remaining production boundary

PR-68 defines and executes loader ports, but concrete production wiring to existing
calculators is not yet present. A later package must construct these loaders from current
read-only services without exposing credentials or introducing broker writes.

Until concrete loaders are wired and invoked:

- registry may remain empty after restart;
- exact positive route acceptance may return `503`;
- Render/GPT/rollback evidence remains `not_executed`;
- no autonomous trading is enabled.

## Production acceptance state

PR-64 still requires eight real evidence cases: Render commit, health, auth-negative,
exact-route-positive, GPT schema import, authenticated Preview, Action-list inspection and
rollback restore. None may be marked passed solely because PR-68 CI is green.

## Что остаётся до полного релиза

### Backend and release acceptance

- concrete production loader wiring for one buy/sell gate, current risk and pro-forma risk;
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

**PR-69 — production read-only loader wiring v1**:

- inventories existing purchase/sell gate and risk builders callable from production code;
- creates concrete loader factories without storing credentials;
- preserves artifact source timestamps and masked-account context;
- maps unsupported or unavailable calculations to `None`/safe failure instead of fabrication;
- constructs a production acquisition adapter from PR-68 and PR-67 coordinator;
- adds loader call, timeout, exception, restart and exact-route integration tests;
- preserves 14 GET Actions, `app:app`, no broker writes and `trading_methods=false`;
- does not mark production acceptance complete before real deploy/GPT evidence.

## Запрет ложного завершения

Проект не считается полностью завершённым только потому, что отдельный PR слит или CI
зелёный. Финальная фраза завершения разрешена только после закрытия всех согласованных
пакетов, production acceptance и отдельной проверки полного Definition of Done.
