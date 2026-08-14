from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from omni_cio.persistence.migration import (
    ConnectionLike,
    current_migration_state,
    discover_migrations,
)
from omni_cio.web.api_v1 import SESSION_COOKIE, SessionRegistryLike
from omni_cio.web.persistence_v1 import PostgresBrokerConnectionRepositoryV1
from omni_cio.web.session_v1 import SessionScopeV1


_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_MAX_RECENT_JOBS = 12
_MAX_RECENT_ERRORS = 8
_DISK_WARN_PERCENT = 20.0
_DISK_WARN_GIB = 50.0
_DISK_BLOCK_PERCENT = 10.0
_DISK_BLOCK_GIB = 20.0
_GPU_TEMP_LIMIT_C = 87.0
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
OperationalState = Literal[
    "READY",
    "PARTIAL",
    "STALE",
    "DEGRADED",
    "BLOCKED",
    "ERROR",
    "OFFLINE",
    "RECOVERING",
    "OWNER_ACTION_REQUIRED",
]
Availability = Literal[
    "AVAILABLE",
    "NOT_CONFIGURED",
    "NOT_AVAILABLE",
    "LOCKED_FUTURE_WP",
]


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("WP22 timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def _timestamp(value: object | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, datetime):
        raise ValueError("WP22 persisted timestamp must be datetime")
    return _utc(value).isoformat()


def _env_timestamp(name: str) -> str | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    candidate = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        return _utc(datetime.fromisoformat(candidate)).isoformat()
    except ValueError:
        return None


def _env_enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in _TRUE_VALUES


def _service(
    service_id: str,
    label: str,
    *,
    state: OperationalState,
    availability: Availability = "AVAILABLE",
    detail: str,
    observed_at: str | None = None,
) -> dict[str, Any]:
    return {
        "id": service_id,
        "label": label,
        "state": state,
        "availability": availability,
        "detail": detail,
        "observed_at": observed_at,
    }


def _job_state(value: str) -> OperationalState:
    if value == "SUCCEEDED":
        return "READY"
    if value in {"QUEUED", "RUNNING", "RETRY_WAIT"}:
        return "RECOVERING"
    if value in {"FAILED_PERMANENT", "RECONCILIATION_REQUIRED"}:
        return "DEGRADED"
    if value == "CANCELLED":
        return "OFFLINE"
    return "DEGRADED"


class SystemAdminReadServiceV1:
    """Sanitized OWNER-scoped operational projection for WP22.

    The service is intentionally read-only. It reuses accepted PostgreSQL,
    broker-connection and job state; it never reads secret values and never
    introduces Web/Telegram/AI/broker-write authority.
    """

    def __init__(
        self,
        connection: ConnectionLike,
        *,
        broker_repository: PostgresBrokerConnectionRepositoryV1,
        repo_root: Path | None = None,
        web_dist: Path | None = None,
        clock: Callable[[], datetime] | None = None,
        disk_usage: Callable[[str | os.PathLike[str]], Any] | None = None,
        command_runner: Callable[..., Any] | None = None,
    ) -> None:
        self._connection = connection
        self._broker_repository = broker_repository
        self._repo_root = repo_root or Path(__file__).resolve().parents[2]
        self._web_dist = web_dist or self._repo_root / "apps" / "web" / "dist"
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._disk_usage = disk_usage or shutil.disk_usage
        self._command_runner = command_runner or subprocess.run

    def _release(self) -> dict[str, Any]:
        sha = ""
        source = "unavailable"
        for name in ("OMNI_V10_IMPLEMENTATION_SHA", "GITHUB_SHA"):
            candidate = os.environ.get(name, "").strip().lower()
            if _GIT_SHA_RE.fullmatch(candidate):
                sha = candidate
                source = name.lower()
                break
        if not sha:
            try:
                result = self._command_runner(
                    ["git", "rev-parse", "HEAD"],
                    cwd=self._repo_root,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                candidate = str(getattr(result, "stdout", "")).strip().lower()
                if int(getattr(result, "returncode", 1)) == 0 and _GIT_SHA_RE.fullmatch(
                    candidate
                ):
                    sha = candidate
                    source = "git"
            except (OSError, subprocess.SubprocessError, ValueError):
                pass

        web_artifact_at = None
        try:
            web_artifact_at = datetime.fromtimestamp(
                (self._web_dist / "index.html").stat().st_mtime,
                tz=timezone.utc,
            ).isoformat()
        except OSError:
            pass

        deploy_at = _env_timestamp("OMNI_V10_LAST_DEPLOY_AT")
        return {
            "release": "V10_UNRELEASED",
            "git_sha": sha or None,
            "git_sha_source": source,
            "last_deploy_at": deploy_at,
            "last_deploy_source": (
                "omni_v10_last_deploy_at" if deploy_at is not None else "unavailable"
            ),
            "web_artifact_at": web_artifact_at,
            "web_artifact_source": (
                "web_dist_mtime" if web_artifact_at is not None else "unavailable"
            ),
        }

    def _database(self) -> tuple[dict[str, Any], OperationalState]:
        try:
            expected = tuple(
                (item.version, item.sha256) for item in discover_migrations()
            )
            current = current_migration_state(self._connection)
            exact = current == expected
            current_version = f"{int(current[-1][0]):04d}" if current else None
            expected_version = f"{int(expected[-1][0]):04d}" if expected else None
            state: OperationalState = "READY" if exact else "BLOCKED"
            return (
                {
                    "state": state,
                    "availability": "AVAILABLE",
                    "current_migration": current_version,
                    "expected_migration": expected_version,
                    "migration_count": len(current),
                    "exact_migration_state": exact,
                },
                state,
            )
        except Exception:
            return (
                {
                    "state": "DEGRADED",
                    "availability": "NOT_AVAILABLE",
                    "current_migration": None,
                    "expected_migration": None,
                    "migration_count": 0,
                    "exact_migration_state": False,
                },
                "DEGRADED",
            )

    def _recent_jobs(self, *, tenant_id: str) -> list[dict[str, Any]]:
        try:
            rows = list(
                self._connection.execute(
                    "SELECT job_type, state, attempts, max_attempts, error_class, "
                    "COALESCE(completed_at, started_at, next_run_at, created_at) "
                    "FROM omni_cio_v10.jobs WHERE tenant_id = %s "
                    "ORDER BY COALESCE(completed_at, started_at, next_run_at, created_at) "
                    "DESC, job_id DESC LIMIT %s",
                    (tenant_id, _MAX_RECENT_JOBS),
                ).fetchall()
            )
        except Exception:
            return []

        jobs: list[dict[str, Any]] = []
        for row in rows:
            jobs.append(
                {
                    "job_type": str(row[0]),
                    "state": str(row[1]),
                    "attempts": int(row[2]),
                    "max_attempts": int(row[3]),
                    "error_class": None if row[4] is None else str(row[4]),
                    "observed_at": _timestamp(row[5]),
                }
            )
        return jobs

    def _recent_errors(self, *, tenant_id: str) -> list[dict[str, Any]]:
        try:
            rows = list(
                self._connection.execute(
                    "SELECT job_type, state, error_class, "
                    "COALESCE(completed_at, started_at, next_run_at, created_at) "
                    "FROM omni_cio_v10.jobs "
                    "WHERE tenant_id = %s AND error_class IS NOT NULL "
                    "ORDER BY COALESCE(completed_at, started_at, next_run_at, created_at) "
                    "DESC, job_id DESC LIMIT %s",
                    (tenant_id, _MAX_RECENT_ERRORS),
                ).fetchall()
            )
        except Exception:
            return []

        errors: list[dict[str, Any]] = []
        for row in rows:
            errors.append(
                {
                    "job_type": str(row[0]),
                    "state": str(row[1]),
                    "error_class": str(row[2]),
                    "observed_at": _timestamp(row[3]),
                }
            )
        return errors

    def _latest_job(
        self,
        *,
        tenant_id: str,
        job_type: str,
    ) -> Sequence[Any] | None:
        try:
            return self._connection.execute(
                "SELECT state, error_class, "
                "COALESCE(completed_at, started_at, next_run_at, created_at) "
                "FROM omni_cio_v10.jobs "
                "WHERE tenant_id = %s AND job_type = %s "
                "ORDER BY COALESCE(completed_at, started_at, next_run_at, created_at) "
                "DESC, job_id DESC LIMIT 1",
                (tenant_id, job_type),
            ).fetchone()
        except Exception:
            return None

    def _backup(self, *, tenant_id: str) -> dict[str, Any]:
        try:
            row = self._connection.execute(
                "SELECT completed_at FROM omni_cio_v10.jobs "
                "WHERE tenant_id = %s AND job_type = 'BACKUP' AND state = 'SUCCEEDED' "
                "ORDER BY completed_at DESC, job_id DESC LIMIT 1",
                (tenant_id,),
            ).fetchone()
        except Exception:
            row = None
        if row is None:
            return {
                "state": "OFFLINE",
                "availability": "NOT_AVAILABLE",
                "last_success_at": None,
                "rpo_minutes": 60,
                "rto_minutes": 240,
            }
        return {
            "state": "READY",
            "availability": "AVAILABLE",
            "last_success_at": _timestamp(row[0]),
            "rpo_minutes": 60,
            "rto_minutes": 240,
        }

    def _disk(self) -> dict[str, Any]:
        root = self._repo_root.anchor or str(self._repo_root)
        try:
            usage = self._disk_usage(root)
            total = float(usage.total)
            free = float(usage.free)
            free_gib = free / (1024**3)
            free_percent = (free / total * 100.0) if total > 0 else 0.0
            if free_percent < _DISK_BLOCK_PERCENT or free_gib < _DISK_BLOCK_GIB:
                state: OperationalState = "BLOCKED"
            elif free_percent < _DISK_WARN_PERCENT or free_gib < _DISK_WARN_GIB:
                state = "DEGRADED"
            else:
                state = "READY"
            return {
                "state": state,
                "availability": "AVAILABLE",
                "free_gib": round(free_gib, 1),
                "free_percent": round(free_percent, 1),
                "warning_threshold_gib": _DISK_WARN_GIB,
                "block_threshold_gib": _DISK_BLOCK_GIB,
            }
        except (OSError, ValueError, ZeroDivisionError):
            return {
                "state": "DEGRADED",
                "availability": "NOT_AVAILABLE",
                "free_gib": None,
                "free_percent": None,
                "warning_threshold_gib": _DISK_WARN_GIB,
                "block_threshold_gib": _DISK_BLOCK_GIB,
            }

    def _temperature(self) -> dict[str, Any]:
        executable = shutil.which("nvidia-smi")
        if executable is None:
            return {
                "state": "OFFLINE",
                "availability": "NOT_AVAILABLE",
                "gpu_c": None,
                "limit_c": _GPU_TEMP_LIMIT_C,
            }
        try:
            result = self._command_runner(
                [
                    executable,
                    "--query-gpu=temperature.gpu",
                    "--format=csv,noheader,nounits",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
            if int(getattr(result, "returncode", 1)) != 0:
                raise ValueError("temperature command failed")
            values = [
                float(item.strip())
                for item in str(getattr(result, "stdout", "")).splitlines()
                if item.strip()
            ]
            if not values:
                raise ValueError("temperature missing")
            peak = max(values)
            return {
                "state": "READY" if peak <= _GPU_TEMP_LIMIT_C else "DEGRADED",
                "availability": "AVAILABLE",
                "gpu_c": round(peak, 1),
                "limit_c": _GPU_TEMP_LIMIT_C,
            }
        except (OSError, subprocess.SubprocessError, ValueError):
            return {
                "state": "DEGRADED",
                "availability": "NOT_AVAILABLE",
                "gpu_c": None,
                "limit_c": _GPU_TEMP_LIMIT_C,
            }

    def _tinvest(self, *, tenant_id: str) -> dict[str, Any]:
        try:
            records = self._broker_repository.list_read_connections(tenant_id=tenant_id)
        except Exception:
            return _service(
                "t_invest",
                "T-Invest READ",
                state="DEGRADED",
                availability="NOT_AVAILABLE",
                detail="Connection state unavailable.",
            )
        active = sum(1 for item in records if item.state == "ACTIVE")
        if active:
            return _service(
                "t_invest",
                "T-Invest READ",
                state="READY",
                detail=f"{active} verified READ connection(s).",
            )
        if records:
            return _service(
                "t_invest",
                "T-Invest READ",
                state="DEGRADED",
                detail="No active READ connection.",
            )
        return _service(
            "t_invest",
            "T-Invest READ",
            state="OFFLINE",
            availability="NOT_CONFIGURED",
            detail="No READ connection configured.",
        )

    def _job_service(
        self,
        *,
        tenant_id: str,
        job_type: str,
        service_id: str,
        label: str,
    ) -> dict[str, Any]:
        row = self._latest_job(tenant_id=tenant_id, job_type=job_type)
        if row is None:
            return _service(
                service_id,
                label,
                state="OFFLINE",
                availability="NOT_AVAILABLE",
                detail="No durable job observation available.",
            )
        state = str(row[0])
        error_class = None if row[1] is None else str(row[1])
        detail = f"Last durable job: {state}."
        if error_class is not None:
            detail += f" Error class: {error_class}."
        return _service(
            service_id,
            label,
            state=_job_state(state),
            detail=detail,
            observed_at=_timestamp(row[2]),
        )

    def read(self, *, tenant_id: str) -> dict[str, Any]:
        now = _utc(self._clock())
        database, database_state = self._database()
        jobs = self._recent_jobs(tenant_id=tenant_id)
        errors = self._recent_errors(tenant_id=tenant_id)
        backup = self._backup(tenant_id=tenant_id)
        disk = self._disk()
        temperature = self._temperature()
        real_trading_enabled = _env_enabled("REAL_TRADING_ENABLED")
        watchtower_enabled = _env_enabled("WATCHTOWER_ENABLED")

        services = [
            _service(
                "web",
                "Local Web",
                state="READY",
                detail="Authenticated local/private Web API is responding.",
                observed_at=now.isoformat(),
            ),
            _service(
                "database",
                "PostgreSQL",
                state=database_state,
                availability=(
                    "AVAILABLE"
                    if database["availability"] == "AVAILABLE"
                    else "NOT_AVAILABLE"
                ),
                detail=(
                    "Migration state matches source-controlled series."
                    if database_state == "READY"
                    else "Migration/connection state is not proven current."
                ),
            ),
            self._tinvest(tenant_id=tenant_id),
            self._job_service(
                tenant_id=tenant_id,
                job_type="WATCHTOWER",
                service_id="watchtower",
                label="Watchtower",
            ),
            _service(
                "telegram",
                "Telegram",
                state="OFFLINE",
                availability="LOCKED_FUTURE_WP",
                detail="Runtime activation is owned by WP23+ and remains locked.",
            ),
            _service(
                "ai",
                "AI / Cortex",
                state="OFFLINE",
                availability="LOCKED_FUTURE_WP",
                detail="Runtime activation is owned by WP27+ and remains locked.",
            ),
        ]

        current_services = [
            item for item in services if item["availability"] != "LOCKED_FUTURE_WP"
        ]
        blocking = (
            database_state == "BLOCKED"
            or disk["state"] == "BLOCKED"
            or real_trading_enabled
        )
        degraded = (
            any(item["state"] in {"DEGRADED", "ERROR"} for item in current_services)
            or disk["state"] == "DEGRADED"
            or temperature["state"] == "DEGRADED"
        )
        partial = (
            backup["availability"] != "AVAILABLE"
            or temperature["availability"] != "AVAILABLE"
            or any(item["availability"] != "AVAILABLE" for item in current_services)
        )
        overall: OperationalState = (
            "BLOCKED"
            if blocking
            else "DEGRADED"
            if degraded
            else "PARTIAL"
            if partial
            else "READY"
        )

        return {
            "schema_version": "1.0.0",
            "generated_at": now.isoformat(),
            "state": overall,
            "release": self._release(),
            "database": database,
            "backup": backup,
            "resources": {
                "disk": disk,
                "temperature": temperature,
            },
            "safety": {
                "mode": "READ_ONLY_DIAGNOSTIC",
                "real_execution_enabled": real_trading_enabled,
                "trading_methods": False,
                "broker_write_authority": False,
                "public_ingress": False,
                "watchtower_enabled": watchtower_enabled,
            },
            "services": services,
            "recent_jobs": jobs,
            "recent_errors": errors,
            "limits": {
                "recent_jobs": _MAX_RECENT_JOBS,
                "recent_errors": _MAX_RECENT_ERRORS,
            },
        }


def _require_system_session(
    request: Request,
    *,
    sessions: SessionRegistryLike,
    now: Callable[[], datetime],
) -> SessionScopeV1:
    scope = sessions.resolve(request.cookies.get(SESSION_COOKIE), now=_utc(now()))
    if scope is None:
        raise HTTPException(status_code=401, detail="AUTHENTICATION_REQUIRED")
    return scope


def install_system_admin_routes(
    app: FastAPI,
    *,
    sessions: SessionRegistryLike,
    service: SystemAdminReadServiceV1,
    now: Callable[[], datetime] | None = None,
) -> None:
    clock = now or (lambda: datetime.now(timezone.utc))

    @app.get("/api/v10/web/system-status")
    def system_status(request: Request) -> JSONResponse:
        scope = _require_system_session(request, sessions=sessions, now=clock)
        payload = service.read(tenant_id=scope.tenant_id)
        return JSONResponse(
            payload,
            headers={
                "Cache-Control": "no-store",
                "Pragma": "no-cache",
            },
        )
