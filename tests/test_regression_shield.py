import json
import os
from pathlib import Path
from typing import Any, Iterator

os.environ.setdefault("TINVEST_TOKEN", "regression-test-tinvest-token")
os.environ.setdefault("GATEWAY_API_KEY", "regression-test-gateway-key")
os.environ.setdefault(
    "RENDER_EXTERNAL_URL",
    "https://omni-cio-gateway.onrender.com",
)

from fastapi.testclient import TestClient

import app as gateway_module
from omni_cio.adapters import tinvest_order_compat_v1 as sdk_order_compat


EXPECTED_VERSION = "3.10.0"
EXPECTED_ENTRYPOINT = "app:app"
EXPECTED_ACTION_PATHS = {
    "/health": "gatewayHealth",
    "/connection": "getConnection",
    "/snapshot": "getPortfolioSnapshot",
    "/snapshot/enriched": "getEnrichedPortfolioSnapshot",
    "/portfolio/market-snapshot": "getPortfolioMarketSnapshot",
    "/portfolio/analytics": "getPortfolioAnalytics",
    "/portfolio/cash-liquidity": "getCashLiquiditySnapshot",
    "/portfolio/purchase-capacity": "getPurchaseCapacityPreview",
    "/operations": "getOperationsHistory",
    "/operations/analytics": "getOperationsAnalytics",
    "/operations/broker-report-reconciliation": "getBrokerReportReconciliation",
    "/instruments/search": "findInstrument",
    "/market/snapshot": "getMarketSnapshot",
    "/decision/final-review": "getFinalDecisionReview",
}
PROTECTED_URLS = (
    "/connection",
    "/snapshot",
    "/snapshot/enriched",
    "/portfolio/market-snapshot?depth=1&max_instruments=1",
    (
        "/portfolio/analytics?valuation_basis=last_price&top_n=5&"
        "depth=1&max_instruments=1"
    ),
    "/portfolio/cash-liquidity",
    (
        "/portfolio/purchase-capacity?"
        "instrument_uid=e6123145-9665-43e0-8413-cd61b8aa9b13&"
        "price_basis=manual&quantity_lots=1&manual_price=269.33"
    ),
    "/operations?days=1",
    "/operations/analytics?days=1",
    "/operations/broker-report-reconciliation?days=1&wait_seconds=0",
    "/instruments/search?query=SBER&limit=1",
    (
        "/market/snapshot?"
        "instrument_uid=e6123145-9665-43e0-8413-cd61b8aa9b13&depth=1"
    ),
    (
        "/decision/final-review?account=****1234&"
        "requested_option_id=option.limited&final_option_id=option.limited&"
        f"intent_fingerprint={'a' * 64}&instrument_count=1&"
        "instrument_keys=uid%3Ainstrument-1&"
        f"response_sha256={'1' * 64}&action_candidate_sha256={'2' * 64}"
    ),
)

client = TestClient(gateway_module.app)


def walk_json(value: Any) -> Iterator[Any]:
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_json(child)


def test_health_contract_and_read_only_invariants() -> None:
    response = client.get("/health")
    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "omni-cio-readonly-gateway"
    assert payload["version"] == EXPECTED_VERSION
    assert payload["trading_methods"] is False

    capabilities = set(payload["capabilities"])
    assert "market_source_diagnostics" in capabilities
    assert "portfolio_market_snapshot" in capabilities
    assert "portfolio_analytics" in capabilities
    assert "cash_liquidity_diagnostics" in capabilities
    assert "purchase_capacity_preview" in capabilities
    assert "purchase_capacity_integrity" in capabilities
    assert "operations_analytics" in capabilities
    assert "operations_cash_flow_reconciliation" in capabilities
    assert "broker_report_reconciliation" in capabilities
    assert "broker_report_async_generation" in capabilities
    assert "broker_report_async_integrity" in capabilities
    assert "broker_report_trade_reconciliation" in capabilities
    assert "final_decision_review" in capabilities
    assert "regression_shield" in capabilities

    assert payload["build"]["entrypoint"] == EXPECTED_ENTRYPOINT
    assert payload["build"]["deployment_platform"] in {"local", "render"}
    assert payload["regression_shield"] == {
        "profile": EXPECTED_VERSION,
        "read_only": True,
        "expected_entrypoint": EXPECTED_ENTRYPOINT,
    }

    serialized = json.dumps(payload, ensure_ascii=False)
    assert "regression-test-tinvest-token" not in serialized
    assert "regression-test-gateway-key" not in serialized


def test_all_private_actions_reject_missing_gateway_key_before_sdk_calls() -> None:
    for url in PROTECTED_URLS:
        response = client.get(url)
        assert response.status_code == 401, url
        assert response.json()["detail"]["code"] == "INVALID_GATEWAY_KEY"


