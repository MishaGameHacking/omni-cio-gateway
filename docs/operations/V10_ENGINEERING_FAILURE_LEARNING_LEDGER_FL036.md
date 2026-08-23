# FL-036 — Hosted runtime startup must not repeat privileged bootstrap writes

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR WP22A PHASE 4; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-22**  
WP / reference: **WP22A Phase 4 Render + Neon synthetic preview / deployment run `32596384401` on accepted main `60ced8498bd6ce64bdbbe04a63eed706d37098a6`**

## Symptom / failing gate

The accepted-main deployment passed the full exact-main and database bootstrap chain:

- exact-main Regression Shield re-verification passed;
- focused Phase 4 source tests passed;
- zero-charge/provider boundary passed;
- Neon Free PostgreSQL 18 project was reused;
- migrations, runtime-role convergence, grants, synthetic seed and runtime connection verification passed;
- the existing Render Free preview service was reused.

Render then terminated the exact accepted-main deployment with the attempt-correlated sanitized classification:

- `RENDER_DEPLOY_STATUS=update_failed`;
- `RENDER_DEPLOY_REASON=NON_ZERO_EXIT`;
- `RENDER_DEPLOY_DIAGNOSTIC=PASS`.

This moved the defect from an unknown provider failure to a deterministic application-startup failure class.

## Root cause

The provider bootstrap already creates and verifies the synthetic preview tenant and user with the privileged bootstrap connection before the Render runtime URI is issued.

`apps/api/hosted_preview.py` nevertheless repeated that bootstrap during every application process start through `_bootstrap_synthetic_scope()`. Its first statement was:

`INSERT INTO omni_cio_v10.tenants ... ON CONFLICT (tenant_id) DO NOTHING`

The accepted hosted PostgreSQL least-privilege contract intentionally grants the runtime role `INSERT` on `omni_cio_v10.tenants` but **not** `SELECT`. It also revokes public table privileges and forbids runtime role memberships, so there is no alternate SELECT authority.

PostgreSQL 18 requires `SELECT` privilege on columns referenced by every `ON CONFLICT` conflict target, including `tenant_id`. Therefore the runtime startup statement is incompatible with the accepted runtime grant surface and raises insufficient privilege before the FastAPI process can become healthy.

The defect is an ownership mismatch: privileged provider bootstrap and least-privilege runtime startup both attempted to own synthetic seed convergence, even though only the bootstrap boundary has the authority required for idempotent conflict inspection.

## Blast radius searched

The review covered:

- accepted-main Phase 4 run `32596384401` and its exact sanitized Render diagnostic;
- Render build/start/deploy semantics for failed start/update commands;
- `apps/api/hosted_preview.py` factory startup sequence and health probe;
- `scripts/provision_v10_render_neon_preview.py` synthetic seed and exact digest verification;
- `infrastructure/cloudru/wp22a/hosted-postgres-runtime.sql` runtime grants and public privilege revocation;
- `infrastructure/cloudru/wp22a/hosted-postgres-runtime-contract.json` plus `omni_cio/persistence/hosted_postgres_runtime_v1.py` exact privilege contract;
- PostgreSQL 18 `INSERT ... ON CONFLICT` privilege requirements;
- `omni_cio/web/product_identity_v1.py` account creation path, which uses ordinary tenant `INSERT` rather than an `ON CONFLICT` tenant upsert;
- PostgreSQL 18 runtime-role rehearsal coverage;
- hosted preview unit tests and why they did not instantiate the real database-backed factory;
- adjacent risks from widening tenant SELECT authority merely to make startup pass.

No runtime grant is widened by the correction. Protected V9 `app:app`, provider authority, public registration, broker authority, Real execution and WP23 boundaries remain unchanged.

## Why preflight missed it

The existing hosted preview tests exercised `create_hosted_preview_app()` with in-memory session services rather than the real `create_app()` database-backed startup path.

The PostgreSQL 18 rehearsal proved runtime-role attributes, membership constraints, grants and password rotation, but it did not seed the preview identity and execute the same read path required at hosted application startup.

Before FL-035 was accepted, the provider failure also lacked a safe terminal class. After FL-035 landed, the next accepted-main retry correctly produced `update_failed / NON_ZERO_EXIT`, which made a startup privilege mismatch the directly relevant failure domain.

## Corrective change

Make provider bootstrap the sole owner of synthetic preview seed mutation and keep hosted runtime startup read-only:

- remove runtime startup tenant/user upserts;
- verify the provider-seeded synthetic user through the already-authorized `users` SELECT surface;
- include the exact synthetic user record digest in the startup/readiness verification;
- combine structural PostgreSQL/runtime-role checks and synthetic-scope verification into the recurring hosted database probe;
- preserve `tenants` as INSERT-only for the hosted runtime instead of granting cross-tenant SELECT merely to satisfy `ON CONFLICT`;
- keep the existing provider bootstrap exact tenant/user digest verification unchanged.

## Permanent regression / guard

The correction adds two complementary guards:

1. focused hosted-preview tests prove synthetic-scope startup verification performs one read-only `SELECT`, contains no `INSERT` or `ON CONFLICT`, and fails closed on record drift;
2. the real PostgreSQL 18 Phase-4 rehearsal seeds the synthetic scope through bootstrap authority, then verifies it through the actual least-privilege runtime role while explicitly proving runtime `SELECT` on `omni_cio_v10.tenants` remains absent. The same check is repeated after runtime password convergence.

This closes the previous gap between grant-contract testing and application-factory startup behavior.

## Future prevention rule

For every hosted runtime SQL path, privilege review must be performed against the **complete SQL statement semantics**, not only the headline verb. In PostgreSQL, UPSERT/conflict handling, `RETURNING`, update predicates and similar clauses can require additional privileges beyond `INSERT` or `UPDATE`.

Bootstrap/migration boundaries and long-lived runtime boundaries must have one explicit owner for initialization writes. If a privileged accepted-main bootstrap already creates and verifies immutable synthetic/bootstrap state, application startup should verify that state with existing least privilege rather than repeat privileged convergence.

Never widen cross-tenant runtime read authority simply to make an idempotent startup statement succeed when the mutation belongs to the bootstrap boundary.

## Dependency/tooling knowledge change

PostgreSQL 18 documents that all `ON CONFLICT` forms require `SELECT` privilege on columns read by the conflict target. This is a statement-level privilege property and must be included in future least-privilege reviews and rehearsals.

Render's accepted diagnostic classification `update_failed / NON_ZERO_EXIT` is sufficient to identify a failed application start/update command class without copying raw provider logs into GitHub Actions.
