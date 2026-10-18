"""Auditable joint-scenario arithmetic, NOT a fitted forecasting model.

The caller supplies probabilities and returns for one shared horizon; correlated
assets must appear in the same scenario. No independent marginal resampling,
missing-return imputation, security selection or brokerage execution occurs here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation, localcontext
from collections.abc import Mapping, Sequence

ONE = Decimal(1)
ZERO = Decimal(0)


class ScenarioError(ValueError):
    pass


def number(value) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ScenarioError("scenario_numeric_type_invalid")
    if len(str(value)) > 100:
        raise ScenarioError("scenario_numeric_size_invalid")
    try:
        parsed = Decimal(str(value))
    except InvalidOperation:
        raise ScenarioError("scenario_numeric_invalid") from None
    if not parsed.is_finite() or parsed.copy_abs() > Decimal("1000000") or (not parsed.is_zero() and parsed.adjusted() < -64):
        raise ScenarioError("scenario_numeric_not_finite_or_bounded")
    return parsed


@dataclass(frozen=True)
class JointScenario:
    probability: Decimal
    returns: Mapping[str, Decimal]


def _unit_weights(values, code: str) -> list[Decimal]:
    converted = [number(value) for value in values]
    if any(not ZERO <= value <= ONE for value in converted) or abs(sum(converted, ZERO) - ONE) > Decimal("1e-18"):
        raise ScenarioError(code)
    total = sum(converted, ZERO)
    return [value / total for value in converted]


def _fresh(as_of: datetime, now: datetime, max_age_seconds: int) -> None:
    if (not isinstance(as_of, datetime) or not isinstance(now, datetime)
            or as_of.utcoffset() is None or now.utcoffset() is None):
        raise ScenarioError("scenario_aware_timestamp_required")
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 604800:
        raise ScenarioError("scenario_freshness_policy_invalid")
    age = (now - as_of).total_seconds()
    if not 0 <= age <= max_age_seconds:
        raise ScenarioError("scenario_snapshot_stale_or_future")


def _tail(losses: list[tuple[Decimal, Decimal]], alpha: Decimal) -> tuple[Decimal, Decimal]:
    # Lower weighted quantile; ES uses exactly the worst (1-alpha) probability
    # mass, including only the required fraction of a boundary scenario.
    ordered = sorted(losses)
    cumulative = ZERO
    value_at_risk = ordered[-1][0]
    for loss, probability in ordered:
        cumulative += probability
        if cumulative >= alpha:
            value_at_risk = loss
            break
    remaining = ONE - alpha
    tail_sum = ZERO
    for loss, probability in reversed(ordered):
        used = min(remaining, probability)
        tail_sum += used * loss
        remaining -= used
        if remaining <= ZERO:
            break
    return value_at_risk, tail_sum / (ONE - alpha)


def _scenario_shape(weights, scenarios, horizon_days):
    if type(horizon_days) is not int or not 1 <= horizon_days <= 365:
        raise ScenarioError("scenario_horizon_invalid")
    if not isinstance(weights, Mapping) or not 1 <= len(weights) <= 128:
        raise ScenarioError("scenario_weights_invalid")
    if not isinstance(scenarios, (list, tuple)) or not 1 <= len(scenarios) <= 4096:
        raise ScenarioError("scenario_count_invalid")
    keys = tuple(weights)
    if any(not isinstance(key, str) or not 1 <= len(key) <= 160 for key in keys):
        raise ScenarioError("scenario_asset_identifier_invalid")
    if any(not isinstance(row, JointScenario) for row in scenarios):
        raise ScenarioError("scenario_row_invalid")
    return keys


def _scenario_outcomes(keys, weights, scenarios, probabilities, cost):
    outcomes = []
    for row, probability in zip(scenarios, probabilities):
        if not isinstance(row.returns, Mapping) or set(row.returns) != set(keys):
            raise ScenarioError("scenario_missing_or_extra_asset")
        returns = [number(row.returns[key]) for key in keys]
        if any(value < -ONE for value in returns):
            raise ScenarioError("scenario_unlevered_asset_return_below_minus_one")
        net = sum((weight * value for weight, value in zip(weights, returns)), ZERO) - cost
        if probability > ZERO:
            outcomes.append((net, probability))
    return outcomes


def assess_scenarios(weights: Mapping[str, Decimal], scenarios: Sequence[JointScenario], *,
                     horizon_days: int, as_of: datetime, now: datetime, max_age_seconds: int,
                     all_in_cost_rate=ZERO, inflation_rate=ZERO, confidence=Decimal("0.95")) -> dict:
    """Long-only normalized portfolio, decimal fractional returns (not percent).

    Fees, slippage and supplied taxes must be represented by all_in_cost_rate
    for this same horizon. A tax engine is not implied. Negative VaR/ES means
    even the corresponding tail is profitable; it is deliberately not clamped.
    """
    _fresh(as_of, now, max_age_seconds)
    keys = _scenario_shape(weights, scenarios, horizon_days)
    with localcontext() as ctx:
        ctx.prec = 34
        normalized_weights = _unit_weights([weights[key] for key in keys], "scenario_weights_not_unit_sum")
        probabilities = _unit_weights([row.probability for row in scenarios], "scenario_probabilities_not_unit_sum")
        cost, inflation, alpha = map(number, (all_in_cost_rate, inflation_rate, confidence))
        if not ZERO <= cost <= ONE or not Decimal("-0.99") < inflation <= Decimal(10) or not ZERO < alpha < ONE:
            raise ScenarioError("scenario_cost_inflation_or_confidence_invalid")
        outcomes = _scenario_outcomes(keys, normalized_weights, scenarios, probabilities, cost)
        expected = sum((net * probability for net, probability in outcomes), ZERO)
        real = sum((((ONE + net) / (ONE + inflation) - ONE) * probability for net, probability in outcomes), ZERO)
        loss_probability = sum((probability for net, probability in outcomes if net < ZERO), ZERO)
        var, es = _tail([(-net, probability) for net, probability in outcomes], alpha)
        return {"basis": "supplied_joint_scenarios_not_a_forecast", "horizon_days": horizon_days,
                "as_of": as_of.isoformat(), "scenario_count": len(scenarios), "confidence": str(alpha),
                "expected_net_return": str(expected), "expected_real_return": str(real),
                "probability_of_loss": str(loss_probability), "value_at_risk": str(var),
                "expected_shortfall": str(es), "orders_allowed": False,
                "probability_normalization_tolerance": "1e-18", "units": "fraction_of_initial_capital"}
