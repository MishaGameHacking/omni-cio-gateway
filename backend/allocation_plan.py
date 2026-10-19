"""Bounded, deterministic lot allocation drafts for one owner's accounts.

Not a forecast, suitability engine, broker quote, or order sender. Targets and
candidate priority must come from an approved strategy/research layer. This
kernel allocates *existing* cash once, never anticipated proceeds from a sale.
It selects the largest feasible whole-lot size within each priority's target;
it does not claim globally optimal returns. A live broker check is mandatory.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Context, Decimal, ROUND_CEILING, ROUND_FLOOR, localcontext
from typing import Sequence

ZERO = Decimal(0)
CENT = Decimal("0.01")
MAX_LOTS = 1_000_000
MAX_ITEMS = 100
CONTEXT = Context(prec=64)
VERSION = "allocation-draft-0.11.0-v1"


def _amount(value) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError("exact_decimal_required")
    if len(str(value)) > 40:
        raise ValueError("amount_out_of_bounds")
    try:
        amount = Decimal(value)
    except ArithmeticError:
        raise ValueError("exact_decimal_required") from None
    if (not amount.is_finite() or amount < 0 or amount > Decimal("1e15")
            or amount.as_tuple().exponent < -9 or amount.as_tuple().exponent > 15):
        raise ValueError("amount_out_of_bounds")
    return amount


def _name(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 160 or any(ord(c) < 32 for c in value):
        raise ValueError("identifier_required")
    return value


def _currency(value: str) -> None:
    if not isinstance(value, str) or value not in {"RUB", "USD", "EUR"}:
        raise ValueError("supported_currency_required")


def _integer(value: int, maximum: int = MAX_LOTS) -> None:
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError("bounded_integer_required")


def _aware(value: datetime) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone_aware_timestamp_required")


def _number(value: Decimal) -> str:
    # Do not normalize using the caller's global Decimal context.
    return format(value, "f")


@dataclass(frozen=True)
class PlanContext:
    snapshot_id: str
    strategy_version: int
    observed_at: datetime
    expires_at: datetime

    def __post_init__(self):
        _name(self.snapshot_id)
        _integer(self.strategy_version, 2**31 - 1)
        if self.strategy_version == 0:
            raise ValueError("confirmed_strategy_required")
        _aware(self.observed_at)
        _aware(self.expires_at)
        if not self.observed_at < self.expires_at <= self.observed_at + timedelta(seconds=300):
            raise ValueError("snapshot_lifetime_invalid")


@dataclass(frozen=True)
class AccountCash:
    account_id: str
    currency: str
    available: Decimal
    reserve: Decimal

    def __post_init__(self):
        _name(self.account_id)
        _currency(self.currency)
        for name in ("available", "reserve"):
            object.__setattr__(self, name, _amount(getattr(self, name)))


@dataclass(frozen=True)
class RiskCapacity:
    """Remaining monetary exposure allowed by the upstream joint risk check."""
    key: str
    currency: str
    available: Decimal

    def __post_init__(self):
        _name(self.key)
        _currency(self.currency)
        object.__setattr__(self, "available", _amount(self.available))


@dataclass(frozen=True)
class Candidate:
    account_id: str
    instrument_uid: str
    currency: str
    side: str
    priority: int
    lot_size: int
    price_per_unit: Decimal
    current_value: Decimal
    target_value: Decimal
    broker_max_lots: int
    visible_lots: int
    held_units: Decimal
    blocked_units: Decimal
    fee_rate: Decimal
    fixed_fee: Decimal
    source_id: str
    observed_at: datetime
    expires_at: datetime
    risk_keys: tuple[str, ...] = ()

    def __post_init__(self):
        for value in (self.account_id, self.instrument_uid, self.source_id):
            _name(value)
        _currency(self.currency)
        if not isinstance(self.side, str) or self.side not in {"buy", "sell"}:
            raise ValueError("buy_or_sell_required")
        for value in (self.priority, self.lot_size, self.broker_max_lots, self.visible_lots):
            _integer(value)
        if self.lot_size == 0:
            raise ValueError("positive_lot_required")
        for name in ("price_per_unit", "current_value", "target_value", "held_units",
                     "blocked_units", "fee_rate", "fixed_fee"):
            object.__setattr__(self, name, _amount(getattr(self, name)))
        if self.price_per_unit == 0 or self.fee_rate > 1 or self.blocked_units > self.held_units:
            raise ValueError("candidate_amounts_inconsistent")
        if not isinstance(self.risk_keys, tuple) or len(self.risk_keys) > 20:
            raise ValueError("bounded_risk_keys_required")
        for key in self.risk_keys:
            _name(key)
        if len(set(self.risk_keys)) != len(self.risk_keys):
            raise ValueError("duplicate_risk_key")
        _aware(self.observed_at)
        _aware(self.expires_at)
        if not self.observed_at < self.expires_at <= self.observed_at + timedelta(seconds=60):
            raise ValueError("quote_lifetime_invalid")


def _principal(candidate: Candidate, lots: int) -> Decimal:
    return candidate.price_per_unit * candidate.lot_size * lots


def _fees(candidate: Candidate, lots: int) -> Decimal:
    if lots == 0:
        return ZERO
    return (_principal(candidate, lots) * candidate.fee_rate + candidate.fixed_fee).quantize(
        CENT, rounding=ROUND_CEILING,
    )


def _maximum_affordable(candidate: Candidate, ceiling: Decimal, limit: int) -> int:
    # Nonnegative fixed/rate fees define a monotone *estimate*, not an assumed
    # monotonicity contract for a remote GetOrderPrice endpoint.
    low, high = 0, limit
    while low < high:
        middle = (low + high + 1) // 2
        if _principal(candidate, middle) + _fees(candidate, middle) <= ceiling:
            low = middle
        else:
            high = middle - 1
    return low


def _initial_resources(accounts, risks):
    cash, reserves, remaining_risk = {}, {}, {}
    for account in accounts:
        if not isinstance(account, AccountCash):
            raise ValueError("validated_account_required")
        key = (account.account_id, account.currency)
        if key in cash:
            raise ValueError("duplicate_account_currency")
        cash[key], reserves[key] = account.available, account.reserve
    for risk in risks:
        if not isinstance(risk, RiskCapacity) or risk.key in remaining_risk:
            raise ValueError("invalid_or_duplicate_risk_capacity")
        remaining_risk[risk.key] = [risk.currency, risk.available]
    return cash, reserves, remaining_risk


def _validate_candidates(candidates, cash, risk):
    seen, instruments = set(), {}
    for candidate in candidates:
        if not isinstance(candidate, Candidate):
            raise ValueError("validated_candidate_required")
        key = (candidate.account_id, candidate.instrument_uid)
        if key in seen:
            raise ValueError("duplicate_instrument_on_account")
        seen.add(key)
        if (candidate.account_id, candidate.currency) not in cash:
            raise ValueError("account_currency_not_verified")
        _verify_instrument(candidate, instruments)
        _verify_risk_keys(candidate, risk)


def _verify_instrument(candidate, instruments):
    identity = (candidate.side, candidate.currency, candidate.lot_size)
    previous = instruments.setdefault(candidate.instrument_uid, identity)
    if previous[0] != identity[0]:
        raise ValueError("opposing_actions_for_same_instrument")
    if previous[1:] != identity[1:]:
        raise ValueError("instrument_metadata_conflict")


def _verify_risk_keys(candidate, risk):
    if candidate.side == "buy" and not candidate.risk_keys:
        raise ValueError("joint_risk_capacity_required")
    for key in candidate.risk_keys:
        if key not in risk or risk[key][0] != candidate.currency:
            raise ValueError("risk_capacity_currency_not_verified")


def _buy_lots(candidate, cash, reserves, risk):
    key = (candidate.account_id, candidate.currency)
    budget = min(cash[key] - reserves[key], candidate.target_value - candidate.current_value,
                 *(risk[name][1] for name in candidate.risk_keys))
    if budget <= 0:
        return 0
    limit = min(candidate.broker_max_lots, candidate.visible_lots)
    return _maximum_affordable(candidate, budget, limit)


def _sell_lots(candidate):
    gap = max(ZERO, candidate.current_value - candidate.target_value)
    desired = int((gap / _principal(candidate, 1)).to_integral_value(rounding=ROUND_FLOOR))
    free = int(((candidate.held_units - candidate.blocked_units) / candidate.lot_size)
               .to_integral_value(rounding=ROUND_FLOOR))
    lots = min(desired, free, candidate.broker_max_lots, candidate.visible_lots)
    if lots > 0 and _fees(candidate, lots) >= _principal(candidate, lots):
        return 0
    return lots


def _allocate(candidate, cash, reserves, risk, now):
    key = (candidate.account_id, candidate.currency)
    before = cash[key]
    fresh = candidate.observed_at <= now < candidate.expires_at
    if not fresh:
        lots, reason = 0, "quote_stale_or_future"
    else:
        lots = (_buy_lots(candidate, cash, reserves, risk) if candidate.side == "buy"
                else _sell_lots(candidate))
        reason = "whole_lot_target_draft" if lots else "no_feasible_whole_lot_within_target"
    principal, fee = _principal(candidate, lots), _fees(candidate, lots)
    if lots and candidate.side == "buy":
        cash[key] -= principal + fee
        for name in candidate.risk_keys:
            risk[name][1] -= principal + fee  # Conservative all-in exposure.
    # Sells do not release either cash or risk capacity until verified execution.
    return {"account_id": candidate.account_id, "instrument_uid": candidate.instrument_uid,
            "action": candidate.side if lots else "wait", "lots": lots,
            "quantity": str(lots * candidate.lot_size), "currency": candidate.currency,
            "settlement_price_per_unit": _number(candidate.price_per_unit), "estimated_fees": _number(fee),
            "estimated_principal": _number(principal),
            "estimated_net_sale_proceeds": _number(principal - fee) if candidate.side == "sell" and lots else "0",
            "cash_before": _number(before), "cash_after_committed_buys": _number(cash[key]),
            "reserve": _number(reserves[key]), "reason": reason, "source_id": candidate.source_id,
            "quote_as_of": candidate.observed_at.isoformat(), "quote_expires_at": candidate.expires_at.isoformat()}


def plan_allocations(*, context: PlanContext, accounts: Sequence[AccountCash],
                     candidates: Sequence[Candidate], risk_capacities: Sequence[RiskCapacity],
                     now: datetime) -> dict:
    """Build a deterministic draft, never a trade permission or live advice."""
    _aware(now)
    if not isinstance(context, PlanContext) or not context.observed_at <= now < context.expires_at:
        raise ValueError("fresh_confirmed_snapshot_required")
    if any(not isinstance(items, (list, tuple)) or len(items) > MAX_ITEMS
           for items in (accounts, candidates, risk_capacities)):
        raise ValueError("bounded_input_sequences_required")
    with localcontext(CONTEXT):
        cash, reserves, risk = _initial_resources(accounts, risk_capacities)
        _validate_candidates(candidates, cash, risk)
        ordered = sorted(candidates, key=lambda item: (item.priority, item.account_id, item.instrument_uid))
        lines = [_allocate(candidate, cash, reserves, risk, now) for candidate in ordered]
        return {"version": VERSION, "state": "draft", "snapshot_id": context.snapshot_id,
                "strategy_version": context.strategy_version, "created_at": now.isoformat(),
                "expires_at": min([context.expires_at, *(c.expires_at for c in candidates)]).isoformat(),
                "lines": lines, "automatic_order": False, "suitability_complete": False,
                "optimality_claimed": False, "requires_fresh_broker_validation": True,
                "fees_basis": "configured_fixed_and_rate_estimate_rounded_up",
                "sale_proceeds_available_for_buys": False,
                "risk_capacity_remaining": {key: _number(value[1]) for key, value in sorted(risk.items())}}
