from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import TypeVar

from pydantic import ValidationError

from omni_cio.contracts.v1.investment_policy import (
    InvestmentPolicyAssessmentV1,
    InvestmentPolicyStatementV1,
)
from omni_cio.contracts.v1.meta_strategy import (
    MetaStrategySelectionV1,
    StrategyRegime,
    meta_strategy_sha256,
)
from omni_cio.contracts.v1.portfolio import InstrumentType
from omni_cio.contracts.v1.portfolio_optimizer import (
    OptimizerAssetV1,
    OptimizerScenarioKind,
    OptimizerTradeSide,
    PortfolioOptimizerResultV1,
    portfolio_optimizer_sha256,
)
from omni_cio.contracts.v1.portfolio_plan import (
    PlanCancellationCode,
    PlanCancellationConditionV1,
    PlanMarketBaselineV1,
    PlanMarketDriftResultV1,
    PlanMarketObservationV1,
    PlanReviewStatus,
    PortfolioPlanAction,
    PortfolioPlanLegV1,
    PortfolioPlanReviewInputV1,
    PortfolioPlanReviewV1,
    PortfolioPlanSettingsV1,
    PortfolioPlanV1,
    owner_approval_phrase,
    portfolio_plan_review_sha256,
    portfolio_plan_sha256,
)
from omni_cio.contracts.v1.portfolio_risk import (
    PortfolioRiskAssessmentV1,
    PortfolioRiskInputV1,
    portfolio_risk_sha256,
)
from omni_cio.policy import policy_fingerprint_sha256


class PortfolioPlanError(ValueError):
    """Plan inputs cannot be bound safely into one immutable plan."""


_T = TypeVar("_T")


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise PortfolioPlanError("PLAN_TIMESTAMP_MUST_BE_AWARE")
    return result.astimezone(timezone.utc)


def _append_unique(target: list[_T], value: _T) -> None:
    if value not in target:
        target.append(value)


def _scenario(
    optimizer: PortfolioOptimizerResultV1,
    kind: OptimizerScenarioKind,
):
    return next(row for row in optimizer.scenarios if row.kind is kind)


def _all_cancellation_conditions() -> tuple[PlanCancellationConditionV1, ...]:
    return tuple(
        PlanCancellationConditionV1(code=code)
        for code in sorted(PlanCancellationCode, key=lambda item: item.value)
    )


def _canonical_upstream(
    *,
    portfolio: PortfolioRiskInputV1,
    policy: InvestmentPolicyStatementV1,
    policy_assessment: InvestmentPolicyAssessmentV1,
    current_risk: PortfolioRiskAssessmentV1,
    strategy: MetaStrategySelectionV1,
    optimizer: PortfolioOptimizerResultV1,
) -> tuple[
    PortfolioRiskInputV1,
    InvestmentPolicyStatementV1,
    InvestmentPolicyAssessmentV1,
    PortfolioRiskAssessmentV1,
    MetaStrategySelectionV1,
    PortfolioOptimizerResultV1,
]:
    try:
        canonical_portfolio = PortfolioRiskInputV1.model_validate(
            portfolio.model_dump(mode="python")
        )
    except ValidationError as exc:
        raise PortfolioPlanError("PLAN_PORTFOLIO_OBJECT_TAMPERED") from exc
    try:
        canonical_policy = InvestmentPolicyStatementV1.model_validate(
            policy.model_dump(mode="python")
        )
    except ValidationError as exc:
        raise PortfolioPlanError("PLAN_POLICY_OBJECT_TAMPERED") from exc
    try:
        canonical_assessment = InvestmentPolicyAssessmentV1.model_validate(
            policy_assessment.model_dump(mode="python")
        )
    except ValidationError as exc:
        raise PortfolioPlanError("PLAN_POLICY_ASSESSMENT_OBJECT_TAMPERED") from exc
    try:
        canonical_risk = PortfolioRiskAssessmentV1.model_validate(
            current_risk.model_dump(mode="python")
        )
    except ValidationError as exc:
        raise PortfolioPlanError("PLAN_CURRENT_RISK_OBJECT_TAMPERED") from exc
    try:
        canonical_strategy = MetaStrategySelectionV1.model_validate(
            strategy.model_dump(mode="python")
        )
    except ValidationError as exc:
        raise PortfolioPlanError("PLAN_STRATEGY_OBJECT_TAMPERED") from exc
    try:
        canonical_optimizer = PortfolioOptimizerResultV1.model_validate(
            optimizer.model_dump(mode="python")
        )
    except ValidationError as exc:
        raise PortfolioPlanError("PLAN_OPTIMIZER_OBJECT_TAMPERED") from exc
    return (
        canonical_portfolio,
        canonical_policy,
        canonical_assessment,
        canonical_risk,
        canonical_strategy,
        canonical_optimizer,
    )


