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


NEON_API_BASE = "https://console.neon.tech/api/v2"
ATTESTATION_PATTERN = re.compile(
    r"^NO_PAYMENT_METHOD_CONFIRMED:"
    r"(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)$"
)
NEON_ORG_ID_PATTERN = re.compile(r"^[a-z0-9-]{1,60}$")
MAX_ATTESTATION_AGE = timedelta(hours=24)
MAX_FUTURE_CLOCK_SKEW = timedelta(minutes=5)
_TRANSIENT_HTTP_STATUSES = frozenset({408, 423, 429, 502, 503, 504})
_RETRY_DELAYS_SECONDS = (1.0, 2.0)
_HTTP_TIMEOUT_SECONDS = 30.0
_MAX_RESPONSE_BYTES = 1_048_576
_NEON_HTTP_ERROR = "NEON_PLAN_PREFLIGHT_HTTP_ERROR"
_NEON_RESPONSE_INVALID = "NEON_ORGANIZATION_RESPONSE_INVALID"


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


def validate_neon_org_id(value: str) -> str:
    if NEON_ORG_ID_PATTERN.fullmatch(value) is None:
        raise BoundaryStopped("NEON_ORG_ID_INVALID")
    return value


def _decode_json_object(raw: bytes, code: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise BoundaryStopped(code) from None
    if not isinstance(payload, dict):
        raise BoundaryStopped(code)
    return payload


def _neon_organization_url(organization_id: str) -> str:
    return f"{NEON_API_BASE}/organizations/{validate_neon_org_id(organization_id)}"


def _neon_request(token: str, organization_id: str) -> Request:
    return Request(
        _neon_organization_url(organization_id),
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


def _read_neon_organization_once(
    token: str,
    organization_id: str,
    open_url: OpenUrl,
) -> bytes:
    try:
        request = _neon_request(token, organization_id)
        with open_url(request, timeout=_HTTP_TIMEOUT_SECONDS) as response:
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
        raise BoundaryStopped("NEON_ORGANIZATION_RESPONSE_TOO_LARGE")
    return raw


def _decode_neon_organization(
    raw: bytes,
    expected_org_id: str,
) -> dict[str, Any]:
    payload = _decode_json_object(raw, _NEON_RESPONSE_INVALID)
    organization = payload.get("organization", payload)
    if not isinstance(organization, dict):
        raise BoundaryStopped(_NEON_RESPONSE_INVALID)
    validate_neon_free_organization(organization, expected_org_id=expected_org_id)
    return organization


def read_neon_organization(
    token: str,
    organization_id: str,
    *,
    opener: OpenUrl | None = None,
    sleeper: Sleep = time.sleep,
) -> dict[str, Any]:
    safe_org_id = validate_neon_org_id(organization_id)
    open_url = _NO_REDIRECT_OPENER.open if opener is None else opener
    attempt = 0
    while True:
        try:
            raw = _read_neon_organization_once(token, safe_org_id, open_url)
        except _RetryableBoundary as exc:
            if attempt >= len(_RETRY_DELAYS_SECONDS):
                raise BoundaryStopped(exc.code, status=exc.status) from None
            sleeper(_RETRY_DELAYS_SECONDS[attempt])
            attempt += 1
            continue
        return _decode_neon_organization(raw, safe_org_id)


def validate_neon_free_organization(
    organization: Mapping[str, Any],
    *,
    expected_org_id: str,
) -> None:
    safe_org_id = validate_neon_org_id(expected_org_id)
    if organization.get("id") != safe_org_id:
        raise BoundaryStopped("NEON_ORGANIZATION_ID_MISMATCH")
    plan = organization.get("plan")
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
    neon_org_id = _required_env("NEON_ORG_ID", source)
    validate_render_zero_charge_attestation(attestation, now=now)
    read_neon_organization(
        neon_token,
        neon_org_id,
        opener=opener,
        sleeper=sleeper,
    )
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
