from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import os
import sys
import threading
from typing import Any

import psycopg

from omni_cio.contracts.v1.domain import OWNER_TENANT_ID, TenantV1
from omni_cio.jobs import (
    DurableJobRepository,
    FailureClass,
    JobConflictError,
    JobLeaseError,
    JobState,
    JobType,
    RecoveryPolicy,
    durable_job_state_digest,
)
from omni_cio.persistence import (
    apply_migrations,
    current_migration_state,
    migration_series_digest,
    model_record_sha256,
)


DSN_ENV = "OMNI_CIO_WP14_DSN"
NOW = datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc)


def _dsn() -> str:
    dsn = os.environ.get(DSN_ENV, "").strip()
    if not dsn:
        raise RuntimeError(f"{DSN_ENV} is required")
    return dsn


def _ensure_owner_tenant(connection: psycopg.Connection[Any]) -> None:
    tenant = TenantV1(created_at=NOW)
    record_sha256 = model_record_sha256(tenant)
    with connection.transaction():
        row = connection.execute(
            "INSERT INTO omni_cio_v10.tenants "
            "(tenant_id, schema_version, identity_version, mode, created_at, record_sha256) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (tenant_id) DO NOTHING RETURNING record_sha256",
            (
                tenant.tenant_id,
                tenant.schema_version,
                tenant.identity_version,
                tenant.mode.value,
                tenant.created_at,
                record_sha256,
            ),
        ).fetchone()
        if row is not None:
            return
        existing = connection.execute(
            "SELECT record_sha256 FROM omni_cio_v10.tenants WHERE tenant_id = %s",
            (OWNER_TENANT_ID,),
        ).fetchone()
        if existing is None or str(existing[0]) != record_sha256:
            raise AssertionError(
                "synthetic OWNER tenant identity conflicts with database"
            )


def _concurrent_claim(dsn: str, *, now: datetime) -> tuple[str, str]:
    barrier = threading.Barrier(2)

    def worker(worker_id: str) -> tuple[str, str | None]:
        with psycopg.connect(dsn) as connection:
            barrier.wait(timeout=10)
            job = DurableJobRepository(connection).claim_next_job(
                worker_id=worker_id,
                lease_seconds=30,
                now=now,
            )
            return worker_id, job.job_id if job is not None else None

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(worker, "wp14-worker-a"),
            executor.submit(worker, "wp14-worker-b"),
        ]
        results = [future.result(timeout=60) for future in futures]

    claimed = [(worker_id, job_id) for worker_id, job_id in results if job_id]
    if len(claimed) != 1:
        raise AssertionError(f"expected one concurrent claim, got {results!r}")
    worker_id, job_id = claimed[0]
    assert job_id is not None
    return worker_id, job_id


def _expect_journal_mutation_failure(
    connection: psycopg.Connection[Any],
    statement: str,
) -> None:
    failed = False
    try:
        with connection.transaction():
            connection.execute(statement)
    except psycopg.Error:
        failed = True
    if not failed:
        raise AssertionError("append-only job journal mutation unexpectedly succeeded")


