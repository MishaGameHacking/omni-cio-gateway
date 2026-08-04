from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timezone
from decimal import Decimal

from omni_cio.contracts.v1.investment_policy import (
    InvestmentPolicyAssessmentV1,
    InvestmentPolicyStatementV1,
)
from omni_cio.contracts.v1.portfolio_risk import (
    ConcentrationRowV1,
    ConcentrationSummaryV1,
    LiquidityPositionResultV1,
    MacroRiskAssumptionsV1,
    PermanentLossStatus,
    PortfolioRiskAssessmentV1,
    PortfolioRiskInputV1,
    PortfolioRiskStateV1,
    ProposedTradeRiskEffectV1,
    RiskBlockerCode,
    RiskEngineSettingsV1,
    RiskExposureDimension,
    RiskLimitSource,
    RiskLimitV1,
    RiskPositionV1,
    RiskSeverity,
    RiskVectorKind,
    RiskVectorV1,
    StressScenarioDefinitionV1,
    StressScenarioResultV1,
    portfolio_risk_sha256,
)
from omni_cio.policy import policy_fingerprint_sha256


class PortfolioRiskError(ValueError):
    """Risk inputs cannot be assessed safely or deterministically."""


DEFAULT_STRESS_SCENARIOS = (
    StressScenarioDefinitionV1(
        scenario_id="stress_market_10",
        name="Broad invested assets -10%",
        dimension=RiskExposureDimension.POSITION,
        default_shock=Decimal("-0.10"),
    ),
    StressScenarioDefinitionV1(
        scenario_id="stress_market_20",
        name="Broad invested assets -20%",
        dimension=RiskExposureDimension.POSITION,
        default_shock=Decimal("-0.20"),
    ),
    StressScenarioDefinitionV1(
        scenario_id="stress_market_30",
        name="Broad invested assets -30%",
        dimension=RiskExposureDimension.POSITION,
        default_shock=Decimal("-0.30"),
    ),
)


_LIMIT_BLOCKERS = {
    RiskExposureDimension.POSITION: RiskBlockerCode.POSITION_LIMIT_BREACH,
    RiskExposureDimension.ISSUER: RiskBlockerCode.ISSUER_LIMIT_BREACH,
    RiskExposureDimension.GROUP: RiskBlockerCode.GROUP_LIMIT_BREACH,
    RiskExposureDimension.SECTOR: RiskBlockerCode.SECTOR_LIMIT_BREACH,
    RiskExposureDimension.ASSET_CLASS: RiskBlockerCode.ASSET_CLASS_LIMIT_BREACH,
    RiskExposureDimension.CURRENCY: RiskBlockerCode.CURRENCY_LIMIT_BREACH,
}


_READINESS_BLOCKERS = {
    RiskBlockerCode.IPS_NOT_READY,
    RiskBlockerCode.POLICY_BINDING_MISMATCH,
    RiskBlockerCode.FX_EVIDENCE_STALE,
    RiskBlockerCode.EXPOSURE_INCOMPLETE,
    RiskBlockerCode.FUND_XRAY_REQUIRED,
    RiskBlockerCode.FUND_XRAY_NOT_READY,
    RiskBlockerCode.CREDIT_EVIDENCE_REQUIRED,
    RiskBlockerCode.CREDIT_NOT_READY,
    RiskBlockerCode.PERMANENT_LOSS_UNKNOWN,
    RiskBlockerCode.LIQUIDITY_EVIDENCE_MISSING,
    RiskBlockerCode.LIQUIDITY_EVIDENCE_STALE,
    RiskBlockerCode.TRADE_BINDING_MISMATCH,
}


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise PortfolioRiskError("RISK_TIMESTAMP_MUST_BE_AWARE")
    return result.astimezone(timezone.utc)


def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator <= 0:
        raise PortfolioRiskError("PORTFOLIO_VALUE_NON_POSITIVE")
    return numerator / denominator


