from __future__ import annotations

from typing import Any

from fastapi import Depends, Query

import app_v360 as legacy
import app_v371 as archived
from app_v371 import *  # noqa: F401,F403
import omni_cio.reconciliation as broker_report_reconciliation_engine
from omni_cio.analytics import operations_source_v1 as operations_analytics_engine
from omni_cio.portfolio import market_source_v1 as portfolio_market_engine
from omni_cio.quality import wrap_portfolio_market_snapshot_with_shadow_validation
from omni_cio.release.final_decision_review_production_registration_v1 import (
    register_final_decision_review_production_sources,
)
import omni_cio.release.final_decision_review_route_v1 as final_review_route
from omni_cio.release.final_decision_review_workflow_bridge_v1 import (
    FinalDecisionReviewWorkflowBridgeV1,
)


APP_VERSION = "3.10.0"
ENTRYPOINT = "app:app"

# Upgrade both archived wrappers because established route handlers resolve
# their module globals at call time.
archived.APP_VERSION = APP_VERSION
archived.ENTRYPOINT = ENTRYPOINT
legacy.APP_VERSION = APP_VERSION
legacy.ENTRYPOINT = ENTRYPOINT

app = archived.app
base = archived.base
base.APP_VERSION = APP_VERSION
base.ENTRYPOINT = ENTRYPOINT
app.version = APP_VERSION
app.description = (
    "Private read-only gateway between a Custom GPT and T-Invest API. It exposes "
    "connection, portfolio, market, purchase-capacity, operations, and a private "
    "final decision-review retrieval route. v3.10.0 adds a bounded internal source "
    "registry and an authenticated GET-only final-review response without broker "
    "writes or execution semantics. It cannot create, submit, replace, or cancel "
    "orders."
)

# Existing route handlers call the module attribute at request time. The wrapper
# observes contract quality without changing the legacy response or blocking the
# current read-only Action while PR-06 runs in shadow mode.
portfolio_market_engine.get_portfolio_market_snapshot = (
    wrap_portfolio_market_snapshot_with_shadow_validation(
        portfolio_market_engine.get_portfolio_market_snapshot,
        logger=base.logger,
    )
)

for capability in (
    "operations_analytics",
    "operations_cash_flow_reconciliation",
    "final_decision_review_workflow_bridge",
    "final_decision_review_production_sources",
):
    if capability not in base.CAPABILITIES:
        base.CAPABILITIES.append(capability)


@app.get(
    "/operations/analytics",
    operation_id="getOperationsAnalytics",
    summary=(
        "Aggregate read-only executed operations, cash flows, turnover, duplicate "
        "protection, and reconciliation separately for each reported currency"
    ),
    dependencies=[Depends(base.require_gateway_key)],
)
def operations_analytics_v380(
    days: int = Query(
        90,
        ge=1,
        le=3650,
        description=(
            "Number of calendar days to load with GetOperationsByCursor. "
            "The default period is 90 days."
        ),
    ),
) -> dict[str, Any]:
    return operations_analytics_engine.get_operations_analytics(
        base=base,
        app_version=APP_VERSION,
        days=days,
    )


