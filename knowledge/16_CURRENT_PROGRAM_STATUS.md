# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-07-30  
Фактическая вершина программы после merge этого пакета: **PR-80**  
Точная версия определяется текущей вершиной ветки `main`.

## Назначение документа

Этот файл — краткая оперативная карта программы. Он имеет приоритет для определения
активного этапа, если master-context содержит более ранний номер PR. Стратегические правила
и Definition of Done продолжают определяться `AGENTS.md` и
`knowledge/00_PROJECT_MASTER_CONTEXT.md`. Код в `main` остаётся окончательным источником
истины.

## Repository maintenance after PR-78

- PR-105 removed the unexported duplicate PR-71 publisher path and closed issue #97; the trusted scenario publisher remains canonical.
- `docs/master-plan/` preserves the exact user specification plus a text-search copy and source hierarchy.
- `gpt/MY_GPT_SETUP_RUNBOOK.md` records the current official My GPTs/Actions setup.
- This maintenance does not replace PR-79 or PR-80 and does not change the functional release contract.

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
- **PR-78:** trusted one-shot composition with explicit pro-forma scenario binding;
- **PR-79:** approved server-context acquisition of exact fresh owner leases before PR-78;
- **PR-80:** concrete one-shot installation of existing typed owner ports into PR-79.

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

## PR-79 — approved server-side owner acquisition v1

PR-79 introduces the internal controller that obtains the exact PR-78 owner ports from
server-owned loaders. It accepts no Action payload and derives invocation, scenario,
correlation, operation and masked account only from
`FinalDecisionReviewApprovedServerContextV1`.

### Exact acquisition gates

- the server context must be typed, authenticated, masked and fresh before any owner loader
  is called;
- the Decision Engine, exact intent, capacity, explicit `ProFormaRiskScenarioV1` and one
  directional preview lease are each loaded exactly once;
- the unselected directional preview loader is never called;
- all selected leases must be present, metadata-bound and no older than 300 seconds, with a
  30-second future-clock tolerance;
- missing, failed, timed-out, mismatched or stale evidence prevents PR-78 invocation;
- decision, pro-forma scenario and every directional preview are rebound to the exact
  server-context masked account;
- owner output is still materialized only once by PR-78 and passes all PR-78 binding gates.

### Safe unavailable behavior

A blocked acquisition returns an internal `unavailable` result mapped to the existing
`FINAL_REVIEW_SOURCE_UNAVAILABLE` / HTTP `503` handler outcome. Missing evidence is never
reported as success or pending. Source and owner exception details are not returned or
logged.

### Production startup

`FinalDecisionReviewProductionRuntimeV1` owns the acquisition controller connected to
the same PR-78 composition object. Startup installs fixed missing context/source loaders and
performs no context, owner, calculator, portfolio, network or broker call.

## PR-80 — approved typed owner installation v1

PR-80 adds the concrete adapter that installs already-existing
`FinalDecisionReviewTrustedPurchaseOwnerPortsV1` or
`FinalDecisionReviewTrustedSellOwnerPortsV1` into one PR-79 acquisition call.

### Exact installation contract

- accepts only one immutable `FinalDecisionReviewApprovedServerContextV1` and one typed
  directional PR-78 owner-port bundle;
- verifies the context operation before creating any loader;
- creates fixed Decision, intent, capacity, explicit pro-forma scenario and selected preview
  loaders with one internal provider identity;
- binds every loader to the exact immutable context;
- leaves the opposite preview direction uninstalled and relies on PR-79 never to call it;
- executes the temporary PR-79 acquisition once and retains no raw financial payload;
- preserves all PR-79 freshness, account, direction, source-evidence and 503 gates;
- preserves all PR-78 exact materialization, provider routing and cleanup gates.

### Production registration

`FinalDecisionReviewProductionRuntimeV1` owns one installer sharing the same PR-78
composition as the PR-79 controller. Registration performs no installation or owner call.
The default `app.py` startup still has no authenticated server context and therefore remains
fail-closed; PR-80 is a typed installation boundary, not a fabricated live request lifecycle.

### Compatibility and safety

- Gateway version remains `3.10.0`;
- production OpenAPI remains exactly 14 authenticated GET Actions;
- no route, operation ID, query field or request body is added;
- no raw calculator values, credentials, full account IDs or provider names are accepted
  from an Action;
- no broker order, replacement, cancellation, transfer or withdrawal method is added;
- `app:app` remains stable;
- `trading_methods=false`.

## Remaining production boundary

PR-80 closes the concrete typed loader-installation gap but deliberately does not fabricate
the authenticated server request lifecycle that production does not yet own. Until a later
reviewed package derives and supplies the real server context and typed owner ports:

- production acquisition returns the existing safe `503` unavailable outcome;
- the public Action cannot publish callables, raw financial payloads or credentials;
- no current-risk value can be substituted for explicit post-change risk;
- owner-callable and final-review registries remain empty after restart;
- Render/GPT/rollback evidence remains `not_executed`;
- no autonomous trading is enabled.

## Production acceptance state

PR-64 still requires eight real evidence cases: Render commit, health, auth-negative,
exact-route-positive, GPT schema import, authenticated Preview, Action-list inspection and
rollback restore. None may be marked passed solely because PR-80 CI is green.

## Что остаётся до полного релиза

### Backend and release acceptance

- concrete production derivation of authenticated server context from the actual request
  lifecycle and exact selection of the already-existing typed owner ports before PR-80;
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

## Следующий пакет после PR-80

Следующий номер не назначается автоматически. Ближайший доказанный функциональный gap:

- определить фактический authenticated server request lifecycle, который после успешной
  Gateway authentication может безопасно создать
  `FinalDecisionReviewApprovedServerContextV1`;
- выбрать только уже существующие typed Decision Engine, exact intent, capacity, explicit
  post-change scenario и directional preview owner ports;
- вызвать PR-80 без принятия raw calculator outputs, credentials, provider names или full
  account IDs из Action;
- сохранить штатный `503`, если контекст или хотя бы один owner недоступен или устарел;
- выполнить это отдельной веткой/PR без изменения 14-GET OpenAPI surface.

Production acceptance остаётся отдельным внешним блоком и не заменяется следующим backend
PR.

## Запрет ложного завершения

Проект не считается полностью завершённым только потому, что отдельный PR слит или CI
зелёный. Финальная фраза завершения разрешена только после закрытия всех согласованных
пакетов, production acceptance и отдельной проверки полного Definition of Done.
