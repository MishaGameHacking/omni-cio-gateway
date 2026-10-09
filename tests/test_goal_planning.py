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
from omnicio.financial import MAX_USER_AMOUNT_RUB, RUB_QUANTUM
from omnicio.goal_planning import goal_forecast, goal_plan_fields, normalize_goal_plan
from omnicio.portfolio_store import SettingsVersionConflict
from omnicio.workspace import amount
from omnicio.workspace_store import WorkspaceNotFound, WorkspaceStore


def plan(**changes: Any) -> dict[str, Any]:
    return {
        "monthly_contribution_rub": "10000", "monthly_income_rub": "1000",
        "annual_return_percent": "0", "annual_volatility_percent": "0",
        "annual_inflation_percent": "0", "target_in_today_money": True, "seed": 42, **changes,
    }


def goal(**changes: Any) -> dict[str, Any]:
    return {"kind": "capital", "progress": {"amount_rub": "100000", "status": "available",
            "source": "manual", "as_of": "2026-01-01T00:00:00+00:00"},
            "target_amount_rub": "220000", "target_date": "2027-01-01", **changes}


def test_goal_and_workspace_amounts_share_the_same_rub_input_boundary() -> None:
    at_limit = str(MAX_USER_AMOUNT_RUB)
    too_large = str(MAX_USER_AMOUNT_RUB + RUB_QUANTUM)
    accepted = plan(monthly_contribution_rub=at_limit, monthly_income_rub=at_limit)
    rejected = plan(monthly_contribution_rub=too_large)
    assert amount(at_limit) == MAX_USER_AMOUNT_RUB
    assert normalize_goal_plan(accepted)["monthly_contribution_rub"] == at_limit
    with pytest.raises(ValueError):
        amount(too_large)
    with pytest.raises(ValueError):
        normalize_goal_plan(rejected)


def test_zero_return_has_exact_linear_growth_and_required_contribution() -> None:
    result = goal_forecast(goal(), plan(), today=date(2026, 1, 1))
    assert result["status"] == "available"
    assert result["projected_amount_rub"] == "220000.00"
    assert result["required_monthly_rub"] == "10000.00"
    assert result["deterministic_months_to_target"] == 12
    assert result["simulation"] is None
    assert result["source_status"] == "available"
    assert result["source_as_of"] == "2026-01-01T00:00:00+00:00"


@pytest.mark.parametrize("kind,annual_return,inflation", [
    ("capital", "0", "0"), ("capital", "-30", "10"),
    ("capital", "15", "0"), ("income", "0", "0"),
])
def test_minimum_monthly_payment_reaches_target_and_one_kopeck_less_does_not(
    kind: str, annual_return: str, inflation: str,
) -> None:
    observed = goal(kind=kind, target_amount_rub="100", target_date="2026-04-01",
                    progress={"amount_rub": "0", "status": "available"})
    assumptions = plan(monthly_contribution_rub="0", monthly_income_rub="0",
                       annual_return_percent=annual_return, annual_inflation_percent=inflation)
    result = goal_forecast(observed, assumptions, today=date(2026, 1, 1))
    payment = Decimal(result["required_monthly_rub"])
    field = "monthly_income_rub" if kind == "income" else "monthly_contribution_rub"
    funded = goal_forecast(observed, {**assumptions, field: str(payment)}, today=date(2026, 1, 1))
    short = goal_forecast(observed, {**assumptions, field: str(payment - Decimal("0.01"))},
                          today=date(2026, 1, 1))
    assert funded["deterministic_months_to_target"] is not None
    assert short["deterministic_months_to_target"] is None
    assert Decimal(funded["projected_amount_rub"]) >= Decimal(
        funded["inflation_adjusted_target_rub"],
    )


def test_allocated_portfolio_progress_keeps_derived_decimal_precision_in_forecast() -> None:
    from omnicio.workspace import goal_progress

    now = datetime(2026, 1, 1, tzinfo=UTC)
    document = {**goal(), "progress_source": "portfolio", "account_id": "A",
                "environment": "prod", "allocation_percent": "33.333333333"}
    progress = goal_progress(
        document, connection={"account_id": "A", "environment": "prod"},
        snapshot={"captured_at": now, "analysis_status": "observed", "nav_rub": "1000.01"},
        operations=[], watermark=None, history_complete=True, now=now,
    )
    assert progress["amount_rub"] == "333.3366666633333"
    result = goal_forecast({**document, "progress": progress}, plan(), today=now.date())
    assert result["status"] == "available"
    assert result["source_amount_rub"] == progress["amount_rub"]
    assert result["projected_amount_rub"] == "120333.34"


