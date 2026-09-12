# V10 Engineering Failure Learning Ledger — FL132

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `RED_REPAIR_ONLY`
- Failure class: `CF_D_INVOKE_CREDENTIAL_CREATE_RESPONSE_SECRET_CUSTODY_GAP`
- Scope: final full-diff review of PR #496 after exact-head CI/Sonar success

## Discovery evidence

PR #496 exact head `a1e2822a17a59a7134e7c3d7f9f82921d0fe7292` reached terminal success on all applicable exact-head PR workflows, including the authoritative Self-Hosted Windows CI, V10 Engineering Governance and SonarQube Quality Gate with zero new issues and zero new Security Hotspots. The mandatory final full-diff review nevertheless found a provider-response custody gap in the newly introduced Neon Function invocation credential helper.

Current official Neon credential API/OpenAPI authority documents the branch credential issue endpoint as Beta and non-idempotent. Its `CreateCredentialResponse` carries two one-time sensitive values, `api_token` and `s3_secret_access_key`, and marks both sensitive. The response also defines the customer-supplied `name` as the label echoed from the request. The PR implementation masked only `api_token` and accepted a successful create response without proving that the returned label still matched the managed Omni-CIO namespace.

No real provider secret, credential identifier, Function URL, account identifier or private payload is recorded here.

## Root cause

The first credential-custody implementation reviewed request scope, returned API bearer token, branch binding and list/revoke reconciliation, but modeled the create response too narrowly. It treated the bearer token as the only generated secret relevant to process custody and relied on later managed-name list reconciliation after response-validation failure.

That left two adjacent failure modes:

1. Neon's second one-time generated secret could remain unmasked in process diagnostics custody even though the contract requires generated secret material to be masked immediately.
2. If a 201 response exposed a syntactically valid `token_id` but returned a missing or mutated label and another validation failed, namespace-based list cleanup could be unable to identify the just-created credential. The response itself already contained enough bounded authority to revoke that exact credential directly.

This is a final-review security completeness defect. It does not justify weakening CI, accepting a malformed provider response, broadening credential scopes or treating a 403 as success.

## Blast radius and adjacent review

The repair is bounded to the new branch-scoped `functions:invoke` credential lifecycle introduced by PR #496. Reviewed coupled surfaces are:

- `scripts/neon_function_invocation_credential.py` create-response parsing, secret masking, exact-label validation and failure cleanup;
- `tests/test_v10_neon_function_invocation_credential.py` deterministic create-response and cleanup regressions;
- the existing FL130 ambiguous-create/revoke custody law;
- the production bootstrap/deployer consumers, which continue to receive only the `api_token` and never receive or persist the S3 secret.

Protected V9, PostgreSQL/RLS, Cloudflare secret custody, GitHub OIDC, broker authority and Real-money boundaries are unchanged.

## Permanent correction

- Parse the successful create response into a bounded object and immediately mask every returned one-time secret field currently marked sensitive by Neon's OpenAPI: `api_token` and `s3_secret_access_key`.
- Require both generated secret fields to be bounded ASCII non-whitespace strings before accepting the response; discard the S3 secret after validation because CF-D does not use object-storage authority.
- Compute the managed credential name once before the non-idempotent POST and require the 201 response to echo that exact label.
- Preserve exact `functions:invoke` scope and exact branch validation; do not invent a `principal_type` requirement for the create response because current provider schema enforces `user` in the request while `CreateCredentialResponse` does not expose that field.
- If a malformed 201 response still contains a syntactically valid returned `token_id`, revoke that exact credential directly before propagating failure. The existing managed-namespace reconciliation remains as a second fail-closed cleanup layer.
- Never retry the non-idempotent create POST.

## Regression guard

Focused tests now require:

- both one-time generated secrets are masked on a valid create response;
- broader scopes, wrong branch and mutated managed label fail closed;
- a malformed 201 response masks both returned secrets before failure;
- a malformed 201 response with a valid token id performs exact credential revoke before namespace reconciliation;
- the create request remains exact `functions:invoke` + `user` and the returned S3 secret is never returned to bootstrap/deployer consumers.

## Prevention law

For every provider mutation that returns generated credentials, review the current provider response schema as part of the authority boundary, not only the request shape. Every response field marked secret/sensitive must enter masking custody immediately, and every returned stable resource identifier that can safely support an endpoint-specific idempotent cleanup must be used to close post-commit validation failures before broader reconciliation. Final manual Files changed review remains mandatory even after all automated gates are GREEN.

## Protected invariants

Unchanged: protected V9 `app:app`; `PUBLIC_MULTI_USER_ENABLED=false`; PostgreSQL 18 + RLS/FORCE RLS; broker write OFF; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; transfer/withdrawal/margin/leverage/uncovered-short remain OFF/FORBIDDEN; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
