# Final Decision-Review Release Eligibility V1

## Purpose

`FinalDecisionReviewReleaseEligibilityV1` is an internal, auditable decision
about whether the compact PR-53 response is structurally safe enough to enter a
separate future GET/read-only Action contract review.

It is not a route approval, deployment approval, trading authorization or
execution permission.

## Inputs

The assessor requires both:

- `FinalDecisionReviewResponseV1`;
- the completed `FinalDecisionReviewShadowValidationV1` for that exact response.

A response cannot become eligible when shadow validation is missing, mismatched,
future-substituted or carries any enabled execution flag.

## Canonical payload

The assessor serializes the response as deterministic sorted JSON, records the
UTF-8 byte size and calculates a SHA-256 digest. The digest is an audit identity,
not a secret and not an order idempotency key.

Default policy bounds are:

- schema name `final_decision_review_response`;
- schema version `1.0`;
- payload size at most 65,536 bytes;
- at most 100 exact intent rows;
- at most 50 sanitized provenance rows;
- future timestamp tolerance of 60 seconds;
- intended HTTP method exactly `GET`.

## Required checks

Every result contains one check for each of the following:

1. shadow parity;
2. schema name;
3. schema version;
4. account masking;
5. canonical payload size;
6. intent count and reconciliation;
7. provenance count and reconciliation;
8. provenance uniqueness and future-clock safety;
9. absence of sensitive fields;
10. absence of execution surface;
11. absence of mutation surface;
12. GET-only compatibility.

A failed check becomes a deterministic blocker. The first failed check is the
primary blocker.

## Sensitive-data boundary

The assessor blocks payloads that expose or declare:

- a full account identifier;
- broker account IDs;
- API keys, access tokens, authorization values, secrets or passwords;
- `source_id`;
- source binding contracts.

The allowed account reference must contain an explicit masking character.

## Execution and mutation boundary

Eligibility requires all response and shadow execution flags to remain false.
The canonical payload is also scanned for truthy mutation keys related to order
creation, submission, replacement, cancellation, transfer or withdrawal.

The result always keeps:

- `route_approval_granted=false`;
- `public_action_created=false`;
- `route_added=false`;
- `openapi_changed=false`;
- `source_values_recomputed=false`;
- `trade_authorized=false`;
- `order_created=false`;
- `execution_ready=false`;
- `trading_methods=false`.

## Eligibility semantics

`eligible=true` means only that the reviewed response and its matching shadow
result satisfy the internal contract checks for a future GET/read-only contract
review.

It does not mean that:

- a public route exists;
- OpenAPI may be changed automatically;
- a GPT Action is approved;
- a portfolio change is recommended;
- an order may be created;
- a trade, transfer or withdrawal may be executed.

Any public Action integration remains a separate package with its own explicit
contract, security review, tests, rollback and production acceptance.

## Tests

Focused tests cover:

- eligible GET/read-only assessment;
- POST rejection;
- shadow mismatch;
- schema-version substitution;
- unmasked account and enabled execution flag;
- payload and provenance count bounds;
- future-dated provenance;
- deterministic digest;
- result tampering;
- naïve timestamp rejection.
