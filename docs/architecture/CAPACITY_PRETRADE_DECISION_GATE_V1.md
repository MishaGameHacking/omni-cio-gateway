# Capacity Pre-Trade Decision Gate v1

## Purpose

This internal read-only layer composes the exact capacity-intent gate with the
existing strict purchase `PreTradePreviewV1`. It answers one narrow question:

> Does every capacity-checked analytical purchase intent still have a fresh,
> complete, affordable and arithmetically verified broker preview for exactly
> the same instrument, currency, price, lot size and quantity?

The result remains an analytical review state. It cannot create, replace,
cancel or submit an order.

## Inputs

The gate consumes:

- one `CapacityIntentDecisionGateV1`;
- one `PreTradePreviewV1` per expected instrument;
- a bounded preview-age policy;
- an aware UTC assessment timestamp.

The base intent gate already proves that market-capacity evidence belongs to
the exact `CapacityOrderRequestV1`. The pre-trade contract already proves that
the broker preview is complete, fresh at its evaluation time, affordable,
currency-consistent and protected against commission double counting.

## Exact preview binding

For every expected request, the purchase preview must match exactly on:

1. stable instrument key;
2. purchase side (`buy` only);
3. currency;
4. lot size;
5. quantity in lots;
6. reference/unit price.

A sell intent cannot reuse the purchase-preview contract. Sell-side validation
continues through the separate `SellPreTradePreviewV1` boundary.

## Freshness

The gate independently checks the preview evaluation timestamp against the gate
time. The default maximum age is 180 seconds and the default future tolerance
is 60 seconds.

This second freshness check is necessary because a preview can have been fresh
when created but become stale before a later analytical decision is reviewed.

## Ready state

`gate_ready=true` only when:

- the base exact-intent gate is ready;
- preview coverage is complete;
- every preview remains fresh and is not from the future;
- every preview has `preview_ready=true`;
- every exact preview-binding field matches.

The ready state preserves the base analytical option and action. It never
selects or upgrades an option.

## Fail-closed state

Any open condition returns:

- `status=abstain`;
- `gate_ready=false`;
- the existing no-action option;
- `final_action=wait_for_data`.

Typed blockers identify:

- blocked base intent gate;
- incomplete preview coverage;
- unready preview;
- stale or future preview;
- preview/intent mismatch.

Duplicate previews and previews for unrequested instruments are structural
errors rather than silently ignored data.

## Money and bond boundary

This gate does not recompute broker totals from the market-capacity notional.
That is deliberate: bond previews may include nominal-price conventions and
accrued interest. The existing `PreTradePreviewV1` remains authoritative for:

- initial order amount;
- canonical commission;
- accrued interest;
- total order amount;
- own funds;
- remaining cash;
- affordability;
- arithmetic integrity.

The gate only binds the analytical intent to that verified preview. It does not
invent a second competing broker-money formula.

## Explicit safety and confirmation fields

Every result states:

- `broker_preview_coverage_complete` — all expected previews are present;
- `affordability_confirmed` — all present previews confirm affordability;
- `commission_integrity_confirmed` — every preview has canonical commission and
  confirmed arithmetic integrity;
- `order_total_recomputed_by_gate=false`;
- `option_selected_by_gate=false`;
- `order_created=false`;
- `execution_ready=false`;
- `trading_methods=false`.

Read-only compatibility properties expose `broker_preview_checked`,
`affordability_checked` and `commission_integrity_checked` with the same honest
boolean values. Missing coverage never appears as a successful check.

## Compatibility

This package adds no:

- FastAPI route;
- HTTP method;
- OpenAPI operation;
- GPT Action;
- broker SDK call;
- order, stop-order, replacement or cancellation method;
- transfer or withdrawal method;
- secret or full account identifier.

Gateway version `3.9.1`, GET-only public Actions and Render entrypoint `app:app`
remain unchanged.

## Rollback

Revert the package commits. The exact capacity-intent gate and the existing
purchase pre-trade preview remain independently usable.
