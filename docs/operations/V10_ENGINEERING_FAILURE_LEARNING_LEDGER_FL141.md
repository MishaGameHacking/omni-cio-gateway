# V10 Engineering Failure Learning Ledger — FL141

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `MAIN_RED_STOP`
- Failure class: `PROVIDER_SECRET_INVENTORY_AND_ROLE_SEPARATION_GUARD_MISSING`
- Scope: GitHub Actions provider-secret custody after OWNER rotation of the active Neon bindings

## Observed condition

Repeated CF-D recovery failures established that provider credential names are authority roles, not interchangeable secret slots. The OWNER then rotated the protected Neon runtime-management bindings and reconfirmed that the repository Actions secret inventory contains the intended Cloudflare/Neon release bindings and canonical Cloudflare custom-host binding only.

Read-only connected Neon evidence independently confirms the intended provider topology: exactly one visible Omni-CIO project, `omni-cio-v10-preview-frankfurt`, in Frankfurt, PostgreSQL 18, with the default `main` branch ready. No secret value or full provider identifier is recorded here.

Repository audit was re-run on exact accepted `main` `fc76c2c56a40c01b3825efc2d41839151ec08ecf` after Production Release #77 completed successfully. The executable workflow bindings remain role-separated as intended:

- `NEON_API_KEY`, `NEON_ORG_ID`, and `NEON_PROJECT_ID` form the active Neon runtime-management tuple;
- `NEON_FUNCTION_DEPLOY_API_KEY` is retained only by dormant legacy Function-deploy source and is not injected into an active workflow;
- Cloudflare account/token authority is step-scoped in the active provider/candidate/production workflows;
- Cloudflare zone/custom-host bindings are production-release-only;
- retired Render workflows are secret-free;
- active workflows do not reference `RENDER_API_KEY` or the removed `NEON_FUNCTION_INVOKE_API_TOKEN`.

The systemic defect was the absence of one repository-wide machine contract that froze this complete inventory and consumer map. Existing guards covered individual workflows and historical failures, but a later edit could add an unreviewed repository secret, reintroduce a retired secret, cross-wire the legacy Function-deploy key into runtime management, fall back to Actions variables for protected provider identifiers, or broaden secret injection to job scope without one deterministic global failure.

## Permanent correction

- Add `docs/architecture/V10_PROVIDER_SECRET_CUSTODY_CONTRACT.json` as the value-free machine-readable provider-secret inventory/role map.
- Add `scripts/check_v10_provider_secret_custody.py` to scan every GitHub Actions workflow for repository-secret and Actions-variable references.
- Freeze the exact current nine provider secret names without storing any values.
- Require the three active Cloudflare workflows to consume exactly their approved role-specific subsets.
- Keep `NEON_FUNCTION_DEPLOY_API_KEY` dormant while the legacy Function transport remains inactive; its mere presence in GitHub secret custody is not authority because no active workflow references it.
- Reject active workflow references to `RENDER_API_KEY` and `NEON_FUNCTION_INVOKE_API_TOKEN`.
- Reject protected provider identifiers/credentials routed through `vars.*`.
- Reject active Cloudflare secret references above step scope.
- Keep retained historical scripts/docs as audit/recovery evidence; do not delete history merely because it names an obsolete provider credential.
- Add deterministic positive/negative tests, including unknown-secret, retired-secret, removed-invoke-secret, dormant-deploy-key, variable-fallback, broad-job-scope, and missing-domain-binding failures.

## Blast radius

Direct consumers/producers reviewed:

- `.github/workflows/v10-cloudflare-provider-readiness.yml`;
- `.github/workflows/v10-cloudflare-candidate-deploy.yml`;
- `.github/workflows/v10-cloudflare-production-release.yml`;
- `.github/workflows/v10-hosted-release-alignment.yml`;
- `.github/workflows/v10-phase4-free-preview-deploy.yml`;
- `scripts/provision_v10_cloudflare_neon_runtime.py`;
- `scripts/manage_v10_cloudflare_production.py`;
- `scripts/deploy_v10_cloudflare_neon_bootstrap_function.py`;
- `scripts/neon_function_invocation_credential.py`;
- existing Cloudflare candidate/release secret-custody regressions.

No source evidence justifies changing Cloudflare credentials, domain bindings, PostgreSQL role semantics, or provider identifiers. Fresh runtime/provider proof is still required after merge because GitHub secret values are intentionally opaque to repository code and are resolved only when a workflow run is queued.

## Prevention law

Treat the repository secret namespace as a reviewed API surface. Every new provider secret name or new workflow consumer requires an explicit contract update and deterministic regression. Dormant credentials must never become active merely because they remain stored in GitHub, and active authority must never be silently aliased to a credential created for a different provider operation.

## Protected invariants

Unchanged: protected V9 `app:app`; `PUBLIC_MULTI_USER_ENABLED=false`; PostgreSQL 18 + RLS/FORCE RLS; broker write OFF; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; transfer/withdrawal/margin/leverage/uncovered-short remain OFF/FORBIDDEN; WP23+, WEB-VISUAL, Telegram, and AI/Cortex remain out of scope.


## Current-main revalidation

The earlier DRAFT PR #511 is not reused as merge authority because its branch diverged from
current protected `main` by eighteen accepted commits. This focused replacement starts
from exact `fc76c2c56a40c01b3825efc2d41839151ec08ecf` and re-audits the current workflow
graph before publishing the contract.

That re-audit found exactly the same three active workflow consumers and no provider
secret references in the two retired Render workflows. It also found two adjacent guard
failure modes in the superseded implementation: uppercase dot-notation-only matching
could miss equivalent bracket/lowercase context references, and checking only the text
before the first `steps:` marker could miss job-scope injection in a later job of a
multi-job workflow. The replacement guard closes both bypass classes fail-closed.
