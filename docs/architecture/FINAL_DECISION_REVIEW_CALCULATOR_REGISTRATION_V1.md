# Final Decision Review Calculator Registration V1

## Purpose

Create one lazy process-local calculator publisher over the exact scenario source store registered by the production source layer.

This package deliberately stops before modifying `app.py`. It separates library registration and production-wrapper integration into two reviewable changes.

## Registration result

The immutable registration holds:

- the exact existing scenario source store;
- one calculator-owned publisher bound to that same store;
- explicit lazy/startup safety flags.

Store identity is checked by object identity, not by value equality.

## Startup behavior

Registration performs no calculation and no broker call. It does not publish a scenario and does not mutate the store.

## Safety invariants

- internal Python API only;
- lazy registration;
- no startup calculation;
- no startup broker call;
- no HTTP publication method;
- no trade authorization;
- no order creation;
- `trading_methods=false`.

## Remaining boundary

A separate package may instantiate this registration in the production wrapper using `final_decision_review_scenario_source_store`. Calculator workflow invocation remains separate and must supply exact typed artifacts.

## Rollback

Revert this package. PR-71 remains available as an unregistered internal publisher implementation.
