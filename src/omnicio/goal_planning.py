"""Reproducible goal scenarios over explicit user assumptions and observed progress.

The stochastic model is a conditional lognormal scenario, not an estimate of a
strategy's real-world success rate. Money accounting remains in workspace.py.
"""

from __future__ import annotations

import math
import random
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any

from .workspace import amount

_FIELDS = {
    "monthly_contribution_rub", "monthly_income_rub", "annual_return_percent",
    "annual_volatility_percent", "annual_inflation_percent", "target_in_today_money", "seed",
}
_PATHS = 2048
_MAX_MONTHS = 360


def normalize_goal_plan(document: object) -> dict[str, Any]:
    if not isinstance(document, dict) or set(document) != _FIELDS:
        raise ValueError("goal_plan_fields_invalid")
    result: dict[str, Any] = {}
    bounds = {
        "monthly_contribution_rub": (Decimal(0), Decimal("1000000000000")),
        "monthly_income_rub": (Decimal(0), Decimal("1000000000000")),
        "annual_return_percent": (Decimal(-99), Decimal(100)),
        "annual_volatility_percent": (Decimal(0), Decimal(200)),
        "annual_inflation_percent": (Decimal(-20), Decimal(100)),
    }
    for field, (lower, upper) in bounds.items():
        value = amount(document[field], maximum=max(abs(lower), upper), places=4)
        if not lower <= value <= upper:
            raise ValueError("goal_plan_value_invalid")
        result[field] = format(value, "f")
    if type(document["target_in_today_money"]) is not bool:
        raise ValueError("goal_plan_inflation_choice_invalid")
    if type(document["seed"]) is not int or not 0 <= document["seed"] < 2**32:
        raise ValueError("goal_plan_seed_invalid")
    result["target_in_today_money"] = document["target_in_today_money"]
    result["seed"] = document["seed"]
    return result


def _money(value: float) -> str:
    return format(value, ".2f")


def _future(capital: float, monthly: float, log_rate: float, months: int) -> float:
    growth = math.exp(log_rate * months)
    annuity = math.expm1(log_rate * months) / math.expm1(log_rate) if log_rate else months
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
        "conditional_probability_percent": str(round(probability * 100, 4)),
        "sampling_interval_95_percent": [round((center - half) * 100, 4),
                                         round((center + half) * 100, 4)],
        "terminal_percentiles_rub": {
            str(percentile): _money(values[round((_PATHS - 1) * percentile / 100)])
            for percentile in (10, 50, 90)
        },
    }


def goal_forecast(
    goal: Mapping[str, Any], document: object, *, today: date,
) -> dict[str, Any]:
    plan = normalize_goal_plan(document)
    result: dict[str, Any] = {
        "status": "unavailable", "reason": None, "as_of": today.isoformat(),
        "method": "monthly_lognormal_scenario_v1", "assumptions": plan,
        "assumptions_source": "user_supplied", "future_success_guaranteed": False,
        "limits": [
            "Returns, volatility, inflation and contributions are assumptions, not forecasts.",
            "Month-end contributions; geometric return assumption after costs.",
            "Independent lognormal monthly returns omit crises and defaults.",
            "The interval measures simulation error, not uncertainty about the real model.",
        ],
    }
    progress = goal.get("progress")
    if not isinstance(progress, dict) or progress.get("amount_rub") is None:
        return {**result, "reason": "goal_progress_unavailable"}
    if not goal.get("target_date"):
        return {**result, "reason": "goal_target_date_required"}
    end = date.fromisoformat(str(goal["target_date"]))
    # A remaining partial month is one future contribution period, stated in output.
    months = (end.year - today.year) * 12 + end.month - today.month + (end.day > today.day)
    if end <= today or not 1 <= months <= _MAX_MONTHS:
        return {**result, "reason": "goal_plan_horizon_out_of_range"}
    capital = float(amount(progress["amount_rub"]))
    target = float(amount(goal["target_amount_rub"]))
    income = goal["kind"] == "income"
    monthly = float(plan["monthly_income_rub" if income else "monthly_contribution_rub"])
    log_rate = 0.0 if income else math.log1p(float(plan["annual_return_percent"]) / 100) / 12
    sigma = 0.0 if income else float(plan["annual_volatility_percent"]) / 100 / math.sqrt(12)
    inflation = (math.log1p(float(plan["annual_inflation_percent"]) / 100) / 12
                 if plan["target_in_today_money"] else 0.0)
    adjusted_target = target * math.exp(inflation * months)
    growth = math.exp(log_rate * months)
    annuity = math.expm1(log_rate * months) / math.expm1(log_rate) if log_rate else months
    required = max(0.0, (adjusted_target - capital * growth) / annuity)
    path: list[dict[str, Any]] = [
        {"month": month, "amount_rub": _money(_future(capital, monthly, log_rate, month)),
             "target_rub": _money(target * math.exp(inflation * month))}
            for month in range(months + 1)]
    reached = next((point["month"] for point in path
                    if Decimal(point["amount_rub"]) >= Decimal(point["target_rub"])), None)
    result.update({
        "status": "available", "reason": None, "months": months,
        "contribution_timing": "end_of_month_including_remaining_partial_month",
        "target_date": end.isoformat(), "inflation_adjusted_target_rub": _money(adjusted_target),
        "projected_amount_rub": path[-1]["amount_rub"],
        "required_monthly_rub": _money(required),
        "required_monthly_kind": "income" if income else "contribution",
        "deterministic_months_to_target": reached, "scenario_path": path,
        "simulation": None,
    })
    if income:
        result["method"] = "monthly_income_accumulation_v1"
    elif sigma > 0:
        result["simulation"] = _simulation(
            capital, monthly, log_rate, sigma, months, adjusted_target, plan["seed"],
        )
    return result
