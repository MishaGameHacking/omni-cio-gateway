from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from omni_cio.adapters import (
    OperationsAnalyticsAdapterError,
    operations_analytics_v1_from_payload,
)
from omni_cio.contracts.v1 import (
    Completeness,
    DataQuality,
    OperationCategory,
)


CATEGORIES = tuple(category.value for category in OperationCategory)


def _bucket(
    *,
    count: int = 0,
    amount: str = "0",
    net_payment: str = "0",
    inflow: str = "0",
    outflow: str = "0",
) -> dict[str, Any]:
    return {
        "count": count,
        "amount": amount,
        "net_payment": net_payment,
        "inflow": inflow,
        "outflow": outflow,
    }


def _cash_row(currency: str) -> dict[str, Any]:
    return {
        "currency": currency,
        **{category: _bucket() for category in CATEGORIES},
    }


def _payload() -> dict[str, Any]:
    rub = _cash_row("RUB")
    rub["deposits"] = _bucket(
        count=1,
        amount="1000",
        net_payment="1000",
        inflow="1000",
    )
    rub["purchases"] = _bucket(
        count=1,
        amount="800",
        net_payment="-800",
        outflow="800",
    )
    rub["broker_commissions"] = _bucket(
        count=1,
        amount="2.5",
        net_payment="-2.5",
        outflow="2.5",
    )
    category_counts = {category: 0 for category in CATEGORIES}
    category_counts.update(
        {
            "deposits": 1,
            "purchases": 1,
            "broker_commissions": 1,
        }
    )
    return {
        "status": "ok",
        "version": "3.9.1",
        "retrieved_at": "2026-07-28T18:10:00+00:00",
        "account": {"masked_id": "***3118", "name": "ИИС"},
        "period": {
            "from": "2026-04-29T18:10:00+00:00",
            "to": "2026-07-28T18:10:00+00:00",
            "days": 90,
        },
        "pagination": {
            "pages_fetched": 1,
            "page_limit": 1000,
            "max_pages": 50,
            "items_received": 5,
            "has_next": False,
            "truncated": False,
            "cursor_loop_detected": False,
            "server_period_filter_applied": True,
        },
        "operations_count": 3,
        "duplicates_removed": 2,
        "executed_operations": 3,
        "canceled_operations": 0,
        "operations_in_progress": 0,
        "state_counts": {"OPERATION_STATE_EXECUTED": 3},
        "category_counts": category_counts,
        "cash_summary_by_currency": [rub],
        "net_external_flow": [
            {
                "currency": "RUB",
                "deposits": "1000",
                "withdrawals": "0",
                "net_external_flow": "1000",
            }
        ],
        "turnover": [
            {
                "currency": "RUB",
                "purchases": "800",
                "sales": "0",
                "turnover": "800",
            }
        ],
        "instrument_activity": [
            {
                "instrument_uid": "uid-rub-share",
                "position_uid": None,
                "figi": None,
                "name": "Тестовая акция",
                "instrument_type": "share",
                "currency": "RUB",
                "operation_count": 1,
                "purchases": "800",
                "sales": "0",
                "coupons": "0",
                "dividends": "0",
                "bond_redemptions": "0",
                "net_payment": "-800",
            }
        ],
        "reconciliation": {
            "executed_only": True,
            "payment_sign_check": {
                "status": "passed",
                "checked": 3,
                "mismatches": 0,
                "examples": [],
            },
            "category_totals_check": {
                "status": "passed",
                "checks": [
                    {
                        "currency": "RUB",
                        "operations_net_payment": "197.5",
                        "categories_net_payment": "197.5",
                        "difference": "0",
                        "status": "passed",
                    }
                ],
            },
            "commission_double_count_protection": {
                "status": "applied",
                "canonical_cash_basis": "top_level_operation.payment",
                "nested_commission_fields_excluded": 1,
                "parent_type_updates_collapsed": 1,
                "passed": True,
            },
            "parent_child_double_count_protection": {
                "status": "applied",
                "top_level_operations_only": True,
                "embedded_child_operations_excluded": 1,
                "embedded_trades_excluded": 1,
                "top_level_parent_linked_operations": 1,
                "passed": True,
            },
            "status": "ok",
        },
        "quality": {
            "raw_items_received": 5,
            "items_outside_period": 0,
            "invalid_date_rows": 0,
            "exact_duplicates_removed": 1,
            "commission_updates_collapsed": 1,
            "currencies_detected": 1,
            "unknown_operation_types": 0,
            "invalid_money_rows": 0,
            "pagination_complete": True,
            "reconciliation_confirmed": True,
            "instrument_groups_total": 1,
            "instrument_groups_returned": 1,
            "instrument_groups_skipped_by_limit": 0,
            "complete": True,
            "no_cross_currency_aggregation": True,
            "read_only": True,
        },
        "complete": True,
        "component_errors": [],
        "trading_methods": False,
        "warnings": ["Currencies are calculated independently."],
    }


