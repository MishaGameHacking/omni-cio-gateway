# Final Decision Review Authenticated Route Context V1

## Status

PR-81 internal authenticated request-lifecycle boundary. Read-only, typed,
bounded and fail-closed.

The package preserves the exact safe identity needed by PR-79/PR-80 and creates
`FinalDecisionReviewApprovedServerContextV1` only after the existing production
Bearer dependency, exact source lookup and successful final-review handler
validation.

## Problem closed

Before PR-81, trusted publication still owned the exact post-change scenario
identity, direction and masked account, but the PR-61 route registry retained
only the compact response plan and canonical query binding. A later request
therefore could not reconstruct the exact PR-79 context without guessing a
scenario or accepting raw Action values.

PR-81 retains a minimal internal seed during trusted publication:

- exact `scenario_id` from `ProFormaRiskIntentBindingV1`;
- publication `correlation_id` used by the existing owner-routing lifecycle;
- purchase/sell operation derived from the trusted binding direction;
- masked `AccountReference`;
- publication observation timestamp.

The seed contains no credentials, full account identifier, calculator output,
position, amount, order parameter or broker payload.

## Authenticated lifecycle

```text
trusted PR-63 publication
        |
        v
safe context seed in bounded PR-61 source
        |
        v
existing Bearer dependency succeeds
        |
        v
exact registry lookup + PR-59 handler validation
        |
        v
fresh account/direction-bound approved server context
        |
        v
internal 300-second bounded capture store
```

The Action-provided `X-Correlation-ID` remains observability-only. The approved
context uses the trusted publication correlation ID because that identity must
match the existing scenario-scoped owner routing. Invocation ID is generated
server-side for the authenticated request.

## Gates

Context creation requires:

- existing Gateway Bearer authentication already confirmed;
- exact typed context seed;
- seed age no greater than 300 seconds;
- future-clock tolerance no greater than 30 seconds;
- exact masked account equality;
- exact purchase/sell direction equality;
- valid server-generated invocation identity.

Authentication failure occurs before the route handler and therefore cannot
capture a context. Context errors are logged only as a generic unavailable
event without exception text, credentials or financial payload.

## Bounded store

`FinalDecisionReviewApprovedRouteContextStoreV1` is process-local:

- TTL: 300 seconds;
- default capacity: 64;
- duplicate invocation IDs rejected;
- oldest entry evicted when capacity is exceeded;
- restart clears all entries;
- only typed masked context is retained.

The store is evidence and a handoff boundary for the next reviewed package. It
is not a public API, owner registry or trade queue.

## Compatibility

- stable entrypoint: `app:app`;
- Gateway version remains `3.10.0`;
- production OpenAPI remains exactly 14 authenticated GET operations;
- no query, header, response field or request body is added;
- compact final-review response is unchanged;
- legacy published sources without a context seed remain readable;
- stale or absent seeds do not fabricate context;
- no broker call or financial owner call occurs during route-context creation;
- `trading_methods=false`.

## Explicitly not completed

PR-81 does not select Decision Engine, intent, capacity, explicit pro-forma or
directional preview owner ports. It does not invoke PR-80 and does not replace
the existing production `503` behavior when the reviewed response source itself
is unavailable.

The next backend package must consume the fresh authenticated context inside the
same server-owned lifecycle, select only already-existing typed owner ports and
call PR-80. Missing, stale or mismatched owners must continue to return the
existing safe unavailable outcome.

Render, Gateway, GPT Editor and rollback acceptance remain external and
`not_executed` until real evidence is collected.

## Rollback

Revert PR-81. Route publication stops retaining the safe seed and authenticated
requests stop capturing approved contexts. The existing compact read-only route,
PR-79/PR-80 internal boundaries, 14-GET OpenAPI and default fail-closed behavior
remain available. No dependency, secret, database or storage migration is
required.
