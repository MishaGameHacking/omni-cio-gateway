"""Chronological, read-only portfolio research from explicit observed daily bars.

The signal is frozen on the training window. Integer orders are sized from the
previous close and filled at the following open, with cash and volume limits.
Unadjusted price research and a verified cash-flow history are separate bases.
No result estimates a personal probability of making a profit.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import ROUND_CEILING, Decimal
from typing import Any, Literal

from .strategy import document_hash, expected_shortfall, normalize_document, strategy_rule_set
from .strategy_assessment import StrategyCandidateFacts, StrategyFact, select_strategy_candidates
from .tbank import TBankHistoricCandle

ResearchBasis = Literal["unadjusted_price", "verified_total_return"]
HISTORY_SOURCE = "https://developer.tbank.ru/invest/api/market-data-service-get-candles"
MAX_RESEARCH_ASSETS = 100
RESEARCH_ENGINE_VERSION = "1.2.0"
MAX_RESEARCH_DAYS = 1095
MIN_TRAIN_OBSERVATIONS = 60
MIN_TEST_OBSERVATIONS = 20
_ZERO, _ONE, _HUNDRED = Decimal(0), Decimal(1), Decimal(100)
_DAY = timedelta(days=1)
_HTTPS_PREFIX = "https://"


@dataclass(frozen=True, slots=True)
class HistoricalCashflow:
    """Verified RUB distribution per security; entitlement and payment differ."""

    entitlement_at: datetime
    paid_at: datetime
    amount_per_unit_rub: Decimal
    source_url: str
    kind: Literal["income", "principal"] = "income"


@dataclass(frozen=True, slots=True)
class FactorObservation:
    time: datetime
    available_at: datetime
    growth_change: Decimal
    inflation_change: Decimal
    source_url: str


@dataclass(frozen=True, slots=True)
class HistoricalSplit:
    time: datetime
    ratio: Decimal
    source_url: str


@dataclass(frozen=True, slots=True)
class BondValuation:
    time: datetime
    nominal_rub: Decimal
    accrued_interest_open_rub: Decimal
    accrued_interest_close_rub: Decimal
    source_url: str


@dataclass(frozen=True, slots=True)
class ResearchAsset:
    candidate: StrategyCandidateFacts
    candles: tuple[TBankHistoricCandle, ...]
    basis: ResearchBasis = "unadjusted_price"
    cashflows: tuple[HistoricalCashflow, ...] = ()
    corporate_action_dates: tuple[datetime, ...] = ()
    lot_history_verified: bool = False
    cashflow_history_verified: bool = False
    verification_source: str = ""
    factors: tuple[FactorObservation, ...] = ()
    splits: tuple[HistoricalSplit, ...] = ()
    bond_valuations: tuple[BondValuation, ...] = ()
    observed_cashflows: tuple[HistoricalCashflow, ...] = ()
    provider_observations: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ResearchCosts:
    commission_bps: Decimal
    slippage_bps: Decimal


def _decimal(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, Decimal, int)):
        raise ValueError("research_decimal_invalid")
    try:
        number = Decimal(value)
    except ArithmeticError as exc:
        raise ValueError("research_decimal_invalid") from exc
    if not number.is_finite() or abs(number) > Decimal("1e15"):
        raise ValueError("research_decimal_invalid")
    return number


def _text(value: Decimal) -> str:
    return format(value, "f")


def _returns(prices: Sequence[Decimal]) -> tuple[Decimal, ...]:
    return tuple(
        current / previous - 1 for previous, current in zip(prices, prices[1:], strict=False)
    )


def _volatility(returns: Sequence[Decimal]) -> Decimal | None:
    if len(returns) < 2:
        return None
    mean = sum(returns, _ZERO) / len(returns)
    variance = sum(((item - mean) ** 2 for item in returns), _ZERO) / (len(returns) - 1)
    return (variance * 252).sqrt() * 100


def _drawdown(prices: Sequence[Decimal]) -> Decimal:
    peak, worst = prices[0], _ZERO
    for price in prices:
        peak = max(peak, price)
        worst = max(worst, (peak - price) / peak * 100)
    return worst


def history_candidate(
    candidate: StrategyCandidateFacts,
    candles: Sequence[TBankHistoricCandle],
    *,
    as_of: datetime,
    factors: Sequence[FactorObservation] = (),
    cashflows: Sequence[HistoricalCashflow] = (),
    document: Mapping[str, Any] | None = None,
    costs: ResearchCosts | None = None,
) -> StrategyCandidateFacts:
    """Only completed bars whose whole daily interval was known by as_of."""
    past = [bar for bar in candles if bar.is_complete and bar.time + _DAY <= as_of]
    if not past:
        return candidate
    prices = [_decimal(bar.close) for bar in past]
    values: dict[str, Decimal | int] = {
        "history_observations": len(past),
        "price_rub": prices[-1],
        "daily_volume_lots": Decimal(sum(bar.volume_lots for bar in past[-60:])) / len(past[-60:]),
        "momentum_percent": (prices[-1] / prices[max(0, len(prices) - 64)] - 1) * 100,
        "max_drawdown_percent": _drawdown(prices),
    }
    volatility = _volatility(_returns(prices))
    if volatility is not None:
        values["volatility_percent"] = volatility
    facts = dict(candidate.facts)
    facts.update(
        {
            key: StrategyFact(value, past[-1].time + _DAY, HISTORY_SOURCE)
            for key, value in values.items()
        }
    )
    if factors:
        for key in ("growth_beta", "inflation_beta", "factor_observations"):
            facts.pop(key, None)
        facts.update(_factor_facts(past, factors, as_of))
    if cashflows:
        facts.update(
            _cashflow_facts(candidate, cashflows, prices[-1], as_of, document=document, costs=costs)
        )
    return StrategyCandidateFacts(
        instrument_uid=candidate.instrument_uid,
        ticker=candidate.ticker,
        asset_class=candidate.asset_class,
        lot_size=candidate.lot_size,
        currency=candidate.currency,
        facts=facts,
        constituents=candidate.constituents,
        fact_history=candidate.fact_history,
    )


def _cashflow_facts(
    candidate: StrategyCandidateFacts,
    cashflows: Sequence[HistoricalCashflow],
    price: Decimal,
    as_of: datetime,
    *,
    document: Mapping[str, Any] | None,
    costs: ResearchCosts | None,
) -> dict[str, StrategyFact]:
    """Trailing observed income, never future payouts or principal disguised as yield."""
    paid = [
        event
        for event in cashflows
        if event.kind == "income" and as_of - timedelta(days=365) < event.paid_at <= as_of
    ]
    if not paid or price <= 0:
        return {}
    gross = sum((event.amount_per_unit_rub for event in paid), _ZERO) / price * 100
    source = max(paid, key=lambda event: event.paid_at).source_url
    facts = {"cashflow_yield_percent": StrategyFact(gross, as_of, source)}
    if candidate.asset_class == "shares":
        facts.update(
            dividend_yield_percent=StrategyFact(gross, as_of, source),
            dividend_declared=StrategyFact(True, as_of, source),
        )
    if document is not None and costs is not None:
        tax, horizon = (
            document["policy"]["securities_tax_rate_percent"],
            document["profile"]["horizon_months"],
        )
        if tax is not None and horizon is not None and Decimal(horizon) > 0:
            net = gross * (1 - Decimal(tax) / 100)
            net -= (costs.commission_bps + costs.slippage_bps) * 2 / 100 * 12 / Decimal(horizon)
            facts["net_yield_percent"] = StrategyFact(net, as_of, source)
    return facts


def _factor_facts(
    bars: Sequence[TBankHistoricCandle],
    factors: Sequence[FactorObservation],
    as_of: datetime,
) -> dict[str, StrategyFact]:
    """OLS with intercept and both factors; only observations published by the cutoff."""
    published = {row.time.date(): row for row in factors if row.available_at <= as_of}
    rows = []
    for before, after in zip(bars, bars[1:], strict=False):
        factor = published.get(after.time.date())
        if factor is not None:
            rows.append((factor, _decimal(after.close) / _decimal(before.close) - 1))
    if len(rows) < 60:
        return {}
    n = Decimal(len(rows))
    means = [
        sum((row[0].growth_change for row in rows), _ZERO) / n,
        sum((row[0].inflation_change for row in rows), _ZERO) / n,
        sum((row[1] for row in rows), _ZERO) / n,
    ]
    centered = [
        (row.growth_change - means[0], row.inflation_change - means[1], value - means[2])
        for row, value in rows
    ]
    xx = sum((x * x for x, _, _ in centered), _ZERO)
    zz = sum((z * z for _, z, _ in centered), _ZERO)
    xz = sum((x * z for x, z, _ in centered), _ZERO)
    xy = sum((x * y for x, _, y in centered), _ZERO)
    zy = sum((z * y for _, z, y in centered), _ZERO)
    determinant = xx * zz - xz * xz
    if determinant <= 0:
        return {}
    available = max(max(row.available_at, row.time + _DAY) for row, _ in rows)
    source = rows[-1][0].source_url
    values: dict[str, Decimal | int] = {
        "growth_beta": (xy * zz - zy * xz) / determinant,
        "inflation_beta": (zy * xx - xy * xz) / determinant,
        "factor_observations": len(rows),
    }
    return {key: StrategyFact(value, available, source) for key, value in values.items()}


def _validate_bar_values(bar: TBankHistoricCandle) -> None:
    if type(bar.volume_lots) is not int or bar.volume_lots < 0:
        raise ValueError("research_invalid_volume")
    prices = tuple(_decimal(value) for value in (bar.open, bar.high, bar.low, bar.close))
    opening, high, low, close = prices
    if min(prices) <= 0 or low > min(opening, close) or high < max(opening, close) or low > high:
        raise ValueError("research_invalid_ohlc")


def _validated_bars(
    asset: ResearchAsset,
    from_at: datetime,
    to_at: datetime,
) -> tuple[TBankHistoricCandle, ...]:
    if len(asset.candles) > MAX_RESEARCH_DAYS + 2:
        raise ValueError("research_too_many_daily_bars")
    result = []
    previous: datetime | None = None
    for bar in asset.candles:
        if bar.time.tzinfo is None or (
            previous is not None
            and (
                bar.time <= previous
                or bar.time.astimezone(UTC).date() == previous.astimezone(UTC).date()
            )
        ):
            raise ValueError("research_non_chronological_bars")
        previous = bar.time
        if (
            bar.instrument_uid != asset.candidate.instrument_uid
            or bar.source != "CANDLE_SOURCE_EXCHANGE"
        ):
            raise ValueError("research_series_identity_or_source")
        if not bar.is_complete or bar.time < from_at or bar.time + _DAY > to_at:
            continue
        _validate_bar_values(bar)
        result.append(bar)
    return tuple(result)


def _discontinuities(bars: Sequence[TBankHistoricCandle]) -> list[str]:
    reasons: set[str] = set()
    for previous, current in zip(bars, bars[1:], strict=False):
        if abs(_decimal(current.open) / _decimal(previous.close) - 1) >= Decimal("0.5"):
            reasons.add("price_discontinuity_requires_review")
        if current.time - previous.time > timedelta(days=14):
            reasons.add("history_gap_requires_review")
    return sorted(reasons)


def _cashflow_reasons(events: Sequence[HistoricalCashflow]) -> list[str]:
    reasons = []
    for event in events:
        if (
            event.entitlement_at.tzinfo is None
            or event.paid_at.tzinfo is None
            or event.paid_at < event.entitlement_at
            or not event.amount_per_unit_rub.is_finite()
            or event.amount_per_unit_rub < 0
            or not event.source_url.startswith(_HTTPS_PREFIX)
            or event.kind not in {"income", "principal"}
        ):
            reasons.append("invalid_distribution_event")
    keys = [(event.entitlement_at, event.paid_at, event.kind) for event in events]
    if len(keys) != len(set(keys)):
        reasons.append("duplicate_distribution_event")
    return reasons


def _corporate_action_reasons(
    asset: ResearchAsset, from_at: datetime, to_at: datetime
) -> list[str]:
    reasons = []
    for when in asset.corporate_action_dates:
        if when.tzinfo is None:
            reasons.append("corporate_action_time_missing")
        elif from_at <= when <= to_at and not any(split.time == when for split in asset.splits):
            reasons.append("corporate_action_requires_adjustment")
    if any(
        split.time.tzinfo is None
        or not split.ratio.is_finite()
        or split.ratio <= 0
        or not split.source_url.startswith(_HTTPS_PREFIX)
        for split in asset.splits
    ):
        reasons.append("split_evidence_invalid")
    if len({split.time for split in asset.splits}) != len(asset.splits):
        reasons.append("duplicate_split_event")
    return reasons


def _bond_history_reasons(asset: ResearchAsset, from_at: datetime, to_at: datetime) -> list[str]:
    reasons = []
    if asset.bond_valuations:
        values = {row.time.date(): row for row in asset.bond_valuations}
        if len(values) != len(asset.bond_valuations) or any(
            bar.time.date() not in values
            for bar in asset.candles
            if from_at <= bar.time and bar.time + _DAY <= to_at
        ):
            reasons.append("bond_valuation_history_incomplete")
        if any(
            row.time.tzinfo is None
            or not row.source_url.startswith(_HTTPS_PREFIX)
            or any(
                not number.is_finite() or number < 0
                for number in (
                    row.nominal_rub,
                    row.accrued_interest_open_rub,
                    row.accrued_interest_close_rub,
                )
            )
            or row.nominal_rub <= 0
            for row in asset.bond_valuations
        ):
            reasons.append("bond_valuation_history_invalid")
    return reasons


def _factor_history_reasons(asset: ResearchAsset) -> list[str]:
    reasons = []
    if any(
        row.time.tzinfo is None
        or row.available_at.tzinfo is None
        or row.available_at < row.time
        or not row.source_url.startswith(_HTTPS_PREFIX)
        or not row.growth_change.is_finite()
        or not row.inflation_change.is_finite()
        for row in asset.factors
    ):
        reasons.append("factor_history_invalid")
    if len({row.time.date() for row in asset.factors}) != len(asset.factors):
        reasons.append("factor_history_duplicate")
    return reasons


def _asset_reasons(asset: ResearchAsset, from_at: datetime, to_at: datetime) -> list[str]:
    reasons = []
    if asset.basis not in {"unadjusted_price", "verified_total_return"}:
        reasons.append("unsupported_return_basis")
    if asset.basis == "verified_total_return" and not (
        asset.lot_history_verified
        and asset.cashflow_history_verified
        and asset.verification_source.startswith(_HTTPS_PREFIX)
    ):
        reasons.append("total_return_basis_not_verified")
    if asset.basis == "unadjusted_price" and asset.cashflows:
        reasons.append("cashflows_require_verified_basis")
    if (
        asset.basis == "verified_total_return"
        and asset.candidate.asset_class == "bonds"
        and not asset.bond_valuations
    ):
        reasons.append("bond_principal_and_accrual_history_required")
    reasons.extend(_corporate_action_reasons(asset, from_at, to_at))
    reasons.extend(_bond_history_reasons(asset, from_at, to_at))
    reasons.extend(_factor_history_reasons(asset))
    reasons.extend(_cashflow_reasons(asset.cashflows))
    return sorted(set(reasons))


@dataclass(slots=True)
class _Simulation:
    cash: Decimal
    lots: dict[str, int]
    costs: Decimal = _ZERO
    fees: Decimal = _ZERO
    slippage: Decimal = _ZERO
    trades: int = 0
    risk_stopped: bool = False
    receivables: list[tuple[datetime, Decimal, bool]] = field(default_factory=list)
    accrued_events: set[tuple[str, int]] = field(default_factory=set)
    curve: list[dict[str, str]] = field(default_factory=list)
    cost_basis: dict[str, Decimal] = field(default_factory=dict)
    taxes: Decimal = _ZERO
    tax_rate: Decimal = _ZERO
    applied_splits: set[tuple[str, int]] = field(default_factory=set)


def _order(
    state: _Simulation,
    uid: str,
    delta: int,
    *,
    opening: Decimal,
    lot: int,
    remaining_turnover: Decimal,
    minimum_cash: Decimal,
    volume_limit: int,
    costs: ResearchCosts,
) -> Decimal:
    if not delta or not volume_limit or remaining_turnover <= 0:
        return _ZERO
    direction = 1 if delta > 0 else -1
    execution = opening * (1 + direction * costs.slippage_bps / 10000)
    per_lot = execution * lot
    fee_per_lot = per_lot * costs.commission_bps / 10000
    amount = min(abs(delta), volume_limit, int(remaining_turnover / per_lot))
    if direction == 1:
        capacity = max(_ZERO, state.cash - minimum_cash)
        amount = min(amount, int(capacity / (per_lot + fee_per_lot)))
    else:
        amount = min(amount, state.lots[uid])
    if amount <= 0:
        return _ZERO
    fee = amount * fee_per_lot
    slip = amount * lot * abs(execution - opening)
    if direction == 1:
        state.cost_basis[uid] = state.cost_basis.get(uid, _ZERO) + amount * per_lot + fee
    else:
        sold_basis = state.cost_basis.get(uid, _ZERO) * amount / state.lots[uid]
        state.cost_basis[uid] = state.cost_basis.get(uid, _ZERO) - sold_basis
        tax = max(_ZERO, amount * per_lot - fee - sold_basis) * state.tax_rate
        state.taxes += tax
        state.cash -= tax
    state.cash -= direction * amount * per_lot + fee
    state.lots[uid] += direction * amount
    state.fees += fee
    state.slippage += slip
    state.costs += fee + slip
    state.trades += 1
    return amount * per_lot


def _accrue_distributions(
    state: _Simulation,
    asset: ResearchAsset,
    *,
    start: datetime,
    through: datetime,
    inclusive: bool,
) -> None:
    for index, event in enumerate(asset.cashflows):
        key = (asset.candidate.instrument_uid, index)
        reached = event.entitlement_at <= through if inclusive else event.entitlement_at < through
        if start <= event.entitlement_at and reached and key not in state.accrued_events:
            state.accrued_events.add(key)
            entitlement = state.lots[asset.candidate.instrument_uid] * asset.candidate.lot_size
            if entitlement:
                amount = entitlement * event.amount_per_unit_rub
                state.receivables.append((event.paid_at, amount, event.kind == "income"))
                if event.kind == "principal":
                    uid = asset.candidate.instrument_uid
                    state.cost_basis[uid] = max(_ZERO, state.cost_basis.get(uid, _ZERO) - amount)


def _distributions(
    state: _Simulation,
    assets: Sequence[ResearchAsset],
    *,
    start: datetime,
    through: datetime,
    inclusive: bool,
) -> None:
    for asset in assets:
        _accrue_distributions(state, asset, start=start, through=through, inclusive=inclusive)
    unpaid = []
    for when, amount, taxable in state.receivables:
        reached = when <= through if inclusive else when < through
        if reached:
            tax = amount * state.tax_rate if taxable else _ZERO
            state.taxes += tax
            state.cash += amount - tax
        else:
            unpaid.append((when, amount, taxable))
    state.receivables = unpaid


def _nav(
    state: _Simulation, assets: Sequence[ResearchAsset], prices: Mapping[str, Decimal]
) -> Decimal:
    return (
        state.cash
        + sum(
            (
                state.lots[asset.candidate.instrument_uid]
                * asset.candidate.lot_size
                * prices[asset.candidate.instrument_uid]
                for asset in assets
            ),
            _ZERO,
        )
        + sum((amount for _, amount, _ in state.receivables), _ZERO)
    )


@dataclass(frozen=True, slots=True)
class _RebalanceSession:
    previous: datetime
    opening: datetime
    previous_nav: Decimal


def _rebalance_change(
    state: _Simulation,
    asset: ResearchAsset,
    previous: TBankHistoricCandle,
    weight: Decimal,
    document: Mapping[str, Any],
    costs: ResearchCosts,
    session: _RebalanceSession,
    participation: Decimal,
) -> int:
    uid = asset.candidate.instrument_uid
    target = _ZERO if state.risk_stopped else session.previous_nav * weight / 100
    split_factor = _split_factor(asset.splits, session.previous, session.opening)
    price = _decimal(previous.close) / split_factor * asset.candidate.lot_size
    change = int(target / price) - state.lots[uid]
    if not state.risk_stopped:
        current = state.lots[uid] * price
        band = _decimal(document["policy"]["no_trade_band_percent"] or "0")
        minimum = _decimal(document["policy"]["min_replace_benefit_rub"] or "0")
        # A geometric improvement in allocation, explicitly not forecast profit.
        reduction = abs(target - current) - abs(target - current - change * price)
        estimated_cost = abs(change * price) * (costs.commission_bps + costs.slippage_bps) / 10000
        if (
            abs(target - current) / session.previous_nav * 100 <= band
            or reduction - estimated_cost < minimum
        ):
            change = 0
    days = document["profile"]["liquidity_horizon_days"]
    if days is not None:
        exit_capacity = int(previous.volume_lots * split_factor * participation * Decimal(days))
        change = min(change, exit_capacity - state.lots[uid])
    return change


def _apply_rebalance(
    state: _Simulation,
    assets: Sequence[ResearchAsset],
    panel: Mapping[str, Mapping[datetime, TBankHistoricCandle]],
    weights: Mapping[str, Decimal],
    document: Mapping[str, Any],
    costs: ResearchCosts,
    session: _RebalanceSession,
) -> None:
    """Size from the previous close, then sell before buying at this session's open."""
    participation = Decimal(document["policy"]["max_daily_turnover_participation_percent"]) / 100
    turnover_fraction = Decimal(document["policy"]["turnover_budget_percent"]) / 100
    cash_target = max(_ZERO, 1 - sum(weights.values(), _ZERO) / 100)
    reserve = sum(
        (
            _decimal(document["profile"][key])
            for key in ("reserve_rub", "planned_withdrawal_rub")
            if document["profile"][key] is not None
        ),
        _ZERO,
    )
    turnover = session.previous_nav * turnover_fraction
    targets = {
        asset.candidate.instrument_uid: _rebalance_change(
            state,
            asset,
            panel[asset.candidate.instrument_uid][session.previous],
            weights[asset.candidate.instrument_uid],
            document,
            costs,
            session,
            participation,
        )
        for asset in assets
    }
    minimum_cash = max(reserve, session.previous_nav * cash_target)
    for side in (-1, 1):
        for asset in assets:
            uid = asset.candidate.instrument_uid
            delta = targets[uid]
            if (delta > 0) != (side > 0) or delta == 0:
                continue
            turnover -= _order(
                state,
                uid,
                delta,
                opening=_decimal(panel[uid][session.opening].open),
                lot=asset.candidate.lot_size,
                remaining_turnover=turnover,
                minimum_cash=minimum_cash,
                volume_limit=int(
                    panel[uid][session.previous].volume_lots
                    * _split_factor(asset.splits, session.previous, session.opening)
                    * participation
                ),
                costs=costs,
            )


