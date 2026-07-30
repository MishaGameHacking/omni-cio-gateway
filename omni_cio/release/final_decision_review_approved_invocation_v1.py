from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from threading import RLock

from omni_cio.contracts.v1.capacity import CapacityAssessmentV1
from omni_cio.contracts.v1.decision import DecisionSetV1
from omni_cio.contracts.v1.decision_capacity_intent import (
    CapacityIntentDecisionGateRequestV1,
)
from omni_cio.contracts.v1.final_decision_review_approved_invocation import (
    ApprovedCalculatorInvocationRequestV1,
    ApprovedCalculatorInvocationResultV1,
    ApprovedCalculatorOperation,
)
from omni_cio.contracts.v1.pretrade import PreTradePreviewV1
from omni_cio.contracts.v1.risk import RiskPolicyEvaluationV1
from omni_cio.contracts.v1.sell_pretrade import SellPreTradePreviewV1
from omni_cio.release.final_decision_review_calculator_intent_workflow_v1 import (
    FinalDecisionReviewCalculatorIntentWorkflowError,
    FinalDecisionReviewCalculatorIntentWorkflowV1,
)


class FinalDecisionReviewApprovedInvocationError(ValueError):
    """An internal calculator invocation cannot be executed safely."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise FinalDecisionReviewApprovedInvocationError(
            "FINAL_DECISION_REVIEW_INVOCATION_TIMESTAMP_MUST_BE_AWARE"
        )
    return result.astimezone(timezone.utc)


class FinalDecisionReviewApprovedInvocationV1:
    """Replay-safe allowlisted invocation boundary for the PR-73 workflow."""

    def __init__(
        self,
        *,
        workflow: FinalDecisionReviewCalculatorIntentWorkflowV1,
        replay_ttl_seconds: int = 900,
        replay_capacity: int = 1_024,
    ) -> None:
        if not isinstance(workflow, FinalDecisionReviewCalculatorIntentWorkflowV1):
            raise FinalDecisionReviewApprovedInvocationError(
                "FINAL_DECISION_REVIEW_INVOCATION_WORKFLOW_TYPE_INVALID"
            )
        if not 1 <= replay_ttl_seconds <= 86_400:
            raise FinalDecisionReviewApprovedInvocationError(
                "FINAL_DECISION_REVIEW_INVOCATION_REPLAY_TTL_INVALID"
            )
        if not 1 <= replay_capacity <= 8_192:
            raise FinalDecisionReviewApprovedInvocationError(
                "FINAL_DECISION_REVIEW_INVOCATION_REPLAY_CAPACITY_INVALID"
            )
        self._workflow = workflow
        self._replay_ttl_seconds = replay_ttl_seconds
        self._replay_capacity = replay_capacity
        self._completed: OrderedDict[str, datetime] = OrderedDict()
        self._lock = RLock()

    @property
    def workflow(self) -> FinalDecisionReviewCalculatorIntentWorkflowV1:
        return self._workflow

    def _purge(self, checked_at: datetime) -> None:
        expired = [
            invocation_id
            for invocation_id, expires_at in self._completed.items()
            if expires_at <= checked_at
        ]
        for invocation_id in expired:
            self._completed.pop(invocation_id, None)

    def _reserve(self, request: ApprovedCalculatorInvocationRequestV1) -> None:
        self._purge(request.invoked_at)
        if request.invocation_id in self._completed:
            raise FinalDecisionReviewApprovedInvocationError(
                "FINAL_DECISION_REVIEW_INVOCATION_REPLAY_DETECTED"
            )

    def _complete(self, request: ApprovedCalculatorInvocationRequestV1) -> None:
        self._completed[request.invocation_id] = request.invoked_at + timedelta(
            seconds=self._replay_ttl_seconds
        )
        self._completed.move_to_end(request.invocation_id)
        while len(self._completed) > self._replay_capacity:
            self._completed.popitem(last=False)

    def invoke_purchase(
        self,
        *,
        request: ApprovedCalculatorInvocationRequestV1,
        decision: DecisionSetV1,
        intent_request: CapacityIntentDecisionGateRequestV1,
        capacity_assessments: Iterable[CapacityAssessmentV1],
        previews: Iterable[PreTradePreviewV1],
        pro_forma_risk: RiskPolicyEvaluationV1,
        completed_at: datetime | None = None,
    ) -> ApprovedCalculatorInvocationResultV1:
        if request.operation is not ApprovedCalculatorOperation.PURCHASE_REVIEW:
            raise FinalDecisionReviewApprovedInvocationError(
                "FINAL_DECISION_REVIEW_INVOCATION_OPERATION_NOT_ALLOWLISTED"
            )
        capacities = tuple(capacity_assessments)
        preview_rows = tuple(previews)
        done_at = _aware_utc(completed_at or request.invoked_at)
        with self._lock:
            self._reserve(request)
            try:
                publication = self._workflow.publish_purchase(
                    scenario_id=request.scenario_id,
                    decision=decision,
                    intent_request=intent_request,
                    capacity_assessments=capacities,
                    previews=preview_rows,
                    pro_forma_risk=pro_forma_risk,
                    published_at=request.invoked_at,
                )
                result = ApprovedCalculatorInvocationResultV1(
                    request=request,
                    completed_at=done_at,
                    publication=publication,
                    capacity_assessment_count=len(capacities),
                    preview_count=len(preview_rows),
                )
            except (
                FinalDecisionReviewCalculatorIntentWorkflowError,
                TypeError,
                ValueError,
            ) as exc:
                raise FinalDecisionReviewApprovedInvocationError(str(exc)) from exc
            self._complete(request)
            return result

    def invoke_sell(
        self,
        *,
        request: ApprovedCalculatorInvocationRequestV1,
        decision: DecisionSetV1,
        intent_request: CapacityIntentDecisionGateRequestV1,
        capacity_assessments: Iterable[CapacityAssessmentV1],
        previews: Iterable[SellPreTradePreviewV1],
        pro_forma_risk: RiskPolicyEvaluationV1,
        completed_at: datetime | None = None,
    ) -> ApprovedCalculatorInvocationResultV1:
        if request.operation is not ApprovedCalculatorOperation.SELL_REVIEW:
            raise FinalDecisionReviewApprovedInvocationError(
                "FINAL_DECISION_REVIEW_INVOCATION_OPERATION_NOT_ALLOWLISTED"
            )
        capacities = tuple(capacity_assessments)
        preview_rows = tuple(previews)
        done_at = _aware_utc(completed_at or request.invoked_at)
        with self._lock:
            self._reserve(request)
            try:
                publication = self._workflow.publish_sell(
                    scenario_id=request.scenario_id,
                    decision=decision,
                    intent_request=intent_request,
                    capacity_assessments=capacities,
                    previews=preview_rows,
                    pro_forma_risk=pro_forma_risk,
                    published_at=request.invoked_at,
                )
                result = ApprovedCalculatorInvocationResultV1(
                    request=request,
                    completed_at=done_at,
                    publication=publication,
                    capacity_assessment_count=len(capacities),
                    preview_count=len(preview_rows),
                )
            except (
                FinalDecisionReviewCalculatorIntentWorkflowError,
                TypeError,
                ValueError,
            ) as exc:
                raise FinalDecisionReviewApprovedInvocationError(str(exc)) from exc
            self._complete(request)
            return result
