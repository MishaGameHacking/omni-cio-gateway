# V10 Engineering Failure Learning Ledger — FL135

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `MAIN_RED_STOP`
- Failure class: `CF_D_EXACT_BRANCH_AUTHORITY_BLOCKED_BY_UNNECESSARY_COLLECTION_LOOKUP`
- Scope: exact-main Neon Function source-convergence management proof after PR #496

## Exact failure evidence

PR #496 squash-merged as exact `main` `51febc17dd5b083f71e0c5560de358467aebe877`. The complete 11-workflow exact-main push batch then reached terminal `success`, including Regression Shield and engineering governance.

Automatic `V10 Cloudflare Production Release` run `34707134608` passed the post-merge gate, provider/build/container/toolchain readiness, staging database-secret reuse, Worker-anchor reuse, exact-SHA staging build, single-version proof, release probe and bootstrap-origin custody. The release then emitted the sanitized project-metadata deferred state and stopped fail-closed with:

`CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_PROJECT_API_KEY_INSUFFICIENT status=403`

Production promotion, Custom Domain mutation and live acceptance did not execute. Cleanup/quarantine succeeded.

No provider credential, project/branch identifier, Function URL, database credential or private payload is recorded here.

## Root cause

The accepted convergence path already possesses a validated `BootstrapFunctionTarget.branch_id` from the restricted bootstrap-origin custody descriptor, but `_exact_branch()` discarded that exact resource identity for the management read and instead requested the broad project branch collection:

`GET /api/v2/projects/{project_id}/branches?limit=100`

After the unauthenticated Function provenance path reached the bounded provider 403, the code loaded the dedicated project-scoped management authority. Exact-project metadata lookup was deliberately allowed to defer on endpoint-specific 403/404. The next collection request then produced the observed `PROJECT_API_KEY_INSUFFICIENT` classification, before the newly added ephemeral `functions:invoke` credential lifecycle could execute.

The failure therefore does not prove the invocation credential implementation is wrong. It proves the convergence control plane required a broader discovery/read surface than its already-custodied exact identity required.

Current Neon OpenAPI exposes `GET /projects/{project_id}/branches/{branch_id}` and returns exact branch identity including `id`, `project_id`, `current_state` and `default`. That exact-resource operation is sufficient for this convergence gate.

## Blast radius and adjacent review

Review covered:

- `scripts/deploy_v10_cloudflare_neon_bootstrap_function.py` project/branch/Function proof order;
- bootstrap-origin custody of `branch_id` and its strict branch-id validation;
- exact Function lookup and active/current deployment identity proof;
- the downstream ephemeral `functions:invoke` credential path from PR #496;
- the generic runtime provisioning path, which still needs branch collection because it performs environment discovery rather than exact Function convergence;
- historical issue #430 / FL127 / FL128 authority failures to avoid reintroducing legacy or organization-wide authority;
- official Neon exact-branch response shape.

The correction is intentionally limited to the Function source-convergence path. It does not change generic Neon runtime provisioning, database authority, Cloudflare promotion, product authentication, public-user activation or broker authority.

## Permanent correction

`_exact_branch()` now requests only the already-custodied branch resource:

`GET /api/v2/projects/{project_id}/branches/{branch_id}`

It preserves fail-closed identity checks:

- target branch id must match the validated custody descriptor;
- if `project_id` is present in the provider response it must match the configured project;
- branch must be the default branch;
- `current_state` must be `ready`;
- malformed or mismatched responses remain blocking.

The function retains bounded compatibility with the already accepted list-shaped deterministic test fixture while the real provider request is always the exact branch path. No collection query is sent by this convergence path.

## Deterministic regression guard

A focused test module proves:

- the outbound management path is exactly `/api/v2/projects/{project_id}/branches/{branch_id}` with no query/discovery collection;
- the exact branch response succeeds only for the expected project/branch/default/ready state;
- cross-project, wrong-branch, non-default and unready responses fail closed;
- malformed exact-resource payloads fail closed.

Existing Function deployment, provenance, race, credential-custody and full Regression Shield tests remain applicable.

## Prevention law

When a provider identity has already been derived from a stronger trusted custody boundary, do not expand the management read surface back to a list/discovery operation merely to rediscover the same identity. Prefer the exact-resource endpoint and validate the response against the custodied identifier. A broader collection lookup requires an independent need and must not become a hidden prerequisite for least-privilege release authority.

## Protected invariants

Unchanged: protected V9 `app:app`; PostgreSQL 18 + RLS/FORCE RLS; `PUBLIC_MULTI_USER_ENABLED=false`; broker write OFF; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; transfer/withdrawal/margin/leverage/uncovered-short remain OFF/FORBIDDEN; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
