from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import hashlib
import json

from omni_cio.contracts.v1.common import Completeness, ContractModel
from omni_cio.contracts.v1.decision import DecisionAction, DecisionSetV1
from omni_cio.contracts.v1.decision_journal import (
    DecisionJournalAction,
    DecisionJournalRecordV1,
)
from omni_cio.contracts.v1.investment_policy import InvestmentObjective
from omni_cio.contracts.v1.plan_execution import PlanExecutionSessionV1
from omni_cio.contracts.v1.portfolio_plan import PortfolioPlanV1
from omni_cio.contracts.v1.portfolio_risk import PortfolioRiskAssessmentV1

from .evaluation_v1 import finalize_decision_record
from .journal_v1 import DecisionJournalV1


class DecisionJournalRecorderError(ValueError):
    """Production decision inputs are not bound to one immutable evidence chain."""


def _canonical_sha256(value: ContractModel) -> str:
    payload = value.model_dump(mode="json")
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _preferred_action(decision_set: DecisionSetV1) -> DecisionAction:
    for option in decision_set.options:
        if option.option_id == decision_set.preferred_option_id:
            return option.action
    raise DecisionJournalRecorderError("DECISION_PREFERRED_OPTION_MISSING")


def _base_action(decision_set: DecisionSetV1) -> DecisionJournalAction:
    action = _preferred_action(decision_set)
    if action is DecisionAction.HOLD:
        return DecisionJournalAction.HOLD
    if action is DecisionAction.WAIT_FOR_DATA:
        return DecisionJournalAction.WAIT_FOR_DATA
    if action in {
        DecisionAction.REVIEW_LIMITED_CHANGE,
        DecisionAction.REVIEW_STRATEGIC_REBALANCE,
    }:
        return DecisionJournalAction.REVIEW_CHANGE
    raise DecisionJournalRecorderError("DECISION_ACTION_NOT_SUPPORTED")


def _has_executed_lots(execution: PlanExecutionSessionV1) -> bool:
    return any(
        attempt.lots_executed > 0
        for instrument in execution.instrument_states
        for stage in instrument.stages
        for attempt in stage.attempts
    )


def _validate_plan_binding(
    risk: PortfolioRiskAssessmentV1,
    plan: PortfolioPlanV1,
) -> None:
    if plan.policy_reference != risk.policy_reference:
        raise DecisionJournalRecorderError("PLAN_POLICY_BINDING_MISMATCH")
    if plan.portfolio_snapshot_sha256 != risk.portfolio_snapshot_sha256:
        raise DecisionJournalRecorderError("PLAN_PORTFOLIO_BINDING_MISMATCH")
    if plan.current_risk_assessment_sha256 != risk.assessment_sha256:
        raise DecisionJournalRecorderError("PLAN_RISK_BINDING_MISMATCH")
    if plan.risk_before != risk.before or plan.risk_after != risk.after:
        raise DecisionJournalRecorderError("PLAN_RISK_STATE_BINDING_MISMATCH")


def _select_action(
    decision_set: DecisionSetV1,
    *,
    plan: PortfolioPlanV1 | None,
    execution: PlanExecutionSessionV1 | None,
) -> DecisionJournalAction:
    base_action = _base_action(decision_set)
    if plan is None:
        if execution is not None:
            raise DecisionJournalRecorderError("EXECUTION_REQUIRES_PLAN")
        return base_action

    if base_action in {
        DecisionJournalAction.HOLD,
        DecisionJournalAction.WAIT_FOR_DATA,
    }:
        raise DecisionJournalRecorderError("NO_CHANGE_DECISION_CANNOT_BIND_PLAN")
    if not decision_set.recommendation_ready:
        raise DecisionJournalRecorderError("PLAN_REQUIRES_READY_DECISION")

    if execution is None:
        return DecisionJournalAction.REVIEW_CHANGE
    if execution.plan_sha256 != plan.plan_sha256:
        raise DecisionJournalRecorderError("EXECUTION_PLAN_BINDING_MISMATCH")

    has_fill = _has_executed_lots(execution)
    if has_fill and not execution.owner_approved:
        raise DecisionJournalRecorderError("EXECUTED_LOTS_REQUIRE_OWNER_APPROVAL")
    if has_fill:
        return DecisionJournalAction.EXECUTED_PLAN
    if execution.owner_approved:
        return DecisionJournalAction.APPROVED_PLAN
    return DecisionJournalAction.REVIEW_CHANGE


