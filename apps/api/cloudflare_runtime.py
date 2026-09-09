from __future__ import annotations

from collections.abc import Mapping
import ipaddress
import os
from pathlib import Path
import re
from typing import Any
from urllib.parse import unquote, unquote_to_bytes

from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from apps.api.app import _SerializedWebConnection, _configure_long_lived_web_connection
from apps.api.cf_d_database_bootstrap import install_cf_d_database_bootstrap_route
from apps.api.hosted_preview import (
    PREVIEW_SESSION_POLICY,
    HostedPreviewServicesV1,
    _hostname,
    _release_sha,
    _verify_synthetic_scope,
    create_hosted_preview_app,
)
from omni_cio.persistence.migration import connect_postgres
from omni_cio.web.persistence_v1 import PostgresWebSessionRegistryV1


_INTERNAL_HOST = "omni-cio.internal"
_INTERNAL_PROXY_PATH = "/_omni/cloudflare-proxy"
_CONTAINER_SOURCE_PATH = "/api/internal/v10/cloudflare/container-source"
_CONTAINER_SOURCE_FILE = Path(__file__).with_name("generated_cloudflare_source_sha.txt")
_DSN_ENV_NAME = "OMNI_V10_POSTGRES_DSN"
_RUNTIME_ROLE_ENV_NAME = "OMNI_V10_POSTGRES_RUNTIME_ROLE"
_ALLOWED_RUNTIME_ROLES = frozenset(
    {
        "omni_cio_cloudflare_prod",
        "omni_cio_cloudflare_staging",
    }
)
_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_SECONDARY_ROUTE_ESCAPE_PATTERN = re.compile(r"%(?:2e|2f|5c|25)", re.IGNORECASE)
_CLIENT_IP_HEADER = b"x-omni-client-ip"
_ROUTE_PATH_HEADER = b"x-omni-route-path"
_ROUTE_QUERY_HEADER = b"x-omni-route-query"
_EDGE_PROVIDER_HEADER = b"x-omni-edge-provider"
_SOURCE_SHA_HEADER = b"x-omni-source-sha"
_INTERNAL_EDGE_HEADERS = frozenset(
    {
        _CLIENT_IP_HEADER,
        _ROUTE_PATH_HEADER,
        _ROUTE_QUERY_HEADER,
        _EDGE_PROVIDER_HEADER,
        _SOURCE_SHA_HEADER,
    }
)
_MAX_RAW_PATH_BYTES = 4096
_MAX_RAW_QUERY_BYTES = 8192


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name}_REQUIRED")
    return value


def _runtime_database_role() -> str:
    role = _required_env(_RUNTIME_ROLE_ENV_NAME)
    if role not in _ALLOWED_RUNTIME_ROLES:
        raise RuntimeError("CLOUDFLARE_RUNTIME_DATABASE_ROLE_INVALID")
    return role


def _container_image_source_sha(path: Path = _CONTAINER_SOURCE_FILE) -> str:
    try:
        value = path.read_text(encoding="ascii").strip().lower()
    except (OSError, UnicodeError) as exc:
        raise RuntimeError("CLOUDFLARE_RUNTIME_IMAGE_SOURCE_SHA_REQUIRED") from exc
    if _SHA_PATTERN.fullmatch(value) is None:
        raise RuntimeError("CLOUDFLARE_RUNTIME_IMAGE_SOURCE_SHA_INVALID")
    return value


def _install_container_source_route(app: Any, image_source_sha: str) -> None:
    if _SHA_PATTERN.fullmatch(image_source_sha) is None:
        raise RuntimeError("CLOUDFLARE_RUNTIME_IMAGE_SOURCE_SHA_INVALID")

    def container_source() -> JSONResponse:
        return JSONResponse(
            {
                "status": "ok",
                "image_source_sha": image_source_sha,
            }
        )

    app.add_api_route(
        _CONTAINER_SOURCE_PATH,
        container_source,
        methods=["GET"],
        include_in_schema=False,
    )
    installed_route = app.router.routes.pop()
    app.router.routes.insert(0, installed_route)


