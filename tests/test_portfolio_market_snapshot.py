import os
from decimal import Decimal

os.environ.setdefault("TINVEST_TOKEN", "regression-test-tinvest-token")
os.environ.setdefault("GATEWAY_API_KEY", "regression-test-gateway-key")
os.environ.setdefault(
    "RENDER_EXTERNAL_URL",
    "https://omni-cio-gateway.onrender.com",
)

from fastapi.testclient import TestClient

import app as gateway_module
from omni_cio.portfolio import market_source_v1 as portfolio_market


client = TestClient(gateway_module.app)
AUTH_HEADERS = {"Authorization": "Bearer regression-test-gateway-key"}


def test_share_valuation_uses_instrument_units_not_lots() -> None:
    valuation, totals = portfolio_market.calculate_position_valuation(
        gateway_module.base,
        Decimal("3"),
        {
            "instrument_kind": "INSTRUMENT_TYPE_SHARE",
            "currency": "RUB",
            "lot": 10,
        },
        {"status": "ok", "price": "100"},
        {
            "status": "ok",
            "best_bid": {"price": "99"},
            "best_ask": {"price": "101"},
        },
    )

    assert valuation["basis"] == "quantity_units_times_price_per_instrument"
    assert valuation["values"] == {
        "last_price": "300",
        "best_bid": "297",
        "best_ask": "303",
    }
    assert totals["last_price"] == Decimal("300")


def test_bond_valuation_converts_points_and_adds_accrued_interest() -> None:
    valuation, totals = portfolio_market.calculate_position_valuation(
        gateway_module.base,
        Decimal("2"),
        {
            "instrument_kind": "INSTRUMENT_TYPE_BOND",
            "currency": "RUB",
            "nominal": {"amount": "1000", "currency": "RUB"},
            "accrued_interest": {"amount": "12.5", "currency": "RUB"},
        },
        {"status": "ok", "price": "95"},
        {
            "status": "ok",
            "best_bid": {"price": "94"},
            "best_ask": {"price": "96"},
        },
    )

    assert valuation["basis"] == (
        "quantity_times_nominal_times_price_percent_plus_accrued_interest"
    )
    assert valuation["clean_values"]["last_price"] == "1900"
    assert valuation["values"]["last_price"] == "1925"
    assert totals["best_bid"] == Decimal("1905")
    assert totals["best_ask"] == Decimal("1945")


def test_cash_balances_keep_blocked_money_separate() -> None:
    balances = portfolio_market.build_cash_balances(
        gateway_module.base,
        {
            "money": [
                {"currency": "rub", "units": "1000", "nano": 0},
                {"currency": "usd", "units": "5", "nano": 500000000},
            ],
            "blocked": [
                {"currency": "rub", "units": "100", "nano": 0},
            ],
        },
    )

    assert balances == [
        {
            "currency": "RUB",
            "reported_money": "1000",
            "reported_blocked": "100",
        },
        {
            "currency": "USD",
            "reported_money": "5.5",
            "reported_blocked": "0",
        },
    ]


