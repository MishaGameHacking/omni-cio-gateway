# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-08-03

## Executive state

Omni-CIO remains one supported Custom GPT + one production Render Gateway.

### Stable production baseline

- production read-only analytics: accepted;
- isolated T-Invest Sandbox execution: accepted and Preview-tested;
- real-money BUY/SELL v1: owner-accepted and released;
- permanent Upstash Redis durable journal: deployed;
- Render remains Free; no Persistent Disk required;
- applied Custom GPT: `Omni-CIO API | Управляющий и аналитик v8.6.1`;
- canonical applied Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`;
- real contour can report `status=ready`, `execution_ready=true`, `journal_backend=upstash`, `journal_integrity=ok` when enabled/configured;
- owner Phase 3, kill-switch drill and Phase 4 first real order acceptance are complete;
- broker-state, real portfolio/operations and replay/idempotency acceptance are complete;
- real BUY/SELL v1 Definition of Done is **100% complete**.

### Active development program

Canonical second-release roadmap:

`docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`

Status: owner-approved / program-locked.

Current package: **WP0 — Baseline freeze and recovery correctness**.

Protected migration contract:

`docs/architecture/V9_BASELINE_FREEZE_AND_MIGRATION.md`

Until v9 Definition of Done is complete, new product development follows this program. Competing roadmaps, duplicate bots, second Gateways, duplicate frontends and unrelated execution surfaces are not started. Blocking defects, security/dependency maintenance and preservation of stable v8.6.1 remain allowed.

## Canonical configuration

- UI name: `Omni-CIO API | Управляющий и аналитик v8.6.1`.
- Canonical GPT Editor Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`.
- Full v8.6 engineering reference: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`.
- Recommended model: `Thinking 5.6` while Actions-compatible.
- Timezone: `Europe/Moscow` / MSK.
- Gateway: `https://omni-cio-gateway.onrender.com`.
- Render plan: Free.
- Entrypoint: `app:app`.
- Production Knowledge: exactly 10 canonical files.

GitHub is canonical for code/config reference but does not automatically synchronize GPT Editor, Render secrets or Upstash.

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

Protected v8.6.1 real lifecycle:

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

No withdrawal/transfer, securities transfer, MARKET/BESTPRICE, derivatives/currencies, stop orders, ReplaceOrder, async submit or autonomous recurring real execution exists in the protected v8.6.1 path.

## Durable journal

Selected production backend:

```text
REAL_TRADING_JOURNAL_BACKEND=upstash
UPSTASH_REDIS_REST_URL=<Render Environment>
UPSTASH_REDIS_REST_TOKEN=<Render secret>
```

Accepted properties:

- survives Render Free sleep/deploy/restart;
- HTTPS REST;
- HMAC-authenticated metadata/proposals/day counters;
- atomic Redis Lua compare-and-swap for critical transitions;
- no fallback to memory when storage is unavailable;
- tamper/missing/corrupt state fails closed;
- broker/Gateway/Upstash secrets are not stored in proposal data.

## Owner Phase 3 acceptance — COMPLETE

Completed on 2026-08-03 with zero real submit.

Verified readiness, separate trading token, permanent Upstash, exact-confirmation rejection paths, own-funds protection, read-only isolation, kill switch and recovery.

Hard-cap, stale-market, SELL-over-position, replay and ambiguous-submit protections remain covered by merged fake-client/regression tests.

## Owner Phase 4 acceptance — COMPLETE

Completed on 2026-08-03 after explicit owner authorization.

Accepted sequence:

1. real contour ready;
2. fresh SBER market snapshot;
3. 1-lot real LIMIT BUY proposal below server cap;
4. exact owner confirmation in new message;
5. exactly one broker submit;
6. initial broker state `EXECUTION_REPORT_STATUS_NEW`;
7. later broker state `EXECUTION_REPORT_STATUS_FILL`, `lots_executed=1`, `fill_confirmed=true`;
8. executed price 280.55 RUB and commission 0.84 RUB reconciled;
9. real portfolio reconciled to SBER = 1 share / 1 lot;
10. operations history reconciled purchase + commission;
11. exact confirmation replay did not invoke a second execution;
12. no second broker submit or second SBER purchase was created.

This proves the narrow real lifecycle:

`prepare → exact owner confirmation → single submit → broker reconciliation → portfolio/operations reconciliation → safe replay`.

## Current safety state

- v8.6.1 production baseline is protected during v9 development;
- `REAL_TRADING_ENABLED=false` remains master rollback;
- account output stays masked;
- current production caps remain server-controlled;
- release completion does not relax any safety rule;
- new v9 engines default to shadow/read-only/feature-flagged behavior until their own acceptance.

## v9 delivery state

- [x] owner-approved v9 master program created and program-locked;
- [ ] WP0 — baseline freeze and recovery correctness;
- [ ] WP1 — Natural Language CIO Router;
- [ ] WP2 — Investment Policy Statement Engine;
- [ ] WP3 — Market Universe Engine;
- [ ] WP4 — Deterministic Candidate Funnel;
- [ ] WP5 — Research & Evidence Engine;
- [ ] WP6 — Credit, Rating & Default Engine 2.0;
- [ ] WP7 — Fund X-Ray Engine;
- [ ] WP8 — Portfolio Risk Engine 2.0;
- [ ] WP9 — Meta-Strategy Selector;
- [ ] WP10 — Portfolio Optimizer & Capital Scaling;
- [ ] WP11 — Immutable Portfolio Plan Protocol;
- [ ] WP12 — Safe Plan Execution Engine;
- [ ] WP13 — Portfolio Watchtower;
- [ ] WP14 — Decision Journal, Evaluation & Learning Loop;
- [ ] WP15 — Custom GPT v9 Configuration & Recovery.

## Definition of Done — stable v8.6.1

- [x] threat model/design merged;
- [x] isolated backend merged;
- [x] durable state + conditional OpenAPI merged;
- [x] permanent Upstash configured;
- [x] dedicated trading token configured separately;
- [x] GPT v8.6.1 Compact applied and saved;
- [x] Phase 3 negative acceptance;
- [x] kill-switch rollback + recovery;
- [x] first controlled real order explicitly authorized and submitted;
- [x] broker state reconciled;
- [x] real portfolio/operations reconciled;
- [x] idempotent replay verified with no second submit.

**Stable release state: Omni-CIO v8.6.1 real BUY/SELL v1 — 100% complete.**

**Development state: Omni-CIO v9 program active; WP0 in progress.**
