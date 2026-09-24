import os

os.environ.setdefault("TINVEST_TOKEN", "regression-test-tinvest-token")
os.environ.setdefault("GATEWAY_API_KEY", "regression-test-gateway-key")
os.environ.setdefault(
    "RENDER_EXTERNAL_URL",
    "https://omni-cio-gateway.onrender.com",
)

from fastapi.testclient import TestClient

import app as gateway_module
from omni_cio.analytics import portfolio_source_v1 as portfolio_analytics


client = TestClient(gateway_module.app)
AUTH_HEADERS = {"Authorization": "Bearer regression-test-gateway-key"}


def cash_only_snapshot() -> dict:
    return {
        "status": "ok",
        "version": "3.5.0",
        "retrieved_at": "2026-07-27T06:00:00+00:00",
        "source_snapshot_retrieved_at": "2026-07-27T05:59:59+00:00",
        "account": {
            "masked_id": "***3118",
            "name": "ИИС",
            "access_level": "ACCOUNT_ACCESS_LEVEL_READ_ONLY",
        },
        "cash_balances": [
            {
                "currency": "RUB",
                "reported_money": "1000",
                "reported_blocked": "0",
            }
        ],
        "portfolio_positions": [],
        "quality": {
            "component_errors": 0,
            "market_instruments_skipped_by_limit": 0,
        },
        "enrichment_quality": {"identity_conflicts": 0},
        "trading_methods": False,
    }


def test_cash_only_mode_is_complete_and_does_not_invent_market_positions() -> None:
    payload = portfolio_analytics.build_portfolio_analytics(
        base=gateway_module.base,
        app_version="3.5.0",
        snapshot=cash_only_snapshot(),
        valuation_basis="last_price",
        top_n=5,
    )

    assert payload["status"] == "ok"
    assert payload["portfolio_mode"] == "cash_only"
    assert payload["currency_mode"] == "single_currency"
    assert payload["position_weights"] == []
    assert payload["summary_by_currency"] == [
        {
            "currency": "RUB",
            "cash_value": "1000",
            "securities_value": "0",
            "portfolio_value": "1000",
            "cash_share_percent": "100",
            "securities_share_percent": "0",
            "market_position_count": 0,
            "valued_position_count": 0,
            "unvalued_position_count": 0,
            "valuation_coverage_percent": "100",
            "top_n": 5,
            "top_n_concentration_percent": "0",
            "top_n_securities_concentration_percent": "unavailable",
        }
    ]
    assert payload["quality"]["complete_for_selected_basis"] is True
    assert payload["quality"]["no_cross_currency_aggregation"] is True


