from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

from omni_cio.analytics import operations_source_v1 as operations_analytics


class FakeBase:
    OPERATION_TYPE_NUMBER_TO_NAME: dict[int, str] = {}
    OPERATION_STATE_NUMBER_TO_NAME: dict[int, str] = {}

    @staticmethod
    def normalized_operation_enum(value: Any, mapping: dict[int, str], default: str) -> str:
        del mapping
        if value is None:
            return default
        if isinstance(value, Enum):
            return value.name
        return str(value).rsplit(".", 1)[-1]

    @staticmethod
    def decimal_from_any(value: Any) -> Decimal | None:
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, Decimal):
            return value
        if isinstance(value, dict):
            if "amount" in value:
                return Decimal(str(value["amount"]))
            if "units" in value or "nano" in value:
                units = Decimal(str(value.get("units", 0)))
                nano = Decimal(str(value.get("nano", 0))) / Decimal("1000000000")
                return units + nano
        return Decimal(str(value))

    @staticmethod
    def decimal_string(value: Decimal) -> str:
        text = format(value.quantize(Decimal("0.000000001")), "f")
        return text.rstrip("0").rstrip(".") or "0"

    @staticmethod
    def parse_datetime(value: Any) -> datetime | None:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            result = value
        else:
            result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if result.tzinfo is None:
            result = result.replace(tzinfo=timezone.utc)
        return result.astimezone(timezone.utc)

    @staticmethod
    def json_safe_value(value: Any) -> Any:
        if isinstance(value, Decimal):
            return FakeBase.decimal_string(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(key): FakeBase.json_safe_value(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [FakeBase.json_safe_value(item) for item in value]
        return value


def money(amount: str, currency: str = "RUB") -> dict[str, str]:
    return {"amount": amount, "currency": currency}


def operation(
    *,
    date: datetime,
    operation_type: str,
    state: str = "OPERATION_STATE_EXECUTED",
    payment: dict[str, str] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "date": date.isoformat(),
        "type": operation_type,
        "state": state,
        "payment": payment,
        **extra,
    }


def build(raw: list[dict[str, Any]], *, truncated: bool = False) -> dict[str, Any]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=90)
    return operations_analytics.build_operations_analytics(
        base=FakeBase,
        app_version="3.8.0",
        account={"masked_id": "***3118"},
        raw_operations=raw,
        period={"from": start.isoformat(), "to": end.isoformat(), "days": 90},
        pagination={
            "pages_fetched": 1,
            "page_limit": 1000,
            "max_pages": 50,
            "items_received": len(raw),
            "has_next": truncated,
            "truncated": truncated,
            "cursor_loop_detected": False,
            "server_period_filter_applied": True,
        },
        component_errors=[],
        retrieved_at=end.isoformat(),
    )


def cash_row(payload: dict[str, Any], currency: str) -> dict[str, Any]:
    return next(row for row in payload["cash_summary_by_currency"] if row["currency"] == currency)


def test_executed_only_deduplication_and_double_count_protection() -> None:
    now = datetime.now(timezone.utc)
    deposit = operation(
        date=now - timedelta(days=10),
        operation_type="OPERATION_TYPE_INPUT",
        payment=money("1000"),
        id="unstable-a",
        cursor="cursor-a",
    )
    duplicate_deposit = {
        **deposit,
        "id": "unstable-b",
        "cursor": "cursor-b",
    }
    buy = operation(
        date=now - timedelta(days=5),
        operation_type="OPERATION_TYPE_BUY",
        payment=money("-800"),
        instrument_uid="uid-sber",
        name="Сбер Банк",
        commission=money("-2.5"),
        child_operations=[{"payment": money("-2.5")}],
        trades_info={"trades": [{"quantity": 1}]},
    )
    old_fee = operation(
        date=now - timedelta(days=5, seconds=2),
        operation_type="OPERATION_TYPE_BROKER_FEE",
        payment=money("-2"),
        parent_operation_id="parent-order-1",
        id="fee-old",
    )
    updated_fee = operation(
        date=now - timedelta(days=5),
        operation_type="OPERATION_TYPE_BROKER_FEE",
        payment=money("-2.5"),
        parent_operation_id="parent-order-1",
        id="fee-new",
    )
    canceled_sell = operation(
        date=now - timedelta(days=1),
        operation_type="OPERATION_TYPE_SELL",
        state="OPERATION_STATE_CANCELED",
        payment=money("900"),
        instrument_uid="uid-sber",
    )

    payload = build(
        [deposit, duplicate_deposit, buy, old_fee, updated_fee, canceled_sell]
    )

    assert payload["status"] == "ok"
    assert payload["version"] == "3.8.0"
    assert payload["operations_count"] == 4
    assert payload["duplicates_removed"] == 2
    assert payload["executed_operations"] == 3
    assert payload["canceled_operations"] == 1

    rub = cash_row(payload, "RUB")
    assert rub["deposits"]["amount"] == "1000"
    assert rub["purchases"]["amount"] == "800"
    assert rub["broker_commissions"]["amount"] == "2.5"
    assert rub["sales"]["amount"] == "0"

    reconciliation = payload["reconciliation"]
    assert reconciliation["status"] == "ok"
    assert reconciliation["commission_double_count_protection"] == {
        "status": "applied",
        "canonical_cash_basis": "top_level_operation.payment",
        "nested_commission_fields_excluded": 1,
        "parent_type_updates_collapsed": 1,
        "passed": True,
    }
    assert reconciliation["parent_child_double_count_protection"][
        "embedded_child_operations_excluded"
    ] == 1
    assert reconciliation["parent_child_double_count_protection"][
        "embedded_trades_excluded"
    ] == 1
    assert payload["complete"] is True
    assert payload["trading_methods"] is False


def test_currencies_remain_separate_without_fx_aggregation() -> None:
    now = datetime.now(timezone.utc)
    payload = build(
        [
            operation(
                date=now - timedelta(days=3),
                operation_type="OPERATION_TYPE_INPUT",
                payment=money("1000", "RUB"),
            ),
            operation(
                date=now - timedelta(days=2),
                operation_type="OPERATION_TYPE_BUY",
                payment=money("-100", "RUB"),
                instrument_uid="rub-share",
            ),
            operation(
                date=now - timedelta(days=1),
                operation_type="OPERATION_TYPE_DIVIDEND",
                payment=money("5", "USD"),
                instrument_uid="usd-share",
            ),
        ]
    )

    assert {row["currency"] for row in payload["cash_summary_by_currency"]} == {
        "RUB",
        "USD",
    }
    assert cash_row(payload, "RUB")["purchases"]["amount"] == "100"
    assert cash_row(payload, "USD")["dividends"]["amount"] == "5"
    assert payload["quality"]["currencies_detected"] == 2
    assert payload["quality"]["no_cross_currency_aggregation"] is True
    assert payload["complete"] is True


def test_sign_warning_or_truncated_pagination_prevents_complete_status() -> None:
    now = datetime.now(timezone.utc)
    payload = build(
        [
            operation(
                date=now - timedelta(days=1),
                operation_type="OPERATION_TYPE_OUTPUT",
                payment=money("10"),
            )
        ],
        truncated=True,
    )

    assert payload["status"] == "partial"
    assert payload["pagination"]["truncated"] is True
    assert payload["reconciliation"]["payment_sign_check"]["status"] == "warning"
    assert payload["reconciliation"]["payment_sign_check"]["mismatches"] == 1
    assert payload["quality"]["pagination_complete"] is False
    assert payload["quality"]["reconciliation_confirmed"] is False
    assert payload["complete"] is False
