from __future__ import annotations

from contextlib import contextmanager
import http.client
import json
import re
import secrets
import time
from typing import Any, Iterator
from urllib.parse import urlsplit

import scripts.bootstrap_v10_cloudflare_builds as builds
from scripts.cloudflare_staging_secrets import (
    delete_staging_secret,
    put_staging_secret,
    staging_secret_type,
)


_BOOTSTRAP_ORIGIN_BINDING = "OMNI_V10_CF_D_NEON_BOOTSTRAP_ORIGIN"
_SYNC_TOKEN_BINDING = "OMNI_V10_CF_D_ORIGIN_SYNC_TOKEN"
_CUSTODY_PATH = "/api/internal/v10/cf-d/bootstrap-origin-custody"
_RELEASE_PATH = "/api/v10/release"
_STAGING_ORIGIN_PATTERN = re.compile(
    r"^https://omni-cio-v10-web-staging\."
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.workers\.dev/?$"
)
_FUNCTION_ORIGIN_PATTERN = re.compile(
    r"^https://(br-[a-z0-9-]{4,57})-cfdprodbootstrap\.compute\."
    r"(c-[a-z0-9]+)\.eu-central-1\.aws\.neon\.tech/$"
)
_SYNC_TOKEN_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_MAX_RESPONSE_BYTES = 8_192
_MAX_ORIGIN_BYTES = 1_024
_RETRY_ATTEMPTS = 15
_RETRY_DELAY_SECONDS = 2
_ORIGIN_SYNC_UNAUTHORIZED = "CLOUDFLARE_CF_D_ORIGIN_SYNC_UNAUTHORIZED"
_ORIGIN_SYNC_NOT_FOUND = "CLOUDFLARE_CF_D_ORIGIN_SYNC_NOT_FOUND"
_ORIGIN_SYNC_DERIVATION_FAILED = "CLOUDFLARE_CF_D_ORIGIN_SYNC_DERIVATION_FAILED"
_ORIGIN_SYNC_STAGING_NOT_READY = "CLOUDFLARE_CF_D_ORIGIN_SYNC_STAGING_NOT_READY"
_ORIGIN_SYNC_UNAVAILABLE = "CLOUDFLARE_CF_D_ORIGIN_SYNC_UNAVAILABLE"
_ORIGIN_SYNC_RESPONSE_INVALID = "CLOUDFLARE_CF_D_ORIGIN_SYNC_RESPONSE_INVALID"
_SYNC_TOKEN_STALE = "CLOUDFLARE_CF_D_ORIGIN_SYNC_TOKEN_STALE"
_PRE_CUSTODY_RELEASE_NOT_READY = "CLOUDFLARE_CF_D_PRE_CUSTODY_RELEASE_NOT_READY"
_PRE_CUSTODY_RELEASE_SHA_MISMATCH = "CLOUDFLARE_CF_D_PRE_CUSTODY_RELEASE_SHA_MISMATCH"
_PRE_CUSTODY_RELEASE_UNAVAILABLE = "CLOUDFLARE_CF_D_PRE_CUSTODY_RELEASE_UNAVAILABLE"
_PRE_CUSTODY_RELEASE_RESPONSE_INVALID = (
    "CLOUDFLARE_CF_D_PRE_CUSTODY_RELEASE_RESPONSE_INVALID"
)
_PRE_CUSTODY_RELEASE_HTTP_STATUS_INVALID = (
    "CLOUDFLARE_CF_D_PRE_CUSTODY_RELEASE_HTTP_STATUS_INVALID"
)
_ORIGIN_SYNC_STATUS_CODES = {
    403: _ORIGIN_SYNC_UNAUTHORIZED,
    404: _ORIGIN_SYNC_NOT_FOUND,
    502: _ORIGIN_SYNC_DERIVATION_FAILED,
    503: _ORIGIN_SYNC_STAGING_NOT_READY,
}
_ORIGIN_SYNC_RETRYABLE = frozenset(
    {
        _ORIGIN_SYNC_DERIVATION_FAILED,
        _ORIGIN_SYNC_STAGING_NOT_READY,
        _ORIGIN_SYNC_UNAVAILABLE,
    }
)
_RELEASE_RETRYABLE_HTTP = frozenset({404, 408, 429, 500, 502, 503, 504})
_RELEASE_RETRYABLE_CODES = frozenset(
    {
        _PRE_CUSTODY_RELEASE_NOT_READY,
        _PRE_CUSTODY_RELEASE_SHA_MISMATCH,
        _PRE_CUSTODY_RELEASE_UNAVAILABLE,
    }
)


def _staging_origin(value: str) -> str:
    candidate = value.strip().lower()
    if _STAGING_ORIGIN_PATTERN.fullmatch(candidate) is None:
        raise builds.BootstrapStopped("CLOUDFLARE_CF_D_STAGING_ORIGIN_INVALID")
    return candidate.removesuffix("/")


def _bootstrap_origin(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > _MAX_ORIGIN_BYTES
        or _FUNCTION_ORIGIN_PATTERN.fullmatch(value) is None
    ):
        raise builds.BootstrapStopped("CLOUDFLARE_CF_D_BOOTSTRAP_ORIGIN_INVALID")
    return value


def _sync_token(value: str) -> str:
    if _SYNC_TOKEN_PATTERN.fullmatch(value) is None:
        raise builds.BootstrapStopped("CLOUDFLARE_CF_D_ORIGIN_SYNC_TOKEN_INVALID")
    return value


def _read_response_body(response: Any) -> bytes:
    body = response.read(_MAX_RESPONSE_BYTES + 1)
    if len(body) > _MAX_RESPONSE_BYTES:
        raise builds.BootstrapStopped("CLOUDFLARE_CF_D_ORIGIN_SYNC_RESPONSE_TOO_LARGE")
    return body


def _json_payload(raw: bytes, code: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise builds.BootstrapStopped(code) from None
    if not isinstance(payload, dict):
        raise builds.BootstrapStopped(code)
    return payload


def _origin_sync_status_code(status: int) -> str:
    return _ORIGIN_SYNC_STATUS_CODES.get(
        status,
        "CLOUDFLARE_CF_D_ORIGIN_SYNC_HTTP_STATUS_INVALID",
    )


def _fetch_bootstrap_origin_once(
    staging_origin: str,
    expected_sha: str,
    token: str,
) -> str:
    origin = _staging_origin(staging_origin)
    hostname = urlsplit(origin).hostname
    if hostname is None:
        raise builds.BootstrapStopped("CLOUDFLARE_CF_D_STAGING_ORIGIN_INVALID")
    connection = http.client.HTTPSConnection(hostname, 443, timeout=20.0)
    try:
        connection.request(
            "POST",
            _CUSTODY_PATH,
            body=b"{}",
            headers={
                "accept": "application/json",
                "content-type": "application/json",
                "x-omni-cf-d-origin-sync-token": token,
                "x-omni-expected-sha": expected_sha,
            },
        )
        response = connection.getresponse()
        status = int(response.status)
        if status != 200:
            raise builds.BootstrapStopped(
                _origin_sync_status_code(status),
                status=status,
            )
        content_type = str(response.getheader("Content-Type", "")).lower()
        if "application/json" not in content_type:
            raise builds.BootstrapStopped(_ORIGIN_SYNC_RESPONSE_INVALID)
        raw = _read_response_body(response)
    except builds.BootstrapStopped:
        raise
    except (TimeoutError, OSError, http.client.HTTPException):
        raise builds.BootstrapStopped(_ORIGIN_SYNC_UNAVAILABLE) from None
    finally:
        connection.close()
    payload = _json_payload(raw, _ORIGIN_SYNC_RESPONSE_INVALID)
    if payload.get("status") != "READY" or payload.get("source_sha") != expected_sha:
        raise builds.BootstrapStopped(_ORIGIN_SYNC_RESPONSE_INVALID)
    return _bootstrap_origin(payload.get("bootstrap_origin"))


def _fetch_bootstrap_origin(staging_origin: str, expected_sha: str, token: str) -> str:
    for attempt in range(1, _RETRY_ATTEMPTS + 1):
        try:
            return _fetch_bootstrap_origin_once(staging_origin, expected_sha, token)
        except builds.BootstrapStopped as exc:
            if exc.code not in _ORIGIN_SYNC_RETRYABLE or attempt == _RETRY_ATTEMPTS:
                raise
            time.sleep(_RETRY_DELAY_SECONDS)
    raise AssertionError("bounded origin sync retry exhausted without terminal result")


def _release_status_code(status: int) -> str:
    if status in _RELEASE_RETRYABLE_HTTP:
        return _PRE_CUSTODY_RELEASE_NOT_READY
    return _PRE_CUSTODY_RELEASE_HTTP_STATUS_INVALID


def _validated_release_payload(raw: bytes, expected_sha: str) -> None:
    payload = _json_payload(raw, _PRE_CUSTODY_RELEASE_RESPONSE_INVALID)
    protected_identity = (
        payload.get("status") == "ok",
        payload.get("platform") == "cloudflare",
        payload.get("backend") == "container",
        payload.get("static_assets") is True,
        payload.get("public_multi_user_enabled") is False,
        payload.get("real_trading_enabled") is False,
    )
    if not all(protected_identity):
        raise builds.BootstrapStopped(_PRE_CUSTODY_RELEASE_RESPONSE_INVALID)
    if payload.get("source_sha") != expected_sha:
        raise builds.BootstrapStopped(_PRE_CUSTODY_RELEASE_SHA_MISMATCH)


def _fetch_exact_release_once(staging_origin: str, expected_sha: str) -> None:
    origin = _staging_origin(staging_origin)
    hostname = urlsplit(origin).hostname
    if hostname is None:
        raise builds.BootstrapStopped("CLOUDFLARE_CF_D_STAGING_ORIGIN_INVALID")
    connection = http.client.HTTPSConnection(hostname, 443, timeout=20.0)
    try:
        connection.request(
            "GET",
            _RELEASE_PATH,
            headers={"accept": "application/json"},
        )
        response = connection.getresponse()
        status = int(response.status)
        if status != 200:
            raise builds.BootstrapStopped(_release_status_code(status), status=status)
        content_type = str(response.getheader("Content-Type", "")).lower()
        if "application/json" not in content_type:
            raise builds.BootstrapStopped(_PRE_CUSTODY_RELEASE_RESPONSE_INVALID)
        raw = _read_response_body(response)
    except builds.BootstrapStopped:
        raise
    except (TimeoutError, OSError, http.client.HTTPException):
        raise builds.BootstrapStopped(_PRE_CUSTODY_RELEASE_UNAVAILABLE) from None
    finally:
        connection.close()
    _validated_release_payload(raw, expected_sha)


def assert_staging_exact_release(staging_origin: str, expected_sha: str) -> None:
    """Require the exact compiled Worker to be live before custody is attempted."""

    sha = builds._expected_sha(expected_sha)
    for attempt in range(1, _RETRY_ATTEMPTS + 1):
        try:
            _fetch_exact_release_once(staging_origin, sha)
            print("CLOUDFLARE_CF_D_PRE_CUSTODY_RELEASE=EXACT_SHA")
            return
        except builds.BootstrapStopped as exc:
            if exc.code not in _RELEASE_RETRYABLE_CODES or attempt == _RETRY_ATTEMPTS:
                raise
            time.sleep(_RETRY_DELAY_SECONDS)
    raise AssertionError(
        "bounded exact release retry exhausted without terminal result"
    )


@contextmanager
def bootstrap_origin_sync_token(api: builds.CloudflareApi) -> Iterator[str]:
    """Arm short-lived Worker custody before the exact-SHA staging build starts."""

    token = secrets.token_hex(32)
    builds._mask(token)
    delete_staging_secret(api, _SYNC_TOKEN_BINDING)
    try:
        put_staging_secret(api, _SYNC_TOKEN_BINDING, token)
        if staging_secret_type(api, _SYNC_TOKEN_BINDING) != "secret_text":
            raise builds.BootstrapStopped(
                "CLOUDFLARE_CF_D_ORIGIN_SYNC_TOKEN_SECRET_MISSING"
            )
        print("CLOUDFLARE_CF_D_ORIGIN_SYNC_TOKEN=ARMED_BEFORE_EXACT_BUILD")
        yield token
    finally:
        try:
            delete_staging_secret(api, _SYNC_TOKEN_BINDING)
            if staging_secret_type(api, _SYNC_TOKEN_BINDING) is not None:
                raise builds.BootstrapStopped(_SYNC_TOKEN_STALE)
        except builds.BootstrapStopped as exc:
            if exc.code == _SYNC_TOKEN_STALE:
                raise
            raise builds.BootstrapStopped(
                "CLOUDFLARE_CF_D_ORIGIN_SYNC_TOKEN_CLEANUP_FAILED"
            ) from None


def fetch_bootstrap_origin_custody(
    *,
    staging_origin: str,
    expected_sha: str,
    token: str,
) -> str:
    """Prove custody after exact release attestation without mutating Worker bindings."""

    sha = builds._expected_sha(expected_sha)
    safe_token = _sync_token(token)
    return _fetch_bootstrap_origin(staging_origin, sha, safe_token)


def persist_bootstrap_origin_custody(
    api: builds.CloudflareApi,
    bootstrap_origin: str,
) -> None:
    """Persist the trusted Function origin only after the sync token is removed."""

    origin = _bootstrap_origin(bootstrap_origin)
    if staging_secret_type(api, _SYNC_TOKEN_BINDING) is not None:
        raise builds.BootstrapStopped(_SYNC_TOKEN_STALE)
    builds._mask(origin)
    put_staging_secret(api, _BOOTSTRAP_ORIGIN_BINDING, origin)
    if staging_secret_type(api, _BOOTSTRAP_ORIGIN_BINDING) != "secret_text":
        raise builds.BootstrapStopped("CLOUDFLARE_CF_D_BOOTSTRAP_ORIGIN_SECRET_MISSING")
    if staging_secret_type(api, _SYNC_TOKEN_BINDING) is not None:
        raise builds.BootstrapStopped(_SYNC_TOKEN_STALE)
    print("CLOUDFLARE_CF_D_BOOTSTRAP_ORIGIN_CUSTODY=READY")
