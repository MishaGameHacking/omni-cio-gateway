import os

os.environ.setdefault("TINVEST_TOKEN", "regression-test-tinvest-token")
os.environ.setdefault("GATEWAY_API_KEY", "regression-test-gateway-key")
os.environ.setdefault(
    "RENDER_EXTERNAL_URL",
    "https://omni-cio-gateway.onrender.com",
)

from fastapi.testclient import TestClient

import app as gateway_module
from omni_cio.pretrade import purchase_capacity_v1 as purchase_capacity


INSTRUMENT_UID = "e6123145-9665-43e0-8413-cd61b8aa9b13"


def quotation(units: int, nano: int = 0) -> dict[str, object]:
    return {"units": str(units), "nano": nano}


def money(currency: str, units: int, nano: int = 0) -> dict[str, object]:
    return {
        "currency": currency,
        "units": str(units),
        "nano": nano,
    }


def resolved_instrument() -> dict[str, object]:
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
            "name": "Сбер Банк",
            "ticker": "SBER",
            "isin": "RU0009029540",
            "figi": "BBG004730N88",
            "uid": INSTRUMENT_UID,
            "position_uid": "41eb2102-5333-4713-bf15-72b204c4bf7b",
            "class_code": "TQBR",
            "instrument_type": "share",
            "instrument_kind": "INSTRUMENT_TYPE_SHARE",
            "lot": 1,
            "currency": "rub",
            "api_trade_available_flag": True,
        },
    }


def test_builder_uses_only_own_funds_and_preliminary_total() -> None:
    payload = purchase_capacity.build_purchase_capacity_preview(
        base=gateway_module.base,
        app_version="3.7.1",
        account={"masked_id": "***3118", "name": "ИИС"},
        instrument_uid=INSTRUMENT_UID,
        instrument_resolution=resolved_instrument(),
        price_basis="best_ask",
        quantity_lots=3,
        price_info={
            "status": "ok",
            "basis": "best_ask",
            "source": "T-Invest GetOrderBook best ask",
            "price": "269.33",
            "source_time": "2026-07-27T08:00:00+00:00",
            "age_seconds": "5",
            "freshness": {
                "status": "fresh",
                "source_time": "2026-07-27T08:00:00+00:00",
                "age_seconds": "5",
                "fresh_threshold_seconds": "120",
            },
        },
        max_lots_data={
            "currency": "rub",
            "buy_limits": {
                "buy_money_amount": quotation(1000),
                "buy_max_lots": 3,
                "buy_max_market_lots": 3,
            },
            "buy_margin_limits": {
                "buy_money_amount": quotation(5000),
                "buy_max_lots": 18,
                "buy_max_market_lots": 18,
            },
        },
        order_price_data={
            "lots_requested": 3,
            "initial_order_amount": money("rub", 807, 990_000_000),
            "total_order_amount": money("rub", 809, 200_000_000),
            "executed_commission": money("rub", 1, 210_000_000),
            "service_commission": money("rub", 0),
            "deal_commission": money("rub", 0),
        },
        component_statuses={
            "market_snapshot": "ok",
            "instrument_reference": "ok",
            "max_lots": "ok",
            "order_price": "ok",
        },
        component_errors=[],
        market_snapshot={
            "dealer_session": False,
            "market_data_sources": {
                "last_price_type": "LAST_PRICE_EXCHANGE",
                "order_book_type": "ORDERBOOK_TYPE_EXCHANGE",
            },
            "trading_flag_consistency": {
                "status": "ok",
                "issues": [],
                "raw_fields_preserved": True,
            },
        },
        retrieved_at="2026-07-27T08:00:05+00:00",
    )

    assert payload["status"] == "ok"
    assert payload["version"] == "3.7.1"
    assert payload["account"]["masked_id"] == "***3118"
    assert payload["own_funds"]["buy_money_amount"] == "1000"
    assert payload["own_funds"]["buy_max_lots"] == 3
    assert payload["margin"]["included"] is False
    assert payload["margin"]["values_returned_but_not_used"] is True
    assert payload["affordable"] == "yes"
    assert payload["affordability_confirmed"] is True
    assert payload["remaining_cash_estimate"] == "190.8"
    assert payload["order_preview"]["total_order_amount"] == {
        "amount": "809.2",
        "currency": "RUB",
    }
    assert payload["quality"]["margin_ignored"] is True
    assert payload["quality"]["no_order_created"] is True
    assert payload["complete"] is True
    assert payload["trading_methods"] is False


def test_manual_price_validation_is_strict() -> None:
    selected = purchase_capacity.select_price(
        base=gateway_module.base,
        price_basis="manual",
        manual_price="269.33",
        market_snapshot=None,
    )
    assert selected["price"] == "269.33"
    assert selected["freshness"]["status"] == "manual_input"


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


