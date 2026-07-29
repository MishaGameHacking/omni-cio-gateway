from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.capacity import (
    CapacityAssessmentV1,
    CapacityBlocker,
    CapacityMetricsV1,
    CapacityOrderRequestV1,
    OrderSide,
)
from omni_cio.contracts.v1.common import (
    AccountReference,
    Completeness,
    ContractMetadata,
    DataQuality,
    QualityMetadata,
    SourceReference,
)
from omni_cio.contracts.v1.decision import (
    DecisionAction,
    DecisionConfidence,
    DecisionEvidenceKind,
    DecisionEvidenceV1,
    DecisionOptionKind,
    DecisionOptionStatus,
    DecisionOptionV1,
    DecisionSetV1,
)
from omni_cio.contracts.v1.decision_capacity import (
    CapacityDecisionGateStatus,
)
from omni_cio.contracts.v1.decision_capacity_intent import (
    CapacityIntentDecisionGateBlocker,
    CapacityIntentDecisionGateRequestV1,
    CapacityIntentDecisionGateV1,
    CapacityIntentDecisionGateWarning,
    CapacityIntentMismatch,
)
from omni_cio.decision.capacity_intent_gate_v1 import (
    CapacityIntentDecisionGateError,
    apply_capacity_intent_decision_gate,
)


NOW = datetime(2026, 7, 29, 18, 0, tzinfo=timezone.utc)
KEY = "uid:intent-a"
SECOND_KEY = "uid:intent-b"


def _metadata(*, retrieved_at: datetime = NOW) -> ContractMetadata:
    return ContractMetadata(
        schema_name="decision_set",
        retrieved_at=retrieved_at,
        account=AccountReference(masked_id="****1234"),
        provenance=(
            SourceReference(
                provider="omni-cio",
                operation="capacity-intent-test",
                retrieved_at=retrieved_at,
                source_id="1.0",
            ),
        ),
        quality=QualityMetadata(
            quality=DataQuality.VERIFIED,
            completeness=Completeness.COMPLETE,
        ),
    )


def _decision(*, retrieved_at: datetime = NOW) -> DecisionSetV1:
    evidence = (
        DecisionEvidenceV1(
            evidence_id="source.intent",
            kind=DecisionEvidenceKind.FACT,
            statement="Verified exact-intent fixture.",
            source_schema="test_source",
        ),
    )
    evidence_ids = ("source.intent",)
    return DecisionSetV1(
        metadata=_metadata(retrieved_at=retrieved_at),
        evidence=evidence,
        options=(
            DecisionOptionV1(
                option_id="option.no_action",
                kind=DecisionOptionKind.NO_ACTION,
                status=DecisionOptionStatus.AVAILABLE,
                action=DecisionAction.HOLD,
                title="Hold",
                rationale="No action remains available.",
                confidence=DecisionConfidence.MEDIUM,
                evidence_ids=evidence_ids,
            ),
            DecisionOptionV1(
                option_id="option.limited_change",
                kind=DecisionOptionKind.LIMITED_CHANGE,
                status=DecisionOptionStatus.PREFERRED,
                action=DecisionAction.REVIEW_LIMITED_CHANGE,
                title="Limited",
                rationale="Review one bounded analytical change.",
                confidence=DecisionConfidence.MEDIUM,
                evidence_ids=evidence_ids,
            ),
            DecisionOptionV1(
                option_id="option.strategic_rebalance",
                kind=DecisionOptionKind.STRATEGIC_REBALANCE,
                status=DecisionOptionStatus.REVIEW_ONLY,
                action=DecisionAction.REVIEW_STRATEGIC_REBALANCE,
                title="Strategic",
                rationale="Review only.",
                confidence=DecisionConfidence.MEDIUM,
                evidence_ids=evidence_ids,
            ),
        ),
        preferred_option_id="option.limited_change",
        abstain=False,
        recommendation_ready=True,
        confidence=DecisionConfidence.MEDIUM,
        global_blockers=(),
        accepted_news_count=0,
        context_news_count=0,
        rejected_news_count=0,
        required_market_count=1,
        market_coverage_count=1,
    )


