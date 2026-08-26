# FL-041 — Security-analyzer dataflow must reflect the real session authority boundary

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR WP22A PHASE 5; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-25**  
WP / PR / reference: **WP22A Phase 5 integrated technical closeout / PR #391 / SonarQube Cloud exact-head Quality Gate**

## Symptom / failing gate

On exact PR head `85cc18e0`, SonarQube Cloud completed its PR analysis and returned **Quality Gate failed** because the **Security Rating on New Code was B**, while the project gate requires A. Semgrep and several deterministic V10 gates were already successful, but that does not override an applicable Sonar failure.

The GitHub check exposed the failed security rating and annotation count, but the current connector could not retrieve Sonar's private issue-level annotation text and the unauthenticated Sonar API could not disclose private-project findings. No OWNER token or Sonar secret was requested merely to bypass that limitation.

## Root-cause analysis

Focused review of new-code session/cookie dataflow identified one boundary where untrusted browser session material and the newly issued session token crossed the same abstract method call:

`authenticate_verified_identity(identity, current_session_token=request_cookie, ...) -> new_session_token`

The concrete implementation was fixation-safe: it resolved the verified provider identity to an internal product scope, revoked the old token, then generated a fresh opaque token with the server-side session registry. However, the route depended only on a Protocol whose input/output shape did not expose those separate authority steps. A taint/security analyzer can therefore conservatively model the returned token as derived from the untrusted browser cookie and report a session-cookie injection path even though the concrete implementation generates a new token independently.

This is both a static-analysis ambiguity and an architectural clarity problem: a security-critical abstraction should make the trusted minting boundary explicit rather than requiring reviewers/analyzers to infer hidden internals across a broad method.

## Blast radius searched

The review covered:

- every repository use of `authenticate_verified_identity`;
- the `ProductAuthenticationLike` route protocol;
- the concrete `ProductAuthenticationServiceV1` implementation;
- process-local and PostgreSQL-backed session issuers;
- provider callback routing and `Set-Cookie` writes;
- provider identity resolution and tenant binding;
- existing session rotation/fixation tests;
- adjacent open-redirect, SSRF, cookie, crypto, SQL and provider-network sinks in the Phase-5 diff.

The broad composite API is used by existing unit tests and remains safe as a compatibility wrapper. The deployed provider route is the security-sensitive browser boundary and is changed to use explicit authority steps.

## Corrective change

`ProductAuthenticationServiceV1` now exposes three explicit operations:

1. `resolve_verified_identity(...)` — verified provider identity -> server-resolved `ProductAccountScopeV1`; accepts no browser session token;
2. `revoke_session(...)` — consumes the untrusted current-session candidate and returns no new credential;
3. `issue_session(...)` — accepts only the server-resolved product scope and mints a fresh opaque server-side session.

The deployed provider callback performs them in that exact order:

`provider verify -> resolve product scope -> revoke old browser session -> issue fresh server session -> bind CSRF -> Set-Cookie`

The previous `authenticate_verified_identity(...)` remains as a compatibility wrapper that composes the same three operations, preserving existing behavior for non-route consumers without keeping the ambiguous browser-route dataflow.

No Sonar suppression, `NOSONAR`, quality-profile change, type escape, reduced rule set or CI weakening is introduced.

## Permanent regression / guard

Deterministic tests now prove:

- the route calls `resolve -> revoke -> issue` in order;
- the old browser token is passed only to revocation;
- fresh issuance receives only a `ProductAccountScopeV1`;
- concrete split flow leaves the old token live until explicit revoke, then invalidates it;
- the newly issued token differs from the old token and resolves to the same server-side user/tenant scope;
- plaintext session tokens remain absent from stored registry state.

The exact-head Sonar Quality Gate remains the independent proof that the browser-cookie taint boundary is acceptable to the configured security rules. A future GREEN claim requires Sonar success/A on the final unchanged head.

## Future prevention rule

For security-sensitive credential rotation APIs:

1. do not combine untrusted old-credential input and fresh-credential output in one broad abstraction when the boundary can be expressed as separate authority steps;
2. make trusted credential minting accept only server-resolved identity/scope, never raw browser credential input;
3. keep revocation as a sink-only operation;
4. preserve explicit operation order with deterministic tests;
5. treat a security-analyzer RED as a real merge blocker until either the code boundary is clarified/fixed or exact rule evidence proves the finding invalid;
6. never solve an analyzer RED by suppressing the rule or weakening the quality gate solely to obtain GREEN.

## Dependency/tooling knowledge change

No dependency update is required. The change is an application authority/dataflow refactor under the existing FastAPI/session/provider stack. The accepted SonarQube Cloud integration and its required Security Rating A remain unchanged.