class FakeOrders:
    calls: list[str] = []

    def get_max_lots(self, **kwargs) -> dict[str, object]:
        assert kwargs["account_id"] == "test-account-3118"
        assert kwargs["instrument_id"] == INSTRUMENT_UID
        assert kwargs["price"] is not None
        self.calls.append("get_max_lots")
        return {
            "currency": "rub",
            "buy_limits": {
                "buy_money_amount": quotation(1000),
                "buy_max_lots": 3,
                "buy_max_market_lots": 3,
            },
            "buy_margin_limits": {
                "buy_money_amount": quotation(5000),
                "buy_max_lots": 18,
                "buy_max_market_lots": 18,
            },
        }

    def get_order_price(self, **kwargs) -> dict[str, object]:
        assert kwargs["account_id"] == "test-account-3118"
        assert kwargs["instrument_id"] == INSTRUMENT_UID
        assert kwargs["quantity"] == 3
        assert kwargs["price"] is not None
        assert kwargs["direction"] is not None
        self.calls.append("get_order_price")
        return {
            "lots_requested": 3,
            "initial_order_amount": money("rub", 807, 990_000_000),
            "total_order_amount": money("rub", 809, 200_000_000),
            "executed_commission": money("rub", 1, 210_000_000),
        }


class FakeClient:
    def __init__(self, token: str) -> None:
        assert token == "regression-test-tinvest-token"
        self.users = FakeUsers()
        self.instruments = FakeInstruments()
        self.orders = FakeOrders()

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None


def fake_market_snapshot(instrument_uid: str, depth: int) -> dict[str, object]:
    assert instrument_uid == INSTRUMENT_UID
    assert depth == 1
    return {
        "status": "ok",
        "last_price": {
            "status": "ok",
            "price": "269.32",
            "time": "2026-07-27T08:00:00+00:00",
            "age_seconds": 5,
        },
        "order_book": {
            "status": "ok",
            "time": "2026-07-27T08:00:04+00:00",
            "age_seconds": 1,
            "best_bid": {"price": "269.32", "quantity_lots": 100},
            "best_ask": {"price": "269.33", "quantity_lots": 50},
        },
        "dealer_session": False,
        "market_data_sources": {
            "last_price_type": "LAST_PRICE_EXCHANGE",
            "order_book_type": "ORDERBOOK_TYPE_EXCHANGE",
        },
        "trading_flag_consistency": {
            "status": "ok",
            "issues": [],
            "raw_fields_preserved": True,
        },
    }


def test_endpoint_is_protected_and_calls_only_read_methods(monkeypatch) -> None:
    FakeOrders.calls = []
    gateway_module.base._instrument_cache.clear()
    monkeypatch.setattr(gateway_module.base, "Client", FakeClient)
    monkeypatch.setattr(
        gateway_module.legacy,
        "market_snapshot_v350",
        fake_market_snapshot,
    )
    client = TestClient(gateway_module.app)

    unauthorized = client.get(
        "/portfolio/purchase-capacity",
        params={
            "instrument_uid": INSTRUMENT_UID,
            "price_basis": "best_ask",
            "quantity_lots": 3,
        },
    )
    assert unauthorized.status_code == 401

    response = client.get(
        "/portfolio/purchase-capacity",
        params={
            "instrument_uid": INSTRUMENT_UID,
            "price_basis": "best_ask",
            "quantity_lots": 3,
        },
        headers={"Authorization": "Bearer regression-test-gateway-key"},
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["version"] == gateway_module.APP_VERSION
    assert payload["account"]["masked_id"] == "***3118"
    assert payload["instrument"]["ticker"] == "SBER"
    assert payload["affordable"] == "yes"
    assert payload["remaining_cash_estimate"] == "190.8"
    assert payload["commission_summary"]["canonical_source"] == "executed_commission"
    assert payload["commission_summary"]["double_count_protection"] is True
    assert payload["currency_consistency"]["status"] == "ok"
    assert payload["limit_summary"]["selected_limit_field"] == "buy_max_lots"
    assert payload["calculation_checks"]["initial_order_amount"]["status"] == "passed"
    assert payload["calculation_checks"]["total_order_amount"]["status"] == "passed"
    assert payload["calculation_checks"]["remaining_cash"]["status"] == "passed"
    assert payload["integrity_status"] == "ok"
    assert payload["quality"]["no_order_created"] is True
    assert payload["quality"]["commission_double_count_protected"] is True
    assert payload["trading_methods"] is False
    assert FakeOrders.calls == ["get_max_lots", "get_order_price"]
