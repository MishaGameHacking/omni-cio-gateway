# V10 Engineering Failure Learning Ledger — FL114

## Failure class

`CF_D_DIRECT_NEON_FUNCTION_FRONTDOOR_403_BEFORE_HANDLER`

## Exact-main evidence

After PR #479 was accepted into `main`, exact main `256fd5e` completed the required post-merge push workflows and the Cloudflare staging Worker + Container rehearsal successfully. The production release then stopped at the one-time production database bootstrap with the bounded failure `CLOUDFLARE_CF_D_DIRECT_HTTP_403_UNCLASSIFIED` before any production promotion occurred.

The same exact accepted source was redeployed to the existing Neon Function through the connected provider control plane and the failed release job was rerun without changing GitHub source. The second attempt reached the same bounded `403` class at the same boundary. Neon Function telemetry for both failure windows contained no handler invocation. This rules out source drift and handler-level OIDC validation as the immediate failure location: the request is being rejected at the provider HTTPS front door before the source-controlled Function handler executes.

No provider response body, Function URL, branch/project identifier, OIDC token, database credential or request identifier is recorded here.

## Root-cause and adjacent defect review

The direct bootstrap client used an explicit TLS-verifying `http.client.HTTPSConnection` with a fixed host, port and `/` path, but sent no stable application `User-Agent` and had no non-credentialed provenance probe before minting the privileged GitHub OIDC token. Consequently, a provider-front-door rejection could only be observed after the privileged request had already been prepared, and the source-controlled handler could not be distinguished from an upstream provider edge by a positive preflight contract.

The provider-side reason for the `403` body is not claimed because the body is intentionally not reflected and Neon Function telemetry proves only that the handler was not invoked. The correction therefore addresses the proven architectural gap rather than guessing an undocumented provider rule.

Blast radius is bounded to the CF-D one-time production database bootstrap transport. Staging product traffic, Cloudflare Workers Builds, normal PostgreSQL runtime access, protected V9 `app:app`, broker authority and Real execution are unchanged.

## Correction

The direct bootstrap path now performs a credential-free Function provenance preflight before requesting GitHub OIDC:

- the client sends `GET /` to the already validated exact Function target over the same certificate-validating TLS connection policy;
- it supplies a fixed source-controlled `User-Agent` and `Accept: application/json` header, with no `Authorization` header and no request body;
- the preflight succeeds only when the source-controlled handler returns the exact allowlisted `405` / `METHOD_NOT_ALLOWED` failure contract;
- every other response remains fail-closed through the existing bounded provider classification and raw provider bodies remain unreflected;
- GitHub OIDC is minted only after that exact handler provenance preflight succeeds;
- the subsequent privileged `POST /` uses the same fixed `User-Agent` while preserving exact-SHA OIDC validation, TLS hostname verification, response bounds and redirect rejection.

## Permanent regression / guard

Deterministic tests require the exact preflight method/path/headers, prove that no OIDC token is minted when the provider edge returns the observed unclassified `403`, verify the privileged request header set, and bind the behavior into the machine-readable Cloudflare release-acceptance contract.

## Prevention law

1. A privileged provider Function call must establish credential-free handler provenance when a deterministic non-mutating source-controlled response is available.
2. Privileged credentials must not be minted or transmitted until that provenance check passes.
3. Direct control-plane HTTP clients must send a stable source-controlled client identity header when provider front-door policy can distinguish anonymous generic clients; the header is metadata only and never substitutes for authentication.
4. Provider-front-door failures without handler telemetry must not be misclassified as handler/OIDC defects. Preserve only bounded status taxonomy and fix proven transport/provenance gaps first.
5. Same-SHA reruns are allowed only after a concrete external-provider correction. Repeating the same failure after an unchanged-source provider redeploy requires a focused source repair rather than another retry.

## Protected invariants

Unchanged: protected V9 `app:app`; `PUBLIC_MULTI_USER_ENABLED=false`; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; broker write, transfer, withdrawal, margin, leverage and uncovered short remain OFF/FORBIDDEN; PostgreSQL 18 + RLS/FORCE RLS remains relational truth; no D1/Hyperdrive/Web Visual/Telegram/AI/Cortex scope; no real credential/provider identifier/private payload is written to source, logs or artifacts.
