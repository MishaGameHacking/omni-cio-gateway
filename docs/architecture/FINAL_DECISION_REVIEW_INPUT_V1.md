# Final Decision-Review Read-Only Input V1

## Purpose

This package defines the internal query/context contract for a future private
`GET /decision/final-review` Action.

It binds the minimal retrieval input to the exact PR-53 response and the exact
PR-55 Action candidate before any production route review.

It does not register a FastAPI route, change OpenAPI, call a broker or authorize
an order.

## Query-only contract

`FinalDecisionReviewReadOnlyQueryV1` carries only:

- masked account context;
- requested option ID;
- final option ID;
- exact intent fingerprint;
- exact ordered instrument keys and count;
- SHA-256 identity of the reviewed response;
- SHA-256 identity of the PR-55 Action candidate.

The contract has no request body and no credential, execution, mutation,
transfer or withdrawal fields.

Unknown fields are rejected by the strict contract model. The account identifier
must remain masked.

## Binding process

`bind_final_decision_review_read_only_input` performs fourteen independent
checks:

1. PR-55 Action shadow is valid and remains private GET/read-only;
2. response SHA-256 matches both the query and PR-54 eligibility evidence;
3. Action candidate SHA-256 matches the query;
4. masked account matches the response;
5. requested and final options match exactly;
6. intent fingerprint matches exactly;
7. instrument count, order and identifiers match exactly;
8. canonical query size and instrument count remain within policy;
9. reviewed response is fresh and not future-dated beyond tolerance;
10. request body is absent;
11. credential fields are absent;
12. execution fields are absent;
13. mutation fields are absent;
14. transfer and withdrawal fields are absent.

Every failed check becomes a deterministic blocker. The first failed check is
the primary blocker.

## Default policy

The default input policy uses:

- maximum canonical query size: 8,192 UTF-8 bytes;
- maximum instruments: 100;
- maximum response age: 900 seconds;
- future-clock tolerance: 60 seconds;
- an exact allowlist of eight query parameters.

The policy is conservative and can only be changed by constructing a separate
validated policy object. It is not a user risk preference.

## Deterministic identities

The binder serializes query, response and Action candidate as sorted compact
JSON and records SHA-256 digests.

These digests are audit identities. They are not secrets, order identifiers,
confirmation tokens or execution idempotency keys.

## Fail-closed behavior

A mismatch in account, option, fingerprint, instruments, response identity,
Action candidate identity, freshness or bounds produces:

- `status=blocked`;
- `input_valid=false`;
- one or more explicit blockers;
- no route or OpenAPI change;
- no public Action;
- no request body;
- no trade authorization;
- no order creation;
- `execution_ready=false`;
- `trading_methods=false`.

## Security boundary

The query contract cannot accept arbitrary extra fields. In particular, API
keys, access tokens, authorization values, passwords, order controls, execution
controls, transfer controls and withdrawal controls are outside the schema and
are rejected.

The package stores the validated source response and Action shadow only inside
the internal binding result. They are not exposed as a public response.

## Tests

Focused tests cover:

- exact valid binding;
- masked-account substitution;
- requested-option substitution;
- intent-fingerprint substitution;
- response-digest substitution;
- Action-candidate-digest substitution;
- instrument-order substitution;
- blocked PR-55 shadow;
- stale and future-dated responses;
- instrument-policy bounds;
- extra credential fields and request-body attempts;
- deterministic digests;
- result tampering;
- naïve validation timestamps.

## Next boundary

A valid input binding is only evidence for a later production route review. It
does not create the route and does not approve deployment.

The next package must compose PR-53 response, PR-54 eligibility, PR-55 OpenAPI
shadow and this input binding into a single production-route readiness dossier,
still without enabling the route automatically.
