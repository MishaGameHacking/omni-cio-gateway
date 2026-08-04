from __future__ import annotations

from datetime import datetime, timedelta
import hmac

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
    """Audited WP12 facade over the accepted v8.6.1 execution primitive.

    Cross-WP hardening lives here so the core state machine remains reviewable:
    immutable-plan expiry blocks any new prepare/submit; the current strategy,
    optimizer and target-risk identities remain bound before every stage action;
    staged legs advance by tranche/day while preserving leg sequence inside each
    tranche; and a single instrument cannot submit two staged slices on one Moscow
    calendar day. Already-submitted orders always remain broker-reconcilable.
    Broker submit itself remains owned exclusively by the existing
    ``RealTradingServiceV1`` path inherited through the core service.
    """

    def prepare_plan(
        self,
        *,
        plan: PortfolioPlanV1,
        now: datetime | None = None,
    ) -> PlanExecutionSessionV1:
        current = _core._aware_utc(now)
        canonical = _core._canonical_plan(plan)
        actionable = _core._actionable_legs(canonical)
        if actionable:
            actual_execution_days = max(
                _core._stage_count(row.optimizer_leg, self._real_policy)
                for row in actionable
                if row.optimizer_leg is not None
            )
            last_slice_time = current + timedelta(days=actual_execution_days - 1)
            if last_slice_time >= canonical.expires_at:
                raise SafePlanExecutionError(
                    "PLAN_EXECUTION_PLAN_HORIZON_TOO_SHORT",
                    "Existing real-money hard cap would stretch staged execution "
                    "beyond immutable plan expiry; a fresh plan or separately "
                    "authorized cap-policy change is required.",
                    halt_code=PlanExecutionHaltCode.PREPARE_REJECTED,
                )
        return super().prepare_plan(plan=canonical, now=current)

    def approve_plan(
        self,
        *,
        execution_id: str,
        plan: PortfolioPlanV1,
        owner_approval_phrase: str,
        now: datetime | None = None,
    ) -> PlanExecutionAdvanceResultV1:
        """Record the exact Unicode owner challenge without submitting an order."""
        current = _core._aware_utc(now)
        canonical = _core._canonical_plan(plan)
        session = self._journal.get(execution_id)
        if session.plan_sha256 != canonical.plan_sha256:
            return self._halt(
                session,
                PlanExecutionHaltCode.PLAN_INVALID,
                "Execution session does not match immutable plan.",
            )
        if session.owner_approved:
            return self._result(
                PlanExecutionAdvanceAction.REPLAY,
                session,
                "Exact plan approval was already recorded; no submit repeated.",
            )
        if current >= canonical.expires_at:
            return self._halt(
                session,
                PlanExecutionHaltCode.PLAN_EXPIRED,
                "Plan expired before owner approval.",
            )

        expected_phrase = canonical.owner_approval_phrase or ""
        exact_match = bool(expected_phrase) and hmac.compare_digest(
            owner_approval_phrase.encode("utf-8"),
            expected_phrase.encode("utf-8"),
        )
        if not exact_match:
            return self._halt(
                session,
                PlanExecutionHaltCode.OWNER_APPROVAL_MISMATCH,
                "Exact owner approval phrase for this plan is required.",
            )

        state = self._state(canonical, current)
        matched, code, message = _core._progress_match(
            plan=canonical,
            session=session,
            state=state,
            settings=self._settings,
            now=current,
        )
        if not matched:
            return self._halt(
                session,
                code or PlanExecutionHaltCode.PORTFOLIO_PROGRESS_MISMATCH,
                message or "Current state no longer matches plan start.",
            )
        bindings = {
            item.binding.stable_key: item.binding
            for item in session.instrument_states
        }
        review = self._initial_review(canonical, state, bindings, current)
        if (
            not review.plan_valid
            or review.expected_owner_approval_phrase != expected_phrase
        ):
            return self._halt(
                session,
                PlanExecutionHaltCode.PLAN_INVALID,
                "Plan became invalid before owner approval.",
            )

        evidence_sha = _core._sha(
            "plan-owner-approval-v1",
            execution_id,
            canonical.plan_sha256,
            owner_approval_phrase,
        )
        updated = _core._session_update(
            session,
            state=PlanExecutionSessionState.ACTIVE,
            last_reviewed_at=current,
            last_review_sha256=review.review_sha256,
            owner_approved=True,
            owner_approved_at=current,
            owner_approval_evidence_sha256=evidence_sha,
        )
        committed = self._commit(session, updated)
        return self._result(
            PlanExecutionAdvanceAction.APPROVED,
            committed,
            "Exact immutable plan approval recorded; no broker submit occurred.",
        )

    @staticmethod
    def _next_execution_stage(
        session: PlanExecutionSessionV1,
    ) -> PlanExecutionStageV1 | None:
        """Return the next immutable tranche stage without reordering its legs."""
        remaining = sorted(
            (
                row
                for row in _core._all_stages(session)
                if row.state is not PlanExecutionStageState.FILLED
            ),
            key=lambda row: (row.stage_index, row.leg_sequence, row.stage_id),
        )
        return remaining[0] if remaining else None

    def advance_execution(
        self,
        *,
        execution_id: str,
        plan: PortfolioPlanV1,
        now: datetime | None = None,
    ) -> PlanExecutionAdvanceResultV1:
        current = _core._aware_utc(now)
        canonical = _core._canonical_plan(plan)
        session = self._journal.get(execution_id)
        if session.plan_sha256 != canonical.plan_sha256:
            return self._halt(
                session,
                PlanExecutionHaltCode.PLAN_INVALID,
                "Execution session no longer matches immutable plan.",
            )
        if session.state is PlanExecutionSessionState.COMPLETED:
            return self._result(
                PlanExecutionAdvanceAction.REPLAY,
                session,
                "Execution is already completed; replay performed no submit.",
            )
        if not session.owner_approved:
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_OWNER_APPROVAL_REQUIRED",
                "Exact plan approval is required before stage preparation.",
            )

        if session.state is PlanExecutionSessionState.HALTED:
            if session.halt_code is not PlanExecutionHaltCode.AMBIGUOUS_SUBMISSION:
                return self._result(
                    PlanExecutionAdvanceAction.HALTED,
                    session,
                    session.halt_message or "Execution is halted.",
                )
            ambiguous = next(
                (
                    row
                    for row in _core._all_stages(session)
                    if row.attempts
                    and row.attempts[-1].state is PlanExecutionAttemptState.UNKNOWN
                ),
                None,
            )
            if ambiguous is None:
                return self._result(
                    PlanExecutionAdvanceAction.HALTED,
                    session,
                    "Ambiguous session has no recoverable request id.",
                )
            recovered = _core._session_update(
                session,
                state=PlanExecutionSessionState.AWAITING_BROKER_RECONCILIATION,
                halt_code=None,
                halt_message=None,
            )
            committed = self._commit(session, recovered)
            return self._reconcile_broker(
                canonical,
                committed,
                _core._stage(committed, ambiguous.stage_id),
                current,
            )

        current_stage = self._next_execution_stage(session)
        if current_stage is None:
            committed = self._commit(
                session,
                _core._session_update(
                    session,
                    state=PlanExecutionSessionState.COMPLETED,
                ),
            )
            return self._result(
                PlanExecutionAdvanceAction.COMPLETED,
                committed,
                "All immutable plan stages are complete.",
            )

        if current >= canonical.expires_at and current_stage.state not in {
            PlanExecutionStageState.AWAITING_BROKER_RECONCILIATION,
            PlanExecutionStageState.BROKER_TERMINAL,
        }:
            return self._halt(
                session,
                PlanExecutionHaltCode.PLAN_EXPIRED,
                "Immutable plan expired; no new stage may be prepared or submitted.",
                stage=current_stage,
            )

        if current_stage.state is PlanExecutionStageState.PENDING:
            return self._prepare_stage(canonical, session, current_stage, current)
        if current_stage.state is PlanExecutionStageState.PREPARED:
            return self._submit_stage(canonical, session, current_stage, current)
        if current_stage.state is PlanExecutionStageState.AWAITING_BROKER_RECONCILIATION:
            return self._reconcile_broker(canonical, session, current_stage, current)
        if current_stage.state is PlanExecutionStageState.BROKER_TERMINAL:
            return self._reconcile_portfolio(canonical, session, current_stage, current)
        if current_stage.state is PlanExecutionStageState.HALTED:
            return self._result(
                PlanExecutionAdvanceAction.HALTED,
                session,
                "Current immutable plan stage is halted.",
                stage_id=current_stage.stage_id,
            )
        return self._result(
            PlanExecutionAdvanceAction.REPLAY,
            session,
            "Stage state does not permit a new submit.",
            stage_id=current_stage.stage_id,
        )

    def _runtime_guard(
        self,
        plan: PortfolioPlanV1,
        session: PlanExecutionSessionV1,
        stage: PlanExecutionStageV1,
        now: datetime,
    ):
        state = self._state(plan, now)
        if state.strategy_selection_sha256 != plan.strategy_selection_sha256:
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_STRATEGY_BINDING_CHANGED",
                "Strategy selection changed after immutable plan approval.",
                halt_code=PlanExecutionHaltCode.PLAN_INVALID,
            )
        if state.optimizer_sha256 != plan.optimizer_sha256:
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_OPTIMIZER_BINDING_CHANGED",
                "Optimizer result changed after immutable plan approval.",
                halt_code=PlanExecutionHaltCode.PLAN_INVALID,
            )
        if (
            state.target_risk_assessment_sha256
            != plan.target_risk_assessment_sha256
        ):
            raise SafePlanExecutionError(
                "PLAN_EXECUTION_TARGET_RISK_BINDING_CHANGED",
                "Target risk assessment changed after immutable plan approval.",
                halt_code=PlanExecutionHaltCode.PLAN_INVALID,
            )

        no_confirmed_fill = all(
            row.broker_terminal_lots == 0 for row in _core._all_stages(session)
        )
        if no_confirmed_fill:
            if state.portfolio_snapshot_sha256 != plan.portfolio_snapshot_sha256:
                raise SafePlanExecutionError(
                    "PLAN_EXECUTION_INITIAL_PORTFOLIO_BINDING_CHANGED",
                    "Portfolio snapshot changed before the first confirmed fill.",
                    halt_code=PlanExecutionHaltCode.PORTFOLIO_PROGRESS_MISMATCH,
                )
            if state.risk_assessment_sha256 != plan.current_risk_assessment_sha256:
                raise SafePlanExecutionError(
                    "PLAN_EXECUTION_INITIAL_RISK_BINDING_CHANGED",
                    "Current risk assessment changed before the first confirmed fill.",
                    halt_code=PlanExecutionHaltCode.CURRENT_RISK_NOT_READY,
                )

        return super()._runtime_guard(plan, session, stage, now)

    def _prepare_stage(
        self,
        plan: PortfolioPlanV1,
        session: PlanExecutionSessionV1,
        stage: PlanExecutionStageV1,
        now: datetime,
    ) -> PlanExecutionAdvanceResultV1:
        today = _core._moscow_date(now)
        if any(
            row.stable_key == stage.stable_key
            and row.last_submission_moscow_date == today
            for row in _core._all_stages(session)
        ):
            return self._result(
                PlanExecutionAdvanceAction.WAITING_NEXT_STAGE_DAY,
                session,
                "A staged slice for this immutable instrument was already "
                "submitted today; no second same-day slice is allowed.",
                stage_id=stage.stage_id,
            )
        return super()._prepare_stage(plan, session, stage, now)

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
