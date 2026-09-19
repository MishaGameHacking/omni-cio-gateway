from __future__ import annotations

from collections.abc import Callable
import json
import os
import time
from typing import Any, NoReturn
from urllib.error import HTTPError
from urllib.request import OpenerDirector, Request

from scripts import probe_v10_timeweb_postgres_control_plane as read_only
from scripts import provision_v10_render_neon_preview as _provider_base


CREATE_PATH = "/api/v1/databases"
TARGET_AVAILABILITY_ZONE = "msk-1"
CREATE_CONFIRMATION = "CREATE_TIMEWEB_RU_PG_SYNTHETIC_790_RUB_MONTH"
CREATE_CONFIRMATION_ENV = "TIMEWEB_RU_PG_CREATE_CONFIRMATION"
MAX_RESPONSE_BYTES = 1024 * 1024
_RECONCILE_DELAYS_SECONDS = (1.0, 2.0, 4.0, 8.0, 15.0)
_START_DELAYS_SECONDS = (2.0, 3.0, 5.0, 5.0, 5.0, 10.0, 10.0, 10.0)
_AMBIGUOUS_HTTP_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
Sleep = Callable[[float], None]


class AmbiguousCreate(RuntimeError):
    pass


class TimewebCreateApi:
    def __init__(
        self,
        token: str,
        *,
        opener: OpenerDirector | Any | None = None,
    ) -> None:
        if not token:
            raise _provider_base.ProvisioningStopped("TIMEWEB_CLOUD_API_TOKEN_REQUIRED")
        self._token = token
        self._opener = opener or _provider_base._NO_REDIRECT_OPENER

    def _request(self, body: dict[str, object]) -> Request:
        encoded = json.dumps(
            body,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return Request(
            f"{read_only.API_BASE}{CREATE_PATH}",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
                "User-Agent": "omni-cio-v10-ru-pg-synthetic-create",
            },
            data=encoded,
            method="POST",
        )

    def post_once(
        self,
        body: dict[str, object],
        *,
        timeout: float = 30.0,
    ) -> Any:
        request = self._request(body)
        try:
            with self._opener.open(request, timeout=timeout) as response:
                status = int(response.status)
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            status = int(exc.code)
            if status in _AMBIGUOUS_HTTP_STATUSES:
                raise AmbiguousCreate("TIMEWEB_CLUSTER_CREATE_AMBIGUOUS") from None
            if status in {401, 403}:
                raise _provider_base.ProvisioningStopped(
                    "TIMEWEB_API_TOKEN_INVALID_OR_INSUFFICIENT",
                    status=status,
                ) from None
            raise _provider_base.ProvisioningStopped(
                "TIMEWEB_CLUSTER_CREATE_REJECTED",
                status=status,
            ) from None
        except OSError:
            raise AmbiguousCreate("TIMEWEB_CLUSTER_CREATE_AMBIGUOUS") from None

        if status != 201:
            if status in _AMBIGUOUS_HTTP_STATUSES or 200 <= status < 300:
                raise AmbiguousCreate("TIMEWEB_CLUSTER_CREATE_AMBIGUOUS")
            raise _provider_base.ProvisioningStopped(
                "TIMEWEB_CLUSTER_CREATE_UNEXPECTED_STATUS",
                status=status,
            )
        if len(raw) > MAX_RESPONSE_BYTES:
            raise AmbiguousCreate("TIMEWEB_CLUSTER_CREATE_RESPONSE_TOO_LARGE")
        try:
            return json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise AmbiguousCreate("TIMEWEB_CLUSTER_CREATE_RESPONSE_INVALID") from None


def _required_confirmation() -> None:
    if os.environ.get(CREATE_CONFIRMATION_ENV, "").strip() != CREATE_CONFIRMATION:
        raise _provider_base.ProvisioningStopped(
            "TIMEWEB_CLUSTER_CREATE_CONFIRMATION_REQUIRED"
        )


def _numeric_id(value: object, code: str) -> int:
    if isinstance(value, bool):
        raise _provider_base.ProvisioningStopped(code)
    if isinstance(value, int):
        number = value
    elif isinstance(value, float) and value.is_integer():
        number = int(value)
    elif isinstance(value, str) and value.isascii() and value.isdigit():
        number = int(value)
    else:
        raise _provider_base.ProvisioningStopped(code)
    if number <= 0:
        raise _provider_base.ProvisioningStopped(code)
    return number


def _target_cluster_id(payload: object) -> int | None:
    rows = read_only._rows(
        payload,
        "databases",
        "TIMEWEB_PROJECT_DATABASES_RESPONSE_INVALID",
    )
    matches = [row for row in rows if row.get("name") == read_only.TARGET_CLUSTER_NAME]
    if len(matches) > 1:
        raise _provider_base.ProvisioningStopped(
            "TIMEWEB_TARGET_CLUSTER_NOT_UNIQUE"
        )
    if not matches:
        return None
    return _numeric_id(
        matches[0].get("id"),
        "TIMEWEB_TARGET_CLUSTER_ID_INVALID",
    )


def _create_response_cluster_id(payload: object) -> int:
    body = _provider_base._json_object(
        payload,
        "TIMEWEB_CLUSTER_CREATE_RESPONSE_INVALID",
    )
    cluster = _provider_base._json_object(
        body.get("db"),
        "TIMEWEB_CLUSTER_CREATE_RESPONSE_INVALID",
    )
    if cluster.get("name") != read_only.TARGET_CLUSTER_NAME:
        raise _provider_base.ProvisioningStopped(
            "TIMEWEB_CLUSTER_CREATE_RESPONSE_INVALID"
        )
    return _numeric_id(
        cluster.get("id"),
        "TIMEWEB_CLUSTER_CREATE_RESPONSE_INVALID",
    )


def _create_payload(
    *,
    provider_type: str,
    preset_id: int,
    project_id: str,
) -> dict[str, object]:
    return {
        "availability_zone": TARGET_AVAILABILITY_ZONE,
        "description": "Omni-CIO V10 RU-PG-B synthetic parity",
        "disk_autoscaling": {"is_enabled": False},
        "is_public_ipv6": False,
        "name": read_only.TARGET_CLUSTER_NAME,
        "preset_id": preset_id,
        "project_id": _numeric_id(project_id, "TIMEWEB_PROJECT_ID_INVALID"),
        "type": provider_type,
    }


def _reconcile_cluster_id(
    api: read_only.TimewebReadOnlyApi,
    project_path: str,
    *,
    sleeper: Sleep = time.sleep,
    delays: tuple[float, ...] = _RECONCILE_DELAYS_SECONDS,
) -> int:
    attempts = len(delays) + 1
    for attempt in range(attempts):
        cluster_id = _target_cluster_id(api.get(project_path))
        if cluster_id is not None:
            return cluster_id
        if attempt < len(delays):
            sleeper(delays[attempt])
    raise _provider_base.ProvisioningStopped(
        "TIMEWEB_CLUSTER_CREATE_AMBIGUOUS_RECONCILIATION_REQUIRED"
    )


def _create_or_reconcile(
    mutation_api: TimewebCreateApi,
    read_api: read_only.TimewebReadOnlyApi,
    project_path: str,
    payload: dict[str, object],
    *,
    sleeper: Sleep = time.sleep,
    reconcile_delays: tuple[float, ...] = _RECONCILE_DELAYS_SECONDS,
) -> tuple[int, str]:
    try:
        response = mutation_api.post_once(payload)
    except AmbiguousCreate:
        return (
            _reconcile_cluster_id(
                read_api,
                project_path,
                sleeper=sleeper,
                delays=reconcile_delays,
            ),
            "reconciled",
        )

    try:
        return _create_response_cluster_id(response), "created"
    except _provider_base.ProvisioningStopped:
        return (
            _reconcile_cluster_id(
                read_api,
                project_path,
                sleeper=sleeper,
                delays=reconcile_delays,
            ),
            "reconciled",
        )


def _disk_size(cluster: dict[str, Any]) -> int:
    disk = _provider_base._json_object(
        cluster.get("disk"),
        "TIMEWEB_CLUSTER_DISK_INVALID",
    )
    return read_only._number(
        disk.get("size"),
        "TIMEWEB_CLUSTER_DISK_INVALID",
    )


def _verify_disk_autoscaling(cluster: dict[str, Any]) -> None:
    value = cluster.get("disk_autoscaling")
    if value is None:
        return
    settings = _provider_base._json_object(
        value,
        "TIMEWEB_CLUSTER_DISK_AUTOSCALING_INVALID",
    )
    if settings.get("is_enabled") is not False:
        raise _provider_base.ProvisioningStopped(
            "TIMEWEB_CLUSTER_DISK_AUTOSCALING_ENABLED"
        )


def _verify_cluster_shape(
    payload: object,
    *,
    expected_cluster_id: int,
    provider_type: str,
    preset_id: int,
) -> str:
    body = _provider_base._json_object(payload, "TIMEWEB_CLUSTER_RESPONSE_INVALID")
    cluster = _provider_base._json_object(
        body.get("db"),
        "TIMEWEB_CLUSTER_RESPONSE_INVALID",
    )
    if _numeric_id(cluster.get("id"), "TIMEWEB_TARGET_CLUSTER_ID_INVALID") != (
        expected_cluster_id
    ):
        raise _provider_base.ProvisioningStopped("TIMEWEB_CLUSTER_ID_DRIFT")
    expected = {
        "name": read_only.TARGET_CLUSTER_NAME,
        "type": provider_type,
        "location": read_only.TARGET_LOCATION,
        "availability_zone": TARGET_AVAILABILITY_ZONE,
        "cpu": read_only.TARGET_CPU,
        "ram": read_only.TARGET_RAM_MB,
        "preset_id": preset_id,
        "is_enabled_public_network": False,
        "is_enabled_public_ipv6": False,
        "is_autobackups_enabled": False,
        "is_backup_schedule_enabled": False,
    }
    for key, value in expected.items():
        if cluster.get(key) != value:
            raise _provider_base.ProvisioningStopped(
                "TIMEWEB_CLUSTER_POST_CREATE_DRIFT"
            )
    if _disk_size(cluster) != read_only.TARGET_DISK_MB:
        raise _provider_base.ProvisioningStopped("TIMEWEB_CLUSTER_POST_CREATE_DRIFT")
    replicas = _provider_base._json_list(
        cluster.get("replica_list"),
        "TIMEWEB_CLUSTER_REPLICA_LIST_INVALID",
    )
    if replicas:
        raise _provider_base.ProvisioningStopped("TIMEWEB_CLUSTER_REPLICAS_PRESENT")
    _verify_disk_autoscaling(cluster)
    status = cluster.get("status")
    if not isinstance(status, str):
        raise _provider_base.ProvisioningStopped("TIMEWEB_CLUSTER_STATUS_INVALID")
    return status


def _wait_for_started(
    api: read_only.TimewebReadOnlyApi,
    cluster_id: int,
    *,
    provider_type: str,
    preset_id: int,
    sleeper: Sleep = time.sleep,
    delays: tuple[float, ...] = _START_DELAYS_SECONDS,
) -> None:
    path = f"/api/v1/databases/{cluster_id}"
    attempts = len(delays) + 1
    for attempt in range(attempts):
        status = _verify_cluster_shape(
            api.get(path),
            expected_cluster_id=cluster_id,
            provider_type=provider_type,
            preset_id=preset_id,
        )
        if status == "started":
            return
        if status != "starting":
            raise _provider_base.ProvisioningStopped(
                "TIMEWEB_CLUSTER_UNSAFE_STATUS"
            )
        if attempt < len(delays):
            sleeper(delays[attempt])
    raise _provider_base.ProvisioningStopped("TIMEWEB_CLUSTER_START_TIMEOUT")


def provision() -> None:
    _required_confirmation()
    token = _provider_base._required_env(read_only.TOKEN_ENV)
    read_api = read_only.TimewebReadOnlyApi(token)
    mutation_api = TimewebCreateApi(token)

    project_id = read_only._select_project(read_api.get("/api/v1/projects"))
    provider_type = read_only._select_postgres18_type(
        read_api.get("/api/v1/database-types")
    )
    preset_id = read_only._select_target_preset(
        read_api.get("/api/v2/presets/dbs"),
        provider_type,
    )
    project_path = f"/api/v1/projects/{project_id}/resources/databases"
    if _target_cluster_id(read_api.get(project_path)) is not None:
        raise _provider_base.ProvisioningStopped(
            "TIMEWEB_TARGET_CLUSTER_ALREADY_EXISTS"
        )

    payload = _create_payload(
        provider_type=provider_type,
        preset_id=preset_id,
        project_id=project_id,
    )
    cluster_id, create_mode = _create_or_reconcile(
        mutation_api,
        read_api,
        project_path,
        payload,
    )
    _wait_for_started(
        read_api,
        cluster_id,
        provider_type=provider_type,
        preset_id=preset_id,
    )
    if _target_cluster_id(read_api.get(project_path)) != cluster_id:
        raise _provider_base.ProvisioningStopped(
            "TIMEWEB_CLUSTER_PROJECT_CUSTODY_DRIFT"
        )

    _provider_base._emit(
        "TIMEWEB_RU_PG_SYNTHETIC_CREATE=READY "
        "pg=18 location=ru-3 zone=msk-1 cpu=1 ram_mb=2048 disk_gb=20 "
        "base_price_rub=790 project=verified cluster=verified addons=none "
        f"create_mode={create_mode}"
    )


def main() -> int:
    try:
        provision()
    except _provider_base.ProvisioningStopped as exc:
        _provider_base._emit(f"TIMEWEB_RU_PG_SYNTHETIC_CREATE=STOPPED code={exc.code}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
