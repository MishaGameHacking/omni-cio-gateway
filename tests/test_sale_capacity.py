import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException

os.environ.setdefault("TINVEST_TOKEN", "regression-test-tinvest-token")
os.environ.setdefault("GATEWAY_API_KEY", "regression-test-gateway-key")

import app as gateway_module
from omni_cio.pretrade import sale_capacity_v1 as sale_capacity
from omni_cio.adapters.sdk_order_compat_v1 import with_sale_request_object_services


INSTRUMENT_UID = "e6123145-9665-43e0-8413-cd61b8aa9b13"
NOW = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)


def quotation(units: int, nano: int = 0) -> dict[str, object]:
    return {"units": str(units), "nano": nano}


def money(currency: str, units: int, nano: int = 0) -> dict[str, object]:
    return {"currency": currency, "units": str(units), "nano": nano}


def resolved_instrument(*, lot: int = 1, currency: str = "rub") -> dict[str, object]:
    return {
        "status": "resolved",
        "identity_check": {
            "overall": "PASS",
            "matches": 1,
            "conflicts": 0,
            "fields": {"instrument_uid": "match"},
        },
        "resolution": {
            "source": "T-Invest GetInstrumentBy",
            "cache_hit": False,
            "identifier_type": "INSTRUMENT_ID_TYPE_UID",
            "identifier": INSTRUMENT_UID,
            "api_calls": 1,
        },
        "instrument": {
            "name": "Тестовая облигация",
            "ticker": "BOND1",
            "isin": "RU000A000001",
            "figi": "BBG000000001",
            "uid": INSTRUMENT_UID,
            "position_uid": "position-uid",
            "class_code": "TQOB",
            "instrument_type": "bond",
            "instrument_kind": "INSTRUMENT_TYPE_BOND",
            "lot": lot,
            "currency": currency,
            "api_trade_available_flag": True,
        },
    }


def price_info() -> dict[str, object]:
    source_time = NOW - timedelta(seconds=10)
    return {
        "status": "ok",
        "basis": "best_bid",
        "source": "T-Invest GetOrderBook best bid",
        "price": "98",
        "source_time": source_time.isoformat(),
        "age_seconds": "10",
        "freshness": {
            "status": "fresh",
            "source_time": source_time.isoformat(),
            "age_seconds": "10",
            "fresh_threshold_seconds": "120",
        },
    }


def positions_data(*, balance: int = 5, blocked: int = 0) -> dict[str, object]:
    return {
        "securities": [
            {
                "instrument_uid": INSTRUMENT_UID,
                "balance": quotation(balance),
                "blocked": quotation(blocked),
            }
        ]
    }


def max_lots_data(*, sell_max_lots: int = 5) -> dict[str, object]:
    return {
        "currency": "rub",
        "sell_limits": {"sell_max_lots": sell_max_lots},
    }


def orders_data() -> dict[str, object]:
    return {
        "orders": [
            {
                "instrument_uid": INSTRUMENT_UID,
                "direction": "ORDER_DIRECTION_SELL",
                "lots_requested": 3,
                "lots_executed": 1,
            },
            {
                "instrument_uid": INSTRUMENT_UID,
                "direction": "ORDER_DIRECTION_BUY",
                "lots_requested": 9,
                "lots_executed": 0,
            },
            {
                "instrument_uid": "other-uid",
                "direction": 2,
                "lots_requested": 7,
                "lots_executed": 0,
            },
        ]
    }


def order_price_data() -> dict[str, object]:
    return {
        "lots_requested": 1,
        "initial_order_amount": money("rub", 98),
        "total_order_amount": money("rub", 99),
        "executed_commission": money("rub", 1),
        "service_commission": money("rub", 0),
        "deal_commission": money("rub", 0),
        "extra_bond": {"aci_value": money("rub", 2)},
    }


def component_statuses() -> dict[str, str]:
    return {
        "market_snapshot": "ok",
        "instrument_reference": "ok",
        "positions": "ok",
        "max_lots": "ok",
        "open_orders": "ok",
        "order_price": "ok",
    }


