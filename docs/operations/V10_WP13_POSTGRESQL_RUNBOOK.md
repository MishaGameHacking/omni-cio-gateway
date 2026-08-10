# Omni-CIO V10 WP13 — PostgreSQL persistence runbook

Status: **WP13 implementation runbook / not production activation authority**  
Authority: `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md` and `docs/architecture/V10_WP13_POSTGRESQL_PERSISTENCE_CONTRACT.md`

## Purpose

This runbook covers only the WP13 local PostgreSQL schema/migration boundary and synthetic acceptance/recovery rehearsal. It does not activate the WP14 durable job runtime, WP15 broker-read integration, Web/Telegram/Cortex or Real execution.

## Database boundary

- PostgreSQL major: 18; reviewed node patch baseline: 18.4.
- Application schema: `omni_cio_v10`.
- Migration source: `omni_cio/persistence/migrations/*.sql`.
- Migration metadata: `omni_cio_v10.schema_migrations`.
- Canonical financial quantities use exact PostgreSQL `numeric`; binary floating-point and PostgreSQL `money` are not canonical financial storage.
- Persisted instants use `timestamptz` and are returned through timezone-aware contract boundaries.
- Audit-sensitive canonical records are append-only. A correction is a new domain revision/event, not an in-place history rewrite.
- Deterministic durable-state digests encode `Decimal` values as fixed-point canonical text, preventing exponent-notation differences from changing recovery hashes for numerically identical exact values.

## Secret boundary

Database authentication is supplied separately by the local runtime secret boundary/libpq environment. Do not place database passwords in Git, workflow YAML, command-line arguments, logs or evidence artifacts. The WP13 acceptance rehearsal deliberately creates a temporary loopback-only PostgreSQL cluster with synthetic trust authentication and no production/private data.

## Migration procedure

Application bootstrap must call the WP13 migration runner before state mutation. The runner:

1. requires PostgreSQL major 18;
2. takes the WP13 transaction-scoped advisory migration lock;
3. creates/reads migration metadata;
4. verifies every previously applied migration name and SHA-256;
5. applies only the next immutable migration in the same transaction that records it;
6. fails closed on checksum drift, unknown version or SQL failure.

The default rollback strategy is forward recovery. Once private durable state exists, do not invent destructive down-migrations merely to run older code. Use a reviewed forward repair migration or restore a verified compatible backup while preserving broker/execution reconciliation truth.

## Synthetic acceptance rehearsal

Authoritative CI runs:

`infrastructure/windows/rehearse_wp13_persistence.ps1`

The rehearsal creates an isolated temporary PostgreSQL 18 cluster and synthetic source DB, then proves:

- concurrent migration application serializes to one migration;
- clean schema bootstrap and migration replay;
- OWNER/scope constraints;
- exact `Decimal`/`numeric(38,18)` round-trip;
- append-only update/delete rejection;
- immutable replay idempotency and conflicting replay rejection;
- two concurrent identical incident-revision writes serialize on the incident identity and converge on one durable state revision rather than producing a duplicate revision or uniqueness failure;
- bounded cache expiry;
- deterministic migration and durable-state digests;
- WP10 logical `pg_dump` bundle creation/hash verification;
- intentional corrupt-copy rejection;
- restore to a separate database;
- exact migration-series/state-digest parity after restore.

Only sanitized hashes, booleans, migration count/revision and duration may become CI evidence. The focused audit emits only sanitized probe exception classes, explicit empty-output classifications, and sanitized PowerShell exception/error identifiers when a synthetic rehearsal fails. Diagnostic formatting must remain parser-safe under the Windows PowerShell runtime used by the Lenovo acceptance lane. Native probe stdout/stderr is captured through isolated temporary files so Windows PowerShell error-stream conversion cannot hide the probe's sanitized failure classification or turn an expected corrupt-backup rejection into an unrelated shell failure. It never needs raw DSNs, secret-bearing paths or payload content for diagnosis. The temporary cluster is deleted after the rehearsal.

## Production binding rule

WP13 may identify the V10 product PostgreSQL schema/database contract for WP10 recovery, but it must not independently enable the scheduled production backup task. WP14 owns durable job/task runtime binding. Existing WP10 OWNER-controlled encrypted off-device recovery remains the authority for encryption/media custody; WP13 does not repeat or synthesize OWNER physical evidence.

## Failure handling

Any migration, constraint, persistence or restore-digest mismatch is a hard failure. Do not fall back to volatile in-memory state for canonical durable facts and do not weaken constraints/checks to make CI green. Diagnose the exact failing migration/query on synthetic data, fix the root cause on the WP13 branch, then rerun the exact-head authoritative gates.

A Ruff format failure is also a real code-quality failure. Apply the Ruff version exercised by the protected acceptance lane only to the affected WP13 source, keep the formatting check enabled, and rerun the complete exact-head gates rather than treating a formatter-only correction as acceptance evidence.

A workflow run that completes as `action_required` without executing jobs is not acceptance evidence. After any automation-authored correction, obtain fresh exact-head jobs from an accepted repository actor before considering an Exit Gate satisfied.

## V9 protection

WP13 does not modify the protected V9 `app:app` runtime, `trading_methods=false` behavior, `REAL_TRADING_ENABLED=false` kill switch, or broker-write authority. V9 remains the product rollback while Block D is incomplete.
