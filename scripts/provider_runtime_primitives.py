from __future__ import annotations

import os
import time
from typing import Any
from urllib.parse import unquote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


_TRANSIENT_RETRY_DELAYS_SECONDS = (1.0, 2.0)
_DATABASE_CONNECT_TIMEOUT_SECONDS = 15


class ProvisioningStopped(RuntimeError):
    """Fail-closed provider/runtime orchestration stop with a sanitized code."""

    def __init__(self, code: str, *, status: int | None = None) -> None:
        self.code = code
        self.status = status
        suffix = f" status={status}" if status is not None else ""
        super().__init__(f"{code}{suffix}")


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(
        self,
        request: Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> None:
        del request, file_pointer, code, message, headers, new_url
        return None


_NO_REDIRECT_OPENER = build_opener(_RejectRedirects())


def _mask(value: str) -> None:
    if value:
        print(f"::add-mask::{value}")


def _emit(message: str) -> None:
    print(message, flush=True)


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ProvisioningStopped(f"{name}_REQUIRED")
    _mask(value)
    return value


def _json_object(value: Any, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProvisioningStopped(code)
    return value


def _json_list(value: Any, code: str) -> list[Any]:
    if not isinstance(value, list):
        raise ProvisioningStopped(code)
    return value


def _safe_api_path(path: str, code: str) -> str:
    if not path.startswith("/") or path.startswith("//") or "\\" in path:
        raise ProvisioningStopped(code)
    if any(character in path for character in ("\r", "\n", "\x00")):
        raise ProvisioningStopped(code)
    parsed = urlsplit(path)
    if parsed.scheme or parsed.netloc or parsed.fragment:
        raise ProvisioningStopped(code)
    for raw_segment in parsed.path.split("/"):
        segment = unquote(raw_segment)
        if segment in {".", ".."} or "/" in segment or "\\" in segment:
            raise ProvisioningStopped(code)
    return path


def _connect_postgres_with_retry(
    psycopg_module: Any,
    uri: str,
    *,
    retry_marker: str,
    failure_code: str,
) -> Any:
    attempts = len(_TRANSIENT_RETRY_DELAYS_SECONDS) + 1
    for attempt in range(attempts):
        try:
            return psycopg_module.connect(
                uri,
                autocommit=True,
                connect_timeout=_DATABASE_CONNECT_TIMEOUT_SECONDS,
            )
        except psycopg_module.OperationalError:
            if attempt + 1 >= attempts:
                raise ProvisioningStopped(failure_code) from None
            _emit(f"{retry_marker} attempt={attempt + 2}/{attempts}")
            time.sleep(_TRANSIENT_RETRY_DELAYS_SECONDS[attempt])
    raise AssertionError("bounded PostgreSQL connection retry exhausted")