def build_production_decision_record(
    decision_set: DecisionSetV1,
    risk_assessment: PortfolioRiskAssessmentV1,
    *,
    policy_objective: InvestmentObjective,
    horizon_days: int,
    recorded_at: datetime,
    plan: PortfolioPlanV1 | None = None,
    execution: PlanExecutionSessionV1 | None = None,
    strategy_selection_sha256: str | None = None,
    optimizer_sha256: str | None = None,
) -> DecisionJournalRecordV1:
    """Bind canonical production decision objects into one immutable journal row.

    WP8/WP11/WP12 identities are consumed from their existing canonical SHA fields;
    this adapter does not invent a second hash authority for those objects. Only the
    DecisionSet and its individual evidence rows are canonically hashed here because
    those v1 contracts do not expose their own digest fields.
    """

    if risk_assessment.policy_reference.fingerprint_sha256 == "0" * 64:
        raise DecisionJournalRecorderError("POLICY_REFERENCE_FINGERPRINT_REQUIRED")

    if plan is not None:
        _validate_plan_binding(risk_assessment, plan)
        if strategy_selection_sha256 not in (None, plan.strategy_selection_sha256):
            raise DecisionJournalRecorderError("STRATEGY_BINDING_MISMATCH")
        if optimizer_sha256 not in (None, plan.optimizer_sha256):
            raise DecisionJournalRecorderError("OPTIMIZER_BINDING_MISMATCH")
        strategy_selection_sha256 = plan.strategy_selection_sha256
        optimizer_sha256 = plan.optimizer_sha256

    selected_action = _select_action(
        decision_set,
        plan=plan,
        execution=execution,
    )

    expected_research = (
        decision_set.required_market_count
        + decision_set.accepted_news_count
        + decision_set.context_news_count
    )
    available_research = (
        decision_set.market_coverage_count
        + decision_set.accepted_news_count
        + decision_set.context_news_count
    )
    data_complete = (
        decision_set.metadata.quality.completeness is Completeness.COMPLETE
        and risk_assessment.decision_ready
        and decision_set.recommendation_ready
    )

    values: dict[str, object] = {
        "recorded_at": recorded_at,
        "horizon_days": horizon_days,
        "policy_reference": risk_assessment.policy_reference,
        "policy_objective": policy_objective,
        "portfolio_snapshot_sha256": risk_assessment.portfolio_snapshot_sha256,
        "decision_set_sha256": _canonical_sha256(decision_set),
        "evidence_sha256s": tuple(
            _canonical_sha256(row) for row in decision_set.evidence
        ),
        "risk_assessment_sha256": risk_assessment.assessment_sha256,
        "strategy_selection_sha256": strategy_selection_sha256,
        "optimizer_sha256": optimizer_sha256,
        "plan_sha256": plan.plan_sha256 if plan is not None else None,
        "execution_id": execution.execution_id if execution is not None else None,
        "selected_action": selected_action,
        "starting_value_base": risk_assessment.before.total_value_base,
        "baseline_top1_weight": risk_assessment.before.concentration.top_1_weight,
        "baseline_cash_weight": risk_assessment.before.cash_weight,
        "target_top1_weight": (
            plan.risk_after.concentration.top_1_weight if plan is not None else None
        ),
        "target_cash_weight": plan.risk_after.cash_weight if plan is not None else None,
        "expected_execution_cost_base": (
            plan.total_commission_base if plan is not None else None
        ),
        "research_items_expected": expected_research,
        "research_items_available": available_research,
        "data_complete_at_decision": data_complete,
        "full_account_identifier_present": False,
        "raw_private_payload_present": False,
        "expectations_rewritable": False,
        "execution_authorized": False,
        "trading_methods": False,
    }
    return finalize_decision_record(values)


def record_production_decision(
    journal: DecisionJournalV1,
    decision_set: DecisionSetV1,
    risk_assessment: PortfolioRiskAssessmentV1,
    *,
    policy_objective: InvestmentObjective,
    horizon_days: int,
    recorded_at: datetime,
    plan: PortfolioPlanV1 | None = None,
    execution: PlanExecutionSessionV1 | None = None,
    strategy_selection_sha256: str | None = None,
    optimizer_sha256: str | None = None,
) -> DecisionJournalRecordV1:
    record = build_production_decision_record(
        decision_set,
        risk_assessment,
        policy_objective=policy_objective,
        horizon_days=horizon_days,
        recorded_at=recorded_at,
        plan=plan,
        execution=execution,
        strategy_selection_sha256=strategy_selection_sha256,
        optimizer_sha256=optimizer_sha256,
    )
    return journal.put_decision(record)
