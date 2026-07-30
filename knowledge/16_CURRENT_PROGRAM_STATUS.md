# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-07-30  
Фактическая вершина программы после merge этого пакета: **PR-61**  
Точная версия определяется текущей вершиной ветки `main`.

## Назначение документа

Этот файл является краткой оперативной картой программы. Он имеет приоритет для
определения активного этапа, если `knowledge/00_PROJECT_MASTER_CONTEXT.md` содержит
более ранний номер PR. Стратегические правила и Definition of Done продолжают
определяться master-context и `AGENTS.md`.

Код в `main` остаётся окончательным источником истины.

## Текущий режим

Сохраняются без исключений:

- `trading_methods=false`;
- пользовательские Gateway Actions только `GET`;
- Render entrypoint `app:app`;
- отсутствие создания, отправки, замены и отмены заявок;
- отсутствие переводов и вывода денег;
- отсутствие margin, short и derivatives execution;
- работа только через отдельную ветку и Pull Request;
- squash merge только после полного Regression Shield.

## Завершённые контуры

### P0 — безопасность и воспроизводимость

В `main` находятся:

- Telegram runtime retirement;
- broker SDK read-only allowlist;
- запрет mutating Actions и торговых SDK-вызовов;
- hash-locked dependencies;
- Ruff, formatting, mypy и coverage gates;
- dependency audit, SAST и secret scan;
- стабильный `app:app` и GET-only release contract;
- маскирование счёта и запрет секретов в GitHub.

### P1 — аналитический backend

Реализованы versioned read-only слои для:

- portfolio, cash, operations и broker-report reconciliation;
- provenance, timestamps, completeness и quality gates;
- portfolio analytics, concentration, stress и conservative risk policy;
- market reference, quotes, liquidity, ratings и corporate events;
- safe news sanitation, deduplication и citation-backed retrieval;
- equity, bond и fund evidence assessments;
- OHLCV technical-indicator evidence;
- Decision Engine с обязательным no-action/abstain;
- threshold rebalancing;
- purchase и sell pre-trade previews;
- shadow и paper workflows;
- authenticated/encrypted paper ledger, backup, restore и DR readiness;
- purged walk-forward planning, OOS performance и statistical stability;
- market-capacity assessment и capacity-aware decision gating.

### Final-review release chain

- **PR-50:** unified homogeneous buy/sell pre-trade review;
- **PR-51:** account-aware risk/pre-trade explanation envelope;
- **PR-52:** tamper-evident pro-forma risk/intention binding;
- **PR-53:** compact user-safe final response and shadow parity;
- **PR-54:** final-response release eligibility and canonical SHA-256;
- **PR-55:** private GET Action candidate and OpenAPI shadow;
- **PR-56:** exact eight-query input binding;
- **PR-57:** production-route readiness dossier;
- **PR-58:** route implementation plan and 13-case acceptance matrix;
- **PR-59:** route-handler shadow and safe observability;
- **PR-60:** isolated FastAPI HTTP integration candidate;
- **PR-61:** production private `GET /decision/final-review` with bounded TTL
  source registry.

## PR-61 — production final-review GET route v1

PR-61 registers exactly one new production Action:

- method: `GET`;
- path: `/decision/final-review`;
- operationId: `getFinalDecisionReview`;
- authentication: existing Gateway Bearer key, exported as `ApiKeyAuth`;
- request body: absent;
- query: exact PR-56 eight-field identity;
- response: `FinalDecisionReviewResponseV1` `1.0`;
- broker calls: none;
- trading and execution semantics: none.

### Source registry

The route cannot reconstruct a response from identity hashes. It uses an internal,
process-local registry containing only already validated route plans and bindings.

Default controls:

- TTL: 15 minutes;
- capacity: 64 entries;
- no HTTP publication method;
- expired-source pruning;
- oldest-source eviction;
- restart/deploy clears the registry;
- no credentials stored.

Fail-closed behavior:

- empty or expired registry → `503`;
- active source with substituted context → `409`;
- invalid masked account/count/uniqueness → `400`;
- framework schema failure → `422`;
- missing/invalid Gateway key → `401`;
- exact active source → compact `200` response.

The production route alone is not an end-to-end orchestration workflow. Until a trusted
internal publisher is connected, the expected production result is `503` after successful
authentication.

## Acceptance state

### Eligible for completion inside PR-61

- current GET-only release contract;
- full Regression Shield;
- production handler and registry tests;
- exact OpenAPI Action count and query contract;
- authentication negative test;
- no broker-write surface;
- `trading_methods=false`.

### Must remain unexecuted until actual deployment

- Render source-commit verification;
- cache-busted `/health` verification;
- live authenticated route call;
- GPT Editor schema import;
- GPT Editor Preview;
- full post-import Action-list inspection;
- rollback drill.

## Что остаётся до полного релиза по мастер-плану

### Backend и orchestration

- internal final-review orchestration publisher into the bounded registry;
- production-grade live ingestion for market, ratings, news and corporate events;
- external versioned RAG index with freshness and citation controls;
- expanded observability, alerting and operational runbooks.

### Web cabinet

- найти и зарегистрировать исходный frontend существующего сайта;
- не создавать дубликат frontend;
- реализовать безопасный HTML-импорт СберИнвестиций без OCR;
- архив, сравнение периодов, расхождения, мобильный UI и обе темы;
- проверить production site и интерактивные элементы.

### Release acceptance

- синхронизировать inventory и file index;
- провести Render/Gateway post-deploy acceptance;
- импортировать актуальную OpenAPI schema в GPT Editor;
- выполнить authenticated GPT Preview;
- выполнить end-to-end read-only acceptance на реальных, но не сохраняемых данных;
- подтвердить rollback и incident procedures.

### Торговые этапы

Shadow, paper и preview инфраструктура не являются разрешением на реальную торговлю.
Confirm-before-trade, idempotency, TTL confirmation, kill switch, partial-fill и timeout
reconciliation требуют отдельной программы допуска и отдельного решения владельца.

Полностью автономная торговля без подтверждения не планируется.

## Следующий рекомендуемый пакет

**PR-62 — final-review internal orchestration publisher v1**:

- подключает существующий read-only final-review chain к PR-61 registry;
- не создаёт HTTP publication endpoint;
- публикует только blocker-free exact plan/binding;
- применяет TTL, bounded capacity и source replacement controls;
- проверяет concurrent publication, expiry and restart semantics;
- добавляет orchestration provenance and safe publisher observability;
- не вызывает broker write methods;
- сохраняет `trading_methods=false`;
- не считает Render/GPT Preview acceptance выполненной заранее.

## Запрет ложного завершения

Проект не считается полностью завершённым только потому, что отдельный PR слит или CI
зелёный. Финальная фраза завершения разрешена только после закрытия всех согласованных
пакетов, production acceptance и отдельной проверки полного Definition of Done.