def _order_request(
    instrument_key: str = KEY,
    *,
    request_id: str | None = None,
    side: OrderSide = OrderSide.BUY,
    quantity_lots: int = 10,
    intended_execution_days: int = 2,
) -> CapacityOrderRequestV1:
    lot_size = 10
    reference_price = Decimal("100")
    units = quantity_lots * lot_size
    return CapacityOrderRequestV1(
        request_id=request_id or f"capacity-{instrument_key}",
        instrument_key=instrument_key,
        side=side,
        currency="RUB",
        quantity_lots=quantity_lots,
        lot_size=lot_size,
        reference_price=reference_price,
        intended_execution_days=intended_execution_days,
        units=units,
        order_notional=Decimal(units) * reference_price,
    )


def _capacity(
    request: CapacityOrderRequestV1,
    *,
    ready: bool = True,
    assessed_at: datetime = NOW,
) -> CapacityAssessmentV1:
    blockers = () if ready else (CapacityBlocker.ZERO_SAFE_CAPACITY,)
    safe_notional = request.order_notional if ready else Decimal("0")
    safe_lots = request.quantity_lots if ready else 0
    metrics = CapacityMetricsV1.model_construct(
        safe_notional_for_requested_window=safe_notional,
        safe_lots_for_requested_window=safe_lots,
    )
    return CapacityAssessmentV1.model_construct(
        assessed_at=assessed_at,
        capacity_ready=ready,
        request=request,
        metrics=metrics,
        blockers=blockers,
    )


def _gate_request(
    *expected: CapacityOrderRequestV1,
) -> CapacityIntentDecisionGateRequestV1:
    return CapacityIntentDecisionGateRequestV1(
        gate_id="capacity-intent-gate-1",
        requested_option_id="option.limited_change",
        expected_capacity_requests=tuple(expected),
    )


def test_exact_capacity_request_binding_allows_review_only() -> None:
    expected = _order_request()
    result = apply_capacity_intent_decision_gate(
        _decision(),
        _gate_request(expected),
        (_capacity(expected),),
        assessed_at=NOW,
    )

    assert result.status is CapacityDecisionGateStatus.READY
    assert result.gate_ready is True
    assert result.abstain is False
    assert result.final_option_id == "option.limited_change"
    assert result.final_action is DecisionAction.REVIEW_LIMITED_CHANGE
    assert result.required_intent_count == 1
    assert result.matched_intent_count == 1
    assert result.exact_match_count == 1
    assert result.coverage[0].exact_match is True
    assert result.coverage[0].mismatch_fields == ()
    assert result.base_gate.gate_ready is True
    assert result.affordability_checked is False
    assert result.broker_preview_checked is False
    assert result.order_created is False
    assert result.trading_methods is False
    assert (
        CapacityIntentDecisionGateWarning.EXACT_INTENT_BINDING_ONLY
        in result.warnings
    )


def test_quantity_and_notional_substitution_force_abstain() -> None:
    actual = _order_request(quantity_lots=10)
    expected = _order_request(
        request_id=actual.request_id,
        quantity_lots=20,
    )
    result = apply_capacity_intent_decision_gate(
        _decision(),
        _gate_request(expected),
        (_capacity(actual),),
        assessed_at=NOW,
    )

    assert result.status is CapacityDecisionGateStatus.ABSTAIN
    assert result.final_option_id == "option.no_action"
    assert result.final_action is DecisionAction.WAIT_FOR_DATA
    assert (
        CapacityIntentDecisionGateBlocker.CAPACITY_INTENT_MISMATCH
        in result.blockers
    )
    assert result.base_gate.gate_ready is True
    assert result.coverage[0].exact_match is False
    assert result.coverage[0].mismatch_fields == (
        CapacityIntentMismatch.QUANTITY_LOTS,
        CapacityIntentMismatch.UNITS,
        CapacityIntentMismatch.ORDER_NOTIONAL,
    )


