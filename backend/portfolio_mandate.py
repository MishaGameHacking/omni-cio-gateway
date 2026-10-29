"""Versioned portfolio mandate; no execution rights or default investor profile.

The canonical copy lives inside workspace_strategy_versions.config_json.
An omitted field from an older client cannot erase an existing mandate.
"""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt
from fastapi import HTTPException

try:
    from .credit_evidence import MAXIMUM_CREDIT_LEVEL
    from .volume_contract import decimal, text_number, financial_context
    from .strategy_construction import permitted_classes
except ImportError:
    from credit_evidence import MAXIMUM_CREDIT_LEVEL
    from volume_contract import decimal, text_number, financial_context
    from strategy_construction import permitted_classes


class PortfolioMandate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_mode: Literal["bonds", "shares", "mixed"]
    base_currency: Literal["RUB"]
    account_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    loss_capacity_percent: str = Field(min_length=1, max_length=40)
    bond_target_percent: str = Field(min_length=1, max_length=40)
    share_target_percent: str = Field(min_length=1, max_length=40)
    minimum_rating_level: StrictInt = Field(ge=0, le=MAXIMUM_CREDIT_LEVEL)
    max_discretionary_turnover_percent: str = Field(min_length=1, max_length=40)
    turnover_window_days: StrictInt = Field(ge=1, le=366)
    max_trade_cost_percent: str = Field(min_length=1, max_length=40)
    rebalance_cooldown_days: StrictInt = Field(ge=0, le=365)
    reinvest_coupons: StrictBool
    reinvest_dividends: StrictBool
    allowed_sessions: list[Literal["main"]] = Field(min_length=1, max_length=1)


@financial_context
def validated_mandate(value: PortfolioMandate | dict) -> dict:
    result = (value if isinstance(value, PortfolioMandate) else PortfolioMandate.model_validate(value)).model_dump()
    for field in ("loss_capacity_percent", "bond_target_percent", "share_target_percent",
                  "max_discretionary_turnover_percent", "max_trade_cost_percent"):
        amount = decimal(result[field])
        if amount is None or not 0 <= amount <= 100:
            raise HTTPException(422, "mandate_percentage_invalid")
        result[field] = text_number(amount)
    bonds, shares = decimal(result["bond_target_percent"]), decimal(result["share_target_percent"])
    if bonds + shares != 100:
        raise HTTPException(422, "mandate_asset_weights_must_total_100")
    mode = result["asset_mode"]
    if (mode == "bonds" and (bonds != 100 or shares != 0)) or (mode == "shares" and (shares != 100 or bonds != 0)) \
            or (mode == "mixed" and (bonds <= 0 or shares <= 0)):
        raise HTTPException(422, "mandate_weights_conflict_with_asset_mode")
    # Zero loss capacity is a valid owner's choice; it is never silently raised.
    return result


def preserve_mandate(config: dict, active: dict | None, *, supplied: bool) -> dict:
    previous = (active or {}).get("config", {}).get("mandate")
    if previous and not supplied:
        # Tighten a legacy BBB- setting on migration; retain stricter choices.
        floor = previous.get("minimum_rating_level")
        migrated = {**previous, "minimum_rating_level": min(floor, MAXIMUM_CREDIT_LEVEL)} if type(floor) is int else previous
        return {**config, "mandate": validated_mandate(migrated)}
    if previous and config.get("mandate") is None:
        raise HTTPException(409, "mandate_cannot_be_removed_by_legacy_edit")
    return config


def assert_mandate_account(config: dict, snapshot: dict) -> None:
    mandate = config.get("mandate")
    if mandate is None:
        return
    if config.get("reserve", {}).get("currency") != "RUB" or snapshot.get("currency") != "RUB":
        raise HTTPException(422, "mandate_requires_ruble_portfolio")
    if mandate["account_id"] not in {account.get("id") for account in snapshot.get("accounts", [])}:
        raise HTTPException(409, "mandate_account_not_in_current_verified_snapshot")


def mandate_purchase_reasons(config: dict, instrument_type: str | None,
                             account_id: str | None = None, credit: dict | None = None) -> list[str]:
    mandate = config.get("mandate")
    if mandate is None:
        # Existing constraint previews retain their legacy semantics. Full
        # suitability/automatic execution remain denied in volume_purchases.
        return []
    result = []
    if instrument_type not in permitted_classes(config):
        result.append("instrument_class_outside_mandate")
    if account_id is not None and account_id != mandate["account_id"]:
        result.append("account_outside_mandate")
    if decimal(mandate["loss_capacity_percent"]) == 0:
        result.append("zero_loss_capacity_blocks_new_risk")
    if credit is not None:
        configured_floor = mandate.get("minimum_rating_level")
        if type(configured_floor) is not int or configured_floor < 0:
            return result + ["rating_mandate_invalid"]
        # Persisted configs and older clients cannot weaken the global floor.
        effective_floor = min(configured_floor, MAXIMUM_CREDIT_LEVEL)
        for row in credit.get("ratings", []):
            level = row.get("level_within_agency")
            if type(level) is not int or not 0 <= level <= effective_floor:
                result.append("rating_below_owner_mandate")
                break
    return result


