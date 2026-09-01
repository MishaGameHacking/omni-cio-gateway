# V10 Engineering Failure Learning Ledger — FL070

## Scope

Current System Update: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`, CF-C live candidate acceptance.

This entry records the exact-head runtime failure on `6937766968828905024f6a72d0fc4adedc8e3ae1`. It does not grant CF-C acceptance and does not authorize CF-D.

## Exact failure evidence

Candidate run `33394553539` proved the following on the exact head:

1. provider readiness passed;
2. Workers Builds authority passed;
3. Containers registry read authority passed;
4. isolated Neon staging provisioning passed as role `omni_cio_cloudflare_staging`;
5. the staging Worker anchor passed;
6. the exact-SHA manual Worker + Container build passed after the FL069 trigger-lifecycle correction;
7. `/api/v10/release` repeatedly returned the exact source SHA successfully;
8. container-backed `/healthz` remained HTTP 500 through the bounded acceptance window;
9. the cleanup/quarantine path completed and no production promotion occurred.

The same exact head also reached authoritative Windows static quality, where the only source-side failure was `ruff format --check` on the two FL069 orchestration files. Those formatting findings are folded into this correction batch rather than published as a separate symptom-only commit.

## Root cause

The Cloudflare runtime reused the historical WP22A hosted-preview database probe. That accepted historical probe requires `current_user = omni_cio_hosted_api`.

CF-C intentionally provisions separate least-privilege Cloudflare roles:

- staging: `omni_cio_cloudflare_staging`;
- production: `omni_cio_cloudflare_prod`.

The candidate DSN was therefore valid and successfully provisioned, but the container rejected its own accepted Cloudflare staging identity during startup/health validation because the reused historical probe asserted the Render-era role name.

The defect is a provider-runtime adapter mismatch, not a database permission failure and not a reason to broaden role privileges.

## Blast radius

- Cloudflare staging runtime startup and health.
- Future Cloudflare production runtime startup and health.
- Any Cloudflare health/database probe that reused the historical hosted role assertion.
- The historical WP22A hosted-preview role itself is not defective and must remain unchanged for historical/recovery semantics.

## Correction

Use `WRAP_ADAPTER` rather than mutating the accepted historical hosted-preview probe:

1. source-control an explicit non-secret Cloudflare runtime-role binding for each Wrangler environment;
2. production default binds `omni_cio_cloudflare_prod`;
3. staging binds `omni_cio_cloudflare_staging` because Wrangler `vars` are non-inheritable;
4. pass the binding from Worker to Container through `envVars` alongside the separately secret DSN;
5. validate the role against the two exact allowed Cloudflare identities at both Worker and Python runtime boundaries;
6. add a Cloudflare-specific database probe preserving PostgreSQL 18, no-membership, required-schema, FORCE-RLS, and synthetic-scope checks;
7. refuse the historical `omni_cio_hosted_api` role inside the Cloudflare runtime rather than weakening the check;
8. add machine-contract and deterministic negative tests for production/staging role drift, missing/invalid role binding, memberships, and FORCE-RLS regression;
9. preserve the accepted historical hosted-preview probe unchanged;
10. format the two FL069 files under the repository-pinned Ruff baseline in the same coherent correction batch.

## Why prior preflight missed it

CF-B source compatibility proved the direct Neon/PostgreSQL 18 path and runtime secret boundary but treated reuse of `_probe_hosted_preview_database` as parity. The preflight did not compare the historical probe's hardcoded role identity with the new environment-specific role names introduced by CF-C provisioning.

The permanent guard now binds provisioning identity, Wrangler environment configuration, Worker-to-Container environment composition, Python runtime allowlist, and database health validation as one coupled contract.

## Security and authority invariants preserved

- Runtime roles remain least privilege; no role is broadened.
- The PostgreSQL DSN remains a Cloudflare secret, not a Wrangler `vars` value.
- The role name is non-secret configuration and contains no credential material.
- PostgreSQL 18, zero inherited memberships, required schema, and FORCE-RLS remain mandatory.
- Historical WP22A/Render behavior is not rewritten.
- No CF-D production promotion occurs in this correction.
- `PUBLIC_MULTI_USER_ENABLED=false` remains protected.
- Telegram/VK remain blocked on their own provider gates.
- Broker write remains OFF; `trading_methods=false`; `REAL_TRADING_ENABLED=false`.

## External contract revalidation

Revalidated on 2026-08-31 against first-party Cloudflare Workers documentation:

- Wrangler `vars` are non-inheritable and must be declared explicitly for each named environment;
- non-secret `vars` are Worker bindings available through the Worker environment;
- Container runtime variables may be supplied through Container `envVars`;
- secrets remain separate and must not be moved into plaintext `vars`.

Provider documentation supports the configuration shape only. Real exact-head CF-C live acceptance remains mandatory evidence.
