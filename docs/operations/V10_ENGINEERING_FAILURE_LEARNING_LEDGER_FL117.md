# V10 Engineering Failure Learning Ledger — FL117

## Failure class

`CF_D_DIRECT_RESPONSE_MEDIA_TYPE_OVERAUTHORITY`

## Exact-main evidence

After PR #480 was accepted, exact main `1958a5fac22ef33c7e5e05d94f07d83e93b050fc` completed the required post-merge push gate and exact-main staging Worker + Container rehearsal. Automatic production release run `34480708867` then reached the one-time production database bootstrap and stopped fail-closed with:

`CLOUDFLARE_CF_D_NEON_FUNCTION_RESPONSE_INVALID`

Production promotion, Custom Domain mutation and live production acceptance were not attempted. Cleanup/quarantine completed successfully.

The bounded failure code alone does not prove which response shape was observed. Source inspection shows that the same code could be produced by a preflight response media-type rejection, a privileged `200` response media-type rejection, or a privileged `200` body that is not a JSON object. No provider body, response header value, Function URL, branch/project identifier, OIDC token, database credential or request identifier is inferred or recorded.

## Root cause and adjacent failure review

The direct bootstrap transport treated the HTTP `Content-Type` response header as a hard authority signal before consuming the already-bounded response body. On the credential-free preflight, that ordering could collapse an otherwise classifiable provider HTTP status into the generic response-invalid code before `_direct_failure_code()` had a chance to preserve the bounded status taxonomy. On a successful privileged response, the same header gate duplicated the stronger validation that already follows: bounded body read, strict JSON-object parse, exact `READY` status, exact runtime role, exact source SHA and constrained Neon PostgreSQL DSN validation.

`Content-Type` is useful representation metadata, but it is not authentication, source provenance or execution authority. The source-controlled preflight contract is stronger: exact HTTP status plus exact allowlisted JSON body shape/code. The privileged success contract is also stronger: HTTP 200 plus bounded strict JSON and exact runtime payload validation. Making the media-type header independently blocking created a false-negative path without adding an authority boundary.

The adjacent redirect path also read the response body before returning its dedicated redirect failure class. Redirect rejection is status-authoritative and does not require consuming an untrusted response body.

Blast radius is limited to the CF-D direct production database bootstrap HTTP client. Staging product traffic, Cloudflare Workers Builds, protected V9 `app:app`, broker authority, public multi-user activation and Real execution are unchanged.

## Correction

The direct bootstrap client now makes response authority content-driven while remaining bounded and fail-closed:

- credential-free preflight rejects redirects immediately without consuming their body;
- every non-redirect preflight response is read only up to the existing bounded failure limit and classified by exact status + exact allowlisted body taxonomy;
- preflight succeeds only for the source-controlled `405` / `METHOD_NOT_ALLOWED` contract, independent of mutable response media-type metadata;
- unknown/provider bodies retain only the existing bounded HTTP status class and cannot mint GitHub OIDC;
- privileged non-200 redirects are rejected before body consumption; other non-200 responses retain the existing bounded classifier;
- privileged HTTP 200 responses are bounded and parsed as strict JSON objects, then continue through the existing exact runtime payload validator without a separate response media-type gate;
- request `Accept`, request `Content-Type`, fixed User-Agent, exact target validation, TLS hostname/certificate verification, no-proxy/no-redirect policy, OIDC ordering and exact-SHA authority are unchanged.

## Permanent regression / guard

Deterministic tests prove that:

1. the exact source-controlled preflight status/body contract is accepted even when response media-type metadata is different;
2. an untrusted 403 remains `CLOUDFLARE_CF_D_DIRECT_HTTP_403_UNCLASSIFIED` before OIDC mint;
3. a non-source-controlled 405 body cannot satisfy provenance;
4. oversized preflight responses remain blocked;
5. redirects are rejected without consuming their body;
6. a bounded HTTP 200 JSON object is parsed independently of response media-type metadata while the request-side JSON/OIDC headers remain exact.

## Prevention law

1. Representation metadata must not outrank a stricter authenticated or exact source-controlled response contract.
2. Provider HTTP status taxonomy must be preserved before generic payload-invalid classification whenever the response is already safely bounded.
3. Credential-free provenance must be proven by exact allowlisted status/body semantics before privileged credentials are minted.
4. Redirect rejection must remain status-authoritative and must not require reading an untrusted redirect body.
5. A live bounded code that can originate from multiple source branches must not be assigned a more specific provider cause without additional evidence.

## Protected invariants

Unchanged: protected V9 `app:app`; `PUBLIC_MULTI_USER_ENABLED=false`; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; broker write, transfer, withdrawal, margin, leverage and uncovered short remain OFF/FORBIDDEN; PostgreSQL 18 + RLS/FORCE RLS remains relational truth; no D1/Hyperdrive/Web Visual/Telegram/AI/Cortex scope; no real credential/provider identifier/private payload is written to source, logs or artifacts.
