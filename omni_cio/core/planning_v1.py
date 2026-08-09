from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from omni_cio.contracts.v1.core_planning import CorePlanningResultV1
from omni_cio.contracts.v1.investment_policy import (
    InvestmentPolicyAssessmentV1,
    InvestmentPolicyStatementV1,
)
from omni_cio.contracts.v1.meta_strategy import MetaStrategySelectionV1
from omni_cio.contracts.v1.portfolio_optimizer import OptimizerAssetV1
from omni_cio.contracts.v1.portfolio_risk import PortfolioRiskInputV1
from omni_cio.optimizer import optimize_portfolio
from omni_cio.plans import build_portfolio_plan
from omni_cio.risk import assess_portfolio_risk


def compile_portfolio_plan(
    *,
    portfolio: PortfolioRiskInputV1,
    policy: InvestmentPolicyStatementV1,
    policy_assessment: InvestmentPolicyAssessmentV1,
    strategy: MetaStrategySelectionV1,
    optimizer_assets: Iterable[OptimizerAssetV1],
    evaluated_at: datetime,
) -> CorePlanningResultV1:
    """Run the accepted V9 risk -> optimizer -> plan chain without presentation code.

    The facade owns composition only. Financial calculations remain in the existing
    versioned V9 engines and contracts so direct legacy imports stay valid during
    parity validation.
    """

    assets = tuple(optimizer_assets)
    current_risk = assess_portfolio_risk(
        portfolio=portfolio,
        policy=policy,
        policy_assessment=policy_assessment,
        assessed_at=evaluated_at,
    )
    optimizer = optimize_portfolio(
        portfolio=portfolio,
        policy=policy,
        policy_assessment=policy_assessment,
        current_risk=current_risk,
        strategy=strategy,
        assets=assets,
        optimized_at=evaluated_at,
    )
    plan = build_portfolio_plan(
        portfolio=portfolio,
        policy=policy,
        policy_assessment=policy_assessment,
        current_risk=current_risk,
        strategy=strategy,
        optimizer=optimizer,
        optimizer_assets=assets,
        created_at=evaluated_at,
    )
    return CorePlanningResultV1(
        current_risk=current_risk,
        optimizer=optimizer,
        plan=plan,
    )
