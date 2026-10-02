"""Deterministic R4 candidate screening and integer-lot allocation.

This module is read-only decision math. It never calls a broker and never grants
execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal, Mapping

RatingTier = Literal["AAA", "AA", "A", "BBB", "below_investment_grade", "unknown"]
PlanStatus = Literal["feasible", "hold", "infeasible"]


@dataclass(frozen=True, slots=True)
class OptimizerCandidate:
    instrument_uid: str
    ticker: str
    name: str
    instrument_type: str
    asset_class: str
    issuer_id: str
    issuer_country_code: str
    group_id: str
    sector: str
    rating_tier: RatingTier
    funding_per_lot_rub: Decimal
    exposure_per_lot_rub: Decimal
    commission_per_lot_rub: Decimal
    spread_cost_per_lot_rub: Decimal
    estimated_tax_per_lot_rub: Decimal
    ytw_percent: Decimal | None
    duration_years: Decimal | None
    quote_at: datetime | None
    evidence_at: datetime | None
    api_trade_available: bool | None
    buy_available: bool | None
    liquidity: bool | None
    for_qual_investor: bool | None
    required_tests: tuple[str, ...]
    real_exchange: str
    floating_coupon: bool | None
    perpetual: bool | None
    amortization: bool | None
    subordinated: bool | None


@dataclass(frozen=True, slots=True)
class PortfolioExposureState:
    nav_rub: Decimal
    available_cash_rub: Decimal
    instrument_rub: Mapping[str, Decimal]
    issuer_rub: Mapping[str, Decimal]
    group_rub: Mapping[str, Decimal]
    sector_rub: Mapping[str, Decimal]
    asset_class_rub: Mapping[str, Decimal]
    rating_rub: Mapping[RatingTier, Decimal]


@dataclass(frozen=True, slots=True)
class OptimizationPolicy:
    reserve_rub: Decimal
    planned_withdrawal_rub: Decimal
    horizon_months: int
    max_duration_years: Decimal
    max_instrument_percent: Decimal
    max_issuer_percent: Decimal
    max_group_percent: Decimal
    max_sector_percent: Decimal
    max_asset_class_percent: Decimal
    rating_max_percent: Mapping[RatingTier, Decimal]
    max_turnover_percent: Decimal
    min_trade_rub: Decimal
    no_trade_band_percent: Decimal
    inflation_percent: Decimal
    rating_haircut_percent: Mapping[RatingTier, Decimal]
    max_quote_age_seconds: int
    max_evidence_age_seconds: int
    allow_below_investment_grade: bool
    is_qualified_investor: bool


@dataclass(frozen=True, slots=True)
class CandidateScreen:
    candidate: OptimizerCandidate
    eligible: bool
    reasons: tuple[str, ...]
    net_real_ytw_percent: Decimal | None


@dataclass(frozen=True, slots=True)
class LotAllocation:
    instrument_uid: str
    ticker: str
    lots: int
    funding_rub: Decimal
    exposure_rub: Decimal
    net_real_ytw_percent: Decimal


@dataclass(frozen=True, slots=True)
class OptimizationPlan:
    status: PlanStatus
    policy_version: str
    spendable_cash_rub: Decimal
    allocated_cash_rub: Decimal
    residual_cash_rub: Decimal
    allocations: tuple[LotAllocation, ...]
    screens: tuple[CandidateScreen, ...]
    reasons: tuple[str, ...]
    execution_enabled: bool = False


@dataclass(frozen=True, slots=True)
class ReplacementCase:
    source_instrument_uid: str
    source_market_value_rub: Decimal
    source_hold_ytw_percent: Decimal | None
    sell_commission_rub: Decimal
    estimated_tax_rub: Decimal | None
    candidate: OptimizerCandidate


@dataclass(frozen=True, slots=True)
class ReplacementScenario:
    action: Literal["hold", "replace"]
    source_instrument_uid: str
    target_instrument_uid: str | None
    lots: int
    funding_rub: Decimal
    projected_improvement_rub: Decimal | None
    reasons: tuple[str, ...]
    execution_enabled: bool = False


R4_OPTIMIZER_VERSION = "r4-integer-lots-v1"


def screen_candidate(
    candidate: OptimizerCandidate,
    policy: OptimizationPolicy,
    *,
    now: datetime,
) -> CandidateScreen:
    _validate_policy(policy)
    observed_at = _utc(now)
    reasons: list[str] = []

    if candidate.instrument_type != "bond":
        reasons.append("objective_not_supported_for_instrument_type")
    if candidate.asset_class != "bonds":
        reasons.append("asset_class_mismatch")
    if candidate.issuer_country_code != "RU" or not candidate.issuer_id:
        reasons.append("verified_russian_issuer_missing")
    if not candidate.group_id:
        reasons.append("verified_issuer_group_missing")
    if not candidate.sector:
        reasons.append("sector_missing")
    if candidate.real_exchange != "REAL_EXCHANGE_MOEX":
        reasons.append("exchange_not_verified_moex")
    if candidate.api_trade_available is not True:
        reasons.append("api_trade_unavailable")
    if candidate.buy_available is not True:
        reasons.append("buy_unavailable")
    if candidate.liquidity is not True:
        reasons.append("liquidity_not_verified")
    if candidate.required_tests:
        reasons.append("broker_tests_required")
    if candidate.for_qual_investor is True and not policy.is_qualified_investor:
        reasons.append("qualified_investor_required")

    if candidate.rating_tier == "unknown":
        reasons.append("credit_rating_missing")
    elif (
        candidate.rating_tier == "below_investment_grade"
        and not policy.allow_below_investment_grade
    ):
        reasons.append("below_investment_grade_not_allowed")
    elif candidate.rating_tier not in policy.rating_max_percent:
        reasons.append("rating_limit_missing")

    if candidate.ytw_percent is None:
        reasons.append("ytw_missing")
    if candidate.duration_years is None:
        reasons.append("duration_missing")
    elif candidate.duration_years <= 0:
        reasons.append("duration_invalid")
    elif candidate.duration_years > policy.max_duration_years:
        reasons.append("duration_limit_exceeded")

    if candidate.floating_coupon is not False:
        reasons.append("floating_coupon_cashflow_not_supported")
    if candidate.perpetual is not False:
        reasons.append("perpetual_cashflow_not_supported")
    if candidate.amortization is not False:
        reasons.append("amortizing_cashflow_not_supported")
    if candidate.subordinated is not False:
        reasons.append("subordinated_bond_not_allowed")

    if candidate.funding_per_lot_rub <= 0 or candidate.exposure_per_lot_rub <= 0:
        reasons.append("lot_cost_invalid")
    if any(
        value < 0
        for value in (
            candidate.commission_per_lot_rub,
            candidate.spread_cost_per_lot_rub,
            candidate.estimated_tax_per_lot_rub,
        )
    ):
        reasons.append("transaction_cost_invalid")

    quote_age = _age_seconds(candidate.quote_at, observed_at)
    if quote_age is None or quote_age > policy.max_quote_age_seconds:
        reasons.append("quote_stale_or_missing")
    evidence_age = _age_seconds(candidate.evidence_at, observed_at)
    if evidence_age is None or evidence_age > policy.max_evidence_age_seconds:
        reasons.append("evidence_stale_or_missing")

    net_real = None
    if not reasons and candidate.ytw_percent is not None:
        haircut = policy.rating_haircut_percent.get(candidate.rating_tier)
        if haircut is None:
            reasons.append("rating_haircut_missing")
        else:
            net_real = _net_real_ytw(candidate, policy, haircut)
            if net_real <= policy.no_trade_band_percent:
                reasons.append("return_does_not_clear_no_trade_band")
                net_real = None

    return CandidateScreen(
        candidate=candidate,
        eligible=not reasons,
        reasons=tuple(reasons),
        net_real_ytw_percent=net_real,
    )


def optimize_integer_lots(
    state: PortfolioExposureState,
    candidates: tuple[OptimizerCandidate, ...],
    policy: OptimizationPolicy,
    *,
    now: datetime,
) -> OptimizationPlan:
    _validate_state(state)
    _validate_policy(policy)
    screens = tuple(screen_candidate(item, policy, now=now) for item in candidates)
    spendable = max(
        Decimal(0),
        state.available_cash_rub - policy.reserve_rub - policy.planned_withdrawal_rub,
    )
    turnover_budget = _limit_value(state.nav_rub, policy.max_turnover_percent)
    budget = min(spendable, turnover_budget)

    if budget < policy.min_trade_rub:
        return OptimizationPlan(
            status="hold",
            policy_version=R4_OPTIMIZER_VERSION,
            spendable_cash_rub=spendable,
            allocated_cash_rub=Decimal(0),
            residual_cash_rub=spendable,
            allocations=(),
            screens=screens,
            reasons=("insufficient_economic_trade_budget",),
        )

    eligible = [
        screen
        for screen in screens
        if screen.eligible and screen.net_real_ytw_percent is not None
    ]
    eligible.sort(
        key=lambda item: (
            -item.net_real_ytw_percent,
            item.candidate.instrument_uid,
        )
    )
    if not eligible:
        return OptimizationPlan(
            status="infeasible",
            policy_version=R4_OPTIMIZER_VERSION,
            spendable_cash_rub=spendable,
            allocated_cash_rub=Decimal(0),
            residual_cash_rub=spendable,
            allocations=(),
            screens=screens,
            reasons=("no_eligible_candidate",),
        )

    allocated_by_instrument: dict[str, Decimal] = {}
    allocated_by_issuer: dict[str, Decimal] = {}
    allocated_by_group: dict[str, Decimal] = {}
    allocated_by_sector: dict[str, Decimal] = {}
    allocated_by_class: dict[str, Decimal] = {}
    allocated_by_rating: dict[RatingTier, Decimal] = {}
    remaining = budget
    allocations: list[LotAllocation] = []

    for screen in eligible:
        candidate = screen.candidate
        assert screen.net_real_ytw_percent is not None
        exposure_capacity = _candidate_capacity(
            state,
            policy,
            candidate,
            allocated_by_instrument,
            allocated_by_issuer,
            allocated_by_group,
            allocated_by_sector,
            allocated_by_class,
            allocated_by_rating,
        )
        max_by_exposure = int(exposure_capacity // candidate.exposure_per_lot_rub)
        max_by_cash = int(remaining // candidate.funding_per_lot_rub)
        lots = min(max_by_exposure, max_by_cash)
        if lots <= 0:
            continue

        funding = candidate.funding_per_lot_rub * lots
        if funding < policy.min_trade_rub:
            minimum_lots = _ceil_div(
                policy.min_trade_rub,
                candidate.funding_per_lot_rub,
            )
            if minimum_lots > lots:
                continue
            lots = minimum_lots
            funding = candidate.funding_per_lot_rub * lots

        exposure = candidate.exposure_per_lot_rub * lots
        allocations.append(
            LotAllocation(
                instrument_uid=candidate.instrument_uid,
                ticker=candidate.ticker,
                lots=lots,
                funding_rub=funding,
                exposure_rub=exposure,
                net_real_ytw_percent=screen.net_real_ytw_percent,
            )
        )
        remaining -= funding
        _add(allocated_by_instrument, candidate.instrument_uid, exposure)
        _add(allocated_by_issuer, candidate.issuer_id, exposure)
        _add(allocated_by_group, candidate.group_id, exposure)
        _add(allocated_by_sector, candidate.sector, exposure)
        _add(allocated_by_class, candidate.asset_class, exposure)
        _add(allocated_by_rating, candidate.rating_tier, exposure)

        if remaining < policy.min_trade_rub:
            break

    allocated = budget - remaining
    if not allocations:
        return OptimizationPlan(
            status="infeasible",
            policy_version=R4_OPTIMIZER_VERSION,
            spendable_cash_rub=spendable,
            allocated_cash_rub=Decimal(0),
            residual_cash_rub=spendable,
            allocations=(),
            screens=screens,
            reasons=("integer_lot_constraints_infeasible",),
        )

    return OptimizationPlan(
        status="feasible",
        policy_version=R4_OPTIMIZER_VERSION,
        spendable_cash_rub=spendable,
        allocated_cash_rub=allocated,
        residual_cash_rub=spendable - allocated,
        allocations=tuple(allocations),
        screens=screens,
        reasons=(),
    )


def compare_replacement(
    case: ReplacementCase,
    policy: OptimizationPolicy,
    *,
    now: datetime,
) -> ReplacementScenario:
    _validate_policy(policy)
    screen = screen_candidate(case.candidate, policy, now=now)
    if not screen.eligible or screen.net_real_ytw_percent is None:
        return ReplacementScenario(
            action="hold",
            source_instrument_uid=case.source_instrument_uid,
            target_instrument_uid=None,
            lots=0,
            funding_rub=Decimal(0),
            projected_improvement_rub=None,
            reasons=("replacement_candidate_ineligible", *screen.reasons),
        )
    if case.source_hold_ytw_percent is None:
        return _hold_replacement(case, "hold_ytw_missing")
    if case.estimated_tax_rub is None:
        return _hold_replacement(case, "tax_estimate_missing")
    if (
        case.source_market_value_rub <= 0
        or case.sell_commission_rub < 0
        or case.estimated_tax_rub < 0
    ):
        return _hold_replacement(case, "replacement_cost_invalid")

    funding = (
        case.source_market_value_rub
        - case.sell_commission_rub
        - case.estimated_tax_rub
    )
    if funding <= 0:
        return _hold_replacement(case, "replacement_has_no_funding")

    lots = int(funding // case.candidate.funding_per_lot_rub)
    if lots <= 0:
        return _hold_replacement(case, "replacement_integer_lot_infeasible")

    invested = case.candidate.funding_per_lot_rub * lots
    years = Decimal(policy.horizon_months) / Decimal(12)
    hold_return = (
        case.source_market_value_rub
        * case.source_hold_ytw_percent
        / Decimal(100)
        * years
    )
    replacement_return = (
        case.candidate.exposure_per_lot_rub
        * lots
        * screen.net_real_ytw_percent
        / Decimal(100)
        * years
    )
    residual = funding - invested
    residual_return = (
        residual
        * (policy.inflation_percent + policy.no_trade_band_percent)
        / Decimal(100)
        * years
    )
    improvement = (
        replacement_return
        + residual_return
        - hold_return
        - case.sell_commission_rub
        - case.estimated_tax_rub
    )
    hurdle = (
        case.source_market_value_rub
        * policy.no_trade_band_percent
        / Decimal(100)
        * years
    )
    if improvement <= hurdle:
        return ReplacementScenario(
            action="hold",
            source_instrument_uid=case.source_instrument_uid,
            target_instrument_uid=None,
            lots=0,
            funding_rub=Decimal(0),
            projected_improvement_rub=improvement,
            reasons=("replacement_does_not_clear_no_trade_band",),
        )

    return ReplacementScenario(
        action="replace",
        source_instrument_uid=case.source_instrument_uid,
        target_instrument_uid=case.candidate.instrument_uid,
        lots=lots,
        funding_rub=invested,
        projected_improvement_rub=improvement,
        reasons=(),
    )


def _hold_replacement(case: ReplacementCase, reason: str) -> ReplacementScenario:
    return ReplacementScenario(
        action="hold",
        source_instrument_uid=case.source_instrument_uid,
        target_instrument_uid=None,
        lots=0,
        funding_rub=Decimal(0),
        projected_improvement_rub=None,
        reasons=(reason,),
    )


def _candidate_capacity(
    state: PortfolioExposureState,
    policy: OptimizationPolicy,
    candidate: OptimizerCandidate,
    allocated_instrument: Mapping[str, Decimal],
    allocated_issuer: Mapping[str, Decimal],
    allocated_group: Mapping[str, Decimal],
    allocated_sector: Mapping[str, Decimal],
    allocated_class: Mapping[str, Decimal],
    allocated_rating: Mapping[RatingTier, Decimal],
) -> Decimal:
    limits = (
        _remaining_limit(
            state.nav_rub,
            policy.max_instrument_percent,
            state.instrument_rub.get(candidate.instrument_uid, Decimal(0)),
            allocated_instrument.get(candidate.instrument_uid, Decimal(0)),
        ),
        _remaining_limit(
            state.nav_rub,
            policy.max_issuer_percent,
            state.issuer_rub.get(candidate.issuer_id, Decimal(0)),
            allocated_issuer.get(candidate.issuer_id, Decimal(0)),
        ),
        _remaining_limit(
            state.nav_rub,
            policy.max_group_percent,
            state.group_rub.get(candidate.group_id, Decimal(0)),
            allocated_group.get(candidate.group_id, Decimal(0)),
        ),
        _remaining_limit(
            state.nav_rub,
            policy.max_sector_percent,
            state.sector_rub.get(candidate.sector, Decimal(0)),
            allocated_sector.get(candidate.sector, Decimal(0)),
        ),
        _remaining_limit(
            state.nav_rub,
            policy.max_asset_class_percent,
            state.asset_class_rub.get(candidate.asset_class, Decimal(0)),
            allocated_class.get(candidate.asset_class, Decimal(0)),
        ),
        _remaining_limit(
            state.nav_rub,
            policy.rating_max_percent[candidate.rating_tier],
            state.rating_rub.get(candidate.rating_tier, Decimal(0)),
            allocated_rating.get(candidate.rating_tier, Decimal(0)),
        ),
    )
    return max(Decimal(0), min(limits))


def _remaining_limit(
    nav: Decimal,
    limit_percent: Decimal,
    current: Decimal,
    allocated: Decimal,
) -> Decimal:
    return _limit_value(nav, limit_percent) - current - allocated


def _limit_value(nav: Decimal, percent: Decimal) -> Decimal:
    return nav * percent / Decimal(100)


def _net_real_ytw(
    candidate: OptimizerCandidate,
    policy: OptimizationPolicy,
    haircut: Decimal,
) -> Decimal:
    assert candidate.ytw_percent is not None
    years = Decimal(policy.horizon_months) / Decimal(12)
    one_time_cost = (
        candidate.commission_per_lot_rub
        + candidate.spread_cost_per_lot_rub
        + candidate.estimated_tax_per_lot_rub
    )
    annualized_cost_drag = (
        one_time_cost
        / candidate.exposure_per_lot_rub
        * Decimal(100)
        / years
    )
    return (
        candidate.ytw_percent
        - policy.inflation_percent
        - haircut
        - annualized_cost_drag
    )


def _age_seconds(value: datetime | None, now: datetime) -> int | None:
    if value is None or value.tzinfo is None:
        return None
    delta = now - value.astimezone(UTC)
    if delta.total_seconds() < 0:
        return None
    return int(delta.total_seconds())


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("optimizer time must be timezone-aware")
    return value.astimezone(UTC)


def _ceil_div(value: Decimal, step: Decimal) -> int:
    quotient = value // step
    return int(quotient if value % step == 0 else quotient + 1)


def _add(target: dict[str, Decimal] | dict[RatingTier, Decimal], key: str, value: Decimal) -> None:
    target[key] = target.get(key, Decimal(0)) + value  # type: ignore[index]


def _validate_state(state: PortfolioExposureState) -> None:
    if state.nav_rub <= 0:
        raise ValueError("portfolio NAV must be positive")
    if state.available_cash_rub < 0:
        raise ValueError("available cash must not be negative")
    for mapping in (
        state.instrument_rub,
        state.issuer_rub,
        state.group_rub,
        state.sector_rub,
        state.asset_class_rub,
        state.rating_rub,
    ):
        if any(value < 0 for value in mapping.values()):
            raise ValueError("portfolio exposures must not be negative")


def _validate_policy(policy: OptimizationPolicy) -> None:
    if policy.horizon_months <= 0:
        raise ValueError("optimizer horizon must be positive")
    if policy.max_duration_years <= 0:
        raise ValueError("maximum duration must be positive")
    if policy.reserve_rub < 0 or policy.planned_withdrawal_rub < 0:
        raise ValueError("cash reservations must not be negative")
    if policy.min_trade_rub < 0:
        raise ValueError("minimum trade must not be negative")
    if policy.max_quote_age_seconds <= 0 or policy.max_evidence_age_seconds <= 0:
        raise ValueError("freshness limits must be positive")

    percentages = (
        policy.max_instrument_percent,
        policy.max_issuer_percent,
        policy.max_group_percent,
        policy.max_sector_percent,
        policy.max_asset_class_percent,
        policy.max_turnover_percent,
        policy.no_trade_band_percent,
    )
    if any(value < 0 or value > 100 for value in percentages):
        raise ValueError("optimizer percentage limits must be between 0 and 100")

    for mapping in (policy.rating_max_percent, policy.rating_haircut_percent):
        if "unknown" in mapping and mapping["unknown"] != 0:
            raise ValueError("unknown rating cannot receive a positive risk budget")
        if any(value < 0 or value > 100 for value in mapping.values()):
            raise ValueError("rating policy values must be between 0 and 100")
