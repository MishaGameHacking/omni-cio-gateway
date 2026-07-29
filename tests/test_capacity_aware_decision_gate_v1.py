from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.capacity import (
    CapacityEvidenceV1,
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
    DecisionBlocker,
    DecisionConfidence,
    DecisionEvidenceKind,
    DecisionEvidenceV1,
    DecisionOptionKind,
    DecisionOptionStatus,
    DecisionOptionV1,
    DecisionSetV1,
)
from omni_cio.contracts.v1.decision_capacity import (
    CapacityDecisionGateBlocker,
    CapacityDecisionGatePolicyV1,
    CapacityDecisionGateRequestV1,
    CapacityDecisionGateStatus,
    CapacityDecisionGateV1,
    CapacityDecisionGateWarning,
)
from omni_cio.contracts.v1.market import (
    MarketAssessmentStatus,
    MarketReadinessAssessmentV1,
    MarketSourceV1,
    SourceAuthority,
)
from omni_cio.decision.capacity_gate_v1 import (
    CapacityDecisionGateError,
    apply_capacity_decision_gate,
)
from omni_cio.market.capacity_v1 import assess_market_capacity


NOW = datetime(2026, 7, 29, 16, 30, tzinfo=timezone.utc)
KEY = "uid:capacity-gate-a"
SECOND_KEY = "uid:capacity-gate-b"


def _metadata(*, retrieved_at: datetime = NOW, verified: bool = True) -> ContractMetadata:
    return ContractMetadata(
        schema_name="decision_set",
        retrieved_at=retrieved_at,
        account=AccountReference(masked_id="****1234"),
        provenance=(
            SourceReference(
                provider="omni-cio",
                operation="test-decision",
                retrieved_at=retrieved_at,
                source_id="1.0",
            ),
        ),
        quality=QualityMetadata(
            quality=DataQuality.VERIFIED if verified else DataQuality.PARTIAL,
            completeness=Completeness.COMPLETE if verified else Completeness.PARTIAL,
        ),
    )


