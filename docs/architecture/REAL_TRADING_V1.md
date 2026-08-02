# Real-money execution v1 — threat model and architecture

Status: **DESIGN ONLY / NOT IMPLEMENTED / DEFAULT-OFF**

Tracking issue: #164.

This document defines the safety architecture for a future real-money BUY/SELL release. It does **not** authorize a production token change and does not add a real broker-write route.

## 1. Scope

Goal: allow the existing Omni-CIO Custom GPT to prepare and, only after an exact short-lived owner confirmation in a separate user message, submit a narrowly constrained real order through T-Invest.

First real-money release deliberately supports less than T-Invest itself supports.

### v1 allowed product scope

- one existing T-Invest account selected by an **account-scoped full-access token**;
- BUY and SELL only;
- cash securities only;
- **LIMIT orders only** in v1;
- `TIME_IN_FORCE_DAY` only;
- `PRICE_TYPE_CURRENCY` only;
- explicit owner confirmation for every order;
- read order state after submit;
- real cancellation only as a separately confirmed operation after the submit path is accepted.

### v1 explicitly excluded

- MARKET / BESTPRICE orders;
- bonds and futures where point-price semantics complicate the first execution release;
- currencies and derivatives;
- margin / uncovered positions;
- stop orders;
- replace order;
- asynchronous order submit;
- automatic re-submit;
- autonomous recurring trading;
- withdrawal or transfer of money;
- transfer of securities;
- bank detail changes;
- token creation/rotation through GPT;
- account opening/closing;
- participation in placements.

Reducing v1 to LIMIT/CURRENCY cash-security orders makes the maximum unit price explicit and confirmation-bound. Broader order types can be a later release after separate acceptance.

## 2. Current invariant before this release

Until this program is implemented, reviewed, merged and externally accepted:

- `TINVEST_TOKEN` remains production read-only;
- `real_trading_methods=false`;
- no real mutation Action is published;
- Sandbox remains the only broker-write contour;
- no owner action is required to create a real trading token.

## 3. Official broker contract used by this design

Current T-Bank Dev Portal documentation distinguishes read-only, full-access, transfer-access, account-scoped and Sandbox tokens. A token can be scoped to a specific account and have full-access rights without being a transfer-access token.

Relevant production REST methods are:

- `OrdersService/GetMaxLots`;
- `OrdersService/GetOrderPrice`;
- `OrdersService/PostOrder`;
- `OrdersService/GetOrderState`;
- `OrdersService/GetOrders` for limited same-day recovery context;
- `OrdersService/CancelOrder` in the later cancellation sub-phase.

Important broker semantics used here:

- `PostOrder.orderId` is a client UID/idempotency key and is limited to 36 characters;
- order quantity is expressed in **lots**;
- `GetOrderState` supports `ORDER_ID_TYPE_REQUEST` to resolve the order by the client request/idempotency id;
- `GetMaxLots` separates own-funds BUY limits from margin BUY limits, and own-position SELL limits from margin SELL limits;
- `confirmMarginTrade` defaults to false and Omni-CIO v1 always sends false;
- `GetOrderPrice` provides a preliminary value for a **limit** order.

Reference URLs:

- https://developer.tbank.ru/invest/intro/intro/token
- https://developer.tbank.ru/invest/api/orders-service
- https://developer.tbank.ru/invest/api/orders-service-post-order
- https://developer.tbank.ru/invest/api/orders-service-get-max-lots
- https://developer.tbank.ru/invest/api/orders-service-get-order-price
- https://developer.tbank.ru/invest/api/orders-service-get-order-state

## 4. Trust boundaries

```text
Owner
  │ exact confirmation in a new ChatGPT message
  ▼
Custom GPT
  │ Bearer GATEWAY_API_KEY
  ▼
Omni-CIO Gateway / Render
  │
  ├── TINVEST_TOKEN ───────────────► production read-only APIs
  │
  ├── TINVEST_SANDBOX_TOKEN ──────► Sandbox only
  │
  └── TINVEST_TRADING_TOKEN ──────► production OrdersService allowlist only
                                      (future, default-off)
```

