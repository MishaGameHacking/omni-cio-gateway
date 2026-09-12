# V10 Engineering Failure Learning Ledger — FL127

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `MAIN_RED_STOP`
- Failure class: `CF_D_NEON_FUNCTION_SOURCE_CONVERGENCE_WRITE_AUTHORITY_DEADLOCK`
- Scope: exact-source Neon Function provenance/convergence authority in the CF-D staging rehearsal and its release contract only

## Observed failure

Exact accepted `main` `215fc4d5b31ea9bcb852c5f9a52f8c23a7c8951c` reached the CF-D staging rehearsal in Production Release #47. The isolated staging database secret and Worker anchor were reused, stale staging build activity was quarantined, the exact-SHA gated build succeeded, the staging Worker reached one exact active version, the release probe matched the exact SHA, and bootstrap-origin custody completed. The step then terminated with the sanitized failure:

`CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY_API_KEY_INSUFFICIENT status=403`

Production promotion, custom-domain mutation and live acceptance did not run. Cleanup/quarantine completed.

No Function URL, project/branch identifier, API key, OIDC token, database credential or private payload is recorded here.

## Root cause

The current accepted source changed the source-provenance wrapper so canonical `GET /` is the bounded read-only source proof while privileged bootstrap remains `POST /`. The currently active provider Function deployment predates that accepted source. Therefore the deterministic wrapper+handler digest correctly reports source drift and the release enters its conditional Function deployment path.

That path used the same `NEON_API_KEY` for both read-only project/function state inspection and the mutating deployment `POST`. The credential is intentionally least-privilege and can read the required state but is not authorized to create a Function deployment. The provider therefore correctly returns 403. This creates a deterministic self-bootstrap deadlock: the release can prove that the Function source is stale, but the one credential exposed to that code path cannot converge the stale Function to the exact source whose provenance route would then permit future read-only reuse.

This is not a Cloudflare build failure, PostgreSQL failure, staging-secret failure, transient network condition or reason to weaken exact-source verification. Re-running the unchanged source without resolving the authority mismatch is expected to repeat the failure.

## Permanent correction

- Keep `NEON_API_KEY` as the read/inspection authority used for project, branch, Function state and post-deploy polling.
- Introduce a distinct secret binding `NEON_FUNCTION_DEPLOY_API_KEY` for the Function deployment `POST` only.
- Load the write credential lazily only after deterministic exact-source provenance proves drift; exact-source reuse must not require mutation authority.
- Reject a missing write credential on proven drift with an explicit fail-closed code.
- Reject identical read/write credentials so the split cannot silently collapse back into one over-broad shared key.
- Mask the write credential before use and never reflect provider response bodies, identifiers or secret material into logs.
- Use the write credential only for the deployment mutation. Continue polling and active/current deployment verification with read authority.
- Align the provenance probe and release contract with the accepted wrapper: literal `GET /` is sufficient; no query, custom header or User-Agent discriminator is required for correctness.
- Preserve exact deterministic source digest comparison, TLS hostname/certificate verification, no redirects, bounded responses, deployment-race checks, active/current completed deployment equality, OIDC bootstrap authority and production rollback gates.

The preferred external credential is project-scoped to the one Neon project and grants only the authority actually required for Function deployment, rather than broadening the existing read credential.

## Blast radius and adjacent review

Directly coupled surfaces inspected and corrected:

- `.github/workflows/v10-cloudflare-production-release.yml`;
- `scripts/deploy_v10_cloudflare_neon_bootstrap_function.py`;
- `docs/architecture/V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json`;
- Function deployment/provenance/Neon-authority regression tests.

Downstream CF-D steps were inspected: exact-main staging acceptance, domain validation, production Worker anchor, OIDC production database bootstrap, stale-build quarantine, rollback snapshot, exact-current-main recheck, gated production build, custom-domain attachment, live acceptance and bounded rollback. No independent current source defect is proven in those paths by this incident, so they are not weakened or speculatively rewritten.

The Function handler, PostgreSQL schema/roles/grants/RLS, Cloudflare runtime code, product authentication, tenant selection, V9 recovery and broker/Real-money surfaces are unchanged.

## Permanent regression / guard

Deterministic tests require:

- exact-source reuse to complete without reading the deployment-write credential;
- source drift to require `NEON_FUNCTION_DEPLOY_API_KEY` explicitly;
- identical read/write credentials to fail closed;
- write credentials to be masked before mutation;
- deployment 403 to be classified specifically as insufficient write authority;
- the deployment key to be scoped only to the staging rehearsal workflow step that can execute Function source convergence;
- direct production database bootstrap to remain GitHub-OIDC-only and contain no static Neon management credential;
- the provenance probe and release contract to use canonical root `GET /` without metadata dependence;
- post-deploy polling and exact active/current Function state verification to continue using read authority.

Full exact-head lint/type/tests/security/review gates remain mandatory. Any replacement SHA invalidates prior final evidence.

## Prevention law

Control-plane observation and provider mutation are separate capabilities and must not be represented by one credential merely because they target the same provider. A self-updating release component must prove drift with read authority first, acquire the narrow mutation authority only when drift is real, and return to read authority for convergence verification. Credential presence is never equivalent to capability authorization.

## Protected invariants

Unchanged: protected V9 `app:app`; `PUBLIC_MULTI_USER_ENABLED=false`; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; broker write, transfer, withdrawal, margin, leverage and uncovered short remain OFF/FORBIDDEN; PostgreSQL 18 + RLS/FORCE RLS remains relational truth; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
