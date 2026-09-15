# V10 Engineering Failure Learning Ledger — FL140

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `MAIN_RED_STOP`
- Failure class: `CF_D_PRODUCTION_NEON_AUTHORITY_FAILURE_DIAGNOSTIC_GAP`
- Scope: missing production PostgreSQL runtime-secret recovery after a fresh protected `NEON_API_KEY` rotation

## Observed failure

Exact accepted `main` `e654b041f0c3fa44c8c18413cdb90047fc234a5d` already contained both permanent source corrections required by the preceding failures: production runtime provisioning is bound to the exact Neon branch preserved in restricted runner-temp custody, and the active runtime-management credential role is the canonical protected `NEON_API_KEY` rather than the retained legacy Function-deployment credential.

After the PROJECT OWNER rotated `NEON_API_KEY` out of band, exact-main Regression Shield run `34748000878` was re-run on unchanged source so a later downstream workflow would resolve a genuinely fresh repository-secret snapshot. Attempt 2 completed both Regression Shield jobs successfully and queued `V10 Cloudflare Production Release` run `34961698712` / run #56 / job `104356553139`.

Run #56 passed the exact-main post-merge gate, Cloudflare provider/Workers Builds/Containers authority, pinned delivery toolchain, reusable staging database-secret probe, exact-SHA isolated staging build, exact single-version staging deployment, exact Worker/Container/health acceptance, bootstrap-origin custody, canonical production-domain configuration and production Worker-anchor readiness. The production runtime-secret probe then correctly reported that `OMNI_V10_POSTGRES_DSN` was absent and bootstrap was required.

The bounded production bootstrap stopped fail-closed with:

`CLOUDFLARE_NEON_RUNTIME=STOPPED code=NEON_PROJECT_KEY_BINDING_MISMATCH`

Production Workers Build promotion, Custom Domain attachment and canonical live acceptance did not execute. Cleanup/quarantine completed successfully.

No Neon API key, project/branch identifier, DSN, Cloudflare account identifier, database credential or private payload is recorded here.

## Root cause

The source correctly remained RED when the current protected Neon management credential could not prove exact project/branch authority. The defect was in recovery observability, not in that fail-closed decision.

The missing-staging-secret recovery path already preserves a failed Neon authority probe, runs `scripts.probe_v10_neon_authority_diagnostics` as read-only failure evidence, and then exits with the original failure status. The missing-production-secret path instead invoked `scripts.provision_v10_cloudflare_neon_runtime` directly under `set -e`. An exact-project/exact-branch authorization failure therefore terminated the step immediately after the provisioner's intentionally bounded `NEON_PROJECT_KEY_BINDING_MISMATCH` marker.

That marker is sufficient to block mutation but is intentionally not specific enough to distinguish an invalid credential, organization-binding drift, exact-project authorization drift or another safe recovery class. Because the existing diagnostic never ran on this production failure path, the next OWNER/provider action could only be chosen by blind secret iteration.

Fresh read-only connected-provider evidence independently confirmed that the intended Frankfurt project remained present on PostgreSQL 18 and that its default `main` branch remained active/ready. That evidence does not prove what credential value GitHub consumed and does not authorize a source bypass.

## Permanent correction

- Preserve `scripts.provision_v10_cloudflare_neon_runtime` as the authoritative production mutation gate and keep exact branch custody/project/default/ready proof fail-closed.
- Capture only the production provisioner's process exit status around the existing command. Do not reinterpret its failure.
- If and only if that production provisioner returns non-zero, run the existing read-only sanitized Neon authority diagnostic as best-effort recovery evidence.
- Diagnostic failure itself must never mask or replace the original production bootstrap failure; after diagnostics, exit with the original provisioner status.
- The diagnostic is non-authoritative observability. It cannot convert `403`, `404`, an invalid credential or any other failed mutation authority into success.
- Do not log token values, provider identifiers, request URLs containing protected identifiers, DSNs, response bodies or tenant-private payloads.
- Preserve production secret reuse: Neon management authority remains exposed only when the production runtime secret is genuinely missing.
- Preserve PostgreSQL 18 verification, migrations, least-privilege runtime-role convergence, grants, RLS/FORCE RLS, runner-temp-only DSN custody, Cloudflare secret convergence, rollback and exact-main release gates.

## Blast radius and adjacent review

Directly coupled surfaces reviewed:

- `.github/workflows/v10-cloudflare-production-release.yml` staging and production missing-secret paths;
- `scripts/provision_v10_cloudflare_neon_runtime.py` as the exact project/branch authority and database-bootstrap producer;
- `scripts/probe_v10_neon_authority_diagnostics.py` as the existing sanitized read-only diagnostic;
- `tests/test_v10_neon_authority_diagnostics.py`;
- `tests/test_v10_cloudflare_cf_d_direct_bootstrap_control_plane.py`;
- `docs/architecture/V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json`;
- external provider recovery issue #430 and focused repair issue #508.

No evidence from run #56 proves an independent defect in production Workers Build promotion, rollback snapshot, Custom Domain attachment, exact-SHA release identity or canonical live acceptance. Those gates remained unexecuted and stay unchanged until production database bootstrap succeeds.

## Permanent regression / guard

Deterministic coverage requires:

- the production missing-secret workflow to invoke the same project-scoped runtime provisioner as before;
- the production provisioner command to execute before the failure-only diagnostic;
- production diagnostic execution to be conditional on a non-zero production provisioner result;
- the original production provisioner exit status to be preserved after diagnostics;
- diagnostic errors to be ignored only for diagnostic collection while the original production failure remains RED;
- no diagnostic execution on the successful production provisioner path;
- the existing staging failure diagnostic behavior to remain intact;
- machine-readable release authority to state that the diagnostic is required, read-only, non-authoritative and forbidden from converting RED to GREEN;
- exact branch custody, project/default/ready proof, project-scoped credential role separation, PostgreSQL 18, RLS/FORCE RLS, no-DSN-log/artifact and all CI/security/recovery gates to remain mandatory.

## Prevention law

A fail-closed authority check and a recovery diagnostic are different responsibilities. The mutation gate decides whether authority is sufficient; a diagnostic may only explain a bounded failure safely. When a production authority gate intentionally collapses sensitive provider failures into a coarse code, every recovery path that can hit that gate must preserve the original RED status while collecting the already-approved sanitized read-only classification needed to choose the next bounded recovery action. Repeated credential rotation without such classification is not a substitute for diagnosis.

## Protected invariants

Unchanged: protected V9 `app:app`; PostgreSQL 18 + RLS/FORCE RLS; `PUBLIC_MULTI_USER_ENABLED=false`; broker write OFF; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; transfer/withdrawal/margin/leverage/uncovered-short remain OFF/FORBIDDEN; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
