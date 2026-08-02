# Real-money execution v1 — threat model and architecture

Status: **PHASES 0–2 IMPLEMENTED / DEFAULT-OFF / OWNER ACCEPTANCE REQUIRED**

Tracking issue: #164.

This document defines the safety architecture for Omni-CIO real-money BUY/SELL. It does not authorize a broker order by itself. The default deployed state is `REAL_TRADING_ENABLED=false`.

## 1. Product scope

The first real-money release intentionally supports less than T-Invest supports.

Allowed:

- one existing T-Invest account bound by an account-scoped full-access **non-transfer** token;
- BUY and SELL only;
- supported cash share/ETF only;
- RUB only;
- LIMIT orders only;
- `TIME_IN_FORCE_DAY` only;
- `PRICE_TYPE_CURRENCY` only;
- own-funds BUY / own-position SELL only;
- explicit owner confirmation for every submit;
- request-id order-state reconciliation.

Explicitly excluded:

- MARKET / BESTPRICE;
- bonds/futures/options/currency execution in v1;
- margin / uncovered positions;
- stop orders;
- ReplaceOrder;
- PostOrderAsync;
- automatic re-submit;
- autonomous recurring trading;
- withdrawal or transfer of money;
- transfer of securities;
- bank/account mutation;
- token management through GPT;
- real cancellation in the first submit milestone.

The LIMIT-only restriction makes the owner-confirmed maximum unit price explicit and confirmation-bound.

## 2. Credential contours

```text
Custom GPT
  │ Bearer GATEWAY_API_KEY
  ▼
Omni-CIO Gateway / Render Free
  │
  ├── TINVEST_TOKEN ───────────────► production read-only APIs
  ├── TINVEST_SANDBOX_TOKEN ──────► T-Invest Sandbox only
  ├── TINVEST_TRADING_TOKEN ──────► production OrdersService allowlist only
  └── HTTPS ───────────────────────► Upstash Redis Free durable journal
```

Rules:

- existing `TINVEST_TOKEN` remains read-only;
- `TINVEST_TRADING_TOKEN` is a new separate account-scoped full-access token;
- trading token must not have transfer access;
- `omni_cio.real_trading` never falls back to `TINVEST_TOKEN`;
- the model never receives a T-Invest token, Upstash REST token or full account id.

## 3. Official broker methods used

Relevant T-Invest REST methods:

- `UsersService/GetAccounts` for trading-token account binding;
- `OrdersService/GetMaxLots`;
- `OrdersService/GetOrderPrice`;
- `OrdersService/PostOrder`;
- `OrdersService/GetOrderState`;
- optionally `OrdersService/GetOrders` for limited recovery diagnostics.

Important semantics:

- `PostOrder.orderId` is the client UUID/idempotency key;
- order quantity is in lots;
- `GetOrderState` can resolve by `ORDER_ID_TYPE_REQUEST`;
- `GetMaxLots` separates own-funds/own-position limits from margin limits;
- `confirmMarginTrade=false` is hard-coded;
- `GetOrderPrice` supplies the preliminary LIMIT-order cost/commission data used by the preflight.

Reference URLs:

- https://developer.tbank.ru/invest/intro/intro/token
- https://developer.tbank.ru/invest/api/orders-service
- https://developer.tbank.ru/invest/api/orders-service-post-order
- https://developer.tbank.ru/invest/api/orders-service-get-max-lots
- https://developer.tbank.ru/invest/api/orders-service-get-order-price
- https://developer.tbank.ru/invest/api/orders-service-get-order-state

## 4. Conditional publication / kill switch

`REAL_TRADING_ENABLED=false` is the default and rollback state.

Rules:

- false/absent → all Real Trading Actions absent from OpenAPI;
- true + invalid static readiness → status-only fail-closed surface;
- true + valid token, policy and durable journal → narrow four-Action surface can register;
- Sandbox enable is independent;
- real enable never changes read-only or Sandbox credentials.

Emergency rollback:

1. set `REAL_TRADING_ENABLED=false`;
2. redeploy/restart;
3. verify real routes disappear;
4. reconcile any unresolved broker request UUIDs before deleting operational evidence.

## 5. Server-side limits

Mandatory before real mutation routes can publish:

- `REAL_TRADING_MAX_ORDER_RUB`;
- `REAL_TRADING_MAX_DAILY_RUB`;
- optional/default `REAL_TRADING_CONFIRMATION_TTL_SECONDS=120`;
- optional/default `REAL_TRADING_MARKET_MAX_AGE_SECONDS=15`.

