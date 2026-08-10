from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import hashlib
import re

from omni_cio.contracts.v1.domain import OWNER_TENANT_ID


_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
MAX_ATTEMPTS = 100
MAX_LEASE_SECONDS = 3600
MAX_RETRY_DELAY_SECONDS = 86400


class JobType(StrEnum):
    PORTFOLIO_REFRESH = "PORTFOLIO_REFRESH"
    MARKET_REFRESH = "MARKET_REFRESH"
    RESEARCH = "RESEARCH"
    WATCHTOWER = "WATCHTOWER"
    AI_RESEARCH = "AI_RESEARCH"
    RECONCILIATION = "RECONCILIATION"
    BACKUP = "BACKUP"
    HEALTH = "HEALTH"


class JobState(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    RETRY_WAIT = "RETRY_WAIT"
    SUCCEEDED = "SUCCEEDED"
    FAILED_PERMANENT = "FAILED_PERMANENT"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    CANCELLED = "CANCELLED"


class FailureClass(StrEnum):
    RETRYABLE = "RETRYABLE"
    RETRY_EXHAUSTED = "RETRY_EXHAUSTED"
    PERMANENT = "PERMANENT"
    VALIDATION = "VALIDATION"
    AMBIGUOUS = "AMBIGUOUS"
    LEASE_EXPIRED = "LEASE_EXPIRED"
    LEASE_EXPIRED_ATTEMPTS_EXHAUSTED = "LEASE_EXPIRED_ATTEMPTS_EXHAUSTED"


class RecoveryPolicy(StrEnum):
    RETRY_SAFE = "RETRY_SAFE"
    RECONCILE = "RECONCILE"


class JobEventType(StrEnum):
    SCHEDULED = "SCHEDULED"
    CLAIMED = "CLAIMED"
    HEARTBEAT = "HEARTBEAT"
    SUCCEEDED = "SUCCEEDED"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    FAILED_PERMANENT = "FAILED_PERMANENT"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    LEASE_RECOVERED = "LEASE_RECOVERED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True, slots=True)
class JobRecord:
    job_id: str
    tenant_id: str
    job_type: JobType
    idempotency_key: str
    payload_sha256: str
    state: JobState
    correlation_id: str
    lease_owner: str | None
    lease_expires_at: datetime | None
    heartbeat_at: datetime | None
    attempts: int
    max_attempts: int
    next_run_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    error_class: FailureClass | None
    recovery_policy: RecoveryPolicy
    created_at: datetime


@dataclass(frozen=True, slots=True)
class JobEvent:
    event_id: int
    job_id: str
    tenant_id: str
    event_type: JobEventType
    from_state: JobState | None
    to_state: JobState
    attempt: int
    worker_id: str | None
    error_class: FailureClass | None
    occurred_at: datetime
    record_sha256: str


def canonical_job_id(job_type: JobType, idempotency_key: str) -> str:
    normalized_key = idempotency_key.strip()
    if not normalized_key:
        raise ValueError("idempotency_key must not be empty")
    digest = hashlib.sha256(
        f"{OWNER_TENANT_ID}\n{job_type.value}\n{normalized_key}".encode("utf-8")
    ).hexdigest()
    return f"job:v1:{digest}"


def require_sha256(value: str, *, field_name: str = "sha256") -> str:
    if _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be lowercase SHA-256 hex")
    return value


def require_max_attempts(value: int) -> int:
    if value < 1 or value > MAX_ATTEMPTS:
        raise ValueError(f"max_attempts must be between 1 and {MAX_ATTEMPTS}")
    return value


def require_lease_seconds(value: int) -> int:
    if value < 1 or value > MAX_LEASE_SECONDS:
        raise ValueError(
            f"lease_seconds must be between 1 and {MAX_LEASE_SECONDS}"
        )
    return value


def require_retry_delay_seconds(value: int) -> int:
    if value < 0 or value > MAX_RETRY_DELAY_SECONDS:
        raise ValueError(
            "retry_delay_seconds must be between 0 and "
            f"{MAX_RETRY_DELAY_SECONDS}"
        )
    return value