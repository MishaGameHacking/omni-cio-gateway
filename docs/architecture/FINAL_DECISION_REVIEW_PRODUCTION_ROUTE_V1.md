# Final decision-review production GET route v1

## Scope

PR-61 registers one production read-only Action:

- method: `GET`;
- path: `/decision/final-review`;
- operationId: `getFinalDecisionReview`;
- authentication: existing Gateway Bearer key, exported in OpenAPI as `ApiKeyAuth`;
- response: `FinalDecisionReviewResponseV1` contract `1.0`;
- request body: absent;
- trading methods: disabled.

The route does not call T-Invest, calculate new recommendations, select an option, or
create an order. It can only return a final response that was already produced and
validated by the PR-53 through PR-59 read-only chain.

## Exact query contract

The route accepts exactly the eight PR-56 query fields:

1. `account` — masked account reference;
2. `requested_option_id`;
3. `final_option_id`;
4. `intent_fingerprint`;
5. `instrument_count`;
6. repeated `instrument_keys`;
7. `response_sha256`;
8. `action_candidate_sha256`.

`instrument_count` must equal the number of unique ordered instrument keys. Full account
identifiers are rejected and are not written to logs.

## Internal source registry

SHA-256 values and query parameters are identity evidence, not a response database. The
production route therefore uses a process-local `FinalDecisionReviewSourceRegistryV1`.

Properties:

- no HTTP publish endpoint;
- publication is available only to trusted in-process orchestration;
- route plan must be ready and blocker-free;
- input binding must be valid and match the plan source exactly;
- default TTL: 15 minutes;
- default capacity: 64 entries;
- expired entries are pruned;
- oldest entries are evicted when capacity is reached;
- no credentials are stored;
- restart or redeploy clears all entries.

An empty or expired registry returns `503`. A context substitution while another reviewed
source exists returns `409`. This is intentional fail-closed behavior.

## HTTP behavior

| Status | Meaning |
|---:|---|
| 200 | Exact authenticated query matches one active reviewed source |
| 400 | Account masking, count, uniqueness, or canonical query semantics are invalid |
| 401 | Existing Gateway Bearer authentication rejected the request |
| 409 | Reviewed account, option, fingerprint, instruments, or digests do not match |
| 422 | FastAPI rejected the query or trace-header schema |
| 503 | No active reviewed source is available |

Every error response preserves `trading_methods=false` and excludes decision response
data.

## Observability

Success and post-authentication identity failures use the PR-59
`ObservabilityEventV1`. Logs may contain:

- correlation ID;
- request ID;
- masked account only;
- error code;
- safe counts.

Logs must not contain holdings, prices, full account IDs, API keys, response payloads, or
private source contracts.

## OpenAPI

The production OpenAPI document adds exactly one authenticated GET operation and the
`ApiKeyAuth` bearer security scheme. Existing Actions remain unchanged. The response is a
reference to `FinalDecisionReviewResponseV1`; no execution or funds-movement surface is
published.

## Acceptance boundary

PR-61 can complete only the PR-58 pre-merge cases. The following remain unexecuted until
an actual deployment:

- Render source-commit verification;
- cache-busted production health check;
- live authentication and exact-query calls;
- GPT Editor schema import and Preview;
- full Action-list inspection;
- rollback drill.

The route alone is not a complete user workflow. A later package must connect the trusted
read-only orchestration output to the registry without adding a public publication method.

## Rollback

Revert PR-61. The previous `app:app` service and PR-53 through PR-60 evidence remain
available, and `/decision/final-review` disappears from production OpenAPI.
