# Final Decision Review Calculator Publication V1

## Purpose

This package closes the internal boundary between trusted calculator-owned pre-trade/risk artifacts and the process-local scenario source store registered by PR-70.

It does not create an HTTP publication method and does not add or change an Action.

## Inputs

One publication contains:

- a bounded scenario ID;
- exactly one purchase or sell pre-trade decision gate;
- one already calculated pro-forma risk evaluation;
- one timezone-aware publication timestamp.

The publisher does not fetch market data, recompute broker previews, calculate risk or construct a second intent.

## Fail-closed checks

Before mutating the store, the publisher requires:

1. exactly one direction;
2. typed purchase/sell gate;
3. typed pro-forma risk evaluation;
4. aware UTC source timestamps;
5. gate/risk timestamp skew within policy;
6. no future source;
7. publication delay within policy.

A failed check leaves the scenario store unchanged.

## Result

The immutable result records:

- direction;
- calculator timestamp;
- publication timestamp;
- source age;
- replacement and eviction state;
- active bundle count.

Safety fields are fixed to internal/read-only values:

- `internal_only=true`;
- `calculator_owned=true`;
- `user_controlled_publication_surface=false`;
- `http_publication_method_created=false`;
- `broker_write_called=false`;
- `trade_authorized=false`;
- `order_created=false`;
- `execution_ready=false`;
- `trading_methods=false`.

## Remaining boundary

This module provides the trusted calculator-owned publication API. A later package must invoke it from the exact purchase/sell calculator after both the broker preview gate and pro-forma risk evaluation have been produced. Render, Gateway, GPT Editor/Preview and rollback acceptance remain separate dated checks.

## Rollback

Revert the package. PR-69/PR-70 source wiring remains registered but the store stays fail-closed and empty unless another trusted internal publisher exists.
