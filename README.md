# Omni-CIO — Custom GPT + T-Invest Gateway

Omni-CIO — личный инвестиционный аналитик и строго подтверждаемый исполнитель внутри ChatGPT. Пользовательский интерфейс проекта — Custom GPT `Omni-CIO API | Управляющий и аналитик v8.4` (UI-name сохраняется до ручного переименования владельцем).

Canonical behavior/config release: **v8.6.0**.

```text
GitHub main ──> Render: `omni-cio-gateway` (`app:app`)
     │                         │
     │                         ├── TINVEST_TOKEN
     │                         │      └── production T-Invest read-only
     │                         │
     │                         ├── optional TINVEST_SANDBOX_TOKEN
     │                         │      └── T-Invest Sandbox / virtual only
     │                         │
     │                         └── optional TINVEST_TRADING_TOKEN
     │                                └── production confirmed LIMIT BUY/SELL only
     │
     └──> canonical GPT config ──manual apply──> GPT Editor

Custom GPT Actions ──HTTPS/Bearer──> https://omni-cio-gateway.onrender.com
```

## Current release boundary

Engineering Phases 0–2 of real-money execution v1 are merged and Regression Shield/security are green.

Real execution remains **default-off** until owner configuration + negative Preview acceptance:

`REAL_TRADING_ENABLED=false`

This means deployment of current `main` does not itself authorize or submit a real order.

Current status: `knowledge/16_CURRENT_PROGRAM_STATUS.md`.

Real release runbook: `docs/operations/REAL_TRADING_RELEASE_RUNBOOK.md`.

## Three isolated broker contours

### 1. Production read-only

Uses existing `TINVEST_TOKEN`, which remains read-only.

Capabilities include:

- health/connection;
- portfolio and enriched positions;
- money/liquidity;
- instrument search;
- market snapshots;
- portfolio analytics;
- technical purchase capacity;
- operations history/analytics;
- official broker-report reconciliation;
- final decision review;
- public web/news context through GPT.

Default baseline surface is 14 GET Actions when Sandbox and Real switches are both off.

### 2. Optional Sandbox

Uses only `TINVEST_SANDBOX_TOKEN` and fixed Sandbox host.

With `SANDBOX_TRADING_ENABLED=true` adds 8 virtual-only Actions for:

- status/account;
- virtual funding/portfolio;
- BUY/SELL proposal;
- exact-confirmed execution;
- state reconciliation;
- explicit Sandbox cancellation.

Sandbox is always `real_money=false`.

Owner Preview on 2 August 2026 validated core BUY/SELL, confirmation mismatch/expiry, replay protection, LIMIT status/cancel and portfolio reconciliation.

### 3. Optional real execution v1

Uses only separate `TINVEST_TRADING_TOKEN`.

It never replaces/falls back to `TINVEST_TOKEN`.

Requirements before publish:

- `REAL_TRADING_ENABLED=true`;
- account-scoped full-access **non-transfer** trading token;
- small server order/daily caps;
- Render persistent disk mounted `/var/data`;
- durable journal integrity;
- exactly one open trading account matching the read-only account.

Narrow real Action surface:

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
- exact short-lived owner phrase in a **new user turn**;
- submit once with UUID idempotency;
- immediate broker state reconciliation.

Hard prohibitions:

- withdrawal/transfer;
- securities transfer;
- token creation/rotation through GPT;
- MARKET/BESTPRICE;
- margin/short;
- futures/options/currency execution;
- stop orders;
- ReplaceOrder;
- async submit;
- automatic retry;
- autonomous recurring trading;
- real cancellation in the first real-submit milestone.

`submitted` is not reported as `filled` unless broker execution status explicitly proves fill.

Ambiguous possible-submit failure becomes `unknown_do_not_resubmit`; only state reconciliation is allowed.

## Durable execution state

Production journal:

`/var/data/omni-cio-real-trading.sqlite3`

Properties:

- Render persistent disk required;
- SQLite WAL;
- `synchronous=FULL`;
- atomic daily-cap reservation;
- proposal/request UUID lifecycle;
- HMAC-authenticated rows;
- owner-confirmation evidence hash;
- restart recovery;
- unknown/submitted daily accounting;
- no broker token storage.

## Canonical GPT configuration

Start: `gpt/SETUP_INDEX.md`.

Canonical Instructions:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`

Actions catalog:

`gpt/ACTIONS_CATALOG.md`

Secrets/Render boundary:

`gpt/SECRETS_AND_RENDER.md`

## Development workflow

Rules: `AGENTS.md`.

Use branch → PR → exact-head Regression Shield → merge. Do not bypass CI for broker-write code.

Stable Render entrypoint remains `app:app`.

Default-off read-only contract must remain green when conditional execution flags are false.

## Definition of Done for real BUY/SELL

Engineering merge alone is not sufficient.

The feature is fully released only after:

1. canonical GPT v8.6 config is merged/applied;
2. owner provisions persistent disk + separate non-transfer trading token;
3. Phase 3 negative Preview acceptance passes with zero real submit;
4. kill-switch rollback is proven;
5. owner explicitly authorizes the first controlled real LIMIT order;
6. broker order state is reconciled;
7. real portfolio/operations are reconciled;
8. safe replay proves no second submit.

Until then the code is engineering-ready but the real-money production release is not declared complete.