def _validate_hash_integrity(
    *,
    current_risk: PortfolioRiskAssessmentV1,
    strategy: MetaStrategySelectionV1,
    optimizer: PortfolioOptimizerResultV1,
) -> None:
    if current_risk.assessment_sha256 != portfolio_risk_sha256(current_risk):
        raise PortfolioPlanError("PLAN_CURRENT_RISK_OBJECT_TAMPERED")
    if strategy.selection_sha256 != meta_strategy_sha256(strategy):
        raise PortfolioPlanError("PLAN_STRATEGY_OBJECT_TAMPERED")
    if optimizer.optimizer_sha256 != portfolio_optimizer_sha256(optimizer):
        raise PortfolioPlanError("PLAN_OPTIMIZER_OBJECT_TAMPERED")
    target_risk = optimizer.target_risk_assessment
    if target_risk is not None and (
        target_risk.assessment_sha256 != portfolio_risk_sha256(target_risk)
    ):
        raise PortfolioPlanError("PLAN_TARGET_RISK_OBJECT_TAMPERED")


def _validate_bindings(
    *,
    portfolio: PortfolioRiskInputV1,
    policy: InvestmentPolicyStatementV1,
    policy_assessment: InvestmentPolicyAssessmentV1,
    current_risk: PortfolioRiskAssessmentV1,
    strategy: MetaStrategySelectionV1,
    optimizer: PortfolioOptimizerResultV1,
) -> None:
    _validate_hash_integrity(
        current_risk=current_risk,
        strategy=strategy,
        optimizer=optimizer,
    )
    if not policy_assessment.ready_for_personal_sizing:
        raise PortfolioPlanError("PLAN_IPS_NOT_READY")
    if (
        policy_assessment.reference.policy_id != policy.policy_id
        or policy_assessment.reference.version != policy.version
        or policy_assessment.reference.fingerprint_sha256
        != policy_fingerprint_sha256(policy)
        or portfolio.policy_reference != policy_assessment.reference
    ):
        raise PortfolioPlanError("PLAN_POLICY_BINDING_MISMATCH")
    if (
        current_risk.portfolio_snapshot_sha256
        != portfolio.portfolio_snapshot_sha256
        or current_risk.policy_reference != policy_assessment.reference
        or current_risk.proposed_trade_ids
        or current_risk.before != current_risk.after
        or not current_risk.decision_ready
        or current_risk.after.total_value_base != portfolio.total_value_base
        or current_risk.after.cash_base != portfolio.cash_base
    ):
        raise PortfolioPlanError("PLAN_CURRENT_RISK_BINDING_MISMATCH")
    if (
        strategy.portfolio_snapshot_sha256 != portfolio.portfolio_snapshot_sha256
        or strategy.policy_reference != policy_assessment.reference
        or strategy.risk_assessment_sha256 != current_risk.assessment_sha256
        or not strategy.decision_ready
    ):
        raise PortfolioPlanError("PLAN_STRATEGY_BINDING_MISMATCH")
    if (
        optimizer.portfolio_snapshot_sha256 != portfolio.portfolio_snapshot_sha256
        or optimizer.policy_reference != policy_assessment.reference
        or optimizer.current_risk_assessment_sha256 != current_risk.assessment_sha256
        or optimizer.strategy_selection_sha256 != strategy.selection_sha256
        or optimizer.selected_regime is not strategy.selected_regime
        or not optimizer.optimizer_ready
    ):
        raise PortfolioPlanError("PLAN_OPTIMIZER_BINDING_MISMATCH")
    if optimizer.target_risk_assessment is None:
        raise PortfolioPlanError("PLAN_TARGET_RISK_REQUIRED")
    target_risk = optimizer.target_risk_assessment
    if (
        target_risk.portfolio_snapshot_sha256 != portfolio.portfolio_snapshot_sha256
        or target_risk.policy_reference != policy_assessment.reference
        or target_risk.before != current_risk.after
    ):
        raise PortfolioPlanError("PLAN_TARGET_RISK_BINDING_MISMATCH")

    no_action = optimizer.selected_regime is StrategyRegime.NO_ACTION
    if no_action:
        if optimizer.legs or optimizer.plan_eligible:
            raise PortfolioPlanError("NO_ACTION_OPTIMIZER_MUST_NOT_HAVE_EXECUTION_LEGS")
        if target_risk != current_risk:
            raise PortfolioPlanError("NO_ACTION_TARGET_RISK_MUST_EQUAL_CURRENT_RISK")
    else:
        if not optimizer.plan_eligible or not optimizer.legs:
            raise PortfolioPlanError("ACTIONABLE_OPTIMIZER_NOT_PLAN_ELIGIBLE")
        if not target_risk.plan_eligible or not target_risk.after.policy_compliant:
            raise PortfolioPlanError("ACTIONABLE_TARGET_RISK_NOT_PLAN_ELIGIBLE")


