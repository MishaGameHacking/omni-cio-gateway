# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-07-30  
Фактическая вершина программы после merge этого пакета: **PR-62**  
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
- **PR-62:** trusted process-local publisher into that registry.

## PR-62 — internal final-review publisher v1

PR-62 adds an internal Python API only:

```python
publish_final_decision_review_source(
    registry,
    route_plan,
    input_binding,
    correlation_id=...,
    request_id=...,
    published_at=...,
)
```

### Preconditions

Publication is rejected unless the route plan is ready and blocker-free, the binding is
valid, and masked account, requested/final options, fingerprint, ordered instruments,
count, query SHA-256, response SHA-256 and Action-candidate SHA-256 match exactly.

Trace identifiers and timezone-aware timestamps are validated before registry mutation.

### Publication semantics

- first exact context → `published`;
- same active context → `replaced`;
- another context beyond capacity → oldest-source eviction is counted;
- expired source remains governed by PR-61 TTL;
- a new process starts with an empty registry.

One publisher/lock is attached to each registry. Concurrent calls therefore share one
atomic lookup/publish/count boundary.

### Safe observability

Publisher telemetry contains only correlation/request IDs, masked account and safe counts
for active sources, eviction, replacement and instrument count. External-call status is
always `not_called`.

The publisher:

- creates no HTTP endpoint;
- changes no production OpenAPI operation;
- calls no broker;
- recalculates no source values;
- authorizes no trade or order;
- preserves `trading_methods=false`.

## Acceptance state

### Eligible inside PR-62

- exact publication and replacement tests;
- bounded-capacity eviction accounting;
- concurrent publication semantics;
- expiry and restart behavior;
- fail-closed context, timestamp and trace validation;
- safe publisher observability;
- proof that production OpenAPI and HTTP method set are unchanged;
- full Regression Shield and security gates.

### Must remain unexecuted until actual deployment

- Render source-commit verification;
- cache-busted `/health` verification;
- live authenticated route call;
- GPT Editor OpenAPI import;
- GPT Editor Preview;
- post-import Action-list inspection;
- rollback drill.

## Что остаётся до полного релиза по мастер-плану

### Backend и orchestration

- end-to-end internal composition of PR-53 through PR-62 from validated read-only inputs;
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

- провести Render/Gateway post-deploy acceptance;
- импортировать актуальную OpenAPI schema в GPT Editor;
- выполнить authenticated GPT Preview;
- провести end-to-end read-only acceptance на реальных, но не сохраняемых данных;
- подтвердить rollback и incident procedures.

### Торговые этапы

Shadow, paper и preview инфраструктура не являются разрешением на реальную торговлю.
Confirm-before-trade, idempotency, TTL confirmation, kill switch, partial-fill и timeout
reconciliation требуют отдельной программы допуска и отдельного решения владельца.
Полностью автономная торговля без подтверждения не планируется.

## Следующий рекомендуемый пакет

**PR-63 — final-review end-to-end internal orchestration composition v1**:

- принимает только уже сформированный compact response и проверяемые release inputs;
- последовательно строит eligibility, Action shadow, query binding, readiness dossier и
  implementation plan;
- публикует source через PR-62 только при полном прохождении всех gates;
- возвращает fail-closed orchestration result с primary blocker;
- не добавляет HTTP endpoint и не меняет production OpenAPI;
- не вызывает broker write methods;
- сохраняет `trading_methods=false`;
- не считает Render/GPT Preview acceptance выполненной заранее.

## Запрет ложного завершения

Проект не считается полностью завершённым только потому, что отдельный PR слит или CI
зелёный. Финальная фраза завершения разрешена только после закрытия всех согласованных
пакетов, production acceptance и отдельной проверки полного Definition of Done.
