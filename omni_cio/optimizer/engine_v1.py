from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal
import hashlib
import re
from typing import TypeVar

from omni_cio.contracts.v1.investment_policy import (
    InvestmentPolicyAssessmentV1,
    InvestmentPolicyStatementV1,
)
from omni_cio.contracts.v1.meta_strategy import (
    MetaStrategySelectionV1,
    StrategyComponentDirective,
    StrategyComponentKind,
    StrategyRegime,
)
from omni_cio.contracts.v1.portfolio_optimizer import (
    OptimizerAssetV1,
    OptimizerBlockerCode,
    OptimizerRebalanceLegV1,
    OptimizerScenarioKind,
    OptimizerScenarioV1,
    OptimizerTargetPositionV1,
    OptimizerTradeSide,
    OptimizerWarningCode,
    PortfolioOptimizerResultV1,
    PortfolioOptimizerSettingsV1,
    portfolio_optimizer_sha256,
)
from omni_cio.contracts.v1.portfolio_risk import (
    MacroRiskAssumptionsV1,
    PortfolioRiskAssessmentV1,
    PortfolioRiskInputV1,
    ProposedTradeRiskEffectV1,
    RiskEngineSettingsV1,
    RiskPositionV1,
    StressScenarioDefinitionV1,
)
from omni_cio.policy import policy_fingerprint_sha256
from omni_cio.risk.engine_v1 import DEFAULT_STRESS_SCENARIOS, assess_portfolio_risk


class PortfolioOptimizerError(ValueError):
    """Optimizer inputs are structurally ambiguous or non-deterministic."""


_T = TypeVar("_T")

_REGIME_COMPONENT_WEIGHTS: dict[
    StrategyRegime,
    dict[StrategyComponentKind, Decimal],
] = {
    StrategyRegime.CAPITAL_PRESERVATION: {
        StrategyComponentKind.LIQUIDITY_RESERVE: Decimal("0.25"),
        StrategyComponentKind.QUALITY_DEBT: Decimal("0.60"),
        StrategyComponentKind.DIVERSIFIED_CORE: Decimal("0.15"),
        StrategyComponentKind.BOUNDED_ACTIVE: Decimal("0"),
    },
    StrategyRegime.DEFENSIVE_BALANCED: {
        StrategyComponentKind.LIQUIDITY_RESERVE: Decimal("0.20"),
        StrategyComponentKind.QUALITY_DEBT: Decimal("0.45"),
        StrategyComponentKind.DIVERSIFIED_CORE: Decimal("0.35"),
        StrategyComponentKind.BOUNDED_ACTIVE: Decimal("0"),
    },
    StrategyRegime.BALANCED_CORE: {
        StrategyComponentKind.LIQUIDITY_RESERVE: Decimal("0.15"),
        StrategyComponentKind.QUALITY_DEBT: Decimal("0.30"),
        StrategyComponentKind.DIVERSIFIED_CORE: Decimal("0.55"),
        StrategyComponentKind.BOUNDED_ACTIVE: Decimal("0"),
    },
    StrategyRegime.GROWTH_CORE: {
        StrategyComponentKind.LIQUIDITY_RESERVE: Decimal("0.10"),
        StrategyComponentKind.QUALITY_DEBT: Decimal("0.20"),
        StrategyComponentKind.DIVERSIFIED_CORE: Decimal("0.60"),
        StrategyComponentKind.BOUNDED_ACTIVE: Decimal("0.10"),
    },
}

_REDUCE_BUY_PRIORITY = {
    StrategyComponentKind.BOUNDED_ACTIVE: 0,
    StrategyComponentKind.DIVERSIFIED_CORE: 1,
    StrategyComponentKind.QUALITY_DEBT: 2,
}


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise PortfolioOptimizerError("OPTIMIZER_TIMESTAMP_MUST_BE_AWARE")
    return result.astimezone(timezone.utc)


def _append_unique(target: list[_T], value: _T) -> None:
    if value not in target:
        target.append(value)


def _money(value: Decimal, quantum: Decimal) -> Decimal:
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def _weight(value: Decimal, quantum: Decimal) -> Decimal:
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def _ceil_ratio(numerator: Decimal, denominator: Decimal) -> int:
    return int((numerator / denominator).to_integral_value(rounding=ROUND_CEILING))


def _floor_ratio(numerator: Decimal, denominator: Decimal) -> int:
    if numerator <= 0:
        return 0
    return int((numerator / denominator).to_integral_value(rounding=ROUND_FLOOR))


