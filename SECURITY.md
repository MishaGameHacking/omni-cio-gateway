# Omni-CIO security policy

Omni-CIO работает с финансовыми данными. Production read-only, Sandbox и conditional real execution — отдельные contours с разными credentials и независимыми kill switches.

Real execution v1 существует только как узкий server-gated surface. Без valid dedicated token, durable journal, limits, fresh market and owner confirmation submit must fail closed.

## Secrets and private data

Never publish values of:

- `TINVEST_TOKEN`;
- `TINVEST_SANDBOX_TOKEN`;
- `TINVEST_TRADING_TOKEN`;
- `UPSTASH_REDIS_REST_TOKEN`;
- `GATEWAY_API_KEY`;
- Authorization/Bearer headers;
- full broker account ID;
- private broker reports/positions/operations as configuration;
- Render/GPT/Upstash credentials;
- private keys/certificates.

Use only placeholders and masked IDs.

## Credential isolation

### Read-only

`TINVEST_TOKEN`:

- remains read-only;
- never promoted to full-access;
- never used as fallback by real-trading package.

### Sandbox

`TINVEST_SANDBOX_TOKEN`:

- Sandbox only;
- fixed Sandbox host;
- virtual money only.

### Real execution

`TINVEST_TRADING_TOKEN`:

- separate account-scoped full-access trading token;
- **without transfer access**;
- only for narrow `omni_cio.real_trading` OrdersService allowlist;
- never stored in durable journal;
- never returned to GPT/user.

## Production runtime invariants

- `app:app` stable entrypoint;
- secrets via environment variables;
- account IDs masked before user-facing output;
- errors sanitized;
- analytics/purchase-capacity never create orders;
- withdrawal/transfer/securities-transfer surface absent;
- real MARKET/BESTPRICE absent;
- margin/short/stop/replace/async/autonomous recurring execution absent in real v1;
- `REAL_TRADING_ENABLED=false` removes real Actions and is master rollback;
- real flag alone is insufficient: invalid token/policy/journal fails closed;
- real submit only after separate proposal + exact short-lived owner phrase in a new user turn;
- `submitted` never means `filled` without broker proof;
- possible-submit ambiguity never auto-retries.

## Sandbox boundary

Sandbox mutation requires `SANDBOX_TRADING_ENABLED=true` and fixed `sandbox-invest-public-api.tbank.ru` host.

Required:

- separate token;
- `sandbox=true`, `real_money=false`;
- allowlisted methods only;
- no transfer/withdrawal;
- `confirmMarginTrade=false`;
- BUY own-funds / SELL own-position limits;
- immutable proposal + exact short-lived confirmation;
- repeat preflight before submit;
- UUID idempotency;
- no duplicate submit;
- ambiguous submit no retry;
- masked account.

## Real execution v1 boundary

Published only when readiness is valid:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- consequential `executeRealTrade`;
- `getRealOrderState`.

Allowed:

- BUY/SELL;
- supported cash share/ETF;
- RUB;
- LIMIT / CURRENCY / DAY;
- own-funds BUY;
- own-position SELL;
- exact price step;
- fresh trusted order book;
- small per-order/daily caps.

Prepare/execute separation:

1. bind exactly one trading account to read-only account;
2. check instrument identity + fresh market;
3. `GetMaxLots` / `GetOrderPrice` preflight;
4. create durable immutable proposal;
5. return exact phrase and stop;
6. phrase must arrive in new user turn;
7. repeat account/market/financial preflight;
8. durable atomic daily reservation before `PostOrder`;
9. submit once with UUID idempotency key;
10. reconcile broker state by request UUID.

Wrong/expired phrase, changed preflight, insufficient own funds/position, account mismatch, stale market, hard-limit failure, journal outage/tamper/integrity failure all fail closed before submit.

## Durable journal

Selected production backend:

```text
REAL_TRADING_JOURNAL_BACKEND=upstash
UPSTASH_REDIS_REST_URL=<HTTPS *.upstash.io endpoint>
UPSTASH_REDIS_REST_TOKEN=<Render secret>
```

Security requirements:

- HTTPS Upstash host restriction;
- REST token only in Render Environment;
- redirects disabled / no proxy-env trust for journal client;
- no fallback to memory;
- HMAC-authenticated metadata/proposals/day counters;
- authenticated proposal count;
- integrity recomputation;
- atomic Redis Lua compare-and-swap for state + daily cap;
- secrets excluded from proposal data;
- tamper/missing/corrupt state blocks readiness/submission.

SQLite remains compatibility/test only.

## Ambiguous broker submit

Timeout/connection break/5xx after `PostOrder` may mean the broker received the request.

Required behavior:

- proposal → `unknown` / do-not-resubmit;
- daily notional remains reserved;
- second `PostOrder` forbidden;
- reconcile original UUID through `GetOrderState` / request-id mode;
- unresolved ambiguity blocks automatic continuation.

Definitive broker rejection → failed and releases reserved notional atomically.

## Custom GPT boundary

Canonical GPT Editor Instructions:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`

Full engineering reference:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`

- OpenAPI only from production Gateway;
- Authentication = API Key → Bearer using `GATEWAY_API_KEY`;
- broker/Upstash tokens never enter GPT Editor;
- ordinary portfolio management is not trade confirmation;
- consequential UI never replaces server-side exact-confirmation gate;
- Apps not used together with Actions;
- GitHub does not sync GPT Editor/Render/Upstash automatically.

## Data integrity

- exact decimal logic;
- verified FX + timestamp before currency mixing;
- partial/truncated/stale/contradictory data fail closed;
- no commission/operation double count;
- last price not executable guarantee;
- fresh market required for real proposal;
- Sandbox fill is not production fill evidence;
- durable journal is not broker state; after submit broker reconciliation is mandatory.

## CI security

- dependencies pinned/hash-locked;
- lock files not edited manually;
- external GitHub Actions pinned to full SHA;
- Regression Shield covers compile, lint, formatting, types, contracts, tests, coverage, dependency audit, SAST and secret scan;
- tests use fake/mock transports and never submit live broker orders.

Required regression evidence includes wrong/expired confirmation, own-funds/own-position guards, hard caps, account mismatch, stale market, replay single-submit, ambiguous-submit no-retry, masking/redaction, journal persistence/integrity and conditional OpenAPI.

## Owner acceptance state

Phase 3 completed on 2026-08-03 with zero real submit:

- permanent Upstash + dedicated trading token configured;
- small caps configured;
- saved GPT v8.6.1 returned ready with `journal_integrity=ok`;
- wrong/expired confirmation rejected;
- own-funds guard rejected excessive BUY without margin fallback;
- read-only isolation remained intact;
- kill switch deployed and produced healthy read-only state;
- re-enable recovered ready state with durable proposal rows.

## Final release gate

Before release can be called 100% complete, Phase 4 still requires:

1. a **new explicit owner instruction** authorizing the first controlled real LIMIT order;
2. proposal shown before submit;
3. exact phrase from a new owner message;
4. one `PostOrder` only;
5. immediate broker-state reconciliation;
6. broker-confirmed fill/partial-fill truth;
7. real portfolio/cash/operations reconciliation;
8. one safe replay proving no second submit.

At any anomaly: disable `REAL_TRADING_ENABLED`, preserve journal evidence and reconcile before further action.

Full procedure: `docs/operations/REAL_TRADING_RELEASE_RUNBOOK.md`.