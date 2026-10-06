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
MAX_RESEARCH_ASSETS = 12
MAX_RESEARCH_DAYS = 1095
MIN_TRAIN_OBSERVATIONS = 60
MIN_TEST_OBSERVATIONS = 20
_ZERO, _ONE, _HUNDRED = Decimal(0), Decimal(1), Decimal(100)
_DAY = timedelta(days=1)


@dataclass(frozen=True, slots=True)
class HistoricalCashflow:
    """Verified RUB distribution per security; entitlement and payment differ."""

    entitlement_at: datetime
    paid_at: datetime
    amount_per_unit_rub: Decimal
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
    return replace(candidate, facts=facts)


def _validate_bar_values(bar: TBankHistoricCandle) -> None:
    if type(bar.volume_lots) is not int or bar.volume_lots < 0:
        raise ValueError("research_invalid_volume")
    prices = tuple(_decimal(value) for value in (bar.open, bar.high, bar.low, bar.close))
    opening, high, low, close = prices
    if (
        min(prices) <= 0
        or low > min(opening, close)
        or high < max(opening, close)
        or low > high
    ):
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


def _asset_reasons(asset: ResearchAsset, from_at: datetime, to_at: datetime) -> list[str]:
    reasons = []
    if asset.basis not in {"unadjusted_price", "verified_total_return"}:
        reasons.append("unsupported_return_basis")
    for when in asset.corporate_action_dates:
        if when.tzinfo is None:
            reasons.append("corporate_action_time_missing")
        elif from_at <= when <= to_at:
            reasons.append("corporate_action_requires_adjustment")
    if asset.basis == "verified_total_return" and not (
        asset.lot_history_verified
        and asset.cashflow_history_verified
        and asset.verification_source.startswith("https://")
    ):
        reasons.append("total_return_basis_not_verified")
    if asset.basis == "unadjusted_price" and asset.cashflows:
        reasons.append("cashflows_require_verified_basis")
    if asset.basis == "verified_total_return" and asset.candidate.asset_class == "bonds":
        reasons.append("bond_principal_and_accrual_history_required")
    for event in asset.cashflows:
        if (
            event.entitlement_at.tzinfo is None
            or event.paid_at.tzinfo is None
            or event.paid_at < event.entitlement_at
            or not event.amount_per_unit_rub.is_finite()
            or event.amount_per_unit_rub < 0
            or not event.source_url.startswith("https://")
        ):
            reasons.append("invalid_distribution_event")
    keys = [(event.entitlement_at, event.paid_at, event.source_url) for event in asset.cashflows]
    if len(keys) != len(set(keys)):
        reasons.append("duplicate_distribution_event")
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
    receivables: list[tuple[datetime, Decimal]] = field(default_factory=list)
    accrued_events: set[tuple[str, int]] = field(default_factory=set)
    curve: list[dict[str, str]] = field(default_factory=list)


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
    state.cash -= direction * amount * per_lot + fee
    state.lots[uid] += direction * amount
    state.fees += fee
    state.slippage += slip
    state.costs += fee + slip
    state.trades += 1
    return amount * per_lot


