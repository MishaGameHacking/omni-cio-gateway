from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any

from omni_cio.contracts.v1.domain import OWNER_TENANT_ID
from omni_cio.jobs.models import (
    FailureClass,
    JobEvent,
    JobEventType,
    JobRecord,
    JobState,
    JobType,
    RecoveryPolicy,
    canonical_job_id,
    require_lease_seconds,
    require_max_attempts,
    require_retry_delay_seconds,
    require_sha256,
)
from omni_cio.persistence.migration import ConnectionLike


_JOB_COLUMNS = (
    "job_id, tenant_id, job_type, idempotency_key, payload_sha256, state, "
    "correlation_id, lease_owner, lease_expires_at, heartbeat_at, attempts, "
    "max_attempts, next_run_at, started_at, completed_at, error_class, "
    "recovery_policy, created_at"
)

_EVENT_COLUMNS = (
    "event_id, job_id, tenant_id, event_type, from_state, to_state, attempt, "
    "worker_id, error_class, occurred_at, record_sha256"
)


class JobPersistenceError(RuntimeError):
    """Base fail-closed durable-job persistence error."""


class JobConflictError(JobPersistenceError):
    """An idempotent job identity was replayed with conflicting semantics."""


class JobLeaseError(JobPersistenceError):
    """A worker attempted a transition without a current valid lease."""