The model never receives any T-Invest token or full broker account id.

## 5. Credential separation

Future variable:

`TINVEST_TRADING_TOKEN`

Requirements:

- new secret; never reuse `TINVEST_TOKEN`;
- account-scoped to the intended account;
- full-access sufficient for trading;
- **not** transfer-access;
- stored only in Render Environment;
- never emitted in exceptions, logs, GPT payloads, PRs, issues or documentation;
- read by `omni_cio/real_trading/` only;
- real-trading module must never fall back to `TINVEST_TOKEN` if the new token is missing.

Missing/invalid `TINVEST_TRADING_TOKEN` means real execution is unavailable, not degraded to another credential.

## 6. Conditional publication and kill switch

Future variable:

`REAL_TRADING_ENABLED=false`

Rules:

- absent/false: real mutation routes are not registered and do not appear in OpenAPI;
- true: registration still fails closed unless every mandatory safety setting is valid;
- Sandbox enable does not imply real enable;
- real enable does not alter read-only or Sandbox credentials.

Emergency rollback begins with:

`REAL_TRADING_ENABLED=false`

then deploy/restart and OpenAPI refresh in GPT Editor if the Action surface changes.

## 7. Required server-side limits

Enabling v1 must fail closed unless these settings are valid positive values:

- `REAL_TRADING_MAX_ORDER_RUB` — maximum confirmed order notional/preview cost;
- `REAL_TRADING_MAX_DAILY_RUB` — maximum daily submitted/executed notional budget;
- `REAL_TRADING_CONFIRMATION_TTL_SECONDS` — proposed default 120, allowed 30..600.

A code-level absolute ceiling should also exist so an accidental Environment value cannot silently remove the safety bound. The concrete ceiling is a release parameter and must be chosen before Phase 1 implementation, not guessed in this design document.

Optional stricter controls:

- maximum lots per order;
- instrument allowlist/denylist;
- maximum number of real submissions per UTC/MSK trading day;
- owner-configured cash reserve / max target position share.

Broker-provided transaction limits are not a substitute for Omni-CIO limits.

## 8. Account binding

Real execution must resolve exactly one account from `TINVEST_TRADING_TOKEN` and bind proposals to its internal full id.

Fail closed if:

- token exposes zero eligible accounts;
- token unexpectedly exposes multiple eligible accounts;
- trading-token account differs from the account selected by the production read-only context;
- account status is not open/eligible;
- account id cannot be resolved.

User-facing output contains only a masked id.

The full id may exist transiently in process memory for the broker request but is never sent to the model.

## 9. Broker method allowlist

The real-trading client must expose only the small method set needed for v1.

Phase 1 allowlist:

- account validation method(s) required to prove account binding;
- `GetMaxLots`;
- `GetOrderPrice`;
- `PostOrder`;
- `GetOrderState`;
- optionally `GetOrders` for same-day recovery diagnostics.

Cancellation sub-phase adds only:

- `CancelOrder`.

Explicitly not implemented:

- `ReplaceOrder`;
- `PostOrderAsync`;
- StopOrdersService methods;
- transfer/withdraw methods;
- account/bank mutation methods.

Unknown broker method name => local rejection before network I/O.

## 10. Proposal state machine

```text
prepared
   │ exact owner phrase + all revalidation passes
   ▼
submitting ───────► executed
   │
   ├──────────────► failed        (definitive broker rejection)
   │
   └──────────────► unknown       (timeout/5xx after possible submit)

prepared ─────────► expired
```

No transition from `unknown` back to `submitting`.

`unknown` means **DO NOT RESUBMIT**. Recovery is reconciliation only.

## 11. Immutable proposal

`prepareRealTrade` must bind, at minimum:

- proposal id;
- UUID broker request/order id;
- internal account id;
- instrument UID plus resolved ticker/ISIN/class where available;
- direction;
- lots;
- order type = LIMIT;
- exact limit price;
- price type = CURRENCY;
- time-in-force = DAY;
- rationale / decision reference;
- preflight own-funds or own-position limit;
- broker preliminary cost/commission fields used by the implementation;
- application hard-limit result;
- market/data-quality snapshot reference and freshness timestamp;
- created time;
- expiration time.

The confirmation code is HMAC-bound to the canonical immutable payload.

Execution accepts only:

- `proposal_id`;
- exact `confirmation_phrase`.

It does not accept instrument, side, quantity or price again, preventing confirmation-time parameter substitution.

## 12. Exact confirmation protocol

Proposed phrase form:

`ПОДТВЕРЖДАЮ РЕАЛЬНУЮ СДЕЛКУ <CODE>`

Requirements:

- generated server-side from the immutable proposal;
- displayed only after a successful proposal/preflight;
- owner must send it in a **new user message**;
- exact comparison; no typo correction, normalization beyond surrounding whitespace, or model-generated substitute;
- short TTL;
- one proposal / one confirmation;
- successful replay returns prior result and never creates a second broker submission.

A broad instruction such as “управляй портфелем самостоятельно” is never a trade confirmation.

## 13. Instrument and market gate

Before proposal and again immediately before submit:

- exact instrument identity is resolved;
- instrument is API-tradable;
- v1 security type is allowlisted;
- lot size and currency are known;
- trading status permits the intended LIMIT order;
- data is complete and sufficiently fresh;
- no identity conflict exists;
- no stale/partial/contradictory market state is treated as current.

Because v1 is LIMIT-only, the owner-confirmed limit price is the maximum unit price for a BUY order. The system still must show best bid/ask and freshness so the owner can judge whether that limit is sensible.

## 14. Financial preflight

### BUY

Use only broker **own-funds** limits from `GetMaxLots`; never use margin capacity for sizing or authorization.

Check:

- requested lots <= own-funds maximum;
- broker preliminary LIMIT-order value from `GetOrderPrice` is available and parseable;
- previewed notional/cost <= `REAL_TRADING_MAX_ORDER_RUB`;
- daily budget remains available;
- optional reserve/portfolio risk limits pass.

### SELL

Use only broker **own-position** `sell_max_lots`.

Check:

- requested lots <= owned-position maximum;
- no short/uncovered sale;
- notional and daily limits pass;
- instrument/position identity matches exactly.

`confirmMarginTrade=false` is hard-coded on every submit.

## 15. Pre-submit revalidation

A successful prepare is never durable authorization to submit later.

Immediately before `PostOrder`, re-run:

- feature flag and mandatory configuration;
- account binding;
- proposal TTL and HMAC confirmation;
- instrument identity/tradability;
- market/data-quality gate;
- own-funds / own-position `GetMaxLots`;
- `GetOrderPrice` for the exact LIMIT order;
- per-order hard cap;
- daily hard cap;
- duplicate/idempotency state.

Any material mismatch blocks submission and requires a new proposal.

## 16. Idempotency and ambiguous-submit recovery

Generate a UUID v4 request id before submission and persist it with the proposal.

Submit once using that same `orderId`.

If the broker definitively rejects before submission, return `failed`.

If there is a timeout, connection break, or 5xx after the request may have crossed the network boundary:

- state = `unknown_do_not_resubmit`;
- never call `PostOrder` again automatically;
- reconcile via `GetOrderState` with `ORDER_ID_TYPE_REQUEST` using the original UUID;
- optionally use `GetOrders` only as supplementary same-day evidence;
- if broker state cannot be proved, stop and require owner-visible manual resolution rather than duplicate risk.

## 17. Durable state requirement

Sandbox intentionally stores proposals in memory so a restart invalidates them. That is acceptable for virtual money.

Real trading is different. A production execution contour needs durable minimal state for:

- proposal lifecycle;
- request UUID/idempotency;
- submit result / ambiguous state;
- owner confirmation evidence hash;
- daily hard-limit accounting;
- reconciliation status;
- safe recovery after process restart.

**In-memory state or ordinary ephemeral Render filesystem is not sufficient for real-money release.**

Phase 1 implementation must not proceed to real enable until a durable storage strategy is selected and tested. The store must contain no broker token and no unnecessary full private payload dumps.

