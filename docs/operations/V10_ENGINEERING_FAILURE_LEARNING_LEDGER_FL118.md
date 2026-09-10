# V10 Engineering Failure Learning Ledger — FL118

## Failure class

`CF_D_DIRECT_NEON_FUNCTION_AUTHORIZATION_FRONTDOOR_403`

## Exact-main evidence

After PR #481 was accepted, exact main `2130d65e306781884ee288ddb53b2cc5e80b83ea` completed all 11 required post-merge push workflows, including Regression Shield, and passed the exact-main Cloudflare staging Worker + Container rehearsal. Automatic production release then reached the one-time production database bootstrap and stopped fail-closed with `CLOUDFLARE_CF_D_DIRECT_HTTP_403_UNCLASSIFIED` before production promotion.

The credential-free `GET /` provenance preflight on the exact same Neon Function hostname, TLS policy and fixed User-Agent succeeded with the exact source-controlled `405 / METHOD_NOT_ALLOWED` contract. The subsequent privileged `POST /` carrying GitHub OIDC in the standard `Authorization` header returned an unclassified `403`.

The Function failure taxonomy test proves that every source-controlled `403` emitted by the accepted handler is an exact allowlisted `OIDC_*` JSON response and is classifiable. The observed response was not classifiable. Function telemetry for the failure window contained no handler invocation. The evidence therefore places the rejection ahead of source-controlled JWT validation, while not claiming an undocumented provider implementation reason.

No provider response body, Function URL, branch/project identifier, OIDC token, database credential or request identifier is recorded here.

## Root cause and adjacent failure review

The direct bootstrap path placed privileged GitHub workflow identity in the public standard `Authorization` namespace even though the project already uses a dedicated `X-Omni-GitHub-OIDC` ingress namespace at its trusted staging boundary. This created an avoidable coupling between provider-front-door handling of the standard authorization header and application-level OIDC verification.

A credential-free GET proved hostname and handler provenance but did not prove that the exact privileged POST method/body/header namespace could traverse the provider front door. Therefore a provider-side rejection specific to the privileged request shape remained discoverable only after a real OIDC token had been minted.

The correction does not assert that Neon Functions universally reject `Authorization`; current Neon guidance supports application handlers receiving bearer authorization. The fix is instead a project-specific namespace isolation that removes the proven failing request difference while preserving cryptographic authority at the handler.

Blast radius is bounded to the CF-D one-time production database bootstrap ingress. Protected V9 `app:app`, staging product traffic, normal PostgreSQL access, Cloudflare release authority, broker boundaries and Real execution remain unchanged.

## Correction

- Direct GitHub OIDC transport now uses the dedicated `X-Omni-GitHub-OIDC` header and sends no standard `Authorization` header.
- The Neon Function accepts that dedicated header, rejects simultaneous dedicated and standard authorization ingress, and still fully verifies the GitHub JWT signature and exact claims before any database mutation.
- The legacy staging relay's bearer `Authorization` form remains temporarily accepted until direct live proof, preserving the bounded recovery path.
- A second non-credentialed provenance check performs the exact `POST /` shape with a fixed synthetic non-JWT value in the dedicated header and valid bounded JSON body. It must receive the exact source-controlled `403 / OIDC_TOKEN_INVALID` result.
- Real GitHub OIDC is minted only after both the anonymous handler preflight and the dedicated-ingress POST preflight succeed.
- TLS hostname/certificate verification, fixed target derivation, redirect rejection, response limits, exact-SHA validation and raw provider-body suppression are unchanged.

## Permanent regression / guard

Deterministic tests require the direct privileged request to omit `Authorization`, require the dedicated header, prove the synthetic dedicated-ingress preflight is non-credentialed and source-controlled, prove failed ingress provenance cannot mint GitHub OIDC, preserve legacy relay compatibility, and bind the behavior into the machine-readable Cloudflare release contract.

## Prevention law

1. Privileged workflow identity must use a project-owned ingress namespace when provider-front-door behavior is outside application authority and a dedicated namespace is available.
2. Moving a credential between HTTP header namespaces must never weaken cryptographic validation, exact claim validation, source-SHA binding or least-privilege database authority.
3. A privileged request shape should have a non-credentialed deterministic provenance probe when the handler can reject a synthetic value before mutation.
4. Standard `Authorization` support documented by a provider must not be converted into a universal provider-failure claim from one bounded incident; preserve only the evidence actually observed.
5. Legacy recovery compatibility may remain only while direct live proof is pending and must not become a competing permanent execution path.

## Protected invariants

Unchanged: protected V9 `app:app`; `PUBLIC_MULTI_USER_ENABLED=false`; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; broker write, transfer, withdrawal, margin, leverage and uncovered short remain OFF/FORBIDDEN; PostgreSQL 18 + RLS/FORCE RLS remains relational truth; no D1/Hyperdrive/Web Visual/Telegram/AI/Cortex scope; no real credential/provider identifier/private payload is written to source, logs or artifacts.
