from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from omni_cio.release.live_acceptance_v1 import (
    FetchedJsonDocument,
    LiveReleaseAcceptanceError,
)
from omni_cio.release.live_authority_v1 import (
    BASELINE_ACTIONS,
    REAL_ACTIONS,
    SANDBOX_ACTIONS,
    accept_live_gateway_authority,
)


BASE = "https://omni-cio-gateway.onrender.com"
VERSION = "3.10.0"


def _health() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": VERSION,
        "trading_methods": False,
        "configured": {"tinvest_token": True, "gateway_api_key": True},
    }


def _operation(operation_id: str, *, consequential: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "operationId": operation_id,
        "responses": {"200": {"description": "ok"}},
    }
    if consequential:
        payload["x-openai-isConsequential"] = True
    return payload


def _openapi(*, sandbox: bool = False, real: str = "off") -> dict[str, Any]:
    paths: dict[str, dict[str, Any]] = {}
    consequential = {
        "openSandboxAccount",
        "fundSandboxAccount",
        "executeSandboxTrade",
        "cancelSandboxOrder",
        "executeRealTrade",
    }

    actions = dict(BASELINE_ACTIONS)
    if sandbox:
        actions.update(SANDBOX_ACTIONS)
    if real == "status":
        actions["getRealTradingStatus"] = REAL_ACTIONS["getRealTradingStatus"]
    elif real == "ready":
        actions.update(REAL_ACTIONS)

    for operation_id, (method, path) in actions.items():
        paths.setdefault(path, {})[method] = _operation(
            operation_id,
            consequential=operation_id in consequential,
        )

    return {
        "openapi": "3.1.0",
        "info": {"title": "Omni-CIO Read-Only Gateway", "version": VERSION},
        "servers": [{"url": BASE}],
        "paths": paths,
    }


def _fetcher(health: dict[str, Any], openapi: dict[str, Any]):
    def fetch(url: str) -> FetchedJsonDocument:
        if url == f"{BASE}/health":
            payload = health
        elif url == f"{BASE}/openapi.json":
            payload = openapi
        else:  # pragma: no cover - contract guard
            raise AssertionError(url)
        return FetchedJsonDocument(
            requested_url=url,
            final_url=url,
            status_code=200,
            content_type="application/json",
            payload=payload,
        )

    return fetch


def _accept(openapi: dict[str, Any]):
    return accept_live_gateway_authority(
        base_url=BASE,
        expected_app_version=VERSION,
        approved_hosts=frozenset({"omni-cio-gateway.onrender.com"}),
        checked_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
        fetcher=_fetcher(_health(), openapi),
    )


def test_baseline_read_only_surface_is_accepted() -> None:
    result = _accept(_openapi())
    assert set(result.operation_ids) == set(BASELINE_ACTIONS)
    assert result.sandbox_enabled is False
    assert result.real_status_exposed is False
    assert result.real_execution_ready_surface is False


def test_full_reviewed_sandbox_and_real_surface_is_accepted() -> None:
    result = _accept(_openapi(sandbox=True, real="ready"))
    assert set(result.operation_ids) == (
        set(BASELINE_ACTIONS) | set(SANDBOX_ACTIONS) | set(REAL_ACTIONS)
    )
    assert result.sandbox_enabled is True
    assert result.real_status_exposed is True
    assert result.real_execution_ready_surface is True


def test_status_only_real_surface_is_accepted_fail_closed() -> None:
    result = _accept(_openapi(real="status"))
    assert result.real_status_exposed is True
    assert result.real_execution_ready_surface is False


def test_unreviewed_action_is_rejected() -> None:
    schema = _openapi()
    schema["paths"]["/mystery"] = {
        "post": _operation("mysteryMutation", consequential=True)
    }
    with pytest.raises(LiveReleaseAcceptanceError, match="LIVE_UNREVIEWED_ACTION_EXPOSED"):
        _accept(schema)


def test_partial_real_mutation_surface_is_rejected() -> None:
    schema = _openapi(real="status")
    method, path = REAL_ACTIONS["prepareRealTrade"]
    schema["paths"][path] = {method: _operation("prepareRealTrade")}
    with pytest.raises(LiveReleaseAcceptanceError, match="LIVE_REAL_SURFACE_PARTIAL"):
        _accept(schema)


def test_consequential_marker_is_required_for_real_execute() -> None:
    schema = _openapi(real="ready")
    method, path = REAL_ACTIONS["executeRealTrade"]
    schema["paths"][path][method].pop("x-openai-isConsequential")
    with pytest.raises(
        LiveReleaseAcceptanceError, match="LIVE_CONSEQUENTIAL_MARKER_MISSING"
    ):
        _accept(schema)


def test_forbidden_transfer_path_is_rejected_even_with_unknown_operation() -> None:
    schema = _openapi()
    schema["paths"]["/real-trading/transfer"] = {
        "post": _operation("transferFunds", consequential=True)
    }
    with pytest.raises(LiveReleaseAcceptanceError, match="LIVE_FORBIDDEN_PATH_EXPOSED"):
        _accept(schema)
