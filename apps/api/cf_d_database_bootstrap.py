from __future__ import annotations

from collections.abc import Mapping
import json
import os
import re
import ssl
from typing import Any
from urllib.parse import parse_qs, urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import httpx


_BOOTSTRAP_PATH = "/api/internal/v10/cf-d/production-database-bootstrap"
_FUNCTION_SLUG = "cfdprodbootstrap"
_PRODUCTION_ROLE = "omni_cio_cloudflare_prod"
_STAGING_ROLE = "omni_cio_cloudflare_staging"
_NEON_REGION_SUFFIX = ".eu-central-1.aws.neon.tech"
_NEON_BRANCH_ID_PATTERN = re.compile(r"^br-[a-z0-9-]{4,57}$")
_NEON_CELL_PATTERN = re.compile(r"^c-[a-z0-9]+\.eu-central-1\.aws\.neon\.tech$")
_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_MAX_AUTHORIZATION_BYTES = 16_384
_MAX_PROVIDER_RESPONSE_BYTES = 32_768
_PROVIDER_STREAM_CHUNK_BYTES = 8_192
_PROVIDER_TIMEOUT_SECONDS = 20.0
_EGRESS_ORIGIN = "https://cf-d-neon-bootstrap.internal/"
_CLOUDFLARE_CONTAINER_CA_FILE = "/etc/cloudflare/certs/cloudflare-containers-ca.crt"


class _BootstrapRouteStopped(RuntimeError):
    def __init__(self, code: str, status_code: int = 502) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def _provider_error(code: str, status_code: int = 502) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"detail": code},
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


def _branch_id(connection: Any) -> str:
    row = connection.execute(
        "SELECT current_setting('neon.branch_id', true)"
    ).fetchone()
    if row is None or len(row) != 1:
        raise RuntimeError("CLOUDFLARE_CF_D_NEON_BRANCH_ID_UNAVAILABLE")
    value = str(row[0] or "").strip().lower()
    if _NEON_BRANCH_ID_PATTERN.fullmatch(value) is None:
        raise RuntimeError("CLOUDFLARE_CF_D_NEON_BRANCH_ID_INVALID")
    return value


def _database_cell(dsn: str) -> str:
    try:
        parsed = urlsplit(dsn)
        hostname = (parsed.hostname or "").lower().rstrip(".")
    except ValueError as exc:
        raise RuntimeError("CLOUDFLARE_CF_D_DATABASE_DSN_INVALID") from exc
    if (
        parsed.scheme not in {"postgres", "postgresql"}
        or not parsed.username
        or not parsed.password
        or not hostname.endswith(_NEON_REGION_SUFFIX)
        or "." not in hostname
    ):
        raise RuntimeError("CLOUDFLARE_CF_D_DATABASE_DSN_INVALID")
    cell = hostname.split(".", 1)[1]
    if _NEON_CELL_PATTERN.fullmatch(cell) is None:
        raise RuntimeError("CLOUDFLARE_CF_D_NEON_CELL_INVALID")
    return cell


def _bootstrap_origin(connection: Any, dsn: str) -> str:
    branch_id = _branch_id(connection)
    cell = _database_cell(dsn)
    return f"https://{branch_id}-{_FUNCTION_SLUG}.compute.{cell}/"


def _validate_staging_provider_context(connection: Any, dsn: str) -> None:
    origin = _bootstrap_origin(connection, dsn)
    try:
        parsed = urlsplit(origin)
        hostname = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port
    except ValueError as exc:
        raise RuntimeError("CLOUDFLARE_CF_D_STAGING_PROVIDER_CONTEXT_INVALID") from exc
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.path != "/"
        or parsed.query
        or parsed.fragment
        or not hostname.endswith(_NEON_REGION_SUFFIX)
    ):
        raise RuntimeError("CLOUDFLARE_CF_D_STAGING_PROVIDER_CONTEXT_INVALID")


def _secure_tls_context(*, cafile: str | None = None) -> ssl.SSLContext:
    context = ssl.create_default_context(cafile=cafile)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    return context