def _trade_id(stable_key: str) -> str:
    slug = re.sub(r"[^a-z0-9_-]+", "_", stable_key.lower()).strip("_")
    slug = slug[:32] or "asset"
    digest = hashlib.sha256(stable_key.encode("utf-8")).hexdigest()[:8]
    return f"trade_opt_{slug}_{digest}"


def _canonical_scenarios(
    *rows: OptimizerScenarioV1,
) -> tuple[OptimizerScenarioV1, ...]:
    return tuple(sorted(rows, key=lambda row: row.kind.value))


def _current_scenario(
    risk: PortfolioRiskAssessmentV1,
    portfolio: PortfolioRiskInputV1,
    *,
    kind: OptimizerScenarioKind,
) -> OptimizerScenarioV1:
    state = risk.after
    return OptimizerScenarioV1(
        kind=kind,
        portfolio_value_base=state.total_value_base,
        cash_base=state.cash_base,
        securities_value_base=state.total_value_base - state.cash_base,
        position_count=sum(1 for row in portfolio.positions if row.base_market_value > 0),
        turnover_base=Decimal("0"),
        commission_base=Decimal("0"),
        estimated_tax_base=Decimal("0"),
        policy_compliant=state.policy_compliant,
        risk_assessment_sha256=risk.assessment_sha256,
        risk_blockers=state.blockers,
    )


def _blocked_result(
    *,
    optimized_at: datetime,
    portfolio: PortfolioRiskInputV1,
    policy_assessment: InvestmentPolicyAssessmentV1,
    current_risk: PortfolioRiskAssessmentV1,
    strategy: MetaStrategySelectionV1,
    blockers: Iterable[OptimizerBlockerCode],
    warnings: Iterable[OptimizerWarningCode] = (),
) -> PortfolioOptimizerResultV1:
    current = _current_scenario(
        current_risk,
        portfolio,
        kind=OptimizerScenarioKind.CURRENT,
    )
    target = _current_scenario(
        current_risk,
        portfolio,
        kind=OptimizerScenarioKind.TARGET,
    )
    no_action = _current_scenario(
        current_risk,
        portfolio,
        kind=OptimizerScenarioKind.NO_ACTION,
    )
    values = {
        "schema_version": "1.0",
        "optimized_at": optimized_at,
        "portfolio_snapshot_sha256": portfolio.portfolio_snapshot_sha256,
        "policy_reference": policy_assessment.reference,
        "current_risk_assessment_sha256": current_risk.assessment_sha256,
        "strategy_selection_sha256": strategy.selection_sha256,
        "selected_regime": strategy.selected_regime,
        "targets": (),
        "legs": (),
        "scenarios": _canonical_scenarios(current, target, no_action),
        "blockers": tuple(sorted(set(blockers), key=str)),
        "warnings": tuple(sorted(set(warnings), key=str)),
        "target_risk_assessment": None,
        "optimizer_ready": False,
        "plan_eligible": False,
        "optimizer_sha256": "0" * 64,
        "trading_methods": False,
    }
    provisional = PortfolioOptimizerResultV1.model_construct(**values)
    values["optimizer_sha256"] = portfolio_optimizer_sha256(provisional)
    return PortfolioOptimizerResultV1.model_validate(values)


def _component_directives(
    strategy: MetaStrategySelectionV1,
) -> dict[StrategyComponentKind, StrategyComponentDirective]:
    return {row.kind: row.directive for row in strategy.components}


