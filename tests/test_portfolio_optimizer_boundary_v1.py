from __future__ import annotations

import inspect

from omni_cio.contracts.v1.portfolio_optimizer import (
    OptimizerRebalanceLegV1,
    OptimizerScenarioV1,
    PortfolioOptimizerResultV1,
)
from omni_cio.optimizer.engine_v1 import optimize_portfolio
from scripts.check_optimizer_boundary import main as check_optimizer_boundary


FORBIDDEN_FIELDS = {
    "expected_return",
    "expected_alpha",
    "alpha",
    "forecast_return",
    "target_return",
    "predicted_return",
    "macro_regime_forecast",
    "execution_authorized",
    "order_created",
}


def test_optimizer_repository_boundary_guard_passes() -> None:
    assert check_optimizer_boundary() == 0


def test_optimizer_contract_has_no_forecast_or_execution_authority_fields() -> None:
    result_fields = set(PortfolioOptimizerResultV1.model_fields)
    leg_fields = set(OptimizerRebalanceLegV1.model_fields)
    scenario_fields = set(OptimizerScenarioV1.model_fields)

    assert not (result_fields & FORBIDDEN_FIELDS)
    assert not (leg_fields & FORBIDDEN_FIELDS)
    assert not (scenario_fields & FORBIDDEN_FIELDS)
    assert PortfolioOptimizerResultV1.model_fields["trading_methods"].default is False


def test_optimizer_has_no_broker_or_order_parameters() -> None:
    parameter_names = set(inspect.signature(optimize_portfolio).parameters)
    assert not parameter_names & {
        "broker",
        "client",
        "token",
        "order",
        "orders",
        "request_id",
        "confirmation",
        "execution_authorized",
    }
