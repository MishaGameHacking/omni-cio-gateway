# Final Decision-Review GET Action OpenAPI Shadow V1

## Purpose

This package defines a candidate GET contract for the PR-53 final review response
and validates it against the effective read-only OpenAPI release rules entirely
in shadow mode.

It does not register a FastAPI route, mutate the application OpenAPI schema,
create a GPT Action or change Render configuration.

## Candidate contract

The fixed candidate is:

- path: `/decision/final-review`;
- method: `get`;
- operation ID: `getFinalDecisionReview`;
- public: `false`;
- API-key authentication required: `true`;
- response contract: `final_decision_review_response` version `1.0`;
- request body: absent;
- mutation parameters: absent;
- trading semantics: absent.

The candidate records deterministic SHA-256 identities for both the generated
Pydantic response schema and the PR-54 eligibility result.

## Shadow process

The builder:

1. deep-copies the supplied effective OpenAPI document;
2. validates the current document with the existing
   `build_read_only_release_manifest` guard;
3. requires a successful PR-54 eligibility result;
4. blocks path or operation-ID collisions;
5. verifies the exact response contract name and version;
6. adds the response schema and candidate operation only to the copy;
7. runs the existing release guard again on the shadow document;
8. requires the shadow manifest to contain exactly one additional Action;
9. verifies the candidate is a private authenticated GET Action;
10. verifies every existing Action remains unchanged.

The input OpenAPI mapping is never mutated.

## Existing release guard reuse

No parallel OpenAPI safety policy is introduced. The shadow candidate passes
through the same validator used for the current release manifest, including:

- OpenAPI 3 requirement;
- exact app version;
- approved HTTPS server hosts;
- GET-only surface;
- unique operation IDs;
- forbidden order, execution, transfer and withdrawal markers;
- public/private authentication classification.

## Fail-closed blockers

The shadow result may block on:

- ineligible PR-54 result;
- unsafe current manifest;
- path collision;
- operation-ID collision;
- missing candidate Action;
- incorrect Action count;
- changed existing Actions;
- response schema mismatch;
- failure of the existing read-only release validator.

## Safety invariants

Every candidate and shadow result keeps:

- `shadow_only=true`;
- `production_schema_mutated=false`;
- `route_added=false`;
- `openapi_changed=false`;
- `public_action_created=false`;
- `trade_authorized=false`;
- `order_created=false`;
- `execution_ready=false`;
- `trading_methods=false`.

A `shadow_valid` result is evidence for a later production contract review. It
is not route approval and does not authorize deployment or execution.

## Tests

Focused tests cover:

- valid private authenticated GET candidate;
- proof that the input OpenAPI mapping is unchanged;
- ineligible release result;
- path collision;
- operation-ID collision;
- response version substitution;
- rejection of an existing POST surface by the current release guard;
- deterministic schema and eligibility digests;
- result tampering;
- naïve timestamp rejection.
