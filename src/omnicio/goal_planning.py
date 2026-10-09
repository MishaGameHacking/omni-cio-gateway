"""Reproducible goal scenarios over explicit user assumptions and observed progress.

The stochastic model is a conditional lognormal scenario, not an estimate of a
strategy's real-world success rate. Money accounting remains in workspace.py.
"""

from __future__ import annotations

import math
import random
from collections.abc import Mapping
from datetime import date
from decimal import ROUND_CEILING, Decimal, localcontext
from typing import Any

from .financial import MAX_USER_AMOUNT_RUB, MONTHS_PER_YEAR, PERCENT_SCALE, RUB_QUANTUM
from .workspace import amount

_FIELDS = {
    "monthly_contribution_rub", "monthly_income_rub", "annual_return_percent",
    "annual_volatility_percent", "annual_inflation_percent", "target_in_today_money", "seed",
}
_PATHS = 2048
_MAX_MONTHS = 360


def goal_plan_fields(kind: str) -> tuple[str, ...]:
    """Fields with a financial consumer for this goal; seed is an internal detail."""
    common = ("target_in_today_money", "annual_inflation_percent")
    if kind == "income":
        return ("monthly_income_rub", *common)
    if kind == "capital":
        return ("monthly_contribution_rub", "annual_return_percent",
                "annual_volatility_percent", *common)
    raise ValueError("goal_plan_kind_invalid")


def _active_plan_fields(document: Mapping[str, Any], kind: str | None) -> set[str]:
    if kind is None:
        if set(document) != _FIELDS:
            raise ValueError("goal_plan_fields_invalid")
        return _FIELDS
    active = set(goal_plan_fields(kind))
    required = active - {"annual_volatility_percent", "annual_inflation_percent"}
    if document.get("target_in_today_money") is True:
        required.add("annual_inflation_percent")
    else:
        active.discard("annual_inflation_percent")
    if not required <= set(document):
        raise ValueError("goal_plan_fields_invalid")
    return active


def normalize_goal_plan(document: object, *, kind: str | None = None) -> dict[str, Any]:
    if not isinstance(document, dict) or set(document) - _FIELDS:
        raise ValueError("goal_plan_fields_invalid")
    active = _active_plan_fields(document, kind)
    result: dict[str, Any] = {}
    bounds = {
        "monthly_contribution_rub": (Decimal(0), MAX_USER_AMOUNT_RUB),
        "monthly_income_rub": (Decimal(0), MAX_USER_AMOUNT_RUB),
        "annual_return_percent": (Decimal(-99), Decimal(100)),
        "annual_volatility_percent": (Decimal(0), Decimal(200)),
        "annual_inflation_percent": (Decimal(-20), Decimal(100)),
    }
    for field, (lower, upper) in bounds.items():
        raw = document.get(field, "0") if field in active else "0"
        value = amount(raw, maximum=max(abs(lower), upper), places=4)
        if not lower <= value <= upper:
            raise ValueError("goal_plan_value_invalid")
        result[field] = format(value, "f")
    if type(document["target_in_today_money"]) is not bool:
        raise ValueError("goal_plan_inflation_choice_invalid")
    seed = document.get("seed", 42) if kind != "income" else 42
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("goal_plan_seed_invalid")
    result["target_in_today_money"] = document["target_in_today_money"]
    result["seed"] = seed
    return result


def _money(value: Decimal | float) -> str:
    return format(value, ".2f")


def _future_factors(monthly_factor: Decimal, months: int) -> tuple[Decimal, Decimal]:
    growth = monthly_factor**months
    annuity = ((growth - 1) / (monthly_factor - 1)
               if monthly_factor != 1 else Decimal(months))
    return growth, annuity


def _future(
    capital: Decimal, monthly: Decimal, monthly_factor: Decimal, months: int,
) -> Decimal:
    growth, annuity = _future_factors(monthly_factor, months)
    return capital * growth + monthly * annuity


def _simulation(
    capital: float, monthly: float, log_rate: float, sigma: float, months: int,
    target: float, seed: int,
) -> dict[str, Any]:
    rng = random.Random(seed)  # scenario reproducibility, never a security token
    values = []
    for _ in range(_PATHS):
        value = capital
        for _ in range(months):
            value = value * math.exp(log_rate + sigma * rng.gauss(0, 1)) + monthly
        values.append(value)
    values.sort()
    successes = sum(value >= target for value in values)
    probability = successes / _PATHS
    z = 1.96
    denominator = 1 + z * z / _PATHS
    center = (probability + z * z / (2 * _PATHS)) / denominator
    half = z * math.sqrt(probability * (1 - probability) / _PATHS + z * z / (4 * _PATHS**2))
    half /= denominator
    return {
        "paths": _PATHS, "seed": seed,
        "conditional_probability_percent": str(round(probability * PERCENT_SCALE, 4)),
        "sampling_interval_95_percent": [round((center - half) * PERCENT_SCALE, 4),
                                         round((center + half) * PERCENT_SCALE, 4)],
        "terminal_percentiles_rub": {
            str(percentile): _money(values[round((_PATHS - 1) * percentile / PERCENT_SCALE)])
            for percentile in (10, 50, 90)
        },
    }


