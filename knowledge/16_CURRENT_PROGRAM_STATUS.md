# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-08-03

## Executive state

Omni-CIO remains one supported Custom GPT + one production Render Gateway.

Current engineering state:

- production read-only analytics contour: accepted;
- isolated T-Invest Sandbox execution: accepted and extensively Preview-tested;
- real-money v1 Phases 0–2 engineering: merged;
- canonical GPT behavior/config: v8.6.0 merged;
- paid Render Persistent Disk requirement is being removed in favor of a free Upstash Redis durable journal;
- Render service remains on Free plan;
- real-money execution remains default-off until the free-storage migration is merged/deployed and owner Phase 3 configuration/negative acceptance passes;
- first real order has not been authorized or submitted as part of the release program.

Do not declare the real buy/sell feature fully released until Phase 3, rollback drill and Phase 4 controlled real execution/reconciliation pass.

## Canonical Custom GPT configuration

- UI/product name currently remains `Omni-CIO API | Управляющий и аналитик v8.4` until owner manually renames it;
- canonical behavior instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`;
- historical Sandbox instructions: v8.5.0;
- historical read-only fallback: v8.4.1;
- recommended model: `Thinking 5.6`;
- user-visible timezone: `Europe/Moscow` / MSK;
- production Gateway: `https://omni-cio-gateway.onrender.com`;
- Render instance type: Free;
- entrypoint: `app:app`.

GitHub does not automatically update GPT Editor Instructions/Knowledge/OpenAPI or external secrets.

## Production read-only contour

Existing `TINVEST_TOKEN` remains read-only and must stay read-only.

Supported read-only facts include:

- connection/account masking;
- portfolio and enriched positions;
- cash/liquidity;
- instrument search;
- market snapshot and order book;
- portfolio market snapshot/analytics;
- purchase-capacity preview;
- operations history/analytics;
- official broker-report reconciliation;
- reviewed decision retrieval;
- public web/news context through GPT when required.

Portfolio-management routing baseline:

`getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics → analysis`

Fresh-market gate blocks exact personalized sizing when market/order-book evidence is stale or incomplete.

## Sandbox execution accepted

Merged Sandbox backend uses a separate `TINVEST_SANDBOX_TOKEN`, fixed Sandbox host and server kill switch.

Owner Preview acceptance on 2026-08-02 demonstrated:

- healthy `getSandboxTradingStatus` with `real_money=false`;
- confirmed virtual account creation/funding;
- virtual portfolio read-back;
- SBER identity/market resolution;
- MARKET BUY and SELL with two-phase exact confirmation;
- SELL-without-position rejection;
- expiry rejection;
- wrong phrase rejection;
- replay/idempotency protection;
- LIMIT order status → confirmed cancellation → CANCELLED state;
- portfolio reconciliation after tests;
- all observed Sandbox responses remained isolated from real money.

Sandbox remains independent of real execution.

## Real-money release program — Phase 0 complete

Tracking issue: #164.

Merged design package defines:

- separate account-scoped `TINVEST_TRADING_TOKEN`;
- never promote/overwrite `TINVEST_TOKEN`;
- no transfer-access token;
- `REAL_TRADING_ENABLED=false` default-off;
- LIMIT/CURRENCY/DAY cash-security v1 only;
- no margin/short/derivatives/currency execution/stop/replace/async;
- immutable proposal + exact short-lived owner confirmation in a new message;
- own-funds/own-position preflight;
- account binding/masking;
- server hard caps;
- idempotency + ambiguous-submit no-retry;
- durable state requirement;
- rollback and staged acceptance.

Architecture: `docs/architecture/REAL_TRADING_V1.md`.

Runbook: `docs/operations/REAL_TRADING_RELEASE_RUNBOOK.md`.

## Real-money release program — Phase 1 complete

Merged `omni_cio/real_trading/` core provides:

- production REST host fixed to `https://invest-public-api.tbank.ru/rest`;
- narrow method allowlist;
- dedicated token passed explicitly; no `TINVEST_TOKEN` environment fallback inside real package;
- exactly one open trading account required and bound to the read-only account;
- cash share/ETF + RUB + LIMIT only;
- exact price-step validation;
- `GetMaxLots` own-funds BUY / own-position SELL checks;
- `GetOrderPrice` cost/commission preview;
- configurable order/daily caps plus immutable code ceilings;
- trusted fresh market gate;
- HMAC-bound proposal/confirmation;
- pre-submit account/market/preflight revalidation;
- atomic daily reservation;
- UUID idempotency;
- `PostOrder` with `TIME_IN_FORCE_DAY`, `PRICE_TYPE_CURRENCY`, `confirmMarginTrade=false`;
- definitive rejection → failed;
- possible-submit transport/5xx ambiguity → unknown/do-not-resubmit;
- request-id `GetOrderState` reconciliation;
- masked/sanitized broker data;
- production requires a durable journal.

Fake-client/security/regression tests are merged and green.

## Real-money release program — Phase 2 backend merged

PR #168 — `Trading: add durable state and conditional real-money Actions` — passed exact-head Regression Shield/security and was squash-merged as commit:

`68e2a658c6d379e8e446b6bc0b46d78beb70c755`

Merged Phase 2 provides trusted market adapter, conditional Action publication, proposal persistence contract, restart recovery semantics and journal integrity gates.

