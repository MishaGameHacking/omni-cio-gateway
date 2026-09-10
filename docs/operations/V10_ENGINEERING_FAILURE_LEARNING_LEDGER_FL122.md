# V10 Engineering Failure Learning Ledger — FL122

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `MAIN_RED_STOP`
- Failure class: `CF_D_FUNCTION_PROVENANCE_NONCANONICAL_INGRESS`
- Scope: exact-source provenance transport for the production database bootstrap Function only

## Observed failure

After PR #484 was accepted and all applicable exact-main push/post-merge gates succeeded, the gated production release repeatedly reached the exact staging candidate, pre-custody release and bootstrap-origin custody boundaries, but still classified the production bootstrap Function source as stale and entered the write-required recovery path. The least-privilege Neon credential correctly rejected that write with the existing insufficient-authority classification.

A fresh exact-source Function deployment through the already-authorized provider control plane did not change the release result. During the failed release window, Function request telemetry contained no invocation corresponding to the provenance probe. Current provider documentation states that requests which reach a deployed Function emit invocation begin/end telemetry and documents the Function invocation URL itself as the public HTTP entrypoint.

No secret value, provider identifier, Function URL, OIDC token or database credential is recorded here.

## Root cause

The source-provenance contract placed the probe on a custom Function subpath while the bootstrap transport itself already used the canonical Function root ingress. Repeated live evidence showed the custom provenance request did not reach the Function runtime. Because the runtime never received that request, the release could not independently prove the active source digest and therefore safely treated the source as drifted.

This is an ingress-contract defect. It is not a reason to weaken digest equality, ignore the provider `403`, broaden Neon write authority, remove deployment-race checks or bypass exact-source proof.

## Permanent correction

Exact source provenance now uses the canonical Function root ingress with one explicit no-secret discriminator:

`GET /` with `X-Omni-Source-Provenance: v1`.

The provenance wrapper intercepts only that exact method/path/query/header tuple. Every other request delegates to the canonical bootstrap handler. Therefore the existing unauthenticated root `GET /` bootstrap preflight still reaches the handler and must return `METHOD_NOT_ALLOWED`, while the dedicated root `POST /` OIDC preflight and real bootstrap request remain unchanged.

The release probe keeps strict TLS hostname verification, TLS minimum version, no redirects, bounded response size, exact SHA-256 digest equality and current/active deployment identity race protection. Function deployment remains conditional on genuine source drift only.

## Regression guard

`tests/test_v10_cloudflare_neon_function_provenance_ingress.py` verifies:

- the release probe uses exact `GET /`;
- the no-secret provenance header name/value are fixed;
- the wrapper requires the exact root/method/empty-query/header tuple;
- non-provenance requests delegate to the canonical handler;
- the obsolete custom provenance subpath is absent from the wrapper;
- the machine-readable release-acceptance contract freezes canonical root ingress and forbids a custom provenance subpath.

The existing deterministic two-file bundle, source-digest, malformed-response, exact-source reuse, provider-write classification and deployment-race tests remain active.

## Reuse rule

Runtime provenance is meaningful only when the probe itself traverses a provider-supported invocation surface. If request routing is not independently demonstrated, a missing provenance response must fail closed, but the permanent repair is to use the canonical provider ingress rather than broadening mutation authority or weakening source identity.
