from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from omni_cio.release.live_acceptance_v1 import (
    FetchedJsonDocument,
    JsonFetcher,
    LiveReleaseAcceptanceError,
    _load_json_document,
    _mapping,
    _normalize_base_url,
    _validate_document_metadata,
)


BASELINE_ACTIONS: dict[str, tuple[str, str]] = {
    "gatewayHealth": ("get", "/health"),
    "getConnection": ("get", "/connection"),
    "getPortfolioSnapshot": ("get", "/snapshot"),
    "getEnrichedPortfolioSnapshot": ("get", "/snapshot/enriched"),
    "findInstrument": ("get", "/instruments/search"),
    "getOperationsHistory": ("get", "/operations"),
    "getMarketSnapshot": ("get", "/market/snapshot"),
    "getPortfolioMarketSnapshot": ("get", "/portfolio/market-snapshot"),
    "getPortfolioAnalytics": ("get", "/portfolio/analytics"),
    "getCashLiquiditySnapshot": ("get", "/portfolio/cash-liquidity"),
    "getPurchaseCapacityPreview": ("get", "/portfolio/purchase-capacity"),
    "getOperationsAnalytics": ("get", "/operations/analytics"),
    "getBrokerReportReconciliation": (
        "get",
        "/operations/broker-report-reconciliation",
    ),
    "getFinalDecisionReview": ("get", "/decision/final-review"),
}

SANDBOX_ACTIONS: dict[str, tuple[str, str]] = {
    "getSandboxTradingStatus": ("get", "/sandbox/status"),
    "openSandboxAccount": ("post", "/sandbox/account/open"),
    "fundSandboxAccount": ("post", "/sandbox/account/fund"),
    "getSandboxPortfolio": ("get", "/sandbox/portfolio"),
    "prepareSandboxTrade": ("post", "/sandbox/trade/prepare"),
    "executeSandboxTrade": ("post", "/sandbox/trade/execute"),
    "getSandboxOrderState": ("get", "/sandbox/order/status"),
    "cancelSandboxOrder": ("post", "/sandbox/order/cancel"),
}

REAL_ACTIONS: dict[str, tuple[str, str]] = {
    "getRealTradingStatus": ("get", "/real-trading/status"),
    "prepareRealTrade": ("post", "/real-trading/trade/prepare"),
    "executeRealTrade": ("post", "/real-trading/trade/execute"),
    "getRealOrderState": ("get", "/real-trading/order/state"),
}

ALLOWED_ACTIONS = BASELINE_ACTIONS | SANDBOX_ACTIONS | REAL_ACTIONS
HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete"})
FORBIDDEN_PATH_FRAGMENTS = (
    "withdraw",
    "transfer",
    "margin",
    "short",
    "stop-order",
    "stop_order",
    "replace-order",
    "replace_order",
    "post-order-async",
    "post_order_async",
)
CONSEQUENTIAL_ACTIONS = frozenset(
    {
        "openSandboxAccount",
        "fundSandboxAccount",
        "executeSandboxTrade",
        "cancelSandboxOrder",
        "executeRealTrade",
    }
)


@dataclass(frozen=True, slots=True)
class LiveGatewayAuthorityAcceptanceV1:
    checked_at: datetime
    base_url: str
    app_version: str
    operation_ids: tuple[str, ...]
    sandbox_enabled: bool
    real_status_exposed: bool
    real_execution_ready_surface: bool


def _extract_actions(
    openapi: Mapping[str, Any],
) -> dict[str, tuple[str, str, Mapping[str, Any]]]:
    raw_paths = _mapping(openapi.get("paths"), "LIVE_OPENAPI_PATHS_REQUIRED")
    actions: dict[str, tuple[str, str, Mapping[str, Any]]] = {}
    for raw_path, raw_item in raw_paths.items():
        if not isinstance(raw_path, str):
            raise LiveReleaseAcceptanceError("LIVE_OPENAPI_PATH_INVALID")
        lowered_path = raw_path.casefold()
        if any(fragment in lowered_path for fragment in FORBIDDEN_PATH_FRAGMENTS):
            raise LiveReleaseAcceptanceError("LIVE_FORBIDDEN_PATH_EXPOSED")
        item = _mapping(raw_item, "LIVE_OPENAPI_PATH_ITEM_INVALID")
        for raw_method, raw_operation in item.items():
            method = str(raw_method).casefold()
            if method not in HTTP_METHODS:
                continue
            operation = _mapping(raw_operation, "LIVE_OPENAPI_OPERATION_INVALID")
            operation_id = operation.get("operationId")
            if not isinstance(operation_id, str) or not operation_id:
                raise LiveReleaseAcceptanceError("LIVE_OPERATION_ID_REQUIRED")
            if operation_id in actions:
                raise LiveReleaseAcceptanceError("LIVE_OPERATION_ID_DUPLICATE")
            actions[operation_id] = (method, raw_path, operation)
    return actions