def _canonical_assets(
    optimizer_assets: Iterable[OptimizerAssetV1],
) -> tuple[OptimizerAssetV1, ...]:
    canonical: list[OptimizerAssetV1] = []
    for row in optimizer_assets:
        try:
            canonical.append(
                OptimizerAssetV1.model_validate(row.model_dump(mode="python"))
            )
        except (AttributeError, ValidationError) as exc:
            raise PortfolioPlanError("PLAN_OPTIMIZER_ASSET_TAMPERED") from exc
    result = tuple(sorted(canonical, key=lambda row: row.stable_key))
    keys = [row.stable_key for row in result]
    if len(keys) != len(set(keys)):
        raise PortfolioPlanError("PLAN_OPTIMIZER_ASSET_KEYS_MUST_BE_UNIQUE")
    return result


def _validate_asset_portfolio_binding(
    *,
    portfolio: PortfolioRiskInputV1,
    assets: tuple[OptimizerAssetV1, ...],
    optimizer: PortfolioOptimizerResultV1,
) -> dict[str, OptimizerAssetV1]:
    asset_map = {row.stable_key: row for row in assets}
    target_keys = {row.stable_key for row in optimizer.targets}
    if set(asset_map) != target_keys:
        raise PortfolioPlanError("PLAN_OPTIMIZER_ASSET_SET_MISMATCH")

    portfolio_map = {row.stable_key: row for row in portfolio.positions}
    current_asset_keys = {row.stable_key for row in assets if row.current_lots > 0}
    if current_asset_keys != set(portfolio_map):
        raise PortfolioPlanError("PLAN_CURRENT_ASSET_SET_MISMATCH")
    for stable_key, position in portfolio_map.items():
        asset = asset_map.get(stable_key)
        if asset is None or asset.risk_template != position:
            raise PortfolioPlanError("PLAN_PORTFOLIO_ASSET_BINDING_MISMATCH")
    return asset_map


def _age_seconds(*, as_of: datetime, now: datetime) -> float:
    return (now - as_of).total_seconds()


