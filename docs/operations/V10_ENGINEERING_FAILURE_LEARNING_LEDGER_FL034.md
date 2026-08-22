# FL-034 — PostgreSQL 18 existing-role retry must not restate privileged attributes

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR WP22A PHASE 4; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-22**  
WP / reference: **WP22A Phase 4 Render + Neon synthetic preview / deployment run `32566140673` on accepted main `3e6a50801e2ac8c75ab872a64d100a9a9424bc06`**

## Symptom / failing gate

The accepted-main Phase 4 deployment passed exact-main Regression Shield verification, all focused deployment-source tests, the zero-charge provider boundary, Neon Free-plan verification, Frankfurt project reuse, database connection and migrations. It then emitted:

`DATABASE_BOOTSTRAP_STAGE=RUNTIME_ROLE`

and stopped with the sanitized classification:

`PHASE4_FREE_PREVIEW=STOPPED code=DATABASE_BOOTSTRAP_FAILED`

The failure occurred before `DATABASE_BOOTSTRAP_STAGE=RUNTIME_GRANTS`.

## Root cause

The earlier PostgreSQL 18 correction fixed the automatic creator-admin membership semantics for a newly created runtime role, but the provisioner still used one SQL template for both first creation and idempotent retry:

`CREATE/ALTER ROLE ... LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD ...`

A previous provider attempt had already created `omni_cio_hosted_api`, so the accepted-main retry took the `ALTER ROLE` path.

PostgreSQL 18 allows a non-superuser `CREATEROLE` administrator with `ADMIN OPTION` to alter most properties of a role it administers, including its password, but non-superusers cannot change the `SUPERUSER` property and can change `CREATEDB`, `REPLICATION` and `BYPASSRLS` only when they possess the corresponding property themselves. Restating those privileged properties during an otherwise harmless password rotation therefore crosses the PostgreSQL 18 authorization boundary even when the requested values are the already-safe negative values.

The Neon bootstrap role is intentionally not a true PostgreSQL superuser. The retry must preserve that provider boundary rather than broadening bootstrap privileges.

## Blast radius searched

The review covered:

- the exact accepted-main deployment log and fixed bootstrap-stage markers;
- first-create versus existing-role branches in `scripts/provision_v10_render_neon_preview.py`;
- PostgreSQL 18 `CREATEROLE` / `ALTER ROLE` authorization semantics;
- the PostgreSQL 18 creator-admin membership correction already accepted through PR #366;
- `hosted-postgres-runtime.sql` effective-authority checks;
- runtime startup verification in `apps/api/hosted_preview.py`;
- the real PostgreSQL 18 CircleCI rehearsal;
- the Phase 4 accepted-main deployment-source test list;
- adjacent unsafe-existing-role and role-membership drift cases.

No Render resource, Neon plan, V9 service, tenant scope, broker credential, broker-write or Real-execution authority is widened.

## Why preflight missed it

The real PostgreSQL 18 rehearsal always dropped `omni_cio_hosted_api` before the test and therefore exercised only the first `CREATE ROLE` path. It proved the creator-admin membership shape and hosted grants, but it never ran the provisioner-equivalent convergence a second time against the already-existing role.

The deterministic tests likewise protected role creation and membership semantics but did not require an exact existing-role retry/password-rotation path.

## Corrective change

The runtime-role convergence is now split by state:

- a missing role is created with the complete least-privilege attributes;
- an existing role is first checked fail-closed for `NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`, `NOREPLICATION`, `NOBYPASSRLS` and zero outgoing memberships;
- any privileged attribute or membership drift stops before mutation;
- only a proven-safe existing role receives `ALTER ROLE ... LOGIN PASSWORD ...`;
- privileged negative attributes are not restated during retry;
- the same hosted SQL and runtime connection checks still verify the final authority boundary.

## Permanent regression / guard

The PostgreSQL 18 rehearsal now uses the exact provisioner convergence function and executes two passes against the same runtime role: initial creation followed by a second password rotation/convergence. Both passes recheck the creator-admin edge, hosted SQL and runtime login/attribute shape.

A deterministic retry test rejects every unsafe existing-role attribute, rejects memberships before mutation and requires the accepted-main Phase 4 workflow to run this guard before provider mutation.

## Future prevention rule

Any idempotent provider/database provisioner must test both `create` and `already exists` paths against the real target major version. A first-create rehearsal is not evidence for retry semantics. For PostgreSQL role convergence, validate privileged state before mutation and request only the minimum attributes that the current administrator is actually authorized to change.

## Dependency/tooling knowledge change

PostgreSQL 18 role administration distinguishes ownership/admin capability from privilege to change protected role attributes. `CREATEROLE + ADMIN OPTION` is sufficient for ordinary role administration and password rotation, but it is not equivalent to superuser and must not be treated as permission to restate every privileged role attribute during `ALTER ROLE`.
