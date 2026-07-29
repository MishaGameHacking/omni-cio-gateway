from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from app import APP_VERSION, app, base
from omni_cio.release import (
    FetchedJsonDocument,
    LiveReleaseAcceptanceError,
    accept_live_read_only_release,
)


BASE_URL = "https://omni-cio-gateway.onrender.com"
APPROVED_HOSTS = frozenset({"omni-cio-gateway.onrender.com"})
CHECKED_AT = datetime(2026, 7, 29, 9, 0, tzinfo=timezone.utc)


def _schema() -> dict[str, Any]:
    app.openapi_schema = None
    return deepcopy(app.openapi())


def _health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "omni-cio-gateway",
        "version": APP_VERSION,
        "configured": {
            "tinvest_token": True,
            "gateway_api_key": True,
        },
        "capabilities": list(base.CAPABILITIES),
        "trading_methods": False,
    }


def _make_fetcher(
    *,
    health: Mapping[str, Any] | None = None,
    schema: Mapping[str, Any] | None = None,
    health_final_url: str | None = None,
    openapi_final_url: str | None = None,
    requested_url_override: str | None = None,
) -> tuple[Any, list[str]]:
    health_payload = health or _health()
    schema_payload = schema or _schema()
    calls: list[str] = []

    def fetch(url: str) -> FetchedJsonDocument:
        calls.append(url)
        if url.endswith("/health"):
            return FetchedJsonDocument(
                requested_url=requested_url_override or url,
                final_url=health_final_url or url,
                status_code=200,
                content_type="application/json",
                payload=health_payload,
            )
        return FetchedJsonDocument(
            requested_url=requested_url_override or url,
            final_url=openapi_final_url or url,
            status_code=200,
            content_type="application/json",
            payload=schema_payload,
        )

    return fetch, calls


def _accept(**overrides: Any):
    fetcher, calls = _make_fetcher(**overrides)
    acceptance = accept_live_read_only_release(
        base_url=BASE_URL,
        expected_app_version=APP_VERSION,
        approved_hosts=APPROVED_HOSTS,
        checked_at=CHECKED_AT,
        fetcher=fetcher,
    )
    return acceptance, calls


def test_live_release_acceptance_validates_only_public_documents() -> None:
    acceptance, calls = _accept()

    assert calls == [f"{BASE_URL}/health", f"{BASE_URL}/openapi.json"]
    assert acceptance.health_version == APP_VERSION
    assert acceptance.health_configured is True
    assert acceptance.required_capabilities_present is True
    assert acceptance.release_manifest.action_count >= 8
    assert acceptance.release_manifest.public_action_count == 1
    assert acceptance.release_manifest.forbidden_surface_count == 0
    assert acceptance.live_http_verified is True
    assert acceptance.trading_methods is False


def test_acceptance_output_contains_no_portfolio_or_secret_material() -> None:
    acceptance, _ = _accept()
    serialized = acceptance.model_dump_json().lower()

    forbidden_markers = (
        "authorization",
        "api_key_value",
        "account_id",
        "positions",
        "portfolio_value",
        "order_id",
        "confirmation_id",
    )
    assert all(marker not in serialized for marker in forbidden_markers)


@pytest.mark.parametrize(
    "base_url",
    (
        "http://omni-cio-gateway.onrender.com",
        "https://example.com",
        "https://omni-cio-gateway.onrender.com/health",
        "https://omni-cio-gateway.onrender.com?mode=test",
        "https://omni-cio-gateway.onrender.com:444",
        "https://" + "user" + ":" + "value" + "@omni-cio-gateway.onrender.com",
    ),
)
def test_unapproved_live_base_urls_fail_closed(base_url: str) -> None:
    fetcher, _ = _make_fetcher()
    with pytest.raises(
        LiveReleaseAcceptanceError,
        match="LIVE_BASE_URL_NOT_APPROVED",
    ):
        accept_live_read_only_release(
            base_url=base_url,
            expected_app_version=APP_VERSION,
            approved_hosts=APPROVED_HOSTS,
            fetcher=fetcher,
        )


