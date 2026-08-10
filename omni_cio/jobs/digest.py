from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from omni_cio.contracts.v1.domain import OWNER_TENANT_ID
from omni_cio.persistence.migration import ConnectionLike


def _utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("durable job digest requires timezone-aware timestamps")
    return value.astimezone(timezone.utc).isoformat()


def _value(value: Any) -> Any:
    if isinstance(value, datetime):
        return _utc(value)
    if isinstance(value, bytes):
        return hashlib.sha256(value).hexdigest()
    return value


def _update_digest(digest: Any, table: str, rows: list[Any]) -> None:
    for row in rows:
        encoded = json.dumps(
            [table, *(_value(value) for value in row)],
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        digest.update(encoded)
        digest.update(b"\n")


def durable_job_state_digest(connection: ConnectionLike) -> str:
    """Hash all durable WP14 job state and append-only transition history."""

    digest = hashlib.sha256()
    job_rows = connection.execute(
        "SELECT job_id, job_type, idempotency_key, payload_sha256, state, "
        "correlation_id, lease_owner, lease_expires_at, heartbeat_at, attempts, "
        "max_attempts, next_run_at, started_at, completed_at, error_class, "
        "recovery_policy, created_at "
        "FROM omni_cio_v10.jobs WHERE tenant_id = %s ORDER BY job_id",
        (OWNER_TENANT_ID,),
    ).fetchall()
    _update_digest(digest, "jobs", job_rows)

    event_rows = connection.execute(
        "SELECT event_id, job_id, event_type, from_state, to_state, attempt, "
        "worker_id, error_class, occurred_at, record_sha256 "
        "FROM omni_cio_v10.job_events WHERE tenant_id = %s ORDER BY event_id",
        (OWNER_TENANT_ID,),
    ).fetchall()
    _update_digest(digest, "job_events", event_rows)
    return digest.hexdigest()