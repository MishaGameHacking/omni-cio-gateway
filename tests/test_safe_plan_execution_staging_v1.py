from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any, cast

from omni_cio.contracts.v1.plan_execution import (
    PlanExecutionAdvanceAction,
    PlanExecutionInstrumentBindingV1,
    PlanExecutionInstrumentStateV1,
    PlanExecutionSessionState,
    PlanExecutionSessionV1,
    PlanExecutionSide,
    PlanExecutionStageState,
    PlanExecutionStageV1,
)
from omni_cio.plan_execution import (
    InMemoryPlanExecutionJournalV1,
    SafePlanExecutionServiceV1,
)
from omni_cio.plan_execution.adapter_v1 import SingleOrderExecutionPrimitiveV1
from omni_cio.real_trading.models_v1 import RealTradingPolicyV1
from tests.v9_execution_fixture import NOW, build_execution_fixture, execution_binding


def _service() -> SafePlanExecutionServiceV1:
    return SafePlanExecutionServiceV1(
        single_order=cast(SingleOrderExecutionPrimitiveV1, cast(Any, object())),
        real_policy=RealTradingPolicyV1(
            max_order_rub=Decimal("100000"),
            max_daily_rub=Decimal("300000"),
            confirmation_ttl_seconds=300,
            market_max_age_seconds=30,
        ),
        journal=InMemoryPlanExecutionJournalV1(),
        instrument_binding_provider=lambda *_: (_ for _ in ()).throw(AssertionError()),
        current_state_provider=lambda *_: (_ for _ in ()).throw(AssertionError()),
        leg_evidence_provider=lambda *_: (_ for _ in ()).throw(AssertionError()),
        require_durable_journal=False,
    )


def test_second_slice_for_same_instrument_is_blocked_on_same_moscow_day() -> None:
    fixture = build_execution_fixture()
    binding = execution_binding(fixture, as_of=NOW + timedelta(minutes=1))
    moscow_day = (NOW + timedelta(hours=3)).date()

    prior_stage = PlanExecutionStageV1(
        stage_id="3" * 64,
        leg_sequence=1,
        stable_key=binding.stable_key,
        side=PlanExecutionSide.BUY,
        stage_index=1,
        stage_count=2,
        planned_lots=1,
        not_before_moscow_date=moscow_day,
        last_submission_moscow_date=moscow_day,
    )
    session = PlanExecutionSessionV1(
        execution_id="1" * 64,
        plan_sha256=fixture.plan.plan_sha256,
        initial_review_sha256="2" * 64,
        prepared_at=NOW,
        last_reviewed_at=NOW,
        last_review_sha256="2" * 64,
        state=PlanExecutionSessionState.PREPARED,
        instrument_states=(
            PlanExecutionInstrumentStateV1(
                binding=binding,
                stages=(prior_stage,),
            ),
        ),
    )
    next_stage = PlanExecutionStageV1(
        stage_id="4" * 64,
        leg_sequence=1,
        stable_key=binding.stable_key,
        side=PlanExecutionSide.BUY,
        stage_index=2,
        stage_count=2,
        planned_lots=1,
        not_before_moscow_date=moscow_day,
    )

    result = _service()._prepare_stage(  # noqa: SLF001 - explicit WP12 invariant test
        fixture.plan,
        session,
        next_stage,
        NOW + timedelta(minutes=5),
    )

    assert result.action is PlanExecutionAdvanceAction.WAITING_NEXT_STAGE_DAY
    assert result.session == session


def test_next_stage_advances_by_tranche_then_preserves_leg_sequence() -> None:
    fixture = build_execution_fixture()
    binding_one = execution_binding(fixture, as_of=NOW + timedelta(minutes=1))
    binding_two = PlanExecutionInstrumentBindingV1.model_validate(
        binding_one.model_copy(
            update={
                "stable_key": "share:SECOND-1",
                "instrument_uid": "uid-share-second-0001",
                "ticker": "SECOND",
                "isin": "RU000A000002",
                "source_sha256": "e" * 64,
            }
        ).model_dump(mode="python")
    )
    moscow_day = (NOW + timedelta(hours=3)).date()
    first_leg_first_slice = PlanExecutionStageV1(
        stage_id="5" * 64,
        leg_sequence=1,
        stable_key=binding_one.stable_key,
        side=PlanExecutionSide.BUY,
        stage_index=1,
        stage_count=2,
        planned_lots=1,
        broker_terminal_lots=1,
        portfolio_reconciled_lots=1,
        state=PlanExecutionStageState.FILLED,
        not_before_moscow_date=moscow_day,
    )
    first_leg_second_slice = PlanExecutionStageV1(
        stage_id="6" * 64,
        leg_sequence=1,
        stable_key=binding_one.stable_key,
        side=PlanExecutionSide.BUY,
        stage_index=2,
        stage_count=2,
        planned_lots=1,
        not_before_moscow_date=moscow_day + timedelta(days=1),
    )
    second_leg_first_slice = PlanExecutionStageV1(
        stage_id="7" * 64,
        leg_sequence=2,
        stable_key=binding_two.stable_key,
        side=PlanExecutionSide.BUY,
        stage_index=1,
        stage_count=2,
        planned_lots=1,
        not_before_moscow_date=moscow_day,
    )
    second_leg_second_slice = PlanExecutionStageV1(
        stage_id="8" * 64,
        leg_sequence=2,
        stable_key=binding_two.stable_key,
        side=PlanExecutionSide.BUY,
        stage_index=2,
        stage_count=2,
        planned_lots=1,
        not_before_moscow_date=moscow_day + timedelta(days=1),
    )
    session = PlanExecutionSessionV1(
        execution_id="9" * 64,
        plan_sha256=fixture.plan.plan_sha256,
        initial_review_sha256="a" * 64,
        prepared_at=NOW,
        last_reviewed_at=NOW,
        last_review_sha256="a" * 64,
        state=PlanExecutionSessionState.ACTIVE,
        instrument_states=(
            PlanExecutionInstrumentStateV1(
                binding=binding_one,
                stages=(first_leg_first_slice, first_leg_second_slice),
            ),
            PlanExecutionInstrumentStateV1(
                binding=binding_two,
                stages=(second_leg_first_slice, second_leg_second_slice),
            ),
        ),
    )

    selected = SafePlanExecutionServiceV1._next_execution_stage(session)  # noqa: SLF001

    assert selected is not None
    assert selected.stage_id == second_leg_first_slice.stage_id
