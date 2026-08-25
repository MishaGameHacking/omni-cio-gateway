# FL-044 — Provider network endpoints must remain structurally fixed at the HTTP sink

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR WP22A PHASE 5; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-25**  
WP / PR / reference: **WP22A Phase 5 integrated technical closeout / PR #391 / repeated Sonar Security Rating B follow-up**

## Symptom / failing gate

While PR #391 remained DRAFT, SonarQube Cloud posted another **Quality Gate failed** result with **Security Rating on New Code = B** and project requirement **A**. The PR decoration was created while `e843d331fe16a5da6597cca7f8f41a61c8ca7c0a` was the unchanged current head, but the available GitHub connector does not expose a Sonar check-run/status object carrying the analyzed Git SHA. Therefore this entry does not claim private issue text or an exact Sonar rule annotation that cannot be retrieved.

The immediately preceding source correction had already made the VK token exchange sink structurally fixed to `VK_ID_TOKEN_ENDPOINT`. Blast-radius review then found the same broader failure class still present in the Telegram adapter: a generic `_bounded_json_response(..., method, url, ...)` helper passed an abstract `url` directly to `httpx.Client.stream(...)` even though all current callers supplied fixed Telegram constants.

## Root-cause analysis

Runtime intent and static trust structure were not identical.

At runtime, Telegram token and JWKS calls were already intended to use only:

- `TELEGRAM_OIDC_TOKEN_ENDPOINT`;
- `TELEGRAM_OIDC_JWKS_ENDPOINT`.

However, the HTTP sink itself accepted arbitrary `method` and `url` parameters. A reviewer or conservative security analyzer therefore had to prove every caller and every future caller before concluding that callback/provider-controlled data could never select a network destination.

The same class had already appeared in VK, where callback-derived values were moved out of URL construction and into encoded request parameters while the network sink was fixed. Leaving the analogous generic Telegram sink would make provider endpoint authority inconsistent across the two allowed human-login protocols.

## Blast radius searched

The review covered:

- every Phase-5 `httpx.Client.stream(...)` sink;
- Telegram token exchange and JWKS retrieval;
- the single-flight Telegram JWKS verifier;
- VK ID token exchange and its newly fixed endpoint regression;
- provider callback `code`, `state`, `device_id`, browser proof and stored redirect material;
- authorization redirects versus backend provider network calls;
- response-size/content-type/JSON validation and redirect-follow policy;
- provider timeout/error behavior;
- protected tenant, session, broker and public-production authority boundaries.

No user/provider value needs to select a Telegram backend network origin. Both backend destinations are protocol constants.

## Corrective change

The generic Telegram network helper is removed from the HTTP sink boundary.

The shared helper now only parses an already-obtained `httpx.Response` with bounded size/content-type/JSON rules. Two network operations own their destinations explicitly:

1. `_bounded_token_response(...)` performs only `POST TELEGRAM_OIDC_TOKEN_ENDPOINT`;
2. `_bounded_jwks_response(...)` performs only `GET TELEGRAM_OIDC_JWKS_ENDPOINT`.

Neither operation accepts a URL or HTTP method argument. Callback authorization code and the server-stored redirect URI remain ordinary form-body data for the fixed token endpoint. The single-flight verifier reuses the fixed JWKS operation, so random `kid` values can influence key selection/retry policy but can never influence the request origin/path.

Response limits, TLS verification, `follow_redirects=False`, Basic client authentication, nonce/signature checks and existing fail-closed error semantics remain unchanged.

## Permanent regression / guard

Deterministic tests now prove:

- a hostile-but-shape-valid Telegram authorization code containing URL-like delimiter material is encoded in the token request body and cannot rewrite scheme/host/path;
- the token request method is exactly POST and destination is exactly `TELEGRAM_OIDC_TOKEN_ENDPOINT`;
- the server-controlled callback URI remains form data, not network destination authority;
- JWKS retrieval method is exactly GET and destination is exactly `TELEGRAM_OIDC_JWKS_ENDPOINT` with no query component;
- the provider runtime still returns the verified external identity through the existing verifier boundary.

The existing VK fixed-endpoint regression remains in place. A new exact-head Sonar analysis is still required; this correction is not represented as proving the private Sonar finding text or as GREEN by itself.

## Future prevention rule

For outbound authentication/provider network calls:

1. protocol-owned origins and paths must be literal/fixed at or immediately adjacent to the HTTP sink;
2. callback/query/provider values may be encoded only as reviewed request fields, never concatenated into backend destination authority;
3. generic transport helpers should share response parsing, not arbitrary destination selection, when only a closed endpoint set is legitimate;
4. apply the rule symmetrically across all supported identity providers;
5. test hostile delimiter/URL-like callback values against the actual captured outbound request;
6. never suppress an SSRF/taint warning or weaken the security quality gate to obtain GREEN.

## Dependency/tooling knowledge change

No dependency update is required. The change uses the existing `httpx` client and existing Telegram protocol constants. Final acceptance remains delegated to exact-head deterministic CI plus the unchanged Sonar Security Rating A requirement.
