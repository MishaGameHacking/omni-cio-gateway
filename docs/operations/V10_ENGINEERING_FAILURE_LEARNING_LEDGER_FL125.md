# V10 Engineering Failure Learning Ledger — FL125

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `MAIN_RED_STOP`
- Failure class: `CF_D_FUNCTION_PROVENANCE_ROOT_REQUEST_OVERDISCRIMINATED`
- Scope: exact-source provenance ingress and the directly coupled pre-OIDC Function preflight only

## Observed failure

Exact accepted `main` `23e3f7adb7e146f18dbd9531bf2fa75553765644` reached the CF-D staging rehearsal in Production Release #46 after the exact-SHA build, single-version staging deployment, pre-custody release proof and bootstrap-origin custody had all succeeded. The candidate then treated the already-converged Function source as stale and entered the write-required recovery path. The least-privilege Neon management credential correctly rejected that write with `CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_API_KEY_INSUFFICIENT status=403`, so production promotion did not run.

The provider bundle had already been rebuilt from the exact accepted-main wrapper and handler and confirmed as one active/current completed deployment before a same-SHA rerun reproduced the same failure. Therefore stale source and propagation are not sufficient explanations for this checkpoint.

No Function URL, provider identifier, credential, OIDC token, database secret or private payload is recorded here.

## Root cause

The source-provenance wrapper required more request metadata than its security purpose needs. The canonical bootstrap handler accepts only `POST`; every `GET` is otherwise rejected. Provenance nevertheless depended on an exact query, a project header or a fixed User-Agent in addition to `GET /`.

Live release evidence proved those additional discriminators are not reliable end-to-end evidence. When they are absent or transformed, the wrapper delegates the request to the POST-only handler, the exact-source proof becomes false, and the release attempts a provider write that its intentionally least-privilege credential does not possess.

The defect is over-discrimination of a read-only proof route, not a reason to broaden Neon write authority, weaken digest equality, ignore the 403 or bypass staging/release gates.

## Permanent correction

- Reserve canonical `GET /` in the deployment wrapper for read-only exact-source provenance.
- Keep privileged bootstrap on canonical `POST /` and delegate every non-GET request to the existing handler unchanged.
- Remove query/header/User-Agent dependence from the wrapper's provenance decision; the existing deploy probe may carry compatibility metadata, but correctness no longer depends on it.
- Keep the provenance response bounded to `status=READY` plus the deterministic source SHA-256, with `cache-control: no-store` and `x-content-type-options: nosniff`.
- Extend the pre-OIDC direct Function preflight so the new bounded provenance response is accepted as source-controlled ingress evidence while retaining the previous exact `405 METHOD_NOT_ALLOWED` response as a compatibility fallback during rollout.
- Reject malformed `200` provenance bodies fail-closed.
- Preserve TLS hostname/certificate verification, no-redirect behavior, response-size limits, deterministic digest equality, active/current deployment identity, deployment-race checks and least-privilege provider write boundaries.

## Blast radius and adjacent review

Direct consumers of the provenance query/header constants, the wrapper, the deploy probe and both direct preflight tests were inspected. The canonical handler contains no legitimate GET route to shadow. The second POST preflight with a synthetic invalid OIDC token and the real POST bootstrap remain unchanged, so OIDC authority is not widened.

No database schema, PostgreSQL role/grant/RLS policy, Worker routing, product authentication, tenant selection, V9 recovery, broker or Real-money authority changes are introduced.

## Permanent regression / guard

Deterministic tests require:

- all canonical root GET requests to resolve to the bounded read-only provenance response in the wrapper;
- the POST-only bootstrap handler to remain unchanged;
- the direct pre-OIDC Function preflight to accept a valid bounded provenance response;
- malformed provenance to fail closed;
- the deploy probe to retain exact SHA-256 validation and the canonical root path;
- no custom provenance subpath.

The full exact-head CI, Sonar, SAST, secret scan and review gates remain unchanged.

## Prevention law

When a privileged handler structurally owns only one HTTP method, prefer an unused standard method on the same canonical path for bounded read-only control-plane proof instead of requiring extra query/header/User-Agent discriminators. Add request metadata only when it carries independent security authority; do not make correctness depend on metadata that is not itself an authority boundary.

## Protected invariants

Unchanged: protected V9 `app:app`; `PUBLIC_MULTI_USER_ENABLED=false`; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; broker write, transfer, withdrawal, margin, leverage and uncovered short remain OFF/FORBIDDEN; PostgreSQL 18 + RLS/FORCE RLS remains relational truth; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
