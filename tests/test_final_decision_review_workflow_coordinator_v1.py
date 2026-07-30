from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.capacity import OrderSide
from omni_cio.contracts.v1.common import AccountReference
from omni_cio.contracts.v1.final_decision_review_workflow_coordinator import (
    FinalDecisionReviewWorkflowCoordinatorResultV1,
    FinalDecisionReviewWorkflowCoordinatorStage,
    FinalDecisionReviewWorkflowCoordinatorStatus,
    FinalDecisionReviewWorkflowSourceEvidenceV1,
    FinalDecisionReviewWorkflowSourceSlot,
    FinalDecisionReviewWorkflowSourceStatus,
)
from omni_cio.contracts.v1.final_decision_review_workflow_producer import (
    FinalDecisionReviewWorkflowProducerResultV1,
    FinalDecisionReviewWorkflowProducerStatus,
)
from omni_cio.release.final_decision_review_workflow_coordinator_v1 import (
    FinalDecisionReviewWorkflowCoordinatorError,
    FinalDecisionReviewWorkflowCoordinatorV1,
    available_final_decision_review_workflow_source,
    failed_final_decision_review_workflow_source,
    missing_final_decision_review_workflow_source,
)


NOW = datetime(2026, 7, 30, 7, 0, tzinfo=timezone.utc)
ACCOUNT = AccountReference(masked_id="****1234")
OTHER_ACCOUNT = AccountReference(masked_id="****9876")


class _FakeProducer:
    def __init__(self, *, published: bool = True) -> None:
        self.calls = 0
        self.published = published

    def produce(self, **_: object) -> FinalDecisionReviewWorkflowProducerResultV1:
        self.calls += 1
        return FinalDecisionReviewWorkflowProducerResultV1.model_construct(
            status=(
                FinalDecisionReviewWorkflowProducerStatus.PUBLISHED
                if self.published
                else FinalDecisionReviewWorkflowProducerStatus.BLOCKED
            ),
            published=self.published,
            primary_blocker=(None if self.published else "producer_blocked"),
        )


def _risk(*, account: AccountReference = ACCOUNT, timestamp: datetime = NOW):
    return SimpleNamespace(
        metadata=SimpleNamespace(account=account, retrieved_at=timestamp)
    )


def _gate(
    *,
    account: AccountReference = ACCOUNT,
    timestamp: datetime = NOW,
    side: OrderSide = OrderSide.BUY,
):
    request = SimpleNamespace(side=side)
    return SimpleNamespace(
        assessed_at=timestamp,
        coverage=(
            SimpleNamespace(
                preview=SimpleNamespace(
                    metadata=SimpleNamespace(account=account)
                )
            ),
        ),
        base_intent_gate=SimpleNamespace(
            request=SimpleNamespace(expected_capacity_requests=(request,))
        ),
    )


def _available(
    slot: FinalDecisionReviewWorkflowSourceSlot,
    *,
    timestamp: datetime = NOW,
) -> FinalDecisionReviewWorkflowSourceEvidenceV1:
    return available_final_decision_review_workflow_source(
        slot=slot,
        observed_at=timestamp,
        provider="omni-cio",
        operation=f"load-{slot.value}",
    )


def _purchase_evidence(
    *,
    current_timestamp: datetime = NOW,
    pro_forma_timestamp: datetime = NOW,
    gate_timestamp: datetime = NOW,
):
    return (
        _available(
            FinalDecisionReviewWorkflowSourceSlot.PURCHASE_GATE,
            timestamp=gate_timestamp,
        ),
        missing_final_decision_review_workflow_source(
            FinalDecisionReviewWorkflowSourceSlot.SELL_GATE
        ),
        _available(
            FinalDecisionReviewWorkflowSourceSlot.CURRENT_RISK,
            timestamp=current_timestamp,
        ),
        _available(
            FinalDecisionReviewWorkflowSourceSlot.PRO_FORMA_RISK,
            timestamp=pro_forma_timestamp,
        ),
    )


