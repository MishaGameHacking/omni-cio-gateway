# V10 Engineering Failure Learning Ledger — FL137

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `MAIN_RED_STOP`
- Failure class: `CF_D_NEON_FUNCTION_INVOKE_CREDENTIAL_NON_DELEGABLE_CUSTODY_DEADLOCK`
- Scope: production-database bootstrap authority and the directly coupled exact-main staging compatibility path

## Observed failure

Accepted main `3842572f759d7e2d289b44023d23f4eb69b6645c` reached Production Release #52 after the complete exact-main post-merge push gate, Cloudflare provider/build/container/toolchain readiness, staging runtime-secret reuse, staging Worker reuse, exact-SHA Build, exact single-version staging deployment, release proof and bootstrap-origin custody.

The staging rehearsal then stopped fail-closed with:

`CLOUDFLARE_CF_D_NEON_FUNCTION_INVOKE_CREDENTIAL_PROJECT_API_KEY_INSUFFICIENT status=403`

Production database bootstrap, production promotion, custom-domain mutation and live acceptance did not execute. Cleanup/quarantine completed.

No API key, branch credential token, Function URL, account identifier, database credential, OIDC token or private payload is recorded here.

## Root cause

The accepted Function-ingress recovery design attempted to create/list/revoke a branch-scoped `functions:invoke` credential through Neon Management API using the existing project-scoped `NEON_FUNCTION_DEPLOY_API_KEY`.

That capability assumption is false for the bounded project credential. Neon documents project-scoped keys as one-project/member-level authority, and the current Neon CLI documents that a project-scoped key cannot mint more keys. Live Release #52 independently proved the boundary with a sanitized provider `403` before any Function invocation could occur.

The proposed static-secret workaround was also not an acceptable permanent authority model. The current Neon Console for the exact branch does not expose `functions:invoke` when creating a credential, and an issued credential secret is returned only at creation/reveal custody boundaries. Our connected GitHub authority cannot safely take such a newly issued provider secret and write it into Actions repository-secret custody without exposing the value to an intermediate channel. Broadening release authority to organization/admin solely to mint an invocation token would violate least privilege.

The systemic defect was therefore architectural: production database availability had become dependent on a Function invocation credential whose creation required broader authority than the release was allowed to possess, despite an already accepted project-scoped PostgreSQL 18 runtime provisioner being able to perform the same database convergence without that credential layer.

## Permanent correction

- Keep `NEON_FUNCTION_DEPLOY_API_KEY` bounded to the exact Neon project; do not broaden it to organization/admin authority.
- Remove `NEON_FUNCTION_INVOKE_API_TOKEN` as an active production-release prerequisite.
- Keep the normal production-secret reuse path Cloudflare-only: it must not receive Neon authority when the existing `OMNI_V10_POSTGRES_DSN` secret is already ready.
- After the production Worker anchor exists, probe the production runtime secret with Cloudflare authority only.
- Only when the protected production runtime secret is genuinely missing, expose the existing project-scoped Neon authority to the already accepted `scripts.provision_v10_cloudflare_neon_runtime` path, aliasing it to the provisioner's canonical `NEON_API_KEY` binding for that bounded step.
- Run the provisioner with `--environment production` and the exact accepted main SHA. Preserve PostgreSQL 18 verification, canonical migrations, least-privilege `omni_cio_cloudflare_prod`, negative membership/ownership checks, grants, tenant RLS/FORCE RLS verification and private runner-temp DSN custody.
- Write the resulting DSN into the production Worker secret through the existing Cloudflare production manager, then independently re-probe the Cloudflare secret in a step that has no Neon credentials.
- Keep the legacy Neon Function/OIDC implementation in the repository as a retained inactive component. Its TLS, exact-source, bounded-response, OIDC and provider-classification tests remain guards against accidental regression if that transport is deliberately reactivated later.
- The exact-main staging compatibility adapter must no longer make Function provenance/deployment authority a predecessor of staging acceptance. If the production runtime secret is absent, it records a bounded deferral to the project-scoped production bootstrap that runs after the production Worker anchor is established.

## Blast radius and adjacent review

Directly coupled surfaces reviewed and corrected:

- `.github/workflows/v10-cloudflare-production-release.yml`;
- `scripts/reuse_v10_cloudflare_neon_bootstrap_function_source.py`;
- `scripts/provision_v10_cloudflare_neon_runtime.py` as the accepted producer now reused for production;
- `scripts/manage_v10_cloudflare_production.py` as the existing Cloudflare secret writer/verifier;
- `docs/architecture/V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json`;
- Function/direct-bootstrap control-plane regressions and Neon authority-preflight regressions.

The production runtime provisioner already accepts `production`, enforces the canonical PostgreSQL 18 project, applies migrations, converges the least-privilege runtime role, verifies RLS/FORCE RLS, writes only a protected runner-temp DSN, and does not log or artifact that DSN. This repair therefore reuses an accepted migration path instead of adding a second broker, database, scheduler, Gateway or secret-custody stack.

Downstream CF-D gates remain unchanged: stale production Builds quarantine, rollback snapshot, exact-current-main recheck, gated production Workers Build, canonical Custom Domain attachment, exact-SHA live release/health/database acceptance and bounded rollback.

No evidence from Release #52 proves an independent defect in those downstream gates.

## Permanent regression / guard

Deterministic coverage requires:

- production runtime-secret reuse to complete without exposing any Neon management or Function invocation secret;
- missing production runtime secret to select the project-scoped Neon runtime provisioner only after the production Worker anchor exists;
- the production bootstrap step to use the exact project-scoped release credential, `NEON_ORG_ID` and `NEON_PROJECT_ID`, and to reject provider-authority failures fail-closed;
- the runtime provisioner to continue requiring exact SHA, PostgreSQL 18, migrations, least-privilege role attributes, no memberships/ownership, canonical grants and RLS/FORCE RLS;
- the DSN to remain runner-temp only, never logged, artifacted or persisted outside the Cloudflare secret binding;
- a separate Cloudflare-only confirmation step to prove the target runtime secret after mutation;
- `NEON_FUNCTION_INVOKE_API_TOKEN` to be absent from the active production workflow;
- the exact-main staging compatibility adapter to perform no active Function invocation/deployment dependency;
- legacy Function security tests to remain intact while the transport is inactive;
- all exact-head CI, security, Sonar/review and exact-main post-merge certification gates to remain mandatory.

## Prevention law

Do not introduce a credential-minting dependency merely to reach a provider transport when an accepted narrower project-scoped path already satisfies the required state transition. A release must first prove whether mutation is needed, then expose the narrowest authority only to the bounded mutation step, and independently verify the resulting state without retaining that authority. A secret that cannot be created and transferred through an auditable non-disclosing custody path is not an acceptable unattended production prerequisite.

## Protected invariants

Unchanged: protected V9 `app:app`; `PUBLIC_MULTI_USER_ENABLED=false`; PostgreSQL 18 + RLS/FORCE RLS; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; broker write, transfer, withdrawal, margin, leverage and uncovered short remain OFF/FORBIDDEN; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