### Conditional Actions

When `REAL_TRADING_ENABLED=false`, all Real Trading Actions are absent.

When flag is true but mandatory static config/journal is invalid, only safe readiness status can publish; mutation routes remain absent.

When static readiness is valid, only these real Actions register:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- `executeRealTrade` — consequential;
- `getRealOrderState`.

No real cancel/replace/transfer/withdraw/market/margin route exists in first release.

Default-off read-only release contract remains green.

## Free durable-storage migration — current engineering package

The initial Phase 2 storage selected SQLite on a paid Render Persistent Disk. The owner cannot use the paid Render plan, so the production storage strategy is being migrated without weakening the real-order safety model.

Selected default backend:

`UpstashRealExecutionJournalV1`

Server configuration:

```text
REAL_TRADING_JOURNAL_BACKEND=upstash
UPSTASH_REDIS_REST_URL=<Render Environment>
UPSTASH_REDIS_REST_TOKEN=<Render secret>
```

Target properties:

- Render Web Service stays Free;
- no `/var/data` disk required;
- external durable state survives Render Free sleep/deploy/restart;
- REST endpoint restricted to HTTPS `*.upstash.io`;
- HMAC-authenticated journal metadata;
- HMAC-authenticated proposal envelopes;
- HMAC-authenticated Moscow-day notional counters;
- authenticated proposal-count metadata detects missing/extra stored proposal rows;
- atomic Redis Lua compare-and-swap for concurrent proposal/daily-limit mutation;
- durable reservation still happens before T-Invest `PostOrder`;
- definitive rejection releases daily reserved notional;
- `unknown` remains reserved;
- storage outage/tamper fails closed and never falls back to ephemeral memory;
- SQLite remains an explicit compatibility/test backend only.

Upstash currently documents a Free Redis tier and no-credit-card creation. Pricing/limits remain an external provider condition, not a safety assumption.

Durable-storage document: `docs/operations/REAL_TRADING_DURABLE_STORAGE_V1.md`.

## Trusted real market adapter

Real execution consumes the established read-only market snapshot but fails closed unless:

- requested/resolved UID identity matches;
- reference/trading status/order book components are complete;
- identity has no conflict;
- instrument type is v1-supported;
- lot/min-price increment are valid;
- API trading + limit order flags allow the request;
- freshness is proven by `order_book.time`, not merely gateway request time.

## Current secret/infrastructure boundary

GitHub stores no values of:

- `TINVEST_TOKEN`;
- `TINVEST_SANDBOX_TOKEN`;
- `TINVEST_TRADING_TOKEN`;
- `UPSTASH_REDIS_REST_TOKEN`;
- `GATEWAY_API_KEY`;
- Authorization headers;
- full account IDs;
- private broker payloads as configuration.

One Render Free service remains canonical.

Details: `gpt/SECRETS_AND_RENDER.md`.

## Current Action surface before owner real enable

Expected production behavior while `REAL_TRADING_ENABLED=false`:

- baseline 14 read-only GET Actions;
- +8 Sandbox Actions if `SANDBOX_TRADING_ENABLED=true`;
- no Real Trading Actions.

This remains the safe state during code/document deployment.

## Next gate after free-storage PR merges — Phase 3 owner configuration, NO REAL SUBMIT

The next owner-only work will be:

1. create/claim one permanent Upstash Redis Free database;
2. add its HTTPS REST URL and REST token only to Render Environment;
3. keep `REAL_TRADING_JOURNAL_BACKEND=upstash`;
4. issue separate account-scoped full-access T-Invest trading token without transfer access;
5. store it only as `TINVEST_TRADING_TOKEN`;
6. keep `TINVEST_TOKEN` unchanged/read-only;
7. keep initial caps at 1000 RUB per order / 2000 RUB per day;
8. keep `REAL_TRADING_ENABLED=false` initially;
9. deploy and run read-only/Sandbox smoke;
10. controlled enable;
11. apply/re-import GPT v8.6 configuration;
12. complete negative Preview acceptance with zero real submit;
13. restart Render and prove Upstash journal persistence;
14. prove kill-switch rollback removes Real Trading Actions.

No Render upgrade or persistent disk purchase is required.

Exact steps: `docs/operations/REAL_TRADING_RELEASE_RUNBOOK.md` and `gpt/SETUP_INDEX.md`.

## Phase 4 still required for Definition of Done

After Phase 3 passes, a first real order requires a **new explicit owner instruction at that time**.

It must be:

- liquid supported cash security;
- minimum practical size;
- LIMIT only;
- fresh market;
- complete proposal;
- exact confirmation in a new message;
- submit once;
- immediate `getRealOrderState`;
- broker fill/partial-fill truth preserved;
- real portfolio/operations reconciled;
- idempotent replay verified safely;
- stop on any ambiguity.

## Definition of Done

Do not use the final completion phrase until all of these are complete:

- free durable-storage code merged after exact-head Regression Shield/security;
- free default-off deployment healthy;
- permanent Upstash Free database configured;
- GPT v8.6 configuration applied;
- owner Phase 3 negative Preview acceptance;
- kill-switch rollback drill;
- first controlled real order explicitly authorized;
- broker state reconciled;
- real portfolio/operations reconciled;
- replay protection verified without a second submit.

Until then the release is engineering-ready/default-off, not fully owner-accepted real-money production.
