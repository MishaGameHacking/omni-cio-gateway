"""Execution state rules, exact quote units and bounded integer-lot allocation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from typing import Any, Literal

from .strategy_assessment import StrategyCandidateFacts, candidate_weight_constraints
from .tbank import TBankInstrumentMetadata, TBankOrderBook, TBankPortfolioPosition

ExecutionMode = Literal["shadow", "sandbox", "live"]
ExecutionRunStatus = Literal[
    "created",
    "running",
    "reconciling",
    "succeeded",
    "cancelled",
    "failed",
]
ExecutionLegStatus = Literal[
    "pending",
    "submitting",
    "submitted",
    "partially_filled",
    "filled",
    "cancel_requested",
    "cancelled",
    "rejected",
    "reconciling",
    "failed",
    "shadow_filled",
]

_PROVIDER_STATUS_TO_LEG: dict[str, ExecutionLegStatus] = {
    "EXECUTION_REPORT_STATUS_NEW": "submitted",
    "EXECUTION_REPORT_STATUS_PARTIALLYFILL": "partially_filled",
    "EXECUTION_REPORT_STATUS_FILL": "filled",
    "EXECUTION_REPORT_STATUS_CANCELLED": "cancelled",
    "EXECUTION_REPORT_STATUS_REJECTED": "rejected",
}


class ExecutionStateError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def provider_leg_status(value: str) -> ExecutionLegStatus:
    try:
        return _PROVIDER_STATUS_TO_LEG[value]
    except KeyError as exc:
        raise ExecutionStateError("provider_order_status_unknown") from exc


def run_status_for_legs(
    statuses: tuple[ExecutionLegStatus, ...],
) -> ExecutionRunStatus:
    if not statuses:
        return "failed"
    if all(status in {"filled", "shadow_filled"} for status in statuses):
        return "succeeded"
    if any(status in {"failed", "rejected"} for status in statuses):
        return "failed"
    if any(status == "cancelled" for status in statuses):
        return "cancelled"
    if any(status == "reconciling" for status in statuses):
        return "reconciling"
    return "running"


def execution_depth(
    book: TBankOrderBook, *, action: str, limit_price: Decimal, cash_price_factor: Decimal
) -> int:
    """Count only native book levels executable at the exact clean RUB order limit."""
    levels = book.asks if action == "buy" else book.bids
    return sum(
        level.quantity_lots
        for level in levels
        if (
            Decimal(level.price) * cash_price_factor <= limit_price
            if action == "buy"
            else Decimal(level.price) * cash_price_factor >= limit_price
        )
    )


def execution_quote(
    metadata: TBankInstrumentMetadata, book: TBankOrderBook, *, slippage_bps: Decimal, now: datetime
) -> dict[str, Any]:
    """Convert native tick prices into exact RUB limits; no foreign nominal or derivatives."""
    if (
        metadata.uid != book.instrument_uid
        or metadata.instrument_type not in {"share", "bond", "etf"}
        or metadata.currency != "RUB"
        or metadata.lot <= 0
        or metadata.min_price_increment is None
        or not book.is_consistent
        or not book.bids
        or not book.asks
        or book.time is None
        or not 0 <= (now - book.time).total_seconds() <= 30
    ):
        raise ExecutionStateError("execution_quote_incomplete_or_stale")
    tick = Decimal(metadata.min_price_increment)
    bid, ask = Decimal(book.bids[0].price), Decimal(book.asks[0].price)
    if not tick.is_finite() or tick <= 0 or not 0 < bid <= ask:
        raise ExecutionStateError("execution_quote_invalid")
    multiplier, nkd = Decimal(1), Decimal(0)
    if metadata.instrument_type == "bond":
        if (
            metadata.nominal is None
            or metadata.nominal.currency != "RUB"
            or metadata.accrued_interest is None
            or metadata.accrued_interest.currency != "RUB"
        ):
            raise ExecutionStateError("execution_bond_nominal_or_accrual_missing")
        multiplier, nkd = (
            Decimal(metadata.nominal.value) / 100,
            Decimal(metadata.accrued_interest.value),
        )
        if multiplier <= 0 or nkd < 0:
            raise ExecutionStateError("execution_bond_valuation_invalid")
    buy = (ask * (1 + slippage_bps / 10000) / tick).to_integral_value(rounding=ROUND_CEILING) * tick
    sell = (bid * (1 - slippage_bps / 10000) / tick).to_integral_value(rounding=ROUND_FLOOR) * tick
    if sell <= 0 or any(
        value * 10**9 != (value * 10**9).to_integral_value()
        for value in (buy * multiplier, sell * multiplier)
    ):
        raise ExecutionStateError("execution_limit_precision_invalid")
    return {
        "instrument_uid": metadata.uid,
        "lot": metadata.lot,
        "buy_limit": buy * multiplier,
        "sell_limit": sell * multiplier,
        "nkd": nkd,
        "mark": bid * multiplier + nkd,
        "cash_price_factor": multiplier,
        "buy_depth": execution_depth(
            book, action="buy", limit_price=buy * multiplier, cash_price_factor=multiplier
        ),
        "sell_depth": execution_depth(
            book, action="sell", limit_price=sell * multiplier, cash_price_factor=multiplier
        ),
        "quote_at": book.time.isoformat(),
        "tick_native": str(tick),
        "price_unit": "percent_nominal" if metadata.instrument_type == "bond" else "RUB",
    }


def strategy_order_plan(
    document: Mapping[str, Any],
    candidates: Sequence[StrategyCandidateFacts],
    selected: Sequence[Mapping[str, Any]],
    positions: Sequence[TBankPortfolioPosition],
    quotes: Mapping[str, Mapping[str, Any]],
    *,
    cash: Decimal,
    blocked_cash: Decimal,
    commission_bps: Decimal,
    now: datetime,
    max_order: Decimal,
    max_daily: Decimal,
) -> dict[str, Any]:
    """No-margin integer orders, sells first, using only broker position quantities."""
    by_uid = {row.instrument_uid: row for row in candidates}
    held: dict[str, int] = {}
    free: dict[str, int] = {}
    cost_basis: dict[str, Decimal] = {}
    for position in positions:
        if position.instrument_type == "currency" or Decimal(position.quantity) == 0:
            continue
        uid = position.instrument_uid
        quote = quotes.get(uid)
        count = Decimal(position.quantity_lots)
        blocked = Decimal(position.blocked_lots)
        if (
            uid in held
            or quote is None
            or count != int(count)
            or count < 0
            or blocked < 0
            or blocked != int(blocked)
            or Decimal(position.quantity) != count * quote["lot"]
        ):
            raise ExecutionStateError("execution_inventory_incomplete")
        held[uid] = int(count)
        free[uid] = 0 if position.blocked else max(0, int(count - blocked))
        average = position.average_price_fifo
        if average is not None and average.currency == "RUB":
            cost_basis[uid] = Decimal(average.value) * quote["lot"]
    if cash < 0 or blocked_cash < 0 or blocked_cash > cash:
        raise ExecutionStateError("execution_cash_inconsistent")
    nav = cash + sum(
        (Decimal(count) * quotes[uid]["lot"] * quotes[uid]["mark"] for uid, count in held.items()),
        Decimal(0),
    )
    if nav <= 0:
        raise ExecutionStateError("execution_capital_missing")
    weights = {
        row["instrument_uid"]: Decimal(str(row["target_weight_percent"])) for row in selected
    }
    reserve = (
        max(
            Decimal(document["profile"]["reserve_rub"])
            + Decimal(document["profile"]["planned_withdrawal_rub"]),
            nav * Decimal(document["allocation"]["cash"]) / 100,
        )
        + blocked_cash
    )
    available = cash
    remaining = min(max_daily, nav * Decimal(document["policy"]["turnover_budget_percent"]) / 100)
    participation = Decimal(document["policy"]["max_daily_turnover_participation_percent"]) / 100
    band = Decimal(document["policy"]["no_trade_band_percent"])
    benefit = Decimal(document["policy"]["min_replace_benefit_rub"])
    tax_rate = Decimal(document["policy"]["securities_tax_rate_percent"]) / 100
    legs = []
    projected = dict(held)
    for action in ("sell", "buy"):
        for uid in sorted(set(weights) | set(held)):
            quote, candidate = quotes[uid], by_uid.get(uid)
            if candidate is None:
                raise ExecutionStateError("execution_held_evidence_missing")
            mark = quote["mark"] * quote["lot"]
            current, target = held.get(uid, 0) * mark, nav * weights.get(uid, Decimal(0)) / 100
            delta = int(target / mark) - held.get(uid, 0)
            if (
                not delta
                or (delta > 0) != (action == "buy")
                or abs(target - current) / nav * 100 <= band
            ):
                continue
            volume = candidate.facts.get("daily_volume_lots")
            if volume is None or volume.available_at > now:
                raise ExecutionStateError("execution_volume_missing")
            volume_cap = int(Decimal(str(volume.value)) * participation)
            amount = (quote[action + "_limit"] + quote["nkd"]) * quote["lot"]
            fee = amount * commission_bps / 10000
            lots = min(
                abs(delta),
                volume_cap,
                int(quote[action + "_depth"]),
                int(max_order / (amount + fee)),
                int(remaining / (amount + fee)),
            )
            if action == "buy":
                lots = min(lots, max(0, int((available - reserve) / (amount + fee))))
            else:
                lots = min(lots, free.get(uid, 0))
            if lots <= 0:
                continue
            reduction = abs(target - current) - abs(
                target - current - (lots if action == "buy" else -lots) * mark
            )
            if reduction - lots * fee < benefit:
                continue
            tax = Decimal(0)
            if action == "sell" and tax_rate:
                if uid not in cost_basis:
                    raise ExecutionStateError("execution_cost_basis_missing")
                tax = max(Decimal(0), amount - fee - cost_basis[uid]) * lots * tax_rate
            gross, commission = lots * amount, lots * fee
            spend = gross + commission
            proceeds = max(Decimal(0), gross - commission - tax)
            available += proceeds if action == "sell" else -spend
            remaining -= spend
            projected[uid] = projected.get(uid, 0) + (lots if action == "buy" else -lots)
            legs.append(
                {
                    "action": action,
                    "instrument_uid": uid,
                    "ticker": candidate.ticker,
                    "lots": lots,
                    "lot_size": quote["lot"],
                    "limit_price": str(quote[action + "_limit"]),
                    "limit_price_type": "currency",
                    "native_price_unit": quote["price_unit"],
                    "quote_at": quote["quote_at"],
                    "gross_amount_rub": str(gross),
                    "commission_cap_rub": str(commission),
                    "tax_reserve_rub": str(tax),
                    "max_spend_rub": str(spend) if action == "buy" else None,
                    "min_proceeds_rub": str(proceeds) if action == "sell" else None,
                }
            )
    after_nav = available + sum(
        (
            Decimal(count) * quotes[uid]["lot"] * quotes[uid]["mark"]
            for uid, count in projected.items()
        ),
        Decimal(0),
    )
    projected_weights = {
        uid: Decimal(count) * quotes[uid]["lot"] * quotes[uid]["mark"] / after_nav * 100
        for uid, count in projected.items()
        if count
    }
    blockers = candidate_weight_constraints(document, candidates, projected_weights, as_of=now)
    if available < reserve:
        blockers.append("cash_reserve")
    return {
        "legs": legs,
        "blockers": blockers,
        "nav_rub": str(nav),
        "cash_before_rub": str(cash),
        "blocked_cash_rub": str(blocked_cash),
        "initial_lots": held,
        "cash_after_rub": str(available),
        "reserve_rub": str(reserve),
        "projected_weights": {uid: str(value) for uid, value in projected_weights.items()},
        "gross_turnover_rub": str(
            sum(
                (
                    Decimal(leg["gross_amount_rub"]) + Decimal(leg["commission_cap_rub"])
                    for leg in legs
                ),
                Decimal(0),
            )
        ),
    }
