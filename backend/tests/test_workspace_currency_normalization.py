"""Broker currency spellings survive collection and autonomous refreshes."""
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backend.tests.test_volume_workspace import activate, config, fixture, position
from backend import volume_monitor as monitor, volume_workspace as workspace
from backend.volume_contract import decimal, source


def persist_broker_currencies(fixture, currency):
    dashboard = deepcopy(fixture["dashboard"])
    metadata = {
        uid: {"currency": value, "_source": source("GetInstrumentBy", uid, dashboard["asOf"])}
        for uid, value in (("aaa", currency), ("bbb", "EUR"))
    }
    snapshot = workspace.normalize_snapshot(fixture["user"], dashboard, metadata)
    workspace.persist(fixture["user"], snapshot)
    return snapshot, metadata


def risk_currency_groups(fixture):
    response = fixture["client"].get("/workspace/risks")
    assert response.status_code == 200, response.text
    result = response.json()
    coverage = next(row for row in result["coverage"] if row["direction"] == "currency")
    groups = {row["id"]: row for row in result["concentrations"] if row["direction"] == "currency"}
    return coverage, groups


@pytest.mark.parametrize("currency", ["usd", "UsD", "USD"])
def test_broker_currency_case_is_normalized_before_risk_grouping(fixture, currency):
    snapshot, raw_metadata = persist_broker_currencies(fixture, currency)
    coverage, groups = risk_currency_groups(fixture)
    assert coverage["state"] == "available"
    assert groups["USD"]["instrument_uids"] == ["aaa"]
    assert decimal(groups["USD"]["value"]) == Decimal("80")
    assert groups["EUR"]["instrument_uids"] == ["bbb"]
    assert groups["RUB"]["instrument_uids"] == ["cash:RUB"]
    assert snapshot["positions"][0]["metadata"]["instrument_currency"] == "USD"
    assert raw_metadata["aaa"]["currency"] == currency
    assert raw_metadata["aaa"]["_source"]["id"] in groups["USD"]["source_ids"]

    response = fixture["client"].post("/workspace/risks/scenario", json={
        "currency": "RUB", "shocks": [{"axis": "currency", "id": "USD", "percent": "-10"}],
    })
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["complete"] is True
    assert decimal(result["estimated_after"]) == Decimal("192")
    assert result["estimated_after"]["currency"] == "RUB"
    assert [row["instrument_uid"] for row in result["positions"]] == ["aaa"]


@pytest.mark.parametrize("currency", [None, "", "US", "USDD", "US1", "u\u017fd", 123])
def test_invalid_broker_currency_remains_unknown(fixture, currency):
    persist_broker_currencies(fixture, currency)
    coverage, groups = risk_currency_groups(fixture)
    assert coverage["state"] == "partial"
    assert coverage["missing_instrument_uids"] == ["aaa"]
    assert set(groups) == {"RUB", "EUR"}
    response = fixture["client"].post("/workspace/risks/scenario", json={
        "currency": "RUB", "shocks": [{"axis": "currency", "id": "EUR", "percent": "-10"}],
    })
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["complete"] is False
    assert result["estimated_after"] is None
    assert result["uncovered_instrument_uids"] == ["aaa"]


def test_monitor_refresh_preserves_known_denominations_and_currency_breaches(fixture):
    before, metadata = persist_broker_currencies(fixture, "USD")
    activate(fixture, config(currency=30))
    updated = monitor.ingest(fixture["user"], fixture["dashboard"], datetime.now(timezone.utc))
    coverage, groups = risk_currency_groups(fixture)
    assert coverage["state"] == "available"
    assert groups["USD"]["instrument_uids"] == ["aaa"]
    assert groups["EUR"]["instrument_uids"] == ["bbb"]
    assert metadata["aaa"]["_source"]["id"] in groups["USD"]["source_ids"]
    assert updated["snapshot"]["positions"][0]["metadata"]["source"] == before["positions"][0]["metadata"]["source"]
    assert {row["id"] for row in updated["breaches"] if row["direction"] == "currency"} == {"USD", "EUR"}
    response = fixture["client"].post("/workspace/risks/scenario", json={
        "currency": "RUB", "shocks": [{"axis": "currency", "id": "USD", "percent": "-10"}],
    })
    assert response.status_code == 200, response.text
    assert response.json()["complete"] is True
    assert decimal(response.json()["estimated_after"]) == Decimal("192")


@pytest.mark.parametrize("new_account_first", [False, True])
def test_same_instrument_on_new_account_keeps_its_metadata_and_account_positions(fixture, new_account_first):
    _, metadata = persist_broker_currencies(fixture, "USD")
    dashboard = deepcopy(fixture["dashboard"])
    additional = position("aaa", "40", quantity="5")
    additional.update(blocked=True, blockedQuantity="2")
    dashboard["accounts"][1]["positions"].append(additional)
    dashboard["accounts"][1]["totalValue"]["value"] = "140"
    dashboard["totalValue"]["value"] = "240"
    if new_account_first:
        dashboard["accounts"].reverse()

    updated = monitor.ingest(fixture["user"], dashboard, datetime.now(timezone.utc))
    coverage, groups = risk_currency_groups(fixture)
    assert coverage["state"] == "available"
    assert decimal(groups["USD"]["value"]) == Decimal("120")
    assert groups["USD"]["instrument_uids"] == ["aaa"]
    assert metadata["aaa"]["_source"]["id"] in groups["USD"]["source_ids"]
    positions = {row["account_id"]: row for row in updated["snapshot"]["positions"] if row["instrument_uid"] == "aaa"}
    assert positions["owned-account-a"]["quantity"] == "10"
    assert positions["owned-account-a"]["blocked"] is False
    assert positions["owned-account-a"]["blocked_quantity"] == "0"
    assert decimal(positions["owned-account-a"]["value"]) == Decimal("80")
    assert positions["owned-account-b"]["quantity"] == "5"
    assert positions["owned-account-b"]["blocked"] is True
    assert positions["owned-account-b"]["blocked_quantity"] == "2"
    assert decimal(positions["owned-account-b"]["value"]) == Decimal("40")
    assert all(row["metadata"]["instrument_currency"] == "USD" for row in positions.values())

    response = fixture["client"].post("/workspace/risks/scenario", json={
        "currency": "RUB", "shocks": [{"axis": "currency", "id": "USD", "percent": "-10"}],
    })
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["complete"] is True
    assert decimal(result["estimated_change"]) == Decimal("-12")
    assert decimal(result["estimated_after"]) == Decimal("228")
    assert {row["account_id"] for row in result["positions"]} == {"owned-account-a", "owned-account-b"}