def test_openapi_is_gpt_actions_compatible_and_operation_ids_are_unique() -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()

    assert schema["info"]["version"] == EXPECTED_VERSION
    assert schema["servers"][0]["url"] == (
        "https://omni-cio-gateway.onrender.com"
    )

    operation_ids: list[str] = []
    for path, expected_operation_id in EXPECTED_ACTION_PATHS.items():
        operation = schema["paths"][path]["get"]
        assert operation["operationId"] == expected_operation_id
        operation_ids.append(operation["operationId"])

        response_schema = operation["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        if "$ref" in response_schema:
            component_name = response_schema["$ref"].rsplit("/", maxsplit=1)[-1]
            response_schema = schema["components"]["schemas"][component_name]
        assert response_schema["type"] == "object"
        assert isinstance(response_schema["properties"], dict)

    purchase_schema = schema["paths"]["/portfolio/purchase-capacity"]["get"][
        "responses"
    ]["200"]["content"]["application/json"]["schema"]
    purchase_properties = purchase_schema["properties"]
    assert "commission_summary" in purchase_properties
    assert "currency_consistency" in purchase_properties
    assert "limit_summary" in purchase_properties
    assert "calculation_checks" in purchase_properties
    assert "integrity_status" in purchase_properties

    operations_schema = schema["paths"]["/operations/analytics"]["get"][
        "responses"
    ]["200"]["content"]["application/json"]["schema"]
    operations_properties = operations_schema["properties"]
    assert "cash_summary_by_currency" in operations_properties
    assert "net_external_flow" in operations_properties
    assert "turnover" in operations_properties
    assert "reconciliation" in operations_properties
    assert "quality" in operations_properties
    assert "complete" in operations_properties

    broker_operation = schema["paths"][
        "/operations/broker-report-reconciliation"
    ]["get"]
    broker_schema = broker_operation["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    broker_properties = broker_schema["properties"]
    assert "report_generation" in broker_properties
    assert "broker_report_summary" in broker_properties
    assert "trade_reconciliation" in broker_properties
    assert "commission_reconciliation" in broker_properties
    assert "cash_flow_reconciliation" in broker_properties
    assert "quality" in broker_properties

    days_parameter = next(
        parameter
        for parameter in broker_operation["parameters"]
        if parameter["name"] == "days"
    )
    assert days_parameter["schema"]["maximum"] == 31

    final_operation = schema["paths"]["/decision/final-review"]["get"]
    assert final_operation["security"] == [{"ApiKeyAuth": []}]
    assert "requestBody" not in final_operation
    final_query_names = tuple(
        parameter["name"]
        for parameter in final_operation["parameters"]
        if parameter["in"] == "query"
    )
    assert final_query_names == (
        "account",
        "requested_option_id",
        "final_option_id",
        "intent_fingerprint",
        "instrument_count",
        "instrument_keys",
        "response_sha256",
        "action_candidate_sha256",
    )

    assert len(operation_ids) == len(set(operation_ids))

    for node in walk_json(schema):
        if isinstance(node, dict) and node.get("type") == "object":
            assert "properties" in node
            assert isinstance(node["properties"], dict)


def test_openapi_exposes_no_mutating_or_trading_operations() -> None:
    schema = client.get("/openapi.json").json()
    http_methods = {"get", "post", "put", "patch", "delete"}
    forbidden_operation_markers = (
        "postorder",
        "createorder",
        "replaceorder",
        "cancelorder",
        "executeorder",
        "confirmtrade",
    )

    for path, path_item in schema["paths"].items():
        normalized_path = path.lower()
        assert not normalized_path.startswith("/orders")
        assert not normalized_path.startswith("/order/")
        assert not normalized_path.startswith("/execution")
        assert not normalized_path.startswith("/withdraw")
        assert not normalized_path.startswith("/transfer")

        exposed_methods = set(path_item).intersection(http_methods)
        assert exposed_methods <= {"get"}, (path, exposed_methods)
        for method in exposed_methods:
            operation_id = str(path_item[method].get("operationId") or "").lower()
            assert not any(
                marker in operation_id for marker in forbidden_operation_markers
            )


def test_purchase_preview_uses_an_explicit_broker_sdk_allowlist() -> None:
    assert sdk_order_compat.ALLOWED_ORDERS_METHODS == frozenset(
        {"get_max_lots", "get_order_price"}
    )
    assert sdk_order_compat.ALLOWED_CLIENT_SERVICES == frozenset(
        {"users", "instruments", "orders"}
    )

    orders_adapter_source = Path("sdk_order_compat.py").read_text(
        encoding="utf-8"
    ).split("class ClientView", maxsplit=1)[0]
    assert "def __getattr__" not in orders_adapter_source

    client_view_source = Path("sdk_order_compat.py").read_text(
        encoding="utf-8"
    ).split("class ClientView", maxsplit=1)[1].split(
        "class ClientContextAdapter",
        maxsplit=1,
    )[0]
    assert "def __getattr__" not in client_view_source


def test_render_uses_only_the_stable_application_entrypoint() -> None:
    render_config = Path("render.yaml").read_text(encoding="utf-8")
    assert (
        "startCommand: uvicorn app:app --host 0.0.0.0 --port $PORT"
        in render_config
    )
    assert "healthCheckPath: /health" in render_config
    assert "main_v" not in render_config


def test_market_source_diagnostics_remain_active() -> None:
    assert gateway_module.app is gateway_module.base.app
    assert gateway_module.app.version == EXPECTED_VERSION

    assert gateway_module.market_dealer_session(
        {"last_price_type": "LAST_PRICE_EXCHANGE"},
        {"trading_status": "SECURITY_TRADING_STATUS_DEALER_NORMAL_TRADING"},
        {"order_book_type": "ORDERBOOK_TYPE_UNSPECIFIED"},
    ) is True

    issues = gateway_module.trading_flag_consistency_issues(
        {"last_price_type": "LAST_PRICE_EXCHANGE"},
        {
            "trading_status": (
                "SECURITY_TRADING_STATUS_NOT_AVAILABLE_FOR_TRADING"
            ),
            "limit_order_available_flag": True,
            "market_order_available_flag": False,
            "api_trade_available_flag": False,
            "bestprice_order_available_flag": False,
            "only_best_price": False,
        },
        {"order_book_type": "ORDERBOOK_TYPE_UNSPECIFIED"},
    )
    assert any("trading is unavailable" in issue for issue in issues)
    assert any("api_trade_available_flag is false" in issue for issue in issues)
