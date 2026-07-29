from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import pytest

from app import APP_VERSION, ENTRYPOINT, app
from omni_cio.release import ReadOnlyReleaseError, build_read_only_release_manifest


NOW = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)
APPROVED_HOSTS = frozenset({"omni-cio-gateway.onrender.com"})


def _schema() -> dict[str, object]:
    app.openapi_schema = None
    return deepcopy(app.openapi())


def _manifest(schema: dict[str, object] | None = None):
    return build_read_only_release_manifest(
        schema or _schema(),
        expected_app_version=APP_VERSION,
        approved_hosts=APPROVED_HOSTS,
        generated_at=NOW,
    )


def _private_operations(schema: dict[str, object]):
    paths = schema["paths"]
    assert isinstance(paths, dict)
    for path, path_item in paths.items():
        if path == "/health":
            continue
        assert isinstance(path_item, dict)
        operation = path_item.get("get")
        if isinstance(operation, dict):
            yield path, operation


def test_effective_openapi_is_a_valid_read_only_gpt_action_release() -> None:
    manifest = _manifest()

    assert ENTRYPOINT == "app:app"
    assert manifest.app_version == "3.9.1"
    assert manifest.entrypoint == "app:app"
    assert manifest.openapi_version.startswith("3.")
    assert manifest.server_urls == ("https://omni-cio-gateway.onrender.com",)
    assert manifest.action_count == len(manifest.actions)
    assert manifest.action_count >= 8
    assert manifest.public_action_count == 1
    assert manifest.authenticated_action_count == manifest.action_count - 1
    assert {action.method for action in manifest.actions} == {"get"}
    assert {action.path for action in manifest.actions if action.public} == {
        "/health"
    }
    assert manifest.get_only is True
    assert manifest.operation_ids_unique is True
    assert manifest.approved_https_servers_only is True
    assert manifest.forbidden_surface_count == 0
    assert manifest.trading_methods is False


def test_non_get_action_fails_closed() -> None:
    schema = _schema()
    paths = schema["paths"]
    assert isinstance(paths, dict)
    paths["/unsafe"] = {
        "post": {
            "operationId": "submitOrder",
            "responses": {"200": {"description": "unsafe"}},
            "security": [{"ApiKeyAuth": []}],
        }
    }

    with pytest.raises(ReadOnlyReleaseError, match="NON_GET_ACTION_EXPOSED"):
        _manifest(schema)


def test_forbidden_execution_surface_fails_closed_even_when_get() -> None:
    schema = _schema()
    paths = schema["paths"]
    assert isinstance(paths, dict)
    paths["/unsafe-preview"] = {
        "get": {
            "operationId": "createOrder",
            "responses": {"200": {"description": "unsafe"}},
            "security": [{"ApiKeyAuth": []}],
        }
    }

    with pytest.raises(
        ReadOnlyReleaseError,
        match="FORBIDDEN_EXECUTION_SURFACE",
    ):
        _manifest(schema)


def test_duplicate_operation_id_fails_closed() -> None:
    schema = _schema()
    operations = list(_private_operations(schema))
    assert len(operations) >= 2
    first_operation_id = operations[0][1]["operationId"]
    operations[1][1]["operationId"] = first_operation_id

    with pytest.raises(ReadOnlyReleaseError, match="DUPLICATE_OPERATION_ID"):
        _manifest(schema)


def test_private_action_without_authentication_fails_closed() -> None:
    schema = _schema()
    operations = list(_private_operations(schema))
    assert operations
    operations[0][1].pop("security", None)

    with pytest.raises(
        ReadOnlyReleaseError,
        match="PRIVATE_ACTION_MISSING_AUTH",
    ):
        _manifest(schema)


def test_public_health_must_remain_public() -> None:
    schema = _schema()
    paths = schema["paths"]
    assert isinstance(paths, dict)
    health = paths["/health"]
    assert isinstance(health, dict)
    operation = health["get"]
    assert isinstance(operation, dict)
    operation["security"] = [{"ApiKeyAuth": []}]

    with pytest.raises(
        ReadOnlyReleaseError,
        match="PUBLIC_ACTION_REQUIRES_AUTH",
    ):
        _manifest(schema)


def test_server_must_be_approved_https_without_credentials() -> None:
    variants = (
        "http://omni-cio-gateway.onrender.com",
        "https://example.com",
        "https://placeholder@omni-cio-gateway.onrender.com",
        "https://omni-cio-gateway.onrender.com?mode=diagnostic",
    )
    for url in variants:
        schema = _schema()
        schema["servers"] = [{"url": url}]
        with pytest.raises(
            ReadOnlyReleaseError,
            match="OPENAPI_SERVER_NOT_APPROVED",
        ):
            _manifest(schema)


def test_missing_or_duplicate_servers_fail_closed() -> None:
    schema = _schema()
    schema["servers"] = []
    with pytest.raises(ReadOnlyReleaseError, match="OPENAPI_SERVER_REQUIRED"):
        _manifest(schema)

    schema = _schema()
    schema["servers"] = [
        {"url": "https://omni-cio-gateway.onrender.com"},
        {"url": "https://omni-cio-gateway.onrender.com/"},
    ]
    with pytest.raises(ReadOnlyReleaseError, match="DUPLICATE_OPENAPI_SERVER"):
        _manifest(schema)


def test_version_and_openapi_major_are_pinned() -> None:
    schema = _schema()
    info = schema["info"]
    assert isinstance(info, dict)
    info["version"] = "4.0.0"
    with pytest.raises(ReadOnlyReleaseError, match="APP_VERSION_MISMATCH"):
        _manifest(schema)

    schema = _schema()
    schema["openapi"] = "2.0.0"
    with pytest.raises(ReadOnlyReleaseError, match="OPENAPI_V3_REQUIRED"):
        _manifest(schema)


def test_manifest_contains_no_write_or_execution_action() -> None:
    manifest = _manifest()
    serialized = manifest.model_dump_json().lower()
    forbidden = (
        "postorder",
        "createorder",
        "submitorder",
        "replaceorder",
        "cancelorder",
        "executeorder",
        "withdrawfunds",
        "transferfunds",
    )
    assert all(marker not in serialized for marker in forbidden)
    assert '"trading_methods":false' in serialized