def _component_budgets(
    *,
    strategy: MetaStrategySelectionV1,
    policy: InvestmentPolicyStatementV1,
    total_value: Decimal,
    assets: tuple[OptimizerAssetV1, ...],
    blockers: list[OptimizerBlockerCode],
    warnings: list[OptimizerWarningCode],
) -> dict[StrategyComponentKind, Decimal]:
    preset = dict(_REGIME_COMPONENT_WEIGHTS[strategy.selected_regime])
    directives = _component_directives(strategy)

    for component in (
        StrategyComponentKind.QUALITY_DEBT,
        StrategyComponentKind.DIVERSIFIED_CORE,
        StrategyComponentKind.BOUNDED_ACTIVE,
    ):
        candidates = tuple(
            row
            for row in assets
            if row.component is component
            and (row.account_eligible is True or row.current_lots > 0)
        )
        directive = directives[component]
        if directive is StrategyComponentDirective.FORBIDDEN:
            preset[StrategyComponentKind.LIQUIDITY_RESERVE] += preset[component]
            preset[component] = Decimal("0")
            continue
        if not candidates:
            if directive is StrategyComponentDirective.REQUIRED:
                _append_unique(
                    blockers,
                    OptimizerBlockerCode.REQUIRED_COMPONENT_UNAVAILABLE,
                )
            if preset[component] > 0:
                _append_unique(
                    warnings,
                    OptimizerWarningCode.COMPONENT_BUDGET_LEFT_AS_CASH,
                )
                preset[StrategyComponentKind.LIQUIDITY_RESERVE] += preset[component]
                preset[component] = Decimal("0")

    reserve_weight = Decimal("0")
    if policy.liquidity_reserve is not None:
        reserve_weight = policy.liquidity_reserve.amount / total_value
        if reserve_weight > 1:
            _append_unique(
                blockers,
                OptimizerBlockerCode.LIQUIDITY_RESERVE_UNFUNDED,
            )
            reserve_weight = Decimal("1")

    cash_before = preset[StrategyComponentKind.LIQUIDITY_RESERVE]
    cash_after = max(cash_before, reserve_weight)
    if cash_after > cash_before and cash_before < 1:
        non_cash_before = Decimal("1") - cash_before
        non_cash_after = Decimal("1") - cash_after
        factor = (
            non_cash_after / non_cash_before
            if non_cash_before > 0
            else Decimal("0")
        )
        for component in (
            StrategyComponentKind.QUALITY_DEBT,
            StrategyComponentKind.DIVERSIFIED_CORE,
            StrategyComponentKind.BOUNDED_ACTIVE,
        ):
            preset[component] *= factor
        preset[StrategyComponentKind.LIQUIDITY_RESERVE] = cash_after
    return preset


def _initial_target_lots(
    *,
    total_value: Decimal,
    assets: tuple[OptimizerAssetV1, ...],
    budgets: dict[StrategyComponentKind, Decimal],
    policy: InvestmentPolicyStatementV1,
    settings: PortfolioOptimizerSettingsV1,
    warnings: list[OptimizerWarningCode],
) -> tuple[dict[str, int], dict[str, Decimal]]:
    targets = {row.stable_key: 0 for row in assets}
    desired_weights = {row.stable_key: Decimal("0") for row in assets}
    max_position = policy.max_position_weight or Decimal("0")

    for component in (
        StrategyComponentKind.QUALITY_DEBT,
        StrategyComponentKind.DIVERSIFIED_CORE,
        StrategyComponentKind.BOUNDED_ACTIVE,
    ):
        budget = budgets[component]
        if budget <= 0:
            continue
        candidates = tuple(
            row
            for row in assets
            if row.component is component
            and (row.account_eligible is True or row.current_lots > 0)
        )
        if not candidates:
            continue
        equal_weight = budget / Decimal(len(candidates))
        per_asset_weight = min(equal_weight, max_position)
        if per_asset_weight * Decimal(len(candidates)) < budget:
            _append_unique(
                warnings,
                OptimizerWarningCode.COMPONENT_BUDGET_LEFT_AS_CASH,
            )
        for asset in candidates:
            desired_weights[asset.stable_key] = per_asset_weight
            lot_notional = asset.unit_base_price * Decimal(asset.lot_size)
            desired_value = total_value * per_asset_weight
            meaningful_floor = max(
                lot_notional,
                total_value * settings.minimum_meaningful_position_weight,
            )
            if desired_value < meaningful_floor:
                _append_unique(
                    warnings,
                    OptimizerWarningCode.MICROPOSITION_SKIPPED,
                )
                targets[asset.stable_key] = 0
                continue
            desired_lots = _floor_ratio(desired_value, lot_notional)
            if (
                asset.account_eligible is not True
                and desired_lots > asset.current_lots
            ):
                desired_lots = asset.current_lots
                _append_unique(
                    warnings,
                    OptimizerWarningCode.COMPONENT_BUDGET_LEFT_AS_CASH,
                )
            targets[asset.stable_key] = desired_lots

    positive = [row for row in assets if targets[row.stable_key] > 0]
    if len(positive) > settings.maximum_target_positions:
        keep = {
            row.stable_key
            for row in sorted(
                positive,
                key=lambda row: (
                    -desired_weights[row.stable_key],
                    row.stable_key,
                ),
            )[: settings.maximum_target_positions]
        }
        for row in positive:
            if row.stable_key not in keep:
                targets[row.stable_key] = 0
                desired_weights[row.stable_key] = Decimal("0")
                _append_unique(
                    warnings,
                    OptimizerWarningCode.MICROPOSITION_SKIPPED,
                )
    return targets, desired_weights


