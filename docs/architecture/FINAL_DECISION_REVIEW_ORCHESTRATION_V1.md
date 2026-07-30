# Final decision-review end-to-end internal orchestration v1

## Scope

PR-63 composes the completed read-only final-review chain into one internal function. The
input is an already formed `ProFormaRiskIntentBindingV1`; the output is either a published
source for the PR-61 production GET route or a structured fail-closed result identifying
the first blocked stage.

The orchestration function is not an Action. It adds no HTTP route, does not mutate
production OpenAPI, does not call T-Invest, does not recompute upstream financial values,
and does not authorize execution.

## Pipeline

The function executes these stages in order:

1. **Response shadow** — PR-53 compact response and exact source-binding parity.
2. **Release eligibility** — PR-54 schema, payload, provenance, account and read-only checks.
3. **Action shadow** — PR-55 candidate rebuilt against a deep-copied pre-route baseline.
4. **Input binding** — PR-56 exact eight-query contract and identity digests.
5. **Route readiness** — PR-57 authentication, rollback, observability and context controls.
6. **Route plan** — PR-58 implementation plan and complete acceptance matrix.
7. **Publication** — PR-62 internal publication into the PR-61 bounded registry.

The first blocked stage stops the chain. Later artifacts are absent and the registry is not
mutated.

## Production OpenAPI reconstruction

PR-61 already exposes `/decision/final-review`. PR-55 validation, however, was designed to
prove that exactly one candidate Action can be added to the previous schema. PR-63 therefore:

- deep-copies the current production OpenAPI document;
- requires the existing route to have exact method, operation ID, `ApiKeyAuth`, no request
  body and the exact ordered eight query parameters;
- removes only that route from the copy;
- rebuilds the PR-55 candidate and validates the resulting shadow schema;
- never mutates `app.openapi()` or the production schema cache.

Missing, substituted or broadened production contracts stop at `action_shadow`.

## Result contract

`FinalDecisionReviewOrchestrationResultV1` contains:

- orchestration timestamp;
- `published` or `blocked` status;
- completed stage;
- primary blocker;
- the contiguous chain of artifacts produced before the stop point;
- publication result only after complete success;
- immutable read-only safety markers.

A published result must contain every stage artifact. A blocked result cannot contain a
publication. Tampering with production-schema, HTTP-route, broker-call or execution flags is
rejected by Pydantic validation.

## No-action behavior

A safe `WAIT_FOR_DATA` / no-action response may pass the release chain and be published. This
is intentional: the route communicates a validated abstention and still preserves
`trade_authorized=false`, `order_created=false`, `execution_ready=false` and
`trading_methods=false`.

## Failure examples

| Stage | Example blocker |
|---|---|
| response shadow | response/source option or account substitution |
| release eligibility | payload, provenance or source-count policy exceeded |
| action shadow | production route missing, wrong auth, wrong query order or unsafe schema |
| input binding | query allowlist, size, freshness or digest mismatch |
| route readiness | authentication, rollback or observability control missing |
| route plan | proposed contract or acceptance matrix drift |
| publication | invalid trace ID, timestamp or exact publication context |

## Acceptance and testing

Focused tests prove:

- complete composition and authenticated production `200`;
- safe no-action publication;
- release-policy stop before Action construction;
- production route substitution detection;
- input-policy and readiness-control stops;
- publication-trace stop with empty registry;
- exact replacement on repeated orchestration;
- unchanged production OpenAPI;
- immutable result and timezone checks.

## Remaining production boundary

The internal composition is code-complete only after Regression Shield. It does not by
itself prove that Render has deployed the new commit or that GPT Editor imported and tested
the schema. Live commit verification, health checks, authenticated Preview, full Action-list
inspection and rollback remain separate acceptance steps.

## Rollback

Revert PR-63. PR-61 route and PR-62 manual internal publisher remain available; with no
published source the route continues to fail closed with `503`.