def _probe_cloudflare_runtime_database(
    connection: Any,
    *,
    expected_runtime_role: str,
) -> None:
    """Validate the Cloudflare least-privilege PostgreSQL runtime boundary.

    This is intentionally a Cloudflare adapter rather than a mutation of the accepted
    historical WP22A hosted-preview probe. The provider-specific role name differs,
    while the PostgreSQL 18, membership, schema, and FORCE-RLS requirements remain
    equivalent and fail closed.
    """

    version = connection.execute("SHOW server_version_num").fetchone()
    if version is None or int(version[0]) // 10000 != 18:
        raise RuntimeError("CLOUDFLARE_RUNTIME_POSTGRES18_REQUIRED")

    role = connection.execute(
        "SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, "
        "rolreplication, rolbypassrls FROM pg_catalog.pg_roles "
        "WHERE rolname = current_user"
    ).fetchone()
    if role != (
        expected_runtime_role,
        True,
        False,
        False,
        False,
        False,
        False,
    ):
        raise RuntimeError("CLOUDFLARE_RUNTIME_DATABASE_ROLE_DRIFT")

    memberships = connection.execute(
        "SELECT count(*) FROM pg_catalog.pg_auth_members m "
        "JOIN pg_catalog.pg_roles r ON r.oid = m.member "
        "WHERE r.rolname = current_user"
    ).fetchone()
    if memberships is None or int(memberships[0]) != 0:
        raise RuntimeError("CLOUDFLARE_RUNTIME_DATABASE_MEMBERSHIP_FORBIDDEN")

    required = connection.execute(
        "SELECT to_regclass('omni_cio_v10.tenants'), "
        "to_regclass('omni_cio_v10.users'), "
        "to_regclass('omni_cio_v10.web_sessions')"
    ).fetchone()
    if required is None or any(value is None for value in required):
        raise RuntimeError("CLOUDFLARE_RUNTIME_DATABASE_SCHEMA_INCOMPLETE")

    rows = connection.execute(
        "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity "
        "FROM pg_catalog.pg_class c "
        "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'omni_cio_v10' "
        "AND c.relname = ANY(%s) ORDER BY c.relname",
        (
            [
                "broker_accounts",
                "broker_connection_accounts",
                "broker_connections",
            ],
        ),
    ).fetchall()
    if len(rows) != 3 or any(not bool(row[1]) or not bool(row[2]) for row in rows):
        raise RuntimeError("CLOUDFLARE_RUNTIME_DATABASE_FORCE_RLS_REQUIRED")


def _probe_cloudflare_database(
    connection: Any,
    *,
    expected_runtime_role: str,
) -> None:
    _probe_cloudflare_runtime_database(
        connection,
        expected_runtime_role=expected_runtime_role,
    )
    _verify_synthetic_scope(connection)


def _header_map(scope: Mapping[str, Any]) -> dict[bytes, bytes]:
    raw_headers = scope.get("headers", ())
    return {bytes(key).lower(): bytes(value) for key, value in raw_headers}


def _ascii_unquote_header(
    headers: Mapping[bytes, bytes],
    name: bytes,
    *,
    max_bytes: int,
) -> bytes:
    raw = headers.get(name)
    if raw is None or len(raw) > max_bytes * 3:
        raise ValueError("route header missing or too large")
    try:
        encoded = raw.decode("ascii")
        decoded = unquote_to_bytes(encoded)
    except UnicodeError as exc:
        raise ValueError("route header encoding invalid") from exc
    if len(decoded) > max_bytes:
        raise ValueError("route header decoded size invalid")
    return decoded


def _validate_canonical_api_path(path: str) -> None:
    if "\\" in path:
        raise ValueError("route path contains backslash")
    segments = path.split("/")
    if any(segment in {".", ".."} for segment in segments):
        raise ValueError("route path contains dot segment")
    if _SECONDARY_ROUTE_ESCAPE_PATTERN.search(path) is not None:
        raise ValueError("route path contains secondary escape")
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in path):
        raise ValueError("route path contains control character")


def _validated_client_ip(headers: Mapping[bytes, bytes]) -> str:
    raw = headers.get(_CLIENT_IP_HEADER)
    if raw is None or len(raw) > 64:
        raise ValueError("client ip missing or too large")
    try:
        value = raw.decode("ascii")
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise ValueError("client ip invalid") from exc
    return address.compressed


def _validated_route(
    scope: Mapping[str, Any], release_sha: str
) -> tuple[str, bytes, bytes, str]:
    if scope.get("path") != _INTERNAL_PROXY_PATH:
        raise ValueError("internal proxy path required")
    headers = _header_map(scope)
    if headers.get(_EDGE_PROVIDER_HEADER) != b"cloudflare":
        raise ValueError("edge provider invalid")
    try:
        source_sha = headers.get(_SOURCE_SHA_HEADER, b"").decode("ascii").lower()
    except UnicodeError as exc:
        raise ValueError("source sha invalid") from exc
    if source_sha != release_sha or _SHA_PATTERN.fullmatch(source_sha) is None:
        raise ValueError("source sha invalid")

    client_ip = _validated_client_ip(headers)
    raw_path = _ascii_unquote_header(
        headers,
        _ROUTE_PATH_HEADER,
        max_bytes=_MAX_RAW_PATH_BYTES,
    )
    raw_query = _ascii_unquote_header(
        headers,
        _ROUTE_QUERY_HEADER,
        max_bytes=_MAX_RAW_QUERY_BYTES,
    )
    try:
        raw_path_text = raw_path.decode("ascii")
        path = unquote(raw_path_text, encoding="utf-8", errors="strict")
    except UnicodeError as exc:
        raise ValueError("route path invalid") from exc
    if path != "/healthz" and not path.startswith("/api/"):
        raise ValueError("route path outside API boundary")
    _validate_canonical_api_path(path)
    if b"\x00" in raw_query or b"\r" in raw_query or b"\n" in raw_query:
        raise ValueError("route query contains control character")
    return path, raw_path, raw_query, client_ip


