from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

from omni_cio.contracts.v1.meta_strategy import (
    StrategyFrictionEvidenceV1,
    StrategyRegime,
)
from omni_cio.contracts.v1.plan_execution import (
    PlanExecutionCurrentStateV1,
    PlanExecutionInstrumentBindingV1,
    PlanExecutionLegEvidenceV1,
    PlanExecutionPositionV1,
    PlanExecutionQuoteV1,
)
from omni_cio.contracts.v1.portfolio_optimizer import OptimizerAssetV1
from omni_cio.contracts.v1.portfolio_plan import PlanMarketObservationV1, PortfolioPlanV1
from omni_cio.contracts.v1.portfolio_risk import (
    PortfolioRiskAssessmentV1,
    PortfolioRiskInputV1,
    RiskPositionV1,
)
from omni_cio.optimizer import optimize_portfolio
from omni_cio.plans import build_portfolio_plan
from omni_cio.risk import assess_portfolio_risk
from omni_cio.strategy import select_meta_strategy
from tests.v9_plan_fixture import NOW, build_fixture


EXECUTION_SNAPSHOT_SHA = "7" * 64
BINDING_SHA = "8" * 64
QUOTE_SHA = "9" * 64
STATE_SOURCE_SHA = "a" * 64


@dataclass(frozen=True)
class ExecutionFixture:
    plan: PortfolioPlanV1
    portfolio: PortfolioRiskInputV1
    risk: PortfolioRiskAssessmentV1
    assets: tuple[OptimizerAssetV1, ...]


def _position_value(position: RiskPositionV1, value: Decimal) -> RiskPositionV1:
    return RiskPositionV1.model_validate(
        position.model_copy(
            update={
                "native_market_value": value,
                "base_market_value": value,
            }
        ).model_dump(mode="python")
    )


def build_execution_fixture() -> ExecutionFixture:
    """Build a complete WP2→WP8→WP9→WP10→WP11 share BUY plan."""

    seed = build_fixture()
    bond_seed = next(
        row for row in seed.portfolio.positions if row.stable_key == "bond:QUALITY-1"
    )
    share_seed = next(
        row for row in seed.portfolio.positions if row.stable_key == "share:CORE-1"
    )
    bond = _position_value(bond_seed, Decimal("450000"))
    share = _position_value(share_seed, Decimal("300000"))

    portfolio = PortfolioRiskInputV1(
        portfolio_snapshot_sha256=EXECUTION_SNAPSHOT_SHA,
        policy_reference=seed.assessment.reference,
        base_currency="RUB",
        cash_base=Decimal("250000"),
        positions=(bond, share),
    )
    risk = assess_portfolio_risk(
        portfolio=portfolio,
        policy=seed.policy,
        policy_assessment=seed.assessment,
        assessed_at=NOW,
    )
    assert risk.plan_eligible

    friction = tuple(
        StrategyFrictionEvidenceV1(
            regime=regime,
            transition_cost_weight=Decimal("0.003"),
            tax_cost_weight=Decimal("0.001"),
            as_of=NOW,
            source_sha256s=(source,),
        )
        for regime, source in (
            (StrategyRegime.CAPITAL_PRESERVATION, "b" * 64),
            (StrategyRegime.DEFENSIVE_BALANCED, "c" * 64),
            (StrategyRegime.BALANCED_CORE, "d" * 64),
            (StrategyRegime.GROWTH_CORE, "e" * 64),
        )
    )
    strategy = select_meta_strategy(
        portfolio_snapshot_sha256=EXECUTION_SNAPSHOT_SHA,
        policy=seed.policy,
        policy_assessment=seed.assessment,
        risk=risk,
        friction_evidence=friction,
        selected_at=NOW,
    )
    assert strategy.selected_regime is StrategyRegime.DEFENSIVE_BALANCED

    bond_asset_seed = next(
        row for row in seed.assets if row.stable_key == "bond:QUALITY-1"
    )
    share_asset_seed = next(
        row for row in seed.assets if row.stable_key == "share:CORE-1"
    )
    bond_asset = OptimizerAssetV1.model_validate(
        bond_asset_seed.model_copy(
            update={"current_lots": 450, "risk_template": bond}
        ).model_dump(mode="python")
    )
    share_asset = OptimizerAssetV1.model_validate(
        share_asset_seed.model_copy(
            update={"current_lots": 3000, "risk_template": share}
        ).model_dump(mode="python")
    )
    assets = (bond_asset, share_asset)
    optimizer = optimize_portfolio(
        portfolio=portfolio,
        policy=seed.policy,
        policy_assessment=seed.assessment,
        current_risk=risk,
        strategy=strategy,
        assets=assets,
        optimized_at=NOW,
    )
    assert optimizer.plan_eligible
    assert len(optimizer.legs) == 1
    assert optimizer.legs[0].stable_key == "share:CORE-1"
    assert optimizer.legs[0].quantity_lots == 500

    plan = build_portfolio_plan(
        portfolio=portfolio,
        policy=seed.policy,
        policy_assessment=seed.assessment,
        current_risk=risk,
        strategy=strategy,
        optimizer=optimizer,
        optimizer_assets=assets,
        created_at=NOW,
    )
    assert plan.approval_required
    assert plan.owner_approval_phrase is not None
    return ExecutionFixture(plan=plan, portfolio=portfolio, risk=risk, assets=assets)


