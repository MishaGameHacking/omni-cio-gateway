# V10 Timeweb PostgreSQL 18 Production Cutover Runbook

Scope: P3 of `TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED` in PR #584.

This runbook never authorizes public users, Telegram activation, DNS changes, broker write, or Real Trading. Secret DSNs, passwords, provider tokens, backup identifiers, and private account identifiers must not be written to GitHub, chat, CI logs, screenshots, or artifacts.

## Production target rule

The production PostgreSQL target must be a Timeweb Cloud Managed PostgreSQL 18 database that is distinct from the historical synthetic parity target. Do not promote a synthetic database containing test Tenant/User/session fixtures into production.

The runtime login is `omni_cio_hosted_api`. It must already exist through the accepted Timeweb provider-user boundary. The P3 controller does not create the login and does not rotate its password. It only applies canonical migrations and provider-neutral runtime ACL/RLS bootstrap to the verified production database.

Both bootstrap and runtime DSNs must use `sslmode=verify-full` and an explicit `sslrootcert`. Retired-provider database hosts are rejected.

## Ordered execution

1. PR #584 P2 source and exact-head verification is GREEN.
2. After the implementation is accepted on protected `main`, invoke the P3 workflow with the exact accepted main SHA and `operation=observe`.
3. Provision or identify the dedicated production PostgreSQL 18 database and the pre-existing `omni_cio_hosted_api` login without exposing credentials.
4. Run `operation=prepare` with confirmation `PREPARE_TIMEWEB_PRODUCTION_POSTGRES`.
5. The controller verifies PostgreSQL 18/TLS, applies canonical migrations twice to prove retry idempotence, applies the canonical runtime ACL bootstrap, verifies the least-privilege runtime role, RLS/FORCE-RLS, tenant security constraints, and requires clean product identity/session/broker tables.
6. Create a Timeweb physical backup recovery point. Physical backup is mandatory and additive to the repository logical recovery contract.
7. Perform a separate restore rehearsal. If Timeweb exposes no documented safe API for the required recovery operation, use the bounded Timeweb panel action. Do not invent an undocumented endpoint.
8. Record recovery acceptance through the manual workflow input `recovery_attestation=TIMEWEB_PHYSICAL_BACKUP_AND_SEPARATE_RESTORE_REHEARSAL_ACCEPTED` and provide `recovery_evidence_sha256` as the SHA-256 of sanitized external recovery evidence. The attestation and digest are not credentials and must not be stored as Actions secrets. Never record provider backup IDs, raw backup payloads, credentials, or private account identifiers in source or CI output.
9. Promote the verified production runtime DSN to the existing Timeweb App Platform application through documented provider controls. P3 source intentionally does not patch App Platform settings because no undocumented settings endpoint is allowed.
10. Run `operation=accept`. The controller re-verifies the production database and then read-only verifies that Timeweb App Platform holds the same runtime DSN, the exact accepted main SHA, and both public-user activation flags remain false.
11. Only after P3 acceptance may P4 canonical `omnicio.ru` DNS/TLS cutover begin.

## Failure and recovery

Any SHA mismatch, TLS downgrade, migration drift, widened runtime role, RLS/FORCE-RLS drift, non-empty clean-target tables, missing recovery attestation or evidence digest, App Platform DSN mismatch, or public-user flag enablement is `DEPLOYMENT_BLOCKED`.

Do not repair a failed P3 by dropping schemas, truncating data, weakening RLS, granting broad predefined roles, bypassing certificate verification, changing CI assertions, or enabling public users.

The last-known-good application release remains the application rollback target. Database recovery uses the accepted Timeweb physical backup plus the provider-neutral logical recovery contract. P3 acceptance does not authorize destructive removal of older recovery points.
