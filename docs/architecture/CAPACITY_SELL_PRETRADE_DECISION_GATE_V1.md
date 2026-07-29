# Capacity Sell Pre-Trade Decision Gate V1

## Purpose

`CapacitySellPreTradeDecisionGateV1` is a read-only overlay that binds an
already-approved capacity intent to the exact broker sell preview for every
affected instrument.

It does not create, replace, cancel or submit an order.

## Inputs

The gate consumes:

- one `CapacityIntentDecisionGateV1`;
- one `SellPreTradePreviewV1` per expected capacity request;
- an explicit point-in-time assessment timestamp;
- a bounded preview-age policy.

## Exact intent binding

For every expected instrument, the sell preview must match the capacity
request on:

1. side (`sell`);
2. currency;
3. lot size;
4. quantity in lots;
5. reference/unit price.

Coverage is exact. Duplicate previews and previews for unrequested instruments
are structural errors.

## Sell-specific confirmations

A ready gate requires complete broker-preview coverage plus:

- confirmed position availability;
- checked open sell orders with no conflict;
- confirmed tax basis and a broker-derived tax estimate;
- confirmed arithmetic integrity and a canonical commission;
- fresh preview timestamps;
- `preview_ready=true` for every preview.

Missing or contradictory evidence produces a typed blocker and forces the
existing no-action option with `final_action=wait_for_data`.

## Money boundary

The gate intentionally does not recompute broker proceeds. This is necessary
because bond sales can use percentage-of-nominal pricing and accrued interest.

The authoritative values remain inside `SellPreTradePreviewV1`:

- gross security proceeds;
- accrued interest;
- gross proceeds;
- commission;
- estimated tax;
- net proceeds.

The result always reports
`net_proceeds_recomputed_by_gate=false`.

## Fail-closed behavior

Any blocker returns:

- `status=abstain`;
- `gate_ready=false`;
- the existing no-action option;
- `final_action=wait_for_data`.

A ready result preserves the option and analytical action from the base intent
gate. The sell gate never selects or upgrades an option.

## Safety invariants

Every result retains:

- `option_selected_by_gate=false`;
- `order_created=false`;
- `execution_ready=false`;
- `trading_methods=false`.

The package adds no FastAPI route, OpenAPI operation, GPT Action, broker write
method, transfer or withdrawal capability.

## Tests

Focused tests cover:

- a fully matched ready sell preview;
- an unready preview;
- buy/sell side substitution;
- price and lot-quantity substitution;
- stale and future timestamps;
- incomplete multi-instrument coverage;
- a blocked base intent;
- duplicate and unrequested previews;
- naïve timestamps;
- contract tampering.
