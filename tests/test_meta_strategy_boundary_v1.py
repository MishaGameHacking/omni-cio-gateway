from __future__ import annotations

import inspect

from omni_cio.contracts.v1.meta_strategy import (
    MetaStrategySelectionV1,
    StrategyComparisonV1,
)
from omni_cio.strategy.selector_v1 import select_meta_strategy
from scripts.check_strategy_boundary import main as check_strategy_boundary


FORBIDDEN_FIELDS = {
    "expected_return",
    "expected_alpha",
    "alpha",
    "forecast_return",
    "target_return",
    "predicted_return",
    "macro_regime_forecast",
}


def test_strategy_repository_boundary_guard_passes() -> None:
    assert check_strategy_boundary() == 0


def test_strategy_contract_has_no_return_forecast_or_execution_authority_fields() -> None:
    comparison_fields = set(StrategyComparisonV1.model_fields)
    selection_fields = set(MetaStrategySelectionV1.model_fields)

    assert not (comparison_fields & FORBIDDEN_FIELDS)
    assert not (selection_fields & FORBIDDEN_FIELDS)
    assert MetaStrategySelectionV1.model_fields["trading_methods"].default is False


def test_selector_has_no_broker_or_order_parameters() -> None:
    parameter_names = set(inspect.signature(select_meta_strategy).parameters)
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
