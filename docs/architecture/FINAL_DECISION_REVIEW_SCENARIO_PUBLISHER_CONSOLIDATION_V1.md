# Final Decision Review Scenario Publisher Consolidation V1

## Decision

PR-71 in pull request 94 is the canonical trusted scenario publisher. It performs stricter account, intent coverage, timestamp, risk-policy and non-execution checks and is already integrated into the production runtime.

The later calculator publication and registration modules from pull requests 95 and 96 duplicate a subset of that functionality. They are removed to preserve a single source of truth.

## Canonical implementation

Use:

- `FinalDecisionReviewTrustedScenarioPublisherV1`;
- `FinalDecisionReviewProductionRuntimeV1.scenario_publisher`;
- the shared production `FinalDecisionReviewScenarioSourceStoreV1`.

## Safety

Consolidation changes no HTTP route, OpenAPI operation, broker call or runtime trading flag. The canonical publisher remains internal, typed and fail-closed.

## Remaining boundary

The next package should connect calculator-owned generation of exact directional gate and pro-forma risk artifacts to the canonical trusted publisher. Production Render/GPT/rollback acceptance remains unexecuted.
