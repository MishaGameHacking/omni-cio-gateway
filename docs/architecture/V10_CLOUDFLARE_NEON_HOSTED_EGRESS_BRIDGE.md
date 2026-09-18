# V10 Cloudflare Neon Hosted Egress Bridge

Status: `ACTIVE_ONLY_INSIDE_CF_D_MISSING_SECRET_RECOVERY`

Authority: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D` under the accepted exact-main release gate and Amendment 16 `MAIN_RED_STOP` repair discipline.

## Purpose

The canonical Cloudflare production release keeps the project-scoped Neon runtime provisioner as the only active database bootstrap implementation. The hosted egress bridge changes **where** the rare missing-runtime-secret recovery transaction executes; it does not introduce a second database stack, second migration path, second runtime role model, or broader Neon authority.

Fresh accepted diagnostics on exact main proved that the same anonymous Neon management-API request receives different bounded response classes by runner egress: the self-hosted Windows contour receives `403 / HTML`, while GitHub-hosted Ubuntu receives `401 / JSON`. Production Release #71 subsequently reproduced the self-hosted exact-project bootstrap denial. The bridge therefore moves only the egress-sensitive Neon management/bootstrap transaction to an ephemeral GitHub-hosted Linux runner when a required Cloudflare runtime secret is absent.

## Authority model

`GITHUB_HOSTED_MISSING_SECRET_RECOVERY_ONLY`

The hosted job is applicable only after a Cloudflare secret probe proves that the staging or production `OMNI_V10_POSTGRES_DSN` binding is absent. Existing secrets are reused unchanged and no hosted Neon bootstrap job runs.

The accepted project-scoped `NEON_API_KEY` remains the active Neon management credential. Organization-wide/admin authority is neither required nor allowed. The hosted job also receives the existing Cloudflare release credential only for the bounded recovery step that writes the generated runtime DSN directly to the corresponding Worker secret.

The workflow is triggered only from the exact-main CF-D release workflow. Repository source is manually fetched at the exact accepted SHA with a read-only `GITHUB_TOKEN`; `actions/checkout` is not used. The only external Action in a hosted recovery job is the repository-pinned first-party `actions/setup-python` commit, and it executes before provider secrets are exposed to a step.

## Production branch custody bridge

`HOSTED_EPHEMERAL_BRANCH_CUSTODY_RESYNC`

FL138 established a strict production rule: when exact branch custody already exists, production authority must use one exact branch resource and must not fall back to branch collection enumeration. The hosted recovery preserves that rule.

The raw production branch identifier is **not** copied from the self-hosted runner to a job output, artifact, summary, environment value, or repository file. Instead, when production recovery is required, the hosted job reacquires the already validated target from the exact-SHA staging release by reusing the accepted custody protocol:

1. resolve the existing staging Worker origin with Cloudflare authority;
2. require `/api/v10/release` to attest the exact accepted main SHA before custody is requested;
3. arm a fresh random `OMNI_V10_CF_D_ORIGIN_SYNC_TOKEN` as a staging Worker secret;
4. fetch the bounded bootstrap-origin custody response through the exact internal endpoint;
5. remove the sync token in the context-manager cleanup path;
6. validate the returned origin and write the existing restricted `RUNNER_TEMP` target descriptor **inside the hosted job**;
7. invoke the unchanged canonical production provisioner, which reads that descriptor and performs its existing exact `GET /projects/{project_id}/branches/{branch_id}` authority check before database mutation.

The raw branch identifier therefore exists only in the hosted job's restricted runner-temp custody immediately before canonical provisioning. It never crosses a job boundary, and production does not re-enter `branches?limit=100`.

## Secret custody

`DSN_JOB_BOUNDARY_FORBIDDEN`

Generated database credentials and DSNs never cross a GitHub job boundary. The canonical provisioner writes the DSN only to the fixed `RUNNER_TEMP` file. In the same hosted job and before cleanup, the bridge writes that DSN directly to the relevant Cloudflare Worker `OMNI_V10_POSTGRES_DSN` secret. The file and any production target descriptor are removed in an `always()` cleanup path.

The workflow must not use job outputs, artifacts, caches, summaries, command-line values, or repository content to transfer a DSN or raw Neon branch/project identifier. Provider credentials are step-scoped environment variables and must never be printed or persisted.

Cross-job production data is limited to exact accepted main SHA and boolean missing-secret state.

## Dependency and source integrity

Hosted recovery uses Python `3.12.10`, matching the protected CF-D control-plane runtime. The minimal hosted provider dependency projection is generated at runtime from the exact accepted main `requirements.txt`; versions and hashes are not independently invented or upgraded.

`PYDANTIC_IMPORT_CLOSURE_EXPLICIT`

Production Release #74 proved that the hosted bootstrap import graph executes regular-package `__init__.py` files under both `omni_cio.contracts` and `omni_cio.persistence` before database mutation. Those package initializers reach the accepted Pydantic-backed domain contracts. The bounded hosted projection therefore contains exactly the canonical hash-locked runtime closure required by that import graph: `annotated-types`, `pydantic`, `pydantic-core`, `psycopg`, `psycopg-binary`, `typing-extensions`, and `typing-inspection`. It remains installed with `--require-hashes --no-deps`.

The projection intentionally excludes application/runtime packages such as FastAPI, HTTPX, Starlette, tzdata and Uvicorn. Any future package needed by hosted recovery must first enter the canonical reviewed lock and the explicit hosted allowlist; pip dependency resolution is not allowed to silently expand the recovery environment.

No hosted recovery job uses an unpinned package version or an unpinned external Action.

## Staging and production sequencing

The release workflow has five bounded phases:

1. self-hosted exact-main/provider inspection, staging Worker anchor, and staging secret probe;
2. hosted staging Neon recovery only if the staging secret is missing; staging has no prior exact branch custody, so its existing canonical project-scoped collection selection remains unchanged;
3. self-hosted exact-SHA staging Worker + Container rehearsal, live acceptance, canonical-domain validation, production Worker anchor, and production secret probe;
4. hosted production Neon recovery only if the production secret is missing; the hosted job reacquires exact production branch custody from the exact-SHA staging release before invoking the canonical exact-branch provisioner;
5. fresh self-hosted production promotion, including Cloudflare authority rechecks, runtime-secret confirmation, stale-Build quarantine, rollback snapshot, exact-current-main recheck, gated Workers Build, Custom Domain attachment, live exact-SHA/health/database acceptance, and bounded rollback.

A skipped hosted job is non-applicable only when the corresponding secret probe proved reuse. When recovery is applicable, only terminal `success` permits the dependent phase to continue.

## Failure semantics

All security, authority, dependency, provider and database failures remain fail-closed. A failed hosted Neon bootstrap runs only the existing sanitized read-only Neon failure diagnostic and preserves the failed recovery outcome. It cannot convert the release to GREEN.

The hosted bridge does not weaken TLS, SHA, project/branch validation, PostgreSQL 18, migration, runtime-role, RLS, Cloudflare exact-main, domain, live-acceptance or rollback gates.

## Legacy transport

`LEGACY_NEON_FUNCTION_TRANSPORT_REMAINS_INACTIVE`

The retained Neon Function/OIDC source and provenance guards remain historical recovery evidence only. The hosted egress bridge must not reactivate `NEON_FUNCTION_*`, mint `functions:invoke` credentials, introduce a static invocation token, or broaden to organization/admin Neon authority. Earlier accepted failures proved that path creates an authority deadlock under the project-scoped release model.

## Cost boundary

Standard GitHub-hosted runners for the private repository may consume the account's included Actions minutes and can become billable after included quota. The bridge minimizes that exposure by making hosted recovery conditional on a genuinely absent runtime secret; normal production releases with reusable database secrets remain self-hosted for the release authority path. Any later change that intentionally adds paid/larger hosted runners, persistent hosted recovery, or a broader hosted CI migration remains a separate OWNER cost decision.

## Protected invariants

Unchanged:

- V9 stable gateway entrypoint `app:app`;
- one V10 Gateway/Web/DB/execution stack;
- PostgreSQL 18 with RLS/FORCE RLS;
- `PUBLIC_MULTI_USER_ENABLED=false` until its future gate;
- broker write OFF;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- transfer/withdrawal/margin/leverage/uncovered-short remain forbidden;
- no WP23+, WEB-VISUAL, Telegram or AI/Cortex scope expansion.
