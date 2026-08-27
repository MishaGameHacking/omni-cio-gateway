from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
import json
import os
import re
import sys
import time
from typing import Any, NoReturn, Protocol
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener


NEON_ORGANIZATIONS_URL = "https://console.neon.tech/api/v2/users/me/organizations"
ATTESTATION_PATTERN = re.compile(
    r"^NO_PAYMENT_METHOD_CONFIRMED:"
    r"(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)$"
)
MAX_ATTESTATION_AGE = timedelta(hours=24)
MAX_FUTURE_CLOCK_SKEW = timedelta(minutes=5)
_TRANSIENT_HTTP_STATUSES = frozenset({408, 429, 502, 503, 504})
_RETRY_DELAYS_SECONDS = (1.0, 2.0)
_HTTP_TIMEOUT_SECONDS = 30.0
_MAX_RESPONSE_BYTES = 1_048_576
_NEON_HTTP_ERROR = "NEON_PLAN_PREFLIGHT_HTTP_ERROR"
_NEON_RESPONSE_INVALID = "NEON_ORGANIZATIONS_RESPONSE_INVALID"


class HttpResponse(Protocol):
    status: int

    def __enter__(self) -> "HttpResponse": ...

    def __exit__(self, *args: object) -> None: ...

    def read(self, _: int = -1) -> bytes: ...


OpenUrl = Callable[..., HttpResponse]
Sleep = Callable[[float], None]


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


class BoundaryStopped(RuntimeError):
    def __init__(self, code: str, *, status: int | None = None) -> None:
        self.code = code
        self.status = status
        suffix = f" status={status}" if status is not None else ""
        super().__init__(f"{code}{suffix}")


class _RetryableBoundary(RuntimeError):
    def __init__(self, code: str, *, status: int | None = None) -> None:
        self.code = code
        self.status = status
        super().__init__(code)


def _required_env(name: str, env: Mapping[str, str]) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise BoundaryStopped(f"{name}_REQUIRED")
    return value


def _parse_attestation_timestamp(value: str) -> datetime:
    match = ATTESTATION_PATTERN.fullmatch(value)
    if match is None:
        raise BoundaryStopped("RENDER_ZERO_CHARGE_ATTESTATION_INVALID")
    timestamp = datetime.strptime(
        match.group("timestamp"),
        "%Y-%m-%dT%H:%M:%SZ",
    )
    return timestamp.replace(tzinfo=timezone.utc)


def validate_render_zero_charge_attestation(
    value: str,
    *,
    now: datetime | None = None,
) -> None:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    current = current.astimezone(timezone.utc)
    attested_at = _parse_attestation_timestamp(value)
    if attested_at > current + MAX_FUTURE_CLOCK_SKEW:
        raise BoundaryStopped("RENDER_ZERO_CHARGE_ATTESTATION_FROM_FUTURE")
    if current - attested_at > MAX_ATTESTATION_AGE:
        raise BoundaryStopped("RENDER_ZERO_CHARGE_ATTESTATION_STALE")


def _decode_json_object(raw: bytes, code: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeEror):
        raise BoundaryStopped(code) from None
    if not isinstance(payload, dict):
        raise BoundaryStopped(code)
    return payload


def _neon_request(token: str) -> Request:
    return Request(
        NEON_ORGANIZATIONS_URL,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "omni-cio-v10-zero-cost-preflight",
        },
        method="GET",
    )


def _raise_neon_http_failure(status: int) -> NoReturn:
    if 300 <= status < 400:
        raise BoundaryStopped(
            "NEON_PLAN_PREFLIGHT_REDIRECT_FORBIDDEN",
            status=status,
        ) from None
    if status == 401:
        raise BoundaryStopped("NEON_API_KEY_INVALID", status=status) from None
    if status == 403:
        raise BoundaryStopped("NEON_API_KEY_INSUFFICIENT", status=status) from None
    if status in _TRANSIENT_HTTP_STATUSES:
        raise _RetryableBoundary(_NEON_HTTP_ERROR, status=status) from None
    raise BoundaryStopped(_NEON_HTTP_ERROR, status=status) from None


def _read_neon_organizations_once(token: str, open_url: OpenUrl) -> bytes:
    try:
        with open_url(_neon_request(token), timeout=_HTTP_TIMEOUT_SECONDS) as response:
            status = int(response.status)
            raw = response.read(_MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        _raise_neon_http_failure(int(exc.code))
    except OSError:
        raise _RetryableBoundary("NEON_PLAN_PREFLIGHT_NETWORK_ERROR") from None

    if status in _TRANSIENT_HTTP_STATUSES:
        raise _RetryableBoundary(_NEON_HTTP_ERROR, status=status)
    if status != 200:
        raise BoundaryStopped(
            "NEON_PLAN_PREFLIGHT_UNEXPECTED_STATUS",
            status=status,
        )
    if len(raw) > _MAX_RESPONSE_BYTES:
        raise BoundaryStopped("NEON_ORGANIZATIONS_RESPONSE_TOO_LARGE")
    return raw


def _decode_neon_organizations(raw: bytes) -> list[dict[str, Any]]:
    payload = _decode_json_object(raw, _NEON_RESPONSE_INVALID)
    rows = payload.get("organizations")
    if not isinstance(rows, list):
        raise BoundaryStopped(_NEON_RESPONSE_INVALID)

    organizations: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise BoundaryStopped("NEON_ORGANIZATION_ROW_INVALID")
        organizations.append(row)
    return organizations


def read_neon_organizations(
    token: str,
    *,
    opener: OpenUrl | None = None,
    sleeper: Sleep = time.sleep,
) -> list[dict[str, Any]]:
    open_url = _NO_REDIRECT_OPENER.open if opener is None else opener
    attempt = 0
    while True:
        try:
            raw = _read_neon_organizations_once(token, open_url)
        except _RetryableBoundary as exc:
            if attempt >= len(_RETRY_DELAYS_SECONDS):
                raise BoundaryStopped(exc.code, status=exc.status) from None
            sleeper(_RETRY_DELAYS_SECONDS[attempt])
            attempt += 1
            continue
        return _decode_neon_organizations(raw)


def validate_neon_free_organization(
    organizations: list[dict[str, Any]],
) -> None:
    if len(organizations) != 1:
        raise BoundaryStopped("NEON_ORGANIZATION_NOT_UNIQUE")
    organization = organizations[0]
    org_id = organization.get("id")
    plan = organization.get("plan")
    if not isinstance(org_id, str) or not org_id:
        raise BoundaryStopped("NEON_ORGANIZATION_ID_MISSING")
    if not isinstance(plan, str) or plan.casefold() != "free":
        raise BoundaryStopped("NEON_FREE_PLAN_REQUIRED")


def verify_zero_cost_provider_boundary(
    *,
    env: Mapping[str, str] | None = None,
    now: datetime | None = None,
    opener: OpenUrl | None = None,
    sleeper: Sleep = time.sleep,
) -> None:
    source = os.environ if env is None else env
    attestation = _required_env("RENDER_ZERO_CHARGE_ATTESTATION", source)
    neon_token = _required_env("NEON_API_KEY", source)
    validate_render_zero_charge_attestation(attestation, now=now)
    organizations = read_neon_organizations(
        neon_token,
        opener=opener,
        sleeper=sleeper,
    )
    validate_neon_free_organization(organizations)
    print("RENDER_ZERO_CHARGE_ATTESTATION=PASS_FRESH_NO_PAYMENT_METHOD")
    print("NEON_ORGANIZATION_PLAN=FREE_VERIFIED")


def main() -> int:
    try:
        verify_zero_cost_provider_boundary()
    except BoundaryStopped as exc:
        suffix = f" status={exc.status}" if exc.status is not None else ""
        print(f"::error::{exc.code}{suffix}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
