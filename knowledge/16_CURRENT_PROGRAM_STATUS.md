# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-08-03

## Executive state

Omni-CIO remains one supported Custom GPT + one production Render Gateway.

Current production state:

- production read-only analytics: accepted;
- isolated T-Invest Sandbox execution: accepted and Preview-tested;
- real-money v1 engineering Phases 0–2: merged and Regression-Shielded;
- zero-cost durable journal migration: merged and deployed;
- production real journal: permanent Upstash Redis over HTTPS REST;
- Render remains on Free plan, no Persistent Disk required;
- Custom GPT UI/config: `Omni-CIO API | Управляющий и аналитик v8.6.1`;
- GPT Editor Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`;
- real contour is enabled and reports `status=ready`, `execution_ready=true`, `journal_backend=upstash`, `journal_integrity=ok`;
- owner Phase 3 negative acceptance and kill-switch rollback drill are complete;
- owner Phase 4 first controlled real order is complete;
- broker-state, real portfolio/operations and replay/idempotency acceptance are complete;
- real BUY/SELL v1 Definition of Done is **100% complete**.

## Canonical configuration

- UI name: `Omni-CIO API | Управляющий и аналитик v8.6.1`.
- Canonical GPT Editor Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`.
- Full v8.6 engineering reference: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`.
- Recommended model: `Thinking 5.6`.
- Timezone: `Europe/Moscow` / MSK.
- Gateway: `https://omni-cio-gateway.onrender.com`.
- Render plan: Free.
- Entrypoint: `app:app`.
- Production Knowledge: exactly 10 canonical files.

GitHub is canonical for code/config reference but does not automatically synchronize GPT Editor, Render secrets, or Upstash.

## Broker contours

### Production read-only

`TINVEST_TOKEN` remains read-only and separate from execution credentials.

Supported facts include connection, portfolio, enriched positions, cash/liquidity, instrument search, market snapshots, analytics, purchase-capacity preview, operations, broker-report reconciliation and final decision review.

Portfolio-management baseline:

`getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics → analysis`

### Sandbox

Uses only `TINVEST_SANDBOX_TOKEN`, fixed Sandbox host and `SANDBOX_TRADING_ENABLED`.

Owner Preview acceptance on 2026-08-02 demonstrated virtual account/funding/portfolio, BUY/SELL, exact confirmation, wrong/expired confirmation rejection, replay protection, own-position rejection, LIMIT state/cancel and final portfolio reconciliation. All observed responses remained `real_money=false`.

### Real execution v1

Uses only separate account-scoped `TINVEST_TRADING_TOKEN` without transfer access.

Conditional Actions:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- `executeRealTrade`;
- `getRealOrderState`.

Real v1 is deliberately narrow:

- BUY/SELL only;
- supported cash share/ETF only;
- RUB;
- LIMIT / CURRENCY / DAY only;
- own-funds BUY / own-position SELL;
- no margin/short;
- fresh trusted order book;
- exact price step;
- immutable proposal + exact short-lived owner confirmation in a new user turn;
- server hard caps;
- UUID idempotency;
- ambiguous possible-submit = unknown/do-not-resubmit;
- broker reconciliation required;
- `submitted` never means `filled` without broker proof.

No withdrawal/transfer, securities transfer, MARKET/BESTPRICE, derivatives/currencies, stop orders, ReplaceOrder, async submit, autonomous recurring execution or first-release real cancellation exists.

## Durable journal

Selected production backend:

```text
REAL_TRADING_JOURNAL_BACKEND=upstash
UPSTASH_REDIS_REST_URL=<Render Environment>
UPSTASH_REDIS_REST_TOKEN=<Render secret>
```

Accepted properties:

- survives Render Free sleep/deploy/restart;
- no Render disk required;
- HTTPS `*.upstash.io` restriction;
- HMAC-authenticated metadata/proposals/day counters;
- atomic Redis Lua compare-and-swap for proposal transition + daily cap reservation;
- no fallback to memory when storage is unavailable;
- tamper/missing/corrupt state fails closed;
- broker/Gateway/Upstash secrets are not stored in proposal data.

