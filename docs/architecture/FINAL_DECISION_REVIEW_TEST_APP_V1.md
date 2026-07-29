# Isolated Final Decision-Review FastAPI Candidate V1

## Purpose

This package builds a separate FastAPI application solely for contract and HTTP
integration testing of the reviewed final-review Action.

It does not import, mount or mutate the production `app` object.

## Reviewed HTTP surface

The isolated application exposes exactly one operation:

- `GET /decision/final-review`;
- operation ID `getFinalDecisionReview`;
- private `ApiKeyAuth` security scheme;
- no request body;
- the exact eight query parameters from PR-56;
- `FinalDecisionReviewResponseV1` response model.

The application declares the approved HTTPS server only so the existing
read-only release validator can inspect the candidate schema.

## Handler composition

The route:

1. lets FastAPI validate required query fields, numeric bounds and SHA-256
   formats;
2. constructs the strict PR-56 query contract;
3. maps invalid masked-account or semantic input to 400;
4. creates a request-scoped copy of the reviewed input binding;
5. invokes the PR-59 handler shadow;
6. returns only the compact response or the fixed safe error body.

No source value is recalculated.

## Tested HTTP outcomes

- 200: exact authenticated reviewed query;
- 400: semantic canonical-query failure such as an unmasked account;
- 401: private authentication missing or rejected;
- 409: option, fingerprint, account or digest substitution;
- 422: FastAPI request-schema validation failure;
- 503: reviewed source unavailable.

## OpenAPI verification

The tests run the existing `build_read_only_release_manifest` against the
isolated schema and require:

- OpenAPI 3;
- approved HTTPS server;
- exactly one GET Action;
- unique `operationId`;
- private authentication;
- no forbidden execution surface;
- `trading_methods=false`.

They also compare path, method and operation ID to the PR-58 proposed route.

## Isolation markers

The test app records:

- `isolated_candidate=true`;
- `production_app_imported=false`;
- `production_app_mutated=false`;
- `trading_methods=false`.

These markers are test assertions, not production health claims.

## Safety boundary

The factory accepts already reviewed plan and binding objects plus an injected
authentication validator. It does not read environment credentials, connect to
a broker, call an external API or register anything in `app.py`.

The production OpenAPI schema and Render entrypoint remain unchanged.

## Next boundary

A separate production route Pull Request may be considered only after this
isolated candidate passes Regression Shield. That later PR must use the PR-58
acceptance matrix and cannot mark post-deploy or GPT Editor Preview checks as
complete before they actually run.
