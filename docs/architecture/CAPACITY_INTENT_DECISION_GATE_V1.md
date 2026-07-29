# Capacity Intent Decision Gate v1

## Purpose

This layer binds a capacity-aware analytical review to the exact order intent
that was assessed. It prevents a ready capacity result for one request from
being reused for another request with a different side, amount, lot structure,
price or execution window.

The layer is internal and read-only. It does not create an order, call the
broker, calculate affordability or expose a FastAPI route.

## Input

`CapacityIntentDecisionGateRequestV1` contains:

- one explicit analytical change-option ID;
- one or more complete `CapacityOrderRequestV1` objects;
- unique instrument keys;
- unique capacity request IDs;
- `execution_ready=false`;
- `trading_methods=false`.

Each expected request already reconciles:

```text
units = quantity_lots × lot_size
order_notional = units × reference_price
```

## Composition

`apply_capacity_intent_decision_gate` first runs the existing
`apply_capacity_decision_gate` using the exact expected instrument coverage.
The base gate retains responsibility for:

- base Decision Set readiness and freshness;
- requested-option existence and status;
- complete capacity coverage;
- capacity freshness;
- capacity readiness;
- duplicate and unrequested capacity assessment rejection.

The exact-intent layer then compares every expected request with the request
embedded in the matched `CapacityAssessmentV1`.

## Exact fields

The following fields must match exactly:

1. capacity request ID;
2. instrument key;
3. side;
4. currency;
5. quantity in lots;
6. lot size;
7. reference price;
8. intended execution days;
9. units;
10. order notional.

Instrument identity is also enforced by the coverage map and both request
contracts. No tolerance, rounding substitution or currency conversion is
applied.

## Fail-closed result

The result abstains and returns the existing no-action option when any of the
following is true:

- the base capacity gate is not ready;
- expected instrument coverage is incomplete;
- at least one exact intent field differs.

A mismatch remains visible through `CapacityIntentMismatch`. The gate never
silently changes expected values to the actual capacity request.

## Readiness

`gate_ready=true` only when:

- the base capacity gate is ready;
- every expected intent has one matched capacity assessment;
- every matched capacity request is an exact field-for-field match.

A ready result preserves the requested analytical review action. It does not
select or upgrade the option and does not assert that a trade may be executed.

## Explicit limitations

Every result states:

- `intent_binding_only=true`;
- `affordability_checked=false`;
- `broker_preview_checked=false`;
- `option_selected_by_gate=false`;
- `order_created=false`;
- `execution_ready=false`;
- `trading_methods=false`.

A later package may compose exact intent binding with affordability and broker
preview evidence. That later package must remain non-executing unless the
project separately completes and approves all trading-admission stages.

## Security boundary

This package adds no:

- FastAPI route;
- OpenAPI operation;
- GPT Action;
- broker SDK import;
- order creation, replacement or cancellation method;
- transfer or withdrawal method;
- secret or account data field.

Gateway version `3.9.1` and Render entrypoint `app:app` remain unchanged.

## Rollback

Revert the package commits. The existing market-capacity assessment and base
capacity decision gate remain independently usable.