# GPT Actions requires explicit object properties for every response object.
_OA_OPS_AMOUNT_BUCKET = base._oa_obj(
    {
        "count": base._OA_INT,
        "amount": base._OA_STRING,
        "net_payment": base._OA_STRING,
        "inflow": base._OA_STRING,
        "outflow": base._OA_STRING,
    }
)
_OA_OPS_CASH_ROW = base._oa_obj(
    {
        "currency": base._OA_STRING,
        "deposits": _OA_OPS_AMOUNT_BUCKET,
        "withdrawals": _OA_OPS_AMOUNT_BUCKET,
        "purchases": _OA_OPS_AMOUNT_BUCKET,
        "sales": _OA_OPS_AMOUNT_BUCKET,
        "broker_commissions": _OA_OPS_AMOUNT_BUCKET,
        "service_fees": _OA_OPS_AMOUNT_BUCKET,
        "margin_fees": _OA_OPS_AMOUNT_BUCKET,
        "other_fees": _OA_OPS_AMOUNT_BUCKET,
        "taxes": _OA_OPS_AMOUNT_BUCKET,
        "coupons": _OA_OPS_AMOUNT_BUCKET,
        "dividends": _OA_OPS_AMOUNT_BUCKET,
        "bond_redemptions": _OA_OPS_AMOUNT_BUCKET,
        "other": _OA_OPS_AMOUNT_BUCKET,
    }
)
_OA_OPS_NET_EXTERNAL_FLOW = base._oa_obj(
    {
        "currency": base._OA_STRING,
        "deposits": base._OA_STRING,
        "withdrawals": base._OA_STRING,
        "net_external_flow": base._OA_STRING,
    }
)
_OA_OPS_TURNOVER = base._oa_obj(
    {
        "currency": base._OA_STRING,
        "purchases": base._OA_STRING,
        "sales": base._OA_STRING,
        "turnover": base._OA_STRING,
    }
)
_OA_OPS_INSTRUMENT_ACTIVITY = base._oa_obj(
    {
        "instrument_uid": base._OA_STRING,
        "position_uid": base._OA_STRING,
        "figi": base._OA_STRING,
        "name": base._OA_STRING,
        "instrument_type": base._OA_STRING,
        "currency": base._OA_STRING,
        "operation_count": base._OA_INT,
        "purchases": base._OA_STRING,
        "sales": base._OA_STRING,
        "coupons": base._OA_STRING,
        "dividends": base._OA_STRING,
        "bond_redemptions": base._OA_STRING,
        "net_payment": base._OA_STRING,
    }
)
_OA_OPS_SIGN_EXAMPLE = base._oa_obj(
    {
        "type": base._OA_STRING,
        "category": base._OA_STRING,
        "currency": base._OA_STRING,
        "payment": base._OA_STRING,
        "expected_sign": base._OA_STRING,
    }
)
_OA_OPS_CATEGORY_CHECK = base._oa_obj(
    {
        "currency": base._OA_STRING,
        "operations_net_payment": base._OA_STRING,
        "categories_net_payment": base._OA_STRING,
        "difference": base._OA_STRING,
        "status": base._OA_STRING,
    }
)
_OA_OPS_ERROR_DETAIL = base._oa_obj(
    {
        "code": base._OA_STRING,
        "grpc_code": base._OA_STRING,
        "exception_type": base._OA_STRING,
        "message": base._OA_STRING,
        "tracking_id": base._OA_STRING,
    }
)
_OA_OPS_ERROR = base._oa_obj(
    {
        "component": base._OA_STRING,
        "error": _OA_OPS_ERROR_DETAIL,
    }
)

