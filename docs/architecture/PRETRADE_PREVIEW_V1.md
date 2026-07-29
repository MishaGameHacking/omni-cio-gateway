# Pre-Trade Preview v1

## Scope

PR-14 adds an internal, read-only orchestration layer that converts the existing
`getPurchaseCapacityPreview` payload and a currency-local
`ThresholdRebalancePlanV1` into a strict `PreTradePreviewV1` contract.

It does not add a FastAPI route, change OpenAPI, ask for confirmation, create an
idempotency key, submit an order, replace an order or cancel an order.

## Why this layer exists

The legacy purchase-capacity endpoint already obtains:

- instrument identity and lot size;
- a selected best-ask, last-trade or manual price;
- own-funds limits from T-Invest `GetMaxLots`;
- preliminary order value and commission fields from `GetOrderPrice`;
- arithmetic and currency integrity diagnostics.

Before PR-14, a stale or timestamp-less price produced a warning but was not a
hard readiness gate. PR-14 makes freshness, account binding, arithmetic,
affordability and target-band alignment mandatory for a recommendation-ready
preview.

## Inputs

`build_pretrade_preview` accepts:

1. the read-only purchase-capacity payload;
2. a verified `ThresholdRebalancePlanV1`;
3. one stable portfolio instrument key;
4. an aware evaluation timestamp;
5. a positive maximum price age, defaulting to 120 seconds.

The orchestration is data-only and performs no network or broker SDK call.

## Hard gates

The preview is blocked when any of the following is true:

- the threshold plan is not decision-ready;
- the selected line is not an add-only underweight position;
- the cash-first alternative is unavailable;
- the masked account differs between the plan and broker preview;
- the source payload is partial, incomplete or trading-enabled;
- instrument resolution is incomplete;
- price is missing or non-positive;
- price timestamp is absent, in the future or older than the configured limit;
- price basis is manual;
- lot size or requested lot count is invalid;
- currencies disagree;
- affordability is unavailable or negative;
- canonical commission is unavailable;
- arithmetic integrity or commission double-count protection is not confirmed;
- the preliminary total exceeds the selected position's value-to-target limit.

`preview_ready` is true only when the blocker set is empty.

## Freshness

Freshness is recomputed from the source timestamp and the orchestration time.
The legacy text status is not trusted as the source of truth.

- age less than or equal to the configured maximum: `fresh`;
- age above the maximum: `stale`;
- absent or future timestamp: `unknown` plus a blocker;
- manual price: `manual_input` plus a blocker.

The source timestamp must be timezone-aware and is normalized to UTC.

## Currency and money

All monetary fields retain their reported currency. A mismatch is preserved as
blocked evidence instead of being silently converted or discarded.

The ready path requires one currency for:

- selected instrument;
- initial amount;
- canonical commission;
- accrued interest, when present;
- total amount;
- own funds;
- remaining cash;
- target value limit.

No FX conversion or cross-currency aggregation occurs.

## Arithmetic

The contract checks, within a 0.01 currency-unit tolerance:

`initial amount + canonical commission + accrued interest = total amount`

and:

`own funds - total amount = remaining cash`

A mismatch may be serialized only when
`arithmetic_integrity_failed` is present, ensuring the evidence is visible while
the preview remains blocked.

## Target-band guard

The preliminary total may not exceed the selected underweight position's
`value_to_target` by more than the money tolerance. This prevents a preview from
silently sizing beyond the analytical target band.

PR-14 still does not choose an instrument or lot count automatically. It only
validates a supplied analytical candidate and requested quantity.

## Execution boundary

Every `PreTradePreviewV1` has:

- `execution_ready=false`;
- `trading_methods=false`.

The contract contains no order ID, confirmation ID, idempotency key, submit
method, cancel method or replace method.

## Official API basis

T-Invest documents that market prices are quoted per instrument and the lot
value requires the instrument lot size. `GetMaxLots` reports available lots and
`GetOrderPrice` reports preliminary order amount and commission fields. The
actual execution endpoint is separate and is not called by this layer.

## Rollback

Revert the PR merge commit. No public API, OpenAPI, Render, database, secret or
broker-side migration is required.