def _coordinate(
    producer: _FakeProducer,
    *,
    evidence: tuple[FinalDecisionReviewWorkflowSourceEvidenceV1, ...] | None = None,
    current_risk: object | None = None,
    pro_forma_risk: object | None = None,
    purchase_gate: object | None = None,
    sell_gate: object | None = None,
    coordinated_at: datetime = NOW,
) -> FinalDecisionReviewWorkflowCoordinatorResultV1:
    coordinator = FinalDecisionReviewWorkflowCoordinatorV1(
        producer=producer,  # type: ignore[arg-type]
    )
    return coordinator.coordinate(
        scenario_id="scenario-coordinator-1",
        source_evidence=evidence or _purchase_evidence(),
        current_risk_evaluation=(
            current_risk if current_risk is not None else _risk()
        ),  # type: ignore[arg-type]
        pro_forma_risk_evaluation=(
            pro_forma_risk if pro_forma_risk is not None else _risk()
        ),  # type: ignore[arg-type]
        purchase_gate=(
            purchase_gate if purchase_gate is not None else _gate()
        ),  # type: ignore[arg-type]
        sell_gate=sell_gate,  # type: ignore[arg-type]
        correlation_id="corr:coordinator-0001",
        request_id="request:coordinator-0001",
        coordinated_at=coordinated_at,
    )


def test_complete_bundle_invokes_producer_once() -> None:
    producer = _FakeProducer()
    result = _coordinate(producer)

    assert producer.calls == 1
    assert result.status is FinalDecisionReviewWorkflowCoordinatorStatus.PUBLISHED
    assert result.completed_stage is FinalDecisionReviewWorkflowCoordinatorStage.PRODUCER
    assert result.published is True
    assert result.primary_blocker is None
    assert result.available_source_count == 3
    assert result.missing_source_count == 1
    assert result.failed_source_count == 0
    assert result.selected_direction_count == 1
    assert result.source_evidence_complete is True
    assert result.freshness_confirmed is True
    assert result.account_context_confirmed is True
    assert result.exact_direction_confirmed is True
    assert result.coordinator_performed_network_calls is False
    assert result.source_payloads_logged is False
    assert result.credentials_logged is False
    assert result.broker_write_called is False
    assert result.trade_authorized is False
    assert result.trading_methods is False


def test_missing_or_failed_source_does_not_invoke_producer() -> None:
    producer = _FakeProducer()
    missing_current = (
        _available(FinalDecisionReviewWorkflowSourceSlot.PURCHASE_GATE),
        missing_final_decision_review_workflow_source(
            FinalDecisionReviewWorkflowSourceSlot.SELL_GATE
        ),
        missing_final_decision_review_workflow_source(
            FinalDecisionReviewWorkflowSourceSlot.CURRENT_RISK
        ),
        _available(FinalDecisionReviewWorkflowSourceSlot.PRO_FORMA_RISK),
    )
    result = _coordinate(
        producer,
        evidence=missing_current,
        current_risk=SimpleNamespace(metadata=SimpleNamespace()),
    )
    assert producer.calls == 0
    assert result.completed_stage is FinalDecisionReviewWorkflowCoordinatorStage.SOURCE_EVIDENCE
    assert result.primary_blocker == (
        "FINAL_DECISION_REVIEW_WORKFLOW_SOURCE_EVIDENCE_INCOMPLETE"
    )

    failed = (
        _available(FinalDecisionReviewWorkflowSourceSlot.PURCHASE_GATE),
        missing_final_decision_review_workflow_source(
            FinalDecisionReviewWorkflowSourceSlot.SELL_GATE
        ),
        failed_final_decision_review_workflow_source(
            slot=FinalDecisionReviewWorkflowSourceSlot.CURRENT_RISK,
            error_code="CURRENT_RISK_LOAD_FAILED",
        ),
        _available(FinalDecisionReviewWorkflowSourceSlot.PRO_FORMA_RISK),
    )
    failed_result = _coordinate(producer, evidence=failed)
    assert producer.calls == 0
    assert failed_result.failed_source_count == 1
    assert failed_result.published is False


