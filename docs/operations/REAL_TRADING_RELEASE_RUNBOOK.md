# Real-money trading v1 — staged release runbook

Status: **RELEASE COMPLETE. PHASES 0–4 OWNER-ACCEPTED. REAL BUY/SELL v1 DEFINITION OF DONE = 100%.**

Architecture: `docs/architecture/REAL_TRADING_V1.md`.

Durable storage: `docs/operations/REAL_TRADING_DURABLE_STORAGE_V1.md`.

Tracking issue: #164.

## 0. Absolute safety rules

Existing production credential remains:

`TINVEST_TOKEN = read-only`

Never replace or promote it.

Real trading uses only:

`TINVEST_TRADING_TOKEN = separate account-scoped full-access, non-transfer token`

First release forbids withdrawal/transfer, securities transfer, token-management,
MARKET/BESTPRICE, margin/short, futures/options/currency execution, stop order,
replace, async submit, autonomous recurring execution and real cancellation.

`REAL_TRADING_ENABLED=false` remains the master rollback state.

## 1. Engineering acceptance — COMPLETE

Merged and Regression-Shielded:

- separate token/account binding;
- fixed production broker host/method allowlist;
- LIMIT/CURRENCY/DAY only;
- immutable proposal + exact short-lived confirmation;
- own-funds BUY / own-position SELL;
- `GetOrderPrice` preview;
- price-step validation;
- hard per-order/daily caps + immutable ceilings;
- fresh market/data gate;
- repeat preflight immediately before submit;
- `confirmMarginTrade=false`;
- UUID idempotency;
- ambiguous-submit no-retry;
- broker `GetOrderState` reconciliation;
- audit/redaction;
- durable journal integrity;
- conditional OpenAPI publication;
- rollback plan.

The selected production durable journal is Upstash Redis over HTTPS REST. SQLite remains compatibility/test only.

Conditional Real Action surface:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- consequential `executeRealTrade`;
- `getRealOrderState`.

When `REAL_TRADING_ENABLED=false`, all real-trading Actions are absent.

## 2. Zero-cost infrastructure — COMPLETE

Production remains one Render Web Service:

`omni-cio-gateway`

Instance type:

`Free`

No Render Persistent Disk is required.

Permanent Upstash Redis Free database is configured through Render Environment only:

```text
REAL_TRADING_JOURNAL_BACKEND=upstash
UPSTASH_REDIS_REST_URL=<HTTPS endpoint>
UPSTASH_REDIS_REST_TOKEN=<secret REST token>
```

Trading token is stored only as:

`TINVEST_TRADING_TOKEN`

Existing read-only `TINVEST_TOKEN` remains unchanged.

Initial release limits:

```text
REAL_TRADING_MAX_ORDER_RUB=1000
REAL_TRADING_MAX_DAILY_RUB=2000
REAL_TRADING_CONFIRMATION_TTL_SECONDS=120
REAL_TRADING_MARKET_MAX_AGE_SECONDS=15
```

## 3. Owner Phase 3 — COMPLETE, ZERO REAL SUBMIT

Completed on 2026-08-03.

Verified:

- readiness and durable Upstash journal integrity;
- saved GPT v8.6.1 configuration and conditional Actions;
- wrong confirmation rejection;
- expired confirmation rejection;
- own-funds protection without margin fallback;
- read-only isolation;
- engineering hard-cap/stale-market/SELL-over-position protections;
- Upstash persistence across deploy/restart;
- Sandbox independence.

## 4. Kill-switch rollback drill — COMPLETE

On 2026-08-03:

1. owner set `REAL_TRADING_ENABLED=false`;
2. Render redeployed successfully;
3. `/health` remained `status=ok` and reported `trading_methods=false`;
4. read-only Gateway capabilities remained present;
5. durable Upstash state remained intact;
6. owner restored `REAL_TRADING_ENABLED=true`;
7. saved GPT returned to `status=ready`, `execution_ready=true`, `journal_backend=upstash`, `journal_integrity=ok`, `real_trading_methods=true`.

PASS. Rollback/recovery was proven before Phase 4.

## 5. Phase 4 — first controlled real order — COMPLETE

