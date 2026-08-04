from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
import json
from typing import Literal, cast

import pytest

from omni_cio.contracts.v1.plan_execution import (
    BrokerExecutionStatus,
    PlanExecutionAdvanceAction,
    PlanExecutionCurrentStateV1,
    PlanExecutionHaltCode,
    PlanExecutionInstrumentBindingV1,
    PlanExecutionLegEvidenceV1,
    PlanExecutionSessionState,
    PlanExecutionStageState,
)
from omni_cio.contracts.v1.portfolio_optimizer import PortfolioOptimizerSettingsV1
from omni_cio.plan_execution import (
    InMemoryPlanExecutionJournalV1,
    SafePlanExecutionError,
    SafePlanExecutionServiceV1,
)
from omni_cio.real_trading.client_v1 import RealTradingApiFailure
from omni_cio.real_trading.models_v1 import RealTradeProposalV1, RealTradingPolicyV1
from tests.v9_execution_fixture import (
    NOW,
    ExecutionFixture,
    build_execution_fixture,
    execution_binding,
    execution_evidence,
    execution_state,
)
from tests.v9_plan_fixture import build_no_action_fixture


class FakeSingleOrderPrimitive:
    def __init__(self) -> None:
        self.prepare_calls = 0
        self.execute_calls = 0
        self.reconcile_calls = 0
        self.ambiguous_submit = False
        self.proposals: dict[str, RealTradeProposalV1] = {}
        self.broker_payloads: list[dict[str, object]] = []

    def prepare_trade(
        self,
        *,
        instrument_uid: str,
        direction: str,
        quantity_lots: int,
        limit_price: str,
        rationale: str,
        now: datetime | None = None,
    ) -> RealTradeProposalV1:
        assert now is not None
        assert direction in {"BUY", "SELL"}
        self.prepare_calls += 1
        direction_value = cast(Literal["BUY", "SELL"], direction)
        price = Decimal(limit_price)
        proposal = RealTradeProposalV1(
            proposal_id=f"proposal-wp12-{self.prepare_calls:04d}",
            order_id=f"request-wp12-{self.prepare_calls:04d}",
            account_id="masked-account",
            instrument_uid=instrument_uid,
            ticker="CORE",
            isin="RU000A000001",
            direction=direction_value,
            quantity_lots=quantity_lots,
            limit_price=price,
            rationale=rationale,
            preview_total_rub=price * Decimal(quantity_lots),
            preview_commission_rub=Decimal("0"),
            available_lots=10000,
            market_retrieved_at=now,
            created_at=now,
            expires_at=now + timedelta(minutes=5),
            confirmation_code=f"WP12{self.prepare_calls:04d}",
        )
        self.proposals[proposal.proposal_id] = proposal
        return proposal

    def execute_trade(
        self,
        proposal_id: str,
        confirmation_phrase: str,
        *,
        now: datetime | None = None,
    ) -> tuple[RealTradeProposalV1, bool]:
        assert now is not None
        proposal = self.proposals[proposal_id]
        assert confirmation_phrase == proposal.confirmation_phrase
        if self.ambiguous_submit:
            raise RealTradingApiFailure(
                code="REAL_ORDER_SUBMISSION_UNCERTAIN",
                message="fake ambiguous submit",
                ambiguous_submission=True,
            )
        self.execute_calls += 1
        submitted = replace(proposal, state="submitted", submitted_at=now)
        self.proposals[proposal_id] = submitted
        return submitted, False

    def reconcile_proposal(self, proposal_id: str) -> RealTradeProposalV1:
        self.reconcile_calls += 1
        if not self.broker_payloads:
            raise RealTradingApiFailure(
                code="FAKE_BROKER_STATE_PENDING",
                message="no fake broker state queued",
            )
        proposal = self.proposals[proposal_id]
        payload = self.broker_payloads.pop(0)
        reconciled = replace(
            proposal,
            state="submitted",
            broker_response_json=json.dumps(payload, separators=(",", ":"), sort_keys=True),
        )
        self.proposals[proposal_id] = reconciled
        return reconciled

    def get_proposal(self, proposal_id: str) -> RealTradeProposalV1:
        return self.proposals[proposal_id]

    def mark_submitted_without_executor(self, proposal_id: str, now: datetime) -> None:
        proposal = self.proposals[proposal_id]
        self.proposals[proposal_id] = replace(
            proposal,
            state="submitted",
            submitted_at=now,
        )


def _money(value: Decimal) -> dict[str, object]:
    units = int(value)
    nano = int((value - Decimal(units)) * Decimal("1000000000"))
    return {"currency": "RUB", "units": str(units), "nano": nano}


def _broker_payload(
    *,
    status: BrokerExecutionStatus,
    requested: int,
    executed: int,
    total: Decimal,
    commission: Decimal,
    price: Decimal = Decimal("100.1"),
) -> dict[str, object]:
    return {
        "executionReportStatus": status.value,
        "lotsRequested": requested,
        "lotsExecuted": executed,
        "totalOrderAmount": _money(total),
        "executedCommission": _money(commission),
        "executedOrderPrice": _money(price),
    }


class Harness:
    def __init__(
        self,
        fixture: ExecutionFixture,
        *,
        max_order_rub: Decimal = Decimal("100000"),
        require_durable_journal: bool = False,
    ) -> None:
        self.fixture = fixture
        self.primitive = FakeSingleOrderPrimitive()
        self.journal = InMemoryPlanExecutionJournalV1()
        self.share_lots = 3000
        self.cash = Decimal("250000")
        self.snapshot_sha = fixture.plan.portfolio_snapshot_sha256
        self.binding_changed = False

        def state_provider(_plan, now: datetime) -> PlanExecutionCurrentStateV1:
            return execution_state(
                fixture,
                observed_at=now,
                share_lots=self.share_lots,
                cash_base=self.cash,
                snapshot_sha256=self.snapshot_sha,
            )

        def binding_provider(
            _stable_key: str,
            now: datetime,
        ) -> PlanExecutionInstrumentBindingV1:
            binding = execution_binding(fixture, as_of=now)
            if not self.binding_changed:
                return binding
            return PlanExecutionInstrumentBindingV1.model_validate(
                binding.model_copy(
                    update={
                        "instrument_uid": "uid-share-core-changed",
                        "source_sha256": "f" * 64,
                    }
                ).model_dump(mode="python")
            )

        def evidence_provider(
            _baseline,
            binding: PlanExecutionInstrumentBindingV1,
            now: datetime,
        ) -> PlanExecutionLegEvidenceV1:
            return execution_evidence(fixture, binding, observed_at=now)

        self.service = SafePlanExecutionServiceV1(
            single_order=self.primitive,
            real_policy=RealTradingPolicyV1(
                max_order_rub=max_order_rub,
                max_daily_rub=Decimal("300000"),
                confirmation_ttl_seconds=300,
                market_max_age_seconds=30,
            ),
            journal=self.journal,
            instrument_binding_provider=binding_provider,
            current_state_provider=state_provider,
            leg_evidence_provider=evidence_provider,
            require_durable_journal=require_durable_journal,
        )

    def prepare_and_approve(self):
        plan = self.fixture.plan
        prepared = self.service.prepare_plan(plan=plan, now=NOW + timedelta(minutes=1))
        assert prepared.state is PlanExecutionSessionState.PREPARED
        assert self.primitive.prepare_calls == 0
        assert self.primitive.execute_calls == 0
        assert plan.owner_approval_phrase is not None
        approved = self.service.approve_plan(
            execution_id=prepared.execution_id,
            plan=plan,
            owner_approval_phrase=plan.owner_approval_phrase,
            now=NOW + timedelta(minutes=2),
        )
        assert approved.action is PlanExecutionAdvanceAction.APPROVED
        assert approved.session.owner_approved is True
        assert approved.execution_authorized is True
        assert self.primitive.prepare_calls == 0
        assert self.primitive.execute_calls == 0
        return approved.session


def test_complete_share_plan_uses_one_submit_and_independent_reconciliation() -> None:
    fixture = build_execution_fixture()
    harness = Harness(fixture)
    session = harness.prepare_and_approve()

    prepared = harness.service.advance_execution(
        execution_id=session.execution_id,
        plan=fixture.plan,
        now=NOW + timedelta(minutes=3),
    )
    assert prepared.action is PlanExecutionAdvanceAction.STAGE_PREPARED
    assert harness.primitive.prepare_calls == 1
    assert harness.primitive.execute_calls == 0
    stage = prepared.session.instrument_states[0].stages[0]
    assert stage.planned_lots == 500

    submitted = harness.service.advance_execution(
        execution_id=session.execution_id,
        plan=fixture.plan,
        now=NOW + timedelta(minutes=4),
    )
    assert submitted.action is PlanExecutionAdvanceAction.STAGE_SUBMITTED
    assert harness.primitive.execute_calls == 1

    harness.primitive.broker_payloads.extend(
        [
            _broker_payload(
                status=BrokerExecutionStatus.PARTIALLY_FILLED,
                requested=500,
                executed=200,
                total=Decimal("20040.02"),
                commission=Decimal("20.02"),
            ),
            _broker_payload(
                status=BrokerExecutionStatus.FILLED,
                requested=500,
                executed=500,
                total=Decimal("50100.05"),
                commission=Decimal("50.05"),
            ),
        ]
    )
    partial = harness.service.advance_execution(
        execution_id=session.execution_id,
        plan=fixture.plan,
        now=NOW + timedelta(minutes=5),
    )
    assert partial.action is PlanExecutionAdvanceAction.BROKER_ACTIVE
    assert partial.broker_snapshot is not None
    assert partial.broker_snapshot.lots_executed == 200
    assert harness.primitive.execute_calls == 1

    terminal = harness.service.advance_execution(
        execution_id=session.execution_id,
        plan=fixture.plan,
        now=NOW + timedelta(minutes=6),
    )
    assert terminal.action is PlanExecutionAdvanceAction.BROKER_TERMINAL
    assert terminal.session.confirmed_cash_delta_rub == Decimal("-50100.05")
    assert harness.primitive.execute_calls == 1

    harness.share_lots = 3500
    harness.cash = Decimal("199899.95")
    harness.snapshot_sha = "b" * 64
    completed = harness.service.advance_execution(
        execution_id=session.execution_id,
        plan=fixture.plan,
        now=NOW + timedelta(minutes=7),
    )
    assert completed.action is PlanExecutionAdvanceAction.COMPLETED
    assert completed.session.state is PlanExecutionSessionState.COMPLETED
    assert completed.execution_authorized is False
    assert harness.primitive.execute_calls == 1

    replay = harness.service.advance_execution(
        execution_id=session.execution_id,
        plan=fixture.plan,
        now=NOW + timedelta(minutes=8),
    )
    assert replay.action is PlanExecutionAdvanceAction.REPLAY
    assert harness.primitive.execute_calls == 1


def test_underlying_submitted_proposal_replays_without_second_submit() -> None:
    fixture = build_execution_fixture()
    harness = Harness(fixture)
    session = harness.prepare_and_approve()
    prepared = harness.service.advance_execution(
        execution_id=session.execution_id,
        plan=fixture.plan,
        now=NOW + timedelta(minutes=3),
    )
    assert prepared.proposal_id is not None
    harness.primitive.mark_submitted_without_executor(
        prepared.proposal_id,
        NOW + timedelta(minutes=3, seconds=30),
    )

    replay = harness.service.advance_execution(
        execution_id=session.execution_id,
        plan=fixture.plan,
        now=NOW + timedelta(minutes=4),
    )
    assert replay.action is PlanExecutionAdvanceAction.REPLAY
    assert replay.session.state is PlanExecutionSessionState.AWAITING_BROKER_RECONCILIATION
    assert harness.primitive.execute_calls == 0


def test_ambiguous_submit_halts_everything_and_recovers_only_by_reconciliation() -> None:
    fixture = build_execution_fixture()
    harness = Harness(fixture)
    session = harness.prepare_and_approve()
    harness.service.advance_execution(
        execution_id=session.execution_id,
        plan=fixture.plan,
        now=NOW + timedelta(minutes=3),
    )
    harness.primitive.ambiguous_submit = True

    halted = harness.service.advance_execution(
        execution_id=session.execution_id,
        plan=fixture.plan,
        now=NOW + timedelta(minutes=4),
    )
    assert halted.action is PlanExecutionAdvanceAction.HALTED
    assert halted.session.halt_code is PlanExecutionHaltCode.AMBIGUOUS_SUBMISSION
    assert harness.primitive.execute_calls == 0

    harness.primitive.ambiguous_submit = False
    harness.primitive.broker_payloads.append(
        _broker_payload(
            status=BrokerExecutionStatus.FILLED,
            requested=500,
            executed=500,
            total=Decimal("50100.05"),
            commission=Decimal("50.05"),
        )
    )
    recovered = harness.service.advance_execution(
        execution_id=session.execution_id,
        plan=fixture.plan,
        now=NOW + timedelta(minutes=5),
    )
    assert recovered.action is PlanExecutionAdvanceAction.BROKER_TERMINAL
    assert harness.primitive.execute_calls == 0
    assert harness.primitive.reconcile_calls == 1


def test_binding_drift_halts_before_single_order_prepare() -> None:
    fixture = build_execution_fixture()
    harness = Harness(fixture)
    session = harness.prepare_and_approve()
    harness.binding_changed = True

    halted = harness.service.advance_execution(
        execution_id=session.execution_id,
        plan=fixture.plan,
        now=NOW + timedelta(minutes=3),
    )
    assert halted.action is PlanExecutionAdvanceAction.HALTED
    assert halted.session.halt_code is PlanExecutionHaltCode.INSTRUMENT_BINDING_MISMATCH
    assert harness.primitive.prepare_calls == 0
    assert harness.primitive.execute_calls == 0


def test_expired_plan_blocks_new_submit_but_not_reconciliation_of_prior_submit() -> None:
    fixture = build_execution_fixture()
    harness = Harness(fixture)
    session = harness.prepare_and_approve()
    harness.service.advance_execution(
        execution_id=session.execution_id,
        plan=fixture.plan,
        now=NOW + timedelta(minutes=3),
    )

    expired = harness.service.advance_execution(
        execution_id=session.execution_id,
        plan=fixture.plan,
        now=fixture.plan.expires_at + timedelta(seconds=1),
    )
    assert expired.action is PlanExecutionAdvanceAction.HALTED
    assert expired.session.halt_code is PlanExecutionHaltCode.PLAN_EXPIRED
    assert harness.primitive.execute_calls == 0

    other = Harness(fixture)
    session2 = other.prepare_and_approve()
    other.service.advance_execution(
        execution_id=session2.execution_id,
        plan=fixture.plan,
        now=NOW + timedelta(minutes=3),
    )
    submitted = other.service.advance_execution(
        execution_id=session2.execution_id,
        plan=fixture.plan,
        now=NOW + timedelta(minutes=4),
    )
    assert submitted.action is PlanExecutionAdvanceAction.STAGE_SUBMITTED
    other.primitive.broker_payloads.append(
        _broker_payload(
            status=BrokerExecutionStatus.FILLED,
            requested=500,
            executed=500,
            total=Decimal("50100.05"),
            commission=Decimal("50.05"),
        )
    )
    after_expiry = other.service.advance_execution(
        execution_id=session2.execution_id,
        plan=fixture.plan,
        now=fixture.plan.expires_at + timedelta(seconds=1),
    )
    assert after_expiry.action is PlanExecutionAdvanceAction.BROKER_TERMINAL
    assert other.primitive.execute_calls == 1


def test_partial_cancel_records_fill_and_never_resubmits_same_day() -> None:
    fixture = build_execution_fixture()
    harness = Harness(fixture)
    session = harness.prepare_and_approve()
    harness.service.advance_execution(
        execution_id=session.execution_id,
        plan=fixture.plan,
        now=NOW + timedelta(minutes=3),
    )
    harness.service.advance_execution(
        execution_id=session.execution_id,
        plan=fixture.plan,
        now=NOW + timedelta(minutes=4),
    )
    harness.primitive.broker_payloads.append(
        _broker_payload(
            status=BrokerExecutionStatus.CANCELLED,
            requested=500,
            executed=200,
            total=Decimal("20040.02"),
            commission=Decimal("20.02"),
        )
    )
    terminal = harness.service.advance_execution(
        execution_id=session.execution_id,
        plan=fixture.plan,
        now=NOW + timedelta(minutes=5),
    )
    assert terminal.action is PlanExecutionAdvanceAction.BROKER_TERMINAL
    stage = terminal.session.instrument_states[0].stages[0]
    assert stage.broker_terminal_lots == 200
    assert stage.remaining_lots == 300

    harness.share_lots = 3200
    harness.cash = Decimal("229959.98")
    harness.snapshot_sha = "c" * 64
    reconciled = harness.service.advance_execution(
        execution_id=session.execution_id,
        plan=fixture.plan,
        now=NOW + timedelta(minutes=6),
    )
    assert reconciled.action is PlanExecutionAdvanceAction.PORTFOLIO_RECONCILED
    stage = reconciled.session.instrument_states[0].stages[0]
    assert stage.state is PlanExecutionStageState.PENDING
    assert stage.remaining_lots == 300

    same_day = harness.service.advance_execution(
        execution_id=session.execution_id,
        plan=fixture.plan,
        now=NOW + timedelta(minutes=7),
    )
    assert same_day.action is PlanExecutionAdvanceAction.WAITING_NEXT_STAGE_DAY
    assert harness.primitive.execute_calls == 1
    assert harness.primitive.prepare_calls == 1


def test_optimizer_staging_splits_plan_into_required_execution_days() -> None:
    fixture = build_execution_fixture(
        optimizer_settings=PortfolioOptimizerSettingsV1(
            maximum_daily_turnover_participation=Decimal("0.005"),
        )
    )
    harness = Harness(fixture)
    session = harness.service.prepare_plan(
        plan=fixture.plan,
        now=NOW + timedelta(minutes=1),
    )
    stages = session.instrument_states[0].stages
    assert len(stages) == 2
    assert tuple(row.planned_lots for row in stages) == (250, 250)
    assert sum(row.planned_lots for row in stages) == 500
    assert stages[1].not_before_moscow_date == stages[0].not_before_moscow_date + timedelta(days=1)


def test_real_order_cap_cannot_extend_immutable_plan_horizon() -> None:
    fixture = build_execution_fixture()
    harness = Harness(fixture, max_order_rub=Decimal("25000"))

    with pytest.raises(SafePlanExecutionError) as exc_info:
        harness.service.prepare_plan(
            plan=fixture.plan,
            now=NOW + timedelta(minutes=1),
        )

    assert exc_info.value.code == "PLAN_EXECUTION_PLAN_HORIZON_TOO_SHORT"
    assert harness.primitive.prepare_calls == 0
    assert harness.primitive.execute_calls == 0


def test_no_action_plan_never_creates_execution_session() -> None:
    fixture = build_no_action_fixture()
    primitive = FakeSingleOrderPrimitive()
    service = SafePlanExecutionServiceV1(
        single_order=primitive,
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
    with pytest.raises(SafePlanExecutionError) as exc_info:
        service.prepare_plan(plan=fixture.plan, now=NOW + timedelta(minutes=1))
    assert exc_info.value.code == "PLAN_EXECUTION_NO_ACTION"
    assert primitive.prepare_calls == 0
    assert primitive.execute_calls == 0


def test_real_execution_requires_durable_plan_journal_by_default() -> None:
    fixture = build_execution_fixture()
    with pytest.raises(SafePlanExecutionError) as exc_info:
        Harness(fixture, require_durable_journal=True)
    assert exc_info.value.code == "PLAN_EXECUTION_DURABLE_JOURNAL_REQUIRED"
