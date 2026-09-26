from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

import omni_cio.reconciliation as broker


class FakeBase:
    OPERATION_TYPE_NUMBER_TO_NAME: dict[int, str] = {}
    OPERATION_STATE_NUMBER_TO_NAME: dict[int, str] = {}

    @staticmethod
    def normalized_operation_enum(
        value: Any,
        mapping: dict[int, str],
        default: str,
    ) -> str:
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
        if value in (None, ""):
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
            return {
                str(key): FakeBase.json_safe_value(item) for key, item in value.items()
            }
        if isinstance(value, (list, tuple, set)):
            return [FakeBase.json_safe_value(item) for item in value]
        return value


def money(amount: str, currency: str = "RUB") -> dict[str, str]:
    return {"amount": amount, "currency": currency}


def operations_payload(
    *,
    purchase: str,
    sale: str = "0",
    commission: str = "0",
    complete: bool = True,
) -> dict[str, Any]:
    return {
        "status": "ok" if complete else "partial",
        "operations_count": 2,
        "executed_operations": 2,
        "duplicates_removed": 0,
        "pagination": {"truncated": not complete},
        "reconciliation": {"status": "ok" if complete else "warning"},
        "cash_summary_by_currency": [
            {
                "currency": "RUB",
                "purchases": {"amount": purchase},
                "sales": {"amount": sale},
                "broker_commissions": {"amount": commission},
            }
        ],
        "complete": complete,
    }


def build(
    *,
    report_rows: list[dict[str, Any]],
    raw_operations: list[dict[str, Any]],
    api_purchase: str,
    api_commission: str,
    report_status: str = "ready",
) -> dict[str, Any]:
    now = datetime(2026, 7, 27, 9, 0, tzinfo=timezone.utc)
    return broker.build_reconciliation_payload(
        base=FakeBase,
        app_version="3.9.1",
        account={"masked_id": "***3118"},
        period={
            "from": "2026-07-01T00:00:00+00:00",
            "to": now.isoformat(),
            "requested_days": 30,
            "period_adjusted_to_calendar_year": False,
        },
        report_generation={
            "status": report_status,
            "task_id": "task-1",
            "wait_seconds": 0,
            "error": {
                "code": "",
                "grpc_code": "",
                "exception_type": "",
                "message": "",
            },
        },
        report_rows=report_rows,
        report_pagination={
            "pages_fetched": 1 if report_status == "ready" else 0,
            "pages_count": 1 if report_status == "ready" else 0,
            "items_count": len(report_rows),
            "rows_received": len(report_rows),
            "max_pages": 100,
            "truncated": False,
        },
        operations_payload=operations_payload(
            purchase=api_purchase,
            commission=api_commission,
        ),
        raw_operations=raw_operations,
        component_errors=[],
        retrieved_at=now.isoformat(),
    )


def test_ready_report_matches_operations_without_double_counting() -> None:
    report_rows = [
        {
            "trade_id": "trade-1",
            "figi": "BBG004730N88",
            "direction": "BUY",
            "trade_datetime": "2026-07-20T10:15:00+00:00",
            "quantity": 3,
            "total_order_amount": money("826.22"),
            "broker_commission": money("2.48"),
            "exchange_commission": money("0"),
            "exchange_clearing_commission": money("0"),
        }
    ]
    raw_operations = [
        {
            "date": "2026-07-20T10:15:00+00:00",
            "type": "OPERATION_TYPE_BUY",
            "state": "OPERATION_STATE_EXECUTED",
            "figi": "BBG004730N88",
            "payment": money("-826.22"),
            "trades_info": {
                "trades": [
                    {
                        "trade_id": "trade-1",
                        "date_time": "2026-07-20T10:15:00+00:00",
                        "quantity": 3,
                        "price": money("274.58"),
                    }
                ]
            },
        },
        {
            "date": "2026-07-20T10:15:01+00:00",
            "type": "OPERATION_TYPE_BROKER_FEE",
            "state": "OPERATION_STATE_EXECUTED",
            "payment": money("-2.48"),
        },
    ]

    payload = build(
        report_rows=report_rows,
        raw_operations=raw_operations,
        api_purchase="826.22",
        api_commission="2.48",
    )

    assert payload["status"] == "ok"
    assert payload["version"] == "3.9.1"
    assert payload["broker_report_summary"]["rows"] == 1
    assert payload["trade_reconciliation"]["matched_by_trade_id"] == 1
    assert payload["trade_reconciliation"]["report_only"] == 0
    assert payload["cash_flow_reconciliation"][0]["status"] == "matched"
    assert payload["commission_reconciliation"][0]["status"] == "matched"
    assert payload["reconciliation"]["confirmed"] is True
    assert payload["quality"]["complete"] is True
    assert payload["complete"] is True
    assert payload["trading_methods"] is False


def test_report_difference_prevents_confirmed_reconciliation() -> None:
    report_rows = [
        {
            "trade_id": "trade-2",
            "figi": "BBG004730N88",
            "direction": "BUY",
            "trade_datetime": "2026-07-21T10:15:00+00:00",
            "quantity": 4,
            "total_order_amount": money("1102.26"),
            "broker_commission": money("3.31"),
        }
    ]
    raw_operations = [
        {
            "date": "2026-07-21T10:15:00+00:00",
            "type": "OPERATION_TYPE_BUY",
            "state": "OPERATION_STATE_EXECUTED",
            "figi": "BBG004730N88",
            "payment": money("-1100"),
            "trades_info": {
                "trades": [
                    {
                        "trade_id": "trade-2",
                        "date_time": "2026-07-21T10:15:00+00:00",
                        "quantity": 4,
                    }
                ]
            },
        }
    ]

    payload = build(
        report_rows=report_rows,
        raw_operations=raw_operations,
        api_purchase="1100",
        api_commission="0",
    )

    assert payload["status"] == "partial"
    assert payload["trade_reconciliation"]["status"] == "matched"
    assert payload["cash_flow_reconciliation"][0]["status"] == "warning"
    assert payload["commission_reconciliation"][0]["status"] == "warning"
    assert payload["reconciliation"]["confirmed"] is False
    assert payload["complete"] is False


def test_pending_report_returns_task_without_false_confirmation() -> None:
    payload = build(
        report_rows=[],
        raw_operations=[],
        api_purchase="0",
        api_commission="0",
        report_status="pending",
    )

    assert payload["status"] == "pending"
    assert payload["report_generation"]["task_id"] == "task-1"
    assert payload["trade_reconciliation"]["status"] == "unavailable"
    assert payload["reconciliation"]["confirmed"] is False
    assert payload["quality"]["report_ready"] is False
    assert payload["complete"] is False
    assert payload["trading_methods"] is False