def _simulate(
    assets: Sequence[ResearchAsset],
    panel: Mapping[str, Mapping[datetime, TBankHistoricCandle]],
    times: Sequence[datetime],
    weights: Mapping[str, Decimal],
    document: Mapping[str, Any],
    capital: Decimal,
    costs: ResearchCosts,
    *,
    rebalance_sessions: int | None,
) -> _Simulation:
    ids = [asset.candidate.instrument_uid for asset in assets]
    state = _Simulation(capital, dict.fromkeys(ids, 0))
    tax = document["policy"]["securities_tax_rate_percent"]
    state.tax_rate = _ZERO if tax is None else _decimal(tax) / 100
    state.curve.append(
        {
            "time": (times[0] + _DAY).isoformat(),
            "nav_rub": _text(capital),
            "cash_rub": _text(capital),
            "receivables_rub": "0",
        }
    )
    previous_nav = peak = capital
    limit = document["profile"]["max_drawdown_percent"]
    for index, when in enumerate(times[1:]):
        previous = times[index]
        _apply_splits(state, assets, previous, when)
        # Entitlement before today's trades; paid cash cannot be spent before its date.
        _distributions(state, assets, start=times[1], through=when, inclusive=True)
        if rebalance_sessions is not None and limit is not None:
            state.risk_stopped |= (peak - previous_nav) / peak * 100 > Decimal(limit)
        rebalance = index == 0 or (
            rebalance_sessions is not None and index % rebalance_sessions == 0
        )
        if rebalance or state.risk_stopped:
            _apply_rebalance(
                state,
                assets,
                panel,
                weights,
                document,
                costs,
                _RebalanceSession(previous, when, previous_nav),
            )
        closing_time = when + _DAY
        # Same-day distributions cannot fund orders already filled at the open.
        _distributions(state, assets, start=times[1], through=closing_time, inclusive=False)
        prices = {uid: _decimal(panel[uid][when].close) for uid in ids}
        previous_nav = _nav(state, assets, prices)
        peak = max(peak, previous_nav)
        state.curve.append(
            {
                "time": closing_time.isoformat(),
                "nav_rub": _text(previous_nav),
                "cash_rub": _text(state.cash),
                "receivables_rub": _text(sum((a for _, a, _ in state.receivables), _ZERO)),
            }
        )
    return state


