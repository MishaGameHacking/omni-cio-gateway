"""Chronological, read-only portfolio research from explicit observed daily bars.

The signal is frozen on the training window. Integer orders are sized from the
previous close and filled at the following open, with cash and volume limits.
Unadjusted price research and a verified cash-flow history are separate bases.
No result estimates a personal probability of making a profit.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import ROUND_CEILING, Decimal
from typing import Any, Literal

from .financial import PERCENT_SCALE
from .research_policy import (
    ANNUALIZATION_SESSIONS,
    CASHFLOW_WINDOW_DAYS,
    CORRECTED_MATH_ENGINES,
    MAX_RESEARCH_ASSETS,
    MAX_RESEARCH_DAYS,
    MIN_TEST_OBSERVATIONS,
    MIN_TRAIN_OBSERVATIONS,
    RESEARCH_ENGINE_VERSION,
    UNIT_AWARE_ENGINES,
)
from .strategy import document_hash, expected_shortfall, normalize_document, strategy_rule_set
from .strategy_assessment import (
    StrategyCandidateFacts,
    StrategyFact,
    _source_url,
    calendar_horizon_days,
    candidate_weight_constraints,
    select_strategy_candidates,
)
from .tbank import TBankHistoricCandle

ResearchBasis = Literal["unadjusted_price", "verified_total_return"]
HISTORY_SOURCE = "https://developer.tbank.ru/invest/api/market-data-service-get-candles"
_OUTCOME_HORIZONS = (1, 5, 21)
_BOOTSTRAP_REPLICATES = 1024
_BOOTSTRAP_SOURCE = "https://users.ssc.wisc.edu/~behansen/718/Politis%20Romano.pdf"
_ZERO, _ONE = Decimal(0), Decimal(1)
_DAY = timedelta(days=1)
_CASHFLOW_YEAR = timedelta(days=CASHFLOW_WINDOW_DAYS)
_CASHFLOW_COVERAGE_FLAGS = (
    "cashflows_complete", "corporate_actions_complete", "lot_history_complete",
)
_HTTPS_PREFIX = "https://"
_MALFORMED_HISTORY_REASONS = {
    "research_too_many_daily_bars", "research_non_chronological_bars",
    "research_series_identity_or_source", "research_invalid_volume",
    "research_decimal_invalid", "research_invalid_ohlc", "invalid_distribution_event",
    "duplicate_distribution_event", "split_evidence_invalid", "duplicate_split_event",
    "corporate_action_time_missing", "bond_valuation_history_invalid",
    "factor_history_invalid", "factor_history_duplicate",
}


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
    if not number.is_finite() or number.copy_abs() > Decimal("1e15"):
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
    return (variance * ANNUALIZATION_SESSIONS).sqrt() * PERCENT_SCALE


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
    splits: Sequence[HistoricalSplit] = (),
    corporate_action_dates: Sequence[datetime] = (),
    cashflow_coverage: object = None,
    engine_version: str = RESEARCH_ENGINE_VERSION,
) -> StrategyCandidateFacts:
    """Completed daily bars; engines from 1.3.2 use raw bars and explicit split evidence."""
    completed = [bar for bar in candles if bar.is_complete and as_of - bar.time >= _DAY]
    if not completed:
        return candidate
    past: Sequence[TBankHistoricCandle] = completed
    if engine_version in UNIT_AWARE_ENGINES:
        past = split_adjusted_history(completed, splits, as_of)
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
    if engine_version in UNIT_AWARE_ENGINES:
        income_end = completed[-1].time + _DAY
        coverage_reasons = _cashflow_window_reasons(
            cashflow_coverage, cashflows, splits, corporate_action_dates, income_end,
        )
        if not coverage_reasons and isinstance(cashflow_coverage, Mapping):
            income_bar = split_adjusted_history(completed[-1:], splits, income_end)[0]
            observed_income = _cashflow_facts(
                candidate, cashflows, _decimal(income_bar.close), income_end,
                document=document, costs=costs,
                splits=splits, coverage_source=str(cashflow_coverage["source_url"]),
            )
            _merge_observed_income(facts, observed_income, as_of)
    elif cashflows:
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


def _newer_income_fact(
    key: str, fact: StrategyFact | None, income_end: datetime, as_of: datetime,
) -> bool:
    if (fact is None or fact.available_at.tzinfo is None
            or not income_end < fact.available_at <= as_of
            or not isinstance(fact.source_url, str) or not _source_url(fact.source_url)):
        return False
    if key == "dividend_declared":
        return type(fact.value) is bool
    try:
        _decimal(fact.value)
    except ValueError:
        return False
    return True


def _merge_observed_income(
    facts: dict[str, StrategyFact], observed: Mapping[str, StrategyFact], as_of: datetime,
) -> None:
    """A daily observation cannot overwrite a valid later explicit scalar fact."""
    for key, observation in observed.items():
        if not _newer_income_fact(key, facts.get(key), observation.available_at, as_of):
            facts[key] = observation


def _cashflow_coverage_period(coverage: Mapping[str, Any]) -> tuple[datetime, datetime]:
    """Validate explicit evidence metadata; timestamps are not guessed from events."""
    source = coverage.get("source_url")
    if not isinstance(source, str) or not source.strip() or len(source) > 2000:
        raise ValueError("cashflow_coverage_invalid")
    if not _source_url(source):
        raise ValueError("cashflow_coverage_invalid")
    if any(type(coverage.get(key)) is not bool for key in _CASHFLOW_COVERAGE_FLAGS):
        raise ValueError("cashflow_coverage_invalid")
    bounds = []
    for key in ("from", "to"):
        raw = coverage.get(key)
        if not isinstance(raw, str):
            raise ValueError("cashflow_coverage_invalid")
        when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if when.tzinfo is None:
            raise ValueError("cashflow_coverage_invalid")
        bounds.append(when)
    if bounds[0] >= bounds[1]:
        raise ValueError("cashflow_coverage_invalid")
    return bounds[0], bounds[1]


def _cashflow_window_reasons(
    coverage: object,
    cashflows: Sequence[HistoricalCashflow],
    splits: Sequence[HistoricalSplit],
    corporate_action_dates: Sequence[datetime],
    as_of: datetime,
) -> list[str]:
    """Require the payment window and every entitlement-to-price unit adjustment."""
    if coverage is None:
        return ["cashflow_coverage_missing"]
    if not isinstance(coverage, Mapping) or as_of.tzinfo is None:
        return ["cashflow_coverage_invalid"]
    try:
        from_at, to_at = _cashflow_coverage_period(coverage)
        year_start = as_of - _CASHFLOW_YEAR
    except (ValueError, OverflowError):
        return ["cashflow_coverage_invalid"]
    reasons = _cashflow_reasons(cashflows)
    if reasons:
        return sorted(set(reasons))
    paid = [event for event in cashflows
            if event.kind == "income" and year_start < event.paid_at <= as_of]
    required_from = min([year_start, *(event.entitlement_at for event in paid)])
    if (from_at > required_from or to_at < as_of
            or not all(coverage[key] for key in _CASHFLOW_COVERAGE_FLAGS)):
        reasons.append("cashflow_coverage_incomplete")
    if coverage.get("cashflow_unit_basis") != "entitlement_security":
        reasons.append("cashflow_unit_basis_unverified")
    reasons.extend(_action_reasons(splits, corporate_action_dates, required_from, as_of))
    return sorted(set(reasons))


def cashflow_coverage_reasons(
    asset: ResearchAsset,
    *,
    as_of: datetime,
    candles: Sequence[TBankHistoricCandle] | None = None,
) -> list[str]:
    """Explain whether observed payments can support a complete annual yield.

    The observation ends with the latest completed daily candle, not the later
    request clock. Independently supplied dated scalar facts keep their source.
    """
    observation_bars = asset.candles if candles is None else candles
    income_end = _income_observation_end(observation_bars, as_of)
    if income_end is None:
        return ["insufficient_training_history"]
    coverage = asset.provider_observations.get("user_cashflow_coverage")
    return _cashflow_window_reasons(
        coverage, asset.observed_cashflows, asset.splits, asset.corporate_action_dates, income_end,
    )


def _income_observation_end(
    bars: Sequence[TBankHistoricCandle], as_of: datetime,
) -> datetime | None:
    return max((bar.time + _DAY for bar in bars
                if bar.is_complete and as_of - bar.time >= _DAY), default=None)


def _cashflow_coverage_diagnostic(
    asset: ResearchAsset, as_of: datetime, *, candles: Sequence[TBankHistoricCandle],
) -> dict[str, Any]:
    reasons = cashflow_coverage_reasons(asset, as_of=as_of, candles=candles)
    income_end = _income_observation_end(candles, as_of)
    return {
        "status": "complete" if not reasons else "incomplete",
        "reasons": reasons,
        "window_days": CASHFLOW_WINDOW_DAYS,
        "as_of": income_end.isoformat() if income_end is not None else None,
    }


def _cashflow_facts(
    candidate: StrategyCandidateFacts,
    cashflows: Sequence[HistoricalCashflow],
    price: Decimal,
    as_of: datetime,
    *,
    document: Mapping[str, Any] | None,
    costs: ResearchCosts | None,
    splits: Sequence[HistoricalSplit] = (),
    coverage_source: str | None = None,
) -> dict[str, StrategyFact]:
    """Trailing observed income, never future payouts or principal disguised as yield."""
    paid = [
        event
        for event in cashflows
        if event.kind == "income" and as_of - _CASHFLOW_YEAR < event.paid_at <= as_of
    ]
    if (not paid and coverage_source is None) or price <= 0:
        return {}
    if coverage_source is None:
        # Archived engines retain their original unadjusted per-security sum.
        gross = sum((event.amount_per_unit_rub for event in paid), _ZERO) / price * 100
        source = max(paid, key=lambda event: event.paid_at).source_url
    else:
        # Entitlement uses the unit after actions effective at that timestamp.
        # A later split therefore divides this historical per-unit payment.
        gross = sum((event.amount_per_unit_rub / _split_factor(
            splits, event.entitlement_at, as_of,
        ) for event in paid), _ZERO) / price * 100
        source = coverage_source
    facts = {"cashflow_yield_percent": StrategyFact(gross, as_of, source)}
    if candidate.asset_class == "shares":
        facts["dividend_yield_percent"] = StrategyFact(gross, as_of, source)
        if paid:
            facts["dividend_declared"] = StrategyFact(True, as_of, source)
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
        if not bar.is_complete or bar.time < from_at or to_at - bar.time < _DAY:
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
    return _action_reasons(asset.splits, asset.corporate_action_dates, from_at, to_at)


def _action_reasons(
    splits: Sequence[HistoricalSplit],
    corporate_action_dates: Sequence[datetime],
    from_at: datetime,
    to_at: datetime,
) -> list[str]:
    reasons = []
    for when in corporate_action_dates:
        if when.tzinfo is None:
            reasons.append("corporate_action_time_missing")
        elif from_at <= when <= to_at and not any(split.time == when for split in splits):
            reasons.append("corporate_action_requires_adjustment")
    if any(
        split.time.tzinfo is None
        or not split.ratio.is_finite()
        or split.ratio <= 0
        or not split.source_url.startswith(_HTTPS_PREFIX)
        for split in splits
    ):
        reasons.append("split_evidence_invalid")
    if len({split.time for split in splits}) != len(splits):
        reasons.append("duplicate_split_event")
    return reasons


def _bond_history_reasons(asset: ResearchAsset, from_at: datetime, to_at: datetime) -> list[str]:
    reasons = []
    if asset.bond_valuations:
        values = {row.time.date(): row for row in asset.bond_valuations}
        if len(values) != len(asset.bond_valuations) or any(
            bar.time.date() not in values
            for bar in asset.candles
            if from_at <= bar.time and to_at - bar.time >= _DAY
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


def research_history_candidate(
    asset: ResearchAsset,
    *,
    as_of: datetime,
    document: Mapping[str, Any] | None = None,
    costs: ResearchCosts | None = None,
    engine_version: str = RESEARCH_ENGINE_VERSION,
) -> StrategyCandidateFacts:
    """Validate imported history before any split, factor or income arithmetic.

    Callers must expose the error as unavailable evidence. Falling back to old
    candidate facts after a corrupt observation would make selection fail open.
    """
    if as_of.tzinfo is None:
        raise ValueError("research_window_invalid")
    begin = datetime.min.replace(tzinfo=UTC)
    reasons = _asset_reasons(asset, begin, as_of)
    reasons.extend(_cashflow_reasons(asset.observed_cashflows))
    if reasons:
        raise ValueError(min(reasons))
    bars = _validated_bars(asset, begin, as_of)
    if len(bars) < MIN_TRAIN_OBSERVATIONS:
        raise ValueError("insufficient_training_history")
    signal_bars = bars
    if engine_version not in UNIT_AWARE_ENGINES:
        signal_bars = split_adjusted_history(bars, asset.splits, as_of)
    return history_candidate(
        asset.candidate,
        signal_bars,
        as_of=as_of,
        factors=asset.factors,
        cashflows=asset.observed_cashflows,
        document=document,
        costs=costs,
        splits=asset.splits,
        corporate_action_dates=asset.corporate_action_dates,
        cashflow_coverage=asset.provider_observations.get("user_cashflow_coverage"),
        engine_version=engine_version,
    )


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
    net_receivables: bool = False
    chronological_actions: bool = False
    constraint_breach_sessions: int = 0
    constraint_breaches: set[str] = field(default_factory=set)
    constraint_unknown: set[str] = field(default_factory=set)


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
    allocation_target: Decimal | None = None,
    minimum_effect: Decimal = _ZERO,
    turnover_includes_commission: bool = False,
) -> Decimal:
    if not delta or not volume_limit or remaining_turnover <= 0:
        return _ZERO
    direction = 1 if delta > 0 else -1
    execution = opening * (1 + direction * costs.slippage_bps / 10000)
    per_lot = execution * lot
    fee_per_lot = per_lot * costs.commission_bps / 10000
    turnover_per_lot = per_lot + fee_per_lot if turnover_includes_commission else per_lot
    amount = min(abs(delta), volume_limit, int(remaining_turnover / turnover_per_lot))
    if direction == 1:
        capacity = max(_ZERO, state.cash - minimum_cash)
        amount = min(amount, int(capacity / (per_lot + fee_per_lot)))
    else:
        amount = min(amount, state.lots[uid])
    if amount <= 0:
        return _ZERO
    fee = amount * fee_per_lot
    slip = amount * lot * abs(execution - opening)
    if allocation_target is not None:
        current = state.lots[uid] * opening * lot
        change = direction * amount * opening * lot
        reduction = abs(allocation_target - current) - abs(allocation_target - current - change)
        if reduction - fee - slip < minimum_effect:
            return _ZERO
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
    return amount * turnover_per_lot


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


def _apply_splits_after_entitlements(
    state: _Simulation,
    asset: ResearchAsset,
    *,
    start: datetime,
    through: datetime,
    inclusive: bool,
) -> None:
    # Closed trading sessions can contain multiple corporate events.
    # Accrue each pre-split entitlement using the old unit count, then
    # apply the split before any entitlement at the same timestamp.
    splits = sorted(
        (split for index, split in enumerate(asset.splits)
         if start <= split.time
         and (split.time <= through if inclusive else split.time < through)
         and (asset.candidate.instrument_uid, index) not in state.applied_splits),
        key=lambda split: split.time,
    )
    for split in splits:
        _accrue_distributions(
            state, asset, start=start, through=split.time, inclusive=False,
        )
        _apply_splits(state, (asset,), split.time - timedelta(microseconds=1), split.time)


def _distributions(
    state: _Simulation,
    assets: Sequence[ResearchAsset],
    *,
    start: datetime,
    through: datetime,
    inclusive: bool,
) -> None:
    for asset in assets:
        if state.chronological_actions:
            _apply_splits_after_entitlements(
                state, asset, start=start, through=through, inclusive=inclusive,
            )
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
        + _receivables_value(state)
    )


def _receivables_value(state: _Simulation) -> Decimal:
    return sum(
        (
            amount * (1 - state.tax_rate if taxable and state.net_receivables else 1)
            for _, amount, taxable in state.receivables
        ),
        _ZERO,
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
    *,
    current_math: bool,
) -> None:
    """Size from the previous close, then sell before buying at this session's open."""
    participation = Decimal(document["policy"]["max_daily_turnover_participation_percent"]) / 100
    turnover_fraction = Decimal(document["policy"]["turnover_budget_percent"]) / 100
    cash_target = max(_ZERO, 1 - sum(weights.values(), _ZERO) / 100)
    reserve = _decimal(document["profile"]["reserve_rub"] or "0")
    withdrawals = _decimal(document["profile"]["planned_withdrawal_rub"] or "0")
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
    minimum_cash = max(reserve + withdrawals, session.previous_nav * cash_target)
    opening_prices = {
        asset.candidate.instrument_uid: _decimal(panel[asset.candidate.instrument_uid][
            session.opening
        ].open)
        for asset in assets
    }
    for side in (-1, 1):
        buying_nav_floor = session.previous_nav
        if side == 1 and current_math:
            opening_nav = _nav(state, assets, opening_prices)
            slip = costs.slippage_bps / 10000
            # Sells and their taxes are already known. Every later purchase loses
            # at most this fraction of notional plus commission to fees and slippage.
            # Size all buys against one lower NAV bound so a later fee cannot
            # push an earlier purchase above its target/concentration ceiling.
            fee_rate = costs.commission_bps / 10000
            buy_loss_rate = (slip / (1 + slip) + fee_rate) / (1 + fee_rate)
            buying_nav_floor = max(_ZERO, opening_nav - turnover * buy_loss_rate)
            minimum_cash = max(reserve, opening_nav * cash_target) + withdrawals
        for asset in assets:
            uid = asset.candidate.instrument_uid
            delta = targets[uid]
            if (delta > 0) != (side > 0) or delta == 0:
                continue
            delta, allocation_target = _rebalance_order_target(
                state, asset, delta, weights[uid], opening_prices[uid], buying_nav_floor,
                current_math=current_math,
            )
            turnover -= _order(
                state,
                uid,
                delta,
                opening=opening_prices[uid],
                lot=asset.candidate.lot_size,
                remaining_turnover=turnover,
                minimum_cash=minimum_cash,
                volume_limit=_session_volume_limit(
                    asset, panel[uid], session, participation, current_math=current_math
                ),
                costs=costs,
                allocation_target=allocation_target,
                minimum_effect=_decimal(document["policy"]["min_replace_benefit_rub"] or "0"),
                turnover_includes_commission=current_math,
            )


