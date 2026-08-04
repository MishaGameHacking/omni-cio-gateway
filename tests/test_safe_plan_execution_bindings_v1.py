from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any, cast

import pytest

from omni_cio.contracts.v1.plan_execution import (
    PlanExecutionAdvanceAction,
    PlanExecutionCurrentStateV1,
    PlanExecutionHaltCode,
)
from omni_cio.plan_execution import (
    InMemoryPlanExecutionJournalV1,
    SafePlanExecutionServiceV1,
)
from omni_cio.plan_execution.adapter_v1 import SingleOrderExecutionPrimitiveV1
from omni_cio.real_trading.models_v1 import RealTradingPolicyV1
from tests.v9_execution_fixture import (
    NOW,
    build_execution_fixture,
    execution_binding,
    execution_evidence,
    execution_state,
)


def _service_with_state_drift(field: str):
    fixture = build_execution_fixture()
    drift_enabled = False

    def state_provider(_plan, now):
        state = execution_state(fixture, observed_at=now)
        if not drift_enabled:
            return state
        payload = state.model_dump(mode="python")
        payload[field] = "f" * 64
        return PlanExecutionCurrentStateV1.model_validate(payload)

    service = SafePlanExecutionServiceV1(
        single_order=cast(SingleOrderExecutionPrimitiveV1, cast(Any, object())),
        real_policy=RealTradingPolicyV1(
            max_order_rub=Decimal("100000"),
            max_daily_rub=Decimal("300000"),
            confirmation_ttl_seconds=300,
            market_max_age_seconds=30,
        ),
        journal=InMemoryPlanExecutionJournalV1(),
        instrument_binding_provider=lambda _key, now: execution_binding(
            fixture,
            as_of=now,
        ),
        current_state_provider=state_provider,
        leg_evidence_provider=lambda _baseline, binding, now: execution_evidence(
            fixture,
            binding,
            observed_at=now,
        ),
        require_durable_journal=False,
    )
    session = service.prepare_plan(
        plan=fixture.plan,
        now=NOW + timedelta(minutes=1),
    )
    assert fixture.plan.owner_approval_phrase is not None
    service.approve_plan(
        execution_id=session.execution_id,
        plan=fixture.plan,
        owner_approval_phrase=fixture.plan.owner_approval_phrase,
        now=NOW + timedelta(minutes=2),
    )
    drift_enabled = True
    return fixture, service, session.execution_id


@pytest.mark.parametrize(
    "field",
    [
        "strategy_selection_sha256",
        "optimizer_sha256",
        "target_risk_assessment_sha256",
    ],
)
def test_upstream_identity_drift_halts_before_stage_prepare(field: str) -> None:
    fixture, service, execution_id = _service_with_state_drift(field)

    result = service.advance_execution(
        execution_id=execution_id,
        plan=fixture.plan,
        now=NOW + timedelta(minutes=3),
    )

    assert result.action is PlanExecutionAdvanceAction.HALTED
    assert result.session.halt_code is PlanExecutionHaltCode.PLAN_INVALID


@pytest.mark.parametrize(
    ("field", "expected_halt"),
    [
        ("portfolio_snapshot_sha256", PlanExecutionHaltCode.PORTFOLIO_PROGRESS_MISMATCH),
        ("risk_assessment_sha256", PlanExecutionHaltCode.CURRENT_RISK_NOT_READY),
    ],
)
def test_pre_first_fill_snapshot_or_risk_binding_drift_halts(
    field: str,
    expected_halt: PlanExecutionHaltCode,
) -> None:
    fixture, service, execution_id = _service_with_state_drift(field)

    result = service.advance_execution(
        execution_id=execution_id,
        plan=fixture.plan,
        now=NOW + timedelta(minutes=3),
    )

    assert result.action is PlanExecutionAdvanceAction.HALTED
    assert result.session.halt_code is expected_halt