def test_weights_and_concentration_are_calculated_separately_by_currency() -> None:
    snapshot = {
        "status": "ok",
        "version": "3.5.0",
        "retrieved_at": "2026-07-27T06:00:00+00:00",
        "account": {"masked_id": "***3118"},
        "cash_balances": [
            {"currency": "RUB", "reported_money": "1000", "reported_blocked": "0"},
            {"currency": "USD", "reported_money": "10", "reported_blocked": "0"},
        ],
        "portfolio_positions": [
            {
                "instrument": {
                    "name": "Акция A",
                    "ticker": "AAA",
                    "uid": "uid-a",
                    "instrument_kind": "INSTRUMENT_TYPE_SHARE",
                    "currency": "RUB",
                },
                "quantity_units": "3",
                "valuation": {
                    "status": "ok",
                    "currency": "RUB",
                    "values": {
                        "last_price": "300",
                        "best_bid": "297",
                        "best_ask": "303",
                    },
                },
            },
            {
                "instrument": {
                    "name": "Облигация B",
                    "ticker": "BBB",
                    "uid": "uid-b",
                    "instrument_kind": "INSTRUMENT_TYPE_BOND",
                    "currency": "RUB",
                },
                "quantity_units": "1",
                "valuation": {
                    "status": "ok",
                    "currency": "RUB",
                    "values": {
                        "last_price": "200",
                        "best_bid": "198",
                        "best_ask": "202",
                    },
                },
            },
            {
                "instrument": {
                    "name": "ETF C",
                    "ticker": "CCC",
                    "uid": "uid-c",
                    "instrument_kind": "INSTRUMENT_TYPE_ETF",
                    "currency": "USD",
                },
                "quantity_units": "2",
                "valuation": {
                    "status": "ok",
                    "currency": "USD",
                    "values": {
                        "last_price": "40",
                        "best_bid": "39",
                        "best_ask": "41",
                    },
                },
            },
        ],
        "quality": {
            "component_errors": 0,
            "market_instruments_skipped_by_limit": 0,
        },
        "enrichment_quality": {"identity_conflicts": 0},
    }

    payload = portfolio_analytics.build_portfolio_analytics(
        base=gateway_module.base,
        app_version="3.5.0",
        snapshot=snapshot,
        valuation_basis="last_price",
        top_n=2,
    )

    rub = next(
        row for row in payload["summary_by_currency"] if row["currency"] == "RUB"
    )
    usd = next(
        row for row in payload["summary_by_currency"] if row["currency"] == "USD"
    )

    assert rub["portfolio_value"] == "1500"
    assert rub["cash_share_percent"] == "66.666667"
    assert rub["securities_share_percent"] == "33.333333"
    assert rub["top_n_concentration_percent"] == "33.333333"
    assert rub["top_n_securities_concentration_percent"] == "100"
    assert rub["largest_position"]["instrument"]["ticker"] == "AAA"
    assert rub["largest_position"]["portfolio_weight_percent"] == "20"

    assert usd["portfolio_value"] == "50"
    assert usd["cash_share_percent"] == "20"
    assert usd["securities_share_percent"] == "80"

    rub_weights = [
        row for row in payload["position_weights"] if row["currency"] == "RUB"
    ]
    assert [row["rank_within_currency"] for row in rub_weights] == [1, 2]
    assert [row["portfolio_weight_percent"] for row in rub_weights] == [
        "20",
        "13.333333",
    ]
    assert all(
        row["cross_currency_share_percent"] == "not_calculated_without_fx_conversion"
        for row in payload["currency_exposure"]
    )


def test_unvalued_position_makes_analytics_partial() -> None:
    snapshot = cash_only_snapshot()
    snapshot["portfolio_positions"] = [
        {
            "instrument": {
                "name": "Без цены",
                "ticker": "NOPRICE",
                "uid": "uid-no-price",
                "instrument_kind": "INSTRUMENT_TYPE_SHARE",
                "currency": "RUB",
            },
            "quantity_units": "1",
            "valuation": {
                "status": "unavailable",
                "currency": "RUB",
                "values": {},
            },
        }
    ]

    payload = portfolio_analytics.build_portfolio_analytics(
        base=gateway_module.base,
        app_version="3.5.0",
        snapshot=snapshot,
        valuation_basis="last_price",
        top_n=5,
    )

    assert payload["status"] == "partial"
    assert payload["portfolio_mode"] == "mixed"
    assert payload["quality"]["valued_positions"] == 0
    assert payload["quality"]["unvalued_positions"] == 1
    assert payload["quality"]["valuation_coverage_percent"] == "0"
    assert payload["quality"]["complete_for_selected_basis"] is False


def test_analytics_endpoint_uses_one_source_snapshot_and_remains_read_only(
    monkeypatch,
) -> None:
    calls = []

    def fake_snapshot(**kwargs):
        calls.append(kwargs)
        return cash_only_snapshot()

    monkeypatch.setattr(
        gateway_module.portfolio_market_engine,
        "get_portfolio_market_snapshot",
        fake_snapshot,
    )

    response = client.get(
        "/portfolio/analytics?valuation_basis=last_price&top_n=5&depth=1&max_instruments=20",
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    payload = response.json()

    assert len(calls) == 1
    assert calls[0]["depth"] == 1
    assert calls[0]["max_instruments"] == 20
    assert payload["version"] == gateway_module.APP_VERSION
    assert payload["portfolio_mode"] == "cash_only"
    assert payload["trading_methods"] is False