def _split_factor(
    splits: Sequence[HistoricalSplit], before: datetime, through: datetime
) -> Decimal:
    factor = _ONE
    for split in splits:
        if before < split.time <= through:
            factor *= split.ratio
    return factor


def _apply_splits(
    state: _Simulation,
    assets: Sequence[ResearchAsset],
    before: datetime,
    through: datetime,
) -> None:
    for asset in assets:
        uid = asset.candidate.instrument_uid
        for index, split in enumerate(asset.splits):
            key = (uid, index)
            if before < split.time <= through and key not in state.applied_splits:
                lots = Decimal(state.lots[uid]) * split.ratio
                if lots != int(lots):
                    raise ValueError("fractional_split_cash_settlement_required")
                state.lots[uid] = int(lots)
                state.applied_splits.add(key)


def split_adjusted_history(
    bars: Sequence[TBankHistoricCandle],
    splits: Sequence[HistoricalSplit],
    as_of: datetime,
) -> tuple[TBankHistoricCandle, ...]:
    """Normalize only splits already effective at the evaluation cutoff for price signals."""
    result = []
    for bar in bars:
        factor = _split_factor(splits, bar.time, as_of)
        if factor == 1:
            result.append(bar)
        else:
            result.append(
                replace(
                    bar,
                    open=_text(_decimal(bar.open) / factor) if bar.open is not None else None,
                    high=_text(_decimal(bar.high) / factor) if bar.high is not None else None,
                    low=_text(_decimal(bar.low) / factor) if bar.low is not None else None,
                    close=_text(_decimal(bar.close) / factor),
                    volume_lots=int(bar.volume_lots * factor),
                )
            )
    return tuple(result)


