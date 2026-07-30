# Final Decision Review Trusted Scenario Publication V1

## Purpose

PR-71 adds the internal trust boundary between calculator-owned read-only artifacts and the
bounded production scenario store registered by PR-70. The publisher does not calculate a
trade, fetch broker data, create an HTTP endpoint or authorize execution.

## Accepted artifacts

One publication contains exactly:

- one typed `CapacityPreTradeDecisionGateV1` for a purchase, or one typed
  `CapacitySellPreTradeDecisionGateV1` for a sale;
- one typed post-change `RiskPolicyEvaluationV1`;
- one safe scenario identifier;
- bounded provider and operation identifiers;
- one timezone-aware publication timestamp.

Raw dictionaries, credentials, full account identifiers and request bodies are not accepted.

## Exact validation

Before the store can be mutated, the publisher proves:

1. exactly one directional gate is present;
2. every retained capacity request has the expected buy or sell side;
3. expected instrument keys are unique;
4. preview coverage exactly matches the retained intent instruments;
5. every preview carries the same masked account;
6. the pro-forma risk account matches that preview account;
7. gate assessment and pro-forma retrieval timestamps match exactly;
8. the common source time is neither stale nor beyond the future tolerance;
9. the gate retains `order_created=false`, `execution_ready=false` and
   `trading_methods=false`;
10. the risk policy keeps margin, short sales, derivatives and currency operations disabled.

Failure occurs before publication and leaves the store unchanged.

## Runtime composition

`register_final_decision_review_production_sources()` creates one publisher backed by the same
`FinalDecisionReviewScenarioSourceStoreV1` used by the PR-69 acquisition wiring. This avoids
parallel stores, split lifecycle state and ambiguous replacement behavior.

The runtime exposes the publisher through
`FinalDecisionReviewProductionRuntimeV1.scenario_publisher`. No additional FastAPI decorator,
path, operation ID, query field or request body is created.

## Lifecycle

The underlying PR-69 store remains responsible for:

- bounded capacity;
- TTL expiry;
- exact scenario replacement;
- oldest-entry eviction;
- empty state after process restart.

The PR-71 result records only safe metadata: masked account, direction, timestamps, source
provider/operation and counts. It contains no financial payload or internal source identifier.

## Safety invariants

- internal Python API only;
- no broker SDK call;
- no order creation, replacement or cancellation;
- no funds movement;
- no public publication endpoint;
- no user-controlled raw payload;
- no trade authorization;
- `trading_methods=false`;
- production `app:app`, version `3.10.0` and the 14 authenticated GET Actions remain unchanged.

## Remaining boundary

PR-71 does not manufacture the directional gate or the pro-forma risk evaluation. A later
calculator-owned handoff must produce those exact typed artifacts from existing read-only
calculators and invoke this publisher. Render, Gateway, GPT Editor, Preview, Action-list and
rollback evidence remain unexecuted until actual production acceptance.

## Rollback

Revert PR-71. PR-70 runtime registration and PR-69 acquisition wiring remain available, but the
scenario store returns to an empty fail-closed state unless populated by another reviewed
internal mechanism.