Completed on 2026-08-03 after a new explicit owner instruction authorizing the first controlled real-money transaction.

### Candidate and proposal

Selected instrument: SBER cash share.

Accepted candidate properties:

- highly liquid supported cash share;
- BUY;
- 1 lot / 1 share;
- LIMIT / CURRENCY / DAY;
- fresh trusted market snapshot;
- exact price step;
- own-funds preflight;
- no margin;
- preliminary total below the 1000 RUB server cap.

The owner received a clearly labelled REAL MONEY proposal with masked account, exact price, preliminary amount/commission, available lots, market freshness, expiry and exact confirmation phrase. `executeRealTrade` was not called in the proposal turn.

### Confirmation and submit

The owner supplied the exact short-lived confirmation phrase in a new message.

Exactly one real LIMIT order was submitted.

Initial broker state:

- `EXECUTION_REPORT_STATUS_NEW`;
- 0 of 1 lot executed;
- no false claim of fill.

### Broker-state reconciliation

A subsequent `getRealOrderState` returned:

- `status=reconciled`;
- `executionReportStatus=EXECUTION_REPORT_STATUS_FILL`;
- `direction=BUY`;
- `quantity_lots=1`;
- `lots_executed=1`;
- `limit_price=280.55 RUB`;
- `executed_price=280.55 RUB`;
- `executed_commission=0.84 RUB`;
- `real_money=true`;
- `sandbox=false`;
- `fill_confirmed=true`.

PASS.

### Real portfolio/operations reconciliation

Read-back confirmed:

- cash balance 718.61 RUB;
- SBER position = 1 share / 1 lot;
- SBER average price 280.55 RUB;
- executed SBER purchase = 280.55 RUB;
- commission = 0.84 RUB;
- total cash debit including commission = 281.39 RUB.

The portfolio and operations state reconciled to the broker-confirmed fill.

PASS.

### Replay/idempotency acceptance

The exact confirmation phrase used for the completed proposal was replayed once as the release test.

Observed result:

- replay returned the already submitted/filled proposal state;
- `EXECUTION_REPORT_STATUS_FILL` remained the reconciled state;
- `lotsExecuted=1/1`;
- `fill_confirmed=true`;
- `executeRealTrade` was **not** called again;
- no second broker submit was created;
- no second SBER purchase appeared.

PASS.

The complete real-money lifecycle is now owner-accepted:

`prepare → exact owner confirmation → single submit → broker reconciliation → portfolio/operations reconciliation → safe replay`.

## 6. First-release cancellation policy

Real cancellation is not part of this release. `cancelRealOrder` is not published and `ReplaceOrder` is forbidden.

## 7. Rollback after release

At any anomaly:

1. set `REAL_TRADING_ENABLED=false`;
2. redeploy/restart;
3. real routes disappear;
4. keep read-only `TINVEST_TOKEN` unchanged;
5. revoke `TINVEST_TRADING_TOKEN` if necessary;
6. preserve Upstash while unresolved `submitting`/`unknown` orders exist;
7. reconcile broker state before deleting operational evidence.

Release completion does not weaken the safety contract. Every future real order still requires a fresh trusted market/preflight, a new immutable proposal, and a new exact owner confirmation.

## 8. Definition of Done

- [x] threat model/design merged;
- [x] isolated backend merged;
- [x] durable execution-journal contract implemented/tested;
- [x] conditional OpenAPI surface implemented/tested;
- [x] exact-head Regression Shield/security green for engineering release;
- [x] no transfer/withdraw/margin/replace/market execution surface;
- [x] wrong/expired confirmation/replay/ambiguous-submit protections covered by tests;
- [x] GPT v8.6.1 Compact configuration merged/applied;
- [x] Upstash journal migration merged and deployed;
- [x] permanent Upstash Free database configured in Render;
- [x] owner Phase 3 negative acceptance complete;
- [x] kill-switch rollback/recovery drill complete;
- [x] first minimal real order explicitly authorized and submitted;
- [x] broker state reconciled;
- [x] real portfolio/operations reconciled;
- [x] idempotent replay verified with no second submit.

**Real BUY/SELL v1 release is 100% finished.**
