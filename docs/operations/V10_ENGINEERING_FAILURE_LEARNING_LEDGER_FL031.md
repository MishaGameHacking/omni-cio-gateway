# FL-031 — PostgreSQL 18 creator-admin membership must not be mistaken for runtime authority

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR WP22A PHASE 4; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-22**  
WP / reference: **WP22A Phase 4 Render + Neon synthetic preview / accepted-main deploy run `32555714430` / PR #366**

## Symptom / failing gate

The exact accepted-main Phase 4 deployment on `4e10a04376523248cba8d5fa2ec8288de345e1e9` successfully verified the exact-main Regression Shield, passed the focused Phase 4 source tests, passed the zero-charge provider boundary, verified the Neon Free organization, and reused the Frankfurt-scoped Neon PostgreSQL 18 preview project.

The provider step then stopped before Render provisioning with:

`PHASE4_FREE_PREVIEW=STOPPED code=DATABASE_BOOTSTRAP_FAILED`

The original bootstrap catch intentionally suppressed raw database exceptions for secret safety, so the accepted-main run alone did not expose the failing PostgreSQL substage.

## Root cause

The Phase 4 provisioner creates or rotates the SQL runtime role `omni_cio_hosted_api` from the privileged Neon database-owner/bootstrap role and then applies `infrastructure/cloudru/wp22a/hosted-postgres-runtime.sql`.

PostgreSQL 18 automatically grants a role created by a non-superuser `CREATEROLE` user back to that creator with the administrative membership shape equivalent to:

`ADMIN=true, INHERIT=false, SET=false`.

That edge lets the creator administer the role but does not let it inherit the runtime role's ordinary privileges or `SET ROLE` into it. PostgreSQL documents that the automatic grant is system-created and cannot be removed or changed by the `CREATEROLE` user itself.

The accepted hosted-runtime SQL incorrectly rejected every `pg_auth_members` row where `roleid` was the runtime role. Therefore the legitimate PostgreSQL 18 creator-admin edge was classified as forbidden runtime membership during hosted-runtime grants/RLS bootstrap.

This is distinct from the protected requirement that the runtime role itself must not be a member of `neon_superuser`, predefined broad roles or any other role. That stricter direction remains unchanged.

## Deterministic reproduction and proof

PR #366 added PostgreSQL 18 rehearsals on the same pinned PostgreSQL 18 CircleCI image already used by the accepted supplemental lane.

Exact-head `27d7a52f847e0407209131740c38a2cf4efe1067` produced:

- `ci/circleci: supplemental_linux_postgres18` — **SUCCESS** / build `476`;
- `ci/circleci: supplemental_linux_phase4_pg18_creator_edge` — **SUCCESS** / build `477`;
- `ci/circleci: supplemental_linux_phase4_pg18_bootstrap` — **SUCCESS** / build `475`;
- `ci/circleci: supplemental_linux_governance` — **SUCCESS** / build `474`.

The creator-edge rehearsal uses a real non-superuser PostgreSQL 18 `CREATEROLE` bootstrap login, creates the exact runtime role and proves the returned membership tuple is exactly one creator row with `admin_option=true`, `inherit_option=false`, `set_option=false`.

The full bootstrap rehearsal additionally applies the committed migrations and executes the corrected hosted-runtime SQL successfully under that same role model. This closes the portability gap that the earlier WP13-only PostgreSQL lane did not exercise.

## Corrective change

The runtime-role guard now preserves both security requirements:

1. any row where `omni_cio_hosted_api` is itself a member of another role remains forbidden;
2. members *of* `omni_cio_hosted_api` are accepted only when there is at most one row and it belongs to the current bootstrap login with exact `ADMIN=true`, `INHERIT=false`, `SET=false` semantics.

Any additional member, different member, missing admin option, inherited access or `SET ROLE` access remains fail-closed with `HOSTED_API_USER_MEMBERS_PRESENT`.

The provisioner also emits fixed non-secret bootstrap stage markers before connection, migrations, runtime-role management, runtime grants, synthetic seeding and completion. Raw database exception messages, URIs, passwords, hostnames and provider bodies remain suppressed.

## Blast radius searched

The review covered:

- Neon organization/project/branch/database/connection discovery;
- PostgreSQL 18 role-creation semantics;
- migration execution;
- SQL creation/rotation of `omni_cio_hosted_api`;
- both directions of `pg_auth_members` authority;
- hosted runtime grants and FORCE RLS application;
- synthetic preview tenant/user seeding;
- the downstream Render service creation boundary;
- secret/logging controls around provider/database failures.

No broker, Real-execution, V9 production, public-registration or paid-resource authority is changed.

## Why preflight missed it

The existing supplemental PostgreSQL 18 lane exercised WP13 persistence semantics but did not create the Phase 4 runtime role through a non-superuser `CREATEROLE` login and did not execute `hosted-postgres-runtime.sql` under the resulting PostgreSQL 18 membership graph.

Static tests saw the old blanket `pg_auth_members` rejection as conservative and therefore could not distinguish a privileged runtime membership from PostgreSQL 18's administrative-only creator edge.

## Permanent regression / guard

Permanent protection now includes:

- fixed sanitized `DATABASE_BOOTSTRAP_STAGE` markers with raw exception suppression;
- source assertions for the exact creator-admin predicate;
- `supplemental_linux_phase4_pg18_creator_edge`, which proves PostgreSQL 18's real membership shape;
- `supplemental_linux_phase4_pg18_bootstrap`, which executes migrations plus the hosted-runtime bootstrap using that shape;
- the original supplemental PostgreSQL 18 persistence lane, which remains independently GREEN.

## Future prevention rule

Security review of role membership must distinguish the direction and effective privilege of each membership edge. A catalog row is not automatically evidence that the protected runtime role inherited authority.

For PostgreSQL version-sensitive authorization semantics, static SQL checks are insufficient when an inexpensive real PostgreSQL rehearsal is available. The CI gate must reproduce the exact role-creation context and inspect `admin_option`, `inherit_option` and `set_option` separately.

Provider-only workflows must also retain fixed stage-level diagnostics so a future external failure can be localized without leaking secret-bearing exception text.
