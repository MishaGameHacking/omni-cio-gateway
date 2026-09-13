# V10 Engineering Failure Learning Ledger — FL139

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `MAIN_RED_STOP`
- Failure class: `CF_D_NEON_RUNTIME_AND_FUNCTION_DEPLOY_CREDENTIAL_ROLE_CONFLATION`
- Scope: missing staging/production PostgreSQL runtime-secret recovery in the exact-main Cloudflare production release

## Observed failure

Exact accepted `main` `c3707b1a4a86f64e78f18cd38ed395ec453a329a` completed the required exact-main post-merge push batch. Automatic `V10 Cloudflare Production Release` run `34745365848` / run #54 then passed the exact-main gate, Cloudflare provider/Workers Builds/Containers authority, pinned delivery toolchain, isolated exact-SHA staging rehearsal, staging live acceptance, canonical-domain validation and the production Worker-anchor gate.

The production runtime-secret probe correctly reported that `OMNI_V10_POSTGRES_DSN` was missing and bootstrap was required. The next step stopped fail-closed with:

`CLOUDFLARE_NEON_RUNTIME=STOPPED code=NEON_PROJECT_KEY_BINDING_MISMATCH`

Production Workers Build promotion, Custom Domain mutation and canonical live acceptance did not execute. Cleanup/quarantine completed successfully.

No Neon API key, project/branch identifier, DSN, Cloudflare account identifier, database credential or private payload is recorded here.

## Root cause

PR #503 fixed a real adjacent defect by binding production runtime provisioning to the already-custodied exact Neon branch instead of unnecessarily enumerating the branch collection. Release #54 proves that exact-resource narrowing alone was not sufficient.

The active release workflow still maps the runtime provisioner's canonical `NEON_API_KEY` environment role to the unrelated `NEON_FUNCTION_DEPLOY_API_KEY` repository secret. The same alias is also present in the staging-recovery portion of the exact-main production-release workflow.

Those credentials have different authority roles:

- `NEON_API_KEY` is the accepted project-scoped database/runtime-management credential used by the candidate/provider workflows and by `scripts.provision_v10_cloudflare_neon_runtime.py`;
- `NEON_FUNCTION_DEPLOY_API_KEY` was introduced for the retained legacy Neon Function source-deployment boundary.

The active production database transport is now `PROJECT_SCOPED_NEON_RUNTIME_PROVISIONER`, while `scripts.reuse_v10_cloudflare_neon_bootstrap_function_source.py` explicitly defers the legacy Function contour when the runtime secret is absent. A legacy Function deployment credential is therefore not an active predecessor of staging or production database provisioning.

Aliasing the legacy Function credential into `NEON_API_KEY` collapses two authority roles merely because both target Neon. Exact branch custody cannot repair a credential-role mismatch.

## Permanent correction

- Use protected `secrets.NEON_API_KEY` directly for the runtime provisioner's `NEON_API_KEY` input in both missing-staging-secret recovery and missing-production-secret bootstrap.
- Remove `NEON_FUNCTION_DEPLOY_API_KEY` from the active exact-main production-release workflow. Retain the secret and legacy Function implementation outside the active transport; do not delete or weaken their dormant security guards.
- Split staging database recovery into a Cloudflare-only runtime-secret probe and a conditional Neon bootstrap step. Do not expose Neon management credentials when the staging runtime secret already exists.
- Preserve the existing production Cloudflare-only runtime-secret probe and conditional Neon bootstrap step. Do not rotate/reprovision a valid existing production runtime secret.
- Preserve PR #503 exact-branch custody for production: the runtime provisioner must still bind downstream database/connection-URI selection to the exact protected branch descriptor and fail closed on project/default/readiness drift.
- Preserve PostgreSQL 18 verification, migrations, least-privilege runtime roles, membership/ownership negatives, required grants, RLS/FORCE RLS verification, runner-temp-only DSN custody and Cloudflare secret convergence.
- Do not widen to organization/admin Neon authority and do not request a new OWNER secret merely to compensate for source-side credential-role conflation.

## Blast radius and adjacent review

Directly coupled surfaces inspected:

- `.github/workflows/v10-cloudflare-production-release.yml`;
- `.github/workflows/v10-cloudflare-candidate-deploy.yml` as the accepted role-separated database-management pattern;
- `scripts/provision_v10_cloudflare_neon_runtime.py` as the canonical runtime-management consumer;
- `scripts/reuse_v10_cloudflare_neon_bootstrap_function_source.py` as proof that legacy Function deployment is deferred on the active transport;
- `scripts/run_v10_cloudflare_gated_candidate.py`, whose runtime-secret synchronization consumes the fixed runner-temp staging DSN when one was conditionally provisioned and otherwise reuses the existing Worker secret;
- `docs/architecture/V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json`;
- Cloudflare/Neon authority and production-bootstrap deterministic regression suites.

Release #54 did not reach production Workers Build promotion, rollback snapshot, Custom Domain attachment or canonical live acceptance. No independent defect in those downstream gates is proven by this failure; they remain unchanged and must execute after the credential-role repair is accepted.

## Permanent regression / guard

Deterministic coverage requires:

- active exact-main production-release source contains no `NEON_FUNCTION_DEPLOY_API_KEY` dependency;
- staging and production runtime-management bootstrap use only `secrets.NEON_API_KEY` for the provisioner's canonical `NEON_API_KEY` environment role;
- Cloudflare-only secret probes do not receive Neon authority;
- staging and production Neon credentials are exposed only when the corresponding runtime secret is actually missing;
- active release contract binds `PROJECT_SCOPED_NEON_RUNTIME_PROVISIONER` directly to `NEON_API_KEY` and forbids aliasing the legacy Function deployment credential into runtime management;
- PR #503 exact-branch custody/project/default/ready guards remain mandatory for production;
- retained legacy Function/OIDC/TLS/provenance tests remain intact as dormant-component guards rather than being deleted to obtain GREEN;
- PostgreSQL 18, migrations, least privilege, RLS/FORCE RLS, no-DSN-log/artifact, rollback and exact-SHA release gates remain fail-closed;
- full exact-head CI, Sonar/security/review certification is required before merge and fresh exact-main post-merge plus automatic production-release evidence is required afterward.

## Prevention law

Credential names represent authority roles, not interchangeable secret slots. A credential introduced for one provider subsystem must never be aliased into a different producer/consumer contract merely because both use the same provider or project. When a transport is retired from the active path, its credential must also disappear from that active dependency graph unless a currently executed operation still proves it is required.

## Protected invariants

Unchanged: protected V9 `app:app`; `PUBLIC_MULTI_USER_ENABLED=false`; PostgreSQL 18 + RLS/FORCE RLS; broker write OFF; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; transfer/withdrawal/margin/leverage/uncovered-short remain OFF/FORBIDDEN; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
