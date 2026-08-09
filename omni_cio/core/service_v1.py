from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from omni_cio.contracts.v1.investment_policy import (
    InvestmentPolicyAssessmentV1,
    InvestmentPolicyStatementV1,
)
from omni_cio.contracts.v1.meta_strategy import (
    MetaStrategySelectionV1,
    MetaStrategySettingsV1,
    StrategyFrictionEvidenceV1,
)
from omni_cio.contracts.v1.portfolio_optimizer import (
    OptimizerAssetV1,
    PortfolioOptimizerResultV1,
    PortfolioOptimizerSettingsV1,
)
from omni_cio.contracts.v1.portfolio_plan import (
    PortfolioPlanSettingsV1,
    PortfolioPlanV1,
)
from omni_cio.contracts.v1.portfolio_risk import (
    MacroRiskAssumptionsV1,
    PortfolioRiskAssessmentV1,
    PortfolioRiskInputV1,
    RiskEngineSettingsV1,
    StressScenarioDefinitionV1,
)
from omni_cio.optimizer import optimize_portfolio
from omni_cio.plans import build_portfolio_plan
from omni_cio.policy import assess_investment_policy
from omni_cio.risk import DEFAULT_STRESS_SCENARIOS, assess_portfolio_risk
from omni_cio.strategy import select_meta_strategy


@dataclass(frozen=True, slots=True)
class CorePlanRequestV1:
    """Stable WP11 orchestration input built from accepted V9 contracts.

    WP11 intentionally reuses the existing versioned financial DTOs instead of
    introducing the future WP12 canonical domain model. ``evaluated_at`` is
    explicit so golden parity and later callers can reproduce one deterministic
    decision snapshot without relying on a presentation-layer clock.
    """

    portfolio: PortfolioRiskInputV1
    policy: InvestmentPolicyStatementV1
    assets: tuple[OptimizerAssetV1, ...]
    friction_evidence: tuple[StrategyFrictionEvidenceV1, ...]
    evaluated_at: datetime
    risk_settings: RiskEngineSettingsV1 | None = None
    strategy_settings: MetaStrategySettingsV1 | None = None
    optimizer_settings: PortfolioOptimizerSettingsV1 | None = None
    plan_settings: PortfolioPlanSettingsV1 | None = None
    stress_scenarios: tuple[StressScenarioDefinitionV1, ...] | None = None
    macro: MacroRiskAssumptionsV1 | None = None


@dataclass(frozen=True, slots=True)
class CorePlanResultV1:
    """Deterministic Core outputs for the WP11 no-GPT planning path."""

    policy_assessment: InvestmentPolicyAssessmentV1
    risk: PortfolioRiskAssessmentV1
    strategy: MetaStrategySelectionV1
    optimizer: PortfolioOptimizerResultV1
    plan: PortfolioPlanV1


def run_core_plan_pipeline(request: CorePlanRequestV1) -> CorePlanResultV1:
    """Run policy -> portfolio risk -> strategy -> optimizer -> plan.

    The function is a narrow adapter over accepted V9 deterministic engines.
    It performs no broker writes, imports no presentation/GPT layer, and grants
    no execution authority. Existing engine contracts remain the financial
    semantics authority while WP11 establishes a stable Core entry point.
    """

    scenarios = (
        DEFAULT_STRESS_SCENARIOS
        if request.stress_scenarios is None
        else request.stress_scenarios
    )
    policy_assessment = assess_investment_policy(
        request.policy,
        assessed_at=request.evaluated_at,
    )
    risk = assess_portfolio_risk(
        portfolio=request.portfolio,
        policy=request.policy,
        policy_assessment=policy_assessment,
        settings=request.risk_settings,
        stress_scenarios=scenarios,
        macro=request.macro,
        assessed_at=request.evaluated_at,
    )
    strategy = select_meta_strategy(
        portfolio_snapshot_sha256=request.portfolio.portfolio_snapshot_sha256,
        policy=request.policy,
        policy_assessment=policy_assessment,
        risk=risk,
        friction_evidence=request.friction_evidence,
        settings=request.strategy_settings,
        selected_at=request.evaluated_at,
    )
    optimizer = optimize_portfolio(
        portfolio=request.portfolio,
        policy=request.policy,
        policy_assessment=policy_assessment,
        current_risk=risk,
        strategy=strategy,
        assets=request.assets,
        settings=request.optimizer_settings,
        risk_settings=request.risk_settings,
        stress_scenarios=scenarios,
        macro=request.macro,
        optimized_at=request.evaluated_at,
    )
    plan = build_portfolio_plan(
        portfolio=request.portfolio,
        policy=request.policy,
        policy_assessment=policy_assessment,
        current_risk=risk,
        strategy=strategy,
        optimizer=optimizer,
        optimizer_assets=request.assets,
        settings=request.plan_settings,
        created_at=request.evaluated_at,
    )
    return CorePlanResultV1(
        policy_assessment=policy_assessment,
        risk=risk,
        strategy=strategy,
        optimizer=optimizer,
        plan=plan,
    )
