"""Deterministic risk mathematics. Inputs must be dated, adjusted return scenarios.

These are conditional sample/model estimates, never a default/ruin guarantee.
No model calls, prices, probability calibration or missing-value imputation here.
"""
from __future__ import annotations

from datetime import date
from math import ceil, floor, fsum, isfinite, sqrt
from random import Random
from typing import Mapping, Sequence


class RiskDataError(ValueError):
    pass


def finite(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RiskDataError('numeric_value_required')
    result = float(value)
    if not isfinite(result):
        raise RiskDataError('nonfinite_value')
    return result


def tail_loss(losses: Sequence[float], confidence: float = .95) -> dict:
    """Empirical VaR and ES: fractional boundary mass, not mean(loss >= VaR)."""
    level = finite(confidence)
    if not 0 < level < 1 or not losses:
        raise RiskDataError('invalid_tail_sample')
    ordered = sorted(finite(x) for x in losses)
    mass = len(ordered) * (1 - level)
    whole = floor(mass)
    fraction = mass - whole
    descending = ordered[::-1]
    numerator = fsum(descending[:whole])
    if fraction > 1e-12:
        numerator += fraction * descending[whole]
    return {'confidence': level, 'var': ordered[max(ceil(len(ordered) * level) - 1, 0)],
            'expected_shortfall': numerator / mass, 'observations': len(ordered),
            'tail_observations': mass, 'thin_tail': mass < 10}


def aligned_returns(series: Mapping[str, Mapping[str, float]], *, minimum: int = 120) -> tuple:
    """Reject unequal trading dates instead of filling holidays/missing prices with zero."""
    if not series or type(minimum) is not int or not 2 <= minimum <= 10000 or len(series) > 100:
        raise RiskDataError('invalid_return_universe')
    names = tuple(sorted(series))
    days = tuple(sorted(series[names[0]]))
    if not minimum <= len(days) <= 10000:
        raise RiskDataError('insufficient_history')
    for day in days:
        if date.fromisoformat(day).isoformat() != day:
            raise RiskDataError('invalid_return_date')
    if any(tuple(sorted(series[name])) != days for name in names):
        raise RiskDataError('unaligned_history')
    rows = tuple(tuple(finite(series[name][day]) for name in names) for day in days)
    if any(value < -1 for row in rows for value in row):
        raise RiskDataError('invalid_simple_return')
    return names, days, rows


def covariance(rows: Sequence[Sequence[float]], shrinkage: float = .2) -> list[list[float]]:
    """Sample covariance shrunk toward its diagonal. Alpha is explicit, not fitted."""
    alpha = finite(shrinkage)
    if len(rows) < 2 or not rows[0] or not 0 <= alpha <= 1:
        raise RiskDataError('invalid_covariance_sample')
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise RiskDataError('ragged_return_panel')
    values = [[finite(value) for value in row] for row in rows]
    means = [fsum(row[i] for row in values) / len(rows) for i in range(width)]
    return [[fsum((row[i] - means[i]) * (row[j] - means[j]) for row in values)
             / (len(rows) - 1) * (1 if i == j else 1 - alpha)
             for j in range(width)] for i in range(width)]


def long_only_weights(weights: Sequence[float], width: int) -> tuple[float, ...]:
    result = tuple(finite(x) for x in weights)
    if len(result) != width or any(x < 0 for x in result) or fsum(result) > 1 + 1e-12:
        raise RiskDataError('invalid_long_only_weights')
    return result


def portfolio_variance(rows: Sequence[Sequence[float]], weights: Sequence[float], shrinkage: float = .2) -> float:
    matrix = covariance(rows, shrinkage)
    w = long_only_weights(weights, len(matrix))
    result = fsum(w[i] * matrix[i][j] * w[j] for i in range(len(w)) for j in range(len(w)))
    return max(0.0, result)


def effective_positions(weights: Sequence[float]) -> float:
    """Inverse HHI among the supplied exposures; does not imply independence."""
    values = [finite(x) for x in weights]
    if any(x < 0 for x in values) or fsum(values) <= 0:
        raise RiskDataError('invalid_exposures')
    total = fsum(values)
    return 1 / fsum((x / total) ** 2 for x in values)


def drawdown(wealth: Sequence[float]) -> float:
    if not wealth:
        raise RiskDataError('missing_wealth_path')
    values = [finite(x) for x in wealth]
    if values[0] <= 0 or any(x < 0 for x in values):
        raise RiskDataError('invalid_wealth_path')
    peak, worst = values[0], 0.0
    for value in values:
        peak = max(peak, value)
        worst = max(worst, (peak - value) / peak)
    return worst


def wilson_interval(hits: int, trials: int) -> tuple[float, float]:
    """95% Monte Carlo sampling interval, NOT model/market uncertainty."""
    if type(hits) is not int or type(trials) is not int or not 0 <= hits <= trials or trials == 0:
        raise RiskDataError('invalid_binomial_counts')
    z = 1.959963984540054
    p = hits / trials
    denominator = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denominator
    radius = z * sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denominator
    return max(0, centre - radius), min(1, centre + radius)


def bootstrap_floor_risk(rows: Sequence[Sequence[float]], weights: Sequence[float], *,
                         horizon: int = 20, block: int = 5, paths: int = 500,
                         floor_fraction: float = .8, seed: int = 0) -> dict:
    """Joint moving-block bootstrap with buy-and-hold weights and flat cash.

    Same sampled days for every asset retain cross-asset co-movement. Within a
    path weights drift with prices (no imaginary daily rebalancing). No fees,
    future withdrawals, new defaults or scenarios absent from history are added.
    """
    if any(type(x) is not int for x in (horizon, block, paths, seed)) or not 1 <= horizon <= 252 or not 1 <= block <= 60 or not 100 <= paths <= 5000:
        raise RiskDataError('invalid_simulation_size')
    if len(rows) < max(120, block) or not rows[0]:
        raise RiskDataError('insufficient_history')
    w = long_only_weights(weights, len(rows[0]))
    if not 0 < finite(floor_fraction) < 1:
        raise RiskDataError('invalid_capital_floor')
    values = [tuple(finite(x) for x in row) for row in rows]
    if any(len(row) != len(w) or any(x < -1 for x in row) for row in values):
        raise RiskDataError('invalid_return_panel')
    rng = Random(seed)  # Reproducible statistical simulation, not a security token.
    losses, breaches = [], 0
    for _ in range(paths):
        relative = [1.0] * len(w)
        lowest, elapsed = 1.0, 0
        while elapsed < horizon:
            start = rng.randrange(len(values) - block + 1)
            for row in values[start:start + min(block, horizon - elapsed)]:
                relative = [value * (1 + change) for value, change in zip(relative, row)]
                wealth = 1 - fsum(w) + fsum(weight * value for weight, value in zip(w, relative))
                if not isfinite(wealth):
                    raise RiskDataError('simulation_overflow')
                lowest = min(lowest, wealth)
                elapsed += 1
        breaches += int(lowest < floor_fraction)
        losses.append(1 - wealth)
    return {**tail_loss(losses), 'horizon_sessions': horizon, 'block_sessions': block,
            'paths': paths, 'seed': seed, 'capital_floor': floor_fraction,
            'conditional_breach_frequency': breaches / paths,
            'monte_carlo_interval_only': wilson_interval(breaches, paths),
            'method': 'joint_moving_block_buy_and_hold_v1',
            'is_default_probability': False, 'guarantee': False}


def credit_loss(exposures: Sequence[Mapping], horizon_days: int) -> dict:
    """EAD * PD * LGD from supplied, calibrated PD only. No rating-to-PD lookup.

    Union bounds need no independence assumption; repeated issuer exposures
    share one default event. Expected losses add even when defaults correlate.
    """
    if type(horizon_days) is not int or horizon_days <= 0:
        raise RiskDataError('invalid_credit_horizon')
    issuers, expected = {}, 0.0
    for item in exposures:
        if item.get('horizon_days') != horizon_days or not item.get('calibration_source'):
            raise RiskDataError('uncalibrated_default_probability')
        ead, pd, lgd = (finite(item[key]) for key in ('exposure', 'pd', 'lgd'))
        issuer = item.get('issuer_id')
        if not issuer or ead < 0 or not 0 <= pd <= 1 or not 0 <= lgd <= 1:
            raise RiskDataError('invalid_credit_exposure')
        if issuer in issuers and issuers[issuer] != pd:
            raise RiskDataError('conflicting_issuer_pd')
        if ead > 0:
            issuers[issuer] = pd
            expected += ead * pd * lgd
    return {'expected_loss': expected, 'horizon_days': horizon_days,
            'any_default_probability_bounds': [max(issuers.values(), default=0), min(1, fsum(issuers.values()))],
            'independence_assumed': False, 'guarantee': False}
