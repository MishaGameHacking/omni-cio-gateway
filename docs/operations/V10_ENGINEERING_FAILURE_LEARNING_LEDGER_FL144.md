# V10 Engineering Failure Learning Ledger — FL144

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `MAIN_RED_STOP`
- Failure class: `CF_D_PROJECT_SCOPED_NEON_DIAGNOSTIC_ACCOUNT_ENDPOINT_COUPLING`
- Scope: fresh-secret production database bootstrap recovery after Release #59

## Observed failure

Accepted `main` `14dd57ac9c4cbca969196f612bc2f4ebc6558717` passed its exact-main post-merge batch and entered automatic `V10 Cloudflare Production Release` #59 / run `35008074486` after the OWNER had already rotated all four protected Neon bindings out of band.

The release passed Cloudflare provider authority, Workers Builds authority, Containers registry authority, the pinned delivery toolchain, staging runtime-secret reuse, the exact-SHA staging Worker + Container rehearsal, staging live acceptance, canonical production-domain validation and production Worker-anchor reuse. The production runtime-secret probe then correctly determined that `OMNI_V10_POSTGRES_DSN` was absent and bootstrap was required.

Production bootstrap stopped fail-closed with:

`CLOUDFLARE_NEON_RUNTIME=STOPPED code=NEON_PROJECT_KEY_BINDING_MISMATCH`

The recovery diagnostic emitted only sanitized status evidence:

`auth_status=403 credential_orgs_status=403 organization_status=403 exact_project_status=403 exact_branches_status=403 canonical_query_status=SKIPPED classification=UNRESOLVED`

All production promotion, Custom Domain mutation and canonical live-acceptance steps after database bootstrap were skipped. Cleanup/quarantine succeeded. No secret value, provider identifier, DSN, database credential or private payload is recorded here.

## Root cause

The mutation gate is correct: an exact project/branch authority failure must remain RED. The defect is the diagnostic decision tree used after that failure.

The diagnostic currently performs a bounded canonical project-name lookup only if `GET /organizations/{org_id}` succeeds. That prerequisite is appropriate for organization-wide credentials but is not valid for project-scoped Neon API keys. Neon documents project-scoped organization API keys as credentials limited to project-level operations; account/organization endpoints can be unavailable even when the key is valid for its project.

As a result, a project-scoped key that returns `403` on account/organization endpoints forces `canonical_query_status=SKIPPED`. The diagnostic can then report only `UNRESOLVED`, even though a bounded project-level collection lookup could safely distinguish:

- configured `NEON_PROJECT_ID` drift from the one canonical project visible to the credential;
- exact-project authorization inconsistency when the canonical project is visible but the exact endpoint is denied;
- a credential that cannot read even its project-scoped project collection.

Fresh connected-provider evidence independently confirms one canonical Omni-CIO Frankfurt PostgreSQL 18 project, a ready default `main` branch and administrative engineering access. That evidence does not reveal or validate the repository secret value and does not justify bypassing the exact mutation gate.

## Permanent correction

- Keep the production runtime provisioner and its exact project/branch authorization fail-closed behavior unchanged.
- Preserve organization-scoped diagnostics when organization detail is readable.
- When both credential-organization discovery and organization detail are denied, treat that as a project-scoped diagnostic shape and perform one bounded read-only `GET /projects` search for the canonical project name without an `org_id` parameter.
- Never enumerate arbitrary organizations or projects; the query remains bounded by the canonical project name and fixed limit.
- Compare project IDs only in memory. Emit only status, match-count and boolean match evidence; never log the configured or discovered provider identifier.
- Classify project-scoped outcomes explicitly as configured project-ID drift, exact-project authorization drift, canonical project not visible, ambiguous canonical name, or credential project-read forbidden.
- Preserve the original failing provisioner exit code after diagnostics. The diagnostic remains read-only and non-authoritative.

## Blast radius and adjacent review

Directly coupled surfaces reviewed:

- `scripts/probe_v10_neon_authority_diagnostics.py`;
- `scripts/provision_v10_cloudflare_neon_runtime.py` as the authoritative exact project/branch mutation gate;
- `scripts/provision_v10_render_neon_preview_org_scope.py` as the shared Bearer-auth Neon API transport;
- `.github/workflows/v10-cloudflare-production-release.yml` staging and production failure-only diagostic calls;
- existing `tests/test_v10_neon_authority_diagnostics.py` organization-scoped classifications;
- new project-scoped diagnostic regressions;
- external recovery issue #430.

The active workflow secret bindings, database mutation transport, Cloudflare promotion path, rollback, Custom Domain gates and broker/security invariants do not change in this repair.

## Permanent regression / guard

Deterministic coverage requires:

- project-scoped account/organization `403` responses to trigger exactly one canonical-name project query without `org_id`;
- a matching canonical project with a different configured ID to classify `CONFIGURED_PROJECT_ID_DRIFT`;
- a matching canonical project with the configured ID but denied exact resource to classify `EXACT_PROJECT_AUTHORIZATION_DRIFT`;
- a denied project-scoped canonical query plus denied exact project/branch to classify `CREDENTIAL_PROJECT_READ_FORBIDDEN`;
- organization-readable diagnostics and their existing classifications to remain unchanged;
- raw organization/project IDs, token values and provider payloads to remain absent from diagnostic output.

## Prevention law

A least-privilege credential must not be diagnosed through a broader authority prerequisite than the credential is designed to possess. Recovery diagnostics should interrogate the narrowest provider surface that can distinguish the failure class, while the mutation gate remains unchanged and fail-closed.

## Protected invariants

Unchanged: protected V9 `app:app`; PostgreSQL 18 + RLS/FORCE RLS; `PUBLIC_MULTI_USER_ENABLED=false`; broker write OFF; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; transfer/withdrawal/margin/leverage/uncovered-short remain OFF/FORBIDDEN; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
