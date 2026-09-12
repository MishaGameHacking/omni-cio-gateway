# V10 Engineering Failure Learning Ledger — FL136

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `MAIN_RED_STOP`
- Failure class: `CF_D_AUTHENTICATED_SOURCE_REUSE_BLOCKED_BY_UNNECESSARY_METADATA_PROOFS`
- Scope: exact-main Neon Function source-reuse authority inside the CF-D staging rehearsal

## Observed failure

Exact accepted `main` `ff8a1a924913f3f83a6630da48f52ba168178934` completed the required exact-main push batch with terminal `success`, including Regression Shield. Automatic `V10 Cloudflare Production Release` #51 / run `34711859185` then passed the exact-main post-merge gate, Cloudflare provider readiness, Workers Builds authority, Containers registry authority, pinned delivery toolchain installation, hashed control-plane dependency installation, staging database-secret reuse, staging Worker-anchor reuse, stale-build quarantine, exact-SHA staging build, exact single-version deployment, exact release probe and bootstrap-origin custody.

The staging rehearsal then stopped fail-closed with:

`CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_PROJECT_API_KEY_INSUFFICIENT status=403`

The release had already emitted the bounded project-metadata deferral. Production promotion, Custom Domain mutation and live acceptance did not execute. Cleanup/quarantine completed successfully.

The canonical Neon Function remains present with one completed active/current Node.js 24 deployment. No API key value, Function URL, project/branch identifier, database credential, OIDC token or private payload is recorded here.

## Root cause

PR #498 correctly removed broad branch enumeration, but the authenticated exact-source reuse path still required project metadata, exact branch metadata and exact Function management reads **before** it could mint the short-lived branch-scoped `functions:invoke` credential required by Neon's current pre-handler ingress boundary.

That ordering is unnecessary for exact-source reuse. Bootstrap-origin custody already provides the validated target branch/cell descriptor from the exact staging release, while the protected project selector remains in secret custody. The only additional capability needed after the bounded unauthenticated Function 403 is an ephemeral branch-scoped `functions:invoke` credential, followed by the existing TLS-verified exact deterministic source-digest probe.

The generic `PROJECT_API_KEY_INSUFFICIENT` classifier is shared by the exact branch and exact Function reads, so run #51 does not safely identify which of those two metadata operations returned the final 403. That ambiguity does not change the correction: neither metadata read is required before an authenticated source-reuse proof. The accepted direct production bootstrap already uses the narrower pattern — acquire project invocation authority, mint the branch-scoped invoke credential from the custodied branch id, prove source-controlled Function ingress, and only then proceed.

Current Neon documentation states that a project-scoped API key is limited to one project while retaining mutation authority inside that project. The live 403 is therefore not a reason to broaden to organization-wide/admin authority or to reinterpret authorization failure as success. The release must instead ask for the narrow capability it actually needs at each stage.

## Permanent correction

- Add one bounded release adapter for exact-source reuse; it delegates all real source convergence to the existing hardened deployer and does not create a parallel deployment stack.
- Preserve the runtime-secret short circuit before any Neon Function authority is acquired.
- Preserve the first unauthenticated provenance request. A real exact-digest `200` remains credential-free reuse.
- Only when that probe returns the already-classified provider pre-handler `403`, load the existing project-scoped invocation authority and mint an ephemeral branch-scoped credential with exactly `functions:invoke`.
- Derive the branch solely from the validated bootstrap-origin custody descriptor and the project solely from protected project-selector custody. The invocation-credential helper continues to validate returned branch/scope/name, mask secret material, revoke after use and reconcile stale managed credentials.
- Require the authenticated provenance response to remain TLS-verified, redirect-free, bounded JSON with `status=READY` and the exact deterministic wrapper+handler digest. No 403 or malformed provider response becomes success.
- If authenticated provenance proves the exact source, return before project/branch/Function metadata reads and before any Function deployment mutation.
- If source drift is real, revoke the invocation credential and delegate to the existing source-convergence path unchanged. Exact project/branch/Function proof, deployment identity/race checks, active/current completed state and post-deploy provenance remain mandatory for mutation.
- Keep direct production database bootstrap, GitHub OIDC, PostgreSQL/RLS, production rollback and Custom Domain gates unchanged.

## Blast radius and adjacent review

Directly coupled surfaces reviewed:

- `scripts/run_v10_cloudflare_gated_candidate.py`;
- `scripts/deploy_v10_cloudflare_neon_bootstrap_function.py`;
- `scripts/neon_function_invocation_credential.py`;
- `scripts/bootstrap_v10_cloudflare_production_database_direct.py`;
- `.github/workflows/v10-cloudflare-production-release.yml`;
- Function deployment/provenance/invocation-credential tests;
- the CF-D release acceptance contract and downstream production/rollback/live-acceptance gates;
- current Neon project-scoped API-key and Function deployment/invocation documentation.

The direct production bootstrap already performs the same bounded invocation-credential fallback after a provider ingress 403, so the repair reuses an accepted repository authority pattern rather than inventing a second provider-authentication model.

No independent defect is proven in production Worker promotion, database bootstrap, Custom Domain attachment or live acceptance because run #51 stopped before those steps. They remain unchanged and must execute successfully after this repair reaches exact main.

## Permanent regression / guard

Deterministic coverage requires:

- runtime-secret readiness to suppress all Function source/deploy authority;
- unauthenticated exact-source reuse to stay credential-free;
- only the classified pre-handler provenance 403 to permit the scoped invocation fallback;
- authenticated exact-source reuse to mint `functions:invoke` directly from protected project custody plus the custodied branch id, without calling project metadata, exact branch metadata, Function metadata or Function deployment first;
- unexpected/malformed provenance failures to remain fail-closed and never mint fallback authority;
- authenticated source drift to revoke the invoke credential and delegate to the existing hardened convergence path rather than weakening its mutation checks;
- the exact-main candidate runner to use the source-reuse adapter while preserving the existing call position after bootstrap-origin custody;
- all existing source-digest, deployment-race, credential cleanup/revocation, GitHub-OIDC, rollback and release-contract tests to remain passing;
- full exact-head lint/type/tests/security/Sonar/review certification before merge;
- fresh exact-main post-merge workflows and a new automatic Production Release before #494 may close.

## Prevention law

A provider capability must not be preceded by unrelated read-authority proofs merely because they share the same credential. When validated custody already identifies the exact resource, request the narrow capability actually required for the next operation and prove the result directly. Metadata reads remain mandatory only where they protect a mutation or identity transition that depends on that metadata. A fail-closed release should narrow its authority sequence, never broaden credentials or treat authorization failures as success.

## Protected invariants

Unchanged: protected V9 `app:app`; `PUBLIC_MULTI_USER_ENABLED=false`; PostgreSQL 18 + RLS/FORCE RLS; broker write OFF; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; transfer/withdrawal/margin/leverage/uncovered-short remain OFF/FORBIDDEN; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
