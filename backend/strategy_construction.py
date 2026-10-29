"""Transparent strategy construction. Scenario losses are not probabilities.

Age never supplies loss capacity. Unknown suitability or fund look-through
keeps a candidate out of the executable action plan. No model calls or orders.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_DOWN
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

try:
    from .volume_contract import decimal, text_number, financial_context
except ImportError:
    from volume_contract import decimal, text_number, financial_context

CLASSES = ("bond", "share", "etf")
# Product policy assumptions, not an estimate of future returns or default odds.
BASE_WEIGHTS = {
    "capital": (70, 0, 30), "coupon": (80, 0, 20),
    "balanced": (40, 20, 40), "growth": (20, 30, 50),
    "equity": (0, 40, 60),
}
STRESS_LOSS = {"bond": Decimal("0.25"), "share": Decimal("0.60"), "etf": Decimal("0.60")}


class StrategyConstruction(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    version: Literal[1] = 1
    enabled_classes: list[Literal["bond", "share", "etf"]] = Field(min_length=1, max_length=3)
    age: StrictInt | None = Field(default=None, ge=18, le=100)
    reserve_percent: StrictInt = Field(default=20, ge=5, le=80)
    key_rate_mode: Literal["allow_below", "at_least_key_rate"] = "allow_below"
    loss_capacity_confirmed: StrictBool = False
    income_stability: Literal["unknown", "stable", "variable"] = "unknown"
    reinvest: StrictBool = True


def permitted_classes(config: dict) -> set[str]:
    construction = config.get("construction")
    if construction:
        return set(construction["enabled_classes"])
    return {"bonds": {"bond"}, "shares": {"share"}, "mixed": {"bond", "share"}}.get(
        (config.get("mandate") or {}).get("asset_mode"), {"bond", "share"})


def profile_construction(identifier: str, previous: dict) -> dict:
    prior = previous.get("construction") or {}
    weights = BASE_WEIGHTS[identifier]
    return StrategyConstruction(
        enabled_classes=[kind for kind, weight in zip(CLASSES, weights) if weight],
        age=prior.get("age"), reserve_percent=max(prior.get("reserve_percent", 0),
            {"capital": 25, "coupon": 20, "balanced": 15, "growth": 15, "equity": 20}[identifier]),
        key_rate_mode=prior.get("key_rate_mode", "allow_below"),
        loss_capacity_confirmed=prior.get("loss_capacity_confirmed", False),
        income_stability=prior.get("income_stability", "unknown"), reinvest=prior.get("reinvest", True),
    ).model_dump()


@financial_context
def allocation_policy(config: dict) -> dict:
    """Constrain preset weights by declared capacity and a common stress case.

Fund exposure is conservatively stressed like equity until looked through.
Short goals and uncertain income reduce invested capital, never widen limits.
The residual is cash; it is not silently redistributed to another risky class.
"""
    settings = config.get("construction") or {}
    profile = (config.get("tuning") or {}).get("profile_id", "capital")
    weights = dict(zip(CLASSES, map(Decimal, BASE_WEIGHTS.get(profile, BASE_WEIGHTS["capital"]))))
    allowed = permitted_classes(config)
    for kind in CLASSES:
        if kind not in allowed:
            weights[kind] = Decimal(0)
    reserve = Decimal(settings.get("reserve_percent", 20))
    investable = (100 - reserve) / 100
    weights = {kind: weight * investable for kind, weight in weights.items()}
    horizon = config.get("horizon_months", 12)
    if horizon < 36:
        weights["share"] = weights["etf"] = Decimal(0)
    capacity = decimal((config.get("mandate") or {}).get("loss_capacity_percent")) or Decimal(0)
    reasons = []
    if not settings.get("loss_capacity_confirmed"):
        capacity = Decimal(0)
        reasons.append("loss_capacity_not_confirmed")
    if settings.get("income_stability", "unknown") == "unknown":
        capacity = Decimal(0)
        reasons.append("income_stability_unknown")
    elif settings["income_stability"] == "variable":
        capacity /= 2
    stress = sum((weights[kind] * STRESS_LOSS[kind] for kind in CLASSES), Decimal(0))
    scale = min(Decimal(1), capacity / stress) if stress > 0 else Decimal(0)
    weights = {kind: (value * scale).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
               for kind, value in weights.items()}
    weights["cash"] = 100 - sum(weights.values(), Decimal(0))
    if capacity <= 0:
        reasons.append("new_risk_not_permitted")
    return {"weights_percent": {key: text_number(value) for key, value in weights.items()},
            "stress_loss_percent": text_number(sum((weights[k] * STRESS_LOSS[k] for k in CLASSES), Decimal(0))),
            "stress_assumptions_percent": {k: text_number(v * 100) for k, v in STRESS_LOSS.items()},
            "risk_basis": "policy_stress_not_probability_or_loss_guarantee", "missing": reasons,
            "age_used_as_loss_capacity": False, "age": settings.get("age"),
            "age_note": "Возраст не определяет допустимые потери: важнее срок, резерв и финансовая устойчивость.",
            "key_rate_scope": "ruble_bonds_yield_to_worst_after_fees_before_personal_tax",
            "paid_model_required": False, "automatic_order": False}


def preserve_construction(config: dict, active: dict | None, supplied: bool) -> dict:
    previous = (active or {}).get("config", {}).get("construction")
    if previous and not supplied:
        config = {**config, "construction": previous}
    elif previous and config.get("construction") is None:
        from fastapi import HTTPException
        raise HTTPException(409, "construction_cannot_be_removed_by_legacy_edit")
    return config


@financial_context
def target_value(config: dict, total: Decimal, kind: str, held_class: Decimal,
                 held_instrument: Decimal) -> Decimal:
    """Add only the remaining class allocation and never exceed position cap."""
    allocation = allocation_policy(config)
    weight = decimal(allocation["weights_percent"].get(kind)) or Decimal(0)
    position = decimal(config.get("limits", {}).get("position_percent")) or Decimal(0)
    class_target = total * weight / 100
    if held_class > class_target and held_class > 0:
        return min(total * position / 100, held_instrument * class_target / held_class)
    class_room = max(Decimal(0), class_target - held_class)
    return min(total * position / 100, held_instrument + class_room)


def ranking_key(item: dict, holdings: set[str]) -> tuple:
    """Prefer existing holdings and lower published risk; deterministic ties.

This is search priority only. Complete independent purchase checks follow.
"""
    return (item.get("uid") not in holdings,
            {"RISK_LEVEL_LOW": 0, "RISK_LEVEL_MODERATE": 1}.get(item.get("riskLevel"), 2),
            str(item.get("uid", "")))