def _metrics(state: _Simulation, capital: Decimal) -> dict[str, Any]:
    navs = [Decimal(row["nav_rub"]) for row in state.curve]
    changes = _returns(navs)
    losses = sorted(-value * 100 for value in changes)
    count = len(losses)
    quantile = int((Decimal(count) * Decimal("0.95")).to_integral_value(rounding=ROUND_CEILING)) - 1
    probability = _ONE / count
    masses = [probability] * (count - 1)
    masses.append(_ONE - sum(masses, _ZERO))
    volatility = _volatility(changes)
    return {
        "net_return_percent": _text((navs[-1] / capital - 1) * 100),
        "max_drawdown_percent": _text(_drawdown(navs)),
        "annualized_volatility_percent": None if volatility is None else _text(volatility),
        "var_95_percent": _text(max(_ZERO, losses[max(0, quantile)])),
        "expected_shortfall_95_percent": _text(max(_ZERO, expected_shortfall(losses, masses))),
        "transaction_costs_rub": _text(state.costs),
        "taxes_rub": _text(state.taxes),
        "commissions_rub": _text(state.fees),
        "slippage_rub": _text(state.slippage),
        "trades": state.trades,
        "ending_cash_rub": _text(state.cash),
        "ending_nav_rub": _text(navs[-1]),
        "observed_positive_periods": sum(value > 0 for value in changes),
        "return_observations": count,
        "risk_limit_triggered": state.risk_stopped,
    }


