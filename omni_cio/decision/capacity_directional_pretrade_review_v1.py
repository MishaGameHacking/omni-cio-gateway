from __future__ import annotations

from omni_cio.contracts.v1.capacity import OrderSide
from omni_cio.contracts.v1.decision import DecisionAction
from omni_cio.contracts.v1.decision_capacity import CapacityDecisionGateStatus
from omni_cio.contracts.v1.decision_capacity_directional_pretrade import (
    CapacityDirectionalPreTradeReviewBlocker,
    CapacityDirectionalPreTradeReviewV1,
    CapacityDirectionalPreTradeReviewWarning,
)
from omni_cio.contracts.v1.decision_capacity_pretrade import (
    CapacityPreTradeDecisionGateV1,
)
from omni_cio.contracts.v1.decision_capacity_sell_pretrade import (
    CapacitySellPreTradeDecisionGateV1,
)


class CapacityDirectionalPreTradeReviewError(ValueError):
    """The supplied directional pre-trade review inputs are invalid."""


def _append_unique[T](target: list[T], value: T) -> None:
    if value not in target:
        target.append(value)


def compose_capacity_directional_pretrade_review(
    *,
    purchase_gate: CapacityPreTradeDecisionGateV1 | None = None,
    sell_gate: CapacitySellPreTradeDecisionGateV1 | None = None,
) -> CapacityDirectionalPreTradeReviewV1:
    """Compose exactly one homogeneous purchase or sell review without execution."""

    if (purchase_gate is None) == (sell_gate is None):
        raise CapacityDirectionalPreTradeReviewError(
            "EXACTLY_ONE_DIRECTIONAL_SOURCE_GATE_REQUIRED"
        )

    if purchase_gate is not None:
        source = purchase_gate
        direction = OrderSide.BUY
        affordability_confirmed: bool | None = source.affordability_confirmed
        position_availability_confirmed: bool | None = None
        open_orders_confirmed: bool | None = None
        tax_basis_confirmed: bool | None = None
    else:
        assert sell_gate is not None
        source = sell_gate
        direction = OrderSide.SELL
        affordability_confirmed = None
        position_availability_confirmed = source.position_availability_confirmed
        open_orders_confirmed = source.open_orders_confirmed
        tax_basis_confirmed = source.tax_basis_confirmed

    base_intent_gate = source.base_intent_gate
    expected_requests = base_intent_gate.request.expected_capacity_requests
    expected_sides = {row.side for row in expected_requests}
    mixed_directions = len(expected_sides) != 1
    expected_direction = next(iter(expected_sides)) if not mixed_directions else None
    direction_mismatch = mixed_directions or expected_direction is not direction

    blockers: list[CapacityDirectionalPreTradeReviewBlocker] = []
    if mixed_directions:
        _append_unique(
            blockers,
            CapacityDirectionalPreTradeReviewBlocker.MIXED_INTENT_DIRECTIONS,
        )
    if direction_mismatch:
        _append_unique(
            blockers,
            CapacityDirectionalPreTradeReviewBlocker.SOURCE_GATE_DIRECTION_MISMATCH,
        )
    if not source.gate_ready:
        _append_unique(
            blockers,
            CapacityDirectionalPreTradeReviewBlocker.SOURCE_GATE_NOT_READY,
        )
    if not source.broker_preview_coverage_complete:
        _append_unique(
            blockers,
            CapacityDirectionalPreTradeReviewBlocker.SOURCE_COVERAGE_INCOMPLETE,
        )

    exact_intent_binding_confirmed = (
        source.exact_match_count == source.required_preview_count
    )
    if not exact_intent_binding_confirmed:
        _append_unique(
            blockers,
            CapacityDirectionalPreTradeReviewBlocker.SOURCE_INTENT_BINDING_INCOMPLETE,
        )

    gate_ready = not blockers
    if gate_ready:
        final_option_id = source.final_option_id
        final_action = source.final_action
        status = CapacityDecisionGateStatus.READY
    else:
        final_option_id = source.no_action_option_id
        final_action = DecisionAction.WAIT_FOR_DATA
        status = CapacityDecisionGateStatus.ABSTAIN

    return CapacityDirectionalPreTradeReviewV1(
        assessed_at=source.assessed_at,
        direction=direction,
        status=status,
        gate_ready=gate_ready,
        abstain=not gate_ready,
        base_intent_gate=base_intent_gate,
        source_gate=source,
        no_action_option_id=source.no_action_option_id,
        final_option_id=final_option_id,
        final_action=final_action,
        required_instrument_count=source.required_preview_count,
        reviewed_instrument_count=source.preview_coverage_count,
        source_gate_ready=source.gate_ready,
        source_coverage_complete=source.broker_preview_coverage_complete,
        exact_intent_binding_confirmed=exact_intent_binding_confirmed,
        affordability_confirmed=affordability_confirmed,
        position_availability_confirmed=position_availability_confirmed,
        open_orders_confirmed=open_orders_confirmed,
        tax_basis_confirmed=tax_basis_confirmed,
        commission_integrity_confirmed=source.commission_integrity_confirmed,
        blockers=tuple(blockers),
        warnings=(
            CapacityDirectionalPreTradeReviewWarning.HOMOGENEOUS_DIRECTION_ONLY,
            CapacityDirectionalPreTradeReviewWarning.SOURCE_GATE_RETAINED,
            CapacityDirectionalPreTradeReviewWarning.REVIEW_ONLY_NO_ORDER_CREATED,
        ),
    )