def _require_fresh_build_evidence(
    *,
    asset: OptimizerAssetV1,
    created_at: datetime,
    settings: PortfolioPlanSettingsV1,
    side: OptimizerTradeSide,
) -> None:
    market = asset.market_evidence
    if market is None:
        raise PortfolioPlanError("PLAN_MARKET_EVIDENCE_REQUIRED")
    tolerance = settings.drift_tolerance
    market_age = _age_seconds(as_of=market.as_of, now=created_at)
    if market_age > tolerance.market_max_age_seconds:
        raise PortfolioPlanError("PLAN_MARKET_EVIDENCE_STALE")
    if market_age < -tolerance.future_tolerance_seconds:
        raise PortfolioPlanError("PLAN_MARKET_EVIDENCE_FUTURE")

    if asset.friction_as_of is None or not asset.friction_source_sha256s:
        raise PortfolioPlanError("PLAN_FRICTION_EVIDENCE_REQUIRED")
    friction_age = _age_seconds(as_of=asset.friction_as_of, now=created_at)
    if friction_age > tolerance.friction_max_age_seconds:
        raise PortfolioPlanError("PLAN_FRICTION_EVIDENCE_STALE")
    if friction_age < -tolerance.future_tolerance_seconds:
        raise PortfolioPlanError("PLAN_FRICTION_EVIDENCE_FUTURE")

    fx = asset.risk_template.fx
    if fx is not None:
        fx_age = _age_seconds(as_of=fx.as_of, now=created_at)
        if fx_age > tolerance.fx_max_age_seconds:
            raise PortfolioPlanError("PLAN_FX_EVIDENCE_STALE")
        if fx_age < -tolerance.future_tolerance_seconds:
            raise PortfolioPlanError("PLAN_FX_EVIDENCE_FUTURE")

    if side is OptimizerTradeSide.BUY and asset.account_eligible is not True:
        raise PortfolioPlanError("PLAN_BUY_ACCOUNT_NOT_ELIGIBLE")
    if (
        asset.risk_template.instrument_type is InstrumentType.BOND
        and market.accrued_interest_per_lot_base is None
    ):
        raise PortfolioPlanError("PLAN_BOND_ACCRUED_INTEREST_REQUIRED")


def _baseline_from_asset(
    *,
    asset: OptimizerAssetV1,
    optimizer_leg,
    created_at: datetime,
    settings: PortfolioPlanSettingsV1,
) -> PlanMarketBaselineV1:
    _require_fresh_build_evidence(
        asset=asset,
        created_at=created_at,
        settings=settings,
        side=optimizer_leg.side,
    )
    market = asset.market_evidence
    assert market is not None
    assert asset.friction_as_of is not None
    assert asset.friction_source_sha256s
    if asset.commission_bps is None:
        raise PortfolioPlanError("PLAN_COMMISSION_EVIDENCE_REQUIRED")
    if (
        optimizer_leg.side is OptimizerTradeSide.SELL
        and asset.estimated_sell_tax_bps is None
    ):
        raise PortfolioPlanError("PLAN_SELL_TAX_EVIDENCE_REQUIRED")

    if asset.risk_template.instrument_type is InstrumentType.BOND:
        if market.accrued_interest_per_lot_base is None:
            raise PortfolioPlanError("PLAN_BOND_ACCRUED_INTEREST_REQUIRED")
        market_aci = market.accrued_interest_per_lot_base
    else:
        market_aci = Decimal("0")
    if optimizer_leg.market_source_sha256 != market.source_sha256:
        raise PortfolioPlanError("PLAN_MARKET_SOURCE_BINDING_MISMATCH")
    if optimizer_leg.reference_clean_unit_price_base != market.clean_unit_price_base:
        raise PortfolioPlanError("PLAN_MARKET_PRICE_BINDING_MISMATCH")
    if optimizer_leg.accrued_interest_per_lot_base != market_aci:
        raise PortfolioPlanError("PLAN_ACCRUED_INTEREST_BINDING_MISMATCH")
    if optimizer_leg.friction_source_sha256s != asset.friction_source_sha256s:
        raise PortfolioPlanError("PLAN_FRICTION_SOURCE_BINDING_MISMATCH")
    if optimizer_leg.commission_bps != asset.commission_bps:
        raise PortfolioPlanError("PLAN_COMMISSION_BINDING_MISMATCH")
    expected_tax_bps = asset.estimated_sell_tax_bps or Decimal("0")
    if optimizer_leg.estimated_sell_tax_bps != expected_tax_bps:
        raise PortfolioPlanError("PLAN_TAX_BINDING_MISMATCH")
    if optimizer_leg.current_lots != asset.current_lots:
        raise PortfolioPlanError("PLAN_LOT_BINDING_MISMATCH")

    fx = asset.risk_template.fx
    return PlanMarketBaselineV1(
        stable_key=asset.stable_key,
        lot_size=asset.lot_size,
        market_source_sha256=market.source_sha256,
        market_as_of=market.as_of,
        clean_unit_price_base=market.clean_unit_price_base,
        accrued_interest_per_lot_base=market.accrued_interest_per_lot_base,
        spread_bps=market.spread_bps,
        average_daily_turnover_base=market.average_daily_turnover_base,
        top_of_book_depth_base=market.top_of_book_depth_base,
        friction_as_of=asset.friction_as_of,
        friction_source_sha256s=asset.friction_source_sha256s,
        commission_bps=asset.commission_bps,
        estimated_sell_tax_bps=expected_tax_bps,
        account_eligible=asset.account_eligible,
        fx_rate_to_base=fx.rate_to_base if fx is not None else None,
        fx_source_sha256=fx.source_sha256 if fx is not None else None,
        fx_as_of=fx.as_of if fx is not None else None,
    )


