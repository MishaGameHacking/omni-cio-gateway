import os

os.environ.setdefault("TINVEST_TOKEN", "regression-test-tinvest-token")
os.environ.setdefault("GATEWAY_API_KEY", "regression-test-gateway-key")
os.environ.setdefault(
    "RENDER_EXTERNAL_URL",
    "https://omni-cio-gateway.onrender.com",
)

from fastapi.testclient import TestClient

import app as gateway_module
from omni_cio.portfolio import cash_liquidity_v1 as cash_liquidity


def money(currency: str, units: int, nano: int = 0) -> dict[str, object]:
    return {
        "currency": currency,
        "units": str(units),
        "nano": nano,
    }


def test_builder_preserves_source_meanings_and_detects_difference() -> None:
    payload = cash_liquidity.build_cash_liquidity_snapshot(
        base=gateway_module.base,
        app_version="3.6.0",
        account={"masked_id": "***3118", "name": "ИИС"},
        positions_data={
            "money": [money("rub", 1000)],
            "blocked": [money("rub", 25)],
            "limits_loading_in_progress": False,
        },
        withdraw_limits_data={
            "money": [money("rub", 900)],
            "blocked": [money("rub", 20)],
            "blocked_guarantee": [money("rub", 5)],
        },
        positions_status="ok",
        withdraw_limits_status="ok",
        component_errors=[],
        retrieved_at="2026-07-27T07:00:00+00:00",
    )

    assert payload["status"] == "ok"
    assert payload["version"] == "3.6.0"
    assert payload["cash_mode"] == "single_currency"
    assert payload["buying_power"]["confirmed"] is False
    assert payload["trading_methods"] is False

    row = payload["cash_by_currency"][0]
    assert row["currency"] == "RUB"
    assert row["reported_money"] == "1000"
    assert row["positions_blocked"] == "25"
    assert row["withdrawable_money"] == "900"
    assert row["withdraw_blocked"] == "20"
    assert row["blocked_guarantee"] == "5"
    assert row["cash_difference"] == "100"
    assert row["cash_status"] == "source_difference"
    assert "reported_money_differs_from_withdrawable_money" in row[
        "discrepancy_reasons"
    ]
    assert "blocked_value_differs_between_sources" in row[
        "discrepancy_reasons"
    ]

    quality = payload["quality"]
    assert quality["positions_source_status"] == "ok"
    assert quality["withdraw_limits_source_status"] == "ok"
    assert quality["currencies_detected"] == 1
    assert quality["currencies_present_in_both_sources"] == 1
    assert quality["currencies_matched"] == 0
    assert quality["source_discrepancies"] == 1
    assert quality["buying_power_confirmed"] is False
    assert quality["complete"] is True
    assert quality["no_cross_currency_aggregation"] is True


def test_builder_returns_partial_when_one_source_fails() -> None:
    payload = cash_liquidity.build_cash_liquidity_snapshot(
        base=gateway_module.base,
        app_version="3.6.0",
        account={"masked_id": "***3118"},
        positions_data={"money": [money("rub", 1000)]},
        withdraw_limits_data=None,
        positions_status="ok",
        withdraw_limits_status="error",
        component_errors=[
            {
                "component": "withdraw_limits",
                "error": {"code": "TINVEST_GRPC_ERROR"},
            }
        ],
    )

    assert payload["status"] == "partial"
    assert payload["quality"]["complete"] is False
    assert payload["quality"]["source_discrepancies"] == 1
    assert payload["cash_by_currency"][0]["cash_status"] == "positions_only"
    assert payload["component_errors"][0]["component"] == "withdraw_limits"


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


class FakeOperations:
    def get_positions(self, *, account_id: str) -> dict[str, object]:
        assert account_id == "test-account-3118"
        return {
            "money": [money("rub", 1000)],
            "blocked": [money("rub", 0)],
            "limits_loading_in_progress": False,
        }

    def get_withdraw_limits(self, *, account_id: str) -> dict[str, object]:
        assert account_id == "test-account-3118"
        return {
            "money": [money("rub", 1000)],
            "blocked": [money("rub", 0)],
            "blocked_guarantee": [money("rub", 0)],
        }


class FakeClient:
    def __init__(self, token: str) -> None:
        assert token == "regression-test-tinvest-token"
        self.users = FakeUsers()
        self.operations = FakeOperations()

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None


def test_endpoint_is_protected_and_returns_compact_diagnostics(monkeypatch) -> None:
    monkeypatch.setattr(gateway_module.base, "Client", FakeClient)
    client = TestClient(gateway_module.app)

    unauthorized = client.get("/portfolio/cash-liquidity")
    assert unauthorized.status_code == 401

    response = client.get(
        "/portfolio/cash-liquidity",
        headers={"Authorization": "Bearer regression-test-gateway-key"},
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["version"] == gateway_module.APP_VERSION
    assert payload["account"]["masked_id"] == "***3118"
    assert payload["cash_by_currency"][0]["cash_status"] == "matched"
    assert payload["quality"]["currencies_matched"] == 1
    assert payload["quality"]["complete"] is True
    assert payload["quality"]["buying_power_confirmed"] is False
    assert payload["trading_methods"] is False
