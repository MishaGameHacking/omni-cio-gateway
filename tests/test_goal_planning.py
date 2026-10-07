"""Goal scenarios expose conditional assumptions and distinguish income from capital."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from test_workspace_api import GOAL, HEADERS, OTHER, OWNER
from test_workspace_api import workspace_http as workspace_http
from test_workspace_postgres import DATABASE_URL, goal_document, user
from test_workspace_postgres import workspace_database as workspace_database

from omnicio.db import Database
from omnicio.goal_planning import goal_forecast, normalize_goal_plan
from omnicio.portfolio_store import SettingsVersionConflict
from omnicio.workspace_store import WorkspaceNotFound, WorkspaceStore


def plan(**changes: Any) -> dict[str, Any]:
    return {
        "monthly_contribution_rub": "10000", "monthly_income_rub": "1000",
        "annual_return_percent": "0", "annual_volatility_percent": "0",
        "annual_inflation_percent": "0", "target_in_today_money": True, "seed": 42, **changes,
    }


def goal(**changes: Any) -> dict[str, Any]:
    return {"kind": "capital", "progress": {"amount_rub": "100000"},
            "target_amount_rub": "220000", "target_date": "2027-01-01", **changes}


def test_zero_return_has_exact_linear_growth_and_required_contribution() -> None:
    result = goal_forecast(goal(), plan(), today=date(2026, 1, 1))
    assert result["status"] == "available"
    assert result["projected_amount_rub"] == "220000.00"
    assert result["required_monthly_rub"] == "10000.00"
    assert result["deterministic_months_to_target"] == 12
    assert result["simulation"] is None


def test_net_geometric_growth_and_inflation_are_separate() -> None:
    result = goal_forecast(goal(), plan(annual_return_percent="10", annual_inflation_percent="10",
                                        monthly_contribution_rub="0"), today=date(2026, 1, 1))
    assert result["projected_amount_rub"] == "110000.00"
    assert result["inflation_adjusted_target_rub"] == "242000.00"
    assert Decimal(result["required_monthly_rub"]) > 10000


def test_income_goal_never_counts_capital_contributions_or_appreciation_as_income() -> None:
    result = goal_forecast(goal(kind="income"), plan(annual_return_percent="100",
                           annual_volatility_percent="30"), today=date(2026, 1, 1))
    assert result["method"] == "monthly_income_accumulation_v1"
    assert result["projected_amount_rub"] == "112000.00"
    assert result["required_monthly_kind"] == "income"
    assert result["simulation"] is None


def test_model_probability_is_reproducible_conditional_and_has_sampling_interval() -> None:
    document = plan(annual_return_percent="5", annual_volatility_percent="25")
    first = goal_forecast(goal(), document, today=date(2026, 1, 1))
    second = goal_forecast(goal(), document, today=date(2026, 1, 1))
    assert first == second
    assert first["assumptions_source"] == "user_supplied"
    assert first["future_success_guaranteed"] is False
    simulation = first["simulation"]
    probability = float(simulation["conditional_probability_percent"])
    assert 0 < probability < 100
    low, high = simulation["sampling_interval_95_percent"]
    assert low < probability < high
    percentiles = simulation["terminal_percentiles_rub"]
    assert Decimal(percentiles["10"]) < Decimal(percentiles["50"]) < Decimal(percentiles["90"])


@pytest.mark.parametrize("changes", [
    {"annual_return_percent": "-100"}, {"annual_volatility_percent": "NaN"},
    {"monthly_income_rub": "-1"}, {"seed": True}, {"seed": 2**32},
    {"target_in_today_money": "true"}, {"extra": "ignored"},
])
def test_invalid_or_unbounded_assumptions_are_rejected(changes: dict[str, Any]) -> None:
    document = plan(**changes)
    with pytest.raises(ValueError):
        normalize_goal_plan(document)


@pytest.mark.parametrize("changes,reason", [
    ({"progress": {"amount_rub": None}}, "goal_progress_unavailable"),
    ({"target_date": None}, "goal_target_date_required"),
    ({"target_date": "2025-01-01"}, "goal_plan_horizon_out_of_range"),
    ({"target_date": "2090-01-01"}, "goal_plan_horizon_out_of_range"),
])
def test_insufficient_basis_never_produces_a_scenario(
    changes: dict[str, Any], reason: str,
) -> None:
    result = goal_forecast(goal(**changes), plan(), today=date(2026, 1, 1))
    assert result["status"] == "unavailable"
    assert result["reason"] == reason


def test_goal_plan_http_requires_both_versions_and_current_profile(
    workspace_http: tuple[TestClient, Mock, Mock, Mock],
) -> None:
    client, _, store, database = workspace_http
    store.goal_plan.return_value = {"version": 1, "document": plan()}
    store.save_goal_plan.return_value = {"version": 2, "document": plan()}
    assert client.get(f"/api/goals/{GOAL}/plan", headers=HEADERS).status_code == 200
    store.goal_plan.assert_called_once_with(OWNER.id, GOAL)
    body = {"document": plan(), "expected_version": 1, "expected_goal_version": 3}
    for invalid in ({**body, "expected_goal_version": True},
                    {**body, "user_id": str(OTHER.id)},
                    {key: value for key, value in body.items() if key != "expected_goal_version"}):
        assert client.put(f"/api/goals/{GOAL}/plan", json=invalid,
                          headers=HEADERS).status_code == 422
    assert client.put(f"/api/goals/{GOAL}/plan", json=body).status_code == 403
    store.save_goal_plan.assert_not_called()
    saved = client.put(f"/api/goals/{GOAL}/plan", json=body, headers=HEADERS)
    assert saved.status_code == 200
    store.save_goal_plan.assert_called_once_with(
        OWNER.id, GOAL, plan(), expected_version=1, expected_goal_version=3,
    )
    store.save_goal_plan.side_effect = SettingsVersionConflict("settings_version_conflict")
    assert client.put(f"/api/goals/{GOAL}/plan", json=body, headers=HEADERS).status_code == 409
    database.has_legal_versions.return_value = False
    before = store.save_goal_plan.call_count
    assert client.put(f"/api/goals/{GOAL}/plan", json=body, headers=HEADERS).status_code == 409
    assert store.save_goal_plan.call_count == before


def test_goal_plan_late_profile_change_discards_saved_result(
    workspace_http: tuple[TestClient, Mock, Mock, Mock],
) -> None:
    client, auth, store, _ = workspace_http

    def saved(*args: object, **kwargs: object) -> dict[str, str]:
        auth.refresh_session.side_effect = None
        auth.refresh_session.return_value = OTHER
        return {"private_result": "not-for-new-profile"}

    store.save_goal_plan.side_effect = saved
    response = client.put(f"/api/goals/{GOAL}/plan", headers=HEADERS, json={
        "document": plan(), "expected_version": 0, "expected_goal_version": 1,
    })
    assert response.status_code == 409
    assert "private_result" not in response.text
    assert store.save_goal_plan.call_count == 1


@pytest.mark.skipif(not DATABASE_URL, reason="ephemeral PostgreSQL is required")
def test_saved_goal_scenarios_enforce_two_version_cas_tenant_and_cascade(
    workspace_database: tuple[Database, str, str],
) -> None:
    database, _, _ = workspace_database
    owner, other = user(database), user(database)
    store = WorkspaceStore(database)
    target = (datetime.now(UTC) + timedelta(days=365)).date().isoformat()
    created = store.create_goal(owner, goal_document(target_date=target))
    from uuid import UUID

    goal_id = UUID(created["id"])
    assert store.goal_plan(owner, goal_id)["document"] is None
    first = store.save_goal_plan(owner, goal_id, plan(), expected_version=0,
                                 expected_goal_version=1)
    assert first["version"] == 1
    assert first["forecast"]["status"] == "available"
    document = plan()
    with pytest.raises(WorkspaceNotFound):
        store.goal_plan(other, goal_id)
    with pytest.raises(WorkspaceNotFound):
        store.save_goal_plan(other, goal_id, document, expected_version=0, expected_goal_version=1)
    with pytest.raises(SettingsVersionConflict):
        store.save_goal_plan(owner, goal_id, document, expected_version=0, expected_goal_version=1)
    store.update_goal(owner, goal_id, goal_document(target_date=target, title="Updated"),
                      expected_version=1)
    with pytest.raises(SettingsVersionConflict):
        store.save_goal_plan(owner, goal_id, document, expected_version=1, expected_goal_version=1)

    def concurrent_save(monthly: str) -> bool:
        try:
            store.save_goal_plan(owner, goal_id, plan(monthly_contribution_rub=monthly),
                                 expected_version=1, expected_goal_version=2)
        except SettingsVersionConflict:
            return False
        return True

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(concurrent_save, ("20000", "30000"))) == [False, True]
    assert store.goal_plan(owner, goal_id)["version"] == 2
    assert store.delete_goal(owner, goal_id, expected_version=2)
    with store._transaction(owner) as cur:
        cur.execute("SELECT 1 FROM goal_plans WHERE user_id = %s AND goal_id = %s",
                    (owner, goal_id))
        assert cur.fetchone() is None
