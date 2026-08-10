# Omni-CIO V10 WP14 — Durable Jobs Runbook

Status: **WP14 implementation runbook / not production activation authority**  
Authority: `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md` and `docs/architecture/V10_WP14_DURABLE_JOB_SYSTEM_CONTRACT.md`

## Purpose

This runbook covers the PostgreSQL-backed durable job lifecycle introduced by WP14. It does not activate WP15 broker reads, Web, Telegram, Cortex/AI or Real execution.

## Runtime boundary

- Durable state remains in PostgreSQL 18 schema `omni_cio_v10`.
- The accepted WP13 migration series is extended only by new immutable forward migrations.
- Generic orchestration code lives under `omni_cio/jobs/`.
- No Redis, QStash, Celery or second queue/database is introduced.
- Job rows store payload hashes and lifecycle metadata, not raw private portfolio payloads.
- Job events are append-only audit records.

## Lifecycle

Normal lifecycle:

`QUEUED -> RUNNING -> SUCCEEDED`

Retryable failure:

`RUNNING -> RETRY_WAIT -> RUNNING`

Terminal failure:

`RUNNING -> FAILED_PERMANENT`

Ambiguous/reconciliation-sensitive result:

`RUNNING -> RECONCILIATION_REQUIRED`

A job may also be explicitly `CANCELLED` only by a later reviewed control surface; WP14 does not add a public cancellation endpoint.

## Scheduling and idempotency

Scheduling requires a bounded job type, idempotency key, payload SHA-256, retry limit and recovery policy. Canonical `job_id` is derived from job type and idempotency key inside OWNER scope.

Equivalent replay returns the existing job. The same idempotency identity with a changed payload hash, correlation identity, retry limit or recovery policy fails closed instead of silently overwriting the prior job.

## Claim and lease

Claim is one PostgreSQL transaction:

1. select the oldest due `QUEUED`/`RETRY_WAIT` row using deterministic ordering;
2. take `FOR UPDATE SKIP LOCKED` on that row;
3. change it to `RUNNING`;
4. increment attempts;
5. write lease owner/expiry and heartbeat time;
6. append the transition to `job_events`;
7. commit atomically.

A heartbeat, completion or explicit failure is accepted only from the current lease owner while the lease is still valid. A stale worker cannot complete a job after lease loss.

## Failure classification

- `RETRYABLE`: reschedule only while attempts remain.
- `PERMANENT`: terminal failure, no retry.
- `VALIDATION`: terminal failure, no retry.
- `AMBIGUOUS`: `RECONCILIATION_REQUIRED`, no automatic retry.

Retry delay is explicit and bounded by the caller/runtime policy. WP14 provides no infinite polling or retry loop.

## Crash/restart recovery

A process crash may leave a durable `RUNNING` row whose lease later expires. Recovery scans only expired leases and locks rows before transition.

- `RETRY_SAFE`: returns the job to `RETRY_WAIT` when attempts remain; otherwise `FAILED_PERMANENT`.
- `RECONCILE`: moves the job to `RECONCILIATION_REQUIRED`.

This is critical for future broker-adjacent work: restart recovery never means "submit again". Any future possible-submit ambiguity remains a reconciliation problem under the protected execution contract.

## Worker integration

`DurableJobWorker.run_once()` is intentionally bounded. It claims at most one due job and dispatches to an explicit local handler registry. There is no generic infinite loop in the library.

Handlers may raise typed WP14 failures:

- retryable;
- permanent;
- validation;
- reconciliation-required.

Unknown exceptions are classified as retryable only within the persisted attempt bound. A missing handler is validation failure, not an implicit external action.

Later WPs bind actual portfolio refresh, market refresh, research, Watchtower, AI research, reconciliation, backup or health handlers. WP14 only establishes durable orchestration semantics.

## Observability and privacy

Safe diagnostic fields:

- canonical job ID/type/state;
- correlation ID;
- attempt counts;
- lease/next-run timestamps;
- sanitized error class;
- transition event identity/hash.

Never log:

- raw payload bytes;
- broker/Telegram tokens;
- database passwords;
- encryption/recovery keys;
- full account IDs;
- private portfolio content.

Worker IDs used in durable state must be generated/runtime labels suitable for diagnostics, not secret values.

## Recovery/backup

WP10 remains backup/off-device authority. WP14 ensures mutable job state and append-only job events participate in the deterministic durable-state digest. Focused acceptance creates only a temporary synthetic PostgreSQL 18 cluster, exercises job recovery, creates a WP10 logical backup, restores into a separate database and requires exact migration/state-digest parity.

Do not repeat or synthesize OWNER physical recovery evidence in WP14.

## Failure handling

Any lifecycle constraint violation, conflicting idempotency replay, duplicate claim, stale lease mutation, unbounded retry, mutable job journal or restore-digest mismatch is a WP14 failure. Fix the root cause; do not weaken the database constraints or skip the focused gate.

Hosted workflow startup failure caused by GitHub account billing/capacity remains infrastructure failure, not PASS. The exact-head Lenovo authoritative and focused WP14 gates remain the acceptance authority defined by the program.

## V9 protection

WP14 does not modify protected V9 `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false`, current broker-write authority or V9 rollback. No job transition grants broker-submit authority.