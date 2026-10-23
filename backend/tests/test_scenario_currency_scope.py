"""Currency scenarios use the same denomination groups as their risk picker."""
from decimal import Decimal

import pytest

from backend.tests.test_volume_workspace import fixture, save
from backend.volume_contract import decimal


def denominated_snapshot(fixture):
    snapshot = fixture["snapshot"]
    denominations = {"aaa": "USD", "bbb": "EUR"}
    for position in snapshot["positions"]:
        if position["instrument_uid"] in denominations:
            position["metadata"]["instrument_currency"] = denominations[position["instrument_uid"]]
    save(fixture)
    return snapshot


@pytest.mark.parametrize("currency,uid,change,after", [
    ("USD", "aaa", "-8", "192"),
    ("EUR", "bbb", "-10", "190"),
    ("RUB", "cash:RUB", "-2", "198"),
])
def test_risk_currency_choice_selects_only_matching_instrument_denomination(fixture, currency, uid, change, after):
    denominated_snapshot(fixture)
    risks = fixture["client"].get("/workspace/risks").json()
    group = next(item for item in risks["concentrations"]
                 if item["direction"] == "currency" and item["id"] == currency)
    assert group["instrument_uids"] == [uid]
    response = fixture["client"].post("/workspace/risks/scenario", json={
        "currency": "RUB", "shocks": [{"axis": "currency", "id": group["id"], "percent": "-10"}],
    })
    assert response.status_code == 200, response.text
    result = response.json()
    assert [item["instrument_uid"] for item in result["positions"]] == group["instrument_uids"]
    assert decimal(result["estimated_change"]) == Decimal(change)
    assert decimal(result["estimated_after"]) == Decimal(after)
    assert result["estimated_change"]["currency"] == "RUB"
    assert result["complete"] is True
    assert result["is_forecast"] is False
    assert result["basis"] == "user_shocks_linear_valuation_no_fx_or_derivative_model"


@pytest.mark.parametrize("missing", [None, "usd", ""])
def test_unknown_denomination_is_not_assumed_unaffected_by_currency_scenario(fixture, missing):
    snapshot = denominated_snapshot(fixture)
    snapshot["positions"][-1]["metadata"]["instrument_currency"] = missing
    save(fixture)
    response = fixture["client"].post("/workspace/risks/scenario", json={
        "currency": "RUB", "shocks": [{"axis": "currency", "id": "USD", "percent": "-10"}],
    })
    assert response.status_code == 200, response.text
    result = response.json()
    assert decimal(result["estimated_change"]) == Decimal("-8")
    assert result["estimated_after"] is None
    assert result["uncovered_instrument_uids"] == ["bbb"]
    assert result["complete"] is False


def test_comparison_uses_distinct_denomination_groups_on_same_ruble_snapshot(fixture):
    denominated_snapshot(fixture)
    response = fixture["client"].post("/workspace/risks/scenarios/compare", json={
        "currency": "RUB", "scenarios": [
            {"id": "A", "title": "USD positions", "shocks": [{"axis": "currency", "id": "USD", "percent": "-10"}]},
            {"id": "B", "title": "EUR positions", "shocks": [{"axis": "currency", "id": "EUR", "percent": "-10"}]},
        ],
    })
    assert response.status_code == 200, response.text
    result = response.json()
    assert {row["result"]["snapshot_id"] for row in result["scenarios"]} == {result["snapshot_id"]}
    assert [decimal(row["result"]["estimated_after"]) for row in result["scenarios"]] == [Decimal("192"), Decimal("190")]
