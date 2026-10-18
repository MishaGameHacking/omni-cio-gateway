"""Deterministic synthetic scenarios: no predictive accuracy claim."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import pytest
from backend.portfolio_scenarios import JointScenario, ScenarioError, assess_scenarios

NOW = datetime(2026, 10, 18, 14, 0, tzinfo=timezone.utc)


def evaluate(scenarios=None, weights=None, **changes):
    rows = scenarios if scenarios is not None else [JointScenario(D("0.96"), {"A": D("0.05")}), JointScenario(D("0.04"), {"A": D("-0.5")})]
    args = {"horizon_days": 10, "as_of": NOW, "now": NOW, "max_age_seconds": 60, **changes}
    return assess_scenarios({"A": D(1)} if weights is None else weights, rows, **args)


def test_weighted_expected_return_and_fractional_tail():
    result = evaluate()
    assert D(result["expected_net_return"]) == D("0.028")
    assert D(result["probability_of_loss"]) == D("0.04")
    assert D(result["value_at_risk"]) == D("-0.05")
    assert D(result["expected_shortfall"]) == D("0.39")
    assert result["orders_allowed"] is False


def test_joint_scenarios_preserve_hedge_and_costs():
    rows = [JointScenario(D("0.5"), {"A": D("0.2"), "B": D("-0.2")}), JointScenario(D("0.5"), {"A": D("-0.2"), "B": D("0.2")})]
    result = evaluate(rows, {"A": D("0.5"), "B": D("0.5")}, all_in_cost_rate="0.01", inflation_rate="0.02")
    assert D(result["expected_net_return"]) == D("-0.01")
    assert D(result["probability_of_loss"]) == D(1)
    assert abs(D(result["expected_real_return"]) - (D("0.99") / D("1.02") - 1)) < D("1e-25")


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "1e999", "1e1000000000", "1e-1000000", True, None, "not-a-number", "9" * 101])
def test_bad_returns_are_not_zero_or_safe(value):
    with pytest.raises(ScenarioError):
        evaluate([JointScenario(D(1), {"A": value})])


@pytest.mark.parametrize("changes", [
    {"confidence": 1}, {"confidence": 0}, {"all_in_cost_rate": -1}, {"inflation_rate": -1},
    {"horizon_days": True}, {"horizon_days": 0}, {"max_age_seconds": False},
    {"as_of": NOW - timedelta(seconds=61)}, {"as_of": NOW + timedelta(seconds=1)},
    {"as_of": NOW.replace(tzinfo=None)},
])
def test_invalid_policy_or_stale_inputs(changes):
    with pytest.raises(ScenarioError):
        evaluate(**changes)


@pytest.mark.parametrize("rows", [[], [JointScenario(D("0.9"), {"A": D(0)})],
    [JointScenario(D(1), {})], [JointScenario(D(1), {"A": D(0), "B": D(0)})],
    [JointScenario(D(1), {"A": D("-1.01")})]])
def test_incomplete_or_infeasible_distribution(rows):
    with pytest.raises(ScenarioError):
        evaluate(rows)


def test_zero_probability_extreme_does_not_change_risk():
    result = evaluate([JointScenario(D(1), {"A": D("0.1")}), JointScenario(D(0), {"A": D("-1")})])
    assert D(result["expected_shortfall"]) == D("-0.1")
    assert D(result["probability_of_loss"]) == 0


def test_weights_must_be_fully_invested_without_leverage():
    for weights in ({}, {"A": D("0.9")}, {"A": D("-1")}):
        with pytest.raises(ScenarioError):
            evaluate(weights=weights)