def test_request_id_side_and_execution_window_are_bound_exactly() -> None:
    actual = _order_request(
        request_id="actual-request",
        side=OrderSide.BUY,
        intended_execution_days=1,
    )
    expected = _order_request(
        request_id="expected-request",
        side=OrderSide.SELL,
        intended_execution_days=3,
    )
    result = apply_capacity_intent_decision_gate(
        _decision(),
        _gate_request(expected),
        (_capacity(actual),),
        assessed_at=NOW,
    )

    assert result.coverage[0].mismatch_fields == (
        CapacityIntentMismatch.REQUEST_ID,
        CapacityIntentMismatch.SIDE,
        CapacityIntentMismatch.INTENDED_EXECUTION_DAYS,
    )
    assert result.abstain is True


def test_missing_intent_coverage_and_failed_capacity_remain_fail_closed() -> None:
    first = _order_request(KEY)
    second = _order_request(SECOND_KEY)
    missing = apply_capacity_intent_decision_gate(
        _decision(),
        _gate_request(first, second),
        (_capacity(first),),
        assessed_at=NOW,
    )

    assert (
        CapacityIntentDecisionGateBlocker.BASE_CAPACITY_GATE_NOT_READY
        in missing.blockers
    )
    assert (
        CapacityIntentDecisionGateBlocker.INTENT_COVERAGE_INCOMPLETE
        in missing.blockers
    )
    assert missing.required_intent_count == 2
    assert missing.matched_intent_count == 1
    assert missing.abstain is True

    failed = apply_capacity_intent_decision_gate(
        _decision(),
        _gate_request(first),
        (_capacity(first, ready=False),),
        assessed_at=NOW,
    )
    assert (
        CapacityIntentDecisionGateBlocker.BASE_CAPACITY_GATE_NOT_READY
        in failed.blockers
    )
    assert failed.coverage[0].capacity_ready is False
    assert failed.abstain is True


def test_stale_base_capacity_gate_is_not_upgraded_by_exact_binding() -> None:
    request = _order_request()
    result = apply_capacity_intent_decision_gate(
        _decision(),
        _gate_request(request),
        (
            _capacity(
                request,
                assessed_at=NOW - timedelta(minutes=10),
            ),
        ),
        assessed_at=NOW,
    )

    assert result.coverage[0].exact_match is True
    assert result.base_gate.gate_ready is False
    assert (
        CapacityIntentDecisionGateBlocker.BASE_CAPACITY_GATE_NOT_READY
        in result.blockers
    )
    assert result.abstain is True


def test_duplicate_capacity_and_naive_timestamp_raise_structural_errors() -> None:
    request = _order_request()
    capacity = _capacity(request)
    with pytest.raises(
        CapacityIntentDecisionGateError,
        match="DUPLICATE_CAPACITY_ASSESSMENT_INSTRUMENT",
    ):
        apply_capacity_intent_decision_gate(
            _decision(),
            _gate_request(request),
            (capacity, capacity),
            assessed_at=NOW,
        )

    with pytest.raises(
        CapacityIntentDecisionGateError,
        match="CAPACITY_INTENT_GATE_TIMESTAMP_MUST_BE_AWARE",
    ):
        apply_capacity_intent_decision_gate(
            _decision(),
            _gate_request(request),
            (capacity,),
            assessed_at=NOW.replace(tzinfo=None),
        )


def test_contract_rejects_tampered_blocked_final_option() -> None:
    actual = _order_request(quantity_lots=10)
    expected = _order_request(
        request_id=actual.request_id,
        quantity_lots=20,
    )
    result = apply_capacity_intent_decision_gate(
        _decision(),
        _gate_request(expected),
        (_capacity(actual),),
        assessed_at=NOW,
    )
    payload = result.model_dump(mode="python")
    payload["final_option_id"] = "option.limited_change"

    with pytest.raises(ValidationError):
        CapacityIntentDecisionGateV1.model_validate(payload)