Policy validation additionally enforces immutable code ceilings. Broker transaction limits are not a substitute for Omni-CIO limits.

Initial owner acceptance uses deliberately small values:

```text
REAL_TRADING_MAX_ORDER_RUB=1000
REAL_TRADING_MAX_DAILY_RUB=2000
```

## 6. Account binding

Real execution resolves exactly one open account through `TINVEST_TRADING_TOKEN` and compares it with the production read-only account.

Fail closed if:

- zero eligible accounts;
- multiple eligible accounts;
- trading-token account differs from read-only account;
- account status/id cannot be resolved.

Full account id exists only where required for broker calls/durable internal proposal state. User-facing output is masked.

## 7. Instrument and market gate

Before proposal and again immediately before submit:

- requested/resolved UID identity matches;
- no identity conflict;
- instrument type is v1 allowlisted;
- currency is RUB;
- lot and min-price increment valid;
- API trade available;
- LIMIT orders available;
- current trading status present;
- market/reference/order-book components complete;
- order-book timestamp is fresh within configured max age;
- requested limit price is an exact multiple of `min_price_increment`.

Stale `last price` does not satisfy the executable market gate.

## 8. Financial preflight

### BUY

- only own-funds `buyMaxLots`;
- margin BUY capacity ignored;
- requested lots <= own-funds maximum;
- `GetOrderPrice` preview available/parseable;
- preview total <= per-order hard cap;
- daily cap available.

### SELL

- only own-position `sellMaxLots`;
- no short/uncovered sale;
- requested lots <= owned-position maximum;
- preview and hard-limit checks pass.

`confirmMarginTrade=false` on every submit.

## 9. Immutable proposal and confirmation

`prepareRealTrade` binds at minimum:

- proposal id;
- UUID broker request/order id;
- internal account id;
- instrument UID/ticker/ISIN;
- direction;
- lots;
- order type = LIMIT;
- exact limit price;
- price type = CURRENCY;
- time-in-force = DAY;
- rationale;
- preliminary total/commission;
- own-funds/own-position available lots;
- market timestamp;
- created/expiry timestamps.

Confirmation phrase:

`ПОДТВЕРЖДАЮ РЕАЛЬНУЮ СДЕЛКУ <CODE>`

Requirements:

- server-generated/HMAC-bound to canonical immutable proposal;
- separate user message required;
- exact comparison;
- short TTL;
- execution endpoint accepts only `proposal_id` + exact phrase, not price/side/quantity again;
- broad instructions such as “управляй портфелем” never count as confirmation.

## 10. Pre-submit revalidation

A prepared proposal is not durable authorization.

Immediately before `PostOrder`, repeat:

- feature/static readiness;
- account binding;
- TTL/confirmation;
- instrument identity/tradability;
- fresh market gate;
- own-funds/own-position `GetMaxLots`;
- exact `GetOrderPrice` preview;
- per-order cap;
- atomic daily cap reservation;
- duplicate/idempotency state.

Material change blocks submit and requires a fresh proposal.

## 11. Proposal state machine

```text
prepared
   │ exact owner phrase + revalidation + durable reserve
   ▼
submitting ───────► submitted
   │
   ├──────────────► failed       (definitive broker rejection)
   └──────────────► unknown      (timeout/5xx after possible submit)

prepared ─────────► expired
```

`submitted` means broker request submission path succeeded; it does **not** mean filled. Fill is reported only from broker execution status.

No transition from `unknown` back to `submitting`. `unknown` means **DO NOT RESUBMIT**.

## 12. Idempotency and ambiguous-submit recovery

Generate UUID v4 before submit and persist it with the proposal.

Submit once using that UUID as `orderId`.

- successful replay returns prior result and never calls `PostOrder` twice;
- definitive rejection → `failed`;
- timeout/network/5xx after possible submit → `unknown_do_not_resubmit`;
- reconcile through `GetOrderState` + `ORDER_ID_TYPE_REQUEST` with the original UUID;
- if broker state cannot be proved, stop and require owner-visible resolution rather than duplicate risk.

## 13. Durable state — zero-cost production choice

Real trading requires persistent state across Render Free sleep, restart and deploy.

Selected default backend:

