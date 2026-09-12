# V10 Engineering Failure Learning Ledger — FL137

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `MAIN_RED_STOP`
- Failure class: `CF_D_PROJECT_SCOPED_MANAGEMENT_KEY_CANNOT_OWN_BRANCH_INVOKE_CREDENTIAL_LIFECYCLE`
- Scope: exact-main Neon Function ingress authority for source provenance and direct production bootstrap

## Observed failure

Exact accepted `main` `3842572f759d7e2d289b44023d23f4eb69b6645c` completed the complete required exact-main push batch with terminal `success`, including Regression Shield and V10 Engineering Governance. Automatic `V10 Cloudflare Production Release` #52 / run `34721127791` then passed the exact-main post-merge gate, Cloudflare provider readiness, Workers Builds authority, Containers registry authority, pinned delivery toolchain installation, hashed control-plane dependency installation, staging database-secret reuse, staging Worker-anchor reuse, stale-build quarantine, exact-SHA staging build, exact single-version staging deployment, exact release probe and bootstrap-origin custody.

The release then stopped fail-closed with:

`CLOUDFLARE_CF_D_NEON_FUNCTION_INVOKE_CREDENTIAL_PROJECT_API_KEY_INSUFFICIENT status=403`

Production database bootstrap, production promotion, Custom Domain mutation and live acceptance did not execute. Cleanup/quarantine completed successfully.

No API key value, Function invocation token, provider identifier, database credential, OIDC token, account identifier or private payload is recorded here.

## Root cause

PR #499 correctly moved authenticated exact-source proof ahead of unrelated project/branch/Function metadata reads. That correction exposed the next exact authority boundary: `scripts/neon_function_invocation_credential.py` attempted to list/create/revoke branch service credentials through the Neon Management API using `NEON_FUNCTION_DEPLOY_API_KEY` before returning a temporary `functions:invoke` token.

Live run #52 proves that the currently protected project-scoped management authority is insufficient for that branch credential-management transaction. The release therefore never reached authenticated Function provenance. This is not evidence that the exact Function source, default branch, Cloudflare staging candidate, PostgreSQL runtime or GitHub OIDC contract is invalid.

Provider state was rechecked without recording identifiers: the exact default branch remained ready, and no active release-managed `functions:invoke` credential remained. Current Neon API documentation exposes `functions:invoke` as a branch-scoped service-credential scope, while current project-scoped API-key guidance explicitly limits key-minting authority. Broadening the release management key to organization/admin authority only to manufacture an invocation credential would violate least privilege and is not an accepted repair.

## Permanent correction

- Separate Function invocation custody from Neon management authority.
- Pre-provision exactly one branch-scoped service credential with exactly `functions:invoke` for the canonical bootstrap Function boundary.
- Store only its secret value in GitHub Actions repository-secret custody as `NEON_FUNCTION_INVOKE_API_TOKEN`; never source-control, log, artifact, summarize or echo it.
- Load and mask that invocation secret only after the already-classified unauthenticated pre-handler `403` proves outer Function ingress authentication is required.
- Keep the first unauthenticated exact-source provenance attempt unchanged; a real exact-digest `200 READY` remains credential-free reuse.
- Keep authenticated provenance TLS-verified, redirect-free, bounded and exact-digest matched. A missing, malformed, revoked, wrong-branch, wrong-scope or provider-rejected invocation secret remains RED.
- Remove all branch credential list/create/revoke operations from the release helper. Release code must not gain organization/admin authority merely to mint another credential.
- Keep `NEON_FUNCTION_DEPLOY_API_KEY` as the bounded project-scoped management/deploy authority for genuine Function source drift/convergence only.
- Remove management/deploy authority from the direct production database-bootstrap workflow step; that step receives only Cloudflare authority, the invocation-only outer token and GitHub OIDC authority.
- Keep inner `X-Omni-GitHub-OIDC` mandatory and fully source-controlled. The outer invocation token only crosses Neon Function ingress; it never replaces GitHub OIDC application authorization.
- Rotate/revoke the pre-provisioned invocation credential through the provider/GitHub secret-custody procedure when required. Release execution itself performs no credential CRUD.

## Blast radius and adjacent review

Directly coupled surfaces reviewed:

- `scripts/neon_function_invocation_credential.py`;
- `scripts/reuse_v10_cloudflare_neon_bootstrap_function_source.py`;
- `scripts/deploy_v10_cloudflare_neon_bootstrap_function.py`;
- `scripts/bootstrap_v10_cloudflare_production_database_direct.py`;
- `.github/workflows/v10-cloudflare-production-release.yml`;
- `docs/architecture/V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json`;
- Function source/provenance/direct-bootstrap and workflow-custody regression tests;
- current Neon branch service-credential and project-scoped API-key behavior.

The existing call shape used by source-reuse/direct-bootstrap/deployer code is retained through a compatibility context manager, but it no longer loads or mutates management authority. Real Function source drift still enters the existing hardened deployer, which owns exact project/branch/Function identity, deployment-race and active/current completed-state checks.

No independent defect is proven in production Worker promotion, database bootstrap SQL/RLS logic, Custom Domain attachment or live release acceptance because run #52 stopped before those gates. They remain unchanged and must execute successfully after this repair is accepted.

## Permanent regression / guard

Deterministic coverage requires:

- invocation-secret loading to fail closed when missing or malformed and to mask the accepted secret immediately;
- the invocation helper source to contain no branch `/credentials` management API path and no create/revoke/cleanup lifecycle;
- the legacy project-authority adapter to load no management secret for exact-source reuse/direct bootstrap;
- staging candidate rehearsal to receive management/deploy authority and invocation authority as separate secret bindings;
- direct production database bootstrap to receive the invocation-only secret but no Neon management/deploy key or protected project selector;
- the release contract to require pre-provisioned exact-branch `functions:invoke` custody, forbid broader scopes and dynamic credential CRUD, and preserve rotation/revocation as an external custody operation;
- exact-source reuse without Management API access to remain allowed while genuine source drift still requires the project-scoped deploy key;
- all existing exact-digest, TLS, redirect, bounded-response, deployment-race, GitHub-OIDC, PostgreSQL/RLS, rollback and live-acceptance guards to remain intact;
- full exact-head CI, Sonar/security/review certification before merge and a fresh exact-main Production Release afterward.

## Prevention law

A credential that can mutate one provider resource is not automatically authorized to mint subordinate credentials. Do not solve a least-privilege authorization failure by widening a release key to organization/admin scope when a narrower pre-provisioned capability exists. Separate long-lived secret custody from runtime authority: persist the narrowest reusable capability in an approved secret store, expose it only to the exact step that needs it, and keep independent application authorization inside the invoked service.

## Protected invariants

Unchanged: protected V9 `app:app`; `PUBLIC_MULTI_USER_ENABLED=false`; PostgreSQL 18 + RLS/FORCE RLS; broker write OFF; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; transfer/withdrawal/margin/leverage/uncovered-short remain OFF/FORBIDDEN; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
