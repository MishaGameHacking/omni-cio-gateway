from __future__ import annotations

import http.client
import json
import re
import secrets
import time
from typing import Any
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
_STAGING_ORIGIN_PATTERN = re.compile(
    r"^https://omni-cio-v10-web-staging\."
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.workers\.dev/?$"
)
_FUNCTION_ORIGIN_PATTERN = re.compile(
    r"^https://(br-[a-z0-9-]{4,57})-cfdprodbootstrap\.compute\."
    r"(c-[a-z0-9]+)\.eu-central-1\.aws\.neon\.tech/$"
)
_MAX_RESPONSE_BYTES = 8_192
_MAX_ORIGIN_BYTES = 1_024


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


def _read_response_body(response: Any) -> bytes:
    body = response.read(_MAX_RESPONSE_BYTES + 1)
    if len(body) > _MAX_RESPONSE_BYTES:
        raise builds.BootstrapStopped("CLOUDFLARE_CF_D_ORIGIN_SYNC_RESPONSE_TOO_LARGE")
    return body


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
        if int(response.status) != 200:
            raise builds.BootstrapStopped("CLOUDFLARE_CF_D_ORIGIN_SYNC_REJECTED")
        content_type = str(response.getheader("Content-Type", "")).lower()
        if "application/json" not in content_type:
            raise builds.BootstrapStopped(
                "CLOUDFLARE_CF_D_ORIGIN_SYNC_RESPONSE_INVALID"
            )
        raw = _read_response_body(response)
    except builds.BootstrapStopped:
        raise
    except (TimeoutError, OSError, http.client.HTTPException):
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_ORIGIN_SYNC_UNAVAILABLE"
        ) from None
    finally:
        connection.close()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_ORIGIN_SYNC_RESPONSE_INVALID"
        ) from None
    if (
        not isinstance(payload, dict)
        or payload.get("status") != "READY"
        or payload.get("source_sha") != expected_sha
    ):
        raise builds.BootstrapStopped("CLOUDFLARE_CF_D_ORIGIN_SYNC_RESPONSE_INVALID")
    return _bootstrap_origin(payload.get("bootstrap_origin"))


def _fetch_bootstrap_origin(staging_origin: str, expected_sha: str, token: str) -> str:
    retryable = {
        "CLOUDFLARE_CF_D_ORIGIN_SYNC_REJECTED",
        "CLOUDFLARE_CF_D_ORIGIN_SYNC_UNAVAILABLE",
    }
    for attempt in range(1, 16):
        try:
            return _fetch_bootstrap_origin_once(staging_origin, expected_sha, token)
        except builds.BootstrapStopped as exc:
            if exc.code not in retryable or attempt == 15:
                raise
            time.sleep(2)
    raise AssertionError("bounded origin sync retry exhausted without terminal result")


def sync_bootstrap_origin_custody(
    api: builds.CloudflareApi,
    *,
    staging_origin: str,
    expected_sha: str,
) -> None:
    sha = builds._expected_sha(expected_sha)
    token = secrets.token_hex(32)
    builds._mask(token)
    try:
        delete_staging_secret(api, _SYNC_TOKEN_BINDING)
        put_staging_secret(api, _SYNC_TOKEN_BINDING, token)
        bootstrap_origin = _fetch_bootstrap_origin(staging_origin, sha, token)
    finally:
        try:
            delete_staging_secret(api, _SYNC_TOKEN_BINDING)
        except builds.BootstrapStopped:
            raise builds.BootstrapStopped(
                "CLOUDFLARE_CF_D_ORIGIN_SYNC_TOKEN_CLEANUP_FAILED"
            ) from None

    builds._mask(bootstrap_origin)
    put_staging_secret(api, _BOOTSTRAP_ORIGIN_BINDING, bootstrap_origin)
    if staging_secret_type(api, _BOOTSTRAP_ORIGIN_BINDING) != "secret_text":
        raise builds.BootstrapStopped("CLOUDFLARE_CF_D_BOOTSTRAP_ORIGIN_SECRET_MISSING")
    if staging_secret_type(api, _SYNC_TOKEN_BINDING) is not None:
        raise builds.BootstrapStopped("CLOUDFLARE_CF_D_ORIGIN_SYNC_TOKEN_STALE")
    print("CLOUDFLARE_CF_D_BOOTSTRAP_ORIGIN_CUSTODY=READY")
