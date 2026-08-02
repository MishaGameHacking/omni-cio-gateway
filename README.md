# Omni-CIO — Custom GPT + T-Invest Gateway

Omni-CIO — личный инвестиционный аналитик и строго подтверждаемый исполнитель внутри ChatGPT. Пользовательский интерфейс проекта — Custom GPT `Omni-CIO API | Управляющий и аналитик v8.4` (UI-name сохраняется до ручного переименования владельцем).

Canonical behavior/config release: **v8.6.0**.

```text
GitHub main ──> Render Free: `omni-cio-gateway` (`app:app`)
     │                         │
     │                         ├── TINVEST_TOKEN
     │                         │      └── production T-Invest read-only
     │                         │
     │                         ├── optional TINVEST_SANDBOX_TOKEN
     │                         │      └── T-Invest Sandbox / virtual only
     │                         │
     │                         ├── optional TINVEST_TRADING_TOKEN
     │                         │      └── production confirmed LIMIT BUY/SELL only
     │                         │
     │                         └── HTTPS → Upstash Redis Free
     │                                └── durable real-execution journal
     │
     └──> canonical GPT config ──manual apply──> GPT Editor

Custom GPT Actions ──HTTPS/Bearer──> https://omni-cio-gateway.onrender.com
```

## Current release boundary

Engineering Phases 0–2 of real-money execution v1 are merged. The final storage path is being migrated from a paid Render disk requirement to **free external Upstash Redis**, so the existing Render service can stay on the Free plan.

Real execution remains **default-off** until owner configuration + negative Preview acceptance:

`REAL_TRADING_ENABLED=false`

Deployment of current `main` therefore does not itself authorize or submit a real order.

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
- `REAL_TRADING_JOURNAL_BACKEND=upstash`;
- permanent Upstash Redis Free database credentials in Render;
- durable journal integrity;
- exactly one open trading account matching the read-only account.

No Render Persistent Disk or paid Render instance is required for the selected production path.

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

## Free durable execution state

Default production backend:

```text
REAL_TRADING_JOURNAL_BACKEND=upstash
UPSTASH_REDIS_REST_URL=<HTTPS endpoint>
UPSTASH_REDIS_REST_TOKEN=<secret>
```

Properties:

- works from Render Free over outbound HTTPS;
- survives Render sleep, deploys and process restarts;
- HMAC-authenticated journal metadata;
- HMAC-authenticated proposal envelopes;
- HMAC-authenticated daily counters;
- atomic Lua compare-and-swap for proposal transition + daily cap reservation;
- proposal/request UUID lifecycle;
- owner-confirmation evidence hash;
- unknown/submitted daily accounting;
- no broker token storage;
- fail closed if storage is missing, unavailable or tampered.

Current Upstash documentation states its Free Redis tier can be created without a payment card. Provider limits can change, so this project treats the provider as an availability dependency, never as an authorization mechanism.

References:

- `https://upstash.com/redis`
- `https://upstash.com/pricing/redis`
- `docs/operations/REAL_TRADING_DURABLE_STORAGE_V1.md`

SQLite remains an explicit compatibility backend for environments that already have a persistent disk, but is not required for this project's zero-cost deployment.

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

1. free Upstash journal migration is merged/deployed;
2. canonical GPT v8.6 config is applied;
3. owner creates a permanent Upstash Free database and installs only its REST URL/token in Render;
4. owner provisions a separate non-transfer trading token;
5. Phase 3 negative Preview acceptance passes with zero real submit;
6. kill-switch rollback is proven;
7. owner explicitly authorizes the first controlled real LIMIT order;
8. broker order state is reconciled;
9. real portfolio/operations are reconciled;
10. safe replay proves no second submit.

Until then the code remains default-off and no real broker mutation is authorized.
