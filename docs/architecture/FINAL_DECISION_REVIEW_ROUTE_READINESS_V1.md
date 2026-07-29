# Final Decision-Review Production-Route Readiness Dossier V1

## Purpose

This package composes the completed read-only evidence chain into one auditable
internal dossier before any production route is added:

- PR-53 user-safe final response;
- PR-54 response release eligibility;
- PR-55 private GET Action/OpenAPI shadow;
- PR-56 exact query-only input binding.

The output may say `ready_for_route_review`. It never grants route approval,
changes OpenAPI, creates a public Action or authorizes execution.

## Evidence checks

The dossier evaluates nine independent gates:

1. all source decisions are valid;
2. every source identifies the same PR-53 response;
3. PR-56 identifies the exact PR-55 Action candidate;
4. the PR-56 query digest remains canonical;
5. masked account, requested/final options, fingerprint and ordered instruments
   match the response;
6. the candidate remains private and uses required `ApiKeyAuth`;
7. deployment rollback is anchored to
   `docs/operations/DEPLOYMENT_RUNBOOK.md`;
8. safe observability requires `ObservabilityEventV1`, correlation IDs,
   masked-account-only logs, no sensitive payload logs, `/health` and `app:app`;
9. no source has already added or approved the route.

Every failed gate becomes a deterministic blocker.

## Operational controls

`FinalDecisionReviewRouteControlsV1` records the controls expected before a
human production contract review:

- private Action;
- mandatory API-key authentication;
- documented server authorization boundary;
- rollback runbook and commit pinning;
- safe structured observability;
- health endpoint `/health`;
- stable entrypoint `app:app`.

These records describe required controls. They are not credentials and contain
no secret values.

## Identity model

Response, Action candidate and query are serialized as compact sorted JSON and
identified with SHA-256. The dossier verifies that the digests stored by
PR-54–PR-56 all point to the same objects.

The digests are audit identities. They are not order IDs, confirmation tokens,
credentials or execution idempotency keys.

## Fail-closed behavior

The dossier is blocked when any source is blocked or when identity, context,
authentication, rollback, observability or safety controls do not reconcile.

A ready dossier still preserves:

- `route_approval_granted=false`;
- `production_route_added=false`;
- `production_openapi_changed=false`;
- `public_action_created=false`;
- `trade_authorized=false`;
- `order_created=false`;
- `execution_ready=false`;
- `trading_methods=false`.

## Tests

Focused tests cover:

- complete ready-for-review evidence;
- response digest substitution;
- candidate digest substitution;
- query digest substitution;
- option/context substitution;
- missing server authorization control;
- incorrect rollback reference;
- missing correlation-ID observability control;
- attempts to mark the route already reviewed;
- dossier-result tampering;
- naïve assessment timestamps.

## Next boundary

A ready dossier is a prerequisite for a separate production contract review.
The next package may define the route implementation plan and acceptance matrix,
but must still avoid activating the production route until:

- the implementation diff is reviewed;
- the current OpenAPI release guard passes;
- Render health is verified after deployment;
- the GPT Editor Action is tested in Preview;
- rollback steps are confirmed.