def test_endpoint_returns_partial_failure_tolerant_portfolio_totals(
    monkeypatch,
) -> None:
    fake_enriched = {
        "status": "ok",
        "version": "3.5.0",
        "retrieved_at": "2026-07-27T05:00:00+00:00",
        "account": {
            "masked_id": "***3118",
            "name": "ИИС",
            "status": "ACCOUNT_STATUS_OPEN",
            "access_level": "ACCOUNT_ACCESS_LEVEL_READ_ONLY",
        },
        "positions": {
            "money": [{"currency": "rub", "units": "1000", "nano": 0}],
            "blocked": [{"currency": "rub", "units": "0", "nano": 0}],
        },
        "enriched_portfolio_positions": [
            {
                "instrument_uid": "uid-share",
                "position_uid": "position-share",
                "quantity": {"units": "2", "nano": 0},
                "enrichment_status": "resolved",
                "identity_check": {"overall": "PASS"},
                "instrument_metadata": {
                    "name": "Тестовая акция",
                    "ticker": "TEST",
                    "figi": "TESTFIGI",
                    "uid": "uid-share",
                    "position_uid": "position-share",
                    "class_code": "TQBR",
                    "instrument_kind": "INSTRUMENT_TYPE_SHARE",
                    "instrument_type": "share",
                    "lot": 10,
                    "currency": "rub",
                },
            },
            {
                "instrument_uid": "uid-rub",
                "quantity": {"units": "1000", "nano": 0},
                "enrichment_status": "resolved",
                "instrument_metadata": {
                    "name": "Российский рубль",
                    "ticker": "RUB000UTSTOM",
                    "uid": "uid-rub",
                    "instrument_kind": "INSTRUMENT_TYPE_CURRENCY",
                    "instrument_type": "currency",
                    "currency": "rub",
                    "lot": 1,
                },
            },
        ],
        "enrichment_quality": {
            "position_occurrences": 2,
            "unique_instrument_references": 2,
            "references_resolved": 2,
            "references_unresolved": 0,
            "cache_hits": 0,
            "instrument_api_calls": 2,
            "identity_conflicts": 0,
        },
    }

    class FakeMarketData:
        def get_last_prices(self, instrument_id):
            assert instrument_id == ["uid-share"]
            return {
                "last_prices": [
                    {
                        "instrument_uid": "uid-share",
                        "figi": "TESTFIGI",
                        "price": {"units": "100", "nano": 0},
                        "time": "2026-07-27T05:00:00+00:00",
                        "last_price_type": "LAST_PRICE_EXCHANGE",
                    }
                ]
            }

        def get_trading_status(self, instrument_id):
            assert instrument_id == "uid-share"
            return {
                "instrument_uid": "uid-share",
                "trading_status": "SECURITY_TRADING_STATUS_NORMAL_TRADING",
                "limit_order_available_flag": True,
                "market_order_available_flag": True,
                "api_trade_available_flag": True,
                "bestprice_order_available_flag": False,
                "only_best_price": False,
            }

        def get_order_book(self, instrument_id, depth):
            assert instrument_id == "uid-share"
            assert depth == 1
            return {
                "instrument_uid": "uid-share",
                "figi": "TESTFIGI",
                "depth": 1,
                "orderbook_ts": "2026-07-27T05:00:00+00:00",
                "order_book_type": "ORDERBOOK_TYPE_EXCHANGE",
                "bids": [{"price": {"units": "99", "nano": 0}, "quantity": 4}],
                "asks": [{"price": {"units": "101", "nano": 0}, "quantity": 3}],
            }

    class FakeClient:
        def __init__(self, token):
            assert token == "regression-test-tinvest-token"
            self.market_data = FakeMarketData()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(gateway_module.base, "enriched_snapshot", lambda: fake_enriched)
    monkeypatch.setattr(gateway_module.base, "Client", FakeClient)

    response = client.get(
        "/portfolio/market-snapshot?depth=1&max_instruments=10",
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] == "ok"
    assert payload["version"] == gateway_module.APP_VERSION
    assert payload["trading_methods"] is False
    assert payload["quality"]["cash_like_portfolio_positions"] == 1
    assert payload["quality"]["unique_market_instruments"] == 1
    assert payload["quality"]["last_price_batch_calls"] == 1

    assert payload["totals_by_currency"] == [
        {
            "currency": "RUB",
            "cash_reported": "1000",
            "cash_blocked_reported": "0",
            "securities_last_price": "200",
            "securities_best_bid": "198",
            "securities_best_ask": "202",
            "portfolio_last_price": "1200",
            "portfolio_best_bid": "1198",
            "portfolio_best_ask": "1202",
            "positions_valued_last_price": 1,
            "positions_valued_best_bid": 1,
            "positions_valued_best_ask": 1,
        }
    ]
