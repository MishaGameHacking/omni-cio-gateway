"""Prepare N01 source text against the existing versioned strategy, on Windows only."""

MODULE = '''"""Versioned portfolio mandate; no execution rights or default investor profile.

The canonical copy lives inside workspace_strategy_versions.config_json.
An omitted field from an older client cannot erase an existing mandate.
"""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt
from fastapi import HTTPException

try:
    from .volume_contract import decimal, text_number, financial_context
except ImportError:
    from volume_contract import decimal, text_number, financial_context


class PortfolioMandate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_mode: Literal["bonds", "shares", "mixed"]
    base_currency: Literal["RUB"]
    account_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    loss_capacity_percent: str = Field(min_length=1, max_length=40)
    bond_target_percent: str = Field(min_length=1, max_length=40)
    share_target_percent: str = Field(min_length=1, max_length=40)
    minimum_rating_level: StrictInt = Field(ge=0, le=9)
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
    if (mode == "bonds" and (bonds != 100 or shares != 0)) or (mode == "shares" and (shares != 100 or bonds != 0)) \\
            or (mode == "mixed" and (bonds <= 0 or shares <= 0)):
        raise HTTPException(422, "mandate_weights_conflict_with_asset_mode")
    # Zero loss capacity is a valid owner's choice; it is never silently raised.
    return result


def preserve_mandate(config: dict, active: dict | None, *, supplied: bool) -> dict:
    previous = (active or {}).get("config", {}).get("mandate")
    if previous and not supplied:
        return {**config, "mandate": validated_mandate(previous)}
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
    permitted = {"bonds": {"bond"}, "shares": {"share"}, "mixed": {"bond", "share"}}
    if instrument_type not in permitted[mandate["asset_mode"]]:
        result.append("instrument_class_outside_mandate")
    if account_id is not None and account_id != mandate["account_id"]:
        result.append("account_outside_mandate")
    if decimal(mandate["loss_capacity_percent"]) == 0:
        result.append("zero_loss_capacity_blocks_new_risk")
    if credit is not None:
        for row in credit.get("ratings", []):
            level = row.get("level_within_agency")
            if type(level) is not int or not 0 <= level <= mandate["minimum_rating_level"]:
                result.append("rating_below_owner_mandate")
                break
    return result
'''


def apply(files, base):
    def read(path):
        return files[path] if path in files else base(path)

    def replace(path, before, after):
        value = read(path)
        assert value.count(before) == 1, (path, before[:100])
        files[path] = value.replace(before, after)

    files['backend/portfolio_mandate.py'] = MODULE
    path = 'backend/volume_state.py'
    anchor = 'class StrategyConfig(StrictModel):'
    replace(path, anchor, '''try:
    from .portfolio_mandate import PortfolioMandate, validated_mandate, preserve_mandate, assert_mandate_account
except ImportError:
    from portfolio_mandate import PortfolioMandate, validated_mandate, preserve_mandate, assert_mandate_account


''' + anchor)
    replace(path, '    allowed_markets: list[Literal["MOEX", "SPB", "RU"]] = Field(min_length=1, max_length=3)',
        '    allowed_markets: list[Literal["MOEX", "SPB", "RU"]] = Field(min_length=1, max_length=3)\n'
        '    mandate: PortfolioMandate | None = None')
    replace(path, 'value = config.model_dump() if isinstance(config, BaseModel) else StrategyConfig.model_validate(config).model_dump()',
        'value = config.model_dump(exclude_none=True) if isinstance(config, BaseModel) else StrategyConfig.model_validate(config).model_dump(exclude_none=True)')
    replace(path, '    value["allowed_markets"] = sorted(set(value["allowed_markets"]))\n    return value',
        '    value["allowed_markets"] = sorted(set(value["allowed_markets"]))\n'
        '    if value.get("mandate") is not None:\n'
        '        value["mandate"] = validated_mandate(value["mandate"])\n'
        '        if value["reserve"]["currency"] != "RUB":\n'
        '            raise HTTPException(422, "mandate_requires_ruble_portfolio")\n'
        '    return value')
    replace(path, '    snapshot = saved_snapshot(user, config["reserve"]["currency"])\n    if not snapshot:',
        '    config = preserve_mandate(config, active, supplied=((payload.config is not None and "mandate" in payload.config.model_fields_set) or (payload.rollback_to_version is not None and config.get("mandate") is not None)))\n'
        '    snapshot = saved_snapshot(user, config["reserve"]["currency"])\n    if not snapshot:')
    replace(path, '    risk = risk_data(user, config=config, snapshot=snapshot)',
        '    assert_mandate_account(config, snapshot)\n    risk = risk_data(user, config=config, snapshot=snapshot)')
    replace(path, 'SELECT id,broker_key FROM workspace_snapshots WHERE user_id=? AND currency=?',
        'SELECT id,broker_key,payload_json FROM workspace_snapshots WHERE user_id=? AND currency=?')
    replace(path, '        version = payload.expected_version + 1\n        db.execute("INSERT INTO workspace_strategy_versions',
        '        assert_mandate_account(config, json.loads(current["payload_json"]))\n'
        '        version = payload.expected_version + 1\n        db.execute("INSERT INTO workspace_strategy_versions')
    replace(path, '    return strategy_data(int(user["id"]))',
        '    result = strategy_data(int(user["id"]))\n'
        '    snapshot = saved_snapshot(user, "RUB")\n'
        '    result["available_accounts"] = (snapshot or {}).get("accounts", [])\n'
        '    result["mandate_execution_mode"] = "read_only"\n'
        '    return result')
    path = 'backend/purchase_policy.py'
    anchor = 'POLICY_VERSION = "purchase-constraints-0.11.0-v1"'
    replace(path, anchor, '''try:
    from .portfolio_mandate import mandate_purchase_reasons
except ImportError:
    from portfolio_mandate import mandate_purchase_reasons

''' + anchor)
    replace(path, '    reasons = instrument_reasons(meta, info, config) + credit_reasons(credit, meta.get("instrumentType"))',
        '    reasons = instrument_reasons(meta, info, config) + credit_reasons(credit, meta.get("instrumentType"))\n'
        '    reasons.extend(mandate_purchase_reasons(config, meta.get("instrumentType"), account_id, credit))')
    path = 'backend/autonomous_controller.py'
    replace(path, '    return bool(exchange and ({exchange, "RU"} & set(config["allowed_markets"]))',
        '    mandate = config.get("mandate")\n'
        '    permitted = {"bonds": {"bond"}, "shares": {"share"}, "mixed": {"bond", "share"}}\n'
        '    if mandate and row.get("instrument_type") not in permitted[mandate["asset_mode"]]:\n'
        '        return False\n'
        '    return bool(exchange and ({exchange, "RU"} & set(config["allowed_markets"]))')
    replace(path, '    eligible = [(amount, account) for account, amount in cash.items() if amount > reserve]',
        '    selected = (config.get("mandate") or {}).get("account_id")\n'
        '    eligible = [(amount, account) for account, amount in cash.items()\n'
        '                if amount > reserve and (selected is None or account == selected)]')
