# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-07-30  
Фактическая вершина программы после merge этого пакета: **PR-82**  
Точная версия определяется текущей вершиной ветки `main`.

## Назначение документа

Этот файл — оперативная карта программы. Он имеет приоритет для определения
активного этапа, если master-context содержит более ранний номер PR.
Стратегические правила и Definition of Done продолжают определяться
`AGENTS.md` и `knowledge/00_PROJECT_MASTER_CONTEXT.md`. Код в `main` остаётся
окончательным источником истины.

## Repository maintenance after PR-78

- PR-105 удалил неэкспортируемый duplicate PR-71 publisher path и закрыл issue #97; trusted scenario publisher остаётся каноническим.
- `docs/master-plan/` сохраняет точную пользовательскую спецификацию, текстовую копию и иерархию источников.
- `gpt/MY_GPT_SETUP_RUNBOOK.md` фиксирует текущую официальную настройку My GPTs/Actions.
- Maintenance-пакеты не заменяют функциональные PR-79…PR-82.

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

В `main` находятся Telegram retirement, broker SDK read-only allowlist,
запрет mutating Actions, hash-locked dependencies, Ruff/formatting/mypy/
coverage, dependency audit, SAST, secret scan, стабильный `app:app`, GET-only
release contract и маскирование счёта.

### P1 — аналитический backend

Реализованы versioned read-only слои для portfolio, cash, operations,
broker-report reconciliation, provenance, quality, analytics, concentration,
stress, conservative risk, market evidence, safe news, instrument
assessments, technical evidence, Decision Engine, threshold rebalancing,
purchase/sell previews, shadow/paper workflows, encrypted paper ledger,
walk-forward/OOS stability и market-capacity gating.

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
- **PR-80:** concrete one-shot installation of existing typed owner ports into PR-79;
- **PR-81:** authenticated route lifecycle for exact approved server-context derivation and bounded capture;
- **PR-82:** exact typed owner snapshots captured after approved calculation and rebound to a fresh authenticated server invocation.

## PR-78 — trusted production owner composition v1

PR-78 materializes already existing typed read-only owners once, validates
that all outputs describe one exact post-change scenario, invokes one fixed
PR-76 provider through the PR-77 store, and removes the temporary owner bundle
on success or downstream failure.

### Explicit pro-forma contract

A plain `RiskPolicyEvaluationV1` does not prove whether it describes current
or post-change risk. PR-78 therefore requires the existing
`ProFormaRiskScenarioV1` and revalidates exact intent fingerprint, masked
account, option, direction, request coverage, timestamps, freshness and
conservative no-margin/no-short/no-derivatives policy.

### Materialization and cleanup

- decision, intent, capacity, pro-forma scenario and selected preview owners are called exactly once;
- capacity and previews are non-empty, typed and bounded;
- purchase and sell types remain isolated;
- account, intent, instruments, scenario and timestamps must reconcile;
- immutable accessors accept only the exact approved invocation request;
- owner exception details are not returned;
- temporary owner bundles and invocation pins are removed in `finally` paths.

## PR-79 — approved server-side owner acquisition v1

PR-79 obtains exact PR-78 owner ports from server-owned loaders. It accepts no
Action payload and derives invocation, scenario, correlation, operation and
masked account only from `FinalDecisionReviewApprovedServerContextV1`.

- context must be typed, masked and fresh before any owner loader is called;
- Decision, intent, capacity, explicit pro-forma scenario and one selected preview lease are each loaded exactly once;
- the opposite preview direction is never called;
- selected leases must be present, metadata-bound and fresh;
- missing, failed, timed-out, mismatched or stale evidence prevents PR-78;
- blocked acquisition maps to existing `FINAL_REVIEW_SOURCE_UNAVAILABLE` / HTTP `503`;
- source and owner exception details are not returned or logged.

## PR-80 — approved typed owner installation v1

PR-80 installs already-existing
`FinalDecisionReviewTrustedPurchaseOwnerPortsV1` or
`FinalDecisionReviewTrustedSellOwnerPortsV1` into one PR-79 acquisition call.

- accepts one immutable approved server context and one typed directional owner bundle;
- validates operation before creating loaders;
- creates fixed Decision, intent, capacity, explicit pro-forma and selected preview loaders;
- binds every loader to the exact context;
- leaves the opposite preview direction uninstalled;
- invokes a temporary PR-79 acquisition once;
- retains no raw financial payload;
- preserves PR-79 freshness/account/source gates and PR-78 routing/cleanup gates.

Production registration remains lazy: startup performs no installation,
owner, calculator, portfolio, network or broker call.

## PR-81 — authenticated route context lifecycle v1

PR-81 closes the proven gap between trusted publication and an authenticated
production request. It does not reconstruct identity from query parameters.
Instead, trusted publication retains a minimal internal seed from the original
`ProFormaRiskIntentBindingV1`:

- exact `scenario_id`;
- trusted publication `correlation_id`;
- purchase/sell operation derived from the original direction;
- masked `AccountReference`;
- publication timestamp.

The seed contains no credentials, full account identifier, positions, amounts,
calculator output, order field or broker payload.

