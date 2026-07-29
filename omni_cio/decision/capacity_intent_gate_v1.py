from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

from omni_cio.contracts.v1.capacity import (
    CapacityAssessmentV1,
    CapacityOrderRequestV1,
)
from omni_cio.contracts.v1.decision import (
    DecisionAction,
    DecisionOptionKind,
    DecisionSetV1,
)
from omni_cio.contracts.v1.decision_capacity import (
    CapacityDecisionGatePolicyV1,
    CapacityDecisionGateRequestV1,
    CapacityDecisionGateStatus,
)
from omni_cio.contracts.v1.decision_capacity_intent import (
    CapacityIntentBindingV1,
    CapacityIntentDecisionGateBlocker,
    CapacityIntentDecisionGateRequestV1,
    CapacityIntentDecisionGateV1,
    CapacityIntentDecisionGateWarning,
    CapacityIntentMismatch,
)
from omni_cio.decision.capacity_gate_v1 import (
    CapacityDecisionGateError,
    apply_capacity_decision_gate,
)


class CapacityIntentDecisionGateError(ValueError):
    """The supplied exact-intent gate inputs are structurally invalid."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise CapacityIntentDecisionGateError(
            "CAPACITY_INTENT_GATE_TIMESTAMP_MUST_BE_AWARE"
        )
    return result.astimezone(timezone.utc)


def _append_unique[T](target: list[T], value: T) -> None:
    if value not in target:
        target.append(value)


def _intent_mismatches(
    expected: CapacityOrderRequestV1,
    actual: CapacityOrderRequestV1,
) -> tuple[CapacityIntentMismatch, ...]:
    mismatches: list[CapacityIntentMismatch] = []
    comparisons = (
        (
            CapacityIntentMismatch.REQUEST_ID,
            expected.request_id,
            actual.request_id,
        ),
        (CapacityIntentMismatch.SIDE, expected.side, actual.side),
        (CapacityIntentMismatch.CURRENCY, expected.currency, actual.currency),
        (
            CapacityIntentMismatch.QUANTITY_LOTS,
            expected.quantity_lots,
            actual.quantity_lots,
        ),
        (CapacityIntentMismatch.LOT_SIZE, expected.lot_size, actual.lot_size),
        (
            CapacityIntentMismatch.REFERENCE_PRICE,
            expected.reference_price,
            actual.reference_price,
        ),
        (
            CapacityIntentMismatch.INTENDED_EXECUTION_DAYS,
            expected.intended_execution_days,
            actual.intended_execution_days,
        ),
        (CapacityIntentMismatch.UNITS, expected.units, actual.units),
        (
            CapacityIntentMismatch.ORDER_NOTIONAL,
            expected.order_notional,
            actual.order_notional,
        ),
    )
    for mismatch, expected_value, actual_value in comparisons:
        if expected_value != actual_value:
            mismatches.append(mismatch)
    return tuple(mismatches)


def apply_capacity_intent_decision_gate(
    decision: DecisionSetV1,
    request: CapacityIntentDecisionGateRequestV1,
    capacity_assessments: Iterable[CapacityAssessmentV1],
    *,
    policy: CapacityDecisionGatePolicyV1 | None = None,
    assessed_at: datetime | None = None,
) -> CapacityIntentDecisionGateV1:
    """Bind capacity evidence to the exact analytical order intent."""

    active_policy = policy or CapacityDecisionGatePolicyV1()
    gate_time = _aware_utc(assessed_at)
    capacities = tuple(capacity_assessments)
    expected_keys = tuple(
        row.instrument_key for row in request.expected_capacity_requests
    )
    base_request = CapacityDecisionGateRequestV1(
        gate_id=request.gate_id,
        requested_option_id=request.requested_option_id,
        required_instrument_keys=expected_keys,
    )
    try:
        base_gate = apply_capacity_decision_gate(
            decision,
            base_request,
            capacities,
            policy=active_policy,
            assessed_at=gate_time,
        )
    except CapacityDecisionGateError as exc:
        raise CapacityIntentDecisionGateError(str(exc)) from exc

    capacity_by_key = {
        assessment.request.instrument_key: assessment for assessment in capacities
    }
    coverage: list[CapacityIntentBindingV1] = []
    for expected_request in request.expected_capacity_requests:
        assessment = capacity_by_key.get(expected_request.instrument_key)
        if assessment is None:
            continue
        mismatch_fields = _intent_mismatches(
            expected_request,
            assessment.request,
        )
        coverage.append(
            CapacityIntentBindingV1(
                instrument_key=expected_request.instrument_key,
                expected_request=expected_request,
                actual_request=assessment.request,
                mismatch_fields=mismatch_fields,
                exact_match=not mismatch_fields,
                capacity_ready=assessment.capacity_ready,
                capacity_assessed_at=assessment.assessed_at,
                safe_notional=(
                    assessment.metrics.safe_notional_for_requested_window
                ),
                safe_lots=assessment.metrics.safe_lots_for_requested_window,
                capacity_blockers=assessment.blockers,
            )
        )

    blockers: list[CapacityIntentDecisionGateBlocker] = []
    if not base_gate.gate_ready:
        _append_unique(
            blockers,
            CapacityIntentDecisionGateBlocker.BASE_CAPACITY_GATE_NOT_READY,
        )
    if len(coverage) != len(request.expected_capacity_requests):
        _append_unique(
            blockers,
            CapacityIntentDecisionGateBlocker.INTENT_COVERAGE_INCOMPLETE,
        )
    if any(not row.exact_match for row in coverage):
        _append_unique(
            blockers,
            CapacityIntentDecisionGateBlocker.CAPACITY_INTENT_MISMATCH,
        )

    no_action = next(
        row for row in decision.options if row.kind is DecisionOptionKind.NO_ACTION
    )
    gate_ready = not blockers
    if gate_ready:
        final_option_id = base_gate.final_option_id
        final_action = base_gate.final_action
        status = CapacityDecisionGateStatus.READY
    else:
        final_option_id = no_action.option_id
        final_action = DecisionAction.WAIT_FOR_DATA
        status = CapacityDecisionGateStatus.ABSTAIN

    return CapacityIntentDecisionGateV1(
        assessed_at=gate_time,
        status=status,
        gate_ready=gate_ready,
        abstain=not gate_ready,
        request=request,
        policy=active_policy,
        base_gate=base_gate,
        no_action_option_id=no_action.option_id,
        final_option_id=final_option_id,
        final_action=final_action,
        required_intent_count=len(request.expected_capacity_requests),
        matched_intent_count=len(coverage),
        exact_match_count=sum(row.exact_match for row in coverage),
        coverage=tuple(coverage),
        blockers=tuple(blockers),
        warnings=(
            CapacityIntentDecisionGateWarning.EXACT_INTENT_BINDING_ONLY,
            CapacityIntentDecisionGateWarning.AFFORDABILITY_NOT_CHECKED,
            CapacityIntentDecisionGateWarning.BROKER_PREVIEW_NOT_CHECKED,
            CapacityIntentDecisionGateWarning.REVIEW_ONLY_NO_ORDER_CREATED,
        ),
    )
