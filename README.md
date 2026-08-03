# Omni-CIO — Custom GPT + T-Invest Gateway

Omni-CIO — личный инвестиционный аналитик и строго подтверждаемый исполнитель внутри ChatGPT.

Current UI/config release: **`Omni-CIO API | Управляющий и аналитик v8.6.1`**.

Canonical GPT Editor Instructions: **`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`**.

Full v8.6 engineering reference: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`.

```text
GitHub main ──> Render Free: `omni-cio-gateway` (`app:app`)
     │                         │
     │                         ├── TINVEST_TOKEN
     │                         │      └── production T-Invest read-only
     │                         ├── optional TINVEST_SANDBOX_TOKEN
     │                         │      └── T-Invest Sandbox / virtual only
     │                         ├── optional TINVEST_TRADING_TOKEN
     │                         │      └── confirmed production LIMIT BUY/SELL only
     │                         └── HTTPS → Upstash Redis Free
     │                                └── durable real-execution journal
     │
     └──> canonical GPT config ──manual apply──> GPT Editor

Custom GPT Actions ──HTTPS/Bearer──> https://omni-cio-gateway.onrender.com
```

## Current release boundary

**Omni-CIO v8.6.1 real-money BUY/SELL v1 is fully released and owner-accepted as of 2026-08-03.**

Engineering Phases 0–2 are merged and green. Zero-cost durable state is deployed on permanent Upstash Redis while the Render service remains on the Free plan.

Owner Phase 3 acceptance completed successfully, including wrong/expired confirmation rejection, own-funds protection, read-only isolation, durable Upstash persistence, kill-switch rollback and recovery.

Owner Phase 4 acceptance then completed with one explicitly authorized real LIMIT BUY of 1 lot SBER:

- broker accepted the real order;
- `getRealOrderState` reconciled `EXECUTION_REPORT_STATUS_FILL`;
- 1 of 1 lot executed at 280.55 RUB;
- executed commission reconciled at 0.84 RUB;
- real portfolio showed SBER = 1 share / 1 lot;
- operations history showed the executed SBER purchase and separate commission operation;
- replay of the exact confirmation phrase did not call `executeRealTrade` again and did not create a second broker submit.

The complete Definition of Done for real BUY/SELL v1 is now satisfied.

Current status: `knowledge/16_CURRENT_PROGRAM_STATUS.md`.

Real release runbook: `docs/operations/REAL_TRADING_RELEASE_RUNBOOK.md`.

## Three isolated broker contours

### 1. Production read-only

Uses existing `TINVEST_TOKEN`, which remains read-only.

Capabilities include health/connection, portfolio/enrichment, cash/liquidity, instrument search, market snapshots, portfolio analytics, purchase-capacity preview, operations analytics/history, broker-report reconciliation and final decision review.

Portfolio-management routing starts:

`getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics → analysis`

### 2. Optional Sandbox

Uses only `TINVEST_SANDBOX_TOKEN` and fixed Sandbox host.

With `SANDBOX_TRADING_ENABLED=true` adds virtual-only account/funding/portfolio/proposal/execution/state/cancel behavior. Sandbox is always `real_money=false`.

Owner Preview on 2 August 2026 validated BUY/SELL, confirmation mismatch/expiry, replay protection, own-position rejection, LIMIT state/cancel and portfolio reconciliation.

### 3. Optional real execution v1

Uses only separate `TINVEST_TRADING_TOKEN`; it never replaces or falls back to `TINVEST_TOKEN`.

Selected production requirements:

- `REAL_TRADING_ENABLED=true` for active contour;
- account-scoped full-access trading token without transfer access;
- small server order/daily caps;
- `REAL_TRADING_JOURNAL_BACKEND=upstash`;
- permanent Upstash Redis credentials stored only in Render;
- durable journal integrity;
- exactly one open trading account matching the read-only account.

Narrow Real Action surface:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- `executeRealTrade`;
- `getRealOrderState`.

## Real execution safety contract

First release allows only:

- BUY/SELL;
- supported cash share/ETF;
- RUB;
- LIMIT / CURRENCY / DAY;
- own-funds BUY;
- own-position SELL;
- exact price step;
- fresh trusted order book;
- immutable proposal;
- exact short-lived owner phrase in a new user turn;
- submit once with UUID idempotency;
- immediate broker-state reconciliation.

Hard prohibitions:

- withdrawal/transfer/securities transfer;
- token management through GPT;
- MARKET/BESTPRICE;
- margin/short;
- futures/options/currency execution;
- stop orders;
- ReplaceOrder;
- async submit;
- automatic retry;
- autonomous recurring trading;
- real cancellation in the first release.

`submitted` is never reported as `filled` unless broker execution status proves fill.

Ambiguous possible-submit failure becomes unknown/do-not-resubmit; only reconciliation is allowed.

## Free durable execution state

Production backend:

```text
REAL_TRADING_JOURNAL_BACKEND=upstash
UPSTASH_REDIS_REST_URL=<HTTPS endpoint>
UPSTASH_REDIS_REST_TOKEN=<secret>
```

Properties:

- works from Render Free over outbound HTTPS;
- survives Render sleep/deploy/restart;
- HMAC-authenticated journal metadata/proposals/day counters;
- atomic Redis Lua compare-and-swap for proposal transition + daily cap;
- UUID proposal/request lifecycle;
- no broker token storage;
- fail closed if storage is unavailable or tampered.

SQLite remains compatibility/test only.

## Canonical GPT configuration

Start: `gpt/SETUP_INDEX.md`.

Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`.

Registry: `gpt/CONFIGURATION.md`.

Actions: `gpt/ACTIONS_CATALOG.md`.

Secrets/Render boundary: `gpt/SECRETS_AND_RENDER.md`.

## Development workflow

Rules: `AGENTS.md`.

Use branch → PR → exact-head Regression Shield → squash merge. Do not bypass CI for broker-write code.

Stable Render entrypoint remains `app:app`.

## Definition of Done for real BUY/SELL

Completed:

1. threat model/design;
2. isolated backend;
3. durable Upstash state + conditional Actions;
4. canonical v8.6.1 Compact GPT config applied;
5. permanent Upstash + dedicated trading token configured;
6. Phase 3 negative acceptance with zero submit;
7. kill-switch rollback and recovery;
8. owner explicitly authorized and submitted one first controlled real LIMIT order;
9. broker order state reconciled to confirmed fill;
10. real portfolio/operations reconciled;
11. replay proved no second submit.

**Status: real BUY/SELL v1 release 100% complete.**