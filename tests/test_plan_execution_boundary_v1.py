from __future__ import annotations

import inspect

from omni_cio.contracts.v1.plan_execution import (
    PlanExecutionSessionV1,
    PlanExecutionSettingsV1,
)
from omni_cio.plan_execution.adapter_v1 import (
    RealTradingPlanAdapterV1,
    SingleOrderExecutionPrimitiveV1,
)
from omni_cio.plan_execution.service_v1 import SafePlanExecutionServiceV1
from scripts.check_plan_execution_boundary import main as check_plan_execution_boundary


def test_plan_execution_repository_boundary_guard_passes() -> None:
    assert check_plan_execution_boundary() == 0


def test_plan_execution_contract_hard_codes_forbidden_authority_off() -> None:
    session_fields = PlanExecutionSessionV1.model_fields
    settings_fields = PlanExecutionSettingsV1.model_fields

    assert session_fields["autonomous_execution"].default is False
    assert session_fields["margin_allowed"].default is False
    assert session_fields["short_allowed"].default is False
    assert session_fields["withdrawal_allowed"].default is False
    assert session_fields["transfer_allowed"].default is False
    assert settings_fields["autonomous_recurring_execution"].default is False


def test_wp12_public_service_has_no_free_form_order_or_forbidden_mutation_api() -> None:
    methods = {
        name
        for name, value in inspect.getmembers(SafePlanExecutionServiceV1, inspect.isfunction)
        if not name.startswith("_")
    }
    assert methods == {
        "prepare_plan",
        "approve_plan",
        "advance_execution",
        "status",
    }
    assert not methods & {
        "post_order",
        "submit_order",
        "cancel_order",
        "replace_order",
        "withdraw",
        "transfer",
        "margin_trade",
        "short_sell",
    }


def test_single_order_adapter_exposes_only_accepted_v861_lifecycle() -> None:
    adapter_methods = {
        name
        for name, value in inspect.getmembers(RealTradingPlanAdapterV1, inspect.isfunction)
        if not name.startswith("_")
    }
    protocol_methods = {
        name
        for name, value in inspect.getmembers(SingleOrderExecutionPrimitiveV1, inspect.isfunction)
        if not name.startswith("_")
    }
    expected = {
        "prepare_trade",
        "execute_trade",
        "reconcile_proposal",
        "get_proposal",
    }
    assert adapter_methods == expected
    assert protocol_methods == expected
