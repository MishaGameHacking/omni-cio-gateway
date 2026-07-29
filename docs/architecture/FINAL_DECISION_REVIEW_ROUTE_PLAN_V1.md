# Final Decision-Review Route Implementation Plan V1

## Purpose

This package converts the PR-57 readiness dossier into a machine-validated
implementation plan and acceptance matrix for a later, separate production
route Pull Request.

The plan does not modify FastAPI, OpenAPI, Render or GPT Actions.

## Proposed contract

The plan fixes the only reviewed route candidate:

- path: `/decision/final-review`;
- method: `GET`;
- operation ID: `getFinalDecisionReview`;
- private Action;
- authentication: `ApiKeyAuth`;
- no request body;
- exact eight-parameter query allowlist from PR-56;
- response: `FinalDecisionReviewResponseV1` contract `1.0`;
- no execution semantics.

A changed method, path, operation ID, authentication scheme, query allowlist or
response contract blocks implementation review.

## Acceptance matrix

The default matrix contains thirteen blocking, unexecuted cases.

### Pre-merge

1. existing read-only release guard accepts exactly one new private GET Action;
2. full Regression Shield passes on the final route PR SHA;
3. route handler reaches only reviewed read-only orchestration.

### Post-deploy

1. Render source commit equals the reviewed merge commit;
2. cache-busted `/health` confirms `app:app`, read-only and
   `trading_methods=false`;
3. unauthenticated request is rejected;
4. exact reviewed query returns the compact v1 response;
5. substituted account, option, fingerprint or digest is rejected.

### GPT Editor Preview

1. reviewed OpenAPI schema imports successfully;
2. authenticated Preview call returns only the masked compact response;
3. full Action list contains no write or funds-movement Action.

### Rollback drill

1. the last known-good immutable commit is recorded;
2. rollback restores the previous health and GET-only contract.

## Truthfulness boundary

Every acceptance case is created with:

- `blocking=true`;
- `executed=false`;
- `passed=false`.

The plan rejects any attempt to mark these future checks as already executed or
successful.

## Readiness meaning

`ready_for_implementation_review` means only that:

- the PR-57 dossier is ready;
- the proposed contract matches reviewed evidence;
- query and response contracts match;
- authentication and safe observability remain required;
- all acceptance stages are represented;
- no production diff has been applied.

It does not authorize implementation, deployment or Action configuration.

## Safety invariants

The plan always keeps:

- `implementation_authorized=false`;
- `route_approval_granted=false`;
- `production_route_added=false`;
- `production_openapi_changed=false`;
- `deployment_performed=false`;
- `gpt_preview_performed=false`;
- `trade_authorized=false`;
- `order_created=false`;
- `execution_ready=false`;
- `trading_methods=false`.

## Next boundary

A later route implementation PR must use this plan as its acceptance checklist.
That PR must remain independently reviewable and must not merge until its final
SHA passes all pre-merge automated checks.

Post-deploy and GPT Editor checks cannot be marked complete before deployment
and Preview actually occur. Any failure triggers rollback to the documented
known-good commit.
