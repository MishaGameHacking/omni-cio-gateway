# Final Decision Review Calculator Intent Workflow V1

## Purpose

Build the exact capacity-intent gate from approved analytical decision and capacity evidence before delegating broker-preview publication to the PR-72 calculator handoff.

The workflow closes the gap between a typed `DecisionSetV1` plus `CapacityAssessmentV1` evidence and the existing purchase/sell pre-trade publication boundary.

## Inputs

Each invocation accepts:

- one typed `DecisionSetV1`;
- one typed `CapacityIntentDecisionGateRequestV1` containing the expected order intent;
- one or more typed `CapacityAssessmentV1` rows;
- typed purchase or sell broker previews;
- one already calculated typed pro-forma risk evaluation;
- a bounded scenario identifier and optional publication timestamp.

Raw decision, capacity and preview mappings are rejected.

## Pipeline

1. validate the decision, intent request and capacity assessments;
2. evaluate the exact capacity-intent gate at the pro-forma risk timestamp;
3. pass the resulting typed intent gate and previews to PR-72;
4. let PR-72 build the directional broker-preview gate;
5. publish through the registered trusted scenario publisher and bounded TTL store.

## Fail-closed behavior

Capacity mismatch, missing coverage, stale data, preview mismatch or an unsafe risk policy cannot produce a ready review source. Structural misuse fails before store mutation. A valid but blocked analytical path may only publish a blocked, non-executing review source.

## Safety invariants

- internal Python API only;
- no FastAPI decorator or public publication method;
- no request body or production OpenAPI change;
- no broker total recomputation;
- no order create, replace or cancel call;
- no credential or full account identifier;
- no trade authorization or execution readiness;
- `trading_methods=false`.

## Runtime composition

`FinalDecisionReviewProductionRuntimeV1` owns one intent workflow backed by the exact PR-72 handoff, trusted publisher and process-local scenario store.

Registration performs no calculation, network request or store mutation.

## Remaining boundary

The workflow does not choose an investment action and does not calculate capacity, broker previews or pro-forma risk. A trusted caller must supply those typed source artifacts from their existing read-only owners. Production Render, Gateway, GPT Preview and rollback acceptance remain separate evidence-driven steps.

## Rollback

Revert this package. PR-72 and the earlier fail-closed source acquisition chain remain available.