def test_builder_collects_read_only_sale_evidence_but_leaves_tax_blocked() -> None:
    payload = sale_capacity.build_sale_capacity_preview(
        base=gateway_module.base,
        app_version="3.9.1",
        account={"masked_id": "***3118", "name": "ИИС"},
        instrument_uid=INSTRUMENT_UID,
        instrument_resolution=resolved_instrument(),
        price_basis="best_bid",
        quantity_lots=1,
        price_info=price_info(),
        positions_data=positions_data(),
        max_lots_data=max_lots_data(),
        orders_data=orders_data(),
        order_price_data=order_price_data(),
        component_statuses=component_statuses(),
        component_errors=[],
        market_snapshot={
            "dealer_session": False,
            "market_data_sources": {
                "last_price_type": "LAST_PRICE_EXCHANGE",
                "order_book_type": "ORDERBOOK_TYPE_EXCHANGE",
            },
            "trading_flag_consistency": {"status": "ok", "issues": []},
        },
        retrieved_at=NOW.isoformat(),
    )

    assert payload["status"] == "ok"
    assert payload["request"]["direction"] == "ORDER_DIRECTION_SELL"
    assert payload["market_price"]["source"].endswith("best bid")
    assert payload["position_limits"]["position_lots"] == 5
    assert payload["position_limits"]["blocked_lots"] == 0
    assert payload["position_limits"]["sell_max_lots"] == 5
    assert payload["open_orders"]["matching_open_sell_orders"] == 1
    assert payload["open_orders"]["conflicting_sell_lots"] == 2
    assert payload["order_preview"]["gross_proceeds"] == {
        "amount": "100",
        "currency": "RUB",
    }
    assert payload["commission_summary"]["canonical_source"] == (
        "executed_commission"
    )
    assert payload["tax_basis"]["confirmed"] is False
    assert payload["calculation_checks"]["integrity_confirmed"] is False
    assert payload["quality"]["complete"] is True
    assert payload["quality"]["tax_basis_confirmed"] is False
    assert payload["quality"]["read_only"] is True
    assert payload["quality"]["no_order_created"] is True
    assert payload["trading_methods"] is False


def test_best_bid_and_last_price_selection_are_sell_specific() -> None:
    snapshot = {
        "last_price": {
            "status": "ok",
            "price": "98.1",
            "time": NOW.isoformat(),
            "age_seconds": 2,
        },
        "order_book": {
            "status": "ok",
            "time": NOW.isoformat(),
            "age_seconds": 1,
            "best_bid": {"price": "98"},
            "best_ask": {"price": "99"},
        },
    }
    bid = sale_capacity.select_sale_price(
        base=gateway_module.base,
        price_basis="best_bid",
        market_snapshot=snapshot,
    )
    last = sale_capacity.select_sale_price(
        base=gateway_module.base,
        price_basis="last_price",
        market_snapshot=snapshot,
    )

    assert bid["price"] == "98"
    assert bid["source"].endswith("best bid")
    assert last["price"] == "98.1"
    with pytest.raises(HTTPException, match="422"):
        sale_capacity.select_sale_price(
            base=gateway_module.base,
            price_basis="manual",
            market_snapshot=snapshot,
        )


def test_position_conversion_must_be_exact_and_duplicate_free() -> None:
    fractional = sale_capacity.build_sale_capacity_preview(
        base=gateway_module.base,
        app_version="3.9.1",
        account={"masked_id": "***3118"},
        instrument_uid=INSTRUMENT_UID,
        instrument_resolution=resolved_instrument(lot=2),
        price_basis="best_bid",
        quantity_lots=1,
        price_info=price_info(),
        positions_data=positions_data(balance=5),
        max_lots_data=max_lots_data(),
        orders_data={"orders": []},
        order_price_data=order_price_data(),
        component_statuses=component_statuses(),
        component_errors=[],
        retrieved_at=NOW.isoformat(),
    )
    assert fractional["status"] == "partial"
    assert fractional["position_limits"]["position_lots"] == "unavailable"
    assert fractional["position_limits"]["exact_lot_conversion"] is False

    duplicate_positions = positions_data()
    rows = duplicate_positions["securities"]
    assert isinstance(rows, list)
    rows.append(dict(rows[0]))
    duplicate = sale_capacity.build_sale_capacity_preview(
        base=gateway_module.base,
        app_version="3.9.1",
        account={"masked_id": "***3118"},
        instrument_uid=INSTRUMENT_UID,
        instrument_resolution=resolved_instrument(),
        price_basis="best_bid",
        quantity_lots=1,
        price_info=price_info(),
        positions_data=duplicate_positions,
        max_lots_data=max_lots_data(),
        orders_data={"orders": []},
        order_price_data=order_price_data(),
        component_statuses=component_statuses(),
        component_errors=[],
        retrieved_at=NOW.isoformat(),
    )
    assert duplicate["position_limits"]["duplicate_position_rows"] == 1
    assert duplicate["quality"]["position_availability_confirmed"] is False


