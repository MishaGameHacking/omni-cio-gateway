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
- real contour is currently enabled and reports `status=ready`, `execution_ready=true`, `journal_backend=upstash`, `journal_integrity=ok`;
- owner Phase 3 negative acceptance and kill-switch rollback drill are complete;
- no real broker order has been submitted during acceptance testing;
- Phase 4 first controlled real order remains the only release gate requiring a new explicit owner authorization at execution time.

Do not call the real BUY/SELL feature fully released until Phase 4 submit, broker-state reconciliation, portfolio/operations reconciliation, and idempotent replay are complete.

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
6. saved GPT (not only Preview) successfully called only `getRealTradingStatus` and remained ready;
7. technical `prepareRealTrade` generated a proposal without broker submit;
8. expired exact confirmation rejected with `REAL_CONFIRMATION_EXPIRED`, no fill and no broker submit;
9. deliberately wrong confirmation rejected before `executeRealTrade`, no broker submit;
10. BUY request beyond own-funds lot limit rejected with `REAL_QUANTITY_EXCEEDS_LIMIT`, proving no margin fallback;
11. read-only `getPortfolioSnapshot` remained isolated and returned masked real account data;
12. kill switch tested: `REAL_TRADING_ENABLED=false` redeploy kept `/health` healthy and reported `trading_methods=false`;
13. real contour re-enabled and returned to `status=ready`, `execution_ready=true`, `journal_integrity=ok` with proposal rows preserved.

Hard-cap, stale-market, SELL-over-position, replay and ambiguous-submit protections are also covered by merged fake-client/regression tests. The live hard-cap scenario could not be isolated because the real account own-funds limit rejected the attempted >1000 RUB test first; no real submit was made.

## Current safety state

Current owner-visible readiness after rollback recovery:

- real contour enabled;
- `status=ready`;
- `execution_ready=true`;
- `journal_backend=upstash`;
- `journal_integrity=ok`;
- account masked;
- order cap 1000 RUB;
- daily cap 2000 RUB;
- Sandbox false for real status;
- no accepted Phase 4 real submit yet.

`REAL_TRADING_ENABLED=false` remains the master rollback action for any anomaly.

## Phase 4 — ONLY REMAINING RELEASE GATE

The first controlled real order requires a new explicit owner instruction at that time. General development autonomy or a portfolio-management command is not sufficient authorization.

Required first-order sequence:

1. choose a highly liquid supported cash security, normally 1 lot, preliminary total < 1000 RUB;
2. LIMIT only, fresh trusted market, exact identity, own-funds/own-position preflight;
3. `prepareRealTrade` and show REAL MONEY proposal + exact phrase, then stop;
4. owner sends exact phrase in a new message;
5. `executeRealTrade` submits once;
6. immediately `getRealOrderState`;
7. do not call it filled unless broker status proves fill;
8. after fill/partial fill, reconcile real portfolio/cash/operations;
9. replay the same confirmation once as an idempotency release test — it must not create a second broker submit;
10. on any ambiguity, never resubmit; reconcile only.

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
- [ ] first controlled real order explicitly authorized and submitted;
- [ ] broker state reconciled;
- [ ] real portfolio/operations reconciled;
- [ ] idempotent replay verified with no second submit.

Until the final four unchecked items pass, Omni-CIO is release-candidate/owner-accepted for safety gates, but the real BUY/SELL feature is not yet 100% released.