This is an intentional release gate, not an invitation to create another user-facing service. A persistence dependency may be added only through a separate reviewed infrastructure decision.

## 18. Audit trail and redaction

Audit minimal structured facts:

- timestamp;
- event type;
- proposal id;
- request UUID;
- masked account;
- instrument public identifiers;
- direction/lots/limit price;
- gate outcomes;
- broker status code/category;
- idempotency/reconciliation state.

Never audit:

- token values;
- Authorization headers;
- full account id;
- full private broker payloads if a minimal normalized result is enough;
- exact confirmation secret/code in long-lived logs.

## 19. Cancellation policy

Real cancellation is not part of the first submit milestone.

When added:

- only a known real order created/reconciled by this contour;
- separate proposal/confirmation step;
- exact phrase bound to order id and current state;
- call only `CancelOrder`;
- verify final state with `GetOrderState`;
- no implicit replace.

## 20. OpenAPI/GPT surface

No real routes while `REAL_TRADING_ENABLED=false`.

Planned staged Actions only after backend tests pass:

- `getRealTradingStatus` — readiness only;
- `prepareRealTrade` — proposal, no submit;
- `executeRealTrade` — consequential, exact confirmation;
- `getRealOrderState` — reconciliation;
- `cancelRealOrder` — later cancellation sub-phase.

Every real execution response must say explicitly that it concerns real money and provide masked account + broker order status. GPT must never infer a fill from an HTTP 200 alone.

## 21. CI / negative-test matrix

Tests must use fake clients; CI must not contact T-Invest or Render.

Mandatory negative coverage:

- real flag off => routes absent;
- missing trading token => unavailable;
- real module never reads/falls back to `TINVEST_TOKEN`;
- transfer-access methods are not implemented;
- unexpected/multiple account => fail closed;
- account mismatch with read-only context => fail closed;
- unsupported instrument type => blocked;
- MARKET/BESTPRICE/POINT/margin => blocked;
- stale/incomplete data => blocked;
- invalid/missing server limits => enable fails closed;
- per-order cap exceeded => blocked;
- daily cap exceeded => blocked;
- BUY above own-funds limit => blocked;
- SELL above own-position limit => blocked;
- wrong confirmation => no submit;
- expired confirmation => no submit;
- proposal tamper => no submit;
- changed preflight/market state => no submit;
- duplicate execution => no second `PostOrder`;
- ambiguous submission => no automatic retry;
- account ids/token/header redaction;
- restart recovery from durable `submitting/unknown` state;
- no live network access in tests.

## 22. Release gates

Real-money execution is not complete until all gates pass:

1. Phase 0 architecture/threat model approved and merged.
2. Durable storage design selected.
3. Phase 1 isolated backend + negative tests green.
4. Exact-head Regression Shield green.
5. Security review shows no withdrawal/transfer/secret leakage path.
6. Conditional OpenAPI surface tested with flag off/on.
7. Owner provisions a separate account-scoped full-access trading token only when asked.
8. Owner acceptance proves kill switch, wrong/expired/tampered confirmation and read-only regression with **no real submit**.
9. A final explicitly authorized controlled minimal real LIMIT order is prepared, confirmed, submitted once and reconciled.
10. Replay protection and real portfolio/order-state reconciliation are verified.

Before gate 9, no real trade should be sent.

## 23. Rollback

At any anomaly:

1. set `REAL_TRADING_ENABLED=false`;
2. redeploy/restart;
3. ensure real mutation routes disappear from OpenAPI;
4. revoke `TINVEST_TRADING_TOKEN` if credential compromise is suspected;
5. keep read-only `TINVEST_TOKEN` unchanged;
6. reconcile any `submitting/unknown` request UUIDs; never blindly replay;
7. document the incident without secrets/private payloads.

## 24. Non-goals for the first real release

The first release is intentionally boring: one confirmed LIMIT order at a time, strong preflight, small server limits, durable idempotency and reconciliation.

Autonomous recurring trading, market orders, derivatives, margin, transfer access, stop orders and order replacement require separate future releases.
