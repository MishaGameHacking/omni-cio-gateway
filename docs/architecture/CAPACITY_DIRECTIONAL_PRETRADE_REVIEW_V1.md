# Capacity Directional Pre-Trade Review V1

## Purpose

`CapacityDirectionalPreTradeReviewV1` provides one read-only envelope for an
already-validated homogeneous purchase or sell review.

It does not repeat market-capacity, affordability, position, tax or commission
calculations. The selected source gate remains embedded and authoritative.

## Inputs

The composer accepts exactly one of:

- `CapacityPreTradeDecisionGateV1` for a purchase intent;
- `CapacitySellPreTradeDecisionGateV1` for a sell intent.

Providing neither gate or both gates is a structural error.

## Direction rules

Every capacity request inside the source intent must use one homogeneous side.

- purchase source requires every request to use `buy`;
- sell source requires every request to use `sell`;
- mixed buy/sell intent sets are rejected fail-closed;
- a source gate for the wrong direction is rejected fail-closed.

This keeps broker-preview semantics explicit and prevents a purchase preview
from being interpreted as sale evidence or vice versa.

## Preserved evidence

The result retains:

- the complete source gate;
- the exact base intent gate;
- required and reviewed instrument counts;
- broker-preview coverage state;
- exact intent-binding state;
- commission integrity;
- purchase affordability when direction is `buy`;
- position, open-order and tax-basis confirmations when direction is `sell`;
- typed source blockers and warnings inside the embedded source gate.

## Fail-closed behavior

The unified review returns `abstain` and the existing no-action option when:

- directions are mixed;
- source type and intent direction disagree;
- the source gate is not ready;
- preview coverage is incomplete;
- exact intent binding is incomplete.

A ready review preserves the source option and analytical action. It never
selects or upgrades an option.

## Safety invariants

Every result keeps:

- `option_selected_by_review=false`;
- `order_created=false`;
- `execution_ready=false`;
- `trading_methods=false`.

The package adds no HTTP route, OpenAPI operation, GPT Action, broker SDK call,
order method, transfer or withdrawal capability.

## Tests

Focused tests cover:

- ready purchase mapping;
- ready sell mapping;
- mixed-direction intent rejection;
- wrong source-direction rejection;
- blocked source preservation;
- incomplete coverage and intent binding;
- exactly-one-source structural validation;
- final-option tamper rejection.
