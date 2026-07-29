from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from omni_cio.contracts.v1.release import (
    ReadOnlyActionV1,
    ReadOnlyReleaseManifestV1,
)


_HTTP_METHODS = {
    "get",
    "put",
    "post",
    "delete",
    "options",
    "head",
    "patch",
    "trace",
}
_PUBLIC_PATHS = frozenset({"/health"})
_FORBIDDEN_SURFACE_MARKERS = (
    "postorder",
    "createorder",
    "submitorder",
    "replaceorder",
    "cancelorder",
    "executeorder",
    "confirmtrade",
    "withdrawfunds",
    "withdrawmoney",
    "transferfunds",
    "transfersecurities",
    "/orders",
    "/withdraw",
    "/transfer",
    "/execution",
)


class ReadOnlyReleaseError(ValueError):
    """The actual OpenAPI surface is not safe for a read-only GPT release."""


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ReadOnlyReleaseError(code)
    return value


def _approved_server_url(url: str, approved_hosts: frozenset[str]) -> bool:
    parsed = urlparse(url)
    return (
        parsed.scheme == "https"
        and parsed.hostname in approved_hosts
        and not parsed.username
        and not parsed.password
        and not parsed.query
        and not parsed.fragment
    )


def build_read_only_release_manifest(
    openapi_schema: Mapping[str, Any],
    *,
    expected_app_version: str,
    approved_hosts: frozenset[str],
    generated_at: datetime | None = None,
) -> ReadOnlyReleaseManifestV1:
    """Inspect the effective OpenAPI schema and fail closed on unsafe surfaces."""

    schema = deepcopy(dict(openapi_schema))
    openapi_version = str(schema.get("openapi") or "")
    if not openapi_version.startswith("3."):
        raise ReadOnlyReleaseError("OPENAPI_V3_REQUIRED")

    info = _mapping(schema.get("info"), "OPENAPI_INFO_REQUIRED")
    actual_version = str(info.get("version") or "")
    if actual_version != expected_app_version:
        raise ReadOnlyReleaseError("APP_VERSION_MISMATCH")

    servers_raw = schema.get("servers")
    if not isinstance(servers_raw, list) or not servers_raw:
        raise ReadOnlyReleaseError("OPENAPI_SERVER_REQUIRED")
    server_urls: list[str] = []
    for server in servers_raw:
        server_data = _mapping(server, "OPENAPI_SERVER_INVALID")
        url = str(server_data.get("url") or "").rstrip("/")
        if not _approved_server_url(url, approved_hosts):
            raise ReadOnlyReleaseError("OPENAPI_SERVER_NOT_APPROVED")
        if url in server_urls:
            raise ReadOnlyReleaseError("DUPLICATE_OPENAPI_SERVER")
        server_urls.append(url)

    paths = _mapping(schema.get("paths"), "OPENAPI_PATHS_REQUIRED")
    actions: list[ReadOnlyActionV1] = []
    operation_ids: set[str] = set()
    for path in sorted(paths):
        path_item = _mapping(paths[path], "OPENAPI_PATH_ITEM_INVALID")
        for method, operation_raw in path_item.items():
            normalized_method = str(method).lower()
            if normalized_method not in _HTTP_METHODS:
                continue
            if normalized_method != "get":
                raise ReadOnlyReleaseError("NON_GET_ACTION_EXPOSED")
            operation = _mapping(operation_raw, "OPENAPI_OPERATION_INVALID")
            operation_id = str(operation.get("operationId") or "").strip()
            if not operation_id:
                raise ReadOnlyReleaseError("OPERATION_ID_REQUIRED")
            if operation_id in operation_ids:
                raise ReadOnlyReleaseError("DUPLICATE_OPERATION_ID")
            operation_ids.add(operation_id)

            surface = f"{path} {operation_id}".lower()
            if any(marker in surface for marker in _FORBIDDEN_SURFACE_MARKERS):
                raise ReadOnlyReleaseError("FORBIDDEN_EXECUTION_SURFACE")

            public = path in _PUBLIC_PATHS
            security = operation.get("security")
            authentication_required = isinstance(security, list) and bool(security)
            if public and authentication_required:
                raise ReadOnlyReleaseError("PUBLIC_ACTION_REQUIRES_AUTH")
            if not public and not authentication_required:
                raise ReadOnlyReleaseError("PRIVATE_ACTION_MISSING_AUTH")

            actions.append(
                ReadOnlyActionV1(
                    path=path,
                    method="get",
                    operation_id=operation_id,
                    public=public,
                    authentication_required=authentication_required,
                )
            )

    if not actions:
        raise ReadOnlyReleaseError("NO_GPT_ACTIONS_EXPOSED")

    timestamp = generated_at or datetime.now(timezone.utc)
    action_tuple = tuple(actions)
    return ReadOnlyReleaseManifestV1(
        generated_at=timestamp,
        app_version=actual_version,
        entrypoint="app:app",
        openapi_version=openapi_version,
        server_urls=tuple(server_urls),
        actions=action_tuple,
        action_count=len(action_tuple),
        public_action_count=sum(action.public for action in action_tuple),
        authenticated_action_count=sum(
            action.authentication_required for action in action_tuple
        ),
        get_only=True,
        operation_ids_unique=True,
        approved_https_servers_only=True,
        forbidden_surface_count=0,
        trading_methods=False,
    )
