# Real-money trading v1 — staged release runbook

Status: **PHASE 3 OWNER ACCEPTANCE + KILL-SWITCH DRILL PASSED. PHASE 4 FIRST CONTROLLED REAL ORDER IS THE ONLY REMAINING RELEASE GATE.**

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

### 3.1 Default-off deployment

Verified:

- `/health` healthy;
- read-only contour remained available;
- durable Upstash configuration initialized;
- no paid Render upgrade/disk required.

### 3.2 Controlled real enable

`REAL_TRADING_ENABLED=true` was deployed intentionally.

`getRealTradingStatus` returned:

- `status=ready`;
- `enabled=true`;
- `configured=true`;
- `mutation_routes_registered=true`;
- `execution_ready=true`;
- masked account only;
- caps 1000 / 2000 RUB;
- confirmation TTL 120 s;
- market freshness 15 s;
- `durable_journal=true`;
- `journal_backend=upstash`;
- `journal_integrity=ok`;
- `real_money=true`;
- `real_trading_methods=true`;
- `sandbox=false`;
- `error_code=null`.

### 3.3 Custom GPT refresh

Applied and saved:

- UI name `Omni-CIO API | Управляющий и аналитик v8.6.1`;
- Instructions `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`;
- exactly 10 canonical Knowledge files;
- production OpenAPI re-imported from `https://omni-cio-gateway.onrender.com/openapi.json`;
- API Key → Bearer authentication retained;
- saved GPT (not only Preview) successfully called `getRealTradingStatus` alone.

Full v8.6 engineering reference remains `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt` and is not pasted on top of Compact.

### 3.4 Negative acceptance results

#### Test A — readiness: PASS

Ready state and durable journal integrity confirmed with zero submit.

#### Test B — read-only regression: PASS for exercised exact-action path

`getPortfolioSnapshot` remained read-only, masked account and did not create a real proposal.

The established portfolio-management routing remains covered by prior acceptance/regression:

`getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics → analysis`

#### Test C — wrong confirmation: PASS

A technical LIMIT proposal was prepared. A deliberately incorrect confirmation phrase was rejected before `executeRealTrade`; no broker order was sent.

#### Test D — expiry: PASS

An exact phrase sent after TTL was rejected with `REAL_CONFIRMATION_EXPIRED`; no broker submit and no fill.

#### Test E — hard cap: ENGINEERING PASS; live isolation not possible without bypassing own-funds guard

A live >1000 RUB attempt was rejected earlier by `GetMaxLots` own-funds protection with `REAL_QUANTITY_EXCEEDS_LIMIT`; no broker submit.

The hard-cap path itself is covered by regression test `test_order_hard_cap_blocks_before_submit`, which requires `REAL_ORDER_CAP_EXCEEDED` and proves `PostOrder` is not called.

Do not fund the real account merely to force this live test.

#### Test F — stale market: ENGINEERING PASS

Regression test requires `REAL_MARKET_DATA_STALE` and zero `PostOrder`.

Do not intentionally create unsafe/stale live market conditions merely for release evidence.

#### Test G — SELL beyond own position: ENGINEERING PASS

Regression test requires own-position rejection and zero `PostOrder`; margin/short limits are not used.

#### Test H — Upstash restart/deploy persistence: PASS

Proposal row count persisted across Render deploy/rollback/re-enable cycle, and readiness returned with `journal_integrity=ok`.

#### Test I — Sandbox independence: PREVIOUSLY ACCEPTED

Sandbox owner acceptance on 2026-08-02 established `real_money=false` and isolated Sandbox behavior.

## 4. Kill-switch rollback drill — COMPLETE

On 2026-08-03:

1. owner set `REAL_TRADING_ENABLED=false`;
2. Render redeployed successfully;
3. `/health` remained `status=ok` and reported `trading_methods=false`;
4. read-only Gateway capabilities remained present;
5. durable Upstash state remained intact;
6. owner restored `REAL_TRADING_ENABLED=true`;
7. saved GPT then returned to `status=ready`, `execution_ready=true`, `journal_backend=upstash`, `journal_integrity=ok`, `real_trading_methods=true`.

PASS. Rollback/recovery is proven before Phase 4.

## 5. Phase 4 — first controlled real order

This is the **only remaining release gate**.

It requires a **new explicit owner instruction at the time of the real order**. General development autonomy, release intent or ordinary portfolio management is not enough to call `executeRealTrade`.

Candidate requirements:

- highly liquid supported cash share/ETF;
- normally 1 lot;
- preliminary total < 1000 RUB;
- LIMIT only;
- fresh trusted order book/trading status;
- exact instrument identity;
- complete own-funds/own-position preflight;
- no margin;
- clear rationale and NO_ACTION alternative.

### Proposal turn

GPT must:

1. label `REAL MONEY` clearly;
2. show masked account;
3. show instrument/ticker;
4. show BUY/SELL;
5. show lots/units;
6. show exact LIMIT price;
7. show preliminary total/commission;
8. show own-funds/own-position limit;
9. show server cap result;
10. show market freshness;
11. show rationale/expiry;
12. show exact `confirmation_phrase`;
13. state **«Реальная заявка ещё не отправлена»**;
14. stop without calling `executeRealTrade`.

### Confirmation turn

Only a new owner message containing the exact phrase may call:

`executeRealTrade(proposal_id, exact phrase)`

No typo correction/substitution.

### Immediately after submit

1. call `getRealOrderState` for the same proposal;
2. do not call a submitted order filled unless broker status proves fill;
3. after fill/partial fill, read back real portfolio/cash/operations as needed;
4. reconcile amount/commission/position;
5. replay the same confirmation once only as the release idempotency test — it must not create a second broker submit;
6. if any state is ambiguous, **never resubmit** — reconcile only.

## 6. First-release cancellation policy

Real cancellation is not part of this release. `cancelRealOrder` is not published and `ReplaceOrder` is forbidden.

For the first controlled order choose parameters intended to execute promptly and avoid leaving an unwanted open order.

## 7. Rollback after release

At any anomaly:

1. set `REAL_TRADING_ENABLED=false`;
2. redeploy/restart;
3. real routes disappear;
4. keep read-only `TINVEST_TOKEN` unchanged;
5. revoke `TINVEST_TRADING_TOKEN` if necessary;
6. preserve Upstash while unresolved `submitting`/`unknown` orders exist;
7. reconcile broker state before deleting operational evidence.

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
- [ ] first minimal real order explicitly authorized and submitted;
- [ ] broker state reconciled;
- [ ] real portfolio/operations reconciled;
- [ ] idempotent replay verified with no second submit.

Only after the final four unchecked items become complete can the real BUY/SELL release be called 100% finished.