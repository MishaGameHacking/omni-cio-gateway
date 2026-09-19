from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal, InvalidOperation
import json
import re
import time
from typing import Any, NoReturn
from urllib.error import HTTPError
from urllib.request import OpenerDirector, Request

from scripts import provision_v10_render_neon_preview as _provider_base


API_BASE = "https://api.timeweb.cloud"
TOKEN_ENV = "TIMEWEB_CLOUD_API_TOKEN"
TARGET_PROJECT_NAME = "Общий проект"
TARGET_CLUSTER_NAME = "omni-cio-v10-ru-pg-synthetic"
TARGET_LOCATION = "ru-3"
TARGET_CPU = 1
TARGET_RAM_MB = 2048
TARGET_DISK_MB = 20 * 1024
TARGET_PRICE_RUB = Decimal("790")
MAX_RESPONSE_BYTES = 1024 * 1024
_RETRY_DELAYS_SECONDS = (1.0, 2.0)
_TRANSIENT_HTTP_STATUSES = frozenset({408, 429, 502, 503, 504})
_PROVIDER_TYPE_PATTERN = re.compile(r"^[a-z0-9_-]{1,64}$")
_PROVIDER_ID_PATTERN = re.compile(r"^\d{1,20}$", re.ASCII)
Sleep = Callable[[float], None]


class TimewebReadOnlyApi:
    def __init__(
        self,
        token: str,
        *,
        opener: OpenerDirector | Any | None = None,
        sleeper: Sleep = time.sleep,
    ) -> None:
        if not token:
            raise _provider_base.ProvisioningStopped(
                "TIMEWEB_CLOUD_API_TOKEN_REQUIRED"
            )
        self._token = token
        self._opener = opener or _provider_base._NO_REDIRECT_OPENER
        self._sleeper = sleeper

    def _request(self, path: str) -> Request:
        safe_path = _provider_base._safe_api_path(
            path,
            "TIMEWEB_API_PATH_INVALID",
        )
        return Request(
            f"{API_BASE}{safe_path}",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self._token}",
                "User-Agent": "omni-cio-v10-ru-pg-readonly",
            },
            method="GET",
        )

    def _open_once(
        self,
        request: Request,
        timeout: float,
    ) -> tuple[int, bytes]:
        with self._opener.open(request, timeout=timeout) as response:
            return int(response.status), response.read(MAX_RESPONSE_BYTES + 1)

    @staticmethod
    def _retry_available(attempt: int, attempts: int) -> bool:
        return attempt + 1 < attempts

    def _sleep_before_retry(self, attempt: int) -> None:
        self._sleeper(_RETRY_DELAYS_SECONDS[attempt])

    def _raise_http_failure(self, status: int) -> NoReturn:
        if status in {401, 403}:
            raise _provider_base.ProvisioningStopped(
                "TIMEWEB_API_TOKEN_INVALID_OR_INSUFFICIENT",
                status=status,
            ) from None
        raise _provider_base.ProvisioningStopped(
            "TIMEWEB_API_HTTP_ERROR",
            status=status,
        ) from None

    def _open_with_retries(
        self,
        request: Request,
        timeout: float,
    ) -> tuple[int, bytes]:
        attempts = len(_RETRY_DELAYS_SECONDS) + 1
        for attempt in range(attempts):
            try:
                return self._open_once(request, timeout)
            except HTTPError as exc:
                status = int(exc.code)
                if (
                    status in _TRANSIENT_HTTP_STATUSES
                    and self._retry_available(attempt, attempts)
                ):
                    self._sleep_before_retry(attempt)
                    continue
                self._raise_http_failure(status)
            except OSError:
                if not self._retry_available(attempt, attempts):
                    raise _provider_base.ProvisioningStopped(
                        "TIMEWEB_API_NETWORK_ERROR"
                    ) from None
                self._sleep_before_retry(attempt)
        raise _provider_base.ProvisioningStopped(
            "TIMEWEB_API_RETRY_STATE_INVALID"
        )

    def _decode_response(self, status: int, raw: bytes) -> Any:
        if status != 200:
            raise _provider_base.ProvisioningStopped(
                "TIMEWEB_API_UNEXPECTED_STATUS",
                status=status,
            )
        if len(raw) > MAX_RESPONSE_BYTES:
            raise _provider_base.ProvisioningStopped(
                "TIMEWEB_API_RESPONSE_TOO_LARGE"
            )
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            raise _provider_base.ProvisioningStopped(
                "TIMEWEB_API_JSON_INVALID"
            ) from None

    def get(self, path: str, *, timeout: float = 30.0) -> Any:
        status, raw = self._open_with_retries(
            self._request(path),
            timeout,
        )
        return self._decode_response(status, raw)


def _rows(payload: object, key: str, code: str) -> list[dict[str, Any]]:
    body = _provider_base._json_object(payload, code)
    values = _provider_base._json_list(body.get(key), code)
    return [_provider_base._json_object(value, code) for value in values]


def _project_id(value: object) -> str:
    if isinstance(value, int) and not isinstance(value, bool):
        text = str(value)
    elif isinstance(value, str):
        text = value.strip()
    else:
        raise _provider_base.ProvisioningStopped(
            "TIMEWEB_PROJECT_ID_INVALID"
        )
    if _PROVIDER_ID_PATTERN.fullmatch(text) is None:
        raise _provider_base.ProvisioningStopped(
            "TIMEWEB_PROJECT_ID_INVALID"
        )
    return text


def _select_project(payload: object) -> str:
    rows = _rows(
        payload,
        "projects",
        "TIMEWEB_PROJECTS_RESPONSE_INVALID",
    )
    matches = [
        row
        for row in rows
        if row.get("name") == TARGET_PROJECT_NAME
    ]
    if len(matches) != 1:
        raise _provider_base.ProvisioningStopped(
            "TIMEWEB_TARGET_PROJECT_NOT_UNIQUE"
        )
    return _project_id(matches[0].get("id"))


def _major_version(value: object) -> int | None:
    try:
        return int(str(value).strip().split(".", maxsplit=1)[0])
    except (TypeError, ValueError):
        return None


def _provider_type(value: object) -> str:
    if not isinstance(value, str):
        raise _provider_base.ProvisioningStopped(
            "TIMEWEB_DATABASE_TYPE_INVALID"
        )
    normalized = value.strip().lower()
    if _PROVIDER_TYPE_PATTERN.fullmatch(normalized) is None:
        raise _provider_base.ProvisioningStopped(
            "TIMEWEB_DATABASE_TYPE_INVALID"
        )
    return normalized


def _select_postgres18_type(payload: object) -> str:
    matches: list[str] = []
    rows = _rows(
        payload,
        "types",
        "TIMEWEB_DATABASE_TYPES_RESPONSE_INVALID",
    )
    for row in rows:
        name = str(row.get("name", "")).strip().casefold()
        if name != "postgresql" or _major_version(row.get("version")) != 18:
            continue
        if row.get("is_deprecated") is True:
            continue
        matches.append(_provider_type(row.get("type")))
    if len(matches) != 1:
        raise _provider_base.ProvisioningStopped(
            "TIMEWEB_POSTGRES18_TYPE_NOT_UNIQUE"
        )
    return matches[0]


def _number(value: object, code: str) -> int:
    if isinstance(value, bool):
        raise _provider_base.ProvisioningStopped(code)
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise _provider_base.ProvisioningStopped(code) from None
    return number


def _price(value: object) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise _provider_base.ProvisioningStopped(
            "TIMEWEB_DATABASE_PRESET_PRICE_INVALID"
        ) from None


def _preset_type_candidates(provider_type: str) -> frozenset[str]:
    family = provider_type.rstrip("0123456789")
    return frozenset({provider_type, family})


def _select_target_preset(payload: object, provider_type: str) -> None:
    candidates = _preset_type_candidates(provider_type)
    matches: list[dict[str, Any]] = []
    rows = _rows(
        payload,
        "databases_presets",
        "TIMEWEB_DATABASE_PRESETS_RESPONSE_INVALID",
    )
    for row in rows:
        raw_type = row.get("type")
        if not isinstance(raw_type, str):
            continue
        if raw_type.strip().lower() not in candidates:
            continue
        if row.get("location") != TARGET_LOCATION:
            continue
        cpu = _number(
            row.get("cpu"),
            "TIMEWEB_DATABASE_PRESET_CPU_INVALID",
        )
        ram = _number(
            row.get("ram"),
            "TIMEWEB_DATABASE_PRESET_RAM_INVALID",
        )
        disk = _number(
            row.get("disk"),
            "TIMEWEB_DATABASE_PRESET_DISK_INVALID",
        )
        if (cpu, ram, disk) != (
            TARGET_CPU,
            TARGET_RAM_MB,
            TARGET_DISK_MB,
        ):
            continue
        if _price(row.get("price")) != TARGET_PRICE_RUB:
            continue
        matches.append(row)
    if len(matches) != 1:
        raise _provider_base.ProvisioningStopped(
            "TIMEWEB_BETA_PRESET_NOT_UNIQUE_OR_PRICE_DRIFT"
        )


def _verify_cluster_name_available(payload: object) -> None:
    rows = _rows(
        payload,
        "databases",
        "TIMEWEB_PROJECT_DATABASES_RESPONSE_INVALID",
    )
    if any(row.get("name") == TARGET_CLUSTER_NAME for row in rows):
        raise _provider_base.ProvisioningStopped(
            "TIMEWEB_TARGET_CLUSTER_ALREADY_EXISTS"
        )


def probe() -> None:
    token = _provider_base._required_env(TOKEN_ENV)
    api = TimewebReadOnlyApi(token)
    project_id = _select_project(api.get("/api/v1/projects"))
    provider_type = _select_postgres18_type(
        api.get("/api/v1/database-types")
    )
    _select_target_preset(
        api.get("/api/v2/presets/dbs"),
        provider_type,
    )
    project_path = (
        f"/api/v1/projects/{project_id}/resources/databases"
    )
    _verify_cluster_name_available(api.get(project_path))
    _provider_base._emit(
        "TIMEWEB_RU_PG_CONTROL_PLANE=READ_ONLY_READY "
        "pg=18 location=ru-3 cpu=1 ram_mb=2048 disk_gb=20 "
        "base_price_rub=790 project=verified cluster_name_available=true"
    )


def main() -> int:
    try:
        probe()
    except _provider_base.ProvisioningStopped as exc:
        _provider_base._emit(
            f"TIMEWEB_RU_PG_CONTROL_PLANE=STOPPED code={exc.code}"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
