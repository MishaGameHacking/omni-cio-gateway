# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-07-30  
Фактическая вершина программы после merge этого пакета: **PR-78**  
Точная версия определяется текущей вершиной ветки `main`.

## Назначение документа

Этот файл — краткая оперативная карта программы. Он имеет приоритет для определения
активного этапа, если master-context содержит более ранний номер PR. Стратегические правила
и Definition of Done продолжают определяться `AGENTS.md` и
`knowledge/00_PROJECT_MASTER_CONTEXT.md`. Код в `main` остаётся окончательным источником
истины.

## Repository maintenance after PR-78

- PR-105 removed the unexported duplicate PR-71 publisher path and closed issue #97; the trusted scenario publisher remains canonical.
- `docs/master-plan/` now preserves the exact user specification plus a text-search copy and source hierarchy.
- `gpt/MY_GPT_SETUP_RUNBOOK.md` records the current official My GPTs/Actions setup.
- This maintenance does not advance the functional top beyond PR-78 and does not replace PR-79.

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
- **PR-71:** trusted typed scenario publication into the registered bounded store;
- **PR-72:** calculator-owned purchase/sell preview handoff into trusted publication;
- **PR-73:** calculator-owned construction of the exact capacity-intent gate before PR-72;
- **PR-74:** allowlisted, freshness-checked and replay-safe internal invocation boundary;
- **PR-75:** explicit calculator-provider registry with typed bundle and context gates;
- **PR-76:** typed adapters from existing read-only owners into fixed provider IDs;
- **PR-77:** scenario-scoped production routing for fixed purchase/sell owner callables;
- **PR-78:** trusted one-shot composition with explicit pro-forma scenario binding.

## PR-78 — trusted production owner composition v1

PR-78 materializes already existing typed read-only owners once, validates that all outputs
describe one exact post-change scenario, invokes one fixed PR-76 provider through the PR-77
store, and removes the temporary owner bundle on success or downstream failure.

### Explicit pro-forma contract

A plain `RiskPolicyEvaluationV1` does not prove whether it describes current or post-change
risk. PR-78 therefore requires the existing `ProFormaRiskScenarioV1` owner output and
revalidates:

- `current_portfolio_risk=false` and `pro_forma_post_change=true`;
- method `exact_capacity_intent_post_change`;
- canonical exact-intent fingerprint;
- masked account, option, direction and capacity-request identity;
- risk/scenario timestamp equality and bounded freshness;
- no margin, short sale, derivatives or currency-operation policy;
- no order, execution or trading capability.

Current portfolio risk cannot be substituted silently.

### Materialization and exact binding

- decision, intent, capacity, pro-forma scenario and directional preview owners are each
  called exactly once;
- capacity and preview iterables are non-empty, typed and bounded to 100 rows;
- capacity coverage exactly equals the expected intent requests;
- preview stable keys exactly cover the intent instruments;
- decision, previews, scenario and risk use the same masked account;
- purchase and sell types remain isolated;
- immutable snapshot accessors accept only the exact approved invocation request;
- owner exception details are not returned in the safe error message.

### One-shot cleanup

The validated snapshots are published under exact scenario, correlation and operation
identity, invoked through the fixed provider ID, then removed. PR-78 releases any remaining
invocation pin and discards the active owner bundle in a `finally` path. Production startup
still contains no scenario-specific owners and performs no calculation or broker call.

### Compatibility and safety

- Gateway version remains `3.10.0`;
- production OpenAPI remains exactly 14 authenticated GET Actions;
- no route, operation ID, query field or request body is added;
- no public callable or financial-payload publication surface;
- no dynamic import or user-selected provider name;
- no broker write method;
- no trade authorization or order creation;
- `app:app` remains stable;
- `trading_methods=false`.

## Remaining production boundary

PR-78 provides a trusted server-side composition and invocation boundary but intentionally
does not decide when a real user request should execute the Decision Engine, capacity,
broker-preview and post-change risk calculators. Until an approved acquisition workflow
binds those existing owners:

- production starts with only the two fixed fail-closed provider dispatchers;
- the owner-callable and scenario stores remain empty after restart;
- no public endpoint accepts callables, raw financial payloads or credentials;
- exact acquisition may report missing scenario sources;
- the final-review route may return `503`;
- Render/GPT/rollback evidence remains `not_executed`;
- no autonomous trading is enabled.

## Production acceptance state

PR-64 still requires eight real evidence cases: Render commit, health, auth-negative,
exact-route-positive, GPT schema import, authenticated Preview, Action-list inspection and
rollback restore. None may be marked passed solely because PR-78 CI is green.

## Что остаётся до полного релиза

### Backend and release acceptance

- approved server-side acquisition that binds existing calculators to the trusted PR-78
  owner ports;
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

**PR-79 — approved server-side owner acquisition v1**:

- selects only existing read-only Decision Engine, capacity and directional preview owners;
- requires an explicit post-change risk calculator that returns
  `ProFormaRiskScenarioV1`;
- derives scenario, correlation, operation and masked account from trusted server context;
- never accepts raw calculator outputs, credentials or full account IDs from the Action;
- calls PR-78 only after every required source is available and fresh;
- maps missing or stale evidence to the existing safe unavailable outcome;
- performs no new HTTP route or production OpenAPI change;
- preserves `app:app`, no broker writes and `trading_methods=false`.

## Запрет ложного завершения

Проект не считается полностью завершённым только потому, что отдельный PR слит или CI
зелёный. Финальная фраза завершения разрешена только после закрытия всех согласованных
пакетов, production acceptance и отдельной проверки полного Definition of Done.
