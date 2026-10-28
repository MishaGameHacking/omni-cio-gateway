"""Freshness and independent rational-arithmetic regressions; synthetic data."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from fractions import Fraction as F
import random
from zoneinfo import ZoneInfo

import pytest
from backend.portfolio_scenarios import JointScenario, ScenarioError, assess_scenarios

NY = ZoneInfo("America/New_York")
NOW = datetime(2026, 10, 19, 6, tzinfo=timezone.utc)


def assess_at(as_of, now, max_age=1800):
    return assess_scenarios({"A": D(1)}, [JointScenario(D(1), {"A": D("0.02")})],
                            horizon_days=1, as_of=as_of, now=now, max_age_seconds=max_age)


def test_fall_back_future_fold_is_rejected():
    now = datetime(2026, 11, 1, 1, 30, tzinfo=NY, fold=0)
    future = now.replace(fold=1)
    assert future.timestamp() - now.timestamp() == 3600
    with pytest.raises(ScenarioError, match="stale_or_future"):
        assess_at(future, now)


def test_fall_back_stale_fold_is_rejected():
    as_of = datetime(2026, 11, 1, 1, 30, tzinfo=NY, fold=0)
    now = as_of.replace(fold=1)
    with pytest.raises(ScenarioError, match="stale_or_future"):
        assess_at(as_of, now, max_age=1800)


def test_fall_back_recent_snapshot_is_not_called_future():
    as_of = datetime(2026, 11, 1, 1, 50, tzinfo=NY, fold=0)
    now = datetime(2026, 11, 1, 1, 10, tzinfo=NY, fold=1)
    assert assess_at(as_of, now)["orders_allowed"] is False


def test_spring_forward_uses_elapsed_time_not_wall_time():
    as_of = datetime(2026, 3, 8, 1, 45, tzinfo=NY)
    now = datetime(2026, 3, 8, 3, 15, tzinfo=NY)
    assert now.timestamp() - as_of.timestamp() == 1800
    assert assess_at(as_of, now)["expected_net_return"] == "0.02"


@pytest.mark.parametrize("offset", [-7, 0, 3, 9])
def test_same_instants_in_other_zones_have_same_result(offset):
    zone = timezone(timedelta(hours=offset))
    baseline = assess_at(NOW - timedelta(seconds=59), NOW)
    actual = assess_at((NOW - timedelta(seconds=59)).astimezone(zone), NOW.astimezone(zone))
    for key in ("expected_net_return", "probability_of_loss", "expected_shortfall"):
        assert actual[key] == baseline[key]


@pytest.mark.parametrize("delta", [timedelta(seconds=1800, microseconds=1), timedelta(microseconds=-1)],
                         ids=["just-stale", "just-future"])
def test_microsecond_boundary_remains_strict(delta):
    with pytest.raises(ScenarioError, match="stale_or_future"):
        assess_at(NOW - delta, NOW)


def rational_tail(losses, confidence):
    """Independent quantile/tail calculation on exact fractions."""
    ordered = sorted(losses)
    quantile = next(loss for index, (loss, _) in enumerate(ordered)
                    if sum(prob for _, prob in ordered[:index + 1]) >= confidence)
    cutoff = 1 - confidence
    worse_mass = F(0)
    tail = F(0)
    for loss, probability in reversed(ordered):
        tail += max(F(0), min(probability, cutoff - worse_mass)) * loss
        worse_mass += probability
    return quantile, tail / cutoff


@pytest.mark.parametrize("seed", range(40))
def test_scenario_metrics_match_independent_fraction_oracle(seed):
    rng = random.Random(seed)
    boundaries = [0, *sorted(rng.sample(range(1, 100), 5)), 100]
    probability_units = [right - left for left, right in zip(boundaries, boundaries[1:])]
    weights = {"A": D("0.2"), "B": D("0.3"), "C": D("0.5")}
    rows, outcomes = [], []
    for units in probability_units:
        returns = {key: D(rng.randint(-75, 75)) / 100 for key in weights}
        probability = D(units) / 100
        net = sum(F(weights[key]) * F(returns[key]) for key in weights) - F(2, 1000)
        outcomes.append((net, F(probability)))
        rows.append(JointScenario(probability, returns))
    confidence = rng.choice([D("0.5"), D("0.9"), D("0.95"), D("0.99")])
    result = assess_scenarios(weights, rows, horizon_days=5, as_of=NOW, now=NOW,
                              max_age_seconds=60, all_in_cost_rate="0.002",
                              inflation_rate="0.003", confidence=confidence)
    var, es = rational_tail([(-net, probability) for net, probability in outcomes], F(confidence))
    expected = sum(net * probability for net, probability in outcomes)
    oracle = {
        "expected_net_return": expected,
        "expected_real_return": (1 + expected) / F(1003, 1000) - 1,
        "probability_of_loss": sum(probability for net, probability in outcomes if net < 0),
        "value_at_risk": var, "expected_shortfall": es,
    }
    for key, exact in oracle.items():
        assert abs(F(result[key]) - exact) < F(1, 10 ** 28), key
    assert result["orders_allowed"] is False
