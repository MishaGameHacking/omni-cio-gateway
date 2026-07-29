from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.capacity import (
    CapacityOrderRequestV1,
    OrderSide,
)
from omni_cio.contracts.v1.decision import DecisionAction
from omni_cio.contracts.v1.decision_capacity import CapacityDecisionGateStatus
from omni_cio.contracts.v1.decision_capacity_directional_pretrade import (
    CapacityDirectionalPreTradeReviewBlocker,
    CapacityDirectionalPreTradeReviewV1,
    CapacityDirectionalPreTradeReviewWarning,
)
from omni_cio.contracts.v1.decision_capacity_intent import (
    CapacityIntentDecisionGateRequestV1,
    CapacityIntentDecisionGateV1,
)
from omni_cio.contracts.v1.decision_capacity_pretrade import (
    CapacityPreTradeDecisionGateV1,
)
from omni_cio.contracts.v1.decision_capacity_sell_pretrade import (
    CapacitySellPreTradeDecisionGateV1,
)
from omni_cio.decision.capacity_directional_pretrade_review_v1 import (
    CapacityDirectionalPreTradeReviewError,
    compose_capacity_directional_pretrade_review,
)


NOW = datetime(2026, 7, 29, 21, 0, tzinfo=timezone.utc)
BUY_KEY = "uid:directional-buy"
SELL_KEY = "uid:directional-sell"


def _request(
    key: str,
    side: OrderSide,
) -> CapacityOrderRequestV1:
    return CapacityOrderRequestV1(
        request_id=f"request-{key}",
        instrument_key=key,
        side=side,
        currency="RUB",
        quantity_lots=2,
        lot_size=10,
        reference_price=Decimal("100"),
        intended_execution_days=2,
        units=20,
        order_notional=Decimal("2000"),
    )


def _intent(
    requests: tuple[CapacityOrderRequestV1, ...],
    *,
    ready: bool = True,
) -> CapacityIntentDecisionGateV1:
    return CapacityIntentDecisionGateV1.model_construct(
        assessed_at=NOW,
        gate_ready=ready,
        abstain=not ready,
        request=CapacityIntentDecisionGateRequestV1(
            gate_id="directional-review-gate",
            requested_option_id="option.limited_change",
            expected_capacity_requests=requests,
        ),
        no_action_option_id="option.no_action",
        final_option_id=(
            "option.limited_change" if ready else "option.no_action"
        ),
        final_action=(
            DecisionAction.REVIEW_LIMITED_CHANGE
            if ready
            else DecisionAction.WAIT_FOR_DATA
        ),
    )


def _purchase_gate(
    requests: tuple[CapacityOrderRequestV1, ...] | None = None,
    *,
    ready: bool = True,
    coverage_complete: bool = True,
    exact: bool = True,
) -> CapacityPreTradeDecisionGateV1:
    intent = _intent(requests or (_request(BUY_KEY, OrderSide.BUY),), ready=ready)
    required = len(intent.request.expected_capacity_requests)
    reviewed = required if coverage_complete else max(0, required - 1)
    exact_count = reviewed if exact else max(0, reviewed - 1)
    return CapacityPreTradeDecisionGateV1.model_construct(
        assessed_at=NOW,
        gate_ready=ready,
        abstain=not ready,
        base_intent_gate=intent,
        no_action_option_id="option.no_action",
        final_option_id=(
            "option.limited_change" if ready else "option.no_action"
        ),
        final_action=(
            DecisionAction.REVIEW_LIMITED_CHANGE
            if ready
            else DecisionAction.WAIT_FOR_DATA
        ),
        required_preview_count=required,
        preview_coverage_count=reviewed,
        exact_match_count=exact_count,
        broker_preview_coverage_complete=coverage_complete,
        affordability_confirmed=ready and coverage_complete,
        commission_integrity_confirmed=ready and coverage_complete,
    )


def _sell_gate(
    requests: tuple[CapacityOrderRequestV1, ...] | None = None,
    *,
    ready: bool = True,
    coverage_complete: bool = True,
    exact: bool = True,
) -> CapacitySellPreTradeDecisionGateV1:
    intent = _intent(requests or (_request(SELL_KEY, OrderSide.SELL),), ready=ready)
    required = len(intent.request.expected_capacity_requests)
    reviewed = required if coverage_complete else max(0, required - 1)
    exact_count = reviewed if exact else max(0, reviewed - 1)
    confirmed = ready and coverage_complete
    return CapacitySellPreTradeDecisionGateV1.model_construct(
        assessed_at=NOW,
        gate_ready=ready,
        abstain=not ready,
        base_intent_gate=intent,
        no_action_option_id="option.no_action",
        final_option_id=(
            "option.limited_change" if ready else "option.no_action"
        ),
        final_action=(
            DecisionAction.REVIEW_LIMITED_CHANGE
            if ready
            else DecisionAction.WAIT_FOR_DATA
        ),
        required_preview_count=required,
        preview_coverage_count=reviewed,
        exact_match_count=exact_count,
        broker_preview_coverage_complete=coverage_complete,
        position_availability_confirmed=confirmed,
        open_orders_confirmed=confirmed,
        tax_basis_confirmed=confirmed,
        commission_integrity_confirmed=confirmed,
    )