base._ACTION_200_SCHEMAS["/operations/analytics"] = base._oa_obj(
    {
        "status": base._OA_STRING,
        "version": base._OA_STRING,
        "retrieved_at": base._OA_STRING,
        "account": base._OA_ACCOUNT,
        "period": base._oa_obj(
            {
                "from": base._OA_STRING,
                "to": base._OA_STRING,
                "days": base._OA_INT,
            }
        ),
        "pagination": base._oa_obj(
            {
                "pages_fetched": base._OA_INT,
                "page_limit": base._OA_INT,
                "max_pages": base._OA_INT,
                "items_received": base._OA_INT,
                "has_next": base._OA_BOOL,
                "truncated": base._OA_BOOL,
                "cursor_loop_detected": base._OA_BOOL,
                "server_period_filter_applied": base._OA_BOOL,
            }
        ),
        "operations_count": base._OA_INT,
        "duplicates_removed": base._OA_INT,
        "executed_operations": base._OA_INT,
        "canceled_operations": base._OA_INT,
        "operations_in_progress": base._OA_INT,
        "state_counts": base._oa_obj(
            {
                "OPERATION_STATE_UNSPECIFIED": base._OA_INT,
                "OPERATION_STATE_EXECUTED": base._OA_INT,
                "OPERATION_STATE_CANCELED": base._OA_INT,
                "OPERATION_STATE_PROGRESS": base._OA_INT,
            }
        ),
        "category_counts": base._oa_obj(
            {
                "deposits": base._OA_INT,
                "withdrawals": base._OA_INT,
                "purchases": base._OA_INT,
                "sales": base._OA_INT,
                "broker_commissions": base._OA_INT,
                "service_fees": base._OA_INT,
                "margin_fees": base._OA_INT,
                "other_fees": base._OA_INT,
                "taxes": base._OA_INT,
                "coupons": base._OA_INT,
                "dividends": base._OA_INT,
                "bond_redemptions": base._OA_INT,
                "other": base._OA_INT,
            }
        ),
        "cash_summary_by_currency": base._oa_array(_OA_OPS_CASH_ROW),
        "net_external_flow": base._oa_array(_OA_OPS_NET_EXTERNAL_FLOW),
        "turnover": base._oa_array(_OA_OPS_TURNOVER),
        "instrument_activity": base._oa_array(_OA_OPS_INSTRUMENT_ACTIVITY),
        "reconciliation": base._oa_obj(
            {
                "executed_only": base._OA_BOOL,
                "payment_sign_check": base._oa_obj(
                    {
                        "status": base._OA_STRING,
                        "checked": base._OA_INT,
                        "mismatches": base._OA_INT,
                        "examples": base._oa_array(_OA_OPS_SIGN_EXAMPLE),
                    }
                ),
                "category_totals_check": base._oa_obj(
                    {
                        "status": base._OA_STRING,
                        "checks": base._oa_array(_OA_OPS_CATEGORY_CHECK),
                    }
                ),
                "commission_double_count_protection": base._oa_obj(
                    {
                        "status": base._OA_STRING,
                        "canonical_cash_basis": base._OA_STRING,
                        "nested_commission_fields_excluded": base._OA_INT,
                        "parent_type_updates_collapsed": base._OA_INT,
                        "passed": base._OA_BOOL,
                    }
                ),
                "parent_child_double_count_protection": base._oa_obj(
                    {
                        "status": base._OA_STRING,
                        "top_level_operations_only": base._OA_BOOL,
                        "embedded_child_operations_excluded": base._OA_INT,
                        "embedded_trades_excluded": base._OA_INT,
                        "top_level_parent_linked_operations": base._OA_INT,
                        "passed": base._OA_BOOL,
                    }
                ),
                "status": base._OA_STRING,
            }
        ),
        "quality": base._oa_obj(
            {
                "raw_items_received": base._OA_INT,
                "items_outside_period": base._OA_INT,
                "invalid_date_rows": base._OA_INT,
                "exact_duplicates_removed": base._OA_INT,
                "commission_updates_collapsed": base._OA_INT,
                "currencies_detected": base._OA_INT,
                "unknown_operation_types": base._OA_INT,
                "invalid_money_rows": base._OA_INT,
                "pagination_complete": base._OA_BOOL,
                "reconciliation_confirmed": base._OA_BOOL,
                "instrument_groups_total": base._OA_INT,
                "instrument_groups_returned": base._OA_INT,
                "instrument_groups_skipped_by_limit": base._OA_INT,
                "complete": base._OA_BOOL,
                "no_cross_currency_aggregation": base._OA_BOOL,
                "read_only": base._OA_BOOL,
            }
        ),
        "complete": base._OA_BOOL,
        "component_errors": base._oa_array(_OA_OPS_ERROR),
        "trading_methods": base._OA_BOOL,
        "warnings": base._oa_array(base._OA_STRING),
    },
    required=[
        "status",
        "version",
        "retrieved_at",
        "account",
        "period",
        "pagination",
        "operations_count",
        "cash_summary_by_currency",
        "reconciliation",
        "quality",
        "complete",
        "trading_methods",
    ],
)

broker_report_reconciliation_engine.register_gateway(
    app=app,
    base=base,
    app_version=APP_VERSION,
)

final_decision_review_registry = (
    final_review_route.register_final_decision_review_gateway(
        app=app,
        base=base,
        app_version=APP_VERSION,
    )
)