def _category_bucket(model: Any, category: OperationCategory) -> Any:
    currency = model.cash_flows_by_currency[0]
    return next(row.bucket for row in currency.categories if row.category == category)


def test_complete_payload_maps_exact_decimals_and_provenance() -> None:
    model = operations_analytics_v1_from_payload(_payload())

    assert model.metadata.schema_name == "operations_analytics"
    assert model.metadata.schema_version == "1.0"
    assert model.metadata.quality.quality == DataQuality.VERIFIED
    assert model.metadata.quality.completeness == Completeness.COMPLETE
    assert model.metadata.account.masked_id == "***3118"
    assert model.metadata.provenance[0].operation == "get_operations_analytics"
    assert _category_bucket(
        model,
        OperationCategory.BROKER_COMMISSIONS,
    ).gross_amount == Decimal("2.5")
    assert model.net_external_flow[0].net_external_flow == Decimal("1000")
    assert model.turnover[0].turnover == Decimal("800")
    assert model.source_quality.no_cross_currency_aggregation is True

    serialized = model.model_dump(mode="json")
    assert serialized["turnover"][0]["turnover"] == "800"
    with pytest.raises(ValidationError):
        model.operations_count = 99  # type: ignore[misc]


def test_multiple_currencies_remain_separate() -> None:
    payload = _payload()
    usd = _cash_row("USD")
    usd["dividends"] = _bucket(
        count=1,
        amount="5",
        net_payment="5",
        inflow="5",
    )
    payload["cash_summary_by_currency"].append(usd)
    payload["net_external_flow"].append(
        {
            "currency": "USD",
            "deposits": "0",
            "withdrawals": "0",
            "net_external_flow": "0",
        }
    )
    payload["turnover"].append(
        {
            "currency": "USD",
            "purchases": "0",
            "sales": "0",
            "turnover": "0",
        }
    )
    payload["instrument_activity"].append(
        {
            "instrument_uid": "uid-usd-share",
            "position_uid": None,
            "figi": None,
            "name": "USD share",
            "instrument_type": "share",
            "currency": "USD",
            "operation_count": 1,
            "purchases": "0",
            "sales": "0",
            "coupons": "0",
            "dividends": "5",
            "bond_redemptions": "0",
            "net_payment": "5",
        }
    )
    payload["operations_count"] = 4
    payload["executed_operations"] = 4
    payload["state_counts"]["OPERATION_STATE_EXECUTED"] = 4
    payload["category_counts"]["dividends"] = 1
    payload["reconciliation"]["payment_sign_check"]["checked"] = 4
    payload["reconciliation"]["category_totals_check"]["checks"].append(
        {
            "currency": "USD",
            "operations_net_payment": "5",
            "categories_net_payment": "5",
            "difference": "0",
            "status": "passed",
        }
    )
    payload["quality"]["currencies_detected"] = 2
    payload["quality"]["instrument_groups_total"] = 2
    payload["quality"]["instrument_groups_returned"] = 2

    model = operations_analytics_v1_from_payload(payload)

    assert {row.currency for row in model.cash_flows_by_currency} == {"RUB", "USD"}
    assert {row.currency for row in model.turnover} == {"RUB", "USD"}
    assert model.metadata.quality.quality == DataQuality.VERIFIED