def _decision(
    *,
    ready: bool = True,
    preferred_kind: DecisionOptionKind = DecisionOptionKind.LIMITED_CHANGE,
    retrieved_at: datetime = NOW,
    limited_blocked: bool = False,
) -> DecisionSetV1:
    evidence = (
        DecisionEvidenceV1(
            evidence_id="source.test",
            kind=DecisionEvidenceKind.FACT,
            statement="Verified decision fixture.",
            source_schema="test_source",
        ),
    )
    evidence_ids = ("source.test",)
    if not ready:
        blockers = (DecisionBlocker.MARKET_NOT_READY,)
        return DecisionSetV1(
            metadata=_metadata(retrieved_at=retrieved_at, verified=False),
            evidence=evidence,
            options=(
                DecisionOptionV1(
                    option_id="option.no_action",
                    kind=DecisionOptionKind.NO_ACTION,
                    status=DecisionOptionStatus.PREFERRED,
                    action=DecisionAction.WAIT_FOR_DATA,
                    title="Wait",
                    rationale="A base gate is open.",
                    confidence=DecisionConfidence.LOW,
                    evidence_ids=evidence_ids,
                ),
                DecisionOptionV1(
                    option_id="option.limited_change",
                    kind=DecisionOptionKind.LIMITED_CHANGE,
                    status=DecisionOptionStatus.BLOCKED,
                    action=DecisionAction.REVIEW_LIMITED_CHANGE,
                    title="Limited",
                    rationale="Blocked by base decision.",
                    confidence=DecisionConfidence.LOW,
                    evidence_ids=evidence_ids,
                    blockers=blockers,
                ),
                DecisionOptionV1(
                    option_id="option.strategic_rebalance",
                    kind=DecisionOptionKind.STRATEGIC_REBALANCE,
                    status=DecisionOptionStatus.BLOCKED,
                    action=DecisionAction.REVIEW_STRATEGIC_REBALANCE,
                    title="Strategic",
                    rationale="Blocked by base decision.",
                    confidence=DecisionConfidence.LOW,
                    evidence_ids=evidence_ids,
                    blockers=blockers,
                ),
            ),
            preferred_option_id="option.no_action",
            abstain=True,
            recommendation_ready=False,
            confidence=DecisionConfidence.LOW,
            global_blockers=blockers,
            accepted_news_count=0,
            context_news_count=0,
            rejected_news_count=0,
            required_market_count=1,
            market_coverage_count=0,
        )

    limited_status = (
        DecisionOptionStatus.BLOCKED
        if limited_blocked
        else DecisionOptionStatus.PREFERRED
        if preferred_kind is DecisionOptionKind.LIMITED_CHANGE
        else DecisionOptionStatus.AVAILABLE
    )
    limited_blockers = (
        (DecisionBlocker.REBALANCING_ENGINE_NOT_AVAILABLE,)
        if limited_blocked
        else ()
    )
    no_action_status = (
        DecisionOptionStatus.PREFERRED
        if preferred_kind is DecisionOptionKind.NO_ACTION
        else DecisionOptionStatus.AVAILABLE
    )
    preferred_id = (
        "option.no_action"
        if preferred_kind is DecisionOptionKind.NO_ACTION
        else "option.limited_change"
    )
    return DecisionSetV1(
        metadata=_metadata(retrieved_at=retrieved_at),
        evidence=evidence,
        options=(
            DecisionOptionV1(
                option_id="option.no_action",
                kind=DecisionOptionKind.NO_ACTION,
                status=no_action_status,
                action=DecisionAction.HOLD,
                title="Hold",
                rationale="Holding remains available.",
                confidence=DecisionConfidence.MEDIUM,
                evidence_ids=evidence_ids,
            ),
            DecisionOptionV1(
                option_id="option.limited_change",
                kind=DecisionOptionKind.LIMITED_CHANGE,
                status=limited_status,
                action=DecisionAction.REVIEW_LIMITED_CHANGE,
                title="Limited",
                rationale="Review a bounded change.",
                confidence=DecisionConfidence.MEDIUM,
                evidence_ids=evidence_ids,
                blockers=limited_blockers,
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
        preferred_option_id=preferred_id,
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


def _source(*, retrieved_at: datetime = NOW) -> MarketSourceV1:
    return MarketSourceV1(
        provider="capacity-gate-source",
        authority=SourceAuthority.OFFICIAL,
        retrieved_at=retrieved_at,
        source_id="capacity-gate-v1",
    )


def _market_ready() -> MarketReadinessAssessmentV1:
    return MarketReadinessAssessmentV1(
        assessed_at=NOW,
        status=MarketAssessmentStatus.READY,
        decision_ready=True,
        stale_components=(),
        missing_components=(),
        untrusted_components=(),
    )


def _capacity(
    instrument_key: str = KEY,
    *,
    quantity_lots: int = 100,
    execution_days: int = 2,
    assessed_at: datetime = NOW,
):
    lot_size = 10
    price = Decimal("100")
    units = quantity_lots * lot_size
    request = CapacityOrderRequestV1(
        request_id=f"capacity-{instrument_key}",
        instrument_key=instrument_key,
        side=OrderSide.BUY,
        currency="RUB",
        quantity_lots=quantity_lots,
        lot_size=lot_size,
        reference_price=price,
        intended_execution_days=execution_days,
        units=units,
        order_notional=Decimal(units) * price,
    )
    evidence = CapacityEvidenceV1(
        instrument_key=instrument_key,
        currency="RUB",
        lot_size=lot_size,
        as_of=assessed_at,
        source=_source(retrieved_at=assessed_at),
        venue="MOEX",
        reference_price=price,
        spread_bps=Decimal("20"),
        top_of_book_depth_notional=Decimal("1000000"),
        average_daily_turnover_notional=Decimal("10000000"),
        median_daily_turnover_notional=Decimal("8000000"),
        turnover_history_days=30,
        daily_return_volatility=Decimal("0.02"),
    )
    return assess_market_capacity(
        request,
        evidence,
        _market_ready(),
        assessed_at=assessed_at,
    )


def _request(
    *,
    option_id: str = "option.limited_change",
    keys: tuple[str, ...] = (KEY,),
) -> CapacityDecisionGateRequestV1:
    return CapacityDecisionGateRequestV1(
        gate_id="capacity-gate-1",
        requested_option_id=option_id,
        required_instrument_keys=keys,
    )


def test_ready_capacity_allows_review_without_changing_base_preference() -> None:
    decision = _decision(preferred_kind=DecisionOptionKind.NO_ACTION)
    result = apply_capacity_decision_gate(
        decision,
        _request(),
        (_capacity(),),
        assessed_at=NOW,
    )

    assert result.status is CapacityDecisionGateStatus.READY
    assert result.gate_ready is True
    assert result.abstain is False
    assert result.base_preferred_option_id == "option.no_action"
    assert result.final_option_id == "option.limited_change"
    assert result.final_action is DecisionAction.REVIEW_LIMITED_CHANGE
    assert result.required_capacity_count == 1
    assert result.capacity_coverage_count == 1
    assert result.capacity_ready_count == 1
    assert result.coverage[0].safe_notional >= result.coverage[0].order_notional
    assert CapacityDecisionGateWarning.CAPACITY_GATE_DOES_NOT_SELECT_OPTION in result.warnings
    assert result.option_selected_by_gate is False
    assert result.order_created is False
    assert result.trading_methods is False


def test_failed_capacity_forces_abstain_and_no_action() -> None:
    result = apply_capacity_decision_gate(
        _decision(),
        _request(),
        (_capacity(quantity_lots=2000, execution_days=1),),
        assessed_at=NOW,
    )

    assert result.status is CapacityDecisionGateStatus.ABSTAIN
    assert result.abstain is True
    assert result.final_option_id == "option.no_action"
    assert result.final_action is DecisionAction.WAIT_FOR_DATA
    assert CapacityDecisionGateBlocker.CAPACITY_NOT_READY in result.blockers
    assert result.capacity_ready_count == 0
    assert result.coverage[0].capacity_blockers


def test_missing_multi_instrument_capacity_is_explicit_coverage_blocker() -> None:
    result = apply_capacity_decision_gate(
        _decision(),
        _request(keys=(KEY, SECOND_KEY)),
        (_capacity(KEY),),
        assessed_at=NOW,
    )

    assert CapacityDecisionGateBlocker.CAPACITY_COVERAGE_INCOMPLETE in result.blockers
    assert result.required_capacity_count == 2
    assert result.capacity_coverage_count == 1
    assert result.abstain is True


def test_base_decision_readiness_and_option_state_are_gated() -> None:
    base_blocked = apply_capacity_decision_gate(
        _decision(ready=False),
        _request(),
        (_capacity(),),
        assessed_at=NOW,
    )
    assert CapacityDecisionGateBlocker.BASE_DECISION_NOT_READY in base_blocked.blockers

    no_action = apply_capacity_decision_gate(
        _decision(preferred_kind=DecisionOptionKind.NO_ACTION),
        _request(option_id="option.no_action"),
        (_capacity(),),
        assessed_at=NOW,
    )
    assert CapacityDecisionGateBlocker.REQUESTED_OPTION_NO_ACTION in no_action.blockers

    blocked_option = apply_capacity_decision_gate(
        _decision(
            preferred_kind=DecisionOptionKind.NO_ACTION,
            limited_blocked=True,
        ),
        _request(),
        (_capacity(),),
        assessed_at=NOW,
    )
    assert CapacityDecisionGateBlocker.REQUESTED_OPTION_BLOCKED in blocked_option.blockers

    missing_option = apply_capacity_decision_gate(
        _decision(),
        _request(option_id="option.unknown"),
        (_capacity(),),
        assessed_at=NOW,
    )
    assert CapacityDecisionGateBlocker.REQUESTED_OPTION_NOT_FOUND in missing_option.blockers
    assert missing_option.requested_option_kind is None


def test_stale_and_future_base_or_capacity_assessment_force_abstain() -> None:
    base_stale = apply_capacity_decision_gate(
        _decision(retrieved_at=NOW - timedelta(minutes=10)),
        _request(),
        (_capacity(),),
        assessed_at=NOW,
    )
    assert CapacityDecisionGateBlocker.BASE_DECISION_STALE in base_stale.blockers

    capacity_stale = apply_capacity_decision_gate(
        _decision(),
        _request(),
        (_capacity(assessed_at=NOW - timedelta(minutes=10)),),
        policy=CapacityDecisionGatePolicyV1(
            base_decision_max_age_seconds=1000,
            capacity_max_age_seconds=300,
        ),
        assessed_at=NOW,
    )
    assert CapacityDecisionGateBlocker.CAPACITY_STALE in capacity_stale.blockers

    capacity_future = apply_capacity_decision_gate(
        _decision(),
        _request(),
        (_capacity(assessed_at=NOW + timedelta(minutes=10)),),
        assessed_at=NOW,
    )
    assert CapacityDecisionGateBlocker.CAPACITY_FROM_FUTURE in capacity_future.blockers


def test_duplicate_and_unrequested_capacity_inputs_raise_structural_error() -> None:
    capacity = _capacity()
    with pytest.raises(
        CapacityDecisionGateError,
        match="DUPLICATE_CAPACITY_ASSESSMENT_INSTRUMENT",
    ):
        apply_capacity_decision_gate(
            _decision(),
            _request(),
            (capacity, capacity),
            assessed_at=NOW,
        )

    with pytest.raises(
        CapacityDecisionGateError,
        match="UNREQUESTED_CAPACITY_ASSESSMENT_INSTRUMENT",
    ):
        apply_capacity_decision_gate(
            _decision(),
            _request(),
            (_capacity(SECOND_KEY),),
            assessed_at=NOW,
        )


def test_request_result_counts_and_safety_flags_are_tamper_resistant() -> None:
    with pytest.raises(ValidationError, match="must be unique"):
        _request(keys=(KEY, KEY))

    result = apply_capacity_decision_gate(
        _decision(),
        _request(),
        (_capacity(),),
        assessed_at=NOW,
    )
    payload = result.model_dump()
    payload["capacity_ready_count"] = 99
    with pytest.raises(ValidationError, match="ready count"):
        CapacityDecisionGateV1.model_validate(payload)

    payload = result.model_dump()
    payload["final_action"] = DecisionAction.WAIT_FOR_DATA
    with pytest.raises(ValidationError, match="changed requested action"):
        CapacityDecisionGateV1.model_validate(payload)

    payload = result.model_dump()
    payload["trading_methods"] = True
    with pytest.raises(ValidationError):
        CapacityDecisionGateV1.model_validate(payload)


def test_naive_gate_timestamp_is_rejected() -> None:
    with pytest.raises(
        CapacityDecisionGateError,
        match="CAPACITY_DECISION_GATE_TIMESTAMP_MUST_BE_AWARE",
    ):
        apply_capacity_decision_gate(
            _decision(),
            _request(),
            (_capacity(),),
            assessed_at=datetime(2026, 7, 29, 16, 30),
        )
