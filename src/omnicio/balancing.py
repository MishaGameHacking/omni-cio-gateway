"""Deterministic R4 integer-lot balancing primitives.

The module has no broker write authority and no hidden policy defaults.  Callers must
supply explicit concentration, liquidity, rating and turnover limits.  Missing
critical candidate evidence makes a candidate ineligible instead of being guessed.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal
from typing import Literal

RiskState = Literal[
    "data_missing",
    "normal",
    "watch",
    "elevated",
    "critical",
    "confirmed_default",
]
RatingBucket = Literal[
    "aaa",
    "aa",
    "a",
    "bbb",
    "below_grade",
    "unknown",
    "not_applicable",
]
ScenarioStatus = Literal["feasible", "infeasible"]
ScenarioKind = Literal["hold", "deploy_cash", "replace", "fallback_cash"]


@dataclass(frozen=True, slots=True)
class AllocationCap:
    key: str
    max_percent: Decimal


@dataclass(frozen=True, slots=True)
class BalancingPolicy:
    reserve_rub: Decimal
    planned_withdrawal_rub: Decimal
    max_instrument_percent: Decimal
    max_sector_percent: Decimal
    max_issuer_percent: Decimal
    max_group_percent: Decimal
    max_below_grade_percent: Decimal
    max_unknown_percent: Decimal
    max_liquidity_days: int
    max_term_months: int
    turnover_budget_rub: Decimal
    no_trade_band_percent: Decimal
    min_replace_benefit_rub: Decimal
    allowed_asset_classes: tuple[str, ...]
    allowed_currencies: tuple[str, ...]
    allowed_risk_states: tuple[RiskState, ...]
    asset_class_caps: tuple[AllocationCap, ...]
    currency_caps: tuple[AllocationCap, ...]
    replacement_same_asset_class: bool = True


@dataclass(frozen=True, slots=True)
class Holding:
    instrument_uid: str
    ticker: str
    asset_class: str
    sector: str
    issuer_id: str
    group_id: str
    rating_bucket: RatingBucket
    currency: str
    risk_state: RiskState
    lots: int
    value_rub: Decimal
    expected_horizon_gain_rub: Decimal
    sell_fee_rub: Decimal = Decimal("0")
    exit_spread_cost_rub: Decimal = Decimal("0")
    tax_if_sold_rub: Decimal = Decimal("0")
    blocked: bool = False


@dataclass(frozen=True, slots=True)
class Candidate:
    instrument_uid: str
    ticker: str
    asset_class: str
    sector: str
    issuer_id: str
    group_id: str
    rating_bucket: RatingBucket
    currency: str
    risk_state: RiskState
    lot_size: int
    market_lot_cost_rub: Decimal
    accrued_coupon_rub_per_lot: Decimal
    buy_fee_rub_per_lot: Decimal
    spread_cost_rub_per_lot: Decimal
    expected_horizon_gain_rub_per_lot: Decimal
    uncertainty_haircut_rub_per_lot: Decimal
    credit_loss_rub_per_lot: Decimal
    liquidity_penalty_rub_per_lot: Decimal
    liquidity_days: int
    term_months: int
    ytw_percent: Decimal | None
    duration_years: Decimal | None
    api_trade_available: bool
    buy_available: bool
    required_tests_passed: bool
    evidence_complete: bool
    structure_supported: bool = True


@dataclass(frozen=True, slots=True)
class ScreenedCandidate:
    candidate: Candidate
    eligible: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PlannedTrade:
    action: Literal["buy", "sell"]
    instrument_uid: str
    ticker: str
    lots: int
    notional_rub: Decimal
    estimated_cost_rub: Decimal
    tax_rub: Decimal
    ytw_percent: Decimal | None


@dataclass(frozen=True, slots=True)
class BalancingScenario:
    kind: ScenarioKind
    status: ScenarioStatus
    reason: str
    trades: tuple[PlannedTrade, ...]
    residual_cash_rub: Decimal
    turnover_rub: Decimal
    expected_incremental_gain_rub: Decimal
    target_instrument_uid: str | None = None
    replaced_instrument_uid: str | None = None


@dataclass(frozen=True, slots=True)
class BalancingPreview:
    hold: BalancingScenario
    deploy_cash: BalancingScenario
    replacements: tuple[BalancingScenario, ...]


@dataclass(slots=True)
class _Exposure:
    instrument: dict[str, Decimal]
    sector: dict[str, Decimal]
    issuer: dict[str, Decimal]
    group: dict[str, Decimal]
    rating: dict[str, Decimal]
    asset_class: dict[str, Decimal]
    currency: dict[str, Decimal]


def build_balancing_preview(
    *,
    nav_rub: Decimal,
    cash_rub: Decimal,
    holdings: tuple[Holding, ...],
    candidates: tuple[Candidate, ...],
    policy: BalancingPolicy,
) -> BalancingPreview:
    _validate_policy(policy)
    _nonnegative(nav_rub, "nav_rub")
    _nonnegative(cash_rub, "cash_rub")
    if nav_rub <= 0:
        raise ValueError("nav_rub must be positive")

    screened = screen_candidates(candidates, policy)
    hold = _hold_scenario(cash_rub)
    deploy_cash = _optimize_cash(
        nav_rub=nav_rub,
        cash_rub=cash_rub,
        holdings=holdings,
        screened=screened,
        policy=policy,
    )
    replacements = tuple(
        _replacement_scenario(
            holding=holding,
            nav_rub=nav_rub,
            screened=screened,
            holdings=holdings,
            policy=policy,
        )
        for holding in holdings
        if holding.risk_state in {"elevated", "critical", "confirmed_default"}
    )
    return BalancingPreview(
        hold=hold,
        deploy_cash=deploy_cash,
        replacements=replacements,
    )


def screen_candidates(
    candidates: tuple[Candidate, ...],
    policy: BalancingPolicy,
) -> tuple[ScreenedCandidate, ...]:
    _validate_policy(policy)
    screened: list[ScreenedCandidate] = []
    for item in candidates:
        reasons = _candidate_reasons(item, policy)
        screened.append(
            ScreenedCandidate(
                candidate=item,
                eligible=not reasons,
                reasons=reasons,
            )
        )
    return tuple(screened)


def _candidate_reasons(candidate: Candidate, policy: BalancingPolicy) -> tuple[str, ...]:
    reasons: list[str] = []
    if not candidate.evidence_complete:
        reasons.append("critical_evidence_missing")
    if not candidate.structure_supported:
        reasons.append("instrument_structure_not_supported")
    if not candidate.api_trade_available:
        reasons.append("api_trade_unavailable")
    if not candidate.buy_available:
        reasons.append("buy_unavailable")
    if not candidate.required_tests_passed:
        reasons.append("required_tests_missing")
    if candidate.lot_size <= 0:
        reasons.append("invalid_lot_size")
    if candidate.market_lot_cost_rub <= 0:
        reasons.append("missing_lot_cost")
    if candidate.asset_class not in policy.allowed_asset_classes:
        reasons.append("asset_class_not_allowed")
    if candidate.currency.upper() not in policy.allowed_currencies:
        reasons.append("currency_not_allowed")
    if candidate.risk_state not in policy.allowed_risk_states:
        reasons.append("risk_state_not_allowed")
    if candidate.liquidity_days < 0 or candidate.liquidity_days > policy.max_liquidity_days:
        reasons.append("liquidity_limit")
    if candidate.term_months < 0:
        reasons.append("term_limit")
    if candidate.asset_class == "bond":
        if candidate.term_months > policy.max_term_months:
            reasons.append("term_limit")
        if candidate.ytw_percent is None:
            reasons.append("bond_ytw_missing")
        if candidate.duration_years is None:
            reasons.append("bond_duration_missing")
    if _cap_for(policy.asset_class_caps, candidate.asset_class) is None:
        reasons.append("asset_class_cap_missing")
    if _cap_for(policy.currency_caps, candidate.currency.upper()) is None:
        reasons.append("currency_cap_missing")
    for value, name in (
        (candidate.market_lot_cost_rub, "market_lot_cost_rub"),
        (candidate.accrued_coupon_rub_per_lot, "accrued_coupon_rub_per_lot"),
        (candidate.buy_fee_rub_per_lot, "buy_fee_rub_per_lot"),
        (candidate.spread_cost_rub_per_lot, "spread_cost_rub_per_lot"),
        (candidate.uncertainty_haircut_rub_per_lot, "uncertainty_haircut_rub_per_lot"),
        (candidate.credit_loss_rub_per_lot, "credit_loss_rub_per_lot"),
        (candidate.liquidity_penalty_rub_per_lot, "liquidity_penalty_rub_per_lot"),
    ):
        if value < 0:
            reasons.append(f"negative_{name}")
    return tuple(dict.fromkeys(reasons))


def _hold_scenario(cash_rub: Decimal) -> BalancingScenario:
    return BalancingScenario(
        kind="hold",
        status="feasible",
        reason="hold_baseline",
        trades=(),
        residual_cash_rub=cash_rub,
        turnover_rub=Decimal("0"),
        expected_incremental_gain_rub=Decimal("0"),
    )


def _optimize_cash(
    *,
    nav_rub: Decimal,
    cash_rub: Decimal,
    holdings: tuple[Holding, ...],
    screened: tuple[ScreenedCandidate, ...],
    policy: BalancingPolicy,
) -> BalancingScenario:
    required_cash = policy.reserve_rub + policy.planned_withdrawal_rub
    available = cash_rub - required_cash
    if available <= 0:
        return BalancingScenario(
            kind="deploy_cash",
            status="infeasible",
            reason="reserve_or_withdrawal_consumes_free_cash",
            trades=(),
            residual_cash_rub=cash_rub,
            turnover_rub=Decimal("0"),
            expected_incremental_gain_rub=Decimal("0"),
        )

    eligible = [
        item.candidate
        for item in screened
        if item.eligible and _net_gain_per_lot(item.candidate) > 0
    ]
    if not eligible:
        return BalancingScenario(
            kind="deploy_cash",
            status="infeasible",
            reason="no_eligible_positive_candidate",
            trades=(),
            residual_cash_rub=cash_rub,
            turnover_rub=Decimal("0"),
            expected_incremental_gain_rub=Decimal("0"),
        )

    exposure = _build_exposure(holdings)
    trades: list[PlannedTrade] = []
    turnover = Decimal("0")
    incremental_gain = Decimal("0")

    eligible.sort(
        key=lambda item: (
            -_gain_efficiency(item),
            item.instrument_uid,
        )
    )
    for candidate in eligible:
        if available <= 0:
            break
        lots = _max_buy_lots(
            candidate=candidate,
            nav_rub=nav_rub,
            cash_available=available,
            turnover_remaining=max(Decimal("0"), policy.turnover_budget_rub - turnover),
            exposure=exposure,
            policy=policy,
        )
        if lots <= 0:
            continue

        spend = _transaction_cost_per_lot(candidate) * lots
        notional = _exposure_value_per_lot(candidate) * lots
        trade_cost = (
            candidate.buy_fee_rub_per_lot + candidate.spread_cost_rub_per_lot
        ) * lots
        gain = _net_gain_per_lot(candidate) * lots
        available -= spend
        turnover += notional
        incremental_gain += gain
        _apply_candidate_exposure(exposure, candidate, notional)
        trades.append(
            PlannedTrade(
                action="buy",
                instrument_uid=candidate.instrument_uid,
                ticker=candidate.ticker,
                lots=lots,
                notional_rub=notional,
                estimated_cost_rub=trade_cost,
                tax_rub=Decimal("0"),
                ytw_percent=candidate.ytw_percent,
            )
        )

    if not trades:
        return BalancingScenario(
            kind="deploy_cash",
            status="infeasible",
            reason="integer_lot_or_policy_limits_block_all_buys",
            trades=(),
            residual_cash_rub=cash_rub,
            turnover_rub=Decimal("0"),
            expected_incremental_gain_rub=Decimal("0"),
        )
    return BalancingScenario(
        kind="deploy_cash",
        status="feasible",
        reason="integer_lot_allocation",
        trades=tuple(trades),
        residual_cash_rub=required_cash + available,
        turnover_rub=turnover,
        expected_incremental_gain_rub=incremental_gain,
    )


def _replacement_scenario(
    *,
    holding: Holding,
    nav_rub: Decimal,
    screened: tuple[ScreenedCandidate, ...],
    holdings: tuple[Holding, ...],
    policy: BalancingPolicy,
) -> BalancingScenario:
    if holding.blocked:
        return _fallback_cash(holding, "holding_blocked")
    if holding.lots <= 0 or holding.value_rub <= 0:
        return _fallback_cash(holding, "holding_not_sellable")

    sale_cost = holding.sell_fee_rub + holding.exit_spread_cost_rub + holding.tax_if_sold_rub
    sale_proceeds = holding.value_rub - sale_cost
    if sale_proceeds <= 0:
        return _fallback_cash(holding, "sale_costs_consume_proceeds")

    base_holdings = tuple(
        item
        for item in holdings
        if item.instrument_uid != holding.instrument_uid
    )
    base_exposure = _build_exposure(base_holdings)
    candidates = [
        item.candidate
        for item in screened
        if item.eligible
        and item.candidate.instrument_uid != holding.instrument_uid
        and _net_gain_per_lot(item.candidate) > 0
        and (
            not policy.replacement_same_asset_class
            or item.candidate.asset_class == holding.asset_class
        )
    ]
    if not candidates:
        return _fallback_cash(holding, "no_eligible_replacement")

    best: BalancingScenario | None = None
    for candidate in candidates:
        lots = _max_buy_lots(
            candidate=candidate,
            nav_rub=nav_rub,
            cash_available=sale_proceeds,
            turnover_remaining=max(Decimal("0"), policy.turnover_budget_rub - holding.value_rub),
            exposure=_clone_exposure(base_exposure),
            policy=policy,
        )
        if lots <= 0:
            continue
        spend = _transaction_cost_per_lot(candidate) * lots
        notional = _exposure_value_per_lot(candidate) * lots
        buy_cost = (
            candidate.buy_fee_rub_per_lot + candidate.spread_cost_rub_per_lot
        ) * lots
        turnover = holding.value_rub + notional
        if turnover > policy.turnover_budget_rub:
            continue

        replacement_gain = _net_gain_per_lot(candidate) * lots - sale_cost
        improvement = replacement_gain - holding.expected_horizon_gain_rub
        threshold = max(
            policy.min_replace_benefit_rub,
            holding.value_rub * policy.no_trade_band_percent / Decimal("100"),
        )
        if improvement <= threshold:
            continue

        scenario = BalancingScenario(
            kind="replace",
            status="feasible",
            reason="net_improvement_after_costs",
            trades=(
                PlannedTrade(
                    action="sell",
                    instrument_uid=holding.instrument_uid,
                    ticker=holding.ticker,
                    lots=holding.lots,
                    notional_rub=holding.value_rub,
                    estimated_cost_rub=holding.sell_fee_rub + holding.exit_spread_cost_rub,
                    tax_rub=holding.tax_if_sold_rub,
                    ytw_percent=None,
                ),
                PlannedTrade(
                    action="buy",
                    instrument_uid=candidate.instrument_uid,
                    ticker=candidate.ticker,
                    lots=lots,
                    notional_rub=notional,
                    estimated_cost_rub=buy_cost,
                    tax_rub=Decimal("0"),
                    ytw_percent=candidate.ytw_percent,
                ),
            ),
            residual_cash_rub=sale_proceeds - spend,
            turnover_rub=turnover,
            expected_incremental_gain_rub=improvement,
            target_instrument_uid=candidate.instrument_uid,
            replaced_instrument_uid=holding.instrument_uid,
        )
        if best is None or (
            scenario.expected_incremental_gain_rub,
            candidate.instrument_uid,
        ) > (
            best.expected_incremental_gain_rub,
            best.target_instrument_uid or "",
        ):
            best = scenario

    if best is not None:
        return best
    return _fallback_cash(holding, "no_replacement_clears_costs_and_no_trade_band")


def _fallback_cash(holding: Holding, reason: str) -> BalancingScenario:
    return BalancingScenario(
        kind="fallback_cash",
        status="infeasible",
        reason=reason,
        trades=(),
        residual_cash_rub=Decimal("0"),
        turnover_rub=Decimal("0"),
        expected_incremental_gain_rub=Decimal("0"),
        replaced_instrument_uid=holding.instrument_uid,
    )


def _max_buy_lots(
    *,
    candidate: Candidate,
    nav_rub: Decimal,
    cash_available: Decimal,
    turnover_remaining: Decimal,
    exposure: _Exposure,
    policy: BalancingPolicy,
) -> int:
    transaction = _transaction_cost_per_lot(candidate)
    exposure_value = _exposure_value_per_lot(candidate)
    if transaction <= 0 or exposure_value <= 0:
        return 0

    limits = [
        _floor_lots(cash_available, transaction),
        _floor_lots(turnover_remaining, exposure_value),
        _capacity_lots(
            nav_rub,
            policy.max_instrument_percent,
            exposure.instrument.get(candidate.instrument_uid, Decimal("0")),
            exposure_value,
        ),
        _capacity_lots(
            nav_rub,
            policy.max_sector_percent,
            exposure.sector.get(candidate.sector, Decimal("0")),
            exposure_value,
        ),
        _capacity_lots(
            nav_rub,
            policy.max_issuer_percent,
            exposure.issuer.get(candidate.issuer_id, Decimal("0")),
            exposure_value,
        ),
        _capacity_lots(
            nav_rub,
            policy.max_group_percent,
            exposure.group.get(candidate.group_id, Decimal("0")),
            exposure_value,
        ),
    ]

    class_cap = _cap_for(policy.asset_class_caps, candidate.asset_class)
    currency_cap = _cap_for(policy.currency_caps, candidate.currency.upper())
    if class_cap is None or currency_cap is None:
        return 0
    limits.extend(
        (
            _capacity_lots(
                nav_rub,
                class_cap,
                exposure.asset_class.get(candidate.asset_class, Decimal("0")),
                exposure_value,
            ),
            _capacity_lots(
                nav_rub,
                currency_cap,
                exposure.currency.get(candidate.currency.upper(), Decimal("0")),
                exposure_value,
            ),
        )
    )
    if candidate.rating_bucket == "below_grade":
        limits.append(
            _capacity_lots(
                nav_rub,
                policy.max_below_grade_percent,
                exposure.rating.get("below_grade", Decimal("0")),
                exposure_value,
            )
        )
    elif candidate.rating_bucket == "unknown":
        limits.append(
            _capacity_lots(
                nav_rub,
                policy.max_unknown_percent,
                exposure.rating.get("unknown", Decimal("0")),
                exposure_value,
            )
        )
    return max(0, min(limits))


def _build_exposure(holdings: tuple[Holding, ...]) -> _Exposure:
    exposure = _Exposure({}, {}, {}, {}, {}, {}, {})
    for item in holdings:
        if item.value_rub <= 0:
            continue
        exposure.instrument[item.instrument_uid] = (
            exposure.instrument.get(item.instrument_uid, Decimal("0")) + item.value_rub
        )
        for mapping, key in (
            (exposure.sector, item.sector),
            (exposure.issuer, item.issuer_id),
            (exposure.group, item.group_id),
            (exposure.rating, item.rating_bucket),
            (exposure.asset_class, item.asset_class),
            (exposure.currency, item.currency.upper()),
        ):
            mapping[key] = mapping.get(key, Decimal("0")) + item.value_rub
    return exposure


def _clone_exposure(source: _Exposure) -> _Exposure:
    return _Exposure(
        dict(source.instrument),
        dict(source.sector),
        dict(source.issuer),
        dict(source.group),
        dict(source.rating),
        dict(source.asset_class),
        dict(source.currency),
    )


def _apply_candidate_exposure(exposure: _Exposure, candidate: Candidate, value: Decimal) -> None:
    exposure.instrument[candidate.instrument_uid] = (
        exposure.instrument.get(candidate.instrument_uid, Decimal("0")) + value
    )
    for mapping, key in (
        (exposure.sector, candidate.sector),
        (exposure.issuer, candidate.issuer_id),
        (exposure.group, candidate.group_id),
        (exposure.rating, candidate.rating_bucket),
        (exposure.asset_class, candidate.asset_class),
        (exposure.currency, candidate.currency.upper()),
    ):
        mapping[key] = mapping.get(key, Decimal("0")) + value


def _transaction_cost_per_lot(candidate: Candidate) -> Decimal:
    return (
        _exposure_value_per_lot(candidate)
        + candidate.buy_fee_rub_per_lot
        + candidate.spread_cost_rub_per_lot
    )


def _exposure_value_per_lot(candidate: Candidate) -> Decimal:
    return candidate.market_lot_cost_rub + candidate.accrued_coupon_rub_per_lot


def _net_gain_per_lot(candidate: Candidate) -> Decimal:
    return (
        candidate.expected_horizon_gain_rub_per_lot
        - candidate.buy_fee_rub_per_lot
        - candidate.spread_cost_rub_per_lot
        - candidate.uncertainty_haircut_rub_per_lot
        - candidate.credit_loss_rub_per_lot
        - candidate.liquidity_penalty_rub_per_lot
    )


def _gain_efficiency(candidate: Candidate) -> Decimal:
    transaction = _transaction_cost_per_lot(candidate)
    if transaction <= 0:
        return Decimal("-Infinity")
    return _net_gain_per_lot(candidate) / transaction


def _capacity_lots(
    nav_rub: Decimal,
    max_percent: Decimal,
    current_value: Decimal,
    lot_value: Decimal,
) -> int:
    capacity = nav_rub * max_percent / Decimal("100") - current_value
    return _floor_lots(capacity, lot_value)


def _floor_lots(value: Decimal, per_lot: Decimal) -> int:
    if value <= 0 or per_lot <= 0:
        return 0
    return int((value / per_lot).to_integral_value(rounding=ROUND_FLOOR))


def _cap_for(caps: tuple[AllocationCap, ...], key: str) -> Decimal | None:
    for cap in caps:
        if cap.key == key:
            return cap.max_percent
    return None


def _validate_policy(policy: BalancingPolicy) -> None:
    for value, name in (
        (policy.reserve_rub, "reserve_rub"),
        (policy.planned_withdrawal_rub, "planned_withdrawal_rub"),
        (policy.turnover_budget_rub, "turnover_budget_rub"),
        (policy.min_replace_benefit_rub, "min_replace_benefit_rub"),
    ):
        _nonnegative(value, name)
    for value, name in (
        (policy.max_instrument_percent, "max_instrument_percent"),
        (policy.max_sector_percent, "max_sector_percent"),
        (policy.max_issuer_percent, "max_issuer_percent"),
        (policy.max_group_percent, "max_group_percent"),
        (policy.max_below_grade_percent, "max_below_grade_percent"),
        (policy.max_unknown_percent, "max_unknown_percent"),
        (policy.no_trade_band_percent, "no_trade_band_percent"),
    ):
        _percent(value, name)
    if policy.max_liquidity_days < 0:
        raise ValueError("max_liquidity_days must be non-negative")
    if policy.max_term_months < 0:
        raise ValueError("max_term_months must be non-negative")
    if not policy.allowed_asset_classes:
        raise ValueError("allowed_asset_classes must not be empty")
    if not policy.allowed_currencies:
        raise ValueError("allowed_currencies must not be empty")
    if not policy.allowed_risk_states:
        raise ValueError("allowed_risk_states must not be empty")
    _validate_caps(policy.asset_class_caps, "asset_class_caps")
    _validate_caps(policy.currency_caps, "currency_caps")


def _validate_caps(caps: tuple[AllocationCap, ...], name: str) -> None:
    if not caps:
        raise ValueError(f"{name} must not be empty")
    seen: set[str] = set()
    for cap in caps:
        if not cap.key or cap.key in seen:
            raise ValueError(f"{name} contains invalid or duplicate key")
        seen.add(cap.key)
        _percent(cap.max_percent, f"{name}.{cap.key}")


def _percent(value: Decimal, name: str) -> None:
    if value < 0 or value > 100:
        raise ValueError(f"{name} must be between 0 and 100")


def _nonnegative(value: Decimal, name: str) -> None:
    if not value.is_finite() or value < 0:
        raise ValueError(f"{name} must be a finite non-negative number")
