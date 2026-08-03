# Omni-CIO v9 — Natural Language CIO Router

Status: **WP1 implementation contract**  
Parent program: `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`  
Protected baseline: **Omni-CIO v8.6.1**

## 1. Purpose

WP1 adds a deterministic internal routing layer so ordinary Russian requests can be mapped to the correct Omni-CIO workflow without requiring the owner to know Gateway Action names.

This package does **not** change the applied GPT, add a public API route, call T-Invest, prepare an order or authorize a real-money write. It creates a versioned routing contract and pure classifier that later v9 orchestration can consume.

## 2. Intent taxonomy

`CioIntent` is limited to:

- `EXACT_ACTION` — one or more explicitly named current Gateway operation IDs;
- `DIAGNOSTIC` — Gateway or T-Invest connection diagnostics;
- `ANALYSIS` — portfolio/status/change analysis;
- `PORTFOLIO_MANAGEMENT` — portfolio-wide decision/management request;
- `RISK` — concentration, drawdown, credit/default or other risk review;
- `RESEARCH` — issuer/instrument research or advisory buy/sell question;
- `CASH_ALLOCATION` — allocation of free cash;
- `PLAN_REVIEW` — review of a prepared plan/decision source;
- `EXECUTION` — explicit request to prepare/execute a real or Sandbox trade, or an execution-confirmation phrase;
- `MONITORING` — request to watch a portfolio/instrument/risk signal;
- `UNKNOWN` — no safe deterministic mapping.

Compound compatible requests use one deterministic primary intent plus ordered secondary intents.

## 3. Precedence

Routing order is safety-first:

1. explicit current Action names → `EXACT_ACTION`;
2. explicit execution/confirmation language → `EXECUTION`;
3. Gateway/connection diagnostics → `DIAGNOSTIC`;
4. normal CIO taxonomy with deterministic priority;
5. otherwise `UNKNOWN` + clarification.

Explicit Action names always lock scope. The router must never add a different Action because it believes that Action would be useful.

## 4. Execution boundary

The router reports execution semantics but cannot authorize execution.

Every `IntentRouteV1` hard-codes:

- `router_read_only=true`;
- `execution_authorized=false`.

For direct execution requests the router records:

- contour: `real`, `sandbox`, `unspecified` or `ambiguous`;
- phase: request or confirmation;
- direction: BUY, SELL, none or ambiguous;
- downstream safety requirements.

A direct BUY/SELL command without an explicit real/Sandbox contour is not silently interpreted as a real trade. It returns `execution_contour_required`.

A request that mentions both real money and Sandbox returns `execution_contour_ambiguous`.

A request that asks for both BUY and SELL returns `execution_direction_ambiguous`.

An execution request without a direction returns `execution_direction_required`.

A confirmation phrase can be classified as `EXECUTION_CONFIRMATION`, but the classifier does not validate proposal identity, TTL, HMAC, exact server-generated phrase or idempotency state. Those remain the responsibility of the existing v8.6.1 execution service. Classification is therefore never submit authorization.

## 5. Advisory vs execution language

The router deliberately separates advice from imperative execution.

Examples:

| User phrase | Route |
|---|---|
| `Стоит ли купить SBER?` | RESEARCH |
| `Что купить на свободные деньги?` | CASH_ALLOCATION |
| `Купи 1 лот SBER` | EXECUTION + contour clarification |
| `Купи 1 лот SBER реально` | EXECUTION / REAL / BUY |
| `ПОДТВЕРЖДАЮ РЕАЛЬНУЮ СДЕЛКУ ...` | EXECUTION_CONFIRMATION, still unauthorized |

This prevents ordinary analytical questions containing the infinitive `купить` from being escalated into mutation intent.

## 6. Workflow requirements

The router emits required evidence/workflow classes, not tool calls.

Key mappings:

- portfolio analysis → portfolio snapshot + cash/liquidity + portfolio analytics;
- `Что изменилось?` → the same baseline plus operations history;
- portfolio management/cash allocation → portfolio baseline + policy context;
- risk → portfolio snapshot + analytics;
- research → instrument identity + fresh market;
- plan review → final decision review source;
- real execution → real trading status + identity + fresh market;
- Sandbox execution → Sandbox status + identity + fresh market.

WP2 supplies the versioned policy engine; WP1 only marks `policy_context` as required where personal sizing/portfolio management depends on it.

## 7. Privacy and data handling

`route_user_intent()` is pure and performs no I/O.

The result does not contain the raw user message. Only bounded enums, current operation IDs and safety requirements are returned. This avoids accidentally persisting user free text as routing state.

## 8. Exact-action compatibility

The current v8.6.1 operation registry is explicitly known to the router. Detection is case-insensitive and returns canonical operation IDs in the order in which the user named them.

Examples:

- `Вызови только getPortfolioSnapshot` → only `getPortfolioSnapshot`;
- `Сначала getPortfolioSnapshot, затем getOperationsHistory` → exactly those two, same sequence;
- `Вызови только executeRealTrade` → exact-action scope remains locked, but owner-confirmation requirement remains true and `execution_authorized=false`.

The test suite cross-checks every router Action ID against `gpt/ACTIONS_CATALOG.md`.

## 9. Migration / rollback

WP1 is additive and internal:

- no `app.py` change;
- no OpenAPI route change;
- no broker client/service change;
- no GPT Editor Instructions/Knowledge change;
- no feature flag required because the module is not wired into production behavior in WP1.

Rollback is deletion/revert of the WP1 contract/router imports. Stable v8.6.1 behavior remains the production fallback throughout.

## 10. Exit gate

WP1 is complete only when:

1. the versioned contract and router exist;
2. canonical Russian commands from the v9 program route deterministically;
3. advisory-vs-execution distinction is tested;
4. exact-action isolation is tested;
5. ambiguous real/Sandbox and BUY/SELL intent fails closed;
6. the router never authorizes a write;
7. output does not retain raw user text;
8. ruff, mypy, tests and exact-head Regression Shield are green;
9. the PR is squash-merged and epic #176 marks WP1 complete.
