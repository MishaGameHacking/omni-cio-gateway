from __future__ import annotations

from typing import Literal

from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.portfolio_optimizer import PortfolioOptimizerResultV1
from omni_cio.contracts.v1.portfolio_plan import PortfolioPlanV1
from omni_cio.contracts.v1.portfolio_risk import PortfolioRiskAssessmentV1


class CorePlanningResultV1(ContractModel):
    """Presentation-independent aggregate of the accepted V9 planning chain."""

    schema_version: Literal["1.0"] = "1.0"
    current_risk: PortfolioRiskAssessmentV1
    optimizer: PortfolioOptimizerResultV1
    plan: PortfolioPlanV1