def test_stale_or_evidence_timestamp_mismatch_blocks_freshness() -> None:
    producer = _FakeProducer()
    stale_time = NOW - timedelta(hours=1)
    stale = _coordinate(
        producer,
        evidence=_purchase_evidence(current_timestamp=stale_time),
        current_risk=_risk(timestamp=stale_time),
    )
    assert producer.calls == 0
    assert stale.completed_stage is FinalDecisionReviewWorkflowCoordinatorStage.FRESHNESS
    assert stale.primary_blocker == "FINAL_DECISION_REVIEW_WORKFLOW_SOURCE_STALE"

    mismatch = _coordinate(
        producer,
        evidence=_purchase_evidence(current_timestamp=NOW - timedelta(seconds=1)),
        current_risk=_risk(timestamp=NOW),
    )
    assert producer.calls == 0
    assert mismatch.completed_stage is FinalDecisionReviewWorkflowCoordinatorStage.FRESHNESS


def test_account_and_direction_mismatch_block_before_producer() -> None:
    producer = _FakeProducer()
    account = _coordinate(
        producer,
        pro_forma_risk=_risk(account=OTHER_ACCOUNT),
    )
    assert producer.calls == 0
    assert account.completed_stage is FinalDecisionReviewWorkflowCoordinatorStage.ACCOUNT_CONTEXT
    assert account.primary_blocker == "FINAL_DECISION_REVIEW_WORKFLOW_ACCOUNT_MISMATCH"

    direction = _coordinate(
        producer,
        purchase_gate=_gate(side=OrderSide.SELL),
    )
    assert producer.calls == 0
    assert direction.primary_blocker == "FINAL_DECISION_REVIEW_WORKFLOW_DIRECTION_MISMATCH"
    assert direction.exact_direction_confirmed is False


def test_artifact_and_evidence_correspondence_is_required() -> None:
    producer = _FakeProducer()
    evidence = _purchase_evidence()
    result = _coordinate(
        producer,
        evidence=evidence,
        purchase_gate=SimpleNamespace(),
        sell_gate=_gate(side=OrderSide.SELL),
    )
    assert producer.calls == 0
    assert result.selected_direction_count == 2
    assert result.source_evidence_complete is False


def test_duplicate_incomplete_and_naive_inputs_fail_closed() -> None:
    producer = _FakeProducer()
    duplicate = (
        _available(FinalDecisionReviewWorkflowSourceSlot.PURCHASE_GATE),
        _available(FinalDecisionReviewWorkflowSourceSlot.PURCHASE_GATE),
        _available(FinalDecisionReviewWorkflowSourceSlot.CURRENT_RISK),
        _available(FinalDecisionReviewWorkflowSourceSlot.PRO_FORMA_RISK),
    )
    with pytest.raises(
        FinalDecisionReviewWorkflowCoordinatorError,
        match="FINAL_DECISION_REVIEW_WORKFLOW_COORDINATOR_DUPLICATE_SOURCE",
    ):
        _coordinate(producer, evidence=duplicate)

    with pytest.raises(
        FinalDecisionReviewWorkflowCoordinatorError,
        match="FINAL_DECISION_REVIEW_WORKFLOW_COORDINATOR_SOURCE_SET_INCOMPLETE",
    ):
        _coordinate(producer, evidence=_purchase_evidence()[:3])

    with pytest.raises(
        FinalDecisionReviewWorkflowCoordinatorError,
        match="FINAL_DECISION_REVIEW_WORKFLOW_COORDINATOR_TIMESTAMP_MUST_BE_AWARE",
    ):
        _coordinate(producer, coordinated_at=NOW.replace(tzinfo=None))


def test_source_evidence_and_result_tampering_are_rejected() -> None:
    with pytest.raises(ValidationError):
        FinalDecisionReviewWorkflowSourceEvidenceV1(
            slot=FinalDecisionReviewWorkflowSourceSlot.CURRENT_RISK,
            status=FinalDecisionReviewWorkflowSourceStatus.AVAILABLE,
        )

    producer = _FakeProducer()
    result = _coordinate(producer)
    payload = result.model_dump(mode="python")
    payload["trade_authorized"] = True
    with pytest.raises(ValidationError):
        FinalDecisionReviewWorkflowCoordinatorResultV1.model_validate(payload)


def test_blocked_producer_is_preserved() -> None:
    producer = _FakeProducer(published=False)
    result = _coordinate(producer)

    assert producer.calls == 1
    assert result.status is FinalDecisionReviewWorkflowCoordinatorStatus.BLOCKED
    assert result.completed_stage is FinalDecisionReviewWorkflowCoordinatorStage.PRODUCER
    assert result.primary_blocker == "producer_blocked"
    assert result.published is False
