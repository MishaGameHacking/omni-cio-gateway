from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from omni_cio.contracts.v1.capacity import CapacityAssessmentV1
from omni_cio.contracts.v1.decision import DecisionSetV1
from omni_cio.contracts.v1.decision_capacity import CapacityDecisionGatePolicyV1
from omni_cio.contracts.v1.decision_capacity_intent import (
    CapacityIntentDecisionGateRequestV1,
)
from omni_cio.contracts.v1.final_decision_review_trusted_scenario import (
    TrustedScenarioPublicationResultV1,
)
from omni_cio.contracts.v1.pretrade import PreTradePreviewV1
from omni_cio.contracts.v1.risk import RiskPolicyEvaluationV1
from omni_cio.contracts.v1.sell_pretrade import SellPreTradePreviewV1
from omni_cio.decision.capacity_intent_gate_v1 import (
    CapacityIntentDecisionGateError,
    apply_capacity_intent_decision_gate,
)
from omni_cio.release.final_decision_review_calculator_handoff_v1 import (
    FinalDecisionReviewCalculatorScenarioHandoffError,
    FinalDecisionReviewCalculatorScenarioHandoffV1,
)


class FinalDecisionReviewCalculatorIntentWorkflowError(ValueError):
    """Calculator intent inputs cannot cross the trusted handoff safely."""


def _require_decision(value: DecisionSetV1) -> DecisionSetV1:
    if not isinstance(value, DecisionSetV1):
        raise FinalDecisionReviewCalculatorIntentWorkflowError(
            "FINAL_DECISION_REVIEW_INTENT_WORKFLOW_DECISION_TYPE_INVALID"
        )
    return value


def _require_request(
    value: CapacityIntentDecisionGateRequestV1,
) -> CapacityIntentDecisionGateRequestV1:
    if not isinstance(value, CapacityIntentDecisionGateRequestV1):
        raise FinalDecisionReviewCalculatorIntentWorkflowError(
            "FINAL_DECISION_REVIEW_INTENT_WORKFLOW_REQUEST_TYPE_INVALID"
        )
    return value


def _typed_assessments(
    values: Iterable[CapacityAssessmentV1],
) -> tuple[CapacityAssessmentV1, ...]:
    rows = tuple(values)
    if not rows or any(not isinstance(row, CapacityAssessmentV1) for row in rows):
        raise FinalDecisionReviewCalculatorIntentWorkflowError(
            "FINAL_DECISION_REVIEW_INTENT_WORKFLOW_ASSESSMENTS_INVALID"
        )
    return rows


def _require_risk(value: RiskPolicyEvaluationV1) -> RiskPolicyEvaluationV1:
    if not isinstance(value, RiskPolicyEvaluationV1):
        raise FinalDecisionReviewCalculatorIntentWorkflowError(
            "FINAL_DECISION_REVIEW_INTENT_WORKFLOW_PRO_FORMA_TYPE_INVALID"
        )
    return value


class FinalDecisionReviewCalculatorIntentWorkflowV1:
    """Build an exact intent gate and delegate preview publication to PR-72."""

    def __init__(
        self,
        *,
        handoff: FinalDecisionReviewCalculatorScenarioHandoffV1,
        capacity_policy: CapacityDecisionGatePolicyV1 | None = None,
    ) -> None:
        if not isinstance(handoff, FinalDecisionReviewCalculatorScenarioHandoffV1):
            raise FinalDecisionReviewCalculatorIntentWorkflowError(
                "FINAL_DECISION_REVIEW_INTENT_WORKFLOW_HANDOFF_TYPE_INVALID"
            )
        self._handoff = handoff
        self._capacity_policy = capacity_policy or CapacityDecisionGatePolicyV1()

    @property
    def handoff(self) -> FinalDecisionReviewCalculatorScenarioHandoffV1:
        return self._handoff

    def _build_intent(
        self,
        *,
        decision: DecisionSetV1,
        intent_request: CapacityIntentDecisionGateRequestV1,
        capacity_assessments: Iterable[CapacityAssessmentV1],
        pro_forma_risk: RiskPolicyEvaluationV1,
    ):
        source_decision = _require_decision(decision)
        request = _require_request(intent_request)
        assessments = _typed_assessments(capacity_assessments)
        risk = _require_risk(pro_forma_risk)
        try:
            return apply_capacity_intent_decision_gate(
                source_decision,
                request,
                assessments,
                policy=self._capacity_policy,
                assessed_at=risk.metadata.retrieved_at,
            )
        except (CapacityIntentDecisionGateError, AttributeError, TypeError, ValueError) as exc:
            raise FinalDecisionReviewCalculatorIntentWorkflowError(str(exc)) from exc

    def publish_purchase(
        self,
        *,
        scenario_id: str,
        decision: DecisionSetV1,
        intent_request: CapacityIntentDecisionGateRequestV1,
        capacity_assessments: Iterable[CapacityAssessmentV1],
        previews: Iterable[PreTradePreviewV1],
        pro_forma_risk: RiskPolicyEvaluationV1,
        published_at: datetime | None = None,
    ) -> TrustedScenarioPublicationResultV1:
        risk = _require_risk(pro_forma_risk)
        intent = self._build_intent(
            decision=decision,
            intent_request=intent_request,
            capacity_assessments=capacity_assessments,
            pro_forma_risk=risk,
        )
        try:
            return self._handoff.publish_purchase(
                scenario_id=scenario_id,
                base_intent_gate=intent,
                previews=previews,
                pro_forma_risk=risk,
                published_at=published_at,
            )
        except FinalDecisionReviewCalculatorScenarioHandoffError as exc:
            raise FinalDecisionReviewCalculatorIntentWorkflowError(str(exc)) from exc

    def publish_sell(
        self,
        *,
        scenario_id: str,
        decision: DecisionSetV1,
        intent_request: CapacityIntentDecisionGateRequestV1,
        capacity_assessments: Iterable[CapacityAssessmentV1],
        previews: Iterable[SellPreTradePreviewV1],
        pro_forma_risk: RiskPolicyEvaluationV1,
        published_at: datetime | None = None,
    ) -> TrustedScenarioPublicationResultV1:
        risk = _require_risk(pro_forma_risk)
        intent = self._build_intent(
            decision=decision,
            intent_request=intent_request,
            capacity_assessments=capacity_assessments,
            pro_forma_risk=risk,
        )
        try:
            return self._handoff.publish_sell(
                scenario_id=scenario_id,
                base_intent_gate=intent,
                previews=previews,
                pro_forma_risk=risk,
                published_at=published_at,
            )
        except FinalDecisionReviewCalculatorScenarioHandoffError as exc:
            raise FinalDecisionReviewCalculatorIntentWorkflowError(str(exc)) from exc