def test_allocated_income_preserves_twenty_decimal_places_without_relaxing_user_inputs() -> None:
    from omnicio.workspace import goal_progress

    now = datetime(2026, 1, 2, tzinfo=UTC)
    document = {**goal(kind="income"), "progress_source": "income", "account_id": "A",
                "environment": "prod", "allocation_percent": "0.000000001",
                "start_date": "2026-01-01"}
    progress = goal_progress(
        document, connection={"account_id": "A", "environment": "prod"}, snapshot=None,
        operations=[{"operation_date": now, "operation_type": "OPERATION_TYPE_COUPON",
                     "operation_state": "OPERATION_STATE_EXECUTED",
                     "payment_value": "0.000000001", "payment_currency": "RUB"}],
        watermark=now, history_complete=True, now=now,
    )
    result = goal_forecast({**document, "progress": progress}, plan(), today=now.date())
    assert result["status"] == "available"
    assert Decimal(result["source_amount_rub"]) == Decimal("1e-20")
    too_precise_plan = plan(monthly_income_rub="0.000000001")
    with pytest.raises(ValueError, match="precision"):
        normalize_goal_plan(too_precise_plan, kind="income")


def test_deterministic_attainment_uses_unrounded_amounts_and_large_money_is_decimal() -> None:
    almost = goal(target_amount_rub="100", target_date="2026-02-01",
                  progress={"amount_rub": "99.995", "status": "available"})
    result = goal_forecast(almost, plan(monthly_contribution_rub="0"), today=date(2026, 1, 1))
    assert result["projected_amount_rub"] == "100.00"
    assert result["deterministic_months_to_target"] is None
    assert result["required_monthly_rub"] == "0.01"
    large = goal(target_date="2056-01-01", target_amount_rub="1000000000000",
                 progress={"amount_rub": "999999999999.99", "status": "available"})
    result = goal_forecast(large, plan(monthly_contribution_rub="999999999999.99"),
                           today=date(2026, 1, 1))
    assert result["projected_amount_rub"] == "360999999999996.39"


def test_stale_portfolio_progress_cannot_be_presented_as_a_current_forecast() -> None:
    from omnicio.workspace import goal_progress

    now = datetime(2026, 10, 7, tzinfo=UTC)
    document = {**goal(), "progress_source": "portfolio", "account_id": "synthetic",
                "environment": "production", "allocation_percent": "100"}
    progress = goal_progress(
        document, connection={"account_id": "synthetic", "environment": "production"},
        snapshot={"account_id": "synthetic", "environment": "production",
                  "nav_rub": Decimal("100000"), "analysis_status": "observed",
                  "captured_at": now - timedelta(days=60)},
        operations=[], watermark=None, history_complete=True, now=now,
    )
    assert progress["status"] == "stale"
    forecast = goal_forecast({**document, "progress": progress}, plan(), today=now.date())
    assert forecast["status"] == "source_stale"
    assert forecast["reason"] == "goal_progress_stale"
    assert forecast["source_as_of"] == progress["as_of"]
    assert forecast["as_of"] == "2026-10-07"
    assert "scenario_path" not in forecast
    assert "simulation" not in forecast


@pytest.mark.parametrize("status", [None, "unavailable", "unknown"])
def test_amount_without_available_source_never_silently_becomes_current(status: str | None) -> None:
    result = goal_forecast(goal(progress={"status": status, "amount_rub": "100000"}),
                           plan(), today=date(2026, 1, 1))
    assert result["status"] == "unavailable"
    assert result["reason"] == "goal_progress_unavailable"
    assert "scenario_path" not in result


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


def test_income_plan_accepts_only_its_active_inputs_and_ignores_inactive_values() -> None:
    document = {"monthly_income_rub": "2500", "target_in_today_money": False,
                "annual_return_percent": "not applicable", "annual_volatility_percent": None,
                "monthly_contribution_rub": -10, "annual_inflation_percent": "unused", "seed": None}
    normalized = normalize_goal_plan(document, kind="income")
    assert normalized["monthly_income_rub"] == "2500"
    assert normalized["monthly_contribution_rub"] == "0"
    assert normalized["annual_return_percent"] == "0"
    assert normalized["seed"] == 42
    result = goal_forecast(goal(kind="income"), document, today=date(2026, 1, 1))
    assert result["projected_amount_rub"] == "130000.00"
    assert result["applicable_fields"] == list(goal_plan_fields("income"))
    assert "annual_return_percent" not in result["applicable_fields"]


def test_capital_plan_does_not_require_income_or_optional_simulation_fields() -> None:
    document = {"monthly_contribution_rub": "10000", "annual_return_percent": "0",
                "target_in_today_money": False}
    result = goal_forecast(goal(), document, today=date(2026, 1, 1))
    assert result["projected_amount_rub"] == "220000.00"
    assert result["simulation"] is None
    assert result["chart_contract"]["observed_history"] is False
    assert result["chart_contract"]["x"] == "model_month"
    assert result["scenario_path"][0] == {
        "month": 0, "amount_rub": "100000.00", "contributions_rub": "0.00",
        "source_amount_rub": "100000.00", "target_rub": "220000.00",
    }
    assert result["scenario_path"][-1]["contributions_rub"] == "120000.00"


@pytest.mark.parametrize("document", [
    {"monthly_income_rub": "2500", "target_in_today_money": True},
    {"monthly_income_rub": "-1", "target_in_today_money": False},
    {"monthly_income_rub": "2500", "target_in_today_money": False, "unknown": 1},
])
def test_typed_plan_still_rejects_missing_active_or_unknown_inputs(
    document: dict[str, Any],
) -> None:
    with pytest.raises(ValueError):
        normalize_goal_plan(document, kind="income")


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