### Authenticated derivation gates

`GET /decision/final-review` creates an approved context only after:

1. the existing Gateway Bearer dependency succeeds;
2. exact bounded-registry source lookup succeeds;
3. PR-59 handler shadow returns the exact compact reviewed response;
4. seed account and response account match;
5. seed operation and response direction match;
6. seed is no older than 300 seconds and not more than 30 seconds in the future.

Invocation ID is generated server-side. The Action `X-Correlation-ID` remains
observability-only; owner routing uses the trusted publication correlation ID.

### Bounded context capture

`FinalDecisionReviewApprovedRouteContextStoreV1` retains only typed approved
contexts:

- process-local;
- TTL 300 seconds;
- default capacity 64;
- duplicate invocation IDs rejected;
- oldest context evicted at capacity;
- restart clears all entries;
- startup context count equals zero.

Authentication failure occurs before the handler and cannot create a context.
A missing or stale seed does not fabricate context and does not expose exception
text. Legacy reviewed responses without a seed remain readable, so PR-81 does
not silently change the existing compact GET contract.

## PR-82 — approved owner snapshot lifecycle v1

PR-82 closes the data-retention gap between a successful allowlisted calculator
invocation and the later authenticated route request without reconstructing a
`DecisionSetV1` from HTTP fields.

### Capture boundary

Snapshot is created only after PR-74 successfully publishes one trusted
purchase or sell scenario. It retains process-local typed objects:

- exact `DecisionSetV1`;
- `CapacityIntentDecisionGateRequestV1`;
- exact `CapacityAssessmentV1` rows;
- explicit `ProFormaRiskScenarioV1`;
- purchase or sell preview rows;
- scenario ID, trusted correlation, operation and masked account.

Capture validates publication direction/account/timestamps, capacity-request
identity, preview coverage and account binding. Failure prevents snapshot
publication and does not consume the invocation replay ID.

### Fresh authenticated rebinding

Original calculator invocation ID is never reused. `select(context)` resolves
only this key:

```text
scenario_id + trusted correlation_id + operation + masked account
```

The selected typed data is rebound to `context.invocation_request()`. Every
new owner callable rejects any other request. Missing, expired, stale or
mismatched snapshots fail closed and do not fabricate owners.

### Runtime and privacy

- process-local bounded store, default TTL 300 seconds and capacity 64;
- expiry cannot exceed explicit pro-forma scenario freshness;
- restart clears all snapshots;
- startup snapshot count equals zero;
- no raw Action body, credentials, full account ID or dynamic provider input;
- no broker/network/portfolio call during registration or selection;
- no HTTP/OpenAPI change;
- no broker write method;
- `app:app` and exactly 14 GET Actions remain unchanged;
- `trading_methods=false`.

## Remaining production boundary

PR-82 provides exact typed owners for one fresh authenticated context, but
intentionally does not invoke PR-80 from the route. The next reviewed package
must, inside the existing server-owned post-auth lifecycle:

- select one fresh PR-82 snapshot for the just-created approved context;
- choose purchase or sell owners only from context operation;
- invoke PR-80 once;
- retain safe internal acquisition evidence without changing the compact response;
- preserve exact scenario/correlation/operation/account identity;
- keep the current response and fail-closed behavior when snapshot or owner evidence is unavailable;
- avoid raw Action calculator values, credentials, full account IDs and dynamic provider selection.

No autonomous trading is enabled. Owner-callable, snapshot and final-review
registries remain empty after restart.

## Production acceptance state

PR-64 still requires eight real evidence cases: Render commit, health,
auth-negative, exact-route-positive, GPT schema import, authenticated Preview,
Action-list inspection and rollback restore. None may be marked passed solely
because PR-82 CI is green.

## Что остаётся до полного релиза

### Backend and release acceptance

- invoke PR-80 once from the authenticated lifecycle using one exact PR-82 snapshot;
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

Shadow, paper и preview инфраструктура не являются разрешением на реальную
торговлю. Confirm-before-trade, idempotency, TTL confirmation, kill switch,
partial-fill и timeout reconciliation требуют отдельной программы допуска и
решения владельца. Полностью автономная торговля без подтверждения не
планируется.

## Следующий пакет после PR-82

Следующий номер не назначается автоматически. Ближайший доказанный gap:

- выбрать fresh snapshot только после authenticated server-context creation;
- вызвать PR-80 one-shot installation для точного purchase/sell owner bundle;
- сохранить безопасное внутреннее evidence и не менять compact GET response;
- сохранить штатный fail-closed outcome при любой недоступности, stale state или mismatch;
- не принимать raw owner outputs, credentials, provider names или full account IDs из Action;
- не менять 14-GET OpenAPI surface.

Production acceptance остаётся отдельным внешним блоком и не заменяется
следующим backend PR.

## Запрет ложного завершения

Проект не считается полностью завершённым только потому, что отдельный PR слит
или CI зелёный. Финальная фраза завершения разрешена только после закрытия всех
согласованных пакетов, production acceptance и отдельной проверки полного
Definition of Done.