def _decimal_text(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == 0:
        return "0"
    return format(normalized, "f")


def _append_unique[T](target: list[T], value: T) -> None:
    if value not in target:
        target.append(value)


def _validate_scenarios(
    scenarios: Iterable[StressScenarioDefinitionV1],
) -> tuple[StressScenarioDefinitionV1, ...]:
    result = tuple(sorted(scenarios, key=lambda row: row.scenario_id))
    if not result:
        raise PortfolioRiskError("STRESS_SCENARIOS_REQUIRED")
    ids = [row.scenario_id for row in result]
    if len(ids) != len(set(ids)):
        raise PortfolioRiskError("STRESS_SCENARIO_IDS_MUST_BE_UNIQUE")
    return result


def _policy_limits(
    policy: InvestmentPolicyStatementV1,
    settings: RiskEngineSettingsV1,
) -> dict[RiskExposureDimension, RiskLimitV1]:
    candidates: list[RiskLimitV1] = []
    for dimension, value in (
        (RiskExposureDimension.POSITION, policy.max_position_weight),
        (RiskExposureDimension.GROUP, policy.max_group_weight),
        (RiskExposureDimension.SECTOR, policy.max_sector_weight),
        (RiskExposureDimension.CURRENCY, policy.max_currency_weight),
    ):
        if value is not None:
            candidates.append(
                RiskLimitV1(
                    dimension=dimension,
                    max_weight=value,
                    source=RiskLimitSource.IPS,
                    hard=True,
                    owner_confirmed=True,
                )
            )
    candidates.extend(settings.additional_limits)

    selected: dict[RiskExposureDimension, RiskLimitV1] = {}
    for limit in candidates:
        current = selected.get(limit.dimension)
        if current is None:
            selected[limit.dimension] = limit
            continue
        if limit.max_weight < current.max_weight:
            selected[limit.dimension] = limit
        elif limit.max_weight == current.max_weight and limit.hard and not current.hard:
            selected[limit.dimension] = limit
    return selected


def _dimension_weights(
    portfolio: PortfolioRiskInputV1,
) -> tuple[
    dict[str, Decimal],
    dict[tuple[RiskExposureDimension, str], Decimal],
]:
    total = portfolio.total_value_base
    if total <= 0:
        raise PortfolioRiskError("PORTFOLIO_VALUE_NON_POSITIVE")
    position_weights: dict[str, Decimal] = {}
    exposure_weights: dict[tuple[RiskExposureDimension, str], Decimal] = defaultdict(
        Decimal
    )
    for position in portfolio.positions:
        position_weight = _ratio(position.base_market_value, total)
        position_weights[position.stable_key] = position_weight
        exposure_weights[
            (RiskExposureDimension.POSITION, position.stable_key)
        ] += position_weight
        for exposure in position.exposures:
            exposure_weights[(exposure.dimension, exposure.bucket_key)] += (
                position_weight * exposure.weight_within_position
            )
    return position_weights, exposure_weights


def _missing_hard_limit_exposure(
    position: RiskPositionV1,
    limits: dict[RiskExposureDimension, RiskLimitV1],
) -> bool:
    supplied = {row.dimension for row in position.exposures}
    required = {
        dimension
        for dimension, limit in limits.items()
        if dimension is not RiskExposureDimension.POSITION and limit.hard
    }
    return not required.issubset(supplied)


def _concentration(
    portfolio: PortfolioRiskInputV1,
    limits: dict[RiskExposureDimension, RiskLimitV1],
    blockers: list[RiskBlockerCode],
) -> ConcentrationSummaryV1:
    position_weights, exposure_weights = _dimension_weights(portfolio)
    ranked = sorted(position_weights.values(), reverse=True)

    rows: list[ConcentrationRowV1] = []
    for (dimension, bucket_key), weight in sorted(
        exposure_weights.items(),
        key=lambda item: (item[0][0].value, item[0][1]),
    ):
        limit = limits.get(dimension)
        breached = limit is not None and weight > limit.max_weight
        row = ConcentrationRowV1(
            dimension=dimension,
            bucket_key=bucket_key,
            weight=weight,
            applicable_limit=limit.max_weight if limit is not None else None,
            limit_source=limit.source if limit is not None else None,
            hard_limit=limit.hard if limit is not None else False,
            breached=breached,
        )
        rows.append(row)
        if breached and limit is not None and limit.hard:
            _append_unique(blockers, _LIMIT_BLOCKERS[dimension])

    return ConcentrationSummaryV1(
        top_1_weight=sum(ranked[:1], Decimal("0")),
        top_3_weight=sum(ranked[:3], Decimal("0")),
        top_5_weight=sum(ranked[:5], Decimal("0")),
        rows=tuple(rows),
    )


def _liquidity_results(
    portfolio: PortfolioRiskInputV1,
    *,
    assessed_at: datetime,
    settings: RiskEngineSettingsV1,
    blockers: list[RiskBlockerCode],
) -> tuple[LiquidityPositionResultV1, ...]:
    total = portfolio.total_value_base
    rows: list[LiquidityPositionResultV1] = []
    for position in portfolio.positions:
        position_weight = _ratio(position.base_market_value, total)
        source = position.liquidity
        if source is None:
            if position.base_market_value > 0:
                _append_unique(blockers, RiskBlockerCode.LIQUIDITY_EVIDENCE_MISSING)
            rows.append(
                LiquidityPositionResultV1(
                    stable_key=position.stable_key,
                    position_weight=position_weight,
                    unknown=position.base_market_value > 0,
                )
            )
            continue

        age = (assessed_at - source.as_of).total_seconds()
        stale = (
            age > settings.liquidity_max_age_seconds
            or age < -settings.future_tolerance_seconds
        )
        if stale and position.base_market_value > 0:
            _append_unique(blockers, RiskBlockerCode.LIQUIDITY_EVIDENCE_STALE)

        exit_days = None
        unknown = False
        if position.base_market_value > 0:
            if (
                source.daily_exit_capacity_base is None
                or source.daily_exit_capacity_base <= 0
            ):
                unknown = True
                _append_unique(blockers, RiskBlockerCode.LIQUIDITY_EVIDENCE_MISSING)
            else:
                exit_days = position.base_market_value / source.daily_exit_capacity_base

        rows.append(
            LiquidityPositionResultV1(
                stable_key=position.stable_key,
                position_weight=position_weight,
                exit_days=exit_days,
                spread_bps=source.spread_bps,
                stale=stale,
                unknown=unknown,
            )
        )
    return tuple(sorted(rows, key=lambda row: row.stable_key))


def _scenario_position_shock(
    position: RiskPositionV1,
    scenario: StressScenarioDefinitionV1,
) -> Decimal:
    if scenario.dimension is RiskExposureDimension.POSITION:
        return scenario.default_shock
    overrides = {row.bucket_key: row.shock for row in scenario.bucket_shocks}
    slices = [
        row for row in position.exposures if row.dimension is scenario.dimension
    ]
    if not slices:
        return scenario.default_shock
    return sum(
        (
            row.weight_within_position
            * overrides.get(row.bucket_key, scenario.default_shock)
            for row in slices
        ),
        Decimal("0"),
    )


def _stress_results(
    portfolio: PortfolioRiskInputV1,
    *,
    policy: InvestmentPolicyStatementV1,
    scenarios: tuple[StressScenarioDefinitionV1, ...],
    blockers: list[RiskBlockerCode],
) -> tuple[StressScenarioResultV1, ...]:
    total = portfolio.total_value_base
    rows: list[StressScenarioResultV1] = []
    for scenario in scenarios:
        change = sum(
            (
                position.base_market_value
                * _scenario_position_shock(position, scenario)
                for position in portfolio.positions
            ),
            Decimal("0"),
        )
        change_weight = change / total
        drawdown_breach = (
            policy.max_drawdown is not None
            and abs(change_weight) > policy.max_drawdown
        )
        if drawdown_breach:
            _append_unique(blockers, RiskBlockerCode.MAX_DRAWDOWN_BREACH)
        rows.append(
            StressScenarioResultV1(
                scenario_id=scenario.scenario_id,
                portfolio_change_base=change,
                portfolio_change_weight=change_weight,
                max_drawdown_limit=policy.max_drawdown,
                drawdown_breach=drawdown_breach,
            )
        )
    return tuple(rows)


def _severity_from_ratio(
    value: Decimal,
    *,
    moderate: Decimal,
    high: Decimal,
) -> RiskSeverity:
    if value >= high:
        return RiskSeverity.HIGH
    if value >= moderate:
        return RiskSeverity.MODERATE
    return RiskSeverity.LOW


def _vectors(
    portfolio: PortfolioRiskInputV1,
    *,
    policy: InvestmentPolicyStatementV1,
    concentration: ConcentrationSummaryV1,
    liquidity: tuple[LiquidityPositionResultV1, ...],
    stress: tuple[StressScenarioResultV1, ...],
    blockers: tuple[RiskBlockerCode, ...],
    macro: MacroRiskAssumptionsV1,
    settings: RiskEngineSettingsV1,
) -> tuple[RiskVectorV1, ...]:
    total = portfolio.total_value_base
    cash_weight = _ratio(portfolio.cash_base, total)

    permanent_block = RiskBlockerCode.PERMANENT_LOSS_BLOCK in blockers
    permanent_unknown = RiskBlockerCode.PERMANENT_LOSS_UNKNOWN in blockers
    permanent_watch = any(
        row.permanent_loss.status is PermanentLossStatus.WATCH
        for row in portfolio.positions
    )
    if permanent_block:
        permanent_severity = RiskSeverity.BREACH
    elif permanent_unknown:
        permanent_severity = RiskSeverity.UNKNOWN
    elif permanent_watch:
        permanent_severity = RiskSeverity.MODERATE
    else:
        permanent_severity = RiskSeverity.LOW

    worst_stress = max(
        (abs(row.portfolio_change_weight) for row in stress),
        default=Decimal("0"),
    )
    drawdown_breach = any(row.drawdown_breach for row in stress)
    max_drawdown = policy.max_drawdown
    if drawdown_breach:
        market_severity = RiskSeverity.BREACH
    elif max_drawdown is not None and max_drawdown > 0:
        market_severity = _severity_from_ratio(
            worst_stress / max_drawdown,
            moderate=Decimal("0.50"),
            high=Decimal("0.75"),
        )
    else:
        market_severity = RiskSeverity.UNKNOWN

    hard_concentration = any(
        row.breached and row.hard_limit for row in concentration.rows
    )
    soft_concentration = any(
        row.breached and not row.hard_limit for row in concentration.rows
    )
    if hard_concentration:
        concentration_severity = RiskSeverity.BREACH
    elif soft_concentration:
        concentration_severity = RiskSeverity.HIGH
    else:
        concentration_severity = RiskSeverity.LOW

    reserve_breach = RiskBlockerCode.LIQUIDITY_RESERVE_BREACH in blockers
    liquidity_unknown = any(row.unknown or row.stale for row in liquidity)
    exit_high = any(
        row.exit_days is not None and row.exit_days > settings.max_exit_days_soft
        for row in liquidity
    )
    spread_high = any(
        row.spread_bps is not None
        and row.spread_bps > settings.max_spread_bps_soft
        for row in liquidity
    )
    if reserve_breach:
        liquidity_severity = RiskSeverity.BREACH
    elif liquidity_unknown:
        liquidity_severity = RiskSeverity.UNKNOWN
    elif exit_high or spread_high:
        liquidity_severity = RiskSeverity.HIGH
    else:
        liquidity_severity = RiskSeverity.LOW

    credit_breach_codes = {
        RiskBlockerCode.ACTIVE_DEFAULT,
        RiskBlockerCode.CREDIT_FLOOR_BREACH,
    }
    credit_unknown_codes = {
        RiskBlockerCode.CREDIT_EVIDENCE_REQUIRED,
        RiskBlockerCode.CREDIT_NOT_READY,
    }
    if any(code in blockers for code in credit_breach_codes):
        credit_severity = RiskSeverity.BREACH
    elif any(code in blockers for code in credit_unknown_codes):
        credit_severity = RiskSeverity.UNKNOWN
    else:
        credit_severity = RiskSeverity.LOW

    currency_breach = RiskBlockerCode.CURRENCY_LIMIT_BREACH in blockers
    currency_rows = [
        row
        for row in concentration.rows
        if row.dimension is RiskExposureDimension.CURRENCY
    ]
    currency_soft = any(row.breached for row in currency_rows)
    if currency_breach:
        currency_severity = RiskSeverity.BREACH
    elif currency_soft:
        currency_severity = RiskSeverity.HIGH
    elif not currency_rows:
        currency_severity = RiskSeverity.UNKNOWN
    else:
        currency_severity = RiskSeverity.LOW

    inflation_rate = macro.annual_inflation_rate
    opportunity_rate = macro.annual_cash_opportunity_rate
    if inflation_rate is None or opportunity_rate is None:
        macro_unknown = True
        macro_severity = RiskSeverity.UNKNOWN
        macro_drag = None
    else:
        macro_unknown = False
        macro_drag = cash_weight * max(inflation_rate, opportunity_rate)
        macro_severity = _severity_from_ratio(
            macro_drag,
            moderate=Decimal("0.02"),
            high=Decimal("0.05"),
        )

    data_unknown_codes = {
        RiskBlockerCode.FX_EVIDENCE_STALE,
        RiskBlockerCode.EXPOSURE_INCOMPLETE,
        RiskBlockerCode.FUND_XRAY_REQUIRED,
        RiskBlockerCode.FUND_XRAY_NOT_READY,
        RiskBlockerCode.CREDIT_EVIDENCE_REQUIRED,
        RiskBlockerCode.CREDIT_NOT_READY,
        RiskBlockerCode.PERMANENT_LOSS_UNKNOWN,
        RiskBlockerCode.LIQUIDITY_EVIDENCE_MISSING,
        RiskBlockerCode.LIQUIDITY_EVIDENCE_STALE,
        RiskBlockerCode.IPS_NOT_READY,
        RiskBlockerCode.POLICY_BINDING_MISMATCH,
        RiskBlockerCode.TRADE_BINDING_MISMATCH,
    }
    data_unknown = bool(portfolio.data_quality_codes) or any(
        code in blockers for code in data_unknown_codes
    )

    fund_credit_positions = sum(
        row.instrument_type.value == "etf" and row.fund_credit is not None
        for row in portfolio.positions
    )
    return (
        RiskVectorV1(
            kind=RiskVectorKind.PERMANENT_LOSS,
            severity=permanent_severity,
            hard_breach=permanent_block,
            metrics=(
                "watch_positions="
                f"{sum(row.permanent_loss.status is PermanentLossStatus.WATCH for row in portfolio.positions)}",
            ),
            evidence_codes=(
                ("PERMANENT_LOSS_UNKNOWN",) if permanent_unknown else ()
            ),
        ),
        RiskVectorV1(
            kind=RiskVectorKind.MARKET,
            severity=market_severity,
            hard_breach=drawdown_breach,
            metrics=(f"worst_stress_weight={_decimal_text(worst_stress)}",),
            evidence_codes=(
                ("MAX_DRAWDOWN_BREACH",) if drawdown_breach else ()
            ),
        ),
        RiskVectorV1(
            kind=RiskVectorKind.CONCENTRATION,
            severity=concentration_severity,
            hard_breach=hard_concentration,
            metrics=(
                f"top1={_decimal_text(concentration.top_1_weight)}",
                f"top3={_decimal_text(concentration.top_3_weight)}",
                f"top5={_decimal_text(concentration.top_5_weight)}",
            ),
            evidence_codes=tuple(
                code.value.upper()
                for code in blockers
                if code in set(_LIMIT_BLOCKERS.values())
            ),
        ),
        RiskVectorV1(
            kind=RiskVectorKind.LIQUIDITY,
            severity=liquidity_severity,
            hard_breach=reserve_breach,
            metrics=(f"cash_weight={_decimal_text(cash_weight)}",),
            evidence_codes=tuple(
                code.value.upper()
                for code in blockers
                if code
                in {
                    RiskBlockerCode.LIQUIDITY_RESERVE_BREACH,
                    RiskBlockerCode.LIQUIDITY_EVIDENCE_MISSING,
                    RiskBlockerCode.LIQUIDITY_EVIDENCE_STALE,
                }
            ),
        ),
        RiskVectorV1(
            kind=RiskVectorKind.CREDIT,
            severity=credit_severity,
            hard_breach=any(code in blockers for code in credit_breach_codes),
            metrics=(
                "bond_positions="
                f"{sum(row.instrument_type.value == 'bond' for row in portfolio.positions)}",
                f"fund_credit_positions={fund_credit_positions}",
            ),
            evidence_codes=tuple(
                code.value.upper()
                for code in blockers
                if code in credit_breach_codes | credit_unknown_codes
            ),
        ),
        RiskVectorV1(
            kind=RiskVectorKind.CURRENCY,
            severity=currency_severity,
            hard_breach=currency_breach,
            metrics=(f"currency_buckets={len(currency_rows)}",),
            evidence_codes=(
                ("CURRENCY_LIMIT_BREACH",) if currency_breach else ()
            ),
        ),
        RiskVectorV1(
            kind=RiskVectorKind.INFLATION_OPPORTUNITY,
            severity=macro_severity,
            hard_breach=False,
            metrics=(
                (
                    "macro_assumptions=missing"
                    if macro_drag is None
                    else f"annual_cash_drag_weight={_decimal_text(macro_drag)}"
                ),
            ),
            evidence_codes=(
                ("MACRO_ASSUMPTIONS_MISSING",) if macro_unknown else ()
            ),
        ),
        RiskVectorV1(
            kind=RiskVectorKind.DATA_QUALITY,
            severity=RiskSeverity.UNKNOWN if data_unknown else RiskSeverity.LOW,
            hard_breach=False,
            metrics=(f"input_quality_codes={len(portfolio.data_quality_codes)}",),
            evidence_codes=tuple(
                sorted(
                    {
                        *portfolio.data_quality_codes,
                        *(
                            code.value.upper()
                            for code in blockers
                            if code in data_unknown_codes
                        ),
                    }
                )
            ),
        ),
    )


def _assess_state(
    portfolio: PortfolioRiskInputV1,
    *,
    policy: InvestmentPolicyStatementV1,
    settings: RiskEngineSettingsV1,
    scenarios: tuple[StressScenarioDefinitionV1, ...],
    macro: MacroRiskAssumptionsV1,
    assessed_at: datetime,
    inherited_blockers: tuple[RiskBlockerCode, ...] = (),
) -> PortfolioRiskStateV1:
    if portfolio.base_currency != policy.base_currency:
        raise PortfolioRiskError("RISK_BASE_CURRENCY_MUST_MATCH_IPS")
    total = portfolio.total_value_base
    if total <= 0:
        raise PortfolioRiskError("PORTFOLIO_VALUE_NON_POSITIVE")

    blockers = list(inherited_blockers)
    limits = _policy_limits(policy, settings)

    for position in portfolio.positions:
        if position.fx is not None:
            fx_age = (assessed_at - position.fx.as_of).total_seconds()
            if (
                fx_age > settings.fx_max_age_seconds
                or fx_age < -settings.future_tolerance_seconds
            ):
                _append_unique(blockers, RiskBlockerCode.FX_EVIDENCE_STALE)

        if _missing_hard_limit_exposure(position, limits):
            _append_unique(blockers, RiskBlockerCode.EXPOSURE_INCOMPLETE)
        if position.exposure_mode.value == "fund_lookthrough":
            if position.fund_xray_sha256 is None:
                _append_unique(blockers, RiskBlockerCode.FUND_XRAY_REQUIRED)
            elif not position.fund_xray_decision_ready:
                _append_unique(blockers, RiskBlockerCode.FUND_XRAY_NOT_READY)

            fund_credit = position.fund_credit
            if fund_credit is None:
                _append_unique(blockers, RiskBlockerCode.CREDIT_EVIDENCE_REQUIRED)
            else:
                if fund_credit.unknown_weight > 0:
                    _append_unique(blockers, RiskBlockerCode.CREDIT_NOT_READY)
                if fund_credit.active_default_weight > 0:
                    _append_unique(blockers, RiskBlockerCode.ACTIVE_DEFAULT)
                if fund_credit.floor_breach_weight > 0:
                    _append_unique(blockers, RiskBlockerCode.CREDIT_FLOOR_BREACH)

        if position.instrument_type.value == "bond":
            credit = position.credit
            if credit is None:
                _append_unique(blockers, RiskBlockerCode.CREDIT_EVIDENCE_REQUIRED)
            else:
                if not credit.decision_ready:
                    _append_unique(blockers, RiskBlockerCode.CREDIT_NOT_READY)
                if credit.active_default_event:
                    _append_unique(blockers, RiskBlockerCode.ACTIVE_DEFAULT)
                if not credit.policy_floor_passed:
                    _append_unique(blockers, RiskBlockerCode.CREDIT_FLOOR_BREACH)

        if position.permanent_loss.status is PermanentLossStatus.BLOCK:
            _append_unique(blockers, RiskBlockerCode.PERMANENT_LOSS_BLOCK)
        elif position.permanent_loss.status is PermanentLossStatus.UNKNOWN:
            _append_unique(blockers, RiskBlockerCode.PERMANENT_LOSS_UNKNOWN)

    if (
        policy.liquidity_reserve is not None
        and portfolio.cash_base < policy.liquidity_reserve.amount
    ):
        _append_unique(blockers, RiskBlockerCode.LIQUIDITY_RESERVE_BREACH)

    concentration = _concentration(portfolio, limits, blockers)
    liquidity = _liquidity_results(
        portfolio,
        assessed_at=assessed_at,
        settings=settings,
        blockers=blockers,
    )
    stress = _stress_results(
        portfolio,
        policy=policy,
        scenarios=scenarios,
        blockers=blockers,
    )
    canonical_blockers = tuple(sorted(set(blockers), key=str))
    vectors = _vectors(
        portfolio,
        policy=policy,
        concentration=concentration,
        liquidity=liquidity,
        stress=stress,
        blockers=canonical_blockers,
        macro=macro,
        settings=settings,
    )
    hard_breach = any(row.hard_breach for row in vectors)
    return PortfolioRiskStateV1(
        total_value_base=total,
        cash_base=portfolio.cash_base,
        cash_weight=_ratio(portfolio.cash_base, total),
        concentration=concentration,
        liquidity=liquidity,
        stress=stress,
        vectors=vectors,
        blockers=canonical_blockers,
        policy_compliant=not hard_breach,
    )


def _apply_proposed_trades(
    before: PortfolioRiskInputV1,
    effects: tuple[ProposedTradeRiskEffectV1, ...],
) -> PortfolioRiskInputV1:
    if not effects:
        return before

    trade_ids = [row.trade_id for row in effects]
    stable_keys = [row.stable_key for row in effects]
    if len(trade_ids) != len(set(trade_ids)):
        raise PortfolioRiskError("PROPOSED_TRADE_IDS_MUST_BE_UNIQUE")
    if len(stable_keys) != len(set(stable_keys)):
        raise PortfolioRiskError("ONE_RISK_EFFECT_PER_POSITION_REQUIRED")

    positions = {row.stable_key: row for row in before.positions}
    cash_after = before.cash_base
    for effect in sorted(effects, key=lambda row: row.trade_id):
        current = positions.get(effect.stable_key)
        current_value = (
            current.base_market_value if current is not None else Decimal("0")
        )
        if current_value != effect.expected_before_value_base:
            raise PortfolioRiskError("TRADE_BINDING_MISMATCH")
        cash_after += effect.cash_delta_base
        if effect.after_position is None:
            if current is None:
                raise PortfolioRiskError("TRADE_BINDING_MISMATCH")
            positions.pop(effect.stable_key)
        else:
            if effect.after_position.base_currency != before.base_currency:
                raise PortfolioRiskError("TRADE_BASE_CURRENCY_MISMATCH")
            positions[effect.stable_key] = effect.after_position

    if cash_after < 0:
        raise PortfolioRiskError("NEGATIVE_AFTER_CASH")
    return PortfolioRiskInputV1(
        portfolio_snapshot_sha256=before.portfolio_snapshot_sha256,
        policy_reference=before.policy_reference,
        base_currency=before.base_currency,
        cash_base=cash_after,
        positions=tuple(positions.values()),
        data_quality_codes=before.data_quality_codes,
    )


def assess_portfolio_risk(
    *,
    portfolio: PortfolioRiskInputV1,
    policy: InvestmentPolicyStatementV1,
    policy_assessment: InvestmentPolicyAssessmentV1,
    proposed_trades: Iterable[ProposedTradeRiskEffectV1] = (),
    settings: RiskEngineSettingsV1 | None = None,
    stress_scenarios: Iterable[
        StressScenarioDefinitionV1
    ] = DEFAULT_STRESS_SCENARIOS,
    macro: MacroRiskAssumptionsV1 | None = None,
    assessed_at: datetime | None = None,
) -> PortfolioRiskAssessmentV1:
    """Assess current and hypothetical after-trade risk without broker mutation."""
    evaluation_time = _aware_utc(assessed_at)
    settings_value = settings or RiskEngineSettingsV1()
    scenario_values = _validate_scenarios(stress_scenarios)
    macro_value = macro or MacroRiskAssumptionsV1()
    effects = tuple(proposed_trades)

    inherited: list[RiskBlockerCode] = []
    if not policy_assessment.ready_for_personal_sizing:
        inherited.append(RiskBlockerCode.IPS_NOT_READY)
    if (
        portfolio.policy_reference != policy_assessment.reference
        or portfolio.policy_reference.policy_id != policy.policy_id
        or portfolio.policy_reference.version != policy.version
        or portfolio.policy_reference.fingerprint_sha256
        != policy_fingerprint_sha256(policy)
    ):
        inherited.append(RiskBlockerCode.POLICY_BINDING_MISMATCH)

    before = _assess_state(
        portfolio,
        policy=policy,
        settings=settings_value,
        scenarios=scenario_values,
        macro=macro_value,
        assessed_at=evaluation_time,
        inherited_blockers=tuple(inherited),
    )

    try:
        after_input = _apply_proposed_trades(portfolio, effects)
    except PortfolioRiskError as exc:
        if str(exc) == "TRADE_BINDING_MISMATCH":
            inherited_after = tuple(
                sorted(
                    {
                        *inherited,
                        RiskBlockerCode.TRADE_BINDING_MISMATCH,
                    },
                    key=str,
                )
            )
            after_input = portfolio
        else:
            raise
    else:
        inherited_after = tuple(inherited)

    after = _assess_state(
        after_input,
        policy=policy,
        settings=settings_value,
        scenarios=scenario_values,
        macro=macro_value,
        assessed_at=evaluation_time,
        inherited_blockers=inherited_after,
    )

    before_blockers = set(before.blockers)
    after_blockers = set(after.blockers)
    new_blockers = tuple(sorted(after_blockers - before_blockers, key=str))
    resolved_blockers = tuple(sorted(before_blockers - after_blockers, key=str))
    readiness_blocked = any(
        code in _READINESS_BLOCKERS
        for code in before_blockers | after_blockers
    )
    decision_ready = not readiness_blocked and not portfolio.data_quality_codes
    values = {
        "schema_version": "1.0",
        "assessed_at": evaluation_time,
        "portfolio_snapshot_sha256": portfolio.portfolio_snapshot_sha256,
        "policy_reference": portfolio.policy_reference,
        "before": before,
        "after": after,
        "proposed_trade_ids": tuple(sorted({row.trade_id for row in effects})),
        "new_blockers": new_blockers,
        "resolved_blockers": resolved_blockers,
        "decision_ready": decision_ready,
        "plan_eligible": decision_ready and after.policy_compliant,
        "assessment_sha256": "0" * 64,
        "trading_methods": False,
    }
    provisional = PortfolioRiskAssessmentV1.model_construct(**values)
    values["assessment_sha256"] = portfolio_risk_sha256(provisional)
    return PortfolioRiskAssessmentV1.model_validate(values)
