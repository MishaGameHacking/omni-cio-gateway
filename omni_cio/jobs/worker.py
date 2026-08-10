from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime

from omni_cio.jobs.models import FailureClass, JobRecord, JobType
from omni_cio.jobs.repository import DurableJobRepository


JobHandler = Callable[[JobRecord], None]


class JobHandlerError(RuntimeError):
    failure_class = FailureClass.RETRYABLE


class RetryableJobError(JobHandlerError):
    failure_class = FailureClass.RETRYABLE


class PermanentJobError(JobHandlerError):
    failure_class = FailureClass.PERMANENT


class ValidationJobError(JobHandlerError):
    failure_class = FailureClass.VALIDATION


class ReconciliationRequiredJobError(JobHandlerError):
    failure_class = FailureClass.AMBIGUOUS


class DurableJobWorker:
    """Bounded single-job dispatcher.

    WP14 intentionally exposes ``run_once`` rather than an unbounded polling loop.
    Windows supervision/scheduling owns process lifetime; this class owns one
    durable claim/handler/transition cycle only.
    """

    def __init__(
        self,
        repository: DurableJobRepository,
        *,
        worker_id: str,
        handlers: Mapping[JobType, JobHandler],
        lease_seconds: int = 60,
        retry_delay_seconds: int = 30,
    ) -> None:
        worker = worker_id.strip()
        if not worker:
            raise ValueError("worker_id must not be empty")
        if retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds must not be negative")
        self._repository = repository
        self._worker_id = worker
        self._handlers = dict(handlers)
        self._lease_seconds = lease_seconds
        self._retry_delay_seconds = retry_delay_seconds

    def run_once(self, *, now: datetime | None = None) -> JobRecord | None:
        job = self._repository.claim_next_job(
            worker_id=self._worker_id,
            lease_seconds=self._lease_seconds,
            now=now,
        )
        if job is None:
            return None

        handler = self._handlers.get(job.job_type)
        if handler is None:
            return self._repository.fail_job(
                job.job_id,
                worker_id=self._worker_id,
                failure_class=FailureClass.VALIDATION,
                retry_delay_seconds=0,
                now=now,
            )

        try:
            handler(job)
        except JobHandlerError as exc:
            return self._repository.fail_job(
                job.job_id,
                worker_id=self._worker_id,
                failure_class=exc.failure_class,
                retry_delay_seconds=self._retry_delay_seconds,
                now=now,
            )
        except Exception:
            # Unknown handler defects are bounded by max_attempts. The exception
            # text is deliberately not persisted or logged by the generic layer.
            return self._repository.fail_job(
                job.job_id,
                worker_id=self._worker_id,
                failure_class=FailureClass.RETRYABLE,
                retry_delay_seconds=self._retry_delay_seconds,
                now=now,
            )

        return self._repository.complete_job(
            job.job_id,
            worker_id=self._worker_id,
            now=now,
        )