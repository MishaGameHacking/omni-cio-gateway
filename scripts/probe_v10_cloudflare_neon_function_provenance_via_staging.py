from __future__ import annotations

import hmac
import http.client
import json
import re
import ssl
import time
from typing import Any
from urllib.parse import urlsplit

import scripts.bootstrap_v10_cloudflare_builds as builds
from scripts.sync_v10_cloudflare_cf_d_bootstrap_origin import (
    _staging_origin,
    _sync_token,
)


_PROVENANCE_CUSTODY_PATH = "/api/internal/v10/cf-d/function-source-provenance-custody"
_JSON_MEDIA_TYPE = "application/json"
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_MAX_RESPONSE_BYTES = 4_096
_RETRY_ATTEMPTS = 4
_RETRY_DELAY_SECONDS = 2
_PROVENANCE_UNAUTHORIZED = "CLOUDFLARE_CF_D_NEON_FUNCTION_PROVENANCE_UNAUTHORIZED"
_PROVENANCE_NOT_FOUND = "CLOUDFLARE_CF_D_NEON_FUNCTION_PROVENANCE_NOT_FOUND"
_PROVENANCE_STAGING_NOT_READY = (
    "CLOUDFLARE_CF_D_NEON_FUNCTION_PROVENANCE_STAGING_NOT_READY"
)
_PROVENANCE_UNAVAILABLE = "CLOUDFLARE_CF_D_NEON_FUNCTION_PROVENANCE_UNAVAILABLE"
_PROVENANCE_DERIVATION_FAILED = (
    "CLOUDFLARE_CF_D_NEON_FUNCTION_PROVENANCE_DERIVATION_FAILED"
)
_PROVENANCE_REDIRECT_REJECTED = (
    "CLOUDFLARE_CF_D_NEON_FUNCTION_PROVENANCE_REDIRECT_REJECTED"
)
_PROVENANCE_RESPONSE_TOO_LARGE = (
    "CLOUDFLARE_CF_D_NEON_FUNCTION_PROVENANCE_RESPONSE_TOO_LARGE"
)
_PROVENANCE_INVALID = "CLOUDFLARE_CF_D_NEON_FUNCTION_PROVENANCE_INVALID"
_PROVENANCE_HTTP_STATUS_INVALID = (
    "CLOUDFLARE_CF_D_NEON_FUNCTION_PROVENANCE_HTTP_STATUS_INVALID"
)
_PROVIDER_FAILURE_CODES = frozenset(
    {
        _PROVENANCE_DERIVATION_FAILED,
        _PROVENANCE_UNAVAILABLE,
        _PROVENANCE_REDIRECT_REJECTED,
        _PROVENANCE_RESPONSE_TOO_LARGE,
        _PROVENANCE_INVALID,
    }
)
_RETRYABLE_CODES = frozenset(
    {
        _PROVENANCE_STAGING_NOT_READY,
        _PROVENANCE_UNAVAILABLE,
        _PROVENANCE_DERIVATION_FAILED,
    }
)


def _tls_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    if not context.check_hostname or context.verify_mode != ssl.CERT_REQUIRED:
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_PROVENANCE_TLS_INVALID"
        )
    return context


def _source_digest(value: str) -> str:
    candidate = value.strip().lower()
    if _SHA256_PATTERN.fullmatch(candidate) is None:
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_PROVENANCE_DIGEST_INVALID"
        )
    return candidate


def _read_body(response: Any) -> bytes:
    raw = response.read(_MAX_RESPONSE_BYTES + 1)
    if len(raw) > _MAX_RESPONSE_BYTES:
        raise builds.BootstrapStopped(_PROVENANCE_RESPONSE_TOO_LARGE)
    return raw


def _json_payload(raw: bytes, code: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise builds.BootstrapStopped(code) from None
    if not isinstance(value, dict):
        raise builds.BootstrapStopped(code)
    return value


def _failure_code(response: Any, status: int) -> str:
    if status == 403:
        return _PROVENANCE_UNAUTHORIZED
    if status == 404:
        return _PROVENANCE_NOT_FOUND
    if status == 503:
        return _PROVENANCE_STAGING_NOT_READY
    if status != 502:
        return _PROVENANCE_HTTP_STATUS_INVALID
    content_type = str(response.getheader("Content-Type", "")).lower()
    if _JSON_MEDIA_TYPE not in content_type:
        return _PROVENANCE_INVALID
    raw = _read_body(response)
    payload = _json_payload(raw, _PROVENANCE_INVALID)
    detail = payload.get("detail")
    if isinstance(detail, str) and detail in _PROVIDER_FAILURE_CODES:
        return detail
    return _PROVENANCE_INVALID


def _validated_state(raw: bytes, expected_sha: str, expected_digest: str) -> bool:
    payload = _json_payload(raw, _PROVENANCE_INVALID)
    if set(payload) != {"status", "source_sha", "source_state", "source_sha256"}:
        raise builds.BootstrapStopped(_PROVENANCE_INVALID)
    if payload.get("status") != "READY" or payload.get("source_sha") != expected_sha:
        raise builds.BootstrapStopped(_PROVENANCE_INVALID)
    state = payload.get("source_state")
    digest = payload.get("source_sha256")
    if state == "LEGACY_STALE" and digest is None:
        return False
    if state != "DIGEST" or not isinstance(digest, str):
        raise builds.BootstrapStopped(_PROVENANCE_INVALID)
    actual = _source_digest(digest)
    return hmac.compare_digest(actual.encode("ascii"), expected_digest.encode("ascii"))


def _probe_once(
    staging_origin: str,
    expected_sha: str,
    token: str,
    expected_digest: str,
) -> bool:
    origin = _staging_origin(staging_origin)
    hostname = urlsplit(origin).hostname
    if hostname is None:
        raise builds.BootstrapStopped("CLOUDFLARE_CF_D_STAGING_ORIGIN_INVALID")
    connection = http.client.HTTPSConnection(
        hostname,
        443,
        timeout=20.0,
        context=_tls_context(),
    )
    try:
        connection.request(
            "POST",
            _PROVENANCE_CUSTODY_PATH,
            body=b"{}",
            headers={
                "accept": _JSON_MEDIA_TYPE,
                "content-type": _JSON_MEDIA_TYPE,
                "x-omni-cf-d-origin-sync-token": token,
                "x-omni-expected-sha": expected_sha,
            },
        )
        response = connection.getresponse()
        status = int(response.status)
        if status != 200:
            raise builds.BootstrapStopped(
                _failure_code(response, status), status=status
            )
        content_type = str(response.getheader("Content-Type", "")).lower()
        if _JSON_MEDIA_TYPE not in content_type:
            raise builds.BootstrapStopped(_PROVENANCE_INVALID)
        raw = _read_body(response)
    except builds.BootstrapStopped:
        raise
    except (OSError, http.client.HTTPException):
        raise builds.BootstrapStopped(_PROVENANCE_UNAVAILABLE) from None
    finally:
        connection.close()
    return _validated_state(raw, expected_sha, expected_digest)


def probe_exact_source_via_staging(
    *,
    staging_origin: str,
    expected_sha: str,
    token: str,
    expected_digest: str,
) -> bool:
    sha = builds._expected_sha(expected_sha)
    safe_token = _sync_token(token)
    digest = _source_digest(expected_digest)
    for attempt in range(1, _RETRY_ATTEMPTS + 1):
        try:
            return _probe_once(staging_origin, sha, safe_token, digest)
        except builds.BootstrapStopped as exc:
            if exc.code not in _RETRYABLE_CODES or attempt == _RETRY_ATTEMPTS:
                raise
            time.sleep(_RETRY_DELAY_SECONDS)
    raise AssertionError("bounded provenance retry exhausted without terminal result")
