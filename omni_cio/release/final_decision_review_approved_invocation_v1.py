from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Protocol

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
from omni_cio.contracts.v1.final_decision_review_trusted_scenario import (
    TrustedScenarioPublicationResultV1,
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


class FinalDecisionReviewApprovedOwnerSnapshotStorePortV1(Protocol):
    def capture_purchase(
        self,
        *,
        request: ApprovedCalculatorInvocationRequestV1,
        decision: DecisionSetV1,
        intent_request: CapacityIntentDecisionGateRequestV1,
        capacity_assessments: tuple[CapacityAssessmentV1, ...],
        purchase_previews: tuple[PreTradePreviewV1, ...],
        pro_forma_risk: RiskPolicyEvaluationV1,
        publication: TrustedScenarioPublicationResultV1,
        captured_at: datetime | None = None,
    ) -> object: ...

    def capture_sell(
        self,
        *,
        request: ApprovedCalculatorInvocationRequestV1,
        decision: DecisionSetV1,
        intent_request: CapacityIntentDecisionGateRequestV1,
        capacity_assessments: tuple[CapacityAssessmentV1, ...],
        sell_previews: tuple[SellPreTradePreviewV1, ...],
        pro_forma_risk: RiskPolicyEvaluationV1,
        publication: TrustedScenarioPublicationResultV1,
        captured_at: datetime | None = None,
    ) -> object: ...


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise FinalDecisionReviewApprovedInvocationError(
            "FINAL_DECISION_REVIEW_INVOCATION_TIMESTAMP_MUST_BE_AWARE"
        )
    return result.astimezone(timezone.utc)


def _require_request(
    value: ApprovedCalculatorInvocationRequestV1,
) -> ApprovedCalculatorInvocationRequestV1:
    if not isinstance(value, ApprovedCalculatorInvocationRequestV1):
        raise FinalDecisionReviewApprovedInvocationError(
            "FINAL_DECISION_REVIEW_INVOCATION_REQUEST_TYPE_INVALID"
        )
    return value


def _snapshot_store(
    value: FinalDecisionReviewApprovedOwnerSnapshotStorePortV1 | None,
) -> FinalDecisionReviewApprovedOwnerSnapshotStorePortV1 | None:
    if value is None:
        return None
    if not callable(getattr(value, "capture_purchase", None)) or not callable(
        getattr(value, "capture_sell", None)
    ):
        raise FinalDecisionReviewApprovedInvocationError(
            "FINAL_DECISION_REVIEW_INVOCATION_SNAPSHOT_STORE_INVALID"
        )
    return value


class FinalDecisionReviewApprovedInvocationV1:
    """Replay-safe allowlisted invocation boundary for the PR-73 workflow."""

    def __init__(
        self,
        *,
        workflow: FinalDecisionReviewCalculatorIntentWorkflowV1,
        snapshot_store: (
            FinalDecisionReviewApprovedOwnerSnapshotStorePortV1 | None
        ) = None,
        replay_ttl_seconds: int = 900,
        replay_capacity: int = 1_024,
        max_invocation_age_seconds: int = 300,
        future_tolerance_seconds: int = 30,
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
        if not 1 <= max_invocation_age_seconds <= 86_400:
            raise FinalDecisionReviewApprovedInvocationError(
                "FINAL_DECISION_REVIEW_INVOCATION_MAX_AGE_INVALID"
            )
        if not 0 <= future_tolerance_seconds <= 3_600:
            raise FinalDecisionReviewApprovedInvocationError(
                "FINAL_DECISION_REVIEW_INVOCATION_FUTURE_TOLERANCE_INVALID"
            )
        self._workflow = workflow
        self._snapshot_store = _snapshot_store(snapshot_store)
        self._replay_ttl_seconds = replay_ttl_seconds
        self._replay_capacity = replay_capacity
        self._max_invocation_age_seconds = max_invocation_age_seconds
        self._future_tolerance_seconds = future_tolerance_seconds
        self._completed: OrderedDict[str, datetime] = OrderedDict()
        self._lock = RLock()

    @property
    def workflow(self) -> FinalDecisionReviewCalculatorIntentWorkflowV1:
        return self._workflow

    @property
    def snapshot_store(
        self,
    ) -> FinalDecisionReviewApprovedOwnerSnapshotStorePortV1 | None:
        return self._snapshot_store

    def _purge(self, checked_at: datetime) -> None:
        expired = [
            invocation_id
            for invocation_id, expires_at in self._completed.items()
            if expires_at <= checked_at
        ]
        for invocation_id in expired:
            self._completed.pop(invocation_id, None)

    def _validate_request(
        self,
        value: ApprovedCalculatorInvocationRequestV1,
        *,
        checked_at: datetime,
    ) -> ApprovedCalculatorInvocationRequestV1:
        request = _require_request(value)
        age_seconds = (checked_at - request.invoked_at).total_seconds()
        if age_seconds > self._max_invocation_age_seconds:
            raise FinalDecisionReviewApprovedInvocationError(
                "FINAL_DECISION_REVIEW_INVOCATION_STALE"
            )
        if age_seconds < -self._future_tolerance_seconds:
            raise FinalDecisionReviewApprovedInvocationError(
                "FINAL_DECISION_REVIEW_INVOCATION_FROM_FUTURE"
            )
        return request

    def _reserve(
        self,
        request: ApprovedCalculatorInvocationRequestV1,
        *,
        checked_at: datetime,
    ) -> None:
        self._purge(checked_at)
        if request.invocation_id in self._completed:
            raise FinalDecisionReviewApprovedInvocationError(
                "FINAL_DECISION_REVIEW_INVOCATION_REPLAY_DETECTED"
            )

    def _complete(
        self,
        request: ApprovedCalculatorInvocationRequestV1,
        *,
        completed_at: datetime,
    ) -> None:
        self._completed[request.invocation_id] = completed_at + timedelta(
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
        done_at = _aware_utc(completed_at)
        approved = self._validate_request(request, checked_at=done_at)
        if approved.operation is not ApprovedCalculatorOperation.PURCHASE_REVIEW:
            raise FinalDecisionReviewApprovedInvocationError(
                "FINAL_DECISION_REVIEW_INVOCATION_OPERATION_NOT_ALLOWLISTED"
            )
        capacities = tuple(capacity_assessments)
        preview_rows = tuple(previews)
        with self._lock:
            self._reserve(approved, checked_at=done_at)
            try:
                publication = self._workflow.publish_purchase(
                    scenario_id=approved.scenario_id,
                    decision=decision,
                    intent_request=intent_request,
                    capacity_assessments=capacities,
                    previews=preview_rows,
                    pro_forma_risk=pro_forma_risk,
                    published_at=approved.invoked_at,
                )
                result = ApprovedCalculatorInvocationResultV1(
                    request=approved,
                    completed_at=done_at,
                    publication=publication,
                    capacity_assessment_count=len(capacities),
                    preview_count=len(preview_rows),
                )
                if self._snapshot_store is not None:
                    self._snapshot_store.capture_purchase(
                        request=approved,
                        decision=decision,
                        intent_request=intent_request,
                        capacity_assessments=capacities,
                        purchase_previews=preview_rows,
                        pro_forma_risk=pro_forma_risk,
                        publication=publication,
                        captured_at=done_at,
                    )
            except (
                FinalDecisionReviewCalculatorIntentWorkflowError,
                TypeError,
                ValueError,
            ) as exc:
                raise FinalDecisionReviewApprovedInvocationError(str(exc)) from exc
            self._complete(approved, completed_at=done_at)
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
        done_at = _aware_utc(completed_at)
        approved = self._validate_request(request, checked_at=done_at)
        if approved.operation is not ApprovedCalculatorOperation.SELL_REVIEW:
            raise FinalDecisionReviewApprovedInvocationError(
                "FINAL_DECISION_REVIEW_INVOCATION_OPERATION_NOT_ALLOWLISTED"
            )
        capacities = tuple(capacity_assessments)
        preview_rows = tuple(previews)
        with self._lock:
            self._reserve(approved, checked_at=done_at)
            try:
                publication = self._workflow.publish_sell(
                    scenario_id=approved.scenario_id,
                    decision=decision,
                    intent_request=intent_request,
                    capacity_assessments=capacities,
                    previews=preview_rows,
                    pro_forma_risk=pro_forma_risk,
                    published_at=approved.invoked_at,
                )
                result = ApprovedCalculatorInvocationResultV1(
                    request=approved,
                    completed_at=done_at,
                    publication=publication,
                    capacity_assessment_count=len(capacities),
                    preview_count=len(preview_rows),
                )
                if self._snapshot_store is not None:
                    self._snapshot_store.capture_sell(
                        request=approved,
                        decision=decision,
                        intent_request=intent_request,
                        capacity_assessments=capacities,
                        sell_previews=preview_rows,
                        pro_forma_risk=pro_forma_risk,
                        publication=publication,
                        captured_at=done_at,
                    )
            except (
                FinalDecisionReviewCalculatorIntentWorkflowError,
                TypeError,
                ValueError,
            ) as exc:
                raise FinalDecisionReviewApprovedInvocationError(str(exc)) from exc
            self._complete(approved, completed_at=done_at)
            return result
