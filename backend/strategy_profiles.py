"""Server-owned strategy presets and bounded, deterministic research tuning.

Presets are drafts until the existing preview/CAS confirmation succeeds.
They never infer a person's capacity for loss or grant trading permissions.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_UP
from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictBool

try:
    from .volume_contract import decimal, text_number, financial_context
except ImportError:
    from volume_contract import decimal, text_number, financial_context

PROFILE_IDS = ("capital", "coupon", "balanced", "growth", "equity")


class StrategyTuning(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_id: Literal["capital", "coupon", "balanced", "growth", "equity"]
    enabled: StrictBool = True


# Rating levels follow the existing within-agency scale, not issuer name matching.
PROFILES = (
    ("capital", "Защита капитала", "Качественные облигации и повышенный резерв.", "preservation", "conservative", 24, 100, 20, 5, 10, 20, 30, 3, 10, "0.3", 30),
    ("coupon", "Купонный доход", "Облигации для регулярных поступлений и реинвестирования.", "income", "conservative", 36, 100, 10, 5, 10, 20, 30, 5, 15, "0.4", 30),
    ("balanced", "Сбалансированный портфель", "Облигации и акции с ограничением концентрации.", "income", "moderate", 60, 60, 10, 5, 10, 20, 30, 5, 20, "0.5", 30),
    ("growth", "Долгосрочный рост", "Большая доля акций при длинном горизонте.", "growth", "aggressive", 84, 30, 10, 5, 10, 20, 30, 5, 20, "0.5", 45),
    ("equity", "Акции и дивиденды", "Только акции; дивиденды возвращаются в портфель.", "growth", "aggressive", 84, 0, 15, 5, 10, 20, 25, 5, 20, "0.5", 45),
)


def _account_reserve(previous: dict, snapshot: dict | None, reserve_pct: int):
    accounts = (snapshot or {}).get("accounts", [])
    account_ids = {str(item.get("id")) for item in accounts if item.get("id")}
    account = (previous.get("mandate") or {}).get("account_id")
    if account not in account_ids:
        account = next(iter(account_ids)) if len(account_ids) == 1 else None
    selected = next((row for row in accounts if row.get("id") == account), None)
    total = decimal((selected or {}).get("value"))
    if (snapshot or {}).get("currency") != "RUB":
        total = None
    old = previous.get("reserve", {})
    old_reserve = decimal(old) if old.get("currency") == "RUB" else None
    calculated = ((total or Decimal(0)) * reserve_pct / 100).quantize(Decimal("0.01"), rounding=ROUND_UP)
    return account, total, max(old_reserve or Decimal(0), calculated)


def _concentration_limits(previous, values):
    keys = ("position_percent", "issuer_percent", "group_percent", "sector_percent", "currency_percent")
    limits = dict(zip(keys, map(str, values)))
    for key, value in limits.items():
        old = decimal(previous.get("limits", {}).get(key))
        if old is not None and old > 0:
            limits[key] = text_number(min(Decimal(value), old))
    return limits


def _smaller_decimal(previous, key, maximum):
    old = decimal(previous.get(key))
    if old is None:
        old = Decimal(maximum)
    return text_number(min(Decimal(maximum), old))


def _asset_mode(bonds):
    if bonds == 100:
        return "bonds"
    return "shares" if bonds == 0 else "mixed"


def _suggested_profile(current):
    mode = (current.get("mandate") or {}).get("asset_mode")
    if mode == "bonds":
        return "coupon" if current.get("goal") == "income" else "capital"
    return {"shares": "equity", "mixed": "balanced"}.get(mode, "capital")


def _batch_size(available):
    if available < 10000:
        return 2
    return 4 if available < 100000 else 8


def _template(row, active: dict | None, snapshot: dict | None) -> dict:
    (identifier, title, description, goal, risk, horizon, bonds, reserve_pct,
     position, issuer, group, sector, rating, turnover, cost, cooldown) = row
    previous = (active or {}).get("config", {})
    prior_mandate = previous.get("mandate") or {}
    account, total, reserve = _account_reserve(previous, snapshot, reserve_pct)
    limits = _concentration_limits(previous, (position, issuer, group, sector, 100))
    mode = _asset_mode(bonds)
    config = {
        "goal": goal, "risk_level": risk, "horizon_months": horizon,
        "reserve": {"amount": text_number(reserve), "currency": "RUB"},
        "limits": limits, "allowed_markets": ["MOEX"],
        "tuning": {"profile_id": identifier, "enabled": True},
    }
    missing = []
    if not account:
        missing.append("account_required")
    # Zero does not invent willingness to accept a loss and blocks new risk.
    capacity = prior_mandate.get("loss_capacity_percent", "0")
    if decimal(capacity) is None or decimal(capacity) <= 0:
        missing.append("loss_capacity_required")
    if total is None:
        missing.append("ruble_snapshot_required")
    mandate = {
        "asset_mode": mode, "base_currency": "RUB", "account_id": account or "",
        "loss_capacity_percent": capacity,
        "bond_target_percent": str(bonds), "share_target_percent": str(100 - bonds),
        "minimum_rating_level": min(rating, prior_mandate.get("minimum_rating_level", rating)),
        "max_discretionary_turnover_percent": _smaller_decimal(prior_mandate, "max_discretionary_turnover_percent", turnover),
        "turnover_window_days": prior_mandate.get("turnover_window_days", 30),
        "max_trade_cost_percent": _smaller_decimal(prior_mandate, "max_trade_cost_percent", cost),
        "rebalance_cooldown_days": max(cooldown, prior_mandate.get("rebalance_cooldown_days", 0)),
        "reinvest_coupons": True, "reinvest_dividends": True, "allowed_sessions": ["main"],
    }
    config["mandate"] = mandate
    return {"id": identifier, "title": title, "description": description, "config": config,
            "missing": missing, "ready_for_preview": not missing, "reserve_percent": reserve_pct}


@financial_context
def catalogue(active: dict | None, snapshot: dict | None) -> dict:
    """Pure persisted-data projection; opening the screen costs no model call."""
    rows = [_template(row, active, snapshot) for row in PROFILES]
    current = (active or {}).get("config", {})
    mode = current.get("mandate", {}).get("asset_mode")
    suggested = _suggested_profile(current)
    return {"revision": 1, "items": rows, "suggested_id": suggested,
            "suggestion_basis": "existing_asset_mode_and_goal" if mode else "conservative_draft_not_personal_suitability",
            "tuning": research_tuning(current, snapshot),
            "requires_strategy_confirmation": True, "paid_calls_on_read": 0}


@financial_context
def research_tuning(config: dict, snapshot: dict | None) -> dict:
    """Tune work, never the owner's loss capacity or exposure limits."""
    tuning = config.get("tuning") or {}
    enabled = tuning.get("enabled") is True
    reserve = decimal(config.get("reserve", {})) or Decimal(0)
    currency = config.get("reserve", {}).get("currency", "RUB")
    selected_account = config.get("mandate", {}).get("account_id")
    if selected_account:
        cash = sum((decimal(item.get("value")) or Decimal(0) for item in (snapshot or {}).get("positions", [])
                    if item.get("account_id") == selected_account and item.get("instrument_type") == "cash"
                    and (item.get("value") or {}).get("currency") == currency), Decimal(0))
    else:
        cash = sum((decimal(item) or Decimal(0) for item in (snapshot or {}).get("capital", {}).get("cash", [])
                    if item.get("currency") == currency), Decimal(0))
    available = max(Decimal(0), cash - reserve)
    mode = config.get("mandate", {}).get("asset_mode", "mixed")
    classes = {"bonds": ["bond"], "shares": ["share"], "mixed": ["bond", "share"]}.get(mode, [])
    # Small portfolios need fewer simultaneous candidate requests, not weaker limits.
    maximum = _batch_size(available)
    return {"enabled": enabled, "profile_id": tuning.get("profile_id"),
            "candidate_batch": maximum if enabled else 8, "asset_classes": classes,
            "available_above_reserve": {"amount": text_number(available), "currency": currency},
            "limits_widened": False, "paid_model_required": False,
            "description": "Объём проверки зависит от доступных денег; лимиты риска и резерв сохраняются.",
            "automatic_trading": False}
