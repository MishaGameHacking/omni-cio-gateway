# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-07-30  
Фактическая вершина программы после merge этого пакета: **PR-63**  
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
- **PR-62:** trusted process-local publisher;
- **PR-63:** end-to-end internal composition and fail-closed publication.

## PR-63 — end-to-end internal orchestration v1

PR-63 accepts an already formed `ProFormaRiskIntentBindingV1` and executes one ordered
internal pipeline:

1. PR-53 compact response and shadow parity;
2. PR-54 release eligibility;
3. PR-55 Action/OpenAPI shadow;
4. PR-56 exact query and input binding;
5. PR-57 production-route readiness dossier;
6. PR-58 implementation plan and acceptance matrix;
7. PR-62 internal publication into the PR-61 registry.

The first blocked stage stops the chain. Later artifacts remain absent and the registry is
not mutated.

### Production OpenAPI protection

The current production schema is deep-copied. The existing PR-61 route must exactly match
its reviewed method, operation ID, authentication, no-body contract and ordered eight query
parameters. Only that route is removed from the copy before PR-55 candidate reconstruction.
The actual production OpenAPI object and schema cache are never mutated.

### Result and safety

`FinalDecisionReviewOrchestrationResultV1` reports:

- `published` or `blocked`;
- completed stage;
- primary blocker;
- contiguous intermediate artifacts;
- publication result only after complete success.

A validated no-action/`WAIT_FOR_DATA` response may be published. It remains a read-only
abstention with `trade_authorized=false`, `order_created=false`,
`execution_ready=false` and `trading_methods=false`.

The orchestration:

- creates no new HTTP route;
- changes no production OpenAPI operation;
- calls no broker;
- recomputes no upstream financial source values;
- authorizes no trade or order.

## Acceptance state

### Eligible inside PR-63

- complete composition through authenticated production `200`;
- safe no-action publication;
- release-policy stop before Action construction;
- production route substitution detection;
- input-policy and readiness-control stops;
- publication-trace stop with empty registry;
- exact replacement on repeated orchestration;
- unchanged production OpenAPI;
- immutable result and timezone checks;
- full Regression Shield and security gates.

### Must remain unexecuted until actual deployment

- Render source-commit verification;
- cache-busted `/health` verification;
- live authenticated route call against deployed commit;
- GPT Editor OpenAPI import;
- GPT Editor Preview;
- post-import Action-list inspection;
- rollback drill.

## Что остаётся до полного релиза по мастер-плану

### Backend and release acceptance

- versioned production-acceptance evidence contract and collector;
- actual Render/Gateway post-deploy acceptance;
- actual GPT Editor schema import and authenticated Preview;
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
reconciliation требуют отдельной программы допуска и отдельного решения владельца.
Полностью автономная торговля без подтверждения не планируется.

## Следующий рекомендуемый пакет

**PR-64 — final-review production acceptance evidence contract v1**:

- вводит immutable evidence contract для Render commit, `/health`, live auth, exact route,
  GPT Editor import/Preview, Action-list inspection и rollback;
- различает `not_executed`, `passed`, `failed` и `not_applicable`;
- не позволяет пометить acceptance выполненным без датированного доказательства;
- маскирует secrets и account context;
- не выполняет deployment или GPT Editor changes автоматически;
- не добавляет HTTP endpoint и не меняет production OpenAPI;
- сохраняет `trading_methods=false`.

## Запрет ложного завершения

Проект не считается полностью завершённым только потому, что отдельный PR слит или CI
зелёный. Финальная фраза завершения разрешена только после закрытия всех согласованных
пакетов, production acceptance и отдельной проверки полного Definition of Done.
