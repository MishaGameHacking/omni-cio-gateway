"""Scenario calculations retain exact output precision and reject overflow."""
from copy import deepcopy
from decimal import Decimal, localcontext

import pytest

from backend.tests.test_volume_workspace import fixture, position, save, workspace


def shock(percent, *, axis="instrument", identifier="aaa"):
    return {"axis": axis, "id": identifier, "percent": percent}


@pytest.mark.parametrize("percent,expected", [("1e-40", "8e-41"), ("-1e-40", "-8e-41"), ("0e-40", "0")])
def test_scenario_keeps_calculated_precision_beyond_input_precision(fixture, percent, expected):
    response = fixture["client"].post("/workspace/risks/scenario", json={"shocks": [shock(percent)]})
    assert response.status_code == 200, response.text
    result = response.json()
    assert Decimal(result["estimated_change"]["amount"]) == Decimal(expected)
    assert Decimal(result["positions"][0]["estimated_change"]["amount"]) == Decimal(expected)
    with localcontext() as context:
        context.prec = 80
        assert Decimal(result["estimated_after"]["amount"]) == Decimal("200") + Decimal(expected)
    assert result["complete"] is True
    assert result["uncovered_instrument_uids"] == []


@pytest.mark.parametrize("count", [2, 3, 4])
def test_comparison_accepts_exact_small_changes_on_one_snapshot(fixture, count):
    cases = [("1e-40", "8e-41"), ("-1e-40", "-8e-41"), ("0", "0"), ("100", "80")][:count]
    scenarios = [{"id": str(index), "title": "Scenario " + str(index), "shocks": [shock(percent)]}
                 for index, (percent, _) in enumerate(cases)]
    response = fixture["client"].post("/workspace/risks/scenarios/compare", json={"scenarios": scenarios})
    assert response.status_code == 200, response.text
    result = response.json()
    assert {row["result"]["snapshot_id"] for row in result["scenarios"]} == {result["snapshot_id"]}
    assert [Decimal(row["result"]["estimated_change"]["amount"]) for row in result["scenarios"]] == [
        Decimal(expected) for _, expected in cases]
    assert all(row["result"]["complete"] for row in result["scenarios"])


def large_snapshot(fixture):
    dashboard = deepcopy(fixture["dashboard"])
    dashboard["totalValue"]["value"] = "1e24"
    for account, uid in zip(dashboard["accounts"], ("aaa", "bbb")):
        account["totalValue"]["value"] = "5e23"
        account["positions"] = [position(uid, "5e23")]
    save(fixture, workspace.normalize_snapshot(fixture["user"], dashboard))


@pytest.mark.parametrize("percent", ["1000", "200", "1"])
def test_unrepresentable_position_change_total_change_or_after_is_rejected(fixture, percent):
    large_snapshot(fixture)
    response = fixture["client"].post("/workspace/risks/scenario", json={
        "shocks": [shock(percent, axis="all", identifier="all")],
    })
    assert response.status_code == 422, response.text
    assert response.json()["detail"] == "scenario_result_out_of_range"


def test_small_known_changes_do_not_hide_an_unvalued_position(fixture):
    fixture["snapshot"]["positions"][-1]["value"] = None
    save(fixture)
    response = fixture["client"].post("/workspace/risks/scenario", json={
        "shocks": [shock("1e-40", axis="all", identifier="all")],
    })
    assert response.status_code == 200, response.text
    result = response.json()
    assert Decimal(result["estimated_change"]["amount"]) == Decimal("1e-40")
    assert result["covered_positions"] == 2
    assert result["complete"] is False
    assert result["estimated_after"] is None
    assert result["uncovered_instrument_uids"] == ["bbb"]
