# V10 Engineering Failure Learning Ledger — FL131

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `RED_REPAIR_ONLY`
- Failure class: `CF_D_BOUNDED_INVOKE_AUTHORITY_STALE_SECURITY_REGRESSIONS`
- Scope: directly coupled CF-D regression contracts after the bounded Neon Function invoke-authority change in PR #496

## Exact-head evidence

PR #496 exact head `79079706c4a873216fb379a51b29bc7e43dd1085` reached the authoritative `Self-Hosted Windows CI` merge gate. Bootstrap/runtime/dependency/PostgreSQL 18 checks, repository and CI-policy contracts, compile, Ruff lint, Ruff format, mypy, protected `app:app`, and the read-only GPT Actions contract all passed. The Regression Shield then reported `8 failed, 3096 passed`, with branch coverage still above the protected threshold.

The failures were not provider/runtime failures. They were deterministic repository regressions in four directly coupled test modules that still encoded the superseded security assumption that no outer Neon Function invocation authority could ever be present:

- two direct-bootstrap tests expected an unauthenticated provider 403 to terminate immediately instead of entering the new bounded `functions:invoke` fallback before real GitHub OIDC mint;
- one transport-contract assertion still required the outer `Authorization` header to be forbidden unconditionally;
- two workflow authority tests still forbade the exact project credential and project id from the production bootstrap-if-missing step and assumed the Function deploy binding appeared in only one step;
- one deployment-contract test still required exact-source reuse to be management-API-free and deploy authority to be required only after source drift.

The same exact head had a successful SonarQube Quality Gate with zero new issues and zero new Security Hotspots. That did not make the head GREEN because the authoritative Regression Shield remained failed.

## Root cause

The production security boundary changed deliberately from one layer to two strictly separated layers:

1. an outer, branch-scoped, ephemeral Neon `functions:invoke` credential may be used only after the unauthenticated provider edge returns the exact bounded pre-handler 403;
2. the source-controlled bootstrap handler still requires and validates the inner GitHub OIDC carried in `X-Omni-GitHub-OIDC`.

New focused tests were added for this boundary, but all older negative tests that consumed the same workflow, contract and bootstrap code were not updated in the same checkpoint. Those tests therefore continued to assert the old absence-of-authority model instead of the new least-authority model.

This was a producer/consumer review completeness defect. Weakening or deleting the old security tests would have been incorrect; they needed to be rewritten to prove the replacement boundary precisely.

## Blast radius and directly related consumers

The repair reviewed and updated the stale assertions in:

- `tests/test_v10_cloudflare_cf_d_direct_bootstrap_control_plane.py`;
- `tests/test_v10_cloudflare_cf_d_preflight_body_provenance.py`;
- `tests/test_v10_cloudflare_neon_authority_preflight.py`;
- `tests/test_v10_cloudflare_neon_function_deployment.py`.

The directly related producers remain:

- `scripts/bootstrap_v10_cloudflare_production_database_direct.py`;
- `scripts/deploy_v10_cloudflare_neon_bootstrap_function.py`;
- `scripts/neon_function_invocation_credential.py`;
- `.github/workflows/v10-cloudflare-production-release.yml`;
- `docs/architecture/V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json`.

No V9, broker, Real-money, Telegram, AI/Cortex or later-WP surface is in scope.

## Permanent correction

The old negative tests now preserve their security purpose while asserting the exact replacement model:

- an unauthenticated provider 403 may load only the bounded Neon invocation fallback, but real GitHub OIDC must not be minted until an authenticated source-controlled preflight succeeds;
- source-controlled handler failures do not trigger provider-authority fallback;
- the outer `Authorization` header is allowed only in the explicit `NEON_FUNCTION_INVOKE_ONLY` role, while the inner GitHub OIDC remains mandatory;
- the production bootstrap step may receive exactly `NEON_FUNCTION_DEPLOY_API_KEY` and `NEON_PROJECT_ID` for bounded invocation fallback, but not the staging recovery alias, org-wide authority, provisioning path, variables-based authority or secret logging;
- the Function project credential is scoped to exactly the staging candidate step and the production bootstrap-if-missing step;
- canonical contract assertions now require unauthenticated-first probing, reject 403-as-success, require exact `functions:invoke`, ephemeral/no-persistence/revoke-after-use/no-broader-scope custody, and record that management authority can be required even when the deployed source is already exact.

## Prevention law

When a security authority boundary is intentionally replaced rather than removed, search and update every directly related negative test, contract consumer and workflow-scope assertion in the same checkpoint. Do not satisfy an old absence assertion by weakening the new least-authority boundary, and do not rely only on newly added positive tests. The full Regression Shield is the authoritative proof that all legacy consumers have converged on the replacement contract.

## Protected invariants

Unchanged: protected V9 `app:app`; `PUBLIC_MULTI_USER_ENABLED=false`; PostgreSQL 18 + RLS/FORCE RLS; broker write OFF; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; transfer/withdrawal/margin/leverage/uncovered-short remain OFF/FORBIDDEN; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
