# Omni-CIO v9.0.0 — reviewed GPT Actions catalog

Gateway: `https://omni-cio-gateway.onrender.com`  
Schema authority: `https://omni-cio-gateway.onrender.com/openapi.json`  
Stable entrypoint: `app:app`

`gatewayHealth` is public; protected Actions use the existing Bearer Gateway authentication.

## 0. WP15 authority rule

This catalog documents the reviewed production surface. The **effective imported OpenAPI** is the runtime authority for what the GPT can call.

WP1–WP14 also contain internal deterministic engines. They are **not automatically GPT Actions**. If an operationId is absent from current `/openapi.json`, the GPT must not invent/call it or claim that internal engine executed.

WP15 changes GPT configuration/recovery; it does not create a second API surface and does not implicitly broaden real-money authority.

## 1. Baseline production read-only surface

When conditional Sandbox and Real execution surfaces are disabled, the reviewed public GPT surface is exactly these 14 GET Actions:

| operationId | HTTP | Path | Purpose |
|---|---:|---|---|
| `gatewayHealth` | GET | `/health` | Gateway health/build/capabilities |
| `getConnection` | GET | `/connection` | T-Invest connection + masked account |
| `getPortfolioSnapshot` | GET | `/snapshot` | Portfolio and cash facts |
| `getEnrichedPortfolioSnapshot` | GET | `/snapshot/enriched` | Positions + canonical instrument identity |
| `findInstrument` | GET | `/instruments/search` | Instrument lookup |
| `getOperationsHistory` | GET | `/operations` | Read-only operation history |
| `getMarketSnapshot` | GET | `/market/snapshot` | Identity/order book/trading status |
| `getPortfolioMarketSnapshot` | GET | `/portfolio/market-snapshot` | Current portfolio market valuation |
| `getPortfolioAnalytics` | GET | `/portfolio/analytics` | Structure/concentration/data quality |
| `getCashLiquiditySnapshot` | GET | `/portfolio/cash-liquidity` | Cash/liquidity diagnostics |
| `getPurchaseCapacityPreview` | GET | `/portfolio/purchase-capacity` | Technical read-only purchase capacity |
| `getOperationsAnalytics` | GET | `/operations/analytics` | Cash flow/categories/reconciliation |
| `getBrokerReportReconciliation` | GET | `/operations/broker-report-reconciliation` | Official broker-report reconciliation |
| `getFinalDecisionReview` | GET | `/decision/final-review` | Reviewed read-only decision source |

Production read-only broker credential remains isolated and is never a fallback for real execution.

## 2. Conditional Sandbox surface

Only when Sandbox is enabled by the server, these 8 operations may additionally appear:

| operationId | HTTP | Path | Consequential | Purpose |
|---|---:|---|---:|---|
| `getSandboxTradingStatus` | GET | `/sandbox/status` | no | Sandbox readiness/accounts |
| `openSandboxAccount` | POST | `/sandbox/account/open` | yes | Open virtual account after confirmation |
| `fundSandboxAccount` | POST | `/sandbox/account/fund` | yes | Fund virtual RUB after confirmation |
| `getSandboxPortfolio` | GET | `/sandbox/portfolio` | no | Virtual portfolio |
| `prepareSandboxTrade` | POST | `/sandbox/trade/prepare` | no submit | Immutable virtual proposal |
| `executeSandboxTrade` | POST | `/sandbox/trade/execute` | yes | Submit virtual proposal after exact phrase |
| `getSandboxOrderState` | GET | `/sandbox/order/status` | no | Virtual broker-state reconciliation |
| `cancelSandboxOrder` | POST | `/sandbox/order/cancel` | yes | Sandbox-only cancel after confirmation |

Sandbox must always be presented as virtual (`sandbox=true`, `real_money=false`).

## 3. Conditional REAL execution surface

Real operations register only under the existing real-trading server feature/readiness gates.