def execution_state(
    fixture: ExecutionFixture,
    *,
    observed_at: datetime,
    share_lots: int = 3000,
    cash_base: Decimal = Decimal("250000"),
    snapshot_sha256: str = EXECUTION_SNAPSHOT_SHA,
) -> PlanExecutionCurrentStateV1:
    plan = fixture.plan
    return PlanExecutionCurrentStateV1(
        observed_at=observed_at,
        portfolio_snapshot_sha256=snapshot_sha256,
        policy_reference=plan.policy_reference,
        cash_base=cash_base,
        positions=(
            PlanExecutionPositionV1(stable_key="bond:QUALITY-1", lots=450),
            PlanExecutionPositionV1(stable_key="share:CORE-1", lots=share_lots),
        ),
        risk_assessment_sha256=plan.current_risk_assessment_sha256,
        risk_decision_ready=True,
        risk_policy_compliant=True,
        strategy_selection_sha256=plan.strategy_selection_sha256,
        optimizer_sha256=plan.optimizer_sha256,
        target_risk_assessment_sha256=plan.target_risk_assessment_sha256,
        source_sha256s=(STATE_SOURCE_SHA,),
    )


def execution_binding(
    fixture: ExecutionFixture,
    *,
    as_of: datetime,
    instrument_type: Literal["share", "etf", "bond"] = "share",
) -> PlanExecutionInstrumentBindingV1:
    baseline = fixture.plan.market_baselines[0]
    return PlanExecutionInstrumentBindingV1(
        stable_key=baseline.stable_key,
        instrument_uid="uid-share-core-0001",
        ticker="CORE",
        isin="RU000A000001",
        instrument_type=instrument_type,
        lot_size=baseline.lot_size,
        source_sha256=BINDING_SHA,
        as_of=as_of,
    )


def execution_evidence(
    fixture: ExecutionFixture,
    binding: PlanExecutionInstrumentBindingV1,
    *,
    observed_at: datetime,
    best_bid: Decimal = Decimal("99.9"),
    best_ask: Decimal = Decimal("100.1"),
) -> PlanExecutionLegEvidenceV1:
    baseline = fixture.plan.market_baselines[0]
    observation = PlanMarketObservationV1(
        stable_key=baseline.stable_key,
        observed_at=observed_at,
        market_source_sha256=baseline.market_source_sha256,
        clean_unit_price_base=baseline.clean_unit_price_base,
        accrued_interest_per_lot_base=baseline.accrued_interest_per_lot_base,
        spread_bps=Decimal("20"),
        average_daily_turnover_base=baseline.average_daily_turnover_base,
        top_of_book_depth_base=baseline.top_of_book_depth_base,
        friction_as_of=baseline.friction_as_of,
        friction_source_sha256s=baseline.friction_source_sha256s,
        commission_bps=baseline.commission_bps,
        estimated_sell_tax_bps=baseline.estimated_sell_tax_bps,
        account_eligible=baseline.account_eligible,
        fx_rate_to_base=baseline.fx_rate_to_base,
        fx_source_sha256=baseline.fx_source_sha256,
        fx_as_of=baseline.fx_as_of,
    )
    quote = PlanExecutionQuoteV1(
        stable_key=baseline.stable_key,
        instrument_uid=binding.instrument_uid,
        as_of=observed_at,
        source_sha256=QUOTE_SHA,
        lot_size=baseline.lot_size,
        min_price_increment=Decimal("0.1"),
        best_bid=best_bid,
        best_ask=best_ask,
        spread_bps=Decimal("20"),
        average_daily_turnover_base=baseline.average_daily_turnover_base,
        top_of_book_depth_base=baseline.top_of_book_depth_base,
    )
    return PlanExecutionLegEvidenceV1(observation=observation, quote=quote)
