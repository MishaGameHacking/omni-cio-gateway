# V10 Engineering Failure Learning Ledger — FL120

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `MAIN_RED_STOP`
- Failure class: `CF_D_NEON_FUNCTION_DEPLOY_CAPABILITY_AUTHORITY_MISMATCH`
- Scope: production database bootstrap Function source/runtime provenance only

## Observed failure

After PR #482 was squash-merged and exact-main post-merge Regression Shield plus all applicable push workflows succeeded, the gated production release reached exact-main candidate composition and failed closed while attempting to create a new deployment for the existing canonical Neon bootstrap Function.

Sanitized evidence:

- exact accepted main had passed the post-merge gate;
- Cloudflare credential, Workers Builds, delivery toolchain, registry, staging database reuse, exact-main staging build, pre-custody SHA and bootstrap-origin custody gates all passed;
- the Function deployment request returned HTTP `403`, classified as `CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_API_KEY_INSUFFICIENT`;
- all later production database, production Worker, Custom Domain, promotion and live-acceptance mutations were skipped;
- cleanup/quarantine succeeded and the production LKG remained protected.

No secret value, provider identifier, Function URL, OIDC token or database credential is recorded here.

## Root cause

The accepted release composition conflated two different provider capabilities:

1. read authority sufficient to prove the exact Neon project/default branch/existing Function binding;
2. Function deployment write authority required by `POST .../functions/{slug}/deployments`.

The release unconditionally attempted the write whenever the production runtime database secret was absent. That made every bootstrap attempt depend on Function deployment authority even when the deployed Function source could already be exact and reusable.

The problem is therefore not solved by weakening the provider gate, ignoring HTTP 403, broadening organization authority, or silently accepting an unknown Function runtime. The missing invariant was independently verifiable exact-source provenance for the already-deployed Function.

## Permanent correction

The Function bundle now carries a source-controlled provenance wrapper. The deployment archive is deterministic and binds both the wrapper template and canonical handler bytes into a SHA-256 digest. The rendered wrapper exposes only that embedded digest through a bounded no-secret `GET /__omni-cio/source-provenance` response and delegates all other requests to the canonical handler.

The release order becomes:

1. verify exact checkout and existing runtime-secret state;
2. derive the exact Function target from restricted custody;
3. build the deterministic expected Function bundle and digest;
4. use the existing least-privilege credential only for read-only project/default-branch/Function-state validation and require a completed `current == active` deployment snapshot;
5. perform a strict TLS/no-redirect/bounded public provenance probe;
6. if the exact digest is active, re-read the Function state and reuse it only when the same completed deployment identity is still current+active, without any Neon Management API write;
7. if the legacy handler or a different valid digest is active, classify source drift and require the existing least-privilege API credential to perform the Function deployment;
8. after any deployment, require current+active completed state and re-probe the exact digest before OIDC mint/bootstrap continues;
9. malformed provenance, redirects, oversized responses, transport failures, deployment races, API rejection or post-deploy digest mismatch remain fail-closed.

## Regression guard

`tests/test_v10_cloudflare_neon_function_deployment.py` verifies:

- deterministic two-file Function bundle construction;
- digest binding across wrapper template and handler;
- exact digest acceptance and legacy/different-source drift classification;
- malformed/untrusted provenance rejection;
- exact-source reuse performs stable read-state validation but no Function deployment write;
- exact-source reuse rejects a changed deployment identity across the provenance probe;
- explicit HTTP 403 Function-write authority classification;
- returned deployment identity/current-active race protection;
- runtime-secret reuse and candidate ordering;
- machine-readable release-contract semantics for conditional Function write authority.

## Reuse rule

Provider credential presence is not provider capability authority. A release must require the narrow capability only when the desired state actually needs that mutation. When immutable/exact runtime state can be independently proven, reuse it; when provenance is absent, malformed or stale, fail closed or require the explicitly authorized mutation. Exact-source reuse still requires bounded read-only state validation so provenance cannot be accepted across a concurrent Function deployment. Never widen provider authority merely to make CI or deployment GREEN.