If real feature flag is on but static readiness is incomplete, the safe surface may expose only `getRealTradingStatus`.

When fully ready, the reviewed Real v1 surface is limited to:

| operationId | HTTP | Path | Consequential | Purpose |
|---|---:|---|---:|---|
| `getRealTradingStatus` | GET | `/real-trading/status` | no | Real readiness/account binding/limits/durable-state integrity |
| `prepareRealTrade` | POST | `/real-trading/trade/prepare` | no submit | Immutable real LIMIT proposal + exact phrase |
| `executeRealTrade` | POST | `/real-trading/trade/execute` | **yes** | One exact previously prepared proposal after owner phrase |
| `getRealOrderState` | GET | `/real-trading/order/state` | no | Broker reconciliation by original request UUID |

### Real hard contract

- separate real-execution broker credential; no read-only fallback;
- masked user-facing account identity;
- supported cash share/ETF, RUB, BUY/SELL only for current v1;
- LIMIT / CURRENCY / DAY;
- own-funds BUY / own-position SELL;
- no margin/uncovered short;
- server per-order/daily hard caps;
- trusted fresh market and exact price step;
- `prepareRealTrade` submits nothing;
- `executeRealTrade` uses only immutable proposal identity + exact owner phrase;
- owner phrase must arrive in a new user turn;
- UUID idempotency;
- ambiguous possible-submit = reconciliation only, no automatic retry;
- submitted != filled without broker proof;
- durable authenticated state required and failure is fail-closed.

### Explicit Real prohibitions

No production GPT/OpenAPI authority for:

- withdrawal or money/securities transfer;
- token creation/rotation;
- MARKET/BESTPRICE;
- margin/short;
- futures/options/currency execution under this reviewed surface;
- stop orders;
- ReplaceOrder/PostOrderAsync;
- autonomous recurring real execution;
- implicit cap increases;
- real cancellation unless a future separately reviewed release adds it.

## 4. Watchtower / v9 internal services

Watchtower internal routes are hidden (`include_in_schema=False`) and authenticated by scheduler signatures. They are not GPT Actions.

The v9 router/policy/universe/candidate/research/credit/fund/risk/strategy/optimizer/portfolio-plan/plan-execution/decision-journal packages likewise do not become GPT Actions merely because they exist in the repository.

The target v9 GPT Instructions therefore use their reviewed rules as decision discipline while only calling actual operationIds from effective OpenAPI.

## 5. GPT Actions compatibility

- OpenAPI v3 production schema;
- approved HTTPS production host;
- one Bearer security scheme for protected operations;
- `gatewayHealth` public;
- explicit operationIds and response properties;
- consequential mutation operations marked accordingly where supported;
- consequential UI is supplemental and never replaces server-side owner confirmation/idempotency.

## 6. Possible effective surfaces

| Sandbox | Real readiness | Expected surface |
|---|---|---|
| OFF | OFF | 14 baseline GET |
| ON | OFF | baseline + 8 Sandbox |
| OFF/ON | Real flag ON but not ready | baseline (+ Sandbox if enabled) + `getRealTradingStatus` |
| OFF | Real ready | baseline + 4 Real |
| ON | Real ready | baseline + 8 Sandbox + 4 Real |

## 7. Existing GPT refresh after WP15 repository merge

1. Open the **existing** Omni-CIO GPT in ChatGPT web Edit/Configure.
2. Refresh the existing Action from production `/openapi.json`.
3. Authentication remains API Key → Bearer with the existing externally managed Gateway key.
4. Compare imported operationIds with the tables above and actual enabled contours.
5. Apply `gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt`.
6. Run `gpt/MY_GPT_SETUP_RUNBOOK.md` Preview acceptance.
7. Select `Update` only after Preview passes.

Do not create a duplicate GPT or a second Action gateway for v9.

GitHub never stores authentication values and does not update GPT Editor automatically.
