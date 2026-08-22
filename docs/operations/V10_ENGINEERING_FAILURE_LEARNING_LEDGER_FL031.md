# FL-031 — Provider bootstrap failures need safe stage evidence

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR WP22A PHASE 4; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-22**  
WP / reference: **WP22A Phase 4 Render + Neon synthetic preview / accepted-main deploy run `32555714430`**

## Symptom / failing gate

The exact accepted-main Phase 4 deployment on `4e10a04376523248cba8d5fa2ec8288de345e1e9` successfully verified the exact-main Regression Shield, passed the focused Phase 4 source tests, passed the zero-charge provider boundary, verified the Neon Free organization, and reused the Frankfurt-scoped Neon PostgreSQL 18 preview project.

The provider step then stopped with only:

`PHASE4_FREE_PREVIEW=STOPPED code=DATABASE_BOOTSTRAP_FAILED`

No Render service was created because the deployment sequence does not enter Render provisioning until the database bootstrap is complete.

## Root cause of the diagnostic gap

`_bootstrap_database()` intentionally suppressed raw database exceptions to keep credentials, connection URIs and provider details out of GitHub logs. That secret-safety decision was correct, but one broad catch covered several materially different operations: direct Neon connection, migrations, runtime-role provisioning, hosted-runtime grants/RLS setup and synthetic preview seeding.

The single generic failure code therefore preserved secrecy but did not preserve enough sanitized stage evidence to distinguish the failing boundary safely.

This entry does **not** guess the underlying Neon/PostgreSQL failure. The exact database root cause must be established from a later accepted-main run after the stage evidence is present.

## Blast radius searched

The review covered:

- the canonical Phase 4 provider workflow;
- Neon organization/project/branch/database/connection discovery;
- PostgreSQL 18 migration execution;
- SQL creation/rotation of the least-privilege `omni_cio_hosted_api` role;
- hosted runtime grants and FORCE RLS application;
- synthetic preview tenant/user seeding;
- the subsequent Render service creation boundary;
- secret/logging rules that forbid raw provider/database error bodies and connection data.

The current evidence proves that Render Git repository access, the Render no-card attestation, the exact-main Regression Shield and Neon Free project discovery are not the failing stages in run `32555714430`.

## Why preflight missed it

The source tests validated provider contracts, safe URI handling, exact-main authority and the provisioner launch mode. They did not exercise the real Neon database connection with repository secrets on a pull request, which is intentionally forbidden. The accepted-main provider run was therefore the first place where this external database boundary could fail.

The provisioner also lacked fixed, non-secret stage markers, so the first real external failure could not be localized without another source change.

## Corrective change

Keep the raw exception suppression and generic terminal code, but emit fixed sanitized stage markers immediately before each risky database bootstrap phase:

- `CONNECT`;
- `MIGRATIONS`;
- `RUNTIME_ROLE`;
- `RUNTIME_GRANTS`;
- `SYNTHETIC_SEED`;
- `COMPLETE`.

The markers contain no hostname, database URI, username, password, SQL text, provider response body or exception message. The last emitted marker before `DATABASE_BOOTSTRAP_FAILED` identifies the failing phase while preserving the existing secret boundary.

## Permanent regression / guard

`tests/test_wp22a_phase4_deploy_contract.py` verifies that every fixed marker occurs exactly once, in execution order, and that the bootstrap block does not log `str(...)` or `repr(...)` exception data. The existing generic terminal failure remains fail-closed.

## Future prevention rule

When a secret-bearing accepted-main/provider-only path contains several distinct external operations under one sanitized exception boundary, preserve both requirements:

1. never expose raw provider/database exceptions or secret-bearing values;
2. emit fixed stage-level evidence sufficient to localize the failed boundary without another speculative debugging cycle.

Do not replace safe classification with verbose exception logging merely to speed diagnosis.

## Dependency/tooling knowledge change

External managed PostgreSQL behavior can differ from local PostgreSQL even when SQL and transaction semantics are valid. Provider-only acceptance must therefore retain safe stage observability around connection, migration and privilege boundaries instead of assuming a local PostgreSQL rehearsal proves the external path end to end.
