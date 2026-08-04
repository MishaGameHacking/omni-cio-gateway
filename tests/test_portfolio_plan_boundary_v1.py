from __future__ import annotations

import inspect

from omni_cio.contracts.v1.portfolio_plan import (
    PortfolioPlanReviewV1,
    PortfolioPlanV1,
)
from omni_cio.plans.protocol_v1 import build_portfolio_plan, review_portfolio_plan
from scripts.check_plan_boundary import main as check_plan_boundary


FORBIDDEN_PARAMETERS = {
    "broker",
    "client",
    "token",
    "journal",
    "order",
    "orders",
    "request_id",
    "confirmation",
    "confirmation_code",
    "submit",
    "execute",
    "replace",
    "cancel",
}


def test_portfolio_plan_repository_boundary_guard_passes() -> None:
    assert check_plan_boundary() == 0


def test_portfolio_plan_contract_hard_codes_no_execution_authority() -> None:
    assert PortfolioPlanV1.model_fields["execution_authorized"].default is False
    assert PortfolioPlanV1.model_fields["trading_methods"].default is False
    assert PortfolioPlanReviewV1.model_fields["execution_authorized"].default is False
    assert PortfolioPlanReviewV1.model_fields["trading_methods"].default is False


def test_plan_builder_and_reviewer_have_no_broker_mutation_parameters() -> None:
    build_parameters = set(inspect.signature(build_portfolio_plan).parameters)
    review_parameters = set(inspect.signature(review_portfolio_plan).parameters)

    assert not build_parameters & FORBIDDEN_PARAMETERS
    assert not review_parameters & FORBIDDEN_PARAMETERS


def test_plan_contract_has_no_broker_execution_state_fields() -> None:
    plan_fields = set(PortfolioPlanV1.model_fields)
    review_fields = set(PortfolioPlanReviewV1.model_fields)
    forbidden_fields = {
        "broker_order_id",
        "order_id",
        "submission_id",
        "submitted_at",
        "filled_at",
        "fill_price",
        "broker_response",
        "confirmation_code",
    }

    assert not plan_fields & forbidden_fields
    assert not review_fields & forbidden_fields