def _validate_trade_evidence(
    *,
    asset: OptimizerAssetV1,
    optimized_at: datetime,
    settings: PortfolioOptimizerSettingsV1,
    side: OptimizerTradeSide,
    blockers: list[OptimizerBlockerCode],
) -> bool:
    ready = True
    if asset.account_eligible is not True and side is OptimizerTradeSide.BUY:
        _append_unique(
            blockers,
            OptimizerBlockerCode.ACCOUNT_ELIGIBILITY_UNKNOWN
            if asset.account_eligible is None
            else OptimizerBlockerCode.ACCOUNT_INELIGIBLE,
        )
        ready = False

    if (
        asset.commission_bps is None
        or asset.friction_as_of is None
        or not asset.friction_source_sha256s
        or (
            side is OptimizerTradeSide.SELL
            and asset.estimated_sell_tax_bps is None
        )
    ):
        _append_unique(
            blockers,
            OptimizerBlockerCode.FRICTION_EVIDENCE_MISSING,
        )
        ready = False
    elif asset.friction_as_of is not None:
        age = (optimized_at - asset.friction_as_of).total_seconds()
        if age > settings.friction_max_age_seconds:
            _append_unique(
                blockers,
                OptimizerBlockerCode.FRICTION_EVIDENCE_STALE,
            )
            ready = False
        if age < -settings.future_tolerance_seconds:
            _append_unique(
                blockers,
                OptimizerBlockerCode.FRICTION_EVIDENCE_FUTURE,
            )
            ready = False

    evidence = asset.market_evidence
    if evidence is None:
        _append_unique(
            blockers,
            OptimizerBlockerCode.MARKET_EVIDENCE_MISSING,
        )
        ready = False
    else:
        age = (optimized_at - evidence.as_of).total_seconds()
        if age > settings.market_max_age_seconds:
            _append_unique(
                blockers,
                OptimizerBlockerCode.MARKET_EVIDENCE_STALE,
            )
            ready = False
        if age < -settings.future_tolerance_seconds:
            _append_unique(
                blockers,
                OptimizerBlockerCode.MARKET_EVIDENCE_FUTURE,
            )
            ready = False
        if evidence.spread_bps > settings.maximum_spread_bps:
            _append_unique(
                blockers,
                OptimizerBlockerCode.SPREAD_TOO_WIDE,
            )
            ready = False
    return ready


def _capacity_scale(
    *,
    asset: OptimizerAssetV1,
    current_lots: int,
    desired_lots: int,
    optimized_at: datetime,
    settings: PortfolioOptimizerSettingsV1,
    warnings: list[OptimizerWarningCode],
    blockers: list[OptimizerBlockerCode],
) -> int:
    if desired_lots == current_lots:
        return desired_lots
    side = (
        OptimizerTradeSide.BUY
        if desired_lots > current_lots
        else OptimizerTradeSide.SELL
    )
    if not _validate_trade_evidence(
        asset=asset,
        optimized_at=optimized_at,
        settings=settings,
        side=side,
        blockers=blockers,
    ):
        return current_lots
    evidence = asset.market_evidence
    assert evidence is not None
    lot_notional = asset.unit_base_price * Decimal(asset.lot_size)
    safe_daily = min(
        evidence.average_daily_turnover_base
        * settings.maximum_daily_turnover_participation,
        evidence.top_of_book_depth_base
        * settings.maximum_top_of_book_participation,
    )
    safe_total = safe_daily * Decimal(settings.maximum_staging_days)
    safe_lots = _floor_ratio(safe_total, lot_notional)
    if safe_lots <= 0:
        _append_unique(
            blockers,
            OptimizerBlockerCode.ZERO_SAFE_CAPACITY,
        )
        return current_lots
    requested = abs(desired_lots - current_lots)
    executable = min(requested, safe_lots)
    if executable < requested:
        _append_unique(
            warnings,
            OptimizerWarningCode.CAPACITY_SCALED,
        )
    return (
        current_lots + executable
        if side is OptimizerTradeSide.BUY
        else current_lots - executable
    )


