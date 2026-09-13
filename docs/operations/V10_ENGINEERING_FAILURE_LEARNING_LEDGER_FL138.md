# V10 Engineering Failure Learning Ledger — FL138

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `MAIN_RED_STOP`
- Failure class: `CF_D_RUNTIME_PROVISIONER_BOUND_TO_LEGACY_FUNCTION_DEPLOY_CREDENTIAL`
- Scope: missing production PostgreSQL runtime-secret bootstrap in the exact-main CF-D production release

## Accepted failure evidence

Exact accepted `main` `27def7710c03299d4d5640f66799bff2d0288835` completed the required exact-main push verification, including Regression Shield run `34741978287` with terminal `success`.

Automatic `V10 Cloudflare Production Release` run `34742456589` / run #53 then passed:

- exact-main post-merge workflow gate;
- Cloudflare provider readiness;
- Workers Builds authority;
- Containers registry authority;
- pinned Cloudflare/toolchain installation;
- exact-SHA isolated staging Worker + Container rehearsal;
- staging release identity and health acceptance;
- bootstrap-origin custody;
- canonical public-domain configuration;
- production Worker-anchor readiness;
- the Cloudflare-only probe proving the production database runtime secret was absent and bootstrap was genuinely required.

The release then failed closed at `Bootstrap production database secret if missing` with the sanitized result:

`CLOUDFLARE_NEON_RUNTIME=STOPPED code=NEON_PROJECT_KEY_BINDING_MISMATCH`

Production promotion, Custom Domain attachment/live acceptance and production evidence recording did not execute. Cleanup/quarantine completed successfully. No credential, project identifier, database URI, private hostname or user payload is recorded here.

## Root cause

PR #500 correctly replaced the active legacy Neon Function bootstrap transport with the existing project-scoped PostgreSQL runtime provisioner for the one-time missing production runtime secret. The workflow, however, aliased the retained Function-deployment credential into that provisioner's canonical database-management input:

`NEON_API_KEY <- NEON_FUNCTION_DEPLOY_API_KEY`

That alias conflated two provider authority roles:

1. `NEON_API_KEY` — the established exact-project database/runtime management credential used by the normal candidate/provider path and by `scripts.provision_v10_cloudflare_neon_runtime`;
2. `NEON_FUNCTION_DEPLOY_API_KEY` — the separately introduced credential for the retained legacy Neon Function source-deployment boundary.

Release #53 proved the Function-deployment credential does not satisfy the runtime provisioner's exact project/default-branch management contract. The provisioner therefore stopped before PostgreSQL mutation rather than accepting a mismatched authority.

The same alias existed in the production workflow's missing-staging-secret recovery branch. Staging normally reused its existing protected runtime secret in run #53, so that adjacent path did not fail live in this run, but it shared the same defect class and blast radius.

## Why the previous repair missed it

The earlier repair correctly identified that the active production database transport no longer requires the Neon Function invocation/deployment chain. It reused the runtime provisioner but carried forward the Function-deployment key as a convenient project-scoped credential because both were described as project-bounded.

That assumption was too coarse. Project scope alone is not a sufficient contract: the credential must also match the exact consumer role and provider permissions required by the called API surface. The repository already had the stronger canonical `NEON_API_KEY` binding for the runtime provisioner, and the production release should have reused that established authority instead of rebinding a different credential by environment-variable alias.

## Permanent correction

- Restore `secrets.NEON_API_KEY` as the only active Neon management credential supplied to `scripts.provision_v10_cloudflare_neon_runtime` in the production release.
- Use that same canonical binding for the missing-staging-secret recovery path and the missing-production-secret bootstrap path.
- Remove `NEON_FUNCTION_DEPLOY_API_KEY` from the active production release workflow while the legacy Function transport remains inactive.
- Keep the retained legacy Function source/deployment code and its separate credential contract guarded for historical/recovery compatibility; do not silently repurpose its credential for database management.
- Update the machine-readable release contract so `PROJECT_SCOPED_NEON_RUNTIME_PROVISIONER` binds directly to `NEON_API_KEY`.
- Add deterministic workflow tests that fail if the production release aliases `NEON_FUNCTION_DEPLOY_API_KEY` into the runtime provisioner again.
- Preserve exact project/organization binding, PostgreSQL 18 verification, migrations, least-privilege runtime-role convergence, RLS/FORCE-RLS verification, runner-temp-only DSN custody, Cloudflare secret convergence and downstream rollback/live-acceptance gates.

## Prevention law

1. Provider credentials are typed capabilities, not interchangeable strings merely because they share a project scope.
2. A workflow must bind the credential that belongs to the called consumer contract; environment-variable aliasing must not collapse independently reviewed authority roles.
3. Retained inactive compatibility/recovery credentials must not become active dependencies of a newer transport unless that transition is explicitly justified and tested.
4. Live provider evidence that a supposedly compatible credential fails an exact consumer boundary invalidates the compatibility assumption; do not widen permissions or reinterpret the failure as success.
5. When a credential-role defect is found, inspect all workflow occurrences of the alias and repair the whole directly coupled path, not only the first failing step.

## External/provider consistency

Current Neon documentation describes project-scoped organization API keys as limited to specific projects with project/member-level permissions. That supports retaining least-privilege project-scoped authority; it does not justify broadening to organization/admin credentials merely to obtain GREEN.

## Protected invariants

Unchanged:

- protected V9 `app:app`;
- `PUBLIC_MULTI_USER_ENABLED=false` until its own accepted live gate;
- PostgreSQL 18 + RLS/FORCE-RLS requirements;
- broker write OFF;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- transfer/withdrawal/margin/leverage/uncovered-short remain OFF/FORBIDDEN;
- no WEB VISUAL, WP23+, Telegram/VK, AI/Cortex or Real-execution scope;
- no secret/provider identifier/private payload disclosure.