_base_openapi = app.openapi
_GPT_ACTIONS_HTTP_METHODS = frozenset(
    {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
)
_GPT_ACTIONS_IGNORED_TRACE_HEADERS = frozenset({"X-Correlation-ID", "X-Request-ID"})


def _patch_gpt_actions_openapi_compat(schema: dict[str, Any]) -> dict[str, Any]:
    """Publish one Bearer scheme and omit headers unsupported by GPT Actions."""

    components = schema.setdefault("components", {})
    security_schemes = components.setdefault("securitySchemes", {})
    canonical_security = security_schemes.get(
        final_review_route.FINAL_REVIEW_SECURITY_SCHEME
    )
    if not isinstance(canonical_security, dict):
        raise final_review_route.FinalDecisionReviewRouteError(
            "GPT_ACTIONS_BEARER_SECURITY_SCHEME_MISSING"
        )
    if (
        canonical_security.get("type") != "http"
        or str(canonical_security.get("scheme", "")).lower() != "bearer"
    ):
        raise final_review_route.FinalDecisionReviewRouteError(
            "GPT_ACTIONS_BEARER_SECURITY_SCHEME_INVALID"
        )

    # ChatGPT Actions supports one authentication scheme per Action definition.
    # Keep the reviewed ApiKeyAuth Bearer contract and rewrite every protected
    # operation to reference only that scheme. Public operations such as /health
    # remain public because they do not declare operation-level security.
    security_schemes.clear()
    security_schemes[final_review_route.FINAL_REVIEW_SECURITY_SCHEME] = (
        canonical_security
    )

    paths = schema.get("paths", {})
    if not isinstance(paths, dict):
        raise final_review_route.FinalDecisionReviewRouteError(
            "GPT_ACTIONS_OPENAPI_PATHS_INVALID"
        )
    for path_item in paths.values():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in _GPT_ACTIONS_HTTP_METHODS:
                continue
            if not isinstance(operation, dict):
                continue
            if operation.get("security"):
                operation["security"] = [
                    {final_review_route.FINAL_REVIEW_SECURITY_SCHEME: []}
                ]

    final_operation = paths.get(final_review_route.FINAL_REVIEW_PATH, {}).get("get")
    if not isinstance(final_operation, dict):
        raise final_review_route.FinalDecisionReviewRouteError(
            "FINAL_DECISION_REVIEW_OPENAPI_OPERATION_MISSING"
        )
    parameters = final_operation.get("parameters", [])
    if not isinstance(parameters, list):
        raise final_review_route.FinalDecisionReviewRouteError(
            "FINAL_DECISION_REVIEW_OPENAPI_PARAMETERS_INVALID"
        )
    final_operation["parameters"] = [
        parameter
        for parameter in parameters
        if not (
            isinstance(parameter, dict)
            and parameter.get("in") == "header"
            and parameter.get("name") in _GPT_ACTIONS_IGNORED_TRACE_HEADERS
        )
    ]
    return schema


def openapi_v310() -> dict[str, Any]:
    schema = _base_openapi()
    schema = final_review_route.patch_final_decision_review_openapi(schema)
    return _patch_gpt_actions_openapi_compat(schema)


app.openapi = openapi_v310
app.openapi_schema = None

final_decision_review_workflow_bridge = FinalDecisionReviewWorkflowBridgeV1(
    registry=final_decision_review_registry,
    openapi_provider=lambda: app.openapi(),
    expected_app_version=APP_VERSION,
)


def _load_final_decision_review_portfolio_payload() -> dict[str, Any]:
    return portfolio_market_engine.get_portfolio_market_snapshot(
        base=base,
        app_version=APP_VERSION,
        market_dealer_session=legacy.market_dealer_session,
        trading_flag_consistency_issues=legacy.trading_flag_consistency_issues,
        depth=1,
        max_instruments=50,
    )


final_decision_review_production_runtime = (
    register_final_decision_review_production_sources(
        bridge=final_decision_review_workflow_bridge,
        portfolio_payload_loader=_load_final_decision_review_portfolio_payload,
    )
)
final_decision_review_scenario_source_store = (
    final_decision_review_production_runtime.source_store
)
final_decision_review_source_wiring = (
    final_decision_review_production_runtime.source_wiring
)