def _leg(
    *,
    asset: OptimizerAssetV1,
    target_lots: int,
    settings: PortfolioOptimizerSettingsV1,
) -> OptimizerRebalanceLegV1:
    current_lots = asset.current_lots
    quantity_lots = abs(target_lots - current_lots)
    if quantity_lots <= 0:
        raise PortfolioOptimizerError("ZERO_QUANTITY_OPTIMIZER_LEG")
    side = (
        OptimizerTradeSide.BUY
        if target_lots > current_lots
        else OptimizerTradeSide.SELL
    )
    assert asset.commission_bps is not None
    assert asset.friction_source_sha256s
    evidence = asset.market_evidence
    assert evidence is not None
    sell_tax_bps = asset.estimated_sell_tax_bps or Decimal("0")
    gross = Decimal(quantity_lots * asset.lot_size) * asset.unit_base_price
    commission = _money(
        gross * asset.commission_bps / Decimal("10000"),
        settings.money_quantum,
    )
    tax = (
        _money(
            gross * sell_tax_bps / Decimal("10000"),
            settings.money_quantum,
        )
        if side is OptimizerTradeSide.SELL
        else Decimal("0").quantize(settings.money_quantum)
    )
    cash_delta = (
        -(gross + commission)
        if side is OptimizerTradeSide.BUY
        else gross - commission - tax
    )
    safe_daily = min(
        evidence.average_daily_turnover_base
        * settings.maximum_daily_turnover_participation,
        evidence.top_of_book_depth_base
        * settings.maximum_top_of_book_participation,
    )
    required_days = max(1, _ceil_ratio(gross, safe_daily))
    daily_slice = gross / Decimal(required_days)
    return OptimizerRebalanceLegV1(
        trade_id=_trade_id(asset.stable_key),
        stable_key=asset.stable_key,
        component=asset.component,
        side=side,
        current_lots=current_lots,
        target_lots=target_lots,
        quantity_lots=quantity_lots,
        lot_size=asset.lot_size,
        reference_unit_price_base=asset.unit_base_price,
        gross_notional_base=gross,
        commission_bps=asset.commission_bps,
        commission_base=commission,
        estimated_sell_tax_bps=sell_tax_bps,
        estimated_tax_base=tax,
        cash_delta_base=cash_delta,
        required_execution_days=required_days,
        daily_turnover_participation=(
            daily_slice / evidence.average_daily_turnover_base
        ),
        top_of_book_participation=(
            daily_slice / evidence.top_of_book_depth_base
        ),
        staged_execution_required=required_days > 1,
        market_source_sha256=evidence.source_sha256,
        friction_source_sha256s=asset.friction_source_sha256s,
    )


def _build_legs(
    *,
    assets: tuple[OptimizerAssetV1, ...],
    target_lots: dict[str, int],
    settings: PortfolioOptimizerSettingsV1,
) -> tuple[OptimizerRebalanceLegV1, ...]:
    return tuple(
        _leg(
            asset=row,
            target_lots=target_lots[row.stable_key],
            settings=settings,
        )
        for row in assets
        if target_lots[row.stable_key] != row.current_lots
    )


def _scale_buys_to_reserve(
    *,
    portfolio: PortfolioRiskInputV1,
    policy: InvestmentPolicyStatementV1,
    assets: tuple[OptimizerAssetV1, ...],
    target_lots: dict[str, int],
    settings: PortfolioOptimizerSettingsV1,
    warnings: list[OptimizerWarningCode],
) -> tuple[dict[str, int], tuple[OptimizerRebalanceLegV1, ...]]:
    legs = _build_legs(
        assets=assets,
        target_lots=target_lots,
        settings=settings,
    )
    reserve = (
        policy.liquidity_reserve.amount
        if policy.liquidity_reserve is not None
        else Decimal("0")
    )
    cash_after = portfolio.cash_base + sum(
        (row.cash_delta_base for row in legs),
        Decimal("0"),
    )
    if cash_after >= reserve:
        return target_lots, legs

    adjusted = dict(target_lots)
    asset_map = {row.stable_key: row for row in assets}
    buy_legs = sorted(
        (row for row in legs if row.side is OptimizerTradeSide.BUY),
        key=lambda row: (
            _REDUCE_BUY_PRIORITY.get(row.component, 99),
            row.stable_key,
        ),
    )
    shortage = reserve - cash_after
    for leg in buy_legs:
        if shortage <= 0:
            break
        asset = asset_map[leg.stable_key]
        commission_per_lot = _money(
            asset.unit_base_price
            * Decimal(asset.lot_size)
            * (asset.commission_bps or Decimal("0"))
            / Decimal("10000"),
            settings.money_quantum,
        )
        cash_per_lot = (
            asset.unit_base_price * Decimal(asset.lot_size)
            + commission_per_lot
        )
        reduce_lots = min(
            leg.quantity_lots,
            _ceil_ratio(shortage, cash_per_lot),
        )
        if reduce_lots <= 0:
            continue
        adjusted[leg.stable_key] -= reduce_lots
        shortage -= cash_per_lot * Decimal(reduce_lots)
        _append_unique(
            warnings,
            OptimizerWarningCode.CASH_RESERVE_SCALED_BUYS,
        )

    rebuilt = _build_legs(
        assets=assets,
        target_lots=adjusted,
        settings=settings,
    )
    return adjusted, rebuilt


