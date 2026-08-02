# Real-money trading v1 — staged release runbook

Status: **DESIGN ONLY. DO NOT ENABLE REAL TRADING YET.**

Architecture/threat model: `docs/architecture/REAL_TRADING_V1.md`.
Tracking issue: #164.

This runbook intentionally separates engineering, owner configuration, and the first controlled real order. Until the relevant gate is reached, the owner must not create or install a real trading token.

## 0. Absolute safety rule

The existing production credential remains:

`TINVEST_TOKEN = read-only`

Never replace it with a full-access token.

Future real trading must use a distinct secret:

`TINVEST_TRADING_TOKEN`

No transfer-access token is required or permitted for this release.

No withdrawal/transfer method is allowed in source code or OpenAPI.

## 1. Phase 0 — architecture only

Owner action: **none**.

Engineering requirements:

- threat model merged;
- exact method allowlist fixed;
- LIMIT-only v1 contract fixed;
- durable execution-state requirement fixed;
- per-order and daily hard-limit strategy fixed;
- rollback path fixed;
- acceptance matrix fixed.

Exit condition: design PR green and reviewed. No broker-write code yet.

## 2. Phase 1 — isolated implementation, still impossible to enable externally

Owner action: **none**.

Implementation lives under:

`omni_cio/real_trading/`

Initial implementation should contain:

- strict production REST client with hardcoded base host;
- allowlisted broker methods only;
- proposal model/state machine;
- HMAC-bound exact confirmation;
- account binding/masking;
- own-funds / own-position preflight;
- LIMIT-order preview;
- hard application limits;
- idempotency/reconciliation logic;
- durable execution journal interface;
- fake-client unit and contract tests.

Do not register OpenAPI routes in this first implementation commit until backend safety tests pass.

### Phase 1 mandatory tests

- production read-only token cannot be used as execution fallback;
- transfer/withdrawal paths do not exist;
- all real writes default off;
- only LIMIT/CURRENCY/DAY orders accepted;
- `confirmMarginTrade=false` hard-coded;
- account mismatch/multiple accounts fail closed;
- own-funds/own-position limits fail closed;
- missing/invalid hard limits fail closed;
- wrong/expired confirmation produces zero broker submits;
- tampered proposal produces zero broker submits;
- duplicate execution produces one broker submit total;
- ambiguous submit produces no retry;
- secrets/full account ids do not escape user-facing responses/logging;
- no live network calls in CI.

Exit condition: focused tests + full Regression Shield green.

## 3. Persistence gate

Owner action: normally **none until engineering identifies the chosen durable option**.

Real execution cannot rely on process memory or ephemeral Render filesystem for proposal/submission state and daily limits.

Before conditional routes are enabled, choose a durable store that supports:

- atomic state transitions;
- request UUID uniqueness;
- restart recovery;
- daily limit accounting;
- minimal encrypted/protected operational metadata;
- no token storage;
- deletion/retention policy.

If the selected persistence option changes Render infrastructure or cost, stop here and ask the owner before provisioning it.

## 4. Phase 2 — conditional real-trading Action surface

Owner action: **none while flag remains false**.

Expected new variables are documented by name only:

```text
TINVEST_TRADING_TOKEN=<not configured yet>
REAL_TRADING_ENABLED=false
REAL_TRADING_CONFIRMATION_TTL_SECONDS=120
REAL_TRADING_MAX_ORDER_RUB=<required before enable>
REAL_TRADING_MAX_DAILY_RUB=<required before enable>
```

Conditional Actions planned:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- `executeRealTrade`;
- `getRealOrderState`;
- later `cancelRealOrder`.

With `REAL_TRADING_ENABLED=false`, these mutation routes must be absent from OpenAPI.

Exit condition: OpenAPI off/on contract and security tests green with fake broker client.

## 5. Phase 3 — owner configuration, no real order

This is the **first point where owner help is needed**.

Do not ask the owner for this step until Phases 0–2 are merged and exact-head Regression Shield is green.

Owner will then:

