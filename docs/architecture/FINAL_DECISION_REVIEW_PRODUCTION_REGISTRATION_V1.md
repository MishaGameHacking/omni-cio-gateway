# Final Decision Review Production Registration V1

## Purpose

PR-70 registers the merged PR-69 production source layer inside the production `app:app`
wrapper. Registration is internal-only and does not add an Action, request field or public
publication endpoint.

## Runtime object graph

At import time the wrapper creates:

1. the existing production final-review workflow bridge;
2. one `FinalDecisionReviewWorkflowProducerV1`;
3. one `FinalDecisionReviewWorkflowCoordinatorV1`;
4. one bounded `FinalDecisionReviewScenarioSourceStoreV1`;
5. one lazy current-risk loader;
6. one `FinalDecisionReviewProductionSourceWiringV1`.

The complete object graph is returned as `FinalDecisionReviewProductionRuntimeV1` and is
exported through:

- `final_decision_review_production_runtime`;
- `final_decision_review_scenario_source_store`;
- `final_decision_review_source_wiring`.

## Startup laziness

Registration receives a callable rather than a portfolio payload. The callable invokes the
existing read-only portfolio-market engine with depth `1` and maximum `50` instruments only
when trusted internal acquisition is explicitly requested.

Importing `app.py` therefore:

- does not connect to T-Invest;
- does not load a portfolio;
- does not calculate risk;
- leaves the scenario source store empty.

## Action compatibility

The release remains version `3.10.0` and the production OpenAPI surface remains exactly 14
private authenticated `GET` operations. No request body or mutating HTTP method is added.

## Safety invariants

- `app:app` remains the Render entrypoint;
- `trading_methods=false`;
- no broker order create, replace or cancel call;
- no public scenario-source publication method;
- no startup network call;
- no credentials or full account in runtime metadata;
- empty or missing scenario sources remain fail-closed;
- production source registration does not complete Render/GPT acceptance.

## Remaining boundary

The process-local source store is now registered, but it is not automatically populated.
A trusted calculator-owned publisher must provide one exact purchase/sell pre-trade gate and
the corresponding pro-forma risk evaluation. Until that package and actual production
acceptance are completed, the final-review route may correctly return `503` after restart.

## Rollback

Revert PR-70. The private final-review GET route and PR-69 library remain available, but the
production scenario store and acquisition wiring are no longer registered in `app.py`.