def build_portfolio_plan(
    *,
    portfolio: PortfolioRiskInputV1,
    policy: InvestmentPolicyStatementV1,
    policy_assessment: InvestmentPolicyAssessmentV1,
    current_risk: PortfolioRiskAssessmentV1,
    strategy: MetaStrategySelectionV1,
    optimizer: PortfolioOptimizerResultV1,
    optimizer_assets: Iterable[OptimizerAssetV1],
    settings: PortfolioPlanSettingsV1 | None = None,
    created_at: datetime | None = None,
) -> PortfolioPlanV1:
    """Build an immutable reviewable plan without granting execution authority."""
    evaluation_time = _aware_utc(created_at)
    settings_value = settings or PortfolioPlanSettingsV1()
    (
        portfolio,
        policy,
        policy_assessment,
        current_risk,
        strategy,
        optimizer,
    ) = _canonical_upstream(
        portfolio=portfolio,
        policy=policy,
        policy_assessment=policy_assessment,
        current_risk=current_risk,
        strategy=strategy,
        optimizer=optimizer,
    )
    _validate_bindings(
        portfolio=portfolio,
        policy=policy,
        policy_assessment=policy_assessment,
        current_risk=current_risk,
        strategy=strategy,
        optimizer=optimizer,
    )
    assets = _canonical_assets(optimizer_assets)
    asset_map = _validate_asset_portfolio_binding(
        portfolio=portfolio,
        assets=assets,
        optimizer=optimizer,
    )

    no_action = optimizer.selected_regime is StrategyRegime.NO_ACTION
    legs: tuple[PortfolioPlanLegV1, ...]
    baselines: tuple[PlanMarketBaselineV1, ...]
    if no_action:
        legs = (
            PortfolioPlanLegV1(
                sequence=1,
                action=PortfolioPlanAction.NO_ACTION,
            ),
        )
        baselines = ()
    else:
        plan_legs: list[PortfolioPlanLegV1] = []
        baseline_rows: list[PlanMarketBaselineV1] = []
        for sequence, optimizer_leg in enumerate(optimizer.legs, start=1):
            asset = asset_map.get(optimizer_leg.stable_key)
            if asset is None:
                raise PortfolioPlanError("PLAN_LEG_ASSET_MISSING")
            baseline_rows.append(
                _baseline_from_asset(
                    asset=asset,
                    optimizer_leg=optimizer_leg,
                    created_at=evaluation_time,
                    settings=settings_value,
                )
            )
            plan_legs.append(
                PortfolioPlanLegV1(
                    sequence=sequence,
                    action=PortfolioPlanAction(optimizer_leg.side.value),
                    optimizer_leg=optimizer_leg,
                )
            )
        legs = tuple(plan_legs)
        baselines = tuple(sorted(baseline_rows, key=lambda row: row.stable_key))

    current_scenario = _scenario(optimizer, OptimizerScenarioKind.CURRENT)
    target_scenario = _scenario(optimizer, OptimizerScenarioKind.TARGET)
    target_risk = optimizer.target_risk_assessment
    assert target_risk is not None
    execution_days = max(
        (row.required_execution_days for row in optimizer.legs),
        default=1,
    )

    values = {
        "schema_version": "1.0",
        "object_type": "PORTFOLIO_PLAN",
        "created_at": evaluation_time,
        "expires_at": evaluation_time
        + timedelta(
            days=execution_days - 1,
            seconds=settings_value.validity_seconds,
        ),
        "portfolio_snapshot_sha256": portfolio.portfolio_snapshot_sha256,
        "policy_reference": policy_assessment.reference,
        "current_risk_assessment_sha256": current_risk.assessment_sha256,
        "strategy_selection_sha256": strategy.selection_sha256,
        "optimizer_sha256": optimizer.optimizer_sha256,
        "target_risk_assessment_sha256": target_risk.assessment_sha256,
        "selected_regime": optimizer.selected_regime,
        "targets": optimizer.targets,
        "legs": legs,
        "market_baselines": baselines,
        "current_value_base": current_scenario.portfolio_value_base,
        "target_value_base": target_scenario.portfolio_value_base,
        "current_cash_base": current_scenario.cash_base,
        "target_cash_base": target_scenario.cash_base,
        "total_clean_turnover_base": sum(
            (row.gross_notional_base for row in optimizer.legs),
            Decimal("0"),
        ),
        "total_accrued_interest_base": sum(
            (row.accrued_interest_base for row in optimizer.legs),
            Decimal("0"),
        ),
        "total_settlement_turnover_base": sum(
            (row.settlement_notional_base for row in optimizer.legs),
            Decimal("0"),
        ),
        "total_commission_base": sum(
            (row.commission_base for row in optimizer.legs),
            Decimal("0"),
        ),
        "total_estimated_tax_base": sum(
            (row.estimated_tax_base for row in optimizer.legs),
            Decimal("0"),
        ),
        "risk_before": current_risk.after,
        "risk_after": target_risk.after,
        "drift_tolerance": settings_value.drift_tolerance,
        "cancellation_conditions": _all_cancellation_conditions(),
        "approval_required": not no_action,
        "owner_approval_phrase": None,
        "plan_sha256": "0" * 64,
        "execution_authorized": False,
        "trading_methods": False,
    }
    provisional = PortfolioPlanV1.model_construct(**values)
    plan_sha = portfolio_plan_sha256(provisional)
    values["plan_sha256"] = plan_sha
    values["owner_approval_phrase"] = (
        owner_approval_phrase(plan_sha) if not no_action else None
    )
    return PortfolioPlanV1.model_validate(values)


