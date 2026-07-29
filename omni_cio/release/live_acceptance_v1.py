from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from time import sleep
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from omni_cio.contracts.v1.release import LiveReleaseAcceptanceV1
from omni_cio.release.read_only_contract_v1 import (
    ReadOnlyReleaseError,
    build_read_only_release_manifest,
)


_DEFAULT_MAX_BYTES = 2_000_000
_DEFAULT_TIMEOUT_SECONDS = 20.0
_DEFAULT_ATTEMPTS = 5
_REQUIRED_CAPABILITIES = frozenset(
    {
        "portfolio_market_snapshot",
        "portfolio_analytics",
        "cash_liquidity_diagnostics",
        "purchase_capacity_preview",
        "operations_analytics",
        "broker_report_reconciliation",
        "regression_shield",
    }
)


class LiveReleaseAcceptanceError(RuntimeError):
    """The deployed gateway is not a verified read-only release."""


@dataclass(frozen=True, slots=True)
class FetchedJsonDocument:
    requested_url: str
    final_url: str
    status_code: int
    content_type: str
    payload: Mapping[str, Any]


JsonFetcher = Callable[[str], FetchedJsonDocument]


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise LiveReleaseAcceptanceError(code)
    return value


def _normalize_base_url(base_url: str, approved_hosts: frozenset[str]) -> str:
    candidate = base_url.strip().rstrip("/")
    parsed = urlparse(candidate)
    try:
        port = parsed.port
    except ValueError as exc:
        raise LiveReleaseAcceptanceError("LIVE_BASE_URL_NOT_APPROVED") from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname not in approved_hosts
        or port not in {None, 443}
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise LiveReleaseAcceptanceError("LIVE_BASE_URL_NOT_APPROVED")
    return f"https://{parsed.hostname}"


def _load_json_document(
    url: str,
    *,
    max_bytes: int = _DEFAULT_MAX_BYTES,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    attempts: int = _DEFAULT_ATTEMPTS,
    sleeper: Callable[[float], None] = sleep,
) -> FetchedJsonDocument:
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if attempts <= 0:
        raise ValueError("attempts must be positive")

    last_code = "LIVE_HTTP_UNAVAILABLE"
    for attempt in range(attempts):
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "omni-cio-live-acceptance/1.0",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                status_code = int(getattr(response, "status", response.getcode()))
                if not 200 <= status_code < 300:
                    raise LiveReleaseAcceptanceError("LIVE_HTTP_STATUS_REJECTED")
                final_url = str(response.geturl())
                content_type = str(response.headers.get("Content-Type", "")).lower()
                if "application/json" not in content_type:
                    raise LiveReleaseAcceptanceError("LIVE_CONTENT_TYPE_REJECTED")
                raw = response.read(max_bytes + 1)
                if len(raw) > max_bytes:
                    raise LiveReleaseAcceptanceError("LIVE_DOCUMENT_TOO_LARGE")
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise LiveReleaseAcceptanceError("LIVE_JSON_INVALID") from exc
                return FetchedJsonDocument(
                    requested_url=url,
                    final_url=final_url,
                    status_code=status_code,
                    content_type=content_type,
                    payload=_mapping(payload, "LIVE_JSON_OBJECT_REQUIRED"),
                )
        except HTTPError as exc:
            if exc.code == 429 or 500 <= exc.code < 600:
                last_code = "LIVE_HTTP_RETRY_EXHAUSTED"
            else:
                raise LiveReleaseAcceptanceError("LIVE_HTTP_STATUS_REJECTED") from exc
        except (TimeoutError, URLError):
            last_code = "LIVE_HTTP_RETRY_EXHAUSTED"

        if attempt + 1 < attempts:
            sleeper(min(15.0, 2.0**attempt))

    raise LiveReleaseAcceptanceError(last_code)


def accept_live_read_only_release(
    *,
    base_url: str,
    expected_app_version: str,
    approved_hosts: frozenset[str],
    checked_at: datetime | None = None,
    fetcher: JsonFetcher | None = None,
) -> LiveReleaseAcceptanceV1:
    """Fetch and verify the deployed public health and OpenAPI documents."""

    canonical_base_url = _normalize_base_url(base_url, approved_hosts)
    health_url = f"{canonical_base_url}/health"
    openapi_url = f"{canonical_base_url}/openapi.json"
    load = fetcher or _load_json_document

    health_document = load(health_url)
    openapi_document = load(openapi_url)
    if health_document.requested_url != health_url:
        raise LiveReleaseAcceptanceError("LIVE_HEALTH_REQUEST_MISMATCH")
    if openapi_document.requested_url != openapi_url:
        raise LiveReleaseAcceptanceError("LIVE_OPENAPI_REQUEST_MISMATCH")
    if health_document.final_url != health_url:
        raise LiveReleaseAcceptanceError("LIVE_HEALTH_REDIRECT_REJECTED")
    if openapi_document.final_url != openapi_url:
        raise LiveReleaseAcceptanceError("LIVE_OPENAPI_REDIRECT_REJECTED")

    health = health_document.payload
    if health.get("status") != "ok":
        raise LiveReleaseAcceptanceError("LIVE_HEALTH_STATUS_REJECTED")
    health_version = str(health.get("version") or "")
    if health_version != expected_app_version:
        raise LiveReleaseAcceptanceError("LIVE_HEALTH_VERSION_MISMATCH")
    if health.get("trading_methods") is not False:
        raise LiveReleaseAcceptanceError("LIVE_TRADING_METHODS_ENABLED")

    configured = _mapping(
        health.get("configured"),
        "LIVE_CONFIGURATION_STATUS_REQUIRED",
    )
    if configured.get("tinvest_token") is not True:
        raise LiveReleaseAcceptanceError("LIVE_TINVEST_NOT_CONFIGURED")
    if configured.get("gateway_api_key") is not True:
        raise LiveReleaseAcceptanceError("LIVE_GATEWAY_KEY_NOT_CONFIGURED")

    capabilities_raw = health.get("capabilities")
    if not isinstance(capabilities_raw, list) or not all(
        isinstance(item, str) for item in capabilities_raw
    ):
        raise LiveReleaseAcceptanceError("LIVE_CAPABILITIES_INVALID")
    capabilities = frozenset(capabilities_raw)
    if not _REQUIRED_CAPABILITIES.issubset(capabilities):
        raise LiveReleaseAcceptanceError("LIVE_CAPABILITIES_INCOMPLETE")

    try:
        release_manifest = build_read_only_release_manifest(
            openapi_document.payload,
            expected_app_version=expected_app_version,
            approved_hosts=approved_hosts,
            generated_at=checked_at,
        )
    except ReadOnlyReleaseError as exc:
        raise LiveReleaseAcceptanceError(
            f"LIVE_OPENAPI_RELEASE_REJECTED:{exc}"
        ) from exc

    if release_manifest.server_urls != (canonical_base_url,):
        raise LiveReleaseAcceptanceError("LIVE_OPENAPI_SERVER_MISMATCH")

    timestamp = checked_at or datetime.now(timezone.utc)
    return LiveReleaseAcceptanceV1(
        checked_at=timestamp,
        base_url=canonical_base_url,
        health_url=health_url,
        openapi_url=openapi_url,
        health_status="ok",
        health_version=health_version,
        health_configured=True,
        required_capabilities_present=True,
        release_manifest=release_manifest,
        live_http_verified=True,
        trading_methods=False,
    )
