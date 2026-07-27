from __future__ import annotations

from typing import Any

from fastapi import Depends, Query

import app_v360 as legacy
import app_v371 as archived
from app_v371 import *  # noqa: F401,F403
import operations_analytics as operations_analytics_engine
import broker_report_reconciliation as broker_report_reconciliation_engine


APP_VERSION = "3.9.1"
ENTRYPOINT = "app:app"

# Upgrade both archived wrappers because established route handlers resolve
# their module globals at call time.
archived.APP_VERSION = APP_VERSION
archived.ENTRYPOINT = ENTRYPOINT
legacy.APP_VERSION = APP_VERSION
legacy.ENTRYPOINT = ENTRYPOINT

app = archived.app
base = archived.base
app.version = APP_VERSION
app.description = (
    "Private read-only gateway between a Custom GPT and T-Invest API. It exposes "
    "connection, portfolio, market, purchase-capacity, and operations data. "
    "v3.9.1 adds asynchronous official broker-report generation, paginated report "
    "loading, and currency-local trade and commission reconciliation. It cannot "
    "create, submit, replace, or cancel orders."
)

for capability in (
    "operations_analytics",
    "operations_cash_flow_reconciliation",
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

app.openapi_schema = None