def _container_tls_context() -> ssl.SSLContext:
    try:
        return _secure_tls_context(cafile=_CLOUDFLARE_CONTAINER_CA_FILE)
    except OSError as exc:
        if os.environ.get("OMNI_V10_CLOUDFLARE_RUNTIME", "").strip() == "1":
            raise RuntimeError("CLOUDFLARE_CF_D_EGRESS_TLS_UNAVAILABLE") from exc
        return _secure_tls_context()


def _runtime_dsn(payload: Mapping[str, object], release_sha: str) -> str:
    if payload.get("status") != "READY":
        raise RuntimeError("CLOUDFLARE_CF_D_BOOTSTRAP_STATUS_INVALID")
    if payload.get("runtime_role") != _PRODUCTION_ROLE:
        raise RuntimeError("CLOUDFLARE_CF_D_BOOTSTRAP_ROLE_INVALID")
    if payload.get("source_sha") != release_sha:
        raise RuntimeError("CLOUDFLARE_CF_D_BOOTSTRAP_SHA_MISMATCH")
    value = payload.get("runtime_dsn")
    if not isinstance(value, str) or not value:
        raise RuntimeError("CLOUDFLARE_CF_D_BOOTSTRAP_DSN_MISSING")
    try:
        parsed = urlsplit(value)
        hostname = (parsed.hostname or "").lower().rstrip(".")
    except ValueError as exc:
        raise RuntimeError("CLOUDFLARE_CF_D_BOOTSTRAP_DSN_INVALID") from exc
    query = parse_qs(parsed.query, keep_blank_values=True)
    if (
        parsed.scheme not in {"postgres", "postgresql"}
        or parsed.username != _PRODUCTION_ROLE
        or not parsed.password
        or not hostname.endswith(_NEON_REGION_SUFFIX)
        or len(parsed.path) < 2
        or parsed.fragment
        or query.get("sslmode") != ["require"]
    ):
        raise RuntimeError("CLOUDFLARE_CF_D_BOOTSTRAP_DSN_INVALID")
    channel_binding = query.get("channel_binding")
    if channel_binding not in (None, ["require"]):
        raise RuntimeError("CLOUDFLARE_CF_D_BOOTSTRAP_DSN_INVALID")
    return value


def _authorization(request: Request) -> str:
    value = request.headers.get("authorization", "")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise RuntimeError("CLOUDFLARE_CF_D_OIDC_HEADER_INVALID") from exc
    if size > _MAX_AUTHORIZATION_BYTES or not value.startswith("Bearer "):
        raise RuntimeError("CLOUDFLARE_CF_D_OIDC_HEADER_INVALID")
    token = value[7:].strip()
    if not token or any(character.isspace() for character in token):
        raise RuntimeError("CLOUDFLARE_CF_D_OIDC_HEADER_INVALID")
    return f"Bearer {token}"


def _read_provider_response(response: httpx.Response) -> bytes:
    content = bytearray()
    for chunk in response.iter_bytes(chunk_size=_PROVIDER_STREAM_CHUNK_BYTES):
        if len(content) + len(chunk) > _MAX_PROVIDER_RESPONSE_BYTES:
            raise RuntimeError("CLOUDFLARE_CF_D_NEON_BOOTSTRAP_RESPONSE_TOO_LARGE")
        content.extend(chunk)
    return bytes(content)


def _validated_request_authorization(request: Request, release_sha: str) -> str:
    expected_sha = request.headers.get("x-omni-expected-sha", "").strip().lower()
    if expected_sha != release_sha or _SHA_PATTERN.fullmatch(expected_sha) is None:
        raise _BootstrapRouteStopped("CLOUDFLARE_CF_D_EXPECTED_SHA_INVALID", 403)
    try:
        return _authorization(request)
    except RuntimeError as exc:
        raise _BootstrapRouteStopped("CLOUDFLARE_CF_D_OIDC_REQUIRED", 401) from exc