```text
REAL_TRADING_JOURNAL_BACKEND=upstash
UPSTASH_REDIS_REST_URL=<HTTPS *.upstash.io endpoint>
UPSTASH_REDIS_REST_TOKEN=<Render secret>
```

A Render Persistent Disk is **not** required for the selected project deployment.

The Upstash journal persists:

- proposal lifecycle;
- request UUID/idempotency;
- submit/unknown state;
- confirmation evidence hash;
- daily hard-limit accounting;
- reconciliation result data.

It does not store T-Invest/Upstash/Gateway token values.

### Integrity

Application-authenticated structures:

- journal metadata with schema/revision/proposal count + HMAC;
- each proposal envelope with revision + canonical proposal JSON + HMAC;
- each Moscow-day notional counter with revision/value + HMAC.

`integrity_check()` verifies stored proposal count, every proposal envelope and counted daily totals.

Tamper/missing/corrupt storage fails closed.

### Atomicity

Upstash Redis `EVAL` is used for short compare-and-swap Lua scripts only.

`reserve_submission()` atomically changes:

1. proposal `prepared → submitting`;
2. signed daily notional counter.

This prevents concurrent confirmations from both consuming the same remaining daily limit.

Definitive broker rejection changes `submitting → failed` and atomically releases the reserved daily notional. `unknown` remains counted.

### External storage failure

Storage failure affects availability, never authorization:

- no durable reserve → no broker submit;
- no fallback to in-memory/ephemeral state;
- after possible broker submit, storage/broker ambiguity never authorizes automatic retry.

SQLite remains an explicit compatibility/test backend for installations with a real persistent filesystem.

Details: `docs/operations/REAL_TRADING_DURABLE_STORAGE_V1.md`.

## 14. Audit/redaction

Minimal normalized facts may be recorded:

- timestamps;
- proposal/request UUID;
- public instrument identifiers;
- direction/lots/limit price;
- gate outcomes;
- broker status category;
- idempotency/reconciliation state.

Never expose/store as audit data:

- token values;
- Authorization headers;
- full account id in user-facing output;
- unnecessary full private broker payload dumps;
- exact confirmation phrase in long-lived logs.

## 15. OpenAPI/GPT surface

Default OFF: no real Actions.

Static failure with flag ON: safe `getRealTradingStatus` only.

Ready surface:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- `executeRealTrade` — consequential;
- `getRealOrderState`.

No `cancelRealOrder`/replace/withdraw/transfer/market/margin Action in first release.

## 16. CI / negative-test requirements

CI uses fake/mock broker/storage transports only.

Mandatory coverage includes:

- real flag off → routes absent;
- missing trading token/storage credentials → no mutation routes;
- no read-only token fallback;
- fixed production broker host;
- account mismatch/multiple accounts fail closed;
- unsupported instrument/currency/order modes blocked;
- stale/incomplete market blocked;
- invalid price step blocked;
- invalid/hard caps blocked;
- BUY above own-funds / SELL above own-position blocked;
- wrong/expired confirmation → zero broker submit;
- duplicate execution → one submit total;
- ambiguous submit → no automatic retry;
- full account/token redaction;
- durable restart recovery;
- durable tamper detection;
- concurrent daily-cap atomicity;
- external journal host/TLS restriction;
- no live T-Invest/Render/Upstash calls in CI.

## 17. Release gates

Real-money BUY/SELL is not complete until:

1. threat model/core/conditional routes/free durable storage merged after exact-head Regression Shield/security;
2. owner configures permanent Upstash Free Redis credentials in Render;
3. owner configures separate account-scoped non-transfer trading token;
4. default-off deployment/read-only/Sandbox regression passes;
5. controlled real enable readiness passes;
6. wrong/expired/hard-cap/stale/over-position negative acceptance passes with zero real submit;
7. Render restart proves Upstash persistence;
8. kill-switch rollback removes real Actions;
9. owner explicitly authorizes first minimal real LIMIT order;
10. order state and real portfolio/operations reconcile;
11. replay proves no second submit.

Before gate 9 no real order should be sent.

## 18. Rollback

At anomaly:

1. `REAL_TRADING_ENABLED=false`;
2. redeploy/restart;
3. real routes disappear;
4. keep `TINVEST_TOKEN` unchanged;
5. revoke `TINVEST_TRADING_TOKEN` if compromise suspected;
6. keep Upstash journal until all `submitting`/`unknown` UUIDs are reconciled;
7. never blindly replay a broker request.
