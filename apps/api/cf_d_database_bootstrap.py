from __future__ import annotations

from collections.abc import Mapping
import re
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
_PROVIDER_TIMEOUT_SECONDS = 20.0


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
    provider_origin = _bootstrap_origin(connection, runtime_dsn)

    @app.post(_BOOTSTRAP_PATH, include_in_schema=False)
    def bootstrap_production_database(request: Request) -> JSONResponse:
        expected_sha = request.headers.get("x-omni-expected-sha", "").strip().lower()
        if expected_sha != release_sha or _SHA_PATTERN.fullmatch(expected_sha) is None:
            return _provider_error("CLOUDFLARE_CF_D_EXPECTED_SHA_INVALID", 403)
        try:
            authorization = _authorization(request)
        except RuntimeError:
            return _provider_error("CLOUDFLARE_CF_D_OIDC_REQUIRED", 401)

        try:
            with httpx.Client(
                timeout=_PROVIDER_TIMEOUT_SECONDS,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                response = client.post(
                    provider_origin,
                    headers={
                        "Authorization": authorization,
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                    json={"expected_sha": release_sha},
                )
        except httpx.HTTPError:
            return _provider_error("CLOUDFLARE_CF_D_NEON_BOOTSTRAP_UNAVAILABLE")

        if response.status_code != 200:
            return _provider_error("CLOUDFLARE_CF_D_NEON_BOOTSTRAP_REJECTED")
        content = response.content
        if len(content) > _MAX_PROVIDER_RESPONSE_BYTES:
            return _provider_error("CLOUDFLARE_CF_D_NEON_BOOTSTRAP_RESPONSE_TOO_LARGE")
        try:
            payload = response.json()
        except ValueError:
            return _provider_error("CLOUDFLARE_CF_D_NEON_BOOTSTRAP_RESPONSE_INVALID")
        if not isinstance(payload, dict):
            return _provider_error("CLOUDFLARE_CF_D_NEON_BOOTSTRAP_RESPONSE_INVALID")
        try:
            dsn = _runtime_dsn(payload, release_sha)
        except RuntimeError:
            return _provider_error("CLOUDFLARE_CF_D_NEON_BOOTSTRAP_RESPONSE_INVALID")
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