def test_invalid_open_order_rows_degrade_checked_state() -> None:
    payload = sale_capacity.build_sale_capacity_preview(
        base=gateway_module.base,
        app_version="3.9.1",
        account={"masked_id": "***3118"},
        instrument_uid=INSTRUMENT_UID,
        instrument_resolution=resolved_instrument(),
        price_basis="best_bid",
        quantity_lots=1,
        price_info=price_info(),
        positions_data=positions_data(),
        max_lots_data=max_lots_data(),
        orders_data={
            "orders": [
                {
                    "instrument_uid": INSTRUMENT_UID,
                    "direction": 2,
                    "lots_requested": "broken",
                    "lots_executed": 0,
                }
            ]
        },
        order_price_data=order_price_data(),
        component_statuses=component_statuses(),
        component_errors=[],
        retrieved_at=NOW.isoformat(),
    )

    assert payload["status"] == "partial"
    assert payload["open_orders"]["checked"] is False
    assert payload["open_orders"]["invalid_order_rows"] == 1


def test_currency_and_component_failures_are_preserved() -> None:
    errors = [{"component": "order_price", "error": {"code": "UPSTREAM"}}]
    statuses = component_statuses()
    statuses["order_price"] = "error"
    payload = sale_capacity.build_sale_capacity_preview(
        base=gateway_module.base,
        app_version="3.9.1",
        account={"masked_id": "***3118"},
        instrument_uid=INSTRUMENT_UID,
        instrument_resolution=resolved_instrument(currency="usd"),
        price_basis="best_bid",
        quantity_lots=1,
        price_info=price_info(),
        positions_data=positions_data(),
        max_lots_data=max_lots_data(),
        orders_data={"orders": []},
        order_price_data=None,
        component_statuses=statuses,
        component_errors=errors,
        retrieved_at=NOW.isoformat(),
    )

    assert payload["status"] == "partial"
    assert payload["currency_consistency"]["status"] == "warning"
    assert payload["quality"]["component_errors"] == 1
    assert payload["component_errors"] == errors


class FakeUsers:
    def get_accounts(self) -> dict[str, object]:
        return {
            "accounts": [
                {
                    "id": "test-account-3118",
                    "name": "ИИС",
                    "type": "ACCOUNT_TYPE_TINKOFF_IIS",
                    "status": "ACCOUNT_STATUS_OPEN",
                    "access_level": "ACCOUNT_ACCESS_LEVEL_READ_ONLY",
                }
            ]
        }


class FakeInstruments:
    def get_instrument_by(self, *, id_type, id: str) -> dict[str, object]:
        assert id == INSTRUMENT_UID
        return {"instrument": resolved_instrument()["instrument"]}


class FakeOperations:
    calls: list[str] = []

    def get_positions(self, **kwargs) -> dict[str, object]:
        assert kwargs["account_id"] == "test-account-3118"
        self.calls.append("get_positions")
        return positions_data()

    def get_withdraw_limits(self, **kwargs):
        raise AssertionError("get_withdraw_limits must not be called")


