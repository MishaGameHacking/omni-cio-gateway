# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-08-03

## Executive state

Omni-CIO remains one supported Custom GPT + one production Render Gateway.

Current production release:

- UI/config: `Omni-CIO API | Управляющий и аналитик v8.6.1`;
- canonical Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`;
- production read-only analytics: accepted;
- isolated T-Invest Sandbox: accepted;
- real-money BUY/SELL v1: accepted and released;
- durable real journal: Upstash Redis over HTTPS;
- Render remains on Free plan;
- stable entrypoint: `app:app`;
- first controlled real order, broker fill, portfolio/operations reconciliation and replay/idempotency acceptance are complete;
- real BUY/SELL v1 Definition of Done is **100% complete**;
- `idempotent replay verified with no second submit`.

Protected release commit:

`baba0fb73e0483fc82b3f0bc7c2f15cbd71d804e`

## Active development program

Canonical second-major-release program:

`docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`

Status: **OWNER-APPROVED / PROGRAM LOCKED**.

Program tracking epic: GitHub issue #176.

Protected baseline/migration contract:

`docs/architecture/V9_BASELINE_AND_RECOVERY_CONTRACT.md`

Development must follow WP0 → WP15 and must not replace or weaken stable v8.6.1 before the relevant package exit gate and acceptance are complete.

### Current package

**WP0 — Baseline freeze and recovery correctness: IN PROGRESS.**

Current WP0 work:

- protected v8.6.1 release commit documented;
- canonical v9 program already locked;
- GPT recovery/version consistency checker introduced;
- recovery documentation drift is being reconciled;
- Regression Shield integration/green exact-head evidence remains required before WP0 is closed.

No user-facing v9 configuration is active yet.

## Canonical production configuration

- UI name: `Omni-CIO API | Управляющий и аналитик v8.6.1`.
- Canonical GPT Editor Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`.
- Full engineering reference: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`.
- Recommended model: `Thinking 5.6`.
- Timezone: `Europe/Moscow` / MSK.
- Gateway: `https://omni-cio-gateway.onrender.com`.
- Render plan: Free.
- Entrypoint: `app:app`.
- Production Knowledge: exactly 10 canonical files from `gpt/CONFIGURATION.md`.

GitHub is canonical for code/config reference but does not automatically synchronize GPT Editor, Render secrets or Upstash state.

## Broker contours

### Production read-only

`TINVEST_TOKEN` remains read-only and separate from execution credentials.

Capabilities include connection, portfolio, enriched positions, cash/liquidity, instrument search, market snapshots, analytics, purchase-capacity preview, operations, broker-report reconciliation and final decision review.

Current portfolio-management baseline:

`getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics → analysis`.

### Sandbox

Uses only `TINVEST_SANDBOX_TOKEN`, fixed Sandbox host and `SANDBOX_TRADING_ENABLED`.

Accepted virtual behavior includes account/funding/portfolio, BUY/SELL, exact confirmation, mismatch/expiry rejection, replay protection, own-position rejection, LIMIT state/cancel and final reconciliation. Sandbox remains `real_money=false`.

### Real execution v1

Uses only separate account-scoped `TINVEST_TRADING_TOKEN` without transfer access.

Conditional Actions:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- `executeRealTrade`;
- `getRealOrderState`.

Safety contract:

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

No withdrawal/transfer, securities transfer, MARKET/BESTPRICE, derivatives/currencies, stop orders, ReplaceOrder, async submit, autonomous recurring execution or token management through GPT.

## Durable journal

Selected production backend:

```text
REAL_TRADING_JOURNAL_BACKEND=upstash
UPSTASH_REDIS_REST_URL=<Render Environment>
UPSTASH_REDIS_REST_TOKEN=<Render secret>
```

Accepted properties:

- survives Render Free sleep/deploy/restart;
- HTTPS external durability;
- HMAC-authenticated metadata/proposals/day counters;
- atomic proposal transition + daily-cap reservation;
- no memory fallback on outage;
- tamper/missing/corrupt state fails closed;
- broker/Gateway/Upstash secrets are not stored in proposal data.

## Owner Phase 3 acceptance — COMPLETE

Completed 2026-08-03 with zero real submit before the first-real phase.

Accepted:

- dedicated trading credential separated from read-only token;
- permanent Upstash configuration;
- ready/integrity status;
- compact GPT config + production OpenAPI;
- wrong/expired confirmation rejection;
- own-funds protection;
- read-only isolation;
- kill switch and recovery.

## Owner Phase 4 acceptance — COMPLETE

Completed 2026-08-03 with explicit owner authorization.

Accepted sequence:

1. real readiness confirmed;
2. fresh SBER market snapshot obtained;
3. 1-lot real LIMIT BUY proposal below the server cap prepared;
4. exact confirmation supplied by owner in a new message;
5. exactly one broker submit performed;
6. initial broker state reported NEW with zero false fill claim;
7. subsequent `getRealOrderState` reconciled `EXECUTION_REPORT_STATUS_FILL`, `lots_executed=1`, `fill_confirmed=true`;
8. executed price reconciled at 280.55 RUB and commission at 0.84 RUB;
9. portfolio reconciled to SBER = 1 share / 1 lot;
10. operations reconciled purchase + commission;
11. exact confirmation replay did not invoke `executeRealTrade` again;
12. no second broker submit or second SBER purchase was created.

This proves the narrow real execution lifecycle:

`prepare → exact owner confirmation → single submit → broker reconciliation → portfolio/operations reconciliation → safe replay`.

## Current safety state

- v8.6.1 production baseline remains active;
- real execution remains explicit-confirmation only;
- account output masked;
- current hard caps remain external server configuration;
- `REAL_TRADING_ENABLED=false` remains the master rollback action for any anomaly;
- v9 development does not authorize broader live execution.

## v9 target direction

The locked v9 program adds, in order, natural-language routing, IPS policy, full market universe, deterministic candidate funnel, evidence/research, credit/rating/default analysis, Fund X-Ray, risk 2.0, strategy selection, capital-scaling optimizer, immutable portfolio plans, safe plan execution, Watchtower, decision/evaluation journal and final GPT v9 recovery/configuration.

Critical financial calculations and constraints must be deterministic Gateway code. Real-money execution remains owner-confirmed and fail-closed.

## v8.6.1 Definition of Done

- [x] threat model/design;
- [x] isolated backend;
- [x] durable state + conditional OpenAPI;
- [x] zero-cost Upstash migration;
- [x] permanent Upstash configured;
- [x] dedicated trading token separated;
- [x] GPT v8.6.1 Compact applied and saved;
- [x] owner Phase 3 negative acceptance;
- [x] kill-switch rollback + recovery;
- [x] first controlled real order explicitly authorized and submitted;
- [x] broker state reconciled;
- [x] real portfolio/operations reconciled;
- [x] idempotent replay verified with no second submit.

**Release state: Omni-CIO v8.6.1 real BUY/SELL v1 — 100% complete.**
