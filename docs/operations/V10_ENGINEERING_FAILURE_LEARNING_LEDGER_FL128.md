# V10 Engineering Failure Learning Ledger — FL128

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `MAIN_RED_STOP`
- Failure class: `CF_D_NEON_LEGACY_READ_AUTHORITY_PRECEDES_PROJECT_SCOPED_CONVERGENCE`
- Scope: exact-main CF-D Neon Function source convergence and the directly coupled staging-runtime recovery credential binding

## Observed failure

Exact accepted `main` `ddc8a2397036b6c6c3104f291d58a571acf9c9e6` reached Production Release #48 after PR #490. The exact-main post-merge gate accepted 11 required push workflows. Cloudflare provider readiness, Workers Builds authority, delivery toolchain, Containers registry authority and provider control-plane dependency checks passed. The staging database secret and Worker anchor were reused, stale staging build activity was quarantined, the exact-SHA gated build completed, the staging Worker reached one exact active version, the exact release probe passed, and bootstrap-origin custody completed.

The staging-rehearsal step then stopped with the sanitized result:

`CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_API_KEY_INSUFFICIENT status=403`

The fresh job contained the newly provisioned project-scoped Function deployment credential in masked form. Production promotion, custom-domain mutation and live acceptance did not execute. Cleanup/quarantine completed successfully.

No API key value, Function URL, account identifier, database credential, OIDC token or private payload is recorded here.

## Root cause

PR #490 correctly separated the Function deployment credential from the earlier least-privilege Neon credential, but the implementation still loaded the legacy `NEON_API_KEY` and performed project/branch/Function management reads before exact-source provenance and before the new project-scoped credential was loaded.

The failure code proves the request failed in the read-side management path: a deployment `POST` rejection would have emitted the distinct `WRITE_API_KEY_INSUFFICIENT` classifier. The old credential therefore remained a mandatory predecessor even though its exact-project 403 behavior was already known from the earlier CF-D authority incident.

A read-only provider cross-check confirmed that the canonical Frankfurt PostgreSQL 18 project, its default branch and `cfdprodbootstrap` Function remained present and healthy. The active Function deployment remained the pre-convergence deployment. This excludes missing provider resources as the cause.

The same legacy credential was also bound to the staging-runtime recovery fallback in the production release. The current run reused the staging database secret, so that adjacent path did not execute; however, a future missing-secret recovery would deterministically re-enter the same known-bad authority contour.

## Permanent correction

- Make canonical Function source provenance the first source-convergence decision. Exact source reuse is credential-free and returns before any Neon Management API credential is loaded.
- On proven source drift only, load the existing project-scoped `NEON_FUNCTION_DEPLOY_API_KEY` and use that one bounded project credential for exact project metadata when available, exact default-branch proof, Function state proof, deployment creation, deployment polling and final active/current deployment verification.
- Recheck source provenance immediately before the non-idempotent deployment `POST`. If another bounded actor already converged the exact source, accept only when the previously observed active deployment identity remains stable.
- Preserve deterministic wrapper+handler digest, TLS hostname/certificate verification, no redirects, bounded responses, deployment identity/race checks and exact active/current completed state.
- Keep project metadata lookup fail-closed where it returns a usable response, while allowing endpoint-specific 403/404 deferral only because exact branch + Function binding proof remains mandatory for project-scoped credentials.
- In the exact-main production release staging-recovery contour, bind the legacy `NEON_API_KEY` environment name to the same project-scoped release credential so the existing staging provisioner and diagnostics do not depend on the known-bad legacy repository secret. The legacy repository secret itself is not changed or deleted because historical/other accepted contours may still reference it.
- Keep direct production database bootstrap on GitHub OIDC to the Neon Function; no static Neon management credential is introduced into that production bootstrap step.
- Preserve FL127 as historical evidence. This entry supersedes only its disproven assumption that the legacy read credential can remain the mandatory Function-state authority.

## Blast radius and adjacent review

Directly coupled surfaces reviewed:

- `.github/workflows/v10-cloudflare-production-release.yml`;
- `scripts/deploy_v10_cloudflare_neon_bootstrap_function.py`;
- `scripts/run_v10_cloudflare_gated_candidate.py`;
- `scripts/provision_v10_cloudflare_neon_runtime.py`;
- `docs/architecture/V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json`;
- Function deployment, provenance, Neon authority and staging-secret recovery tests;
- the exact-main rollback, production-build, custom-domain and live-acceptance steps downstream of the failed staging rehearsal.

The staging provisioner already supports project-scoped branch authority. The focused repair therefore changes the production-release credential binding rather than duplicating or weakening its SQL/runtime-role/RLS logic.

No evidence from run #48 proves an independent defect in production Worker promotion, rollback snapshot, exact-current-main recheck, Custom Domain attachment or live release acceptance. Those gates remain unchanged and must execute after this repair passes its own exact-main staging boundary.

## Permanent regression / guard

Deterministic coverage requires:

- exact-source reuse to perform zero Management API credential reads and zero Function management calls;
- source drift to load the project-scoped credential only after provenance proves drift;
- exact project/branch/Function state, deployment `POST`, polling and final identity verification to use the same bounded project-scoped credential;
- a second provenance check immediately before deployment mutation;
- a concurrent source convergence with changed deployment identity to fail as a race;
- missing project-scoped authority on real drift to fail closed;
- 403 on the bounded project management transaction to classify as insufficient project authority without provider-body reflection;
- the legacy Function read binding to remain metadata-only/inactive in the release contract;
- the production staging-recovery `NEON_API_KEY` environment alias to resolve from the project-scoped release secret;
- the direct production database bootstrap section to remain free of static Neon management credentials;
- full exact-head CI, security, Sonar/review and exact-main post-merge certification to remain mandatory.

## Prevention law

When a provider credential is known to be unable to perform an exact-project operation, a new capable credential must not be placed *after* the failing credential in the mandatory control flow. First prove whether mutation is needed without credentials where possible; then acquire the narrowest credential that owns the exact project transaction and use it consistently for that bounded transaction. Historical credential names are not authority boundaries.

## Protected invariants

Unchanged: protected V9 `app:app`; `PUBLIC_MULTI_USER_ENABLED=false`; PostgreSQL 18 + RLS/FORCE RLS; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; broker write, transfer, withdrawal, margin, leverage and uncovered short remain OFF/FORBIDDEN; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