def _distributions(
    state: _Simulation,
    assets: Sequence[ResearchAsset],
    *,
    start: datetime,
    through: datetime,
    inclusive: bool,
) -> None:
    for asset in assets:
        for index, event in enumerate(asset.cashflows):
            key = (asset.candidate.instrument_uid, index)
            reached = (
                event.entitlement_at <= through if inclusive else event.entitlement_at < through
            )
            if start <= event.entitlement_at and reached and key not in state.accrued_events:
                state.accrued_events.add(key)
                entitlement = state.lots[asset.candidate.instrument_uid] * asset.candidate.lot_size
                if entitlement:
                    state.receivables.append(
                        (event.paid_at, entitlement * event.amount_per_unit_rub)
                    )
    unpaid = []
    for when, amount in state.receivables:
        reached = when <= through if inclusive else when < through
        if reached:
            state.cash += amount
        else:
            unpaid.append((when, amount))
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
        + sum((amount for _, amount in state.receivables), _ZERO)
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
    state.curve.append(
        {
            "time": (times[0] + _DAY).isoformat(),
            "nav_rub": _text(capital),
            "cash_rub": _text(capital),
            "receivables_rub": "0",
        }
    )
    previous_nav = peak = capital
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
    limit = document["profile"]["max_drawdown_percent"]
    for index, when in enumerate(times[1:]):
        previous = times[index]
        # Entitlement before today's trades; paid cash cannot be spent before its date.
        _distributions(state, assets, start=times[1], through=when, inclusive=True)
        if rebalance_sessions is not None and limit is not None:
            state.risk_stopped |= (peak - previous_nav) / peak * 100 > Decimal(limit)
        rebalance = index == 0 or (
            rebalance_sessions is not None and index % rebalance_sessions == 0
        )
        if rebalance or state.risk_stopped:
            turnover = previous_nav * turnover_fraction
            targets = {}
            for asset in assets:
                uid = asset.candidate.instrument_uid
                target = _ZERO if state.risk_stopped else previous_nav * weights[uid] / 100
                price = _decimal(panel[uid][previous].close) * asset.candidate.lot_size
                targets[uid] = int(target / price) - state.lots[uid]
                days = document["profile"]["liquidity_horizon_days"]
                if days is not None:
                    exit_capacity = int(
                        panel[uid][previous].volume_lots * participation * Decimal(days)
                    )
                    targets[uid] = min(targets[uid], exit_capacity - state.lots[uid])
            minimum_cash = max(reserve, previous_nav * cash_target)
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
                        opening=_decimal(panel[uid][when].open),
                        lot=asset.candidate.lot_size,
                        remaining_turnover=turnover,
                        minimum_cash=minimum_cash,
                        volume_limit=int(panel[uid][previous].volume_lots * participation),
                        costs=costs,
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
                "receivables_rub": _text(sum((a for _, a in state.receivables), _ZERO)),
            }
        )
    return state


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
    assets: Sequence[ResearchAsset], from_at: datetime, to_at: datetime, split: datetime,
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
                candidate=history_candidate(asset.candidate, training, as_of=split),
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
        breaks = _discontinuities(asset.candles)
        missing.update(breaks)
        if breaks:
            diagnostic["status"] = "incomplete"
            diagnostic["reasons"] = sorted(set(diagnostic["reasons"] + breaks))
    for key in ("max_daily_turnover_participation_percent", "turnover_budget_percent"):
        if data["policy"][key] is None:
            missing.add("policy." + key)
    return missing


def _common_research_times(
    panel: Mapping[str, Mapping[datetime, TBankHistoricCandle]], split: datetime,
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
) -> dict[str, Any]:
    """Frozen-training holdout research; never silently replace a failed chosen asset."""
    data = normalize_document(document)
    observed = now or datetime.now(UTC)
    capital = _validated_research_capital(
        from_at, to_at, observed, len(assets), initial_capital_rub, costs,
    )
    split = from_at + (to_at - from_at) * 0.7
    clean_assets, diagnostics = _prepare_research_assets(assets, from_at, to_at, split)
    selection = select_strategy_candidates(
        data, [asset.candidate for asset in clean_assets], as_of=split
    )
    chosen = {
        row["instrument_uid"]: Decimal(row["target_weight_percent"])
        for row in selection["selected"]
    }
    selected_assets = [asset for asset in clean_assets if asset.candidate.instrument_uid in chosen]
    bases = {asset.basis for asset in selected_assets}
    basis = next(iter(bases)) if len(bases) == 1 else "unadjusted_price"
    fingerprint = {
        "engine_version": "1.0.0",
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
                    ]
                    for e in asset.cashflows
                ],
            }
            for asset in clean_assets
        ],
    }
    limitations = [
        "Историческая проверка условной корзины, не фактическая доходность счёта.",
        "Состав доступной выборки задаётся источником: исключённые с биржи бумаги "
        "могут отсутствовать.",
        "Гипотеза выбрана без поиска оптимума на тестовом периоде; проверена одна конфигурация.",
        "Налоги, инфляция, плата за заём и процент на денежный остаток не моделируются.",
        "Позиции в конце периода оценены по цене закрытия, без обязательной продажи.",
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
                "Дивиденды, купоны, НКД и изменения номинала не входят "
                "в этот расчёт движения цены.",
                "Корпоративные действия и исторические изменения лота не подтверждены полностью.",
            ]
        )
    result: dict[str, Any] = {
        "status": "insufficient_data",
        "strategy_hash": document_hash(data),
        "method": strategy_rule_set(data["base_preset_id"])["ranking"],
        "basis": basis,
        "engine_version": "1.0.0",
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
    state = _simulate(
        selected_assets, panel, times, chosen, data, capital, costs, rebalance_sessions=period
    )
    baseline = _simulate(
        selected_assets, panel, times, chosen, data, capital, costs, rebalance_sessions=None
    )
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
    return result