async def _reject_proxy(send: Send) -> None:
    body = b'{"detail":"CLOUDFLARE_EDGE_ROUTE_REJECTED"}'
    await send(
        {
            "type": "http.response.start",
            "status": 404,
            "headers": [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"cache-control", b"no-store"),
                (b"x-content-type-options", b"nosniff"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


async def _reject_websocket(receive: Receive, send: Send) -> None:
    message = await receive()
    if message.get("type") == "websocket.connect":
        await send({"type": "websocket.close", "code": 1008})


class CloudflareEdgeRouteRestoreV1:
    def __init__(self, app: ASGIApp, *, release_sha: str) -> None:
        self._app = app
        self._release_sha = release_sha

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        scope_type = scope.get("type")
        if scope_type == "lifespan":
            await self._app(scope, receive, send)
            return
        if scope_type == "websocket":
            await _reject_websocket(receive, send)
            return
        if scope_type != "http":
            await self._app(scope, receive, send)
            return
        try:
            path, raw_path, raw_query, client_ip = _validated_route(
                scope, self._release_sha
            )
        except ValueError:
            await _reject_proxy(send)
            return

        filtered_headers = [
            (key, value)
            for key, value in scope.get("headers", ())
            if bytes(key).lower() not in _INTERNAL_EDGE_HEADERS
        ]
        restored_scope = dict(scope)
        restored_scope["scheme"] = "https"
        restored_scope["server"] = (_INTERNAL_HOST, 443)
        restored_scope["client"] = (client_ip, 0)
        restored_scope["path"] = path
        restored_scope["raw_path"] = raw_path
        restored_scope["query_string"] = raw_query
        restored_scope["headers"] = filtered_headers
        await self._app(restored_scope, receive, send)


def create_app():
    if os.environ.get("OMNI_V10_CLOUDFLARE_RUNTIME", "").strip() != "1":
        raise RuntimeError("CLOUDFLARE_RUNTIME_NOT_ENABLED")
    hostname = _hostname(_required_env("OMNI_V10_INTERNAL_HOSTNAME"))
    if hostname != _INTERNAL_HOST:
        raise RuntimeError("CLOUDFLARE_RUNTIME_INTERNAL_HOST_INVALID")
    release_sha = _release_sha(_required_env("OMNI_V10_RELEASE_SHA"))
    if _SHA_PATTERN.fullmatch(release_sha) is None:
        raise RuntimeError("CLOUDFLARE_RUNTIME_RELEASE_SHA_INVALID")
    image_source_sha = _container_image_source_sha()
    if image_source_sha != release_sha:
        raise RuntimeError("CLOUDFLARE_RUNTIME_IMAGE_SOURCE_SHA_DRIFT")
    runtime_role = _runtime_database_role()
    runtime_dsn = _required_env(_DSN_ENV_NAME)

    raw_connection = connect_postgres(runtime_dsn)
    _configure_long_lived_web_connection(raw_connection)
    connection = _SerializedWebConnection(raw_connection)
    _probe_cloudflare_database(
        connection,
        expected_runtime_role=runtime_role,
    )
    sessions = PostgresWebSessionRegistryV1(
        connection,
        policy=PREVIEW_SESSION_POLICY,
    )

    # Product providers deliberately remain disabled here. CF-D may only compose
    # Telegram/VK after real provider registration, canonical public origin, secret
    # custody and live acceptance evidence exist. The public Cloudflare shell must
    # not turn infrastructure migration into an authentication bypass.
    hosted_app = create_hosted_preview_app(
        HostedPreviewServicesV1(
            sessions=sessions,
            database_probe=lambda: _probe_cloudflare_database(
                connection,
                expected_runtime_role=runtime_role,
            ),
            hostname=hostname,
            release_sha=release_sha,
            provider_auth=None,
        ),
        trusted_edge_tls_terminated=False,
    )
    install_cf_d_database_bootstrap_route(
        hosted_app,
        connection=connection,
        runtime_dsn=runtime_dsn,
        release_sha=release_sha,
        runtime_role=runtime_role,
    )
    _install_container_source_route(hosted_app, image_source_sha)
    return CloudflareEdgeRouteRestoreV1(hosted_app, release_sha=release_sha)