def _validated_research_capital(
    from_at: datetime,
    to_at: datetime,
    observed: datetime,
    asset_count: int,
    initial_capital_rub: Decimal,
    costs: ResearchCosts,
) -> Decimal:
    if (
        from_at.tzinfo is None
        or to_at.tzinfo is None
        or observed.tzinfo is None
        or not from_at < to_at <= observed
        or to_at - from_at > timedelta(days=MAX_RESEARCH_DAYS)
        or asset_count > MAX_RESEARCH_ASSETS
    ):
        raise ValueError("research_window_invalid")
    capital = _decimal(initial_capital_rub)
    if not 0 < capital <= Decimal("1e12"):
        raise ValueError("research_capital_invalid")
    if any(
        not 0 <= _decimal(value) <= 1000 for value in (costs.commission_bps, costs.slippage_bps)
    ):
        raise ValueError("research_costs_invalid")
    return capital


def _prepare_research_assets(
    assets: Sequence[ResearchAsset],
    from_at: datetime,
    to_at: datetime,
    split: datetime,
    document: Mapping[str, Any],
    costs: ResearchCosts,
    engine_version: str,
) -> tuple[list[ResearchAsset], list[dict[str, Any]]]:
    diagnostics: list[dict[str, Any]] = []
    clean_assets = []
    for asset in assets:
        reasons = _asset_reasons(asset, from_at, to_at)
        try:
            bars = _validated_bars(asset, from_at, to_at)
        except ValueError as exc:
            bars = ()
            reasons.append(str(exc))
        training = tuple(bar for bar in bars if bar.time + _DAY <= split)
        if len(training) < MIN_TRAIN_OBSERVATIONS:
            reasons.append("insufficient_training_history")
        prices = [_decimal(bar.close) for bar in bars]
        diagnostics.append(
            {
                "instrument_uid": asset.candidate.instrument_uid,
                "ticker": asset.candidate.ticker,
                "observations": len(bars),
                "train_observations": len(training),
                "status": "observed" if not reasons else "incomplete",
                "reasons": reasons,
                "price_return_percent": _text((prices[-1] / prices[0] - 1) * 100)
                if prices
                else None,
            }
        )
        clean_assets.append(
            replace(
                asset,
                candles=bars,
                candidate=history_candidate(
                    asset.candidate,
                    split_adjusted_history(training, asset.splits, split),
                    as_of=split,
                    factors=asset.factors,
                    cashflows=asset.observed_cashflows if engine_version != "1.1.0" else (),
                    document=document,
                    costs=costs,
                ),
            )
        )
    return clean_assets, diagnostics


