# V10 Engineering Failure Learning Ledger — FL135

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `MAIN_RED_STOP`
- Failure class: `CF_D_PROJECT_SCOPED_AUTHORITY_BLOCKED_BY_BROAD_BRANCH_COLLECTION_READ`
- Scope: exact-main Neon Function source/invocation preparation inside the CF-D staging rehearsal

## Observed failure

Exact accepted `main` `51febc17dd5b083f71e0c5560de358467aebe877` completed all 11 required exact-main push workflows with terminal `success`, including Regression Shield and V10 Engineering Governance. Automatic `V10 Cloudflare Production Release` #50 / run `34707134608` then passed Cloudflare provider readiness, Workers Builds authority, Containers registry authority, pinned delivery toolchain installation, hashed control-plane dependency installation, staging database-secret reuse, staging Worker-anchor reuse, stale-build quarantine, exact-SHA staging build, exact single-version deployment, exact release probe and bootstrap-origin custody.

The release then emitted:

`CLOUDFLARE_CF_D_NEON_FUNCTION_PROJECT_METADATA=DEFERRED`

and stopped fail-closed with:

`CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_PROJECT_API_KEY_INSUFFICIENT status=403`

Production promotion, Custom Domain mutation and live acceptance did not execute. Cleanup/quarantine completed successfully.

No API key value, Function URL, project/branch identifier, database credential, OIDC token or private payload is recorded here.

## Root cause

The accepted invocation-credential repair correctly classified the unauthenticated Neon Function ingress 403 and then acquired the bounded `NEON_FUNCTION_DEPLOY_API_KEY` management authority before minting a branch-scoped `functions:invoke` credential.

However, the next control-plane proof still used a broad collection request:

`GET /api/v2/projects/{project_id}/branches?limit=100`

That collection read was not required for correctness because bootstrap-origin custody already supplied the exact branch id in the restricted runner-temp target descriptor. The live 403 therefore occurred before the new invocation-credential helper was reached.

Current Neon API reference exposes the narrower idempotent exact-resource endpoint:

`GET /api/v2/projects/{project_id}/branches/{branch_id}`

The exact response can prove the custodied branch identity, default designation and ready state without enumerating the project branch collection. This is a least-privilege control-flow defect, not evidence that the canonical project, branch or Function is missing.

## Permanent correction

- Replace the broad branch collection read in the Function convergence path with the exact branch resource request derived from the already validated custody descriptor.
- Preserve strict branch-id validation before constructing the provider path.
- Accept only the custodied branch id, `default=true` and `current_state=ready`; when provider `project_id` is present it must match the configured project exactly.
- Keep project metadata 403/404 deferral bounded to the existing endpoint-specific rule; do not reinterpret a provider 403 as success.
- Keep exact Function binding, active/current completed deployment equality, deterministic source digest, TLS hostname/certificate verification, no redirects and bounded responses unchanged.
- Keep the ephemeral `functions:invoke` credential issuance/revocation and authenticated provenance retry unchanged and downstream of exact branch/Function proof.
- Do not broaden to organization-wide/admin authority merely to make the release green.

## Blast radius and adjacent review

Directly coupled surfaces reviewed:

- `scripts/deploy_v10_cloudflare_neon_bootstrap_function.py`;
- `scripts/neon_function_invocation_credential.py`;
- `scripts/run_v10_cloudflare_gated_candidate.py`;
- `.github/workflows/v10-cloudflare-production-release.yml`;
- Function source/provenance/deployment regressions;
- current Neon exact-branch and Function API contracts.

The staging-runtime bootstrap fallback also contains a branch-collection discovery path, but that path was not executed in run #50 because the staging database secret was reused. It has a different pre-custody information boundary: before the candidate build it does not yet possess the bootstrap-origin branch descriptor. It is therefore not rewritten speculatively inside this focused repair. If a future missing-staging-secret recovery proves the same live authority failure, it remains fail-closed and requires its own exact evidence/authority solution rather than importing a hidden branch identifier.

## Permanent regression / guard

Deterministic coverage requires:

- the Function convergence source to contain no `/branches?limit=100` collection read;
- exact branch proof to call `/projects/{project_id}/branches/{branch_id}` using the custodied branch id;
- provider project-id mismatch, non-default branch and non-ready branch state to fail closed;
- the pre-existing compatibility test for exact default branch identity to remain passing;
- all existing Function provenance, invocation-credential lifecycle, deployment-race, OIDC and cleanup tests to remain unchanged and passing;
- full exact-head lint/type/tests/security/Sonar/review certification before merge;
- fresh exact-main post-merge workflows and a new automatic Production Release before acceptance.

## Prevention law

When an exact provider resource identifier has already crossed a validated custody boundary, downstream authorization checks must prefer the exact idempotent resource endpoint over collection enumeration. Do not require broader collection-read authority merely to rediscover an identifier already held under stronger provenance. Exact-resource narrowing must still validate the returned identity/state and must never convert authorization failures into success.

## Protected invariants

Unchanged: protected V9 `app:app`; `PUBLIC_MULTI_USER_ENABLED=false`; PostgreSQL 18 + RLS/FORCE RLS; broker write OFF; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; transfer/withdrawal/margin/leverage/uncovered-short remain OFF/FORBIDDEN; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