def _rebalance_order_target(
    state: _Simulation,
    asset: ResearchAsset,
    delta: int,
    weight: Decimal,
    opening_price: Decimal,
    nav_floor: Decimal,
    *,
    current_math: bool,
) -> tuple[int, Decimal | None]:
    """Bound buys by opening value and retain the final-fill allocation target."""
    if not current_math:
        return delta, None
    allocation_target = nav_floor * weight / 100
    if delta > 0:
        cap_lots = int(allocation_target / (opening_price * asset.candidate.lot_size))
        delta = min(delta, max(0, cap_lots - state.lots[asset.candidate.instrument_uid]))
    if state.risk_stopped:
        return delta, None
    return delta, allocation_target


def _session_volume_limit(
    asset: ResearchAsset,
    bars: Mapping[datetime, TBankHistoricCandle],
    session: _RebalanceSession,
    participation: Decimal,
    *,
    current_math: bool,
) -> int:
    volume = bars[session.previous].volume_lots * _split_factor(
        asset.splits, session.previous, session.opening
    )
    if current_math:
        volume = min(volume, Decimal(bars[session.opening].volume_lots))
    return int(volume * participation)


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
    engine_version: str,
) -> _Simulation:
    ids = [asset.candidate.instrument_uid for asset in assets]
    state = _Simulation(capital, dict.fromkeys(ids, 0))
    current_math = engine_version in CORRECTED_MATH_ENGINES
    state.net_receivables = current_math
    state.chronological_actions = engine_version == "1.3.3"
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
        if not state.chronological_actions:
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
                current_math=current_math,
            )
        closing_time = when + _DAY
        # Same-day distributions cannot fund orders already filled at the open.
        _distributions(state, assets, start=times[1], through=closing_time, inclusive=False)
        prices = {uid: _decimal(panel[uid][when].close) for uid in ids}
        previous_nav = _nav(state, assets, prices)
        peak = max(peak, previous_nav)
        if current_math:
            _record_holding_constraints(
                state, assets, prices, previous_nav, document, when, engine_version=engine_version,
            )
        state.curve.append(
            {
                "time": closing_time.isoformat(),
                "nav_rub": _text(previous_nav),
                "cash_rub": _text(state.cash),
                "receivables_rub": _text(_receivables_value(state)),
            }
        )
    return state