def _selected_evidence_requirements(
    data: Mapping[str, Any],
    selection: Mapping[str, Any],
    assets: Sequence[ResearchAsset],
    diagnostics: Sequence[dict[str, Any]],
    bases: set[ResearchBasis],
) -> set[str]:
    missing: set[str] = set()
    if not assets:
        missing.update(selection["missing_requirements"] or ["eligible_training_assets"])
    if len(bases) > 1:
        missing.add("mixed_return_bases")
    by_uid = {row["instrument_uid"]: row for row in diagnostics}
    for asset in assets:
        diagnostic = by_uid[asset.candidate.instrument_uid]
        missing.update(diagnostic["reasons"])
        breaks = _discontinuities(
            split_adjusted_history(
                asset.candles,
                asset.splits,
                asset.candles[-1].time if asset.candles else datetime.min.replace(tzinfo=UTC),
            )
        )
        missing.update(breaks)
        if breaks:
            diagnostic["status"] = "incomplete"
            diagnostic["reasons"] = sorted(set(diagnostic["reasons"] + breaks))
    for key in ("max_daily_turnover_participation_percent", "turnover_budget_percent"):
        if data["policy"][key] is None:
            missing.add("policy." + key)
    return missing


def _common_research_times(
    panel: Mapping[str, Mapping[datetime, TBankHistoricCandle]],
    split: datetime,
) -> tuple[int, list[datetime], list[datetime], set[str]]:
    common = set.intersection(*(set(series) for series in panel.values())) if panel else set()
    missing = set()
    if panel and any(set(series) != common for series in panel.values()):
        missing.add("unaligned_history")
    training_times = sorted(when for when in common if when + _DAY <= split)
    test_times = sorted(when for when in common if when >= split)
    if len(training_times) < MIN_TRAIN_OBSERVATIONS:
        missing.add("insufficient_training_history")
    if len(test_times) < MIN_TEST_OBSERVATIONS:
        missing.add("insufficient_test_history")
    return len(common), training_times, test_times, missing


