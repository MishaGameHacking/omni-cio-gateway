from __future__ import annotations

from datetime import datetime

from omni_cio.contracts.v1.plan_execution import (
    BrokerExecutionStatus,
    PlanExecutionAdvanceAction,
    PlanExecutionAdvanceResultV1,
    PlanExecutionAttemptState,
    PlanExecutionAttemptV1,
    PlanExecutionHaltCode,
    PlanExecutionSessionState,
    PlanExecutionSessionV1,
    PlanExecutionSide,
    PlanExecutionStageState,
    PlanExecutionStageV1,
)
from omni_cio.contracts.v1.portfolio_plan import PortfolioPlanV1
from omni_cio.real_trading.client_v1 import RealTradingApiFailure

from . import service_core_v1 as _core
from .broker_reconciliation_v1 import (
    PlanExecutionBrokerStateError,
    broker_snapshot_from_proposal,
)


SafePlanExecutionError = _core.SafePlanExecutionError
InstrumentBindingProviderV1 = _core.InstrumentBindingProviderV1
CurrentStateProviderV1 = _core.CurrentStateProviderV1
LegEvidenceProviderV1 = _core.LegEvidenceProviderV1


class SafePlanExecutionServiceV1(_core.SafePlanExecutionServiceV1):
    """WP12 public orchestrator with audited terminal reconciliation.

    The full fail-closed state machine lives in ``service_core_v1``.  This facade
    intentionally overrides only broker-terminal reconciliation so the plan
    object remains available for deterministic SELL tax allowance calculations.
    No broker submit implementation is introduced here; submission still flows
    through the existing v8.6.1 single-order primitive owned by the base class.
    """

    def _reconcile_broker(
        self,
        plan: PortfolioPlanV1,
        session: PlanExecutionSessionV1,
        stage: PlanExecutionStageV1,
        now: datetime,
    ) -> PlanExecutionAdvanceResultV1:
        if not stage.attempts or not stage.attempts[-1].proposal_id:
            return self._halt(
                session,
                PlanExecutionHaltCode.JOURNAL_CONFLICT,
                "Broker-reconciliation stage has no proposal identity.",
                stage=stage,
            )
        attempt = stage.attempts[-1]
        assert attempt.proposal_id is not None
        try:
            proposal = self._single_order.reconcile_proposal(attempt.proposal_id)
            snapshot = broker_snapshot_from_proposal(proposal)
        except RealTradingApiFailure as exc:
            return self._result(
                PlanExecutionAdvanceAction.REPLAY,
                session,
                f"Broker state is not yet reconcilable ({exc.code}); no resubmit occurred.",
                stage_id=stage.stage_id,
                proposal_id=attempt.proposal_id,
            )
        except PlanExecutionBrokerStateError as exc:
            return self._halt(
                session,
                PlanExecutionHaltCode.BROKER_RECONCILIATION_INCOMPLETE,
                str(exc),
                stage=stage,
            )

        if snapshot.status in {
            BrokerExecutionStatus.NEW,
            BrokerExecutionStatus.PARTIALLY_FILLED,
        }:
            active = PlanExecutionAttemptV1.model_validate(
                attempt.model_copy(
                    update={
                        "state": PlanExecutionAttemptState.ACTIVE,
                        "broker_status": snapshot.status,
                        "lots_executed": snapshot.lots_executed,
                        "total_order_amount_rub": snapshot.total_order_amount_rub,
                        "executed_commission_rub": snapshot.executed_commission_rub,
                        "broker_response_sha256": snapshot.response_sha256,
                    }
                ).model_dump(mode="python")
            )
            updated_stage = PlanExecutionStageV1.model_validate(
                stage.model_copy(
                    update={"attempts": (*stage.attempts[:-1], active)}
                ).model_dump(mode="python")
            )
            committed = self._commit(
                session,
                _core._stage_update(
                    session,
                    updated_stage,
                    state=PlanExecutionSessionState.AWAITING_BROKER_RECONCILIATION,
                ),
            )
            return self._result(
                PlanExecutionAdvanceAction.BROKER_ACTIVE,
                committed,
                "Broker order remains active/partially filled; remainder is not resubmitted.",
                stage_id=stage.stage_id,
                proposal_id=attempt.proposal_id,
                broker_snapshot=snapshot,
            )

        if snapshot.status in {
            BrokerExecutionStatus.REJECTED,
            BrokerExecutionStatus.UNSPECIFIED,
        }:
            return self._halt(
                session,
                PlanExecutionHaltCode.BROKER_REJECTED,
                f"Broker status {snapshot.status.value} halted all remaining plan legs.",
                stage=stage,
            )

        prior_terminal = sum(
            row.lots_executed
            for row in stage.attempts[:-1]
            if row.state is PlanExecutionAttemptState.TERMINAL
        )
        terminal_lots = prior_terminal + snapshot.lots_executed
        if terminal_lots > stage.planned_lots:
            return self._halt(
                session,
                PlanExecutionHaltCode.BROKER_FILL_OVERFLOW,
                "Broker fills exceed immutable stage quantity.",
                stage=stage,
            )

        terminal = PlanExecutionAttemptV1.model_validate(
            attempt.model_copy(
                update={
                    "state": PlanExecutionAttemptState.TERMINAL,
                    "reconciled_at": now,
                    "broker_status": snapshot.status,
                    "lots_executed": snapshot.lots_executed,
                    "total_order_amount_rub": snapshot.total_order_amount_rub,
                    "executed_commission_rub": snapshot.executed_commission_rub,
                    "broker_response_sha256": snapshot.response_sha256,
                }
            ).model_dump(mode="python")
        )
        broker_terminal = PlanExecutionStageV1.model_validate(
            stage.model_copy(
                update={
                    "state": PlanExecutionStageState.BROKER_TERMINAL,
                    "broker_terminal_lots": terminal_lots,
                    "attempts": (*stage.attempts[:-1], terminal),
                }
            ).model_dump(mode="python")
        )
        cash_delta = (
            -snapshot.total_order_amount_rub
            if stage.side is PlanExecutionSide.BUY
            else snapshot.total_order_amount_rub
        )
        updated = _core._stage_update(
            session,
            broker_terminal,
            state=PlanExecutionSessionState.AWAITING_PORTFOLIO_RECONCILIATION,
            confirmed_cash_delta_rub=session.confirmed_cash_delta_rub + cash_delta,
            estimated_tax_allowance_rub=(
                session.estimated_tax_allowance_rub
                + _core._tax_allowance(plan, stage, snapshot.lots_executed)
            ),
        )
        committed = self._commit(session, updated)
        return self._result(
            PlanExecutionAdvanceAction.BROKER_TERMINAL,
            committed,
            "Broker terminal state recorded; independent portfolio reconciliation is required.",
            stage_id=stage.stage_id,
            proposal_id=attempt.proposal_id,
            broker_snapshot=snapshot,
        )