def _risk_position_for_target(
    asset: OptimizerAssetV1,
    target_lots: int,
) -> RiskPositionV1 | None:
    if target_lots <= 0:
        return None
    units = target_lots * asset.lot_size
    payload = asset.risk_template.model_dump(mode="python")
    payload["native_market_value"] = Decimal(units) * asset.unit_native_price
    payload["base_market_value"] = Decimal(units) * asset.unit_base_price
    return RiskPositionV1.model_validate(payload)


def _trade_effects(
    *,
    assets: tuple[OptimizerAssetV1, ...],
    target_lots: dict[str, int],
    legs: tuple[OptimizerRebalanceLegV1, ...],
) -> tuple[ProposedTradeRiskEffectV1, ...]:
    leg_map = {row.stable_key: row for row in legs}
    effects: list[ProposedTradeRiskEffectV1] = []
    for asset in assets:
        if target_lots[asset.stable_key] == asset.current_lots:
            continue
        leg = leg_map[asset.stable_key]
        effects.append(
            ProposedTradeRiskEffectV1(
                trade_id=leg.trade_id,
                stable_key=asset.stable_key,
                expected_before_value_base=asset.risk_template.base_market_value,
                cash_delta_base=leg.cash_delta_base,
                after_position=_risk_position_for_target(
                    asset,
                    target_lots[asset.stable_key],
                ),
            )
        )
    return tuple(effects)


def _targets(
    *,
    assets: tuple[OptimizerAssetV1, ...],
    target_lots: dict[str, int],
    desired_weights: dict[str, Decimal],
    target_total: Decimal,
    settings: PortfolioOptimizerSettingsV1,
) -> tuple[OptimizerTargetPositionV1, ...]:
    rows: list[OptimizerTargetPositionV1] = []
    for asset in assets:
        target_value = (
            Decimal(target_lots[asset.stable_key] * asset.lot_size)
            * asset.unit_base_price
        )
        target_weight = (
            target_value / target_total
            if target_total > 0
            else Decimal("0")
        )
        rows.append(
            OptimizerTargetPositionV1(
                stable_key=asset.stable_key,
                component=asset.component,
                current_lots=asset.current_lots,
                target_lots=target_lots[asset.stable_key],
                lot_size=asset.lot_size,
                desired_weight=_weight(
                    desired_weights[asset.stable_key],
                    settings.weight_quantum,
                ),
                current_value_base=asset.risk_template.base_market_value,
                target_value_base=target_value,
                target_weight=_weight(
                    target_weight,
                    settings.weight_quantum,
                ),
            )
        )
    return tuple(rows)