def _require_staging_provider_context(connection: Any, runtime_dsn: str) -> None:
    try:
        _validate_staging_provider_context(connection, runtime_dsn)
    except Exception as exc:
        raise _BootstrapRouteStopped(
            "CLOUDFLARE_CF_D_STAGING_PROVIDER_CONTEXT_UNAVAILABLE"
        ) from exc


def _required_container_tls_context() -> ssl.SSLContext:
    try:
        return _container_tls_context()
    except RuntimeError as exc:
        raise _BootstrapRouteStopped("CLOUDFLARE_CF_D_EGRESS_TLS_UNAVAILABLE") from exc


def _fetch_bootstrap_response(
    authorization: str,
    release_sha: str,
    tls_context: ssl.SSLContext,
) -> bytes:
    try:
        with httpx.Client(
            timeout=_PROVIDER_TIMEOUT_SECONDS,
            follow_redirects=False,
            trust_env=False,
            verify=tls_context,
        ) as client:
            with client.stream(
                "POST",
                _EGRESS_ORIGIN,
                headers={
                    "Authorization": authorization,
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json={"expected_sha": release_sha},
            ) as response:
                if response.status_code != 200:
                    raise _BootstrapRouteStopped(
                        "CLOUDFLARE_CF_D_NEON_BOOTSTRAP_REJECTED"
                    )
                try:
                    return _read_provider_response(response)
                except RuntimeError as exc:
                    raise _BootstrapRouteStopped(
                        "CLOUDFLARE_CF_D_NEON_BOOTSTRAP_RESPONSE_TOO_LARGE"
                    ) from exc
    except _BootstrapRouteStopped:
        raise
    except httpx.HTTPError as exc:
        raise _BootstrapRouteStopped(
            "CLOUDFLARE_CF_D_NEON_BOOTSTRAP_UNAVAILABLE"
        ) from exc


def _validated_provider_runtime_dsn(content: bytes, release_sha: str) -> str:
    try:
        payload = json.loads(content.decode("utf-8"))
    except ValueError as exc:
        raise _BootstrapRouteStopped(
            "CLOUDFLARE_CF_D_NEON_BOOTSTRAP_RESPONSE_INVALID"
        ) from exc
    if not isinstance(payload, dict):
        raise _BootstrapRouteStopped("CLOUDFLARE_CF_D_NEON_BOOTSTRAP_RESPONSE_INVALID")
    try:
        return _runtime_dsn(payload, release_sha)
    except RuntimeError as exc:
        raise _BootstrapRouteStopped(
            "CLOUDFLARE_CF_D_NEON_BOOTSTRAP_RESPONSE_INVALID"
        ) from exc


def _ready_response(dsn: str, release_sha: str) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content={
            "status": "READY",
            "runtime_role": _PRODUCTION_ROLE,
            "runtime_dsn": dsn,
            "source_sha": release_sha,
        },
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


def install_cf_d_database_bootstrap_route(
    app: FastAPI,
    *,
    connection: Any,
    runtime_dsn: str,
    release_sha: str,
    runtime_role: str,
) -> None:
    if runtime_role != _STAGING_ROLE:
        return
    if _SHA_PATTERN.fullmatch(release_sha) is None:
        raise RuntimeError("CLOUDFLARE_CF_D_RELEASE_SHA_INVALID")

    @app.post(_BOOTSTRAP_PATH, include_in_schema=False)
    def bootstrap_production_database(request: Request) -> JSONResponse:
        try:
            authorization = _validated_request_authorization(request, release_sha)
            _require_staging_provider_context(connection, runtime_dsn)
            tls_context = _required_container_tls_context()
            content = _fetch_bootstrap_response(
                authorization,
                release_sha,
                tls_context,
            )
            dsn = _validated_provider_runtime_dsn(content, release_sha)
        except _BootstrapRouteStopped as exc:
            return _provider_error(exc.code, exc.status_code)
        return _ready_response(dsn, release_sha)
