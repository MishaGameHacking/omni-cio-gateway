# Final Decision Review Approved Invocation V1

## Purpose

Provide one internal allowlisted and replay-safe control-plane boundary over the PR-73 calculator intent workflow.

This boundary controls **analytical review publication only**. It is not order idempotency and cannot authorize, create, replace or cancel a broker order.

## Request contract

An invocation contains only:

- one safe invocation ID;
- one safe scenario ID;
- one safe correlation ID;
- one allowlisted operation: `purchase_review` or `sell_review`;
- one timezone-aware invocation timestamp.

Raw mappings, credentials, full account IDs and HTTP request bodies are not accepted.

## Invocation policy

Before calling PR-73 the boundary verifies:

1. exact request contract type;
2. operation allowlist and directional method parity;
3. invocation freshness and future tolerance;
4. absence of a completed invocation with the same ID inside the replay TTL;
5. bounded replay-cache capacity.

The validation, PR-73 call, result construction and replay-cache commit run under one process-local lock.

## Failure semantics

- wrong operation, stale/future timestamp or replay fails before PR-73;
- a structural PR-73 failure does not consume the invocation ID;
- only a successfully constructed trusted publication result commits the replay ID;
- concurrent duplicate invocations can complete at most once.

## Result contract

The result includes the request, completion time, trusted publication result and safe source counts. It permanently fixes all execution and public-surface flags to `false`.

## Safety invariants

- internal Python API only;
- no FastAPI route or operation ID;
- no production OpenAPI change;
- no request body;
- no broker write call;
- no trade authorization or execution readiness;
- no full account identifier or credential;
- `trading_methods=false`.

## Runtime composition

`FinalDecisionReviewProductionRuntimeV1` owns one approved invocation boundary over the exact registered PR-73 workflow. Registration is lazy and performs no calculation, publication or broker call.

## Remaining boundary

A trusted internal caller must still provide the typed decision, capacity evidence, broker previews and pro-forma risk. Real Render/Gateway/GPT/rollback acceptance remains evidence-driven and unexecuted until deployment checks are performed.

## Rollback

Revert this package. PR-73 and the earlier fail-closed calculator/source layers remain available.