## Owner Phase 3 acceptance — COMPLETE

Completed on 2026-08-03 with zero real submit.

Observed/accepted:

1. permanent Upstash Free database configured in Render;
2. dedicated T-Invest trading token configured separately from read-only token;
3. initial limits: 1000 RUB/order, 2000 RUB/day, 120 s confirmation TTL, 15 s market freshness;
4. `getRealTradingStatus` returned ready, masked account, durable journal true, `journal_backend=upstash`, `journal_integrity=ok`;
5. Custom GPT updated to v8.6.1 Compact, 10 Knowledge files retained, production OpenAPI re-imported;
6. saved GPT successfully called only `getRealTradingStatus` and remained ready;
7. technical proposal generation worked without broker submit;
8. expired confirmation rejected with `REAL_CONFIRMATION_EXPIRED`;
9. deliberately wrong confirmation rejected before execution;
10. excessive BUY rejected by own-funds protection;
11. read-only contour remained isolated;
12. kill switch returned Gateway to healthy read-only state;
13. re-enable restored real readiness with durable journal integrity.

Hard-cap, stale-market, SELL-over-position, replay and ambiguous-submit protections remain covered by merged fake-client/regression tests.

## Owner Phase 4 acceptance — COMPLETE

Completed on 2026-08-03 with explicit owner authorization for the first controlled real order.

Accepted sequence:

1. `getRealTradingStatus` confirmed ready real contour;
2. fresh SBER market snapshot was obtained;
3. `prepareRealTrade` created a 1-lot real LIMIT BUY proposal below the 1000 RUB per-order cap;
4. exact confirmation was supplied by the owner in a new message;
5. exactly one real broker submit was performed;
6. broker initially reported `EXECUTION_REPORT_STATUS_NEW` and zero lots executed;
7. subsequent `getRealOrderState` reconciled `EXECUTION_REPORT_STATUS_FILL`, `lots_executed=1`, `fill_confirmed=true`;
8. executed price reconciled at 280.55 RUB and executed commission at 0.84 RUB;
9. real portfolio reconciled to SBER = 1 share / 1 lot;
10. operations history reconciled the executed SBER purchase at 280.55 RUB and commission at 0.84 RUB;
11. exact confirmation replay did not invoke `executeRealTrade` again and returned the already submitted/filled proposal state;
12. no second broker submit or second SBER purchase was created.

This completes the first real-money owner acceptance and proves the full narrow execution lifecycle:

`prepare → exact owner confirmation → single submit → broker reconciliation → portfolio/operations reconciliation → safe replay`.

## Current safety state

- real contour enabled;
- `status=ready`;
- `execution_ready=true`;
- `journal_backend=upstash`;
- `journal_integrity=ok`;
- account output masked;
- order cap 1000 RUB;
- daily cap 2000 RUB;
- `REAL_TRADING_ENABLED=false` remains the master rollback action for any anomaly.

Release completion does **not** relax any safety rule: every future order still requires fresh market/preflight, a new immutable proposal and an exact short-lived owner confirmation.

## Definition of Done

- [x] threat model/design merged;
- [x] isolated backend merged;
- [x] durable state + conditional OpenAPI merged;
- [x] zero-cost Upstash journal migration merged and deployed;
- [x] permanent Upstash Free database configured;
- [x] dedicated trading token configured separately;
- [x] GPT v8.6.1 Compact applied and saved;
- [x] owner Phase 3 negative acceptance completed with zero real submit;
- [x] kill-switch rollback + recovery completed;
- [x] first controlled real order explicitly authorized and submitted;
- [x] broker state reconciled;
- [x] real portfolio/operations reconciled;
- [x] idempotent replay verified with no second submit.

**Release state: Omni-CIO v8.6.1 real BUY/SELL v1 — 100% complete.**
