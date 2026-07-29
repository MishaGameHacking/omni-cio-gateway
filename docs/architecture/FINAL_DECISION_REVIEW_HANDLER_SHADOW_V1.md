# Final Decision-Review Handler Shadow V1

## Purpose

This package models the future route-handler boundary without registering a
FastAPI route or changing production OpenAPI.

It accepts only:

- a PR-58 route implementation plan;
- a PR-56 exact input binding;
- an authentication decision boolean;
- source availability state;
- safe trace identifiers.

It returns either the exact PR-53 compact response or a fail-closed typed error.

## Success path

A shadow request succeeds only when:

- private authentication is confirmed;
- the PR-58 plan is ready and blocker-free;
- the PR-56 binding is valid and blocker-free;
- query, response and Action-candidate identities match the binding embedded in
  the plan;
- the reviewed source is available.

Success produces:

- HTTP model status `200`;
- the exact compact response stored in the readiness dossier;
- no recalculation;
- no external broker call;
- safe observability metadata.

## Error mapping

The fixed mapping records both framework-level and handler-level outcomes:

| Error | HTTP | Boundary |
|---|---:|---|
| `FINAL_REVIEW_INVALID_REQUEST` | 400 | canonical request parsing |
| `FINAL_REVIEW_AUTHENTICATION_REQUIRED` | 401 | private authentication |
| `FINAL_REVIEW_SOURCE_CONFLICT` | 409 | exact identity or binding conflict |
| `FINAL_REVIEW_SCHEMA_VALIDATION` | 422 | framework/Pydantic validation |
| `FINAL_REVIEW_SOURCE_UNAVAILABLE` | 503 | plan or reviewed source unavailable |

The shadow adapter directly models 200, 401, 409 and 503. A malformed request
cannot enter the adapter and is represented by the documented 400/422 framework
boundary.

## Safe observability

Every result produces `ObservabilityEventV1` with:

- correlation ID;
- optional request ID;
- masked account reference;
- outcome and non-sensitive error code;
- instrument count;
- route-plan blocker count;
- external-call status `not_called`;
- `contains_sensitive_payload=false`;
- `trading_methods=false`.

The event does not contain holdings, prices, order parameters, tokens or the
full account identifier.

## Fail-closed precedence

1. missing authentication → 401;
2. blocked plan or unavailable source → 503;
3. blocked or substituted input binding → 409;
4. otherwise → exact 200 response.

No failed result may include response data.

## Safety invariants

Every result keeps:

- `shadow_only=true`;
- `route_registered=false`;
- `production_openapi_changed=false`;
- `public_action_created=false`;
- `external_broker_called=false`;
- `source_values_recomputed=false`;
- `trade_authorized=false`;
- `order_created=false`;
- `execution_ready=false`;
- `trading_methods=false`.

## Next boundary

A later production route PR may wrap this reviewed adapter with FastAPI query
parsing and existing API-key authentication. That route PR must still pass the
PR-58 pre-merge matrix and cannot claim post-deploy or GPT Preview acceptance
before those checks actually run.