def optimize_portfolio(
    *,
    portfolio: PortfolioRiskInputV1,
    policy: InvestmentPolicyStatementV1,
    policy_assessment: InvestmentPolicyAssessmentV1,
    current_risk: PortfolioRiskAssessmentV1,
    strategy: MetaStrategySelectionV1,
    assets: Iterable[OptimizerAssetV1],
    settings: PortfolioOptimizerSettingsV1 | None = None,
    risk_settings: RiskEngineSettingsV1 | None = None,
    stress_scenarios: Iterable[
        StressScenarioDefinitionV1
    ] = DEFAULT_STRESS_SCENARIOS,
    macro: MacroRiskAssumptionsV1 | None = None,
    optimized_at: datetime | None = None,
) -> PortfolioOptimizerResultV1:
    """Compile a strategy into lot-executable targets and revalidate via WP8."""
    evaluation_time = _aware_utc(optimized_at)
    settings_value = settings or PortfolioOptimizerSettingsV1()
    asset_values = tuple(sorted(assets, key=lambda row: row.stable_key))
    if len({row.stable_key for row in asset_values}) != len(asset_values):
        raise PortfolioOptimizerError("OPTIMIZER_ASSET_KEYS_MUST_BE_UNIQUE")

    blockers: list[OptimizerBlockerCode] = []
    warnings: list[OptimizerWarningCode] = []

    if (
        policy_assessment.reference.policy_id != policy.policy_id
        or policy_assessment.reference.version != policy.version
        or policy_assessment.reference.fingerprint_sha256
        != policy_fingerprint_sha256(policy)
        or portfolio.policy_reference != policy_assessment.reference
    ):
        _append_unique(
            blockers,
            OptimizerBlockerCode.POLICY_BINDING_MISMATCH,
        )
    if (
        current_risk.portfolio_snapshot_sha256
        != portfolio.portfolio_snapshot_sha256
        or current_risk.policy_reference != policy_assessment.reference
        or current_risk.proposed_trade_ids
        or current_risk.before != current_risk.after
    ):
        _append_unique(
            blockers,
            OptimizerBlockerCode.RISK_BINDING_MISMATCH,
        )
    if (
        strategy.portfolio_snapshot_sha256
        != portfolio.portfolio_snapshot_sha256
        or strategy.policy_reference != policy_assessment.reference
        or strategy.risk_assessment_sha256 != current_risk.assessment_sha256
    ):
        _append_unique(
            blockers,
            OptimizerBlockerCode.STRATEGY_BINDING_MISMATCH,
        )
    if not strategy.decision_ready or (
        strategy.selected_regime is not StrategyRegime.NO_ACTION
        and not strategy.optimizer_eligible
    ):
        _append_unique(
            blockers,
            OptimizerBlockerCode.STRATEGY_NOT_READY,
        )

    current_positions = {row.stable_key: row for row in portfolio.positions}
    asset_map = {row.stable_key: row for row in asset_values}
    if not set(current_positions).issubset(asset_map):
        _append_unique(
            blockers,
            OptimizerBlockerCode.ASSET_UNIVERSE_INCOMPLETE,
        )
    for stable_key, position in current_positions.items():
        asset = asset_map.get(stable_key)
        if asset is not None and asset.risk_template != position:
            _append_unique(
                blockers,
                OptimizerBlockerCode.PORTFOLIO_BINDING_MISMATCH,
            )

    if blockers:
        return _blocked_result(
            optimized_at=evaluation_time,
            portfolio=portfolio,
            policy_assessment=policy_assessment,
            current_risk=current_risk,
            strategy=strategy,
            blockers=blockers,
        )

    if strategy.selected_regime is StrategyRegime.NO_ACTION:
        warnings.append(OptimizerWarningCode.NO_ACTION_SELECTED)
        target_lots = {
            row.stable_key: row.current_lots for row in asset_values
        }
        desired_weights = {
            row.stable_key: (
                row.risk_template.base_market_value
                / portfolio.total_value_base
            )
            for row in asset_values
        }
        targets = _targets(
            assets=asset_values,
            target_lots=target_lots,
            desired_weights=desired_weights,
            target_total=portfolio.total_value_base,
            settings=settings_value,
        )
        current = _current_scenario(
            current_risk,
            portfolio,
            kind=OptimizerScenarioKind.CURRENT,
        )
        target = _current_scenario(
            current_risk,
            portfolio,
            kind=OptimizerScenarioKind.TARGET,
        )
        no_action = _current_scenario(
            current_risk,
            portfolio,
            kind=OptimizerScenarioKind.NO_ACTION,
        )
        values = {
            "schema_version": "1.0",
            "optimized_at": evaluation_time,
            "portfolio_snapshot_sha256": portfolio.portfolio_snapshot_sha256,
            "policy_reference": policy_assessment.reference,
            "current_risk_assessment_sha256": current_risk.assessment_sha256,
            "strategy_selection_sha256": strategy.selection_sha256,
            "selected_regime": strategy.selected_regime,
            "targets": targets,
            "legs": (),
            "scenarios": _canonical_scenarios(current, target, no_action),
            "blockers": (),
            "warnings": tuple(sorted(set(warnings), key=str)),
            "target_risk_assessment": current_risk,
            "optimizer_ready": True,
            "plan_eligible": False,
            "optimizer_sha256": "0" * 64,
            "trading_methods": False,
        }
        provisional = PortfolioOptimizerResultV1.model_construct(**values)
        values["optimizer_sha256"] = portfolio_optimizer_sha256(provisional)
        return PortfolioOptimizerResultV1.model_validate(values)

    budgets = _component_budgets(
        strategy=strategy,
        policy=policy,
        total_value=portfolio.total_value_base,
        assets=asset_values,
        blockers=blockers,
        warnings=warnings,
    )
    target_lots, desired_weights = _initial_target_lots(
        total_value=portfolio.total_value_base,
        assets=asset_values,
        budgets=budgets,
        policy=policy,
        settings=settings_value,
        warnings=warnings,
    )

    for asset in asset_values:
        target_lots[asset.stable_key] = _capacity_scale(
            asset=asset,
            current_lots=asset.current_lots,
            desired_lots=target_lots[asset.stable_key],
            optimized_at=evaluation_time,
            settings=settings_value,
            warnings=warnings,
            blockers=blockers,
        )

    target_lots, legs = _scale_buys_to_reserve(
        portfolio=portfolio,
        policy=policy,
        assets=asset_values,
        target_lots=target_lots,
        settings=settings_value,
        warnings=warnings,
    )
    cash_after = portfolio.cash_base + sum(
        (row.cash_delta_base for row in legs),
        Decimal("0"),
    )
    reserve = (
        policy.liquidity_reserve.amount
        if policy.liquidity_reserve is not None
        else Decimal("0")
    )
    if cash_after < reserve:
        _append_unique(
            blockers,
            OptimizerBlockerCode.LIQUIDITY_RESERVE_UNFUNDED,
        )
    if any(row.required_execution_days > 1 for row in legs):
        _append_unique(
            warnings,
            OptimizerWarningCode.STAGED_EXECUTION_REQUIRED,
        )
    if legs:
        _append_unique(
            warnings,
            OptimizerWarningCode.PARTIAL_FILL_AWARE,
        )
    if any(
        Decimal(target_lots[row.stable_key] * row.lot_size)
        * row.unit_base_price
        < portfolio.total_value_base * desired_weights[row.stable_key]
        for row in asset_values
        if desired_weights[row.stable_key] > 0
    ):
        _append_unique(
            warnings,
            OptimizerWarningCode.LOT_ROUNDING_RESIDUAL_CASH,
        )

    effects = _trade_effects(
        assets=asset_values,
        target_lots=target_lots,
        legs=legs,
    )
    target_risk = assess_portfolio_risk(
        portfolio=portfolio,
        policy=policy,
        policy_assessment=policy_assessment,
        proposed_trades=effects,
        settings=risk_settings,
        stress_scenarios=stress_scenarios,
        macro=macro,
        assessed_at=evaluation_time,
    )
    if target_risk.before != current_risk.after:
        _append_unique(
            blockers,
            OptimizerBlockerCode.RISK_REVALIDATION_BASELINE_MISMATCH,
        )
    if not target_risk.decision_ready:
        _append_unique(
            blockers,
            OptimizerBlockerCode.TARGET_RISK_NOT_READY,
        )
    if not target_risk.after.policy_compliant:
        _append_unique(
            blockers,
            OptimizerBlockerCode.TARGET_POLICY_BREACH,
        )

    turnover = sum(
        (row.gross_notional_base for row in legs),
        Decimal("0"),
    )
    commission = sum(
        (row.commission_base for row in legs),
        Decimal("0"),
    )
    tax = sum(
        (row.estimated_tax_base for row in legs),
        Decimal("0"),
    )
    target_state = target_risk.after
    targets = _targets(
        assets=asset_values,
        target_lots=target_lots,
        desired_weights=desired_weights,
        target_total=target_state.total_value_base,
        settings=settings_value,
    )
    current = _current_scenario(
        current_risk,
        portfolio,
        kind=OptimizerScenarioKind.CURRENT,
    )
    no_action = _current_scenario(
        current_risk,
        portfolio,
        kind=OptimizerScenarioKind.NO_ACTION,
    )
    target = OptimizerScenarioV1(
        kind=OptimizerScenarioKind.TARGET,
        portfolio_value_base=target_state.total_value_base,
        cash_base=target_state.cash_base,
        securities_value_base=(
            target_state.total_value_base - target_state.cash_base
        ),
        position_count=sum(1 for row in targets if row.target_lots > 0),
        turnover_base=turnover,
        commission_base=commission,
        estimated_tax_base=tax,
        policy_compliant=target_state.policy_compliant,
        risk_assessment_sha256=target_risk.assessment_sha256,
        risk_blockers=target_state.blockers,
    )

    canonical_blockers = tuple(sorted(set(blockers), key=str))
    canonical_warnings = tuple(sorted(set(warnings), key=str))
    optimizer_ready = not canonical_blockers
    plan_eligible = (
        optimizer_ready and bool(legs) and target_risk.plan_eligible
    )
    values = {
        "schema_version": "1.0",
        "optimized_at": evaluation_time,
        "portfolio_snapshot_sha256": portfolio.portfolio_snapshot_sha256,
        "policy_reference": policy_assessment.reference,
        "current_risk_assessment_sha256": current_risk.assessment_sha256,
        "strategy_selection_sha256": strategy.selection_sha256,
        "selected_regime": strategy.selected_regime,
        "targets": targets,
        "legs": legs,
        "scenarios": _canonical_scenarios(current, target, no_action),
        "blockers": canonical_blockers,
        "warnings": canonical_warnings,
        "target_risk_assessment": target_risk,
        "optimizer_ready": optimizer_ready,
        "plan_eligible": plan_eligible,
        "optimizer_sha256": "0" * 64,
        "trading_methods": False,
    }
    provisional = PortfolioOptimizerResultV1.model_construct(**values)
    values["optimizer_sha256"] = portfolio_optimizer_sha256(provisional)
    return PortfolioOptimizerResultV1.model_validate(values)