def _source_progress(goal: Mapping[str, Any]) -> dict[str, Any]:
    progress = goal.get("progress")
    return progress if isinstance(progress, dict) else {}


def goal_forecast(
    goal: Mapping[str, Any], document: object, *, today: date,
) -> dict[str, Any]:
    kind = str(goal["kind"])
    plan = normalize_goal_plan(document, kind=kind)
    progress = _source_progress(goal)
    result: dict[str, Any] = {
        "status": "unavailable", "reason": None, "as_of": today.isoformat(),
        "source_status": progress.get("status", "unavailable"),
        "source_as_of": progress.get("as_of"), "source_kind": progress.get("source"),
        "source_amount_rub": progress.get("amount_rub"),
        "method": "monthly_lognormal_scenario_v1", "assumptions": plan,
        "assumptions_source": "user_supplied", "future_success_guaranteed": False,
        "goal_kind": kind, "applicable_fields": list(goal_plan_fields(kind)),
        "limits": [
            "Returns, volatility, inflation and contributions are assumptions, not forecasts.",
            "Month-end contributions; geometric return assumption after costs.",
            "Independent lognormal monthly returns omit crises and defaults.",
            "The interval measures simulation error, not uncertainty about the real model.",
        ],
    }
    if progress.get("amount_rub") is None:
        return {**result, "reason": "goal_progress_unavailable"}
    if progress.get("status") == "stale":
        return {**result, "status": "source_stale", "reason": "goal_progress_stale"}
    if progress.get("status") != "available":
        return {**result, "reason": "goal_progress_unavailable"}
    if not goal.get("target_date"):
        return {**result, "reason": "goal_target_date_required"}
    end = date.fromisoformat(str(goal["target_date"]))
    # A remaining partial month is one future contribution period, stated in output.
    months = (end.year - today.year) * 12 + end.month - today.month + (end.day > today.day)
    if end <= today or not 1 <= months <= _MAX_MONTHS:
        return {**result, "reason": "goal_plan_horizon_out_of_range"}
    # Server-derived progress multiplies 8-place NAV or 9-place received income
    # by a 9-place allocation percentage and divides by 100. These calculated
    # amounts legitimately have more precision than user-entered assumptions.
    capital = amount(progress["amount_rub"], places=20)
    target = amount(goal["target_amount_rub"])
    income = goal["kind"] == "income"
    monthly = Decimal(plan["monthly_income_rub" if income else "monthly_contribution_rub"])
    sigma = (0.0 if income else float(plan["annual_volatility_percent"])
             / PERCENT_SCALE / math.sqrt(MONTHS_PER_YEAR))
    with localcontext() as context:
        # Bounded 30-year assumptions fit with ample guard digits. Binary floats
        # are used only by the explicitly approximate stochastic model below.
        context.prec = 48
        rate = Decimal(0) if income else Decimal(plan["annual_return_percent"])
        monthly_factor = (1 + rate / PERCENT_SCALE) ** (1 / Decimal(MONTHS_PER_YEAR))
        inflation = Decimal(plan["annual_inflation_percent"])
        inflation_factor = ((1 + inflation / PERCENT_SCALE) ** (1 / Decimal(MONTHS_PER_YEAR))
                            if plan["target_in_today_money"] else Decimal(1))
        adjusted_target = target * inflation_factor**months
        growth, annuity = _future_factors(monthly_factor, months)
        required = max(Decimal(0), (adjusted_target - capital * growth) / annuity)
        required = required.quantize(RUB_QUANTUM, rounding=ROUND_CEILING)
        points = [(_future(capital, monthly, monthly_factor, month),
                   target * inflation_factor**month) for month in range(months + 1)]
        reached = next((month for month, (value, threshold) in enumerate(points)
                        if value >= threshold), None)
        path: list[dict[str, Any]] = [
            {"month": month, "amount_rub": _money(value),
             "contributions_rub": _money(monthly * month),
             "source_amount_rub": _money(capital), "target_rub": _money(threshold)}
            for month, (value, threshold) in enumerate(points)]
        log_rate = float(monthly_factor.ln())
    result.update({
        "status": "available", "reason": None, "months": months,
        "contribution_timing": "end_of_month_including_remaining_partial_month",
        "target_date": end.isoformat(), "inflation_adjusted_target_rub": _money(adjusted_target),
        "projected_amount_rub": path[-1]["amount_rub"],
        "required_monthly_rub": _money(required),
        "required_monthly_kind": "income" if income else "contribution",
        "deterministic_months_to_target": reached, "scenario_path": path,
        "chart_contract": {
            "kind": "scenario", "x": "model_month", "currency": "RUB",
            "source_amount_rub": result["source_amount_rub"],
            "source_as_of": result["source_as_of"], "start_date": today.isoformat(),
            "target_date": end.isoformat(), "observed_history": False,
        },
        "simulation": None,
    })
    if income:
        result["method"] = "monthly_income_accumulation_v1"
    elif sigma > 0:
        result["simulation"] = _simulation(
            float(capital), float(monthly), log_rate, sigma, months,
            float(adjusted_target), plan["seed"],
        )
    return result
