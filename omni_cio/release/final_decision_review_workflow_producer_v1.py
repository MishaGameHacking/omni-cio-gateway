from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock

from omni_cio.contracts.v1.decision_capacity_pretrade import (
    CapacityPreTradeDecisionGateV1,
)
from omni_cio.contracts.v1.decision_capacity_sell_pretrade import (
    CapacitySellPreTradeDecisionGateV1,
)
from omni_cio.contracts.v1.final_decision_review_workflow_producer import (
    FinalDecisionReviewWorkflowProducerResultV1,
    FinalDecisionReviewWorkflowProducerStage,
    FinalDecisionReviewWorkflowProducerStatus,
)
from omni_cio.contracts.v1.risk import RiskPolicyEvaluationV1
from omni_cio.decision.capacity_directional_pretrade_review_v1 import (
    CapacityDirectionalPreTradeReviewError,
    compose_capacity_directional_pretrade_review,
)
from omni_cio.decision.risk_pretrade_explanation_v1 import (
    RiskPreTradeExplanationError,
    compose_risk_pretrade_explanation,
)
from omni_cio.release.final_decision_review_workflow_bridge_v1 import (
    FinalDecisionReviewWorkflowBridgeError,
    FinalDecisionReviewWorkflowBridgeV1,
)


class FinalDecisionReviewWorkflowProducerError(ValueError):
    """The live read-only workflow producer cannot be configured safely."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise FinalDecisionReviewWorkflowProducerError(
            "FINAL_DECISION_REVIEW_WORKFLOW_PRODUCER_TIMESTAMP_MUST_BE_AWARE"
        )
    return result.astimezone(timezone.utc)


def _blocked_result(
    *,
    produced_at: datetime,
    stage: FinalDecisionReviewWorkflowProducerStage,
    blocker: str,
    bridge: FinalDecisionReviewWorkflowBridgeV1,
    input_direction_count: int,
    directional_review: object | None = None,
    risk_explanation: object | None = None,
) -> FinalDecisionReviewWorkflowProducerResultV1:
    return FinalDecisionReviewWorkflowProducerResultV1(
        produced_at=produced_at,
        status=FinalDecisionReviewWorkflowProducerStatus.BLOCKED,
        completed_stage=stage,
        published=False,
        primary_blocker=blocker,
        directional_review=directional_review,
        risk_explanation=risk_explanation,
        registry_active_sources=bridge.registry.active_source_count(
            checked_at=produced_at
        ),
        input_direction_count=input_direction_count,
    )


class FinalDecisionReviewWorkflowProducerV1:
    """Compose typed read-only decision evidence and invoke the PR-65 bridge."""

    def __init__(self, *, bridge: FinalDecisionReviewWorkflowBridgeV1) -> None:
        self._bridge = bridge
        self._lock = RLock()

    @property
    def bridge(self) -> FinalDecisionReviewWorkflowBridgeV1:
        return self._bridge

    def produce(
        self,
        *,
        scenario_id: str,
        current_risk_evaluation: RiskPolicyEvaluationV1,
        pro_forma_risk_evaluation: RiskPolicyEvaluationV1,
        purchase_gate: CapacityPreTradeDecisionGateV1 | None = None,
        sell_gate: CapacitySellPreTradeDecisionGateV1 | None = None,
        correlation_id: str,
        request_id: str | None = None,
        produced_at: datetime | None = None,
    ) -> FinalDecisionReviewWorkflowProducerResultV1:
        now = _aware_utc(produced_at)
        input_direction_count = int(purchase_gate is not None) + int(sell_gate is not None)
        with self._lock:
            try:
                directional_review = compose_capacity_directional_pretrade_review(
                    purchase_gate=purchase_gate,
                    sell_gate=sell_gate,
                )
            except (CapacityDirectionalPreTradeReviewError, AttributeError, TypeError, ValueError):
                return _blocked_result(
                    produced_at=now,
                    stage=FinalDecisionReviewWorkflowProducerStage.DIRECTIONAL_REVIEW,
                    blocker=(
                        "FINAL_DECISION_REVIEW_WORKFLOW_DIRECTIONAL_REVIEW_INVALID"
                    ),
                    bridge=self._bridge,
                    input_direction_count=input_direction_count,
                )

            try:
                risk_explanation = compose_risk_pretrade_explanation(
                    current_risk_evaluation,
                    directional_review,
                    assessed_at=now,
                )
            except (RiskPreTradeExplanationError, AttributeError, TypeError, ValueError):
                return _blocked_result(
                    produced_at=now,
                    stage=FinalDecisionReviewWorkflowProducerStage.RISK_EXPLANATION,
                    blocker="FINAL_DECISION_REVIEW_WORKFLOW_RISK_EXPLANATION_INVALID",
                    bridge=self._bridge,
                    input_direction_count=input_direction_count,
                    directional_review=directional_review,
                )

            expected_requests = (
                directional_review.base_intent_gate.request.expected_capacity_requests
            )
            try:
                workflow_bridge = self._bridge.publish(
                    scenario_id=scenario_id,
                    base_explanation=risk_explanation,
                    capacity_requests=expected_requests,
                    pro_forma_risk_evaluation=pro_forma_risk_evaluation,
                    correlation_id=correlation_id,
                    request_id=request_id,
                    bridged_at=now,
                )
            except (FinalDecisionReviewWorkflowBridgeError, AttributeError, TypeError, ValueError):
                return _blocked_result(
                    produced_at=now,
                    stage=FinalDecisionReviewWorkflowProducerStage.WORKFLOW_BRIDGE,
                    blocker="FINAL_DECISION_REVIEW_WORKFLOW_BRIDGE_INVALID",
                    bridge=self._bridge,
                    input_direction_count=input_direction_count,
                    directional_review=directional_review,
                    risk_explanation=risk_explanation,
                )

            published = workflow_bridge.published
            return FinalDecisionReviewWorkflowProducerResultV1(
                produced_at=now,
                status=(
                    FinalDecisionReviewWorkflowProducerStatus.PUBLISHED
                    if published
                    else FinalDecisionReviewWorkflowProducerStatus.BLOCKED
                ),
                completed_stage=FinalDecisionReviewWorkflowProducerStage.WORKFLOW_BRIDGE,
                published=published,
                primary_blocker=workflow_bridge.primary_blocker,
                directional_review=directional_review,
                risk_explanation=risk_explanation,
                workflow_bridge=workflow_bridge,
                registry_active_sources=self._bridge.registry.active_source_count(
                    checked_at=now
                ),
                input_direction_count=input_direction_count,
            )