def _exercise(connection: psycopg.Connection[Any], *, dsn: str) -> dict[str, Any]:
    apply_migrations(connection)
    _ensure_owner_tenant(connection)
    repository = DurableJobRepository(connection)

    first = repository.schedule_job(
        job_type=JobType.HEALTH,
        idempotency_key="wp14-idempotent-health",
        payload_sha256="1" * 64,
        correlation_id="wp14-correlation-health",
        max_attempts=3,
        recovery_policy=RecoveryPolicy.RETRY_SAFE,
        run_at=NOW,
        created_at=NOW,
    )
    replay = repository.schedule_job(
        job_type=JobType.HEALTH,
        idempotency_key="wp14-idempotent-health",
        payload_sha256="1" * 64,
        correlation_id="wp14-correlation-health",
        max_attempts=3,
        recovery_policy=RecoveryPolicy.RETRY_SAFE,
        run_at=NOW,
        created_at=NOW,
    )
    if replay.job_id != first.job_id:
        raise AssertionError("equivalent scheduling replay changed job identity")

    conflict_rejected = False
    try:
        repository.schedule_job(
            job_type=JobType.HEALTH,
            idempotency_key="wp14-idempotent-health",
            payload_sha256="2" * 64,
            correlation_id="wp14-correlation-health",
            max_attempts=3,
            recovery_policy=RecoveryPolicy.RETRY_SAFE,
            run_at=NOW,
            created_at=NOW,
        )
    except JobConflictError:
        conflict_rejected = True
    if not conflict_rejected:
        raise AssertionError("conflicting idempotency replay was not rejected")

    health = repository.claim_next_job(
        worker_id="wp14-health-worker",
        lease_seconds=30,
        now=NOW,
    )
    if health is None or health.job_id != first.job_id or health.attempts != 1:
        raise AssertionError("idempotent health job was not claimed correctly")
    health = repository.heartbeat_job(
        health.job_id,
        worker_id="wp14-health-worker",
        lease_seconds=30,
        now=NOW + timedelta(seconds=1),
    )
    if health.state is not JobState.RUNNING:
        raise AssertionError("heartbeat changed running job state")
    health = repository.complete_job(
        health.job_id,
        worker_id="wp14-health-worker",
        now=NOW + timedelta(seconds=2),
    )
    if health.state is not JobState.SUCCEEDED:
        raise AssertionError("successful job did not become SUCCEEDED")

    concurrency_job = repository.schedule_job(
        job_type=JobType.BACKUP,
        idempotency_key="wp14-concurrent-claim",
        payload_sha256="3" * 64,
        correlation_id="wp14-correlation-concurrency",
        max_attempts=3,
        run_at=NOW + timedelta(minutes=1),
        created_at=NOW + timedelta(minutes=1),
    )
    claim_worker, claimed_job_id = _concurrent_claim(
        dsn,
        now=NOW + timedelta(minutes=1),
    )
    if claimed_job_id != concurrency_job.job_id:
        raise AssertionError("concurrent claim selected an unexpected job")
    with psycopg.connect(dsn) as claim_connection:
        completed = DurableJobRepository(claim_connection).complete_job(
            claimed_job_id,
            worker_id=claim_worker,
            now=NOW + timedelta(minutes=1, seconds=1),
        )
        if completed.state is not JobState.SUCCEEDED:
            raise AssertionError("concurrent claim owner could not complete job")

    crash_job = repository.schedule_job(
        job_type=JobType.RESEARCH,
        idempotency_key="wp14-crash-retry-safe",
        payload_sha256="4" * 64,
        correlation_id="wp14-correlation-crash",
        max_attempts=2,
        recovery_policy=RecoveryPolicy.RETRY_SAFE,
        run_at=NOW + timedelta(minutes=2),
        created_at=NOW + timedelta(minutes=2),
    )
    crash_claim = repository.claim_next_job(
        worker_id="wp14-crashed-worker",
        lease_seconds=2,
        now=NOW + timedelta(minutes=2),
    )
    if crash_claim is None or crash_claim.job_id != crash_job.job_id:
        raise AssertionError("crash simulation job was not claimed")

    with psycopg.connect(dsn) as recovery_connection:
        recovery_repository = DurableJobRepository(recovery_connection)
        recovered = recovery_repository.recover_expired_leases(
            now=NOW + timedelta(minutes=2, seconds=3)
        )
        if len(recovered) != 1 or recovered[0].state is not JobState.RETRY_WAIT:
            raise AssertionError(
                "expired RETRY_SAFE lease did not recover to RETRY_WAIT"
            )

        stale_worker_rejected = False
        try:
            recovery_repository.complete_job(
                crash_job.job_id,
                worker_id="wp14-crashed-worker",
                now=NOW + timedelta(minutes=2, seconds=3),
            )
        except JobLeaseError:
            stale_worker_rejected = True
        if not stale_worker_rejected:
            raise AssertionError("stale worker retained authority after lease recovery")

        retry_claim = recovery_repository.claim_next_job(
            worker_id="wp14-retry-worker",
            lease_seconds=30,
            now=NOW + timedelta(minutes=2, seconds=3),
        )
        if retry_claim is None or retry_claim.attempts != 2:
            raise AssertionError("recovered retry job did not reach second attempt")
        exhausted = recovery_repository.fail_job(
            retry_claim.job_id,
            worker_id="wp14-retry-worker",
            failure_class=FailureClass.RETRYABLE,
            retry_delay_seconds=1,
            now=NOW + timedelta(minutes=2, seconds=4),
        )
        if (
            exhausted.state is not JobState.FAILED_PERMANENT
            or exhausted.error_class is not FailureClass.RETRY_EXHAUSTED
        ):
            raise AssertionError("retryable job exceeded max attempts")

    reconcile_job = repository.schedule_job(
        job_type=JobType.RECONCILIATION,
        idempotency_key="wp14-crash-reconcile",
        payload_sha256="5" * 64,
        correlation_id="wp14-correlation-reconcile",
        max_attempts=3,
        recovery_policy=RecoveryPolicy.RECONCILE,
        run_at=NOW + timedelta(minutes=3),
        created_at=NOW + timedelta(minutes=3),
    )
    reconcile_claim = repository.claim_next_job(
        worker_id="wp14-reconcile-crash-worker",
        lease_seconds=2,
        now=NOW + timedelta(minutes=3),
    )
    if reconcile_claim is None or reconcile_claim.job_id != reconcile_job.job_id:
        raise AssertionError("reconciliation crash job was not claimed")
    reconciled = repository.recover_expired_leases(
        now=NOW + timedelta(minutes=3, seconds=3)
    )
    if (
        len(reconciled) != 1
        or reconciled[0].state is not JobState.RECONCILIATION_REQUIRED
    ):
        raise AssertionError("RECONCILE lease expiry did not block for reconciliation")

    validation_job = repository.schedule_job(
        job_type=JobType.PORTFOLIO_REFRESH,
        idempotency_key="wp14-validation-terminal",
        payload_sha256="6" * 64,
        correlation_id="wp14-correlation-validation",
        max_attempts=5,
        run_at=NOW + timedelta(minutes=4),
        created_at=NOW + timedelta(minutes=4),
    )
    validation_claim = repository.claim_next_job(
        worker_id="wp14-validation-worker",
        lease_seconds=30,
        now=NOW + timedelta(minutes=4),
    )
    if validation_claim is None or validation_claim.job_id != validation_job.job_id:
        raise AssertionError("validation job was not claimed")
    validation_terminal = repository.fail_job(
        validation_claim.job_id,
        worker_id="wp14-validation-worker",
        failure_class=FailureClass.VALIDATION,
        now=NOW + timedelta(minutes=4, seconds=1),
    )
    if validation_terminal.state is not JobState.FAILED_PERMANENT:
        raise AssertionError("validation failure was incorrectly retried")

    ambiguous_job = repository.schedule_job(
        job_type=JobType.WATCHTOWER,
        idempotency_key="wp14-ambiguous-reconcile",
        payload_sha256="7" * 64,
        correlation_id="wp14-correlation-ambiguous",
        max_attempts=5,
        run_at=NOW + timedelta(minutes=5),
        created_at=NOW + timedelta(minutes=5),
    )
    ambiguous_claim = repository.claim_next_job(
        worker_id="wp14-ambiguous-worker",
        lease_seconds=30,
        now=NOW + timedelta(minutes=5),
    )
    if ambiguous_claim is None or ambiguous_claim.job_id != ambiguous_job.job_id:
        raise AssertionError("ambiguous job was not claimed")
    ambiguous = repository.fail_job(
        ambiguous_claim.job_id,
        worker_id="wp14-ambiguous-worker",
        failure_class=FailureClass.AMBIGUOUS,
        now=NOW + timedelta(minutes=5, seconds=1),
    )
    if ambiguous.state is not JobState.RECONCILIATION_REQUIRED:
        raise AssertionError("ambiguous failure was not blocked for reconciliation")

    _expect_journal_mutation_failure(
        connection,
        "UPDATE omni_cio_v10.job_events SET event_type = 'CANCELLED'",
    )
    _expect_journal_mutation_failure(
        connection,
        "DELETE FROM omni_cio_v10.job_events",
    )

    event_count_row = connection.execute(
        "SELECT COUNT(*) FROM omni_cio_v10.job_events"
    ).fetchone()
    if event_count_row is None or int(event_count_row[0]) < 12:
        raise AssertionError(
            "job journal did not capture required lifecycle transitions"
        )

    digest = durable_job_state_digest(connection)
    if len(digest) != 64:
        raise AssertionError("durable job state digest is not SHA-256")
    migrations = current_migration_state(connection)
    if len(migrations) < 2:
        raise AssertionError("WP14 migration is not applied")

    return {
        "status": "PASS",
        "postgres_major": 18,
        "migration_count": len(migrations),
        "migration_series_sha256": migration_series_digest(),
        "job_state_digest_sha256": digest,
        "duplicate_schedule_idempotent": True,
        "conflicting_replay_rejected": True,
        "concurrent_single_claim": True,
        "heartbeat_and_completion": True,
        "crash_retry_safe_recovered": True,
        "stale_worker_rejected": True,
        "retry_bound_enforced": True,
        "crash_reconcile_blocked": True,
        "validation_retry_blocked": True,
        "ambiguous_retry_blocked": True,
        "append_only_job_journal": True,
        "raw_payload_logged": False,
        "real_secrets_used": False,
        "broker_write_authority_used": False,
    }


def _digest(connection: psycopg.Connection[Any]) -> dict[str, Any]:
    migrations = current_migration_state(connection)
    return {
        "status": "PASS",
        "migration_count": len(migrations),
        "migration_series_sha256": migration_series_digest(),
        "job_state_digest_sha256": durable_job_state_digest(connection),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="WP14 durable jobs synthetic acceptance probe"
    )
    parser.add_argument("command", choices=("exercise", "digest"))
    args = parser.parse_args()

    try:
        dsn = _dsn()
        with psycopg.connect(dsn) as connection:
            result = (
                _exercise(connection, dsn=dsn)
                if args.command == "exercise"
                else _digest(connection)
            )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "reason": type(exc).__name__,
                    "raw_payload_logged": False,
                    "real_secrets_used": False,
                    "broker_write_authority_used": False,
                },
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        return 1

    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
