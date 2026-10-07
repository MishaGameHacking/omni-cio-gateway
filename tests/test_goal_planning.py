"""Goal scenarios expose conditional assumptions and distinguish income from capital."""

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from omnicio.goal_planning import goal_forecast, normalize_goal_plan


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
    with pytest.raises(ValueError):
        normalize_goal_plan(plan(**changes))


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