def _drift_bps(current: Decimal, baseline: Decimal) -> Decimal:
    return abs(current - baseline) / baseline * Decimal("10000")


def _market_drift(
    *,
    baseline: PlanMarketBaselineV1,
    observation: PlanMarketObservationV1 | None,
    action: PortfolioPlanAction,
    reviewed_at: datetime,
    plan: PortfolioPlanV1,
) -> PlanMarketDriftResultV1:
    codes: list[PlanCancellationCode] = []
    if observation is None:
        codes.append(PlanCancellationCode.MARKET_EVIDENCE_MISSING)
        return PlanMarketDriftResultV1(
            stable_key=baseline.stable_key,
            cancellation_codes=tuple(codes),
        )

    tolerance = plan.drift_tolerance
    market_age = _age_seconds(as_of=observation.observed_at, now=reviewed_at)
    if market_age > tolerance.market_max_age_seconds:
        _append_unique(codes, PlanCancellationCode.MARKET_EVIDENCE_STALE)
    if market_age < -tolerance.future_tolerance_seconds:
        _append_unique(codes, PlanCancellationCode.MARKET_EVIDENCE_FUTURE)

    friction_age = _age_seconds(as_of=observation.friction_as_of, now=reviewed_at)
    if friction_age > tolerance.friction_max_age_seconds:
        _append_unique(codes, PlanCancellationCode.FRICTION_EVIDENCE_STALE)
    if friction_age < -tolerance.future_tolerance_seconds:
        _append_unique(codes, PlanCancellationCode.FRICTION_EVIDENCE_FUTURE)

    clean_drift = _drift_bps(
        observation.clean_unit_price_base,
        baseline.clean_unit_price_base,
    )
    if clean_drift > tolerance.max_clean_price_drift_bps:
        _append_unique(codes, PlanCancellationCode.CLEAN_PRICE_DRIFT_EXCEEDED)

    baseline_aci = baseline.accrued_interest_per_lot_base
    observed_aci = observation.accrued_interest_per_lot_base
    aci_drift: Decimal | None = None
    if baseline_aci is not None:
        if observed_aci is None:
            _append_unique(codes, PlanCancellationCode.MARKET_EVIDENCE_MISSING)
        else:
            clean_lot = baseline.clean_unit_price_base * Decimal(baseline.lot_size)
            aci_drift = (
                abs(observed_aci - baseline_aci)
                / clean_lot
                * Decimal("10000")
            )
            if aci_drift > tolerance.max_accrued_interest_drift_bps:
                _append_unique(
                    codes,
                    PlanCancellationCode.ACCRUED_INTEREST_DRIFT_EXCEEDED,
                )
    elif observed_aci is not None:
        _append_unique(codes, PlanCancellationCode.ACCRUED_INTEREST_DRIFT_EXCEEDED)

    spread_widening = max(
        observation.spread_bps - baseline.spread_bps,
        Decimal("0"),
    )
    if spread_widening > tolerance.max_spread_widening_bps:
        _append_unique(codes, PlanCancellationCode.SPREAD_DRIFT_EXCEEDED)

    turnover_ratio_raw = (
        observation.average_daily_turnover_base
        / baseline.average_daily_turnover_base
    )
    turnover_ratio = min(turnover_ratio_raw, Decimal("1"))
    if turnover_ratio_raw < tolerance.minimum_turnover_ratio:
        _append_unique(codes, PlanCancellationCode.TURNOVER_CAPACITY_DROPPED)

    depth_ratio_raw = (
        observation.top_of_book_depth_base / baseline.top_of_book_depth_base
    )
    depth_ratio = min(depth_ratio_raw, Decimal("1"))
    if depth_ratio_raw < tolerance.minimum_top_of_book_depth_ratio:
        _append_unique(codes, PlanCancellationCode.TOP_OF_BOOK_DEPTH_DROPPED)

    if (
        observation.friction_source_sha256s != baseline.friction_source_sha256s
        or observation.commission_bps != baseline.commission_bps
        or observation.estimated_sell_tax_bps != baseline.estimated_sell_tax_bps
    ):
        _append_unique(codes, PlanCancellationCode.FRICTION_CHANGED)

    if action is PortfolioPlanAction.BUY and observation.account_eligible is not True:
        _append_unique(codes, PlanCancellationCode.ACCOUNT_ELIGIBILITY_CHANGED)

    fx_drift: Decimal | None = None
    if baseline.fx_rate_to_base is not None:
        if observation.fx_rate_to_base is None or observation.fx_as_of is None:
            _append_unique(codes, PlanCancellationCode.FX_DRIFT_EXCEEDED)
        else:
            fx_age = _age_seconds(as_of=observation.fx_as_of, now=reviewed_at)
            if fx_age > tolerance.fx_max_age_seconds:
                _append_unique(codes, PlanCancellationCode.FX_EVIDENCE_STALE)
            if fx_age < -tolerance.future_tolerance_seconds:
                _append_unique(codes, PlanCancellationCode.FX_EVIDENCE_FUTURE)
            fx_drift = _drift_bps(
                observation.fx_rate_to_base,
                baseline.fx_rate_to_base,
            )
            if fx_drift > tolerance.max_fx_drift_bps:
                _append_unique(codes, PlanCancellationCode.FX_DRIFT_EXCEEDED)
    elif observation.fx_rate_to_base is not None:
        _append_unique(codes, PlanCancellationCode.FX_DRIFT_EXCEEDED)

    return PlanMarketDriftResultV1(
        stable_key=baseline.stable_key,
        clean_price_drift_bps=clean_drift,
        accrued_interest_drift_bps=aci_drift,
        spread_widening_bps=spread_widening,
        turnover_ratio=turnover_ratio,
        top_of_book_depth_ratio=depth_ratio,
        fx_drift_bps=fx_drift,
        cancellation_codes=tuple(
            sorted(set(codes), key=lambda item: item.value)
        ),
    )