def run_strategy_backtest(
    document: object,
    assets: Sequence[ResearchAsset],
    *,
    from_at: datetime,
    to_at: datetime,
    initial_capital_rub: Decimal,
    costs: ResearchCosts,
    now: datetime | None = None,
    engine_version: str = RESEARCH_ENGINE_VERSION,
) -> dict[str, Any]:
    """Frozen-training holdout research; never silently replace a failed chosen asset."""
    data = normalize_document(document)
    observed = now or datetime.now(UTC)
    capital = _validated_research_capital(
        from_at,
        to_at,
        observed,
        len(assets),
        initial_capital_rub,
        costs,
    )
    split = from_at + (to_at - from_at) * 0.7
    clean_assets, diagnostics = _prepare_research_assets(
        assets, from_at, to_at, split, data, costs, engine_version
    )
    selection = select_strategy_candidates(
        data,
        [asset.candidate for asset in clean_assets],
        as_of=split,
        engine_version=engine_version,
    )
    chosen = {
        row["instrument_uid"]: Decimal(row["target_weight_percent"])
        for row in selection["selected"]
    }
    selected_assets = [asset for asset in clean_assets if asset.candidate.instrument_uid in chosen]
    bases = {asset.basis for asset in selected_assets}
    basis = next(iter(bases)) if len(bases) == 1 else "unadjusted_price"
    fingerprint: dict[str, Any] = {
        "engine_version": engine_version,
        "method_rules": strategy_rule_set(data["base_preset_id"]),
        "strategy": data,
        "from": from_at.isoformat(),
        "to": to_at.isoformat(),
        "capital": _text(capital),
        "costs": [str(costs.commission_bps), str(costs.slippage_bps)],
        "assets": [
            {
                "uid": asset.candidate.instrument_uid,
                "asset_class": asset.candidate.asset_class,
                "currency": asset.candidate.currency,
                "basis": asset.basis,
                "lot_size": asset.candidate.lot_size,
                "lot_history_verified": asset.lot_history_verified,
                "cashflow_history_verified": asset.cashflow_history_verified,
                "verification_source": asset.verification_source,
                "corporate_actions": [when.isoformat() for when in asset.corporate_action_dates],
                "constituents": [
                    [
                        row.issuer_id,
                        row.group_id,
                        row.sector,
                        str(row.weight_percent),
                        row.available_at.isoformat(),
                        row.source_url,
                    ]
                    for row in asset.candidate.constituents
                ],
                "bars": [
                    [bar.time.isoformat(), bar.open, bar.high, bar.low, bar.close, bar.volume_lots]
                    for bar in asset.candles
                ],
                "facts": {
                    key: [str(f.value), f.available_at.isoformat(), f.source_url]
                    for key, f in asset.candidate.facts.items()
                },
                "cashflows": [
                    [
                        e.entitlement_at.isoformat(),
                        e.paid_at.isoformat(),
                        str(e.amount_per_unit_rub),
                        e.source_url,
                        e.kind,
                    ]
                    for e in asset.cashflows
                ],
                "factors": [
                    [
                        row.time.isoformat(),
                        row.available_at.isoformat(),
                        str(row.growth_change),
                        str(row.inflation_change),
                        row.source_url,
                    ]
                    for row in asset.factors
                ],
                "splits": [
                    [row.time.isoformat(), str(row.ratio), row.source_url] for row in asset.splits
                ],
                "bond_valuations": [
                    [
                        row.time.isoformat(),
                        str(row.nominal_rub),
                        str(row.accrued_interest_open_rub),
                        str(row.accrued_interest_close_rub),
                        row.source_url,
                    ]
                    for row in asset.bond_valuations
                ],
            }
            for asset in clean_assets
        ],
    }
    if engine_version != "1.1.0":
        for row, asset in zip(fingerprint["assets"], clean_assets, strict=True):
            row["fact_history"] = {
                key: [
                    [str(f.value), f.available_at.isoformat(), f.source_url] for f in observations
                ]
                for key, observations in asset.candidate.fact_history.items()
            }
            row["observed_cashflows"] = [
                [
                    event.entitlement_at.isoformat(),
                    event.paid_at.isoformat(),
                    str(event.amount_per_unit_rub),
                    event.source_url,
                    event.kind,
                ]
                for event in asset.observed_cashflows
            ]
    limitations = [
        "Историческая проверка условной корзины, не фактическая доходность счёта.",
        "Состав доступной выборки задаётся источником: исключённые с биржи бумаги "
        "могут отсутствовать.",
        "Гипотеза выбрана без поиска оптимума на тестовом периоде; проверена одна конфигурация.",
        "Инфляция, плата за заём и процент на денежный остаток не моделируются.",
        "Если задана налоговая ставка, используется условное удержание с каждой "
        "прибыльной продажи и выплаты без зачёта убытков и льгот; это не налоговый расчёт.",
        "Позиции в конце периода оценены по цене закрытия, без обязательной продажи.",
        "Возврат номинала отделён от дохода и уменьшает модельную стоимость приобретения; "
        "фактические налоговые правила амортизации могут отличаться.",
        "Дробления меняют количество бумаг; дробные остатки требуют отдельных данных расчёта. "
        "Исторический размер лота считается неизменным в подтверждённом интервале.",
    ]
    if selection["status"] == "partial":
        limitations.append(
            "Исследована частичная корзина. Недостающие классы и непроверенные ограничения "
            "перечислены в подборе; незаполненный вес оставлен деньгами."
        )
    if any(data["profile"][key] is None for key in ("reserve_rub", "planned_withdrawal_rub")):
        limitations.append(
            "Личные суммы резерва или снятий не указаны. Проверяется модельный капитал "
            "с целевой денежной долей, а не пригодность вложения личных средств."
        )
    if basis == "unadjusted_price":
        limitations.extend(
            [
                "Дивиденды, купоны, НКД и выплаты при возврате номинала не входят "
                "в этот расчёт движения цены.",
                "Корпоративные действия и исторические изменения лота не подтверждены полностью.",
            ]
        )
    result: dict[str, Any] = {
        "status": "insufficient_data",
        "strategy_hash": document_hash(data),
        "method": strategy_rule_set(data["base_preset_id"])["ranking"],
        "basis": basis,
        "engine_version": engine_version,
        "complete_strategy_coverage": selection["candidate_selection_ready"],
        "research_asset_weight_percent": _text(sum(chosen.values(), _ZERO)),
        "return_label": "Полная доходность после заданных издержек"
        if basis == "verified_total_return"
        else "Изменение цены после заданных издержек",
        "period": {
            "from": from_at.isoformat(),
            "to": to_at.isoformat(),
            "train_end": split.isoformat(),
            "test_from": None,
            "observations": 0,
            "train_observations": 0,
            "test_observations": 0,
        },
        "metrics": None,
        "benchmark": None,
        "equity_curve": [],
        "selection": selection,
        "asset_diagnostics": diagnostics,
        "execution_enabled": False,
        "probability_of_profit": None,
        "probability_reason": "Один исторический тест и доля положительных дней не являются "
        "калиброванной вероятностью будущей прибыли.",
        "limitations": limitations,
        "assumptions": {
            "commission_bps": str(costs.commission_bps),
            "slippage_bps": str(costs.slippage_bps),
            "annualization_sessions": 252,
            "training_fraction": "0.70",
            "execution": "next_open_from_previous_close",
            "liquidity": "previous_session_volume",
            "integer_lots": True,
            "configurations_tested": 1,
            "tail_confidence": "0.95",
            "risk_control": "previous_close_drawdown_next_open_liquidation_with_volume_limits",
            "liquidity_horizon_days": data["profile"]["liquidity_horizon_days"],
            "reserve_rub": data["profile"]["reserve_rub"],
            "planned_withdrawal_rub": data["profile"]["planned_withdrawal_rub"],
            "tax_rate_percent": data["policy"]["securities_tax_rate_percent"],
            "tax_method": "positive_realized_gain_and_distributions_no_offsets"
            if data["policy"]["securities_tax_rate_percent"] is not None
            else "not_configured",
            "rebalance_band": "absolute_allocation_deviation_percentage_points",
            "minimum_rebalance_effect": "reduction_of_allocation_error_less_costs_rub",
        },
        "sources": [{"id": "tbank_daily_candles", "url": HISTORY_SOURCE}],
        "data_hash": hashlib.sha256(json.dumps(fingerprint, sort_keys=True).encode()).hexdigest(),
        "missing_requirements": [],
    }
    missing = _selected_evidence_requirements(data, selection, selected_assets, diagnostics, bases)
    panel = {
        asset.candidate.instrument_uid: {bar.time: bar for bar in asset.candles}
        for asset in selected_assets
    }
    observations, training_times, test_times, history_missing = _common_research_times(panel, split)
    missing.update(history_missing)
    result["period"].update(
        observations=observations,
        train_observations=len(training_times),
        test_observations=len(test_times),
        test_from=test_times[0].isoformat() if test_times else None,
    )
    result["missing_requirements"] = sorted(missing | set(selection["missing_requirements"]))
    if missing:
        return result
    times = [training_times[-1], *test_times]
    period = strategy_rule_set(data["base_preset_id"])["rebalance_sessions"]
    try:
        state = _simulate(
            selected_assets, panel, times, chosen, data, capital, costs, rebalance_sessions=period
        )
        baseline = _simulate(
            selected_assets, panel, times, chosen, data, capital, costs, rebalance_sessions=None
        )
    except ValueError as exc:
        if str(exc) != "fractional_split_cash_settlement_required":
            raise
        result["missing_requirements"].append(str(exc))
        return result
    result.update(
        status="computed",
        metrics=_metrics(state, capital),
        equity_curve=state.curve,
        benchmark={
            "name": "Та же начальная корзина без перебалансировок",
            "basis": basis,
            "metrics": _metrics(baseline, capital),
        },
    )
    result["stress_scenario"] = _stress_scenario(state, selected_assets, panel, times[-1], data)
    return result