class FakeOrders:
    calls: list[str] = []

    def get_orders(self, **kwargs) -> dict[str, object]:
        assert kwargs["account_id"] == "test-account-3118"
        self.calls.append("get_orders")
        return orders_data()

    def get_max_lots(self, **kwargs) -> dict[str, object]:
        assert kwargs["account_id"] == "test-account-3118"
        assert kwargs["instrument_id"] == INSTRUMENT_UID
        assert kwargs["price"] is not None
        self.calls.append("get_max_lots")
        return max_lots_data()

    def get_order_price(self, **kwargs) -> dict[str, object]:
        assert kwargs["account_id"] == "test-account-3118"
        assert kwargs["instrument_id"] == INSTRUMENT_UID
        assert kwargs["quantity"] == 1
        assert str(kwargs["direction"]).upper().endswith("SELL")
        self.calls.append("get_order_price")
        return order_price_data()

    def post_order(self, **kwargs):
        raise AssertionError("post_order must not be called")

    def replace_order(self, **kwargs):
        raise AssertionError("replace_order must not be called")

    def cancel_order(self, **kwargs):
        raise AssertionError("cancel_order must not be called")


class FakeClient:
    def __init__(self, token: str) -> None:
        assert token == "regression-test-tinvest-token"
        self.users = FakeUsers()
        self.instruments = FakeInstruments()
        self.operations = FakeOperations()
        self.orders = FakeOrders()
        self.market_data = object()
        self.stop_orders = object()
        self.sandbox = object()

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None


def fake_market_snapshot(instrument_uid: str, depth: int) -> dict[str, object]:
    assert instrument_uid == INSTRUMENT_UID
    assert depth == 1
    current = datetime.now(timezone.utc)
    return {
        "status": "ok",
        "last_price": {
            "status": "ok",
            "price": "98.1",
            "time": current.isoformat(),
            "age_seconds": 0,
        },
        "order_book": {
            "status": "ok",
            "time": current.isoformat(),
            "age_seconds": 0,
            "best_bid": {"price": "98", "quantity_lots": 100},
            "best_ask": {"price": "99", "quantity_lots": 50},
        },
        "dealer_session": False,
        "market_data_sources": {
            "last_price_type": "LAST_PRICE_EXCHANGE",
            "order_book_type": "ORDERBOOK_TYPE_EXCHANGE",
        },
        "trading_flag_consistency": {"status": "ok", "issues": []},
    }


def test_live_collector_calls_only_allowlisted_read_methods(monkeypatch) -> None:
    FakeOrders.calls = []
    FakeOperations.calls = []
    gateway_module.base._instrument_cache.clear()
    monkeypatch.setattr(gateway_module.base, "Client", FakeClient)
    safe_base = with_sale_request_object_services(gateway_module.base)

    payload = sale_capacity.get_sale_capacity_preview(
        base=safe_base,
        app_version="3.9.1",
        market_snapshot_loader=fake_market_snapshot,
        instrument_uid=INSTRUMENT_UID,
        price_basis="best_bid",
        quantity_lots=1,
    )

    assert payload["status"] == "ok"
    assert payload["account"]["masked_id"] == "***3118"
    assert payload["position_limits"]["position_lots"] == 5
    assert payload["open_orders"]["conflicting_sell_lots"] == 2
    assert payload["tax_basis"]["confirmed"] is False
    assert payload["trading_methods"] is False
    assert FakeOperations.calls == ["get_positions"]
    assert FakeOrders.calls == ["get_orders", "get_max_lots", "get_order_price"]


def test_live_collector_validates_quantity_and_price_basis() -> None:
    safe_base = with_sale_request_object_services(gateway_module.base)
    with pytest.raises(HTTPException) as quantity_error:
        sale_capacity.get_sale_capacity_preview(
            base=safe_base,
            app_version="3.9.1",
            market_snapshot_loader=fake_market_snapshot,
            instrument_uid=INSTRUMENT_UID,
            price_basis="best_bid",
            quantity_lots=0,
        )
    assert quantity_error.value.status_code == 422

    with pytest.raises(HTTPException) as basis_error:
        sale_capacity.get_sale_capacity_preview(
            base=safe_base,
            app_version="3.9.1",
            market_snapshot_loader=fake_market_snapshot,
            instrument_uid=INSTRUMENT_UID,
            price_basis="manual",
            quantity_lots=1,
        )
    assert basis_error.value.status_code == 422


def test_price_freshness_threshold_remains_120_seconds() -> None:
    assert sale_capacity.PRICE_FRESH_SECONDS == Decimal("120")
