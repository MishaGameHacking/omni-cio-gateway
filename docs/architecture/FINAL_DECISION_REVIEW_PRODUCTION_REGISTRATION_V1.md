# Final Decision Review Production Registration V1

## Purpose

PR-70 introduced lazy internal registration of the PR-69 production source layer. The production object graph has since been extended by the reviewed PR-71…PR-78 packages. Registration remains internal-only and adds no Action, request field or public publication endpoint.

## Current runtime object graph

`register_final_decision_review_production_sources()` composes:

1. one bounded `FinalDecisionReviewScenarioSourceStoreV1`;
2. the canonical `FinalDecisionReviewTrustedScenarioPublisherV1`;
3. PR-72 calculator scenario handoff;
4. PR-73 exact-intent workflow;
5. PR-74 approved invocation boundary;
6. PR-75 fixed calculator-provider registry;
7. one bounded production owner-callable store;
8. PR-76 adapters registered under two fixed purchase/sell provider IDs;
9. PR-77 scenario-scoped owner-callable registration;
10. PR-78 trusted one-shot owner composition;
11. the existing workflow producer, coordinator, current-risk loader and production source wiring.

The complete graph is returned as `FinalDecisionReviewProductionRuntimeV1`. The scenario publisher and all later components share the same bounded source/store chain; the retired duplicate PR-71 publisher path is forbidden by `scripts/check_repository_layout.py`.

## Startup laziness

Registration receives callables, not financial payloads. Importing `app.py`:

- does not connect to T-Invest;
- does not load a portfolio;
- does not execute Decision Engine or risk calculators;
- starts without scenario-specific owner bundles;
- keeps process-local stores empty and fail-closed after restart.

## Action compatibility

The Gateway remains version `3.10.0` with exactly 14 authenticated `GET` Actions. No request body, mutating HTTP method, broker-write surface or user-selected provider name is added.

## Safety invariants

- `app:app` remains the Render entrypoint;
- `trading_methods=false`;
- no order create, replace or cancel call;
- no transfer, withdrawal, margin, short or derivatives execution;
- no public callable or raw financial-payload publication surface;
- no startup network/calculator call;
- no credentials or full account identifier in runtime metadata;
- missing or expired scenario sources remain fail-closed;
- green CI does not complete Render/GPT acceptance.

## Current remaining boundary

PR-78 can validate and invoke already materialized typed owners, but it intentionally does not decide when a real request should acquire them. The next functional package is PR-79 approved server-side owner acquisition as defined by `knowledge/16_CURRENT_PROGRAM_STATUS.md`. It must derive context on the server, accept no raw calculator outputs or credentials from an Action, preserve the existing OpenAPI surface and call PR-78 only after all required read-only sources are present and fresh.

Until that package and real production acceptance are complete, an empty store or `503` can be correct behavior.

## Rollback

Runtime rollback must revert the specific functional PR being deployed; this documentation package changes no runtime. The stable fallback remains the existing private GET route with empty fail-closed process-local sources, `app:app` and `trading_methods=false`.
