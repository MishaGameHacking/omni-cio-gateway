# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-07-30  
Фактическая вершина программы после merge этого пакета: **PR-64**  
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
- **PR-63:** end-to-end internal composition and fail-closed publication;
- **PR-64:** production-acceptance evidence contract and offline collector.

## PR-64 — production acceptance evidence v1

PR-64 вводит восемь обязательных evidence-case:

1. `render_source_commit`;
2. `health_contract`;
3. `private_auth_negative`;
4. `exact_route_positive`;
5. `gpt_schema_import`;
6. `gpt_authenticated_preview`;
7. `gpt_action_list`;
8. `rollback_restore`.

### Evidence statuses

- `not_executed` — проверка не проводилась, proof fields запрещены;
- `passed` — есть UTC timestamp, типизированный source, safe reference, summary и SHA-256;
- `failed` — есть те же доказательства и safe error code;
- `not_applicable` — только датированное manual-review решение, не закрывающее acceptance.

Каждый executed row связан canonical SHA-256 с case, status, timestamp, source, reference,
summary, error code и safe count metrics. Подмена proof field блокируется.

### Collector behavior

`collect_final_decision_review_acceptance_evidence(...)`:

- принимает ожидаемые merge commit, app version и HTTPS base URL;
- принимает только уже сформированные observations;
- проверяет source по case, Render commit identity, UTC time, duplicates и future evidence;
- заполняет отсутствующие case статусом `not_executed`;
- применяет dependency order от Render до GPT Action-list;
- считает counters и overall status;
- не выполняет network calls;
- не меняет Render или GPT Editor;
- сохраняет `trading_methods=false`.

Полный `passed` возможен только при восьми `passed`. Любой `failed` переводит dossier в
`failed`; `not_executed` и `not_applicable` оставляют acceptance незавершённой.

## Acceptance state после PR-64

Сам PR-64 не проводит production acceptance. После его merge ожидаемый начальный dossier:

- восемь `not_executed`;
- `overall_status=not_executed`;
- `actual_deployment_verified=false`;
- `gpt_preview_verified=false`;
- `rollback_verified=false`;
- `acceptance_completed=false`.

До фактического выполнения остаются:

- Render source-commit verification;
- cache-busted `/health` verification;
- live unauthenticated negative route call;
- live exact authenticated positive route call;
- GPT Editor OpenAPI import;
- GPT Editor authenticated Preview;
- post-import Action-list inspection;
- rollback drill.

## Выявленный production-разрыв

PR-61 route читает только process-local registry. PR-63 умеет построить и опубликовать
reviewed source, но пока не подключён к production workflow, который формирует
`ProFormaRiskIntentBindingV1`. После process restart registry пуст, поэтому route честно
возвращает `503` до внутренней публикации.

Следовательно, positive-route acceptance нельзя считать готовой только по наличию route и
collector. Нужен отдельный production bridge, который вызывает PR-63 внутри процесса без
публичного publication endpoint и без broker write methods.

## Что остаётся до полного релиза по мастер-плану

### Backend and release acceptance

- production orchestration bridge from a validated read-only workflow into PR-63;
- actual Render/Gateway post-deploy acceptance and evidence recording;
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

**PR-65 — final-review production orchestration bridge v1**:

- находит существующий validated read-only workflow, создающий
  `ProFormaRiskIntentBindingV1`;
- вызывает PR-63 orchestration внутри того же процесса;
- не создаёт HTTP publication endpoint;
- не принимает source contracts или secrets через query/body;
- публикует только exact blocker-free evidence chain;
- добавляет restart/TTL/concurrency and failure-path tests;
- сохраняет production OpenAPI, `app:app` и GET-only Action set;
- не вызывает broker write methods;
- сохраняет `trading_methods=false`;
- не отмечает Render/GPT acceptance выполненной заранее.

## Запрет ложного завершения

Проект не считается полностью завершённым только потому, что отдельный PR слит или CI
зелёный. Финальная фраза завершения разрешена только после закрытия всех согласованных
пакетов, production acceptance и отдельной проверки полного Definition of Done.