def _validate_action_surface(
    actions: Mapping[str, tuple[str, str, Mapping[str, Any]]],
) -> None:
    missing_baseline = set(BASELINE_ACTIONS) - set(actions)
    if missing_baseline:
        raise LiveReleaseAcceptanceError("LIVE_BASELINE_ACTIONS_INCOMPLETE")

    unexpected = set(actions) - set(ALLOWED_ACTIONS)
    if unexpected:
        raise LiveReleaseAcceptanceError("LIVE_UNREVIEWED_ACTION_EXPOSED")

    for operation_id, (method, path, operation) in actions.items():
        expected_method, expected_path = ALLOWED_ACTIONS[operation_id]
        if method != expected_method or path != expected_path:
            raise LiveReleaseAcceptanceError("LIVE_ACTION_ROUTE_MISMATCH")
        if method not in {"get", "post"}:
            raise LiveReleaseAcceptanceError("LIVE_UNREVIEWED_HTTP_METHOD")
        if operation_id in CONSEQUENTIAL_ACTIONS and operation.get(
            "x-openai-isConsequential"
        ) is not True:
            raise LiveReleaseAcceptanceError("LIVE_CONSEQUENTIAL_MARKER_MISSING")

    sandbox_present = set(actions) & set(SANDBOX_ACTIONS)
    if sandbox_present and sandbox_present != set(SANDBOX_ACTIONS):
        raise LiveReleaseAcceptanceError("LIVE_SANDBOX_SURFACE_PARTIAL")

    real_present = set(actions) & set(REAL_ACTIONS)
    allowed_real_shapes: tuple[set[str], ...] = (
        set(),
        {"getRealTradingStatus"},
        set(REAL_ACTIONS),
    )
    if real_present not in allowed_real_shapes:
        raise LiveReleaseAcceptanceError("LIVE_REAL_SURFACE_PARTIAL")


def accept_live_gateway_authority(
    *,
    base_url: str,
    expected_app_version: str,
    approved_hosts: frozenset[str],
    checked_at: datetime | None = None,
    fetcher: JsonFetcher | None = None,
) -> LiveGatewayAuthorityAcceptanceV1:
    """Verify live health and the reviewed v9 GPT Action authority without mutation calls."""

    canonical_base_url = _normalize_base_url(base_url, approved_hosts)
    health_url = f"{canonical_base_url}/health"
    openapi_url = f"{canonical_base_url}/openapi.json"
    load = fetcher or _load_json_document

    health_document: FetchedJsonDocument = load(health_url)
    openapi_document: FetchedJsonDocument = load(openapi_url)
    _validate_document_metadata(
        health_document,
        expected_url=health_url,
        component="HEALTH",
    )
    _validate_document_metadata(
        openapi_document,
        expected_url=openapi_url,
        component="OPENAPI",
    )

    health = health_document.payload
    if health.get("status") != "ok":
        raise LiveReleaseAcceptanceError("LIVE_HEALTH_STATUS_REJECTED")
    health_version = str(health.get("version") or "")
    if health_version != expected_app_version:
        raise LiveReleaseAcceptanceError("LIVE_HEALTH_VERSION_MISMATCH")
    if health.get("trading_methods") is not False:
        raise LiveReleaseAcceptanceError("LIVE_LEGACY_TRADING_METHODS_ENABLED")

    configured = _mapping(health.get("configured"), "LIVE_CONFIGURATION_STATUS_REQUIRED")
    if configured.get("tinvest_token") is not True:
        raise LiveReleaseAcceptanceError("LIVE_TINVEST_NOT_CONFIGURED")
    if configured.get("gateway_api_key") is not True:
        raise LiveReleaseAcceptanceError("LIVE_GATEWAY_KEY_NOT_CONFIGURED")

    openapi = openapi_document.payload
    openapi_version = str(openapi.get("openapi") or "")
    if not openapi_version.startswith("3."):
        raise LiveReleaseAcceptanceError("LIVE_OPENAPI_VERSION_REJECTED")
    info = _mapping(openapi.get("info"), "LIVE_OPENAPI_INFO_REQUIRED")
    if str(info.get("version") or "") != expected_app_version:
        raise LiveReleaseAcceptanceError("LIVE_OPENAPI_APP_VERSION_MISMATCH")
    servers = openapi.get("servers")
    if not isinstance(servers, list) or len(servers) != 1:
        raise LiveReleaseAcceptanceError("LIVE_OPENAPI_SERVER_REQUIRED")
    server = _mapping(servers[0], "LIVE_OPENAPI_SERVER_INVALID")
    if server.get("url") != canonical_base_url:
        raise LiveReleaseAcceptanceError("LIVE_OPENAPI_SERVER_MISMATCH")

    actions = _extract_actions(openapi)
    _validate_action_surface(actions)

    operation_ids = tuple(sorted(actions))
    sandbox_present = bool(set(actions) & set(SANDBOX_ACTIONS))
    real_present = set(actions) & set(REAL_ACTIONS)
    timestamp = checked_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("checked_at must be timezone-aware")

    return LiveGatewayAuthorityAcceptanceV1(
        checked_at=timestamp.astimezone(timezone.utc),
        base_url=canonical_base_url,
        app_version=health_version,
        operation_ids=operation_ids,
        sandbox_enabled=sandbox_present,
        real_status_exposed="getRealTradingStatus" in actions,
        real_execution_ready_surface=real_present == set(REAL_ACTIONS),
    )