@pytest.mark.parametrize(
    ("field", "value", "error_code"),
    (
        ("status", "degraded", "LIVE_HEALTH_STATUS_REJECTED"),
        ("version", "0.0.0", "LIVE_HEALTH_VERSION_MISMATCH"),
        ("trading_methods", True, "LIVE_TRADING_METHODS_ENABLED"),
    ),
)
def test_unsafe_health_state_fails_closed(
    field: str,
    value: object,
    error_code: str,
) -> None:
    health = _health()
    health[field] = value
    fetcher, _ = _make_fetcher(health=health)

    with pytest.raises(LiveReleaseAcceptanceError, match=error_code):
        accept_live_read_only_release(
            base_url=BASE_URL,
            expected_app_version=APP_VERSION,
            approved_hosts=APPROVED_HOSTS,
            fetcher=fetcher,
        )


def test_missing_live_configuration_fails_closed() -> None:
    health = _health()
    health["configured"] = {
        "tinvest_token": True,
        "gateway_api_key": False,
    }
    fetcher, _ = _make_fetcher(health=health)

    with pytest.raises(
        LiveReleaseAcceptanceError,
        match="LIVE_GATEWAY_KEY_NOT_CONFIGURED",
    ):
        accept_live_read_only_release(
            base_url=BASE_URL,
            expected_app_version=APP_VERSION,
            approved_hosts=APPROVED_HOSTS,
            fetcher=fetcher,
        )


def test_missing_required_capability_fails_closed() -> None:
    health = _health()
    capabilities = list(base.CAPABILITIES)
    capabilities.remove("regression_shield")
    health["capabilities"] = capabilities
    fetcher, _ = _make_fetcher(health=health)

    with pytest.raises(
        LiveReleaseAcceptanceError,
        match="LIVE_CAPABILITIES_INCOMPLETE",
    ):
        accept_live_read_only_release(
            base_url=BASE_URL,
            expected_app_version=APP_VERSION,
            approved_hosts=APPROVED_HOSTS,
            fetcher=fetcher,
        )


def test_redirected_public_documents_are_rejected() -> None:
    fetcher, _ = _make_fetcher(
        health_final_url=f"{BASE_URL}/other-health",
    )
    with pytest.raises(
        LiveReleaseAcceptanceError,
        match="LIVE_HEALTH_REDIRECT_REJECTED",
    ):
        accept_live_read_only_release(
            base_url=BASE_URL,
            expected_app_version=APP_VERSION,
            approved_hosts=APPROVED_HOSTS,
            fetcher=fetcher,
        )


def test_fetcher_cannot_substitute_another_requested_url() -> None:
    fetcher, _ = _make_fetcher(
        requested_url_override=f"{BASE_URL}/unexpected",
    )
    with pytest.raises(
        LiveReleaseAcceptanceError,
        match="LIVE_HEALTH_REQUEST_MISMATCH",
    ):
        accept_live_read_only_release(
            base_url=BASE_URL,
            expected_app_version=APP_VERSION,
            approved_hosts=APPROVED_HOSTS,
            fetcher=fetcher,
        )


def test_unsafe_live_openapi_surface_is_rejected() -> None:
    schema = _schema()
    paths = schema["paths"]
    assert isinstance(paths, dict)
    paths["/orders"] = {
        "post": {
            "operationId": "submitOrder",
            "responses": {"200": {"description": "unsafe"}},
            "security": [{"ApiKeyAuth": []}],
        }
    }
    fetcher, _ = _make_fetcher(schema=schema)

    with pytest.raises(
        LiveReleaseAcceptanceError,
        match="LIVE_OPENAPI_RELEASE_REJECTED:NON_GET_ACTION_EXPOSED",
    ):
        accept_live_read_only_release(
            base_url=BASE_URL,
            expected_app_version=APP_VERSION,
            approved_hosts=APPROVED_HOSTS,
            fetcher=fetcher,
        )


def test_openapi_server_must_equal_the_live_base_url() -> None:
    schema = _schema()
    schema["servers"] = [{"url": f"{BASE_URL}/api"}]
    fetcher, _ = _make_fetcher(schema=schema)

    with pytest.raises(
        LiveReleaseAcceptanceError,
        match="LIVE_OPENAPI_SERVER_MISMATCH",
    ):
        accept_live_read_only_release(
            base_url=BASE_URL,
            expected_app_version=APP_VERSION,
            approved_hosts=APPROVED_HOSTS,
            fetcher=fetcher,
        )


def test_live_acceptance_module_has_no_broker_sdk_import() -> None:
    source = (
        Path("omni_cio/release/live_acceptance_v1.py")
        .read_text(encoding="utf-8")
        .lower()
    )
    forbidden_imports = (
        "tinkoff.invest",
        "t_tech.invest",
        "t_tech.investments",
        "import grpc",
    )
    assert all(marker not in source for marker in forbidden_imports)