def test_ready_purchase_gate_maps_to_unified_review_without_execution() -> None:
    result = compose_capacity_directional_pretrade_review(
        purchase_gate=_purchase_gate()
    )

    assert result.direction is OrderSide.BUY
    assert result.status is CapacityDecisionGateStatus.READY
    assert result.gate_ready is True
    assert result.final_option_id == "option.limited_change"
    assert result.final_action is DecisionAction.REVIEW_LIMITED_CHANGE
    assert result.affordability_confirmed is True
    assert result.position_availability_confirmed is None
    assert result.open_orders_confirmed is None
    assert result.tax_basis_confirmed is None
    assert result.commission_integrity_confirmed is True
    assert result.option_selected_by_review is False
    assert result.order_created is False
    assert result.execution_ready is False
    assert result.trading_methods is False
    assert (
        CapacityDirectionalPreTradeReviewWarning.SOURCE_GATE_RETAINED
        in result.warnings
    )


def test_ready_sell_gate_maps_to_unified_review_without_execution() -> None:
    result = compose_capacity_directional_pretrade_review(sell_gate=_sell_gate())

    assert result.direction is OrderSide.SELL
    assert result.status is CapacityDecisionGateStatus.READY
    assert result.affordability_confirmed is None
    assert result.position_availability_confirmed is True
    assert result.open_orders_confirmed is True
    assert result.tax_basis_confirmed is True
    assert result.commission_integrity_confirmed is True
    assert result.order_created is False
    assert result.trading_methods is False


def test_mixed_direction_intent_is_fail_closed() -> None:
    requests = (
        _request(BUY_KEY, OrderSide.BUY),
        _request(SELL_KEY, OrderSide.SELL),
    )
    result = compose_capacity_directional_pretrade_review(
        purchase_gate=_purchase_gate(requests)
    )

    assert result.status is CapacityDecisionGateStatus.ABSTAIN
    assert result.final_option_id == "option.no_action"
    assert result.final_action is DecisionAction.WAIT_FOR_DATA
    assert (
        CapacityDirectionalPreTradeReviewBlocker.MIXED_INTENT_DIRECTIONS
        in result.blockers
    )
    assert (
        CapacityDirectionalPreTradeReviewBlocker.SOURCE_GATE_DIRECTION_MISMATCH
        in result.blockers
    )


def test_wrong_source_direction_is_fail_closed() -> None:
    sell_requests = (_request(SELL_KEY, OrderSide.SELL),)
    result = compose_capacity_directional_pretrade_review(
        purchase_gate=_purchase_gate(sell_requests)
    )

    assert result.abstain is True
    assert (
        CapacityDirectionalPreTradeReviewBlocker.SOURCE_GATE_DIRECTION_MISMATCH
        in result.blockers
    )


def test_blocked_or_incomplete_source_cannot_be_upgraded() -> None:
    blocked = compose_capacity_directional_pretrade_review(
        purchase_gate=_purchase_gate(ready=False)
    )
    assert (
        CapacityDirectionalPreTradeReviewBlocker.SOURCE_GATE_NOT_READY
        in blocked.blockers
    )
    assert blocked.final_action is DecisionAction.WAIT_FOR_DATA

    incomplete = compose_capacity_directional_pretrade_review(
        sell_gate=_sell_gate(coverage_complete=False, exact=False)
    )
    assert (
        CapacityDirectionalPreTradeReviewBlocker.SOURCE_COVERAGE_INCOMPLETE
        in incomplete.blockers
    )
    assert (
        CapacityDirectionalPreTradeReviewBlocker.SOURCE_INTENT_BINDING_INCOMPLETE
        in incomplete.blockers
    )
    assert incomplete.abstain is True


def test_exactly_one_source_gate_is_required() -> None:
    with pytest.raises(
        CapacityDirectionalPreTradeReviewError,
        match="EXACTLY_ONE_DIRECTIONAL_SOURCE_GATE_REQUIRED",
    ):
        compose_capacity_directional_pretrade_review()

    with pytest.raises(
        CapacityDirectionalPreTradeReviewError,
        match="EXACTLY_ONE_DIRECTIONAL_SOURCE_GATE_REQUIRED",
    ):
        compose_capacity_directional_pretrade_review(
            purchase_gate=_purchase_gate(),
            sell_gate=_sell_gate(),
        )


def test_contract_rejects_ready_review_with_substituted_option() -> None:
    result = compose_capacity_directional_pretrade_review(
        purchase_gate=_purchase_gate()
    )
    payload = dict(result.__dict__)
    payload["final_option_id"] = "option.no_action"

    with pytest.raises(ValidationError):
        CapacityDirectionalPreTradeReviewV1.model_validate(payload)