def _stress_scenario(
    state: _Simulation,
    assets: Sequence[ResearchAsset],
    panel: Mapping[str, Mapping[datetime, TBankHistoricCandle]],
    when: datetime,
    document: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply the user's explicit shocks to ending holdings, never a probability."""
    uncertainty = _decimal(document["policy"]["uncertainty_haircut_percent"] or "0") / 100
    credit = _decimal(document["policy"]["credit_loss_haircut_percent"] or "0") / 100
    nav = Decimal(state.curve[-1]["nav_rub"])
    loss = _ZERO
    for asset in assets:
        uid = asset.candidate.instrument_uid
        value = state.lots[uid] * asset.candidate.lot_size * _decimal(panel[uid][when].close)
        factor = (1 - uncertainty) * (1 - credit if asset.candidate.asset_class == "bonds" else 1)
        loss += value * (1 - factor)
    return {
        "method": "user_defined_instantaneous_haircuts",
        "probability": None,
        "uncertainty_haircut_percent": _text(uncertainty * 100),
        "bond_credit_haircut_percent": _text(credit * 100),
        "base_nav_rub": _text(nav),
        "stressed_nav_rub": _text(nav - loss),
        "loss_rub": _text(loss),
        "loss_percent": _text(loss / nav * 100) if nav else None,
        "scope": "Заданные пользователем одновременные шоки к остаточным позициям. "
        "Не оценка вероятности события, дефолта или будущего убытка.",
    }


def research_robustness(
    document: object,
    assets: Sequence[ResearchAsset],
    *,
    from_at: datetime,
    to_at: datetime,
    initial_capital_rub: Decimal,
    costs: ResearchCosts,
    now: datetime,
    engine_version: str = RESEARCH_ENGINE_VERSION,
) -> dict[str, Any]:
    """Three declared chronological holdouts; no search for the best result."""
    windows = []
    for fraction in (Decimal("0.6"), Decimal("0.8"), Decimal("1")):
        end = from_at + (to_at - from_at) * float(fraction)
        result = run_strategy_backtest(
            document,
            assets,
            from_at=from_at,
            to_at=end,
            initial_capital_rub=initial_capital_rub,
            costs=costs,
            now=now,
            engine_version=engine_version,
        )
        windows.append(
            {
                "period": result["period"],
                "status": result["status"],
                "metrics": result["metrics"],
                "data_hash": result["data_hash"],
                "missing_requirements": result["missing_requirements"],
            }
        )
    computed = [row for row in windows if row["status"] == "computed"]
    returns = [Decimal(row["metrics"]["net_return_percent"]) for row in computed]
    return {
        "method": "expanding_prefix_holdouts_60_80_100_percent",
        "windows": windows,
        "computed_windows": len(computed),
        "minimum_return_percent": _text(min(returns)) if returns else None,
        "maximum_return_percent": _text(max(returns)) if returns else None,
        "scope": "Три заранее заданных пересекающихся исторических окна. "
        "Не независимые эксперименты, не подбор лучшего окна и не вероятность прибыли.",
    }