def _canonical_plan_for_review(plan: PortfolioPlanV1) -> PortfolioPlanV1:
    try:
        return PortfolioPlanV1.model_validate(plan.model_dump(mode="python"))
    except (AttributeError, ValidationError) as exc:
        raise PortfolioPlanError("PLAN_OBJECT_TAMPERED") from exc


def review_portfolio_plan(
    *,
    plan: PortfolioPlanV1,
    review_input: PortfolioPlanReviewInputV1,
) -> PortfolioPlanReviewV1:
    """Review exact plan identity and market drift without execution authority."""
    plan = _canonical_plan_for_review(plan)
    reviewed_at = review_input.reviewed_at
    codes: list[PlanCancellationCode] = []
    if reviewed_at < plan.created_at:
        codes.append(PlanCancellationCode.PLAN_NOT_YET_VALID)
    expired = reviewed_at >= plan.expires_at
    if expired:
        _append_unique(codes, PlanCancellationCode.PLAN_EXPIRED)
    if review_input.portfolio_snapshot_sha256 != plan.portfolio_snapshot_sha256:
        _append_unique(codes, PlanCancellationCode.PORTFOLIO_CHANGED)
    if review_input.policy_reference != plan.policy_reference:
        _append_unique(codes, PlanCancellationCode.POLICY_CHANGED)
    if (
        review_input.current_risk_assessment_sha256
        != plan.current_risk_assessment_sha256
    ):
        _append_unique(codes, PlanCancellationCode.CURRENT_RISK_CHANGED)
    if review_input.strategy_selection_sha256 != plan.strategy_selection_sha256:
        _append_unique(codes, PlanCancellationCode.STRATEGY_CHANGED)
    if review_input.optimizer_sha256 != plan.optimizer_sha256:
        _append_unique(codes, PlanCancellationCode.OPTIMIZER_CHANGED)
    if (
        review_input.target_risk_assessment_sha256
        != plan.target_risk_assessment_sha256
    ):
        _append_unique(codes, PlanCancellationCode.TARGET_RISK_CHANGED)

    observations = {
        row.stable_key: row for row in review_input.market_observations
    }
    baseline_keys = {row.stable_key for row in plan.market_baselines}
    if not set(observations).issubset(baseline_keys):
        raise PortfolioPlanError("PLAN_REVIEW_OBSERVATION_SET_MISMATCH")
    action_by_key = {
        row.optimizer_leg.stable_key: row.action
        for row in plan.legs
        if row.optimizer_leg is not None
    }
    drifts = tuple(
        _market_drift(
            baseline=baseline,
            observation=observations.get(baseline.stable_key),
            action=action_by_key[baseline.stable_key],
            reviewed_at=reviewed_at,
            plan=plan,
        )
        for baseline in plan.market_baselines
    )
    for drift in drifts:
        for code in drift.cancellation_codes:
            _append_unique(codes, code)

    canonical_codes = tuple(
        sorted(set(codes), key=lambda item: item.value)
    )
    valid = not canonical_codes
    status = (
        PlanReviewStatus.EXPIRED
        if expired
        else PlanReviewStatus.VALID
        if valid
        else PlanReviewStatus.CANCELLED
    )
    expected_phrase = (
        plan.owner_approval_phrase
        if valid and plan.approval_required
        else None
    )
    values = {
        "schema_version": "1.0",
        "reviewed_at": reviewed_at,
        "plan_sha256": plan.plan_sha256,
        "status": status,
        "expired": expired,
        "drift_results": drifts,
        "cancellation_codes": canonical_codes,
        "plan_valid": valid,
        "expected_owner_approval_phrase": expected_phrase,
        "execution_authorized": False,
        "review_sha256": "0" * 64,
        "trading_methods": False,
    }
    provisional = PortfolioPlanReviewV1.model_construct(**values)
    values["review_sha256"] = portfolio_plan_review_sha256(provisional)
    return PortfolioPlanReviewV1.model_validate(values)