class JobNotFoundError(JobPersistenceError):
    """A requested durable job does not exist."""


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("job timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def _now(value: datetime | None) -> datetime:
    return _utc(value or datetime.now(timezone.utc))


def _job_from_row(row: Any) -> JobRecord:
    error_class = FailureClass(str(row[15])) if row[15] is not None else None
    return JobRecord(
        job_id=str(row[0]),
        tenant_id=str(row[1]),
        job_type=JobType(str(row[2])),
        idempotency_key=str(row[3]),
        payload_sha256=str(row[4]),
        state=JobState(str(row[5])),
        correlation_id=str(row[6]),
        lease_owner=str(row[7]) if row[7] is not None else None,
        lease_expires_at=row[8],
        heartbeat_at=row[9],
        attempts=int(row[10]),
        max_attempts=int(row[11]),
        next_run_at=row[12],
        started_at=row[13],
        completed_at=row[14],
        error_class=error_class,
        recovery_policy=RecoveryPolicy(str(row[16])),
        created_at=row[17],
    )


def _event_from_row(row: Any) -> JobEvent:
    from_state = JobState(str(row[4])) if row[4] is not None else None
    error_class = FailureClass(str(row[8])) if row[8] is not None else None
    return JobEvent(
        event_id=int(row[0]),
        job_id=str(row[1]),
        tenant_id=str(row[2]),
        event_type=JobEventType(str(row[3])),
        from_state=from_state,
        to_state=JobState(str(row[5])),
        attempt=int(row[6]),
        worker_id=str(row[7]) if row[7] is not None else None,
        error_class=error_class,
        occurred_at=row[9],
        record_sha256=str(row[10]),
    )


def _event_sha256(
    *,
    job_id: str,
    event_type: JobEventType,
    from_state: JobState | None,
    to_state: JobState,
    attempt: int,
    worker_id: str | None,
    error_class: FailureClass | None,
    occurred_at: datetime,
) -> str:
    payload = {
        "attempt": attempt,
        "error_class": error_class.value if error_class is not None else None,
        "event_type": event_type.value,
        "from_state": from_state.value if from_state is not None else None,
        "job_id": job_id,
        "occurred_at": _utc(occurred_at).isoformat(),
        "tenant_id": OWNER_TENANT_ID,
        "to_state": to_state.value,
        "worker_id": worker_id,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _append_event(
    connection: ConnectionLike,
    *,
    job_id: str,
    event_type: JobEventType,
    from_state: JobState | None,
    to_state: JobState,
    attempt: int,
    worker_id: str | None,
    error_class: FailureClass | None,
    occurred_at: datetime,
) -> None:
    timestamp = _utc(occurred_at)
    record_sha256 = _event_sha256(
        job_id=job_id,
        event_type=event_type,
        from_state=from_state,
        to_state=to_state,
        attempt=attempt,
        worker_id=worker_id,
        error_class=error_class,
        occurred_at=timestamp,
    )
    connection.execute(
        "INSERT INTO omni_cio_v10.job_events "
        "(job_id, tenant_id, event_type, from_state, to_state, attempt, "
        "worker_id, error_class, occurred_at, record_sha256) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (
            job_id,
            OWNER_TENANT_ID,
            event_type.value,
            from_state.value if from_state is not None else None,
            to_state.value,
            attempt,
            worker_id,
            error_class.value if error_class is not None else None,
            timestamp,
            record_sha256,
        ),
    )


class DurableJobRepository:
    def __init__(self, connection: ConnectionLike) -> None:
        self._connection = connection

    def schedule_job(
        self,
        *,
        job_type: JobType,
        idempotency_key: str,
        payload_sha256: str,
        correlation_id: str | None = None,
        max_attempts: int = 3,
        recovery_policy: RecoveryPolicy = RecoveryPolicy.RETRY_SAFE,
        run_at: datetime | None = None,
        created_at: datetime | None = None,
    ) -> JobRecord:
        normalized_key = idempotency_key.strip()
        job_id = canonical_job_id(job_type, normalized_key)
        payload_hash = require_sha256(payload_sha256, field_name="payload_sha256")
        attempts_limit = require_max_attempts(max_attempts)
        timestamp = _now(created_at)
        due_at = _utc(run_at) if run_at is not None else timestamp
        correlation = (correlation_id or job_id).strip()
        if not correlation:
            raise ValueError("correlation_id must not be empty")

        with self._connection.transaction():
            cursor = self._connection.execute(
                "INSERT INTO omni_cio_v10.jobs "
                "(job_id, tenant_id, job_type, idempotency_key, payload_sha256, "
                "created_at, state, correlation_id, attempts, max_attempts, "
                "next_run_at, recovery_policy) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (tenant_id, job_type, idempotency_key) DO NOTHING "
                f"RETURNING {_JOB_COLUMNS}",
                (
                    job_id,
                    OWNER_TENANT_ID,
                    job_type.value,
                    normalized_key,
                    payload_hash,
                    timestamp,
                    JobState.QUEUED.value,
                    correlation,
                    0,
                    attempts_limit,
                    due_at,
                    recovery_policy.value,
                ),
            )
            row = cursor.fetchone()
            inserted = row is not None
            if row is None:
                row = self._connection.execute(
                    f"SELECT {_JOB_COLUMNS} FROM omni_cio_v10.jobs "
                    "WHERE tenant_id = %s AND job_type = %s AND idempotency_key = %s",
                    (OWNER_TENANT_ID, job_type.value, normalized_key),
                ).fetchone()
            if row is None:
                raise JobConflictError("idempotent job replay could not resolve identity")

            job = _job_from_row(row)
            if (
                job.job_id != job_id
                or job.payload_sha256 != payload_hash
                or job.correlation_id != correlation
                or job.max_attempts != attempts_limit
                or job.recovery_policy is not recovery_policy
                or job.next_run_at != due_at
            ):
                raise JobConflictError(
                    "job idempotency identity replay conflicts with durable semantics"
                )

            if inserted:
                _append_event(
                    self._connection,
                    job_id=job.job_id,
                    event_type=JobEventType.SCHEDULED,
                    from_state=None,
                    to_state=JobState.QUEUED,
                    attempt=0,
                    worker_id=None,
                    error_class=None,
                    occurred_at=timestamp,
                )
            return job

    def claim_next_job(
        self,
        *,
        worker_id: str,
        lease_seconds: int = 60,
        now: datetime | None = None,
    ) -> JobRecord | None:
        worker = worker_id.strip()
        if not worker:
            raise ValueError("worker_id must not be empty")
        lease_duration = require_lease_seconds(lease_seconds)
        timestamp = _now(now)
        lease_expires_at = timestamp + timedelta(seconds=lease_duration)

        with self._connection.transaction():
            row = self._connection.execute(
                f"SELECT {_JOB_COLUMNS} FROM omni_cio_v10.jobs "
                "WHERE tenant_id = %s "
                "AND state IN (%s, %s) "
                "AND next_run_at <= %s "
                "AND attempts < max_attempts "
                "ORDER BY next_run_at, created_at, job_id "
                "FOR UPDATE SKIP LOCKED LIMIT 1",
                (
                    OWNER_TENANT_ID,
                    JobState.QUEUED.value,
                    JobState.RETRY_WAIT.value,
                    timestamp,
                ),
            ).fetchone()
            if row is None:
                return None

            current = _job_from_row(row)
            updated = self._connection.execute(
                "UPDATE omni_cio_v10.jobs SET "
                "state = %s, lease_owner = %s, lease_expires_at = %s, "
                "heartbeat_at = %s, attempts = attempts + 1, "
                "next_run_at = NULL, started_at = COALESCE(started_at, %s), "
                "completed_at = NULL, error_class = NULL "
                "WHERE job_id = %s "
                f"RETURNING {_JOB_COLUMNS}",
                (
                    JobState.RUNNING.value,
                    worker,
                    lease_expires_at,
                    timestamp,
                    timestamp,
                    current.job_id,
                ),
            ).fetchone()
            if updated is None:
                raise JobConflictError("claimed job disappeared before durable update")
            job = _job_from_row(updated)
            _append_event(
                self._connection,
                job_id=job.job_id,
                event_type=JobEventType.CLAIMED,
                from_state=current.state,
                to_state=JobState.RUNNING,
                attempt=job.attempts,
                worker_id=worker,
                error_class=None,
                occurred_at=timestamp,
            )
            return job

    def heartbeat_job(
        self,
        job_id: str,
        *,
        worker_id: str,
        lease_seconds: int = 60,
        now: datetime | None = None,
    ) -> JobRecord:
        worker = worker_id.strip()
        if not worker:
            raise ValueError("worker_id must not be empty")
        lease_duration = require_lease_seconds(lease_seconds)
        timestamp = _now(now)
        lease_expires_at = timestamp + timedelta(seconds=lease_duration)

        with self._connection.transaction():
            row = self._connection.execute(
                "UPDATE omni_cio_v10.jobs SET "
                "heartbeat_at = %s, lease_expires_at = %s "
                "WHERE job_id = %s AND tenant_id = %s AND state = %s "
                "AND lease_owner = %s AND lease_expires_at > %s "
                f"RETURNING {_JOB_COLUMNS}",
                (
                    timestamp,
                    lease_expires_at,
                    job_id,
                    OWNER_TENANT_ID,
                    JobState.RUNNING.value,
                    worker,
                    timestamp,
                ),
            ).fetchone()
            if row is None:
                raise JobLeaseError("heartbeat requires the current unexpired lease")
            job = _job_from_row(row)
            _append_event(
                self._connection,
                job_id=job.job_id,
                event_type=JobEventType.HEARTBEAT,
                from_state=JobState.RUNNING,
                to_state=JobState.RUNNING,
                attempt=job.attempts,
                worker_id=worker,
                error_class=None,
                occurred_at=timestamp,
            )
            return job

    def complete_job(
        self,
        job_id: str,
        *,
        worker_id: str,
        now: datetime | None = None,
    ) -> JobRecord:
        worker = worker_id.strip()
        if not worker:
            raise ValueError("worker_id must not be empty")
        timestamp = _now(now)

        with self._connection.transaction():
            row = self._connection.execute(
                "UPDATE omni_cio_v10.jobs SET "
                "state = %s, lease_owner = NULL, lease_expires_at = NULL, "
                "heartbeat_at = NULL, next_run_at = NULL, completed_at = %s, "
                "error_class = NULL "
                "WHERE job_id = %s AND tenant_id = %s AND state = %s "
                "AND lease_owner = %s AND lease_expires_at > %s "
                f"RETURNING {_JOB_COLUMNS}",
                (
                    JobState.SUCCEEDED.value,
                    timestamp,
                    job_id,
                    OWNER_TENANT_ID,
                    JobState.RUNNING.value,
                    worker,
                    timestamp,
                ),
            ).fetchone()
            if row is None:
                raise JobLeaseError("completion requires the current unexpired lease")
            job = _job_from_row(row)
            _append_event(
                self._connection,
                job_id=job.job_id,
                event_type=JobEventType.SUCCEEDED,
                from_state=JobState.RUNNING,
                to_state=JobState.SUCCEEDED,
                attempt=job.attempts,
                worker_id=worker,
                error_class=None,
                occurred_at=timestamp,
            )
            return job

    def fail_job(
        self,
        job_id: str,
        *,
        worker_id: str,
        failure_class: FailureClass,
        retry_delay_seconds: int = 0,
        now: datetime | None = None,
    ) -> JobRecord:
        worker = worker_id.strip()
        if not worker:
            raise ValueError("worker_id must not be empty")
        retry_delay = require_retry_delay_seconds(retry_delay_seconds)
        timestamp = _now(now)

        with self._connection.transaction():
            row = self._connection.execute(
                f"SELECT {_JOB_COLUMNS} FROM omni_cio_v10.jobs "
                "WHERE job_id = %s AND tenant_id = %s FOR UPDATE",
                (job_id, OWNER_TENANT_ID),
            ).fetchone()
            if row is None:
                raise JobNotFoundError("durable job does not exist")
            current = _job_from_row(row)
            if (
                current.state is not JobState.RUNNING
                or current.lease_owner != worker
                or current.lease_expires_at is None
                or current.lease_expires_at <= timestamp
            ):
                raise JobLeaseError("failure transition requires the current unexpired lease")

            if failure_class is FailureClass.AMBIGUOUS:
                state = JobState.RECONCILIATION_REQUIRED
                error = FailureClass.AMBIGUOUS
                event_type = JobEventType.RECONCILIATION_REQUIRED
                next_run_at = None
                completed_at = timestamp
            elif failure_class in (FailureClass.PERMANENT, FailureClass.VALIDATION):
                state = JobState.FAILED_PERMANENT
                error = failure_class
                event_type = JobEventType.FAILED_PERMANENT
                next_run_at = None
                completed_at = timestamp
            elif current.attempts >= current.max_attempts:
                state = JobState.FAILED_PERMANENT
                error = FailureClass.RETRY_EXHAUSTED
                event_type = JobEventType.FAILED_PERMANENT
                next_run_at = None
                completed_at = timestamp
            else:
                state = JobState.RETRY_WAIT
                error = FailureClass.RETRYABLE
                event_type = JobEventType.RETRY_SCHEDULED
                next_run_at = timestamp + timedelta(seconds=retry_delay)
                completed_at = None

            updated = self._connection.execute(
                "UPDATE omni_cio_v10.jobs SET "
                "state = %s, lease_owner = NULL, lease_expires_at = NULL, "
                "heartbeat_at = NULL, next_run_at = %s, completed_at = %s, "
                "error_class = %s "
                "WHERE job_id = %s "
                f"RETURNING {_JOB_COLUMNS}",
                (
                    state.value,
                    next_run_at,
                    completed_at,
                    error.value,
                    job_id,
                ),
            ).fetchone()
            if updated is None:
                raise JobConflictError("failure transition could not persist job state")
            job = _job_from_row(updated)
            _append_event(
                self._connection,
                job_id=job.job_id,
                event_type=event_type,
                from_state=JobState.RUNNING,
                to_state=state,
                attempt=job.attempts,
                worker_id=worker,
                error_class=error,
                occurred_at=timestamp,
            )
            return job

    def recover_expired_leases(
        self,
        *,
        now: datetime | None = None,
        limit: int = 100,
    ) -> tuple[JobRecord, ...]:
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")
        timestamp = _now(now)
        recovered: list[JobRecord] = []

        with self._connection.transaction():
            rows = self._connection.execute(
                f"SELECT {_JOB_COLUMNS} FROM omni_cio_v10.jobs "
                "WHERE tenant_id = %s AND state = %s "
                "AND lease_expires_at <= %s "
                "ORDER BY lease_expires_at, job_id "
                "FOR UPDATE SKIP LOCKED LIMIT %s",
                (
                    OWNER_TENANT_ID,
                    JobState.RUNNING.value,
                    timestamp,
                    limit,
                ),
            ).fetchall()

            for row in rows:
                current = _job_from_row(row)
                prior_worker = current.lease_owner
                if current.recovery_policy is RecoveryPolicy.RECONCILE:
                    state = JobState.RECONCILIATION_REQUIRED
                    error = FailureClass.LEASE_EXPIRED
                    event_type = JobEventType.RECONCILIATION_REQUIRED
                    next_run_at = None
                    completed_at = timestamp
                elif current.attempts >= current.max_attempts:
                    state = JobState.FAILED_PERMANENT
                    error = FailureClass.LEASE_EXPIRED_ATTEMPTS_EXHAUSTED
                    event_type = JobEventType.FAILED_PERMANENT
                    next_run_at = None
                    completed_at = timestamp
                else:
                    state = JobState.RETRY_WAIT
                    error = FailureClass.LEASE_EXPIRED
                    event_type = JobEventType.LEASE_RECOVERED
                    next_run_at = timestamp
                    completed_at = None

                updated = self._connection.execute(
                    "UPDATE omni_cio_v10.jobs SET "
                    "state = %s, lease_owner = NULL, lease_expires_at = NULL, "
                    "heartbeat_at = NULL, next_run_at = %s, completed_at = %s, "
                    "error_class = %s "
                    "WHERE job_id = %s "
                    f"RETURNING {_JOB_COLUMNS}",
                    (
                        state.value,
                        next_run_at,
                        completed_at,
                        error.value,
                        current.job_id,
                    ),
                ).fetchone()
                if updated is None:
                    raise JobConflictError("expired lease recovery lost durable job")
                job = _job_from_row(updated)
                _append_event(
                    self._connection,
                    job_id=job.job_id,
                    event_type=event_type,
                    from_state=JobState.RUNNING,
                    to_state=state,
                    attempt=job.attempts,
                    worker_id=prior_worker,
                    error_class=error,
                    occurred_at=timestamp,
                )
                recovered.append(job)

        return tuple(recovered)

    def get_job(self, job_id: str) -> JobRecord:
        row = self._connection.execute(
            f"SELECT {_JOB_COLUMNS} FROM omni_cio_v10.jobs "
            "WHERE job_id = %s AND tenant_id = %s",
            (job_id, OWNER_TENANT_ID),
        ).fetchone()
        if row is None:
            raise JobNotFoundError("durable job does not exist")
        return _job_from_row(row)

    def list_events(self, job_id: str) -> tuple[JobEvent, ...]:
        rows = self._connection.execute(
            f"SELECT {_EVENT_COLUMNS} FROM omni_cio_v10.job_events "
            "WHERE job_id = %s AND tenant_id = %s ORDER BY event_id",
            (job_id, OWNER_TENANT_ID),
        ).fetchall()
        return tuple(_event_from_row(row) for row in rows)