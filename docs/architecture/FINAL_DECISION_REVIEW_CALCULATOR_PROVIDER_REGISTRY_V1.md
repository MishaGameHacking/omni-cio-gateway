# Final Decision Review Calculator Provider Registry V1

## Purpose

Provide one internal allowlist of calculator-provider and analytical-operation pairs over the PR-74 invocation boundary.

The registry makes the trusted caller explicit. It does not discover providers dynamically and does not accept user-selected module names, callables or raw payloads.

## Registration

A provider is registered by:

- one safe provider ID;
- one exact allowlisted operation: `purchase_review` or `sell_review`;
- one callable returning `ApprovedCalculatorProviderBundleV1`.

Registration is process-local, protected by a lock and performs no provider, network or broker call. Duplicate provider/operation pairs are rejected.

## Provider bundle

The immutable typed bundle contains:

- exact scenario and correlation IDs;
- one timezone-aware build timestamp;
- one typed analytical decision;
- one typed exact-intent request;
- one or more typed capacity assessments;
- exactly one non-empty purchase or sell preview tuple;
- one typed pro-forma risk evaluation.

The build timestamp must match the pro-forma risk retrieval timestamp exactly.

## Invocation gates

Before PR-74 the registry verifies:

1. provider ID and request contract type;
2. exact registered provider/operation pair;
3. typed bundle return value;
4. exact scenario and correlation parity;
5. bundle freshness and future tolerance;
6. purchase/sell operation and preview-direction parity.

Provider exceptions are converted to a stable error code without exposing exception text.

## Safety invariants

- internal Python API only;
- no FastAPI route or operation ID;
- no production OpenAPI change;
- no startup provider or broker call;
- no raw provider mapping;
- no credential or full account identifier;
- no broker create, replace or cancel call;
- no trade authorization or execution readiness;
- `trading_methods=false`.

## Runtime composition

`FinalDecisionReviewProductionRuntimeV1` owns one initially empty provider registry over the exact PR-74 invocation boundary. Concrete provider registration requires a separate reviewed package.

## Remaining boundary

The registry does not implement concrete portfolio, capacity, broker-preview or pro-forma risk providers. Those adapters must reuse existing read-only owners and must be registered explicitly. Render/Gateway/GPT/rollback acceptance remains evidence-driven and unexecuted.

## Rollback

Revert this package. PR-74 and earlier fail-closed calculator/source layers remain available.