1. issue a T-Invest token scoped to the intended single account with full-access trading rights but **without transfer access**;
2. store it in Render only as `TINVEST_TRADING_TOKEN`;
3. keep `TINVEST_TOKEN` unchanged/read-only;
4. configure deliberately small `REAL_TRADING_MAX_ORDER_RUB` and `REAL_TRADING_MAX_DAILY_RUB` values supplied by the release instructions;
5. keep `REAL_TRADING_ENABLED=false` initially;
6. redeploy and verify read-only + Sandbox behavior did not regress.

Then engineering/Preview acceptance tests:

- `getRealTradingStatus` only after controlled enable;
- masked account and exact account binding;
- wrong confirmation rejection;
- expired confirmation rejection;
- tamper rejection;
- limit exceed rejection;
- unsupported MARKET order rejection;
- SELL over owned position rejection;
- no real submit during negative acceptance;
- kill switch removes real routes again.

Exit condition: all negative tests pass and no real order has been submitted.

## 6. Phase 4 — first controlled real order

This phase requires a **new explicit owner instruction at that time**. Previous general autonomy does not authorize the first real broker order.

Candidate criteria:

- highly liquid supported cash security;
- minimum practical lot count, normally 1 lot;
- LIMIT order only;
- fresh market and trading status;
- exact instrument identity;
- complete broker/app preflight;
- order below small server hard caps;
- no margin;
- clear rationale and NO_ACTION alternative.

### Proposal turn

GPT/Gateway must show:

- unmistakable `REAL MONEY` label;
- masked account;
- instrument + identifiers;
- BUY/SELL;
- lots and units;
- exact limit price;
- broker preliminary value and commission fields when available;
- available own-funds/own-position limit;
- server hard-limit check;
- market freshness;
- rationale;
- expiry time;
- exact confirmation phrase.

Then stop. No submit in the proposal turn.

### Confirmation turn

Only a new owner message containing the exact phrase returned by the proposal may call `executeRealTrade`.

No typo correction or substitution.

### Post-submit

- submit once with proposal UUID;
- immediately call `getRealOrderState`;
- do not claim filled unless broker state says so;
- reconcile real portfolio/operations after fill/partial fill;
- repeat the same execution confirmation once only as an idempotency test **only if the release protocol explicitly permits this safe replay check**; it must return prior state without another broker submit;
- if any result is ambiguous, stop and reconcile — never resubmit.

## 7. Phase 5 — cancellation sub-release

Do not bundle cancellation with the first real-submit acceptance unless implementation and review explicitly include it.

When released, cancellation requires:

- a known order id;
- current broker order state;
- a separate immutable cancel proposal;
- separate exact confirmation phrase;
- `CancelOrder` only;
- post-cancel `GetOrderState` reconciliation.

No ReplaceOrder in v1.

## 8. Rollback drill

Before declaring the real trading release complete, prove:

1. set `REAL_TRADING_ENABLED=false`;
2. redeploy/restart;
3. real mutation Actions disappear from OpenAPI;
4. read-only production Actions remain healthy;
5. Sandbox remains independent;
6. any previously submitted order can still be inspected/reconciled by safe tooling/process;
7. trading token can be revoked without changing the read-only token.

## 9. Release acceptance checklist

- [ ] Phase 0 threat model merged.
- [ ] Persistence design chosen and tested.
- [ ] Isolated backend implementation merged.
- [ ] No transfer/withdraw paths exist.
- [ ] LIMIT-only order contract enforced.
- [ ] Hard per-order and daily limits enforced.
- [ ] Wrong/expired/tampered confirmations fail closed.
- [ ] Duplicate submit protection tested.
- [ ] Ambiguous submit no-retry tested.
- [ ] Account binding/masking tested.
- [ ] Exact-head Regression Shield green.
- [ ] Security review complete.
- [ ] Owner config negative acceptance complete with no real submit.
- [ ] Kill switch rollback proven.
- [ ] First minimal real order explicitly authorized at that time.
- [ ] Broker state reconciled.
- [ ] Real portfolio/operations reconciled.

Only after every item above is complete can the buy/sell feature be considered fully released.
