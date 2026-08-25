# FL-042 — Session credential provenance must remain structurally visible at the cookie sink

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR WP22A PHASE 5; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-25**  
WP / PR / reference: **WP22A Phase 5 integrated technical closeout / PR #391 / SonarQube Cloud exact-head Quality Gate**

## Symptom / failing gate

After FL-041 split browser-session revocation from fresh session issuance, exact PR head `0301ee09` was independently re-analyzed by SonarQube Cloud. The result remained **Quality Gate failed** because **Security Rating on New Code = B**, while the accepted gate requires A.

This proved that the first authority refactor was insufficient. It improved the runtime abstraction, but it did not make fresh browser credential provenance explicit enough at the `Set-Cookie` sink.

The current GitHub connector exposes the Sonar check result and annotation count but cannot retrieve the private check-run annotation endpoint. No OWNER token, Sonar credential, rule suppression, quality-profile mutation or CI weakening was requested to work around that tooling limitation.

## Root-cause analysis

The deployed callback after FL-041 had the following shape:

`provider callback input -> verified identity -> ProductAccountScopeV1 -> issue_session(scope) -> returned token -> Set-Cookie`

The concrete `issue_session` implementation was safe: both process-local and PostgreSQL session registries created the token with Python `secrets.token_urlsafe`. However, the cookie-writing route saw only an abstract method whose input was provider-derived account scope and whose output was the session token.

For a taint/dataflow analyzer, the CSPRNG origin of that returned credential was hidden behind the abstraction. The fresh exact-head Sonar RED therefore demonstrated a broader reusable rule than FL-041: separating old-credential revocation is not enough when new-credential provenance is still opaque across the security sink boundary.

Official Sonar Python rule inventory classifies **"Applications should not create session cookies from untrusted input"** as a Vulnerability. The exact private annotation text is not asserted here; this entry records the repository evidence and the high-confidence dataflow class used to drive a security-improving fix, with final validation delegated to the unchanged Sonar Quality Gate.

## Blast radius searched

The follow-up review covered:

- the provider callback and every session `Set-Cookie` sink in the Phase-5 path;
- `ProductAuthenticationLike` and `ProductAuthenticationServiceV1`;
- `SessionIssuerLike`;
- `SessionRegistryV1` and `PostgresWebSessionRegistryV1`;
- session token hashing, resolve and revoke behavior for malformed browser candidates;
- existing session rotation and provider-route regressions;
- directly coupled hosted composition and recovery paths;
- protected V9, tenant authority and broker-write boundaries to confirm they remain unchanged.

Only the two session registry implementations mint browser session credentials. Both are changed through one common provenance contract while retaining their existing `create()` APIs for compatibility.

## Corrective change

Fresh token minting is now a named, input-free CSPRNG operation:

`new_session_token_v1() -> opaque token`

Session registries expose a separate `bind(...)` operation that accepts a pre-minted token and binds only its SHA-256 digest to a server-resolved user/tenant scope. Existing `create(...)` remains a compatibility wrapper implemented as:

`new_session_token_v1() -> bind(...)`

The deployed provider callback now performs:

`provider verify -> resolve product scope -> revoke old browser session -> CSPRNG mint -> bind token to resolved scope -> bind CSRF -> Set-Cookie`

The value written to the session cookie is therefore locally and structurally produced by an input-free CSPRNG call. Callback query parameters, provider claims, browser proof cookies and the old session cookie can affect whether authentication succeeds and which server-side scope is selected, but they cannot construct the new session credential.

`resolve()` and `revoke()` also fail closed for malformed token shapes instead of allowing the stricter token hash helper to raise through a browser-controlled path.

No Sonar suppression, `NOSONAR`, quality-profile change, rule exclusion, type escape or reduced CI gate is introduced.

## Permanent regression / guard

Deterministic tests prove that:

- provider callback order is `resolve -> revoke -> bind` around a locally minted credential;
- the new credential is URL-safe and the exact expected CSPRNG token length;
- it differs from the old session token, provider state/code and browser proof material;
- the exact token placed in the browser cookie is the token bound to the server-side account scope;
- direct registry binding rejects malformed token shapes and duplicate credential binding;
- bound sessions resolve to the expected user/tenant scope;
- plaintext session tokens are never retained by the process-local registry;
- legacy `create()` callers remain supported through the new mint-then-bind implementation.

The configured SonarQube Cloud Quality Gate remains the independent proof for the final browser credential dataflow. The branch is not GREEN until a fresh exact-head Sonar check concludes success with the required Security Rating.

## Future prevention rule

For session/authentication credential issuance:

1. generate browser credentials with a named input-free CSPRNG operation;
2. keep credential generation visible in or immediately adjacent to the cookie/credential sink;
3. bind generated credentials to server-resolved identity in a separate operation;
4. never derive the new credential value from provider claims, callback parameters, browser cookies, account IDs or tenant IDs;
5. retain backward-compatible high-level helpers only as wrappers over the same explicit mint-and-bind primitives;
6. treat repeated analyzer RED after an attempted refactor as evidence that the trust boundary is still too opaque, not as justification for suppression.

## Dependency/tooling knowledge change

No dependency update is required. The fix uses the existing Python `secrets` CSPRNG and existing session persistence. SonarQube Cloud and its Security Rating A requirement remain unchanged.
