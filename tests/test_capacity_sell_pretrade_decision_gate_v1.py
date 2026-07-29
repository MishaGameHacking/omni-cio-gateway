from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.capacity import (
    CapacityAssessmentV1,
    CapacityMetricsV1,
    CapacityOrderRequestV1,
    OrderSide,
)
from omni_cio.contracts.v1.common import (
    AccountReference,
    Completeness,
    ContractMetadata,
    DataQuality,
    Money,
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
from omni_cio.contracts.v1.decision_capacity import CapacityDecisionGateStatus
from omni_cio.contracts.v1.decision_capacity_intent import (
    CapacityIntentDecisionGateRequestV1,
)
from omni_cio.contracts.v1.decision_capacity_sell_pretrade import (
    CapacitySellPreTradeDecisionGateBlocker,
    CapacitySellPreTradeDecisionGateV1,
    CapacitySellPreTradeDecisionGateWarning,
    CapacitySellPreTradeMismatch,
)
from omni_cio.contracts.v1.pretrade import PreviewFreshnessStatus
from omni_cio.contracts.v1.sell_pretrade import (
    SellPreTradeBlocker,
    SellPreTradePreviewV1,
    SellPreviewPriceBasis,
)
from omni_cio.decision.capacity_intent_gate_v1 import (
    apply_capacity_intent_decision_gate,
)
from omni_cio.decision.capacity_sell_pretrade_gate_v1 import (
    CapacitySellPreTradeDecisionGateError,
    apply_capacity_sell_pretrade_decision_gate,
)


NOW = datetime(2026, 7, 29, 20, 30, tzinfo=timezone.utc)
KEY = "uid:sell-pretrade-a"
SECOND_KEY = "uid:sell-pretrade-b"


def _metadata(schema_name: str, *, retrieved_at: datetime = NOW) -> ContractMetadata:
    return ContractMetadata(
        schema_name=schema_name,
        retrieved_at=retrieved_at,
        account=AccountReference(masked_id="****1234"),
        provenance=(
            SourceReference(
                provider="omni-cio",
                operation="capacity-sell-pretrade-test",
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
            evidence_id="source.sell-pretrade",
            kind=DecisionEvidenceKind.FACT,
            statement="Verified capacity/sell-pretrade fixture.",
            source_schema="test_source",
        ),
    )
    evidence_ids = ("source.sell-pretrade",)
    return DecisionSetV1(
        metadata=_metadata("decision_set", retrieved_at=retrieved_at),
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
                rationale="Review a bounded change.",
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
    quantity_lots: int = 1,
    reference_price: Decimal = Decimal("98"),
    side: OrderSide = OrderSide.SELL,
) -> CapacityOrderRequestV1:
    lot_size = 1
    units = quantity_lots * lot_size
    return CapacityOrderRequestV1(
        request_id=f"capacity-{instrument_key}",
        instrument_key=instrument_key,
        side=side,
        currency="RUB",
        quantity_lots=quantity_lots,
        lot_size=lot_size,
        reference_price=reference_price,
        intended_execution_days=2,
        units=units,
        order_notional=Decimal(units) * reference_price,
    )


def _capacity(
    request: CapacityOrderRequestV1,
    *,
    assessed_at: datetime = NOW,
) -> CapacityAssessmentV1:
    metrics = CapacityMetricsV1.model_construct(
        safe_notional_for_requested_window=request.order_notional,
        safe_lots_for_requested_window=request.quantity_lots,
    )
    return CapacityAssessmentV1.model_construct(
        assessed_at=assessed_at,
        capacity_ready=True,
        request=request,
        metrics=metrics,
        blockers=(),
    )


def _intent_gate(
    expected_requests: tuple[CapacityOrderRequestV1, ...],
    actual_requests: tuple[CapacityOrderRequestV1, ...] | None = None,
):
    actual = actual_requests or expected_requests
    return apply_capacity_intent_decision_gate(
        _decision(),
        CapacityIntentDecisionGateRequestV1(
            gate_id="capacity-sell-pretrade-gate-1",
            requested_option_id="option.limited_change",
            expected_capacity_requests=expected_requests,
        ),
        tuple(_capacity(row) for row in actual),
        assessed_at=NOW,
    )


def _sell_preview(
    instrument_key: str = KEY,
    *,
    evaluated_at: datetime = NOW,
    ready: bool = True,
) -> SellPreTradePreviewV1:
    blockers = () if ready else (SellPreTradeBlocker.POSITION_INSUFFICIENT,)
    return SellPreTradePreviewV1(
        metadata=_metadata("sell_pretrade_preview", retrieved_at=evaluated_at),
        stable_key=instrument_key,
        instrument_uid=instrument_key.removeprefix("uid:"),
        currency="RUB",
        price_basis=SellPreviewPriceBasis.BEST_BID,
        price_source="t-invest-best-bid",
        price_time=evaluated_at,
        evaluated_at=evaluated_at,
        price_age_seconds=Decimal("0"),
        max_price_age_seconds=Decimal("120"),
        freshness_status=PreviewFreshnessStatus.FRESH,
        unit_price=Decimal("98"),
        lot_size=1,
        quantity_lots=1,
        quantity_units=1,
        position_lots=5,
        sell_max_lots=5,
        conflicting_open_sell_lots=0,
        available_after_open_orders_lots=5,
        remaining_position_lots=4,
        current_position_value=Money(amount=Decimal("500"), currency="RUB"),
        sold_position_value=Money(amount=Decimal("100"), currency="RUB"),
        gross_security_proceeds=Money(amount=Decimal("98"), currency="RUB"),
        accrued_interest_proceeds=Money(amount=Decimal("2"), currency="RUB"),
        gross_proceeds=Money(amount=Decimal("100"), currency="RUB"),
        canonical_commission=Money(amount=Decimal("1"), currency="RUB"),
        estimated_tax=Money(amount=Decimal("4"), currency="RUB"),
        net_proceeds=Money(amount=Decimal("95"), currency="RUB"),
        estimated_post_sale_position_value=Money(
            amount=Decimal("400"),
            currency="RUB",
        ),
        estimated_portfolio_value_before=Money(
            amount=Decimal("1000"),
            currency="RUB",
        ),
        estimated_portfolio_value_after=Money(
            amount=Decimal("995"),
            currency="RUB",
        ),
        current_weight=Decimal("0.5"),
        lower_weight=Decimal("0.35"),
        target_weight=Decimal("0.4"),
        upper_weight=Decimal("0.45"),
        estimated_post_sale_weight=Decimal("400") / Decimal("995"),
        reduction_value_limit=Money(amount=Decimal("100"), currency="RUB"),
        tax_basis_confirmed=True,
        open_orders_checked=True,
        position_availability_confirmed=ready,
        source_complete=True,
        integrity_confirmed=True,
        blockers=blockers,
        preview_ready=ready,
    )


def test_ready_sell_preview_completes_capacity_review_without_execution() -> None:
    request = _order_request()
    result = apply_capacity_sell_pretrade_decision_gate(
        _intent_gate((request,)),
        (_sell_preview(),),
        assessed_at=NOW,
    )

    assert result.status is CapacityDecisionGateStatus.READY
    assert result.gate_ready is True
    assert result.abstain is False
    assert result.final_option_id == "option.limited_change"
    assert result.final_action is DecisionAction.REVIEW_LIMITED_CHANGE
    assert result.required_preview_count == 1
    assert result.preview_coverage_count == 1
    assert result.preview_ready_count == 1
    assert result.exact_match_count == 1
    assert result.coverage[0].exact_match is True
    assert result.broker_preview_checked is True
    assert result.position_availability_checked is True
    assert result.open_orders_checked is True
    assert result.tax_basis_checked is True
    assert result.commission_integrity_checked is True
    assert result.net_proceeds_recomputed_by_gate is False
    assert result.order_created is False
    assert result.execution_ready is False
    assert result.trading_methods is False
    assert (
        CapacitySellPreTradeDecisionGateWarning.BROKER_NET_PROCEEDS_NOT_RECOMPUTED_BY_GATE
        in result.warnings
    )


def test_unready_sell_preview_forces_no_action() -> None:
    request = _order_request()
    result = apply_capacity_sell_pretrade_decision_gate(
        _intent_gate((request,)),
        (_sell_preview(ready=False),),
        assessed_at=NOW,
    )

    assert result.status is CapacityDecisionGateStatus.ABSTAIN
    assert result.final_option_id == "option.no_action"
    assert result.final_action is DecisionAction.WAIT_FOR_DATA
    assert (
        CapacitySellPreTradeDecisionGateBlocker.PREVIEW_NOT_READY
        in result.blockers
    )
    assert (
        CapacitySellPreTradeDecisionGateBlocker.POSITION_AVAILABILITY_UNCONFIRMED
        in result.blockers
    )


def test_buy_intent_cannot_use_sell_preview() -> None:
    request = _order_request(side=OrderSide.BUY)
    result = apply_capacity_sell_pretrade_decision_gate(
        _intent_gate((request,)),
        (_sell_preview(),),
        assessed_at=NOW,
    )

    assert result.coverage[0].mismatch_fields == (
        CapacitySellPreTradeMismatch.SIDE,
    )
    assert result.abstain is True


def test_quantity_and_price_substitution_are_explicit_mismatches() -> None:
    request = _order_request(
        quantity_lots=2,
        reference_price=Decimal("99"),
    )
    result = apply_capacity_sell_pretrade_decision_gate(
        _intent_gate((request,)),
        (_sell_preview(),),
        assessed_at=NOW,
    )

    assert (
        CapacitySellPreTradeDecisionGateBlocker.PREVIEW_INTENT_MISMATCH
        in result.blockers
    )
    assert result.coverage[0].mismatch_fields == (
        CapacitySellPreTradeMismatch.QUANTITY_LOTS,
        CapacitySellPreTradeMismatch.REFERENCE_PRICE,
    )
    assert result.abstain is True


def test_stale_and_future_sell_previews_force_abstain() -> None:
    request = _order_request()
    stale = apply_capacity_sell_pretrade_decision_gate(
        _intent_gate((request,)),
        (_sell_preview(evaluated_at=NOW - timedelta(minutes=10)),),
        assessed_at=NOW,
    )
    assert CapacitySellPreTradeDecisionGateBlocker.PREVIEW_STALE in stale.blockers

    future = apply_capacity_sell_pretrade_decision_gate(
        _intent_gate((request,)),
        (_sell_preview(evaluated_at=NOW + timedelta(minutes=10)),),
        assessed_at=NOW,
    )
    assert (
        CapacitySellPreTradeDecisionGateBlocker.PREVIEW_FROM_FUTURE
        in future.blockers
    )


def test_missing_multi_instrument_sell_preview_is_explicit() -> None:
    first = _order_request(KEY)
    second = _order_request(SECOND_KEY)
    result = apply_capacity_sell_pretrade_decision_gate(
        _intent_gate((first, second)),
        (_sell_preview(KEY),),
        assessed_at=NOW,
    )

    assert (
        CapacitySellPreTradeDecisionGateBlocker.PREVIEW_COVERAGE_INCOMPLETE
        in result.blockers
    )
    assert result.required_preview_count == 2
    assert result.preview_coverage_count == 1
    assert result.broker_preview_checked is False
    assert result.position_availability_checked is False
    assert result.tax_basis_checked is False
    assert result.abstain is True


def test_blocked_intent_gate_cannot_be_upgraded_by_ready_sell_preview() -> None:
    expected = _order_request(quantity_lots=2)
    actual = _order_request(quantity_lots=1)
    intent_gate = _intent_gate((expected,), (actual,))
    assert intent_gate.gate_ready is False

    result = apply_capacity_sell_pretrade_decision_gate(
        intent_gate,
        (_sell_preview(),),
        assessed_at=NOW,
    )
    assert (
        CapacitySellPreTradeDecisionGateBlocker.BASE_INTENT_GATE_NOT_READY
        in result.blockers
    )
    assert result.abstain is True


def test_duplicate_unrequested_and_naive_inputs_raise_structural_errors() -> None:
    request = _order_request()
    intent_gate = _intent_gate((request,))
    preview = _sell_preview()

    with pytest.raises(
        CapacitySellPreTradeDecisionGateError,
        match="DUPLICATE_SELL_PRETRADE_PREVIEW_INSTRUMENT",
    ):
        apply_capacity_sell_pretrade_decision_gate(
            intent_gate,
            (preview, preview),
            assessed_at=NOW,
        )

    with pytest.raises(
        CapacitySellPreTradeDecisionGateError,
        match="UNREQUESTED_SELL_PRETRADE_PREVIEW_INSTRUMENT",
    ):
        apply_capacity_sell_pretrade_decision_gate(
            intent_gate,
            (_sell_preview(SECOND_KEY),),
            assessed_at=NOW,
        )

    with pytest.raises(
        CapacitySellPreTradeDecisionGateError,
        match="CAPACITY_SELL_PRETRADE_GATE_TIMESTAMP_MUST_BE_AWARE",
    ):
        apply_capacity_sell_pretrade_decision_gate(
            intent_gate,
            (preview,),
            assessed_at=NOW.replace(tzinfo=None),
        )


def test_contract_rejects_blocked_result_with_change_option() -> None:
    request = _order_request()
    result = apply_capacity_sell_pretrade_decision_gate(
        _intent_gate((request,)),
        (_sell_preview(ready=False),),
        assessed_at=NOW,
    )
    payload = result.model_dump(mode="python")
    payload["final_option_id"] = "option.limited_change"

    with pytest.raises(ValidationError):
        CapacitySellPreTradeDecisionGateV1.model_validate(payload)
