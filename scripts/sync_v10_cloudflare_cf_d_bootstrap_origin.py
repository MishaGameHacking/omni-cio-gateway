from __future__ import annotations

import argparse
from collections.abc import Mapping
import http.client
import json
import os
import re
import secrets
import sys
import time
from typing import Any
from urllib.parse import quote, urlsplit

import scripts.bootstrap_v10_cloudflare_builds as builds


_BOOTSTRAP_ORIGIN_BINDING = "OMNI_V10_CF_D_NEON_BOOTSTRAP_ORIGIN"
_SYNC_TOKEN_BINDING = "OMNI_V10_CF_D_ORIGIN_SYNC_TOKEN"
_CUSTODY_PATH = "/api/internal/v10/cf-d/bootstrap-origin-custody"
_EXPECTED_WORKER = builds._STAGING_WORKER
_STAGING_HOST_PATTERN = re.compile(
    r"^omni-cio-v10-web-staging\.[a-z0-9-]{1,63}\.workers\.dev$"
)
_FUNCTION_ORIGIN_PATTERN = re.compile(
    r"^https://(br-[a-z0-9-]{4,57})-cfdprodbootstrap\.compute\."
    r"(c-[a-z0-9]+)\.eu-central-1\.aws\.neon\.tech/$"
)
_MAX_RESPONSE_BYTES = 8_192
_MAX_ORIGIN_BYTES = 1_024


def _staging_origin(value: str) -> str:
    try:
        parsed = urlsplit(value.strip())
        port = parsed.port
    except ValueError:
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_STAGING_ORIGIN_INVALID"
        ) from None
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or _STAGING_HOST_PATTERN.fullmatch(parsed.hostname) is None
    ):
        raise builds.BootstrapStopped("CLOUDFLARE_CF_D_STAGING_ORIGIN_INVALID")
    return f"https://{parsed.hostname}"


def _bootstrap_origin(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > _MAX_ORIGIN_BYTES
        or _FUNCTION_ORIGIN_PATTERN.fullmatch(value) is None
    ):
        raise builds.BootstrapStopped("CLOUDFLARE_CF_D_BOOTSTRAP_ORIGIN_INVALID")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_BOOTSTRAP_ORIGIN_INVALID"
        ) from None
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.path != "/"
        or parsed.query
        or parsed.fragment
    ):
        raise builds.BootstrapStopped("CLOUDFLARE_CF_D_BOOTSTRAP_ORIGIN_INVALID")
    return value


def _secret_path(api: builds.CloudflareApi, name: str = "") -> str:
    base = (
        f"/accounts/{api.account_id}/workers/scripts/"
        f"{quote(_EXPECTED_WORKER, safe='')}/secrets"
    )
    return f"{base}/{quote(name, safe='')}" if name else base


def _put_secret(api: builds.CloudflareApi, name: str, value: str) -> None:
    api.request(
        "PUT",
        _secret_path(api),
        body={"name": name, "text": value, "type": "secret_text"},
    )


def _delete_secret(api: builds.CloudflareApi, name: str) -> None:
    try:
        api.request("DELETE", _secret_path(api, name))
    except builds.BootstrapStopped as exc:
        if exc.code == "CLOUDFLARE_API_HTTP_ERROR" and exc.status == 404:
            return
        raise


def _listed_secrets(api: builds.CloudflareApi) -> dict[str, str]:
    rows = builds._list(
        api.request("GET", _secret_path(api)),
        "CLOUDFLARE_STAGING_SECRETS_INVALID",
    )
    result: dict[str, str] = {}
    for row in rows:
        record = builds._object(row, "CLOUDFLARE_STAGING_SECRET_INVALID")
        name = record.get("name")
        secret_type = record.get("type")
        if not isinstance(name, str) or not isinstance(secret_type, str):
            raise builds.BootstrapStopped("CLOUDFLARE_STAGING_SECRET_INVALID")
        if name in result:
            raise builds.BootstrapStopped("CLOUDFLARE_STAGING_SECRET_NOT_UNIQUE")
        result[name] = secret_type
    return result


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
    parsed = urlsplit(origin)
    hostname = parsed.hostname
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
        _delete_secret(api, _SYNC_TOKEN_BINDING)
        _put_secret(api, _SYNC_TOKEN_BINDING, token)
        bootstrap_origin = _fetch_bootstrap_origin(staging_origin, sha, token)
    finally:
        try:
            _delete_secret(api, _SYNC_TOKEN_BINDING)
        except builds.BootstrapStopped:
            raise builds.BootstrapStopped(
                "CLOUDFLARE_CF_D_ORIGIN_SYNC_TOKEN_CLEANUP_FAILED"
            ) from None

    builds._mask(bootstrap_origin)
    _put_secret(api, _BOOTSTRAP_ORIGIN_BINDING, bootstrap_origin)
    secrets_by_name = _listed_secrets(api)
    if secrets_by_name.get(_BOOTSTRAP_ORIGIN_BINDING) != "secret_text":
        raise builds.BootstrapStopped("CLOUDFLARE_CF_D_BOOTSTRAP_ORIGIN_SECRET_MISSING")
    if _SYNC_TOKEN_BINDING in secrets_by_name:
        raise builds.BootstrapStopped("CLOUDFLARE_CF_D_ORIGIN_SYNC_TOKEN_STALE")
    print("CLOUDFLARE_CF_D_BOOTSTRAP_ORIGIN_CUSTODY=READY")


def run(
    expected_sha: str,
    staging_origin: str,
    environ: Mapping[str, str] | None = None,
) -> None:
    environment = os.environ if environ is None else environ
    token = environment.get("CLOUDFLARE_API_TOKEN", "").strip()
    account_id = environment.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    if not token:
        raise builds.BootstrapStopped("CLOUDFLARE_API_TOKEN_REQUIRED")
    if not account_id:
        raise builds.BootstrapStopped("CLOUDFLARE_ACCOUNT_ID_REQUIRED")
    builds._mask(token)
    sync_bootstrap_origin_custody(
        builds.CloudflareApi(account_id, token),
        staging_origin=staging_origin,
        expected_sha=expected_sha,
    )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--origin", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        run(args.expected_sha, args.origin)
    except builds.BootstrapStopped as exc:
        fields = [
            "CLOUDFLARE_CF_D_BOOTSTRAP_ORIGIN_CUSTODY=STOPPED",
            f"code={exc.code}",
        ]
        if exc.status is not None:
            fields.append(f"status={exc.status}")
        print(" ".join(fields), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
