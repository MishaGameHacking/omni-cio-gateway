from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock

from omni_cio.contracts.v1.decision_capacity_pretrade import (
    CapacityPreTradeDecisionGateV1,
)
from omni_cio.contracts.v1.decision_capacity_sell_pretrade import (
    CapacitySellPreTradeDecisionGateV1,
)
from omni_cio.contracts.v1.final_decision_review_workflow_coordinator import (
    FinalDecisionReviewWorkflowCoordinatorResultV1,
    FinalDecisionReviewWorkflowCoordinatorStage,
    FinalDecisionReviewWorkflowCoordinatorStatus,
    FinalDecisionReviewWorkflowSourceEvidenceV1,
    FinalDecisionReviewWorkflowSourceSlot,
    FinalDecisionReviewWorkflowSourceStatus,
)
from omni_cio.contracts.v1.risk import RiskPolicyEvaluationV1
from omni_cio.release.final_decision_review_workflow_producer_v1 import (
    FinalDecisionReviewWorkflowProducerError,
    FinalDecisionReviewWorkflowProducerV1,
)


class FinalDecisionReviewWorkflowCoordinatorError(ValueError):
    """The read-only workflow coordinator cannot be configured safely."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise FinalDecisionReviewWorkflowCoordinatorError(
            "FINAL_DECISION_REVIEW_WORKFLOW_COORDINATOR_TIMESTAMP_MUST_BE_AWARE"
        )
    return result.astimezone(timezone.utc)


def available_final_decision_review_workflow_source(
    *,
    slot: FinalDecisionReviewWorkflowSourceSlot,
    observed_at: datetime,
    provider: str,
    operation: str,
) -> FinalDecisionReviewWorkflowSourceEvidenceV1:
    return FinalDecisionReviewWorkflowSourceEvidenceV1(
        slot=slot,
        status=FinalDecisionReviewWorkflowSourceStatus.AVAILABLE,
        observed_at=observed_at,
        provider=provider,
        operation=operation,
    )


def missing_final_decision_review_workflow_source(
    slot: FinalDecisionReviewWorkflowSourceSlot,
) -> FinalDecisionReviewWorkflowSourceEvidenceV1:
    return FinalDecisionReviewWorkflowSourceEvidenceV1(
        slot=slot,
        status=FinalDecisionReviewWorkflowSourceStatus.MISSING,
    )


def failed_final_decision_review_workflow_source(
    *,
    slot: FinalDecisionReviewWorkflowSourceSlot,
    error_code: str,
) -> FinalDecisionReviewWorkflowSourceEvidenceV1:
    return FinalDecisionReviewWorkflowSourceEvidenceV1(
        slot=slot,
        status=FinalDecisionReviewWorkflowSourceStatus.FAILED,
        error_code=error_code,
    )


def _ordered_evidence(
    evidence: tuple[FinalDecisionReviewWorkflowSourceEvidenceV1, ...],
) -> tuple[FinalDecisionReviewWorkflowSourceEvidenceV1, ...]:
    by_slot: dict[
        FinalDecisionReviewWorkflowSourceSlot,
        FinalDecisionReviewWorkflowSourceEvidenceV1,
    ] = {}
    for row in evidence:
        if row.slot in by_slot:
            raise FinalDecisionReviewWorkflowCoordinatorError(
                "FINAL_DECISION_REVIEW_WORKFLOW_COORDINATOR_DUPLICATE_SOURCE"
            )
        by_slot[row.slot] = row
    if set(by_slot) != set(FinalDecisionReviewWorkflowSourceSlot):
        raise FinalDecisionReviewWorkflowCoordinatorError(
            "FINAL_DECISION_REVIEW_WORKFLOW_COORDINATOR_SOURCE_SET_INCOMPLETE"
        )
    return tuple(by_slot[slot] for slot in FinalDecisionReviewWorkflowSourceSlot)


def _result(
    *,
    coordinated_at: datetime,
    stage: FinalDecisionReviewWorkflowCoordinatorStage,
    evidence: tuple[FinalDecisionReviewWorkflowSourceEvidenceV1, ...],
    selected_direction_count: int,
    source_evidence_complete: bool,
    freshness_confirmed: bool,
    account_context_confirmed: bool,
    exact_direction_confirmed: bool,
    blocker: str | None,
    producer_result: object | None = None,
) -> FinalDecisionReviewWorkflowCoordinatorResultV1:
    available = sum(
        row.status is FinalDecisionReviewWorkflowSourceStatus.AVAILABLE
        for row in evidence
    )
    missing = sum(
        row.status is FinalDecisionReviewWorkflowSourceStatus.MISSING
        for row in evidence
    )
    failed = sum(
        row.status is FinalDecisionReviewWorkflowSourceStatus.FAILED
        for row in evidence
    )
    published = bool(getattr(producer_result, "published", False))
    return FinalDecisionReviewWorkflowCoordinatorResultV1(
        coordinated_at=coordinated_at,
        status=(
            FinalDecisionReviewWorkflowCoordinatorStatus.PUBLISHED
            if published
            else FinalDecisionReviewWorkflowCoordinatorStatus.BLOCKED
        ),
        completed_stage=stage,
        published=published,
        primary_blocker=(
            getattr(producer_result, "primary_blocker", None)
            if producer_result is not None
            else blocker
        ),
        source_evidence=evidence,
        producer_result=producer_result,
        available_source_count=available,
        missing_source_count=missing,
        failed_source_count=failed,
        selected_direction_count=selected_direction_count,
        source_evidence_complete=source_evidence_complete,
        freshness_confirmed=freshness_confirmed,
        account_context_confirmed=account_context_confirmed,
        exact_direction_confirmed=exact_direction_confirmed,
    )


class FinalDecisionReviewWorkflowCoordinatorV1:
    """Validate source acquisition outcomes and invoke PR-66 only when complete."""

    def __init__(
        self,
        *,
        producer: FinalDecisionReviewWorkflowProducerV1,
        max_source_age_seconds: int = 900,
        future_tolerance_seconds: int = 60,
    ) -> None:
        if not 1 <= max_source_age_seconds <= 86_400:
            raise FinalDecisionReviewWorkflowCoordinatorError(
                "FINAL_DECISION_REVIEW_WORKFLOW_COORDINATOR_MAX_AGE_INVALID"
            )
        if not 0 <= future_tolerance_seconds <= 3_600:
            raise FinalDecisionReviewWorkflowCoordinatorError(
                "FINAL_DECISION_REVIEW_WORKFLOW_COORDINATOR_FUTURE_TOLERANCE_INVALID"
            )
        self._producer = producer
        self._max_source_age_seconds = max_source_age_seconds
        self._future_tolerance_seconds = future_tolerance_seconds
        self._lock = RLock()

    @property
    def producer(self) -> FinalDecisionReviewWorkflowProducerV1:
        return self._producer

    def coordinate(
        self,
        *,
        scenario_id: str,
        source_evidence: tuple[FinalDecisionReviewWorkflowSourceEvidenceV1, ...],
        current_risk_evaluation: RiskPolicyEvaluationV1 | None,
        pro_forma_risk_evaluation: RiskPolicyEvaluationV1 | None,
        purchase_gate: CapacityPreTradeDecisionGateV1 | None = None,
        sell_gate: CapacitySellPreTradeDecisionGateV1 | None = None,
        correlation_id: str,
        request_id: str | None = None,
        coordinated_at: datetime | None = None,
    ) -> FinalDecisionReviewWorkflowCoordinatorResultV1:
        now = _aware_utc(coordinated_at)
        ordered = _ordered_evidence(source_evidence)
        selected_direction_count = int(purchase_gate is not None) + int(sell_gate is not None)
        by_slot = {row.slot: row for row in ordered}
        artifacts_present = {
            FinalDecisionReviewWorkflowSourceSlot.PURCHASE_GATE: purchase_gate is not None,
            FinalDecisionReviewWorkflowSourceSlot.SELL_GATE: sell_gate is not None,
            FinalDecisionReviewWorkflowSourceSlot.CURRENT_RISK: (
                current_risk_evaluation is not None
            ),
            FinalDecisionReviewWorkflowSourceSlot.PRO_FORMA_RISK: (
                pro_forma_risk_evaluation is not None
            ),
        }
        correspondence_confirmed = all(
            (
                row.status is FinalDecisionReviewWorkflowSourceStatus.AVAILABLE
            )
            is artifacts_present[row.slot]
            for row in ordered
        )
        available_count = sum(
            row.status is FinalDecisionReviewWorkflowSourceStatus.AVAILABLE
            for row in ordered
        )
        missing_count = sum(
            row.status is FinalDecisionReviewWorkflowSourceStatus.MISSING
            for row in ordered
        )
        failed_count = sum(
            row.status is FinalDecisionReviewWorkflowSourceStatus.FAILED
            for row in ordered
        )
        evidence_complete = (
            selected_direction_count == 1
            and available_count == 3
            and missing_count == 1
            and failed_count == 0
        )
        if not evidence_complete or not correspondence_confirmed:
            return _result(
                coordinated_at=now,
                stage=FinalDecisionReviewWorkflowCoordinatorStage.SOURCE_EVIDENCE,
                evidence=ordered,
                selected_direction_count=selected_direction_count,
                source_evidence_complete=evidence_complete,
                freshness_confirmed=False,
                account_context_confirmed=False,
                exact_direction_confirmed=False,
                blocker="FINAL_DECISION_REVIEW_WORKFLOW_SOURCE_EVIDENCE_INCOMPLETE",
            )

        selected_gate = purchase_gate if purchase_gate is not None else sell_gate
        assert selected_gate is not None
        assert current_risk_evaluation is not None
        assert pro_forma_risk_evaluation is not None
        source_times = {
            FinalDecisionReviewWorkflowSourceSlot.PURCHASE_GATE: (
                purchase_gate.assessed_at if purchase_gate is not None else None
            ),
            FinalDecisionReviewWorkflowSourceSlot.SELL_GATE: (
                sell_gate.assessed_at if sell_gate is not None else None
            ),
            FinalDecisionReviewWorkflowSourceSlot.CURRENT_RISK: (
                current_risk_evaluation.metadata.retrieved_at
            ),
            FinalDecisionReviewWorkflowSourceSlot.PRO_FORMA_RISK: (
                pro_forma_risk_evaluation.metadata.retrieved_at
            ),
        }
        freshness_confirmed = True
        for row in ordered:
            if row.status is not FinalDecisionReviewWorkflowSourceStatus.AVAILABLE:
                continue
            source_time = source_times[row.slot]
            if source_time is None or row.observed_at != source_time:
                freshness_confirmed = False
                break
            age = (now - source_time).total_seconds()
            if (
                age > self._max_source_age_seconds
                or age < -self._future_tolerance_seconds
            ):
                freshness_confirmed = False
                break
        if not freshness_confirmed:
            return _result(
                coordinated_at=now,
                stage=FinalDecisionReviewWorkflowCoordinatorStage.FRESHNESS,
                evidence=ordered,
                selected_direction_count=selected_direction_count,
                source_evidence_complete=True,
                freshness_confirmed=False,
                account_context_confirmed=False,
                exact_direction_confirmed=False,
                blocker="FINAL_DECISION_REVIEW_WORKFLOW_SOURCE_STALE",
            )

        current_account = current_risk_evaluation.metadata.account
        pro_forma_account = pro_forma_risk_evaluation.metadata.account
        preview_accounts = tuple(
            row.preview.metadata.account for row in selected_gate.coverage
        )
        account_confirmed = (
            current_account == pro_forma_account
            and bool(preview_accounts)
            and all(account == current_account for account in preview_accounts)
        )
        if not account_confirmed:
            return _result(
                coordinated_at=now,
                stage=FinalDecisionReviewWorkflowCoordinatorStage.ACCOUNT_CONTEXT,
                evidence=ordered,
                selected_direction_count=selected_direction_count,
                source_evidence_complete=True,
                freshness_confirmed=True,
                account_context_confirmed=False,
                exact_direction_confirmed=False,
                blocker="FINAL_DECISION_REVIEW_WORKFLOW_ACCOUNT_MISMATCH",
            )

        expected_side = (
            "buy" if purchase_gate is not None else "sell"
        )
        requests = selected_gate.base_intent_gate.request.expected_capacity_requests
        direction_confirmed = bool(requests) and all(
            row.side.value == expected_side for row in requests
        )
        if not direction_confirmed:
            return _result(
                coordinated_at=now,
                stage=FinalDecisionReviewWorkflowCoordinatorStage.SOURCE_EVIDENCE,
                evidence=ordered,
                selected_direction_count=selected_direction_count,
                source_evidence_complete=True,
                freshness_confirmed=True,
                account_context_confirmed=True,
                exact_direction_confirmed=False,
                blocker="FINAL_DECISION_REVIEW_WORKFLOW_DIRECTION_MISMATCH",
            )

        with self._lock:
            try:
                producer_result = self._producer.produce(
                    scenario_id=scenario_id,
                    current_risk_evaluation=current_risk_evaluation,
                    pro_forma_risk_evaluation=pro_forma_risk_evaluation,
                    purchase_gate=purchase_gate,
                    sell_gate=sell_gate,
                    correlation_id=correlation_id,
                    request_id=request_id,
                    produced_at=now,
                )
            except (FinalDecisionReviewWorkflowProducerError, AttributeError, TypeError, ValueError):
                return _result(
                    coordinated_at=now,
                    stage=FinalDecisionReviewWorkflowCoordinatorStage.PRODUCER,
                    evidence=ordered,
                    selected_direction_count=selected_direction_count,
                    source_evidence_complete=True,
                    freshness_confirmed=True,
                    account_context_confirmed=True,
                    exact_direction_confirmed=True,
                    blocker="FINAL_DECISION_REVIEW_WORKFLOW_PRODUCER_INVALID",
                )

        return _result(
            coordinated_at=now,
            stage=FinalDecisionReviewWorkflowCoordinatorStage.PRODUCER,
            evidence=ordered,
            selected_direction_count=selected_direction_count,
            source_evidence_complete=True,
            freshness_confirmed=True,
            account_context_confirmed=True,
            exact_direction_confirmed=True,
            blocker=producer_result.primary_blocker,
            producer_result=producer_result,
        )
