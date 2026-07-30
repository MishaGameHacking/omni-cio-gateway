# Final Decision Review Production Sources V1

## Purpose

PR-69 provides the first concrete production-facing source layer for the PR-68 acquisition adapter without creating a new HTTP endpoint or enabling trading.

## Source ownership

Current portfolio risk is loaded from the existing read-only portfolio pipeline:

1. `get_portfolio_market_snapshot`;
2. `portfolio_snapshot_v1_from_market_payload`;
3. `build_advanced_portfolio_analytics`;
4. `evaluate_conservative_risk_policy`.

The loader does not call any order-placement method and preserves the source timestamps carried by the versioned contracts.

Scenario-specific inputs cannot be reconstructed from hashes or the current portfolio alone. They are therefore stored as one atomic process-local bundle:

- exactly one purchase or sell pre-trade gate;
- exactly one already calculated pro-forma risk evaluation;
- a safe scenario identifier;
- bounded storage time and expiry.

Partial bundles are rejected. Missing or expired bundles remain missing and are never fabricated.

## Store lifecycle

`FinalDecisionReviewScenarioSourceStoreV1` defaults to:

- TTL: 900 seconds;
- capacity: 64 bundles;
- oldest-entry eviction;
- replacement by exact scenario ID;
- empty state after process restart.

The store is internal Python state. There is no HTTP publication method.

## Acquisition wiring

`FinalDecisionReviewProductionSourceWiringV1` constructs the four PR-68 loaders for one acquisition attempt:

- selected purchase or sell gate from the scenario store;
- unselected direction remains missing and is not called;
- current risk from the live read-only portfolio pipeline;
- pro-forma risk from the exact scenario bundle.

The existing PR-68 adapter then converts loader outcomes into PR-67 evidence and invokes the coordinator.

## Safety invariants

- `trading_methods=false`;
- no public source-publication endpoint;
- no request body;
- no order create, replace, cancel or execution call;
- no funds movement;
- no credentials or full account in store metadata;
- missing, expired, invalid or failed sources stay fail-closed;
- production OpenAPI and the 14 GET Actions are unchanged.

## Remaining boundary

This package exports production-facing wiring but does not register it in `app.py`. Registration and calculator-owned publication of scenario bundles require a separate PR so the startup/runtime diff remains reviewable.

Real Render, Gateway, GPT Editor Preview and rollback evidence remain unexecuted until actual deployment acceptance.

## Rollback

Revert PR-69. PR-68 acquisition, PR-67 coordinator and earlier final-review layers remain unchanged.
