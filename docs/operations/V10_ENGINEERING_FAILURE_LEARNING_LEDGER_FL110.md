# V10 Engineering Failure Learning Ledger — FL110

## Failure class

`CF_D_STAGING_DATABASE_REUSE_GATED_BY_UNNECESSARY_NEON_MANAGEMENT_API_PREFLIGHT`

## Accepted evidence

On exact accepted `main` `6b28198550adc09a001de8779df900b13caa5c42`, the post-merge Cloudflare production release reused the already-accepted staging PostgreSQL runtime secret and reached exact Worker + Container staging acceptance. The one-time production database bootstrap remained separately RED.

After the canonical `system/cloudflare-public-product` branch was recreated from that exact main, the automatic provider-readiness workflow failed before any useful branch mutation because it unconditionally required Neon management-API exact-project authority. The bounded diagnostic was `NEON_PROJECT_KEY_BINDING_MISMATCH status=403`.

Independent database evidence confirms the canonical PostgreSQL 18 database and the existing staging runtime role remain healthy. Therefore the management API is not required merely to re-prove or rotate an already-accepted staging runtime credential.

No provider identifier, credential, DSN, token, private hostname or portfolio payload is recorded here.

## Root cause

The branch-side readiness and candidate workflows retained the older bootstrap assumption:

`candidate verification -> Neon management API authority -> recreate/converge staging role -> staging deployment`

That assumption conflated two different states:

1. normal release/rehearsal with an existing protected staging runtime secret; and
2. recovery/bootstrap when the staging runtime secret is actually absent.

The accepted post-merge production workflow had already evolved to the correct secret-first behavior, but the branch-side readiness/candidate workflows had not. This was a producer/consumer policy drift.

## Blast radius

Directly coupled surfaces:

- `.github/workflows/v10-cloudflare-provider-readiness.yml`;
- `.github/workflows/v10-cloudflare-candidate-deploy.yml`;
- `scripts.probe_v10_cloudflare_staging_runtime_secret`;
- `scripts.provision_v10_cloudflare_neon_runtime`;
- `scripts.run_v10_cloudflare_gated_candidate`;
- `docs/architecture/V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json`;
- deterministic candidate/provider authority tests.

The defect could also cause unnecessary staging password rotation whenever a branch candidate is verified, which conflicts with the stable database lifecycle required by the final Cloudflare + Neon convergence law.

## Correction

The staging database authority sequence is now explicit:

`probe protected staging runtime secret`

- present -> reuse the existing runtime credential and do not require Neon management API;
- missing -> require exact-project Neon management API authority, then provision/converge the staging role once;
- malformed/unreadable provider state -> fail closed.

The management API remains available as a recovery/bootstrap control-plane capability. It is not weakened or bypassed when it is actually required.

## Prevention law

1. Persistent runtime secrets/roles are reused by default.
2. Management-plane authority is required only for a management-plane mutation that is actually necessary.
3. A stale or unavailable optional recovery credential must not block a healthy normal runtime/release path.
4. Missing runtime state must never be converted to synthetic GREEN; it activates the exact recovery authority gate.
5. Machine-readable release contracts and deterministic tests must encode this distinction.

## Protected invariants

Unchanged:

- protected V9 `app:app`;
- `PUBLIC_MULTI_USER_ENABLED=false` until its own accepted live gate;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- broker write, transfer, withdrawal, margin, leverage and uncovered short remain OFF/FORBIDDEN;
- no Web Visual, Telegram/VK, AI/Cortex or Real execution scope;
- no D1 or speculative Hyperdrive migration;
- no credential/provider-identifier disclosure.