def test_truncated_pagination_becomes_degraded_and_incomplete() -> None:
    payload = _payload()
    payload["status"] = "partial"
    payload["complete"] = False
    payload["pagination"]["has_next"] = True
    payload["pagination"]["truncated"] = True
    payload["quality"]["pagination_complete"] = False
    payload["quality"]["complete"] = False

    model = operations_analytics_v1_from_payload(payload)

    assert model.metadata.quality.quality == DataQuality.DEGRADED
    assert model.metadata.quality.completeness == Completeness.INCOMPLETE
    assert "OPERATIONS_PAGINATION_TRUNCATED" in {
        issue.code for issue in model.metadata.quality.issues
    }


def test_sign_warning_is_preserved_instead_of_inventing_clean_data() -> None:
    payload = _payload()
    payload["status"] = "partial"
    payload["complete"] = False
    payload["reconciliation"]["payment_sign_check"] = {
        "status": "warning",
        "checked": 3,
        "mismatches": 1,
        "examples": [
            {
                "type": "OPERATION_TYPE_OUTPUT",
                "category": "withdrawals",
                "currency": "RUB",
                "payment": "10",
                "expected_sign": "nonpositive",
            }
        ],
    }
    payload["reconciliation"]["status"] = "warning"
    payload["quality"]["reconciliation_confirmed"] = False
    payload["quality"]["complete"] = False

    model = operations_analytics_v1_from_payload(payload)

    assert model.reconciliation.payment_sign_check.mismatches == 1
    assert model.reconciliation.payment_sign_check.examples[0].payment == Decimal(
        "10"
    )
    assert model.metadata.quality.quality == DataQuality.DEGRADED


def test_component_error_is_represented_without_raw_error_content() -> None:
    payload = _payload()
    payload["status"] = "partial"
    payload["complete"] = False
    payload["quality"]["complete"] = False
    payload["component_errors"] = [
        {
            "component": "operations",
            "error": {"message": "private upstream detail"},
        }
    ]

    model = operations_analytics_v1_from_payload(payload)

    assert "OPERATIONS_COMPONENT_ERRORS" in {
        issue.code for issue in model.metadata.quality.issues
    }
    assert "private upstream detail" not in model.model_dump_json()


def test_adapter_rejects_trading_enabled_or_unmasked_account() -> None:
    trading_payload = _payload()
    trading_payload["trading_methods"] = True
    with pytest.raises(
        OperationsAnalyticsAdapterError,
        match="trading_methods must be explicitly false",
    ):
        operations_analytics_v1_from_payload(trading_payload)

    account_payload = _payload()
    account_payload["account"]["masked_id"] = "123456789"
    with pytest.raises(ValidationError, match="account identifier must be masked"):
        operations_analytics_v1_from_payload(account_payload)


def test_cash_flow_and_reconciliation_arithmetic_fail_closed() -> None:
    bucket_payload = _payload()
    bucket_payload["cash_summary_by_currency"][0]["purchases"]["amount"] = "801"
    with pytest.raises(ValidationError, match="gross_amount"):
        operations_analytics_v1_from_payload(bucket_payload)

    reconciliation_payload = _payload()
    reconciliation_payload["reconciliation"]["category_totals_check"]["checks"][
        0
    ]["difference"] = "1"
    with pytest.raises(ValidationError, match="difference"):
        operations_analytics_v1_from_payload(reconciliation_payload)


def test_missing_quality_counter_and_cross_currency_flag_fail_closed() -> None:
    missing_payload = _payload()
    del missing_payload["quality"]["raw_items_received"]
    with pytest.raises(
        OperationsAnalyticsAdapterError,
        match="raw_items_received must be an integer",
    ):
        operations_analytics_v1_from_payload(missing_payload)

    currency_payload = _payload()
    currency_payload["quality"]["no_cross_currency_aggregation"] = False
    with pytest.raises(ValidationError, match="cross-currency aggregation"):
        operations_analytics_v1_from_payload(currency_payload)


def test_source_payload_is_not_mutated() -> None:
    payload = _payload()
    original = deepcopy(payload)

    operations_analytics_v1_from_payload(payload)

    assert payload == original
