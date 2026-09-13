# V10 Engineering Failure Learning Ledger — FL138

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `MAIN_RED_STOP`
- Failure class: `CF_D_PRODUCTION_NEON_PROJECT_SCOPED_BRANCH_COLLECTION_FALSE_BINDING_MISMATCH`
- Scope: production PostgreSQL 18 bootstrap authority selection inside the accepted project-scoped Neon runtime provisioner

## Observed failure

Exact accepted `main` `27def7710c03299d4d5640f66799bff2d0288835` reached automatic Production Release #53 after the complete exact-main post-merge gate. Cloudflare provider readiness, Workers Builds authority, Containers registry authority, delivery toolchain, isolated staging rehearsal, exact-SHA staging live acceptance, canonical-domain validation and production Worker anchor all passed. The production runtime-secret probe correctly reported that database bootstrap was required.

The bounded production bootstrap step then stopped fail-closed with:

`CLOUDFLARE_NEON_RUNTIME=STOPPED code=NEON_PROJECT_KEY_BINDING_MISMATCH`

Production Workers Build promotion, Custom Domain mutation and live production acceptance did not execute. Cleanup completed.

No Neon API key, project or branch identifier, DSN, Cloudflare account identifier, database credential or private payload is recorded here.

## Root cause

The active production bootstrap correctly reused the accepted project-scoped Neon management credential. When exact project metadata was unavailable to that bounded credential, `scripts/provision_v10_cloudflare_neon_runtime.py` fell back to provider collection enumeration through `GET /projects/{project_id}/branches?limit=100`. Any `403` or `404` from that broader collection endpoint was then collapsed to `NEON_PROJECT_KEY_BINDING_MISMATCH`.

That classifier was stronger than the evidence. A denial of branch collection enumeration does not prove that the credential is bound to a different project. More importantly, collection enumeration is unnecessary in the exact-main production release because the canonical default branch identifier has already been validated and placed into restricted runner-temp custody by the staging bootstrap-origin handoff earlier in the same release job.

The repository already contained the correct authority pattern in the retained Neon Function deployment path: use `GET /projects/{project_id}/branches/{branch_id}` for the already-custodied exact branch and require exact branch identity, exact project binding, `default=true` and `current_state=ready`.

Independent read-only provider evidence confirmed that the canonical Frankfurt PostgreSQL 18 project and its default `main` branch remained present and ready. The failure therefore came from selecting an unnecessarily broad read surface, not from proven provider-resource deletion or project misbinding.

## Permanent correction

- Keep the existing project-scoped release credential. Do not broaden it to organization/admin authority and do not require a new OWNER secret.
- For `--environment production`, read the already protected bootstrap-origin handoff from runner-temp custody and validate its branch identifier without logging it.
- If exact project metadata is unavailable, prove project-scoped authority with `GET /projects/{project_id}/branches/{branch_id}` for that exact custodied branch instead of branch collection enumeration.
- Require the exact-branch response to match the expected branch id and project id and to report `default=true` plus `current_state=ready` before database mutation.
- Preserve fail-closed `NEON_PROJECT_KEY_BINDING_MISMATCH` for `403`/`404` on the exact resource. Preserve distinct fail-closed classes for malformed response, project-binding drift, non-default branch, non-ready branch and custody drift.
- Bind downstream database/connection-URI target selection to the same expected branch id so the authority producer and consumer cannot silently diverge.
- Preserve the existing branch-collection fallback only for contours that genuinely lack prior trusted branch custody, including staging recovery. Do not widen or redesign that adjacent contour without its own evidence.
- Preserve PostgreSQL 18 verification, migrations, least-privilege runtime-role convergence, no role memberships/ownership, grants, RLS/FORCE RLS, runner-temp-only DSN custody and Cloudflare-only secret re-probe.

## Blast radius and adjacent review

Directly coupled surfaces inspected:

- `scripts/provision_v10_cloudflare_neon_runtime.py`;
- `.github/workflows/v10-cloudflare-production-release.yml`;
- `scripts/bootstrap_v10_cloudflare_production_database_direct.py` handoff custody;
- `scripts/deploy_v10_cloudflare_neon_bootstrap_function.py` exact-branch provider pattern;
- `tests/test_v10_cloudflare_neon_binding_diagnostics.py` and the new production exact-branch regression surface;
- `docs/architecture/V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json`;
- downstream CF-D production build, Custom Domain, live acceptance and rollback gates.

No source change is required in the production workflow: it already preserves the restricted bootstrap-origin handoff until after production database-secret confirmation and exposes Neon management authority only to the missing-secret bootstrap step.

No evidence from Release #53 proves an independent defect in production Workers Build promotion, rollback snapshot, Custom Domain attachment, exact-SHA release identity, `/healthz` database acceptance or bounded rollback. Those gates remain unchanged and unexecuted until this bootstrap boundary passes.

## Permanent regression / guard

Deterministic coverage requires:

- production runtime provisioning to obtain its expected branch from restricted bootstrap-origin custody;
- exact project-scoped fallback to use one exact branch resource and never `branches?limit=100` when custody is available;
- exact branch id, project id, default state and ready state to be verified before database mutation;
- exact branch `403`/`404` to remain fail-closed as project-key binding failure;
- branch/project/default/ready/custody drift to have distinct sanitized failure classes;
- project-scoped metadata success followed by organization-scope denial to still converge onto the exact custodied branch for production rather than re-enter collection enumeration;
- staging/no-custody compatibility to remain unchanged;
- all PostgreSQL 18, runtime-role, RLS/FORCE RLS, secret-custody, CI, Sonar and exact-main release gates to remain mandatory.

## Prevention law

When an exact provider-resource identifier has already been validated and placed in protected custody, use the narrow exact-resource endpoint before any collection enumeration. A broader collection denial is not proof of resource misbinding. Authority classifiers must distinguish “this exact resource is forbidden/not found” from “this broader listing is not permitted,” and production mutation must remain bound to the same exact resource proof consumed downstream.

## Protected invariants

Unchanged: protected V9 `app:app`; PostgreSQL 18 + RLS/FORCE RLS; `PUBLIC_MULTI_USER_ENABLED=false`; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; broker write, transfer, withdrawal, margin, leverage and uncovered short remain OFF/FORBIDDEN; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