def _record_holding_constraints(
    state: _Simulation,
    assets: Sequence[ResearchAsset],
    prices: Mapping[str, Decimal],
    nav: Decimal,
    document: Mapping[str, Any],
    when: datetime,
    *,
    engine_version: str,
) -> None:
    weights = {
        asset.candidate.instrument_uid: (
            state.lots[asset.candidate.instrument_uid] * asset.candidate.lot_size
            * prices[asset.candidate.instrument_uid] * 100 / nav
        )
        for asset in assets
    }
    checks = candidate_weight_constraints(
        document, [asset.candidate for asset in assets], weights, as_of=when + _DAY,
        engine_version=engine_version,
    )
    breaches = [
        reason for reason in checks
        if reason.startswith(("instrument_cap:", "excluded_class:", "fund_wrapper_cap:",
                              "exposure_cap:", "class_cap:"))
    ]
    state.constraint_unknown.update(set(checks) - set(breaches))
    if breaches:
        state.constraint_breach_sessions += 1
        state.constraint_breaches.update(breaches)


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
    var, shortfall = _tail_loss_percent([value * 100 for value in changes]) if changes else (
        None, None
    )
    count = len(changes)
    volatility = _volatility(changes)
    return {
        "net_return_percent": _text((navs[-1] / capital - 1) * 100),
        "max_drawdown_percent": _text(_drawdown(navs)),
        "annualized_volatility_percent": None if volatility is None else _text(volatility),
        "var_95_percent": _text(var) if var is not None else None,
        "expected_shortfall_95_percent": _text(shortfall) if shortfall is not None else None,
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


def _tail_loss_percent(gains: Sequence[Decimal]) -> tuple[Decimal, Decimal]:
    losses = sorted(-value for value in gains)
    count = len(losses)
    quantile = int((Decimal(count) * Decimal("0.95")).to_integral_value(rounding=ROUND_CEILING)) - 1
    probability = _ONE / count
    masses = [probability] * (count - 1)
    masses.append(_ONE - sum(masses, _ZERO))
    return max(_ZERO, losses[max(0, quantile)]), max(_ZERO, expected_shortfall(losses, masses))


def _percentile(values: Sequence[Decimal], probability: Decimal) -> Decimal:
    """Linear interpolation of an explicitly sorted empirical sample."""
    index = (len(values) - 1) * probability
    lower = int(index)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (index - lower)


def _bootstrap_words(seed: str) -> Iterator[int]:
    """Domain-separated SHA-256 counter stream for local statistical resampling.

    The public seed identifies the observed data and window size. Fixed byte
    order and a counter make the resampling reproducible across Python runtimes.
    """
    prefix = hashlib.sha256(b"omnicio-stationary-bootstrap-v1\x00" + seed.encode()).digest()
    counter = 0
    while True:
        digest = hashlib.sha256(prefix + counter.to_bytes(8, "big")).digest()
        counter += 1
        for offset in range(0, len(digest), 8):
            yield int.from_bytes(digest[offset:offset + 8], "big")


def _bootstrap_index(words: Iterator[int], size: int) -> int:
    """Uniform index under uniform 64-bit words, with no remainder bias.

    Reject the incomplete upper residue group. Each accepted index then has
    exactly floor(2**64 / size) preimages before the modulo operation.
    """
    space = 1 << 64
    if not 1 <= size <= space:
        raise ValueError("bootstrap_sample_size_invalid")
    ceiling = space - space % size
    for word in words:
        if word < ceiling:
            return word % size
    raise ValueError("bootstrap_word_stream_exhausted")


def _profit_frequency_interval(
    gains: Sequence[Decimal], *, seed: str, risk_stopped: bool,
) -> dict[str, Any]:
    """Stationary block bootstrap of indicators, not hypothetical strategy paths.

    The resampled statistic is the historical mean of 1[net return > 0].
    No rebalance, drawdown stop or fee is replayed on a fabricated price path.
    """
    count = len(gains)
    indicators = [int(value > 0) for value in gains]
    block_length = 1
    while block_length ** 3 < count:
        block_length += 1
    result: dict[str, Any] = {
        "method": "stationary_block_bootstrap_of_profit_indicators",
        "confidence": "0.95",
        "lower_percent": None,
        "upper_percent": None,
        "replicates": _BOOTSTRAP_REPLICATES,
        "expected_block_length_windows": block_length,
        "block_length_selection": "ceiling_cube_root_window_count_not_optimized",
        "resampling_generator": "sha256_counter_64bit_rejection_v1",
        "reason": None,
        "assumption": "Стационарность и слабая временная зависимость внутри выбранного "
        "периода; интервал не учитывает смену режима и ошибку выбора модели.",
    }
    if count < MIN_TEST_OBSERVATIONS:
        result["reason"] = "insufficient_non_overlapping_windows"
        return result
    if risk_stopped:
        result["reason"] = "strategy_risk_stop_regime_change"
        return result
    if min(indicators) == max(indicators):
        result["reason"] = "no_profit_indicator_variation"
        return result
    words = _bootstrap_words(seed)
    totals = []
    for _ in range(_BOOTSTRAP_REPLICATES):
        position = _bootstrap_index(words, count)
        wins = indicators[position]
        for _ in range(1, count):
            if _bootstrap_index(words, block_length) == 0:
                position = _bootstrap_index(words, count)
            else:
                position = (position + 1) % count
            wins += indicators[position]
        totals.append(Decimal(wins) * 100 / count)
    totals.sort()
    result.update(
        lower_percent=_text(_percentile(totals, Decimal("0.025"))),
        upper_percent=_text(_percentile(totals, Decimal("0.975"))),
    )
    return result


def _outcome_window_row(
    curve: Sequence[Mapping[str, str]],
    sessions: int,
    *,
    complete: bool,
    seed: str,
    risk_stopped: bool,
) -> dict[str, Any]:
    windows = max(0, (len(curve) - 1) // sessions)
    gains = [
        (Decimal(curve[(index + 1) * sessions]["nav_rub"])
         / Decimal(curve[index * sessions]["nav_rub"]) - 1) * 100
        for index in range(windows)
    ]
    profitable = sum(value > 0 for value in gains)
    losing = sum(value < 0 for value in gains)
    enough = complete and windows >= MIN_TEST_OBSERVATIONS
    reason = None
    if not complete:
        reason = "incomplete_strategy_coverage"
    elif windows < MIN_TEST_OBSERVATIONS:
        reason = "insufficient_non_overlapping_windows"
    interval = (
        _profit_frequency_interval(gains, seed=seed + ":" + str(sessions),
                                   risk_stopped=risk_stopped) if enough else None
    )
    ordered = sorted(gains)
    var, shortfall = _tail_loss_percent(gains) if enough else (None, None)
    return {
        "status": "computed" if enough else "insufficient_data",
        "reason": reason,
        "sessions": sessions,
        "from": curve[0]["time"] if windows else None,
        "to": curve[windows * sessions]["time"] if windows else None,
        "windows": windows,
        "discarded_trailing_sessions": max(0, len(curve) - 1) % sessions,
        "profit_windows": profitable,
        "loss_windows": losing,
        "flat_windows": windows - profitable - losing,
        "profit_frequency_percent": _text(Decimal(profitable) * 100 / windows) if enough else None,
        "loss_frequency_percent": _text(Decimal(losing) * 100 / windows) if enough else None,
        "worst_return_percent": _text(ordered[0]) if enough else None,
        "median_return_percent": _text(_percentile(ordered, Decimal("0.5"))) if enough else None,
        "var_95_loss_percent": _text(var) if var is not None else None,
        "expected_shortfall_95_loss_percent": _text(shortfall) if shortfall is not None else None,
        "sampling_interval": interval,
    }


def _requested_horizon(
    document: Mapping[str, Any], curve: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    months = document["profile"]["horizon_months"]
    first = datetime.fromisoformat(curve[0]["time"]) if curve else None
    days = calendar_horizon_days(Decimal(months), first) if months is not None and first else None
    end = first + timedelta(days=int(days)) if first is not None and days is not None else None
    last = datetime.fromisoformat(curve[-1]["time"]) if curve else None
    covered = bool(end is not None and last is not None and last >= end)
    return {
        "calendar_months": months,
        "first_window_end": end.isoformat() if end is not None else None,
        "one_window_covered": covered,
        "future_probability_of_profit": None,
        "reason": "future_probability_not_calibrated" if covered
        else "insufficient_calendar_horizon_history",
    }


def _historical_outcomes(
    result: Mapping[str, Any], document: Mapping[str, Any],
) -> dict[str, Any]:
    curve = result["equity_curve"]
    complete = result["complete_strategy_coverage"]
    risk_stopped = bool((result["metrics"] or {}).get("risk_limit_triggered"))
    rows = [
        _outcome_window_row(curve, sessions, complete=complete, seed=result["data_hash"],
                            risk_stopped=risk_stopped)
        for sessions in _OUTCOME_HORIZONS
    ]
    if result["basis"] == "cash_balance_model":
        for row in rows:
            row["reason"] = "cash_only_no_market_observations"
    computed = sum(row["status"] == "computed" for row in rows)
    status = "computed"
    if computed < len(rows):
        status = "partial" if computed else "insufficient_data"
    return {
        "status": status,
        "method": "non_overlapping_held_out_net_strategy_nav",
        "source": "no_market_observations_cash_model" if result["basis"] == "cash_balance_model"
        else "executed_strategy_equity_curve",
        "basis": result["basis"],
        "strategy_hash": result["strategy_hash"],
        "data_hash": result["data_hash"],
        "complete_strategy_coverage": complete,
        "minimum_windows": MIN_TEST_OBSERVATIONS,
        "method_source_url": _BOOTSTRAP_SOURCE,
        "future_probability_calibrated": False,
        "horizons": rows,
        "requested_horizon": _requested_horizon(document, curve),
        "limitations": [
            "Частота положительного результата на прошлом тестовом периоде, "
            "не калиброванная вероятность будущей прибыли.",
            "Окна внутри каждого горизонта не пересекаются, но могут зависеть друг от друга. "
            "Горизонты между собой не являются независимыми исследованиями.",
            "Доходности получены из фактического пути исторической модели после её "
            "издержек и налоговых допущений. Сделки и остановки не переставляются местами.",
            "21 торговая сессия не приравнивается к календарному месяцу или личному горизонту.",
            "Не менее 20 окон — технический минимум отображения оценки, "
            "не доказательство достаточной статистической точности.",
        ],
    }


def _cash_balance_research(
    result: dict[str, Any], document: Mapping[str, Any], capital: Decimal, missing: set[str],
) -> dict[str, Any]:
    """A constant nominal balance is a disclosed model, with zero market observations."""
    missing.update(
        section + "." + key for section in ("profile", "policy")
        for key, value in document[section].items() if value is None
    )
    reserve, withdrawals = (
        document["profile"][key] for key in ("reserve_rub", "planned_withdrawal_rub")
    )
    required = None
    if reserve is not None and withdrawals is not None:
        required = max(Decimal(reserve), capital) + Decimal(withdrawals)
        if required > capital:
            missing.add("cash_reserve_conflict")
    ready = not missing
    state = _Simulation(capital, {})
    state.curve.append({"time": result["period"]["to"], "nav_rub": _text(capital)})
    result.update(
        status="computed" if ready else "insufficient_data",
        basis="cash_balance_model",
        return_label="Модель денежного остатка при нулевой ставке",
        complete_strategy_coverage=ready,
        metrics=_metrics(state, capital) if ready else None,
        sources=[],
        missing_requirements=sorted(missing),
        probability_reason="Денежная модель не содержит рыночных наблюдений "
        "для оценки вероятности прибыли.",
        cash_projection={
            "method": "constant_nominal_cash_zero_rate_no_flows",
            "source": "strategy_document_and_initial_capital",
            "from": result["period"]["from"],
            "to": result["period"]["to"],
            "starting_cash_rub": _text(capital),
            "ending_cash_rub": _text(capital),
            "assumed_annual_cash_rate_percent": "0",
            "required_retained_cash_rub": _text(required) if required is not None else None,
            "personal_constraints_ready": ready,
            "scope": "Условный начальный капитал уже находится в рублях. Ставка равна нулю, "
            "пополнений и выплат в модели нет. Нулевой номинальный результат не означает "
            "отсутствия инфляционного или иных рисков. Продажа существующих активов "
            "и её издержки проверяются отдельно по текущему счёту.",
        },
    )
    result["selection"].update(
        status="ready" if ready else "insufficient_data",
        candidate_selection_ready=ready,
        missing_requirements=sorted(missing),
    )
    result["assumptions"].update(
        execution="no_orders_cash_balance_model", annual_cash_rate_percent="0",
        tax_method="no_taxable_events_in_cash_model", configurations_tested=1,
        training_fraction=None, annualization_sessions=None, tail_confidence=None,
        risk_control="not_inferred_nominal_cash_model",
    )
    result["period"]["train_end"] = None
    result["limitations"] = [result["cash_projection"]["scope"]]
    result["historical_outcomes"] = _historical_outcomes(result, document)
    return result


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
        clean, diagnostic = _prepare_research_asset(
            asset, from_at, to_at, split, document, costs, engine_version
        )
        clean_assets.append(clean)
        diagnostics.append(diagnostic)
    return clean_assets, diagnostics


def _prepare_research_asset(
    asset: ResearchAsset,
    from_at: datetime,
    to_at: datetime,
    split: datetime,
    document: Mapping[str, Any],
    costs: ResearchCosts,
    engine_version: str,
) -> tuple[ResearchAsset, dict[str, Any]]:
    """Validate one series and derive its facts from the training window only."""
    reasons = _asset_reasons(asset, from_at, to_at)
    if engine_version in CORRECTED_MATH_ENGINES:
        reasons.extend(_cashflow_reasons(asset.observed_cashflows))
    try:
        bars = _validated_bars(asset, from_at, to_at)
    except ValueError as exc:
        bars = ()
        reasons.append(str(exc))
    training = tuple(bar for bar in bars if split - bar.time >= _DAY)
    if len(training) < MIN_TRAIN_OBSERVATIONS:
        reasons.append("insufficient_training_history")
    unsafe = engine_version in CORRECTED_MATH_ENGINES and bool(
        set(reasons) & _MALFORMED_HISTORY_REASONS
    )
    candidate = asset.candidate
    if not unsafe:
        signal_bars = training
        if engine_version not in UNIT_AWARE_ENGINES:
            signal_bars = split_adjusted_history(training, asset.splits, split)
        candidate = history_candidate(
            asset.candidate,
            signal_bars,
            as_of=split,
            factors=asset.factors,
            cashflows=asset.observed_cashflows if engine_version != "1.1.0" else (),
            document=document,
            costs=costs,
            splits=asset.splits,
            corporate_action_dates=asset.corporate_action_dates,
            cashflow_coverage=asset.provider_observations.get("user_cashflow_coverage"),
            engine_version=engine_version,
        )
    prices = [_decimal(bar.close) for bar in bars]
    diagnostic = {
        "instrument_uid": asset.candidate.instrument_uid,
        "ticker": asset.candidate.ticker,
        "observations": len(bars),
        "train_observations": len(training),
        "status": "observed" if not reasons else "incomplete",
        "reasons": sorted(set(reasons)) if engine_version in CORRECTED_MATH_ENGINES else reasons,
        "price_return_percent": _text((prices[-1] / prices[0] - 1) * 100) if prices else None,
    }
    if engine_version in UNIT_AWARE_ENGINES:
        diagnostic["cashflow_yield_coverage"] = _cashflow_coverage_diagnostic(
            asset, split, candles=training,
        )
    return replace(asset, candles=bars, candidate=candidate), diagnostic


def _selection_cashflow_gaps(
    selection: dict[str, Any], diagnostics: Sequence[Mapping[str, Any]],
) -> None:
    """Explain a missing required yield without blocking unrelated eligible assets."""
    coverage = {row["instrument_uid"]: row["cashflow_yield_coverage"] for row in diagnostics}
    required = {
        "missing:cashflow_yield_percent", "missing:dividend_yield_percent",
        "missing:net_yield_percent",
    }
    missing = set(selection["missing_requirements"])
    for row in selection["candidates"]:
        if not required.intersection(row["reasons"]):
            continue
        gaps = {"missing:" + reason for reason in coverage[row["instrument_uid"]]["reasons"]}
        row["reasons"] = sorted(set(row["reasons"]) | gaps)
        if "eligible_" + row["asset_class"] in missing:
            missing.update(gaps)
    selection["missing_requirements"] = sorted(missing)


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
    *, trim_boundaries: bool = True,
) -> tuple[int, list[datetime], list[datetime], set[str]]:
    common = set.intersection(*(set(series) for series in panel.values())) if panel else set()
    missing = set()
    compared = [set(series) for series in panel.values()]
    if common and trim_boundaries:
        first, last = min(common), max(common)
        compared = [{when for when in dates if first <= when <= last} for dates in compared]
    if any(dates != common for dates in compared):
        missing.add("unaligned_history")
    training_times = sorted(when for when in common if split - when >= _DAY)
    test_times = sorted(when for when in common if when >= split)
    if len(training_times) < MIN_TRAIN_OBSERVATIONS:
        missing.add("insufficient_training_history")
    if len(test_times) < MIN_TEST_OBSERVATIONS:
        missing.add("insufficient_test_history")
    return len(common), training_times, test_times, missing


def _research_limitations(
    data: Mapping[str, Any], selection: Mapping[str, Any], basis: str,
) -> list[str]:
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
    return limitations


def _research_asset_fingerprint(asset: ResearchAsset, engine_version: str) -> dict[str, Any]:
    """Serialize every observed input with the archived engine's provenance schema."""
    row: dict[str, Any] = {
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
            key: _fact_fingerprint(f, engine_version)
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
    if engine_version != "1.1.0":
        row["fact_history"] = {
            key: [
                _fact_fingerprint(f, engine_version) for f in observations
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
    if engine_version in UNIT_AWARE_ENGINES:
        row["user_cashflow_coverage"] = _structured_fingerprint(
            asset.provider_observations.get("user_cashflow_coverage"),
        )
    return row


def _structured_fingerprint(value: object) -> Any:
    """Keep structured evidence as JSON so nested key order cannot alter its hash."""
    if isinstance(value, Mapping):
        return {key: _structured_fingerprint(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_structured_fingerprint(item) for item in value]
    if isinstance(value, (datetime, Decimal)):
        return str(value)
    return value


def _fact_fingerprint(fact: StrategyFact, engine_version: str) -> list[Any]:
    value: Any = str(fact.value)
    if engine_version in UNIT_AWARE_ENGINES and isinstance(fact.value, Mapping):
        value = _structured_fingerprint(fact.value)
    return [value, fact.available_at.isoformat(), fact.source_url]


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
    invalid_assets = {
        row["instrument_uid"] for row in diagnostics
        if engine_version in CORRECTED_MATH_ENGINES
        and set(row["reasons"]) & _MALFORMED_HISTORY_REASONS
    }
    selection = select_strategy_candidates(
        data,
        [asset.candidate for asset in clean_assets
         if asset.candidate.instrument_uid not in invalid_assets],
        as_of=split,
        engine_version=engine_version,
    )
    if engine_version in UNIT_AWARE_ENGINES:
        _selection_cashflow_gaps(selection, diagnostics)
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
        "assets": [_research_asset_fingerprint(asset, engine_version) for asset in clean_assets],
    }
    limitations = _research_limitations(data, selection, basis)
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
            "annualization_sessions": ANNUALIZATION_SESSIONS,
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
    if engine_version in CORRECTED_MATH_ENGINES and data["allocation"]["cash"] == 100:
        cash_missing = set(selection["missing_requirements"])
        cash_missing.update(
            reason for row in diagnostics if row["instrument_uid"] in invalid_assets
            for reason in row["reasons"]
        )
        return _cash_balance_research(result, data, capital, cash_missing)
    missing = _selected_evidence_requirements(data, selection, selected_assets, diagnostics, bases)
    if invalid_assets:
        missing.update(
            reason for row in diagnostics if row["instrument_uid"] in invalid_assets
            for reason in row["reasons"]
        )
    panel = {
        asset.candidate.instrument_uid: {bar.time: bar for bar in asset.candles}
        for asset in selected_assets
    }
    observations, training_times, test_times, history_missing = _common_research_times(
        panel, split, trim_boundaries=engine_version not in {"1.1.0", "1.2.0"},
    )
    if engine_version not in {"1.1.0", "1.2.0"}:
        result["history_alignment"] = {
            "method": "observed_common_sessions_without_fill",
            "common_observations": observations,
            "input_observations": {uid: len(series) for uid, series in panel.items()},
            "internal_gaps": "unaligned_history" in history_missing,
            "boundary_trimmed": any(len(series) != observations for series in panel.values()),
        }
    missing.update(history_missing)
    result["period"].update(
        observations=observations,
        train_observations=len(training_times),
        test_observations=len(test_times),
        test_from=test_times[0].isoformat() if test_times else None,
    )
    result["missing_requirements"] = sorted(missing | set(selection["missing_requirements"]))
    if engine_version in CORRECTED_MATH_ENGINES:
        result["assumptions"].update(
            liquidity="min_previous_planned_and_observed_session_volume",
            buy_sizing="previous_close_signal_bounded_by_open_mark_and_post_cost_nav_floor",
            receivable_valuation="net_of_configured_distribution_tax",
            volatility_annualization=(
                f"daily_sample_standard_deviation_sqrt_{ANNUALIZATION_SESSIONS}_no_serial_adjustment"
            ),
            turnover_budget="gross_execution_notional_plus_commission",
        )
        result["limitations"].append(
            "Дневной объём ограничивает модельное исполнение, но не доказывает "
            "доступность всего этого объёма на аукционе открытия."
        )
    if missing:
        if engine_version in CORRECTED_MATH_ENGINES:
            result["historical_outcomes"] = _historical_outcomes(result, data)
        return result
    times = [training_times[-1], *test_times]
    return _simulate_research_result(
        result, data, selected_assets, panel, times, chosen, capital, costs,
        engine_version=engine_version,
    )


def _simulate_research_result(
    result: dict[str, Any],
    data: Mapping[str, Any],
    selected_assets: Sequence[ResearchAsset],
    panel: Mapping[str, Mapping[datetime, TBankHistoricCandle]],
    times: Sequence[datetime],
    chosen: Mapping[str, Decimal],
    capital: Decimal,
    costs: ResearchCosts,
    *,
    engine_version: str,
) -> dict[str, Any]:
    """Run the admitted holdout and baseline, then attach their observed results."""
    period = strategy_rule_set(data["base_preset_id"])["rebalance_sessions"]
    try:
        state = _simulate(
            selected_assets, panel, times, chosen, data, capital, costs, rebalance_sessions=period,
            engine_version=engine_version,
        )
        baseline = _simulate(
            selected_assets, panel, times, chosen, data, capital, costs, rebalance_sessions=None,
            engine_version=engine_version,
        )
    except ValueError as exc:
        if str(exc) != "fractional_split_cash_settlement_required":
            raise
        result["missing_requirements"].append(str(exc))
        if engine_version in CORRECTED_MATH_ENGINES:
            result["historical_outcomes"] = _historical_outcomes(result, data)
        return result
    result.update(
        status="computed",
        metrics=_metrics(state, capital),
        equity_curve=state.curve,
        benchmark={
            "name": "Та же начальная корзина без перебалансировок",
            "basis": result["basis"],
            "metrics": _metrics(baseline, capital),
        },
    )
    result["stress_scenario"] = _stress_scenario(state, selected_assets, panel, times[-1], data)
    if engine_version in CORRECTED_MATH_ENGINES:
        result["historical_outcomes"] = _historical_outcomes(result, data)
        result["holding_constraints"] = {
            "evaluated_sessions": len(times) - 1,
            "breach_sessions": state.constraint_breach_sessions,
            "breaches": sorted(state.constraint_breaches),
            "unknown": sorted(state.constraint_unknown),
            "scope": "Проверка долей после каждого закрытия. Движение цен между "
            "перебалансировками может нарушать лимиты; это не гарантия ограничения потерь.",
        }
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
    if engine_version in CORRECTED_MATH_ENGINES and normalize_document(document)[
        "allocation"
    ]["cash"] == 100:
        _validated_research_capital(
            from_at, to_at, now, len(assets), initial_capital_rub, costs
        )
        return {
            "method": "not_applicable_cash_balance_model",
            "windows": [],
            "computed_windows": 0,
            "minimum_return_percent": None,
            "maximum_return_percent": None,
            "scope": "Постоянный денежный остаток при заданной нулевой ставке "
            "не является исторической проверкой устойчивости стратегии.",
        }
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
