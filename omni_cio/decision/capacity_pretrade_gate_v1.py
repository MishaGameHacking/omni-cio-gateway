from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

from omni_cio.contracts.v1.capacity import (
    CapacityOrderRequestV1,
    OrderSide,
)
from omni_cio.contracts.v1.decision import DecisionAction
from omni_cio.contracts.v1.decision_capacity import CapacityDecisionGateStatus
from omni_cio.contracts.v1.decision_capacity_intent import (
    CapacityIntentDecisionGateV1,
)
from omni_cio.contracts.v1.decision_capacity_pretrade import (
    CapacityPreTradeCoverageV1,
    CapacityPreTradeDecisionGateBlocker,
    CapacityPreTradeDecisionGatePolicyV1,
    CapacityPreTradeDecisionGateV1,
    CapacityPreTradeDecisionGateWarning,
    CapacityPreTradeMismatch,
)
from omni_cio.contracts.v1.pretrade import PreTradeBlocker, PreTradePreviewV1


class CapacityPreTradeDecisionGateError(ValueError):
    """The supplied capacity/pre-trade gate inputs are structurally invalid."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise CapacityPreTradeDecisionGateError(
            "CAPACITY_PRETRADE_GATE_TIMESTAMP_MUST_BE_AWARE"
        )
    return result.astimezone(timezone.utc)


def _append_unique[T](target: list[T], value: T) -> None:
    if value not in target:
        target.append(value)


def _preview_mismatches(
    expected_request: CapacityOrderRequestV1,
    preview: PreTradePreviewV1,
) -> tuple[CapacityPreTradeMismatch, ...]:
    mismatches: list[CapacityPreTradeMismatch] = []
    if expected_request.side is not OrderSide.BUY:
        mismatches.append(CapacityPreTradeMismatch.SIDE)
    if expected_request.currency != preview.currency:
        mismatches.append(CapacityPreTradeMismatch.CURRENCY)
    if expected_request.lot_size != preview.lot_size:
        mismatches.append(CapacityPreTradeMismatch.LOT_SIZE)
    if expected_request.quantity_lots != preview.quantity_lots:
        mismatches.append(CapacityPreTradeMismatch.QUANTITY_LOTS)
    if expected_request.reference_price != preview.unit_price:
        mismatches.append(CapacityPreTradeMismatch.REFERENCE_PRICE)
    return tuple(mismatches)


def _time_blockers(
    *,
    value_at: datetime,
    assessed_at: datetime,
    policy: CapacityPreTradeDecisionGatePolicyV1,
    blockers: list[CapacityPreTradeDecisionGateBlocker],
) -> None:
    age_seconds = (assessed_at - value_at).total_seconds()
    if age_seconds > policy.preview_max_age_seconds:
        _append_unique(
            blockers,
            CapacityPreTradeDecisionGateBlocker.PREVIEW_STALE,
        )
    if age_seconds < -policy.future_tolerance_seconds:
        _append_unique(
            blockers,
            CapacityPreTradeDecisionGateBlocker.PREVIEW_FROM_FUTURE,
        )


def apply_capacity_pretrade_decision_gate(
    base_intent_gate: CapacityIntentDecisionGateV1,
    previews: Iterable[PreTradePreviewV1],
    *,
    policy: CapacityPreTradeDecisionGatePolicyV1 | None = None,
    assessed_at: datetime | None = None,
) -> CapacityPreTradeDecisionGateV1:
    """Require ready, fresh purchase previews for the exact capacity intent."""

    active_policy = policy or CapacityPreTradeDecisionGatePolicyV1()
    gate_time = _aware_utc(assessed_at)
    preview_rows = tuple(previews)
    expected_requests = base_intent_gate.request.expected_capacity_requests
    expected_keys = {row.instrument_key for row in expected_requests}

    preview_by_key: dict[str, PreTradePreviewV1] = {}
    for preview in preview_rows:
        if preview.stable_key in preview_by_key:
            raise CapacityPreTradeDecisionGateError(
                "DUPLICATE_PRETRADE_PREVIEW_INSTRUMENT"
            )
        preview_by_key[preview.stable_key] = preview
    if set(preview_by_key) - expected_keys:
        raise CapacityPreTradeDecisionGateError(
            "UNREQUESTED_PRETRADE_PREVIEW_INSTRUMENT"
        )

    blockers: list[CapacityPreTradeDecisionGateBlocker] = []
    if not base_intent_gate.gate_ready:
        _append_unique(
            blockers,
            CapacityPreTradeDecisionGateBlocker.BASE_INTENT_GATE_NOT_READY,
        )

    coverage: list[CapacityPreTradeCoverageV1] = []
    for expected_request in expected_requests:
        matched_preview = preview_by_key.get(expected_request.instrument_key)
        if matched_preview is None:
            continue
        mismatch_fields = _preview_mismatches(expected_request, matched_preview)
        coverage.append(
            CapacityPreTradeCoverageV1(
                instrument_key=expected_request.instrument_key,
                expected_request=expected_request,
                preview=matched_preview,
                mismatch_fields=mismatch_fields,
                exact_match=not mismatch_fields,
                preview_ready=matched_preview.preview_ready,
                preview_evaluated_at=matched_preview.evaluated_at,
                preview_currency=matched_preview.currency,
                preview_price_basis=matched_preview.price_basis,
                preview_unit_price=matched_preview.unit_price,
                preview_lot_size=matched_preview.lot_size,
                preview_quantity_lots=matched_preview.quantity_lots,
                preview_blockers=matched_preview.blockers,
            )
        )
        _time_blockers(
            value_at=matched_preview.evaluated_at,
            assessed_at=gate_time,
            policy=active_policy,
            blockers=blockers,
        )
        if not matched_preview.preview_ready:
            _append_unique(
                blockers,
                CapacityPreTradeDecisionGateBlocker.PREVIEW_NOT_READY,
            )
        if mismatch_fields:
            _append_unique(
                blockers,
                CapacityPreTradeDecisionGateBlocker.PREVIEW_INTENT_MISMATCH,
            )

    if len(coverage) != len(expected_requests):
        _append_unique(
            blockers,
            CapacityPreTradeDecisionGateBlocker.PREVIEW_COVERAGE_INCOMPLETE,
        )

    gate_ready = not blockers
    if gate_ready:
        final_option_id = base_intent_gate.final_option_id
        final_action = base_intent_gate.final_action
        status = CapacityDecisionGateStatus.READY
    else:
        final_option_id = base_intent_gate.no_action_option_id
        final_action = DecisionAction.WAIT_FOR_DATA
        status = CapacityDecisionGateStatus.ABSTAIN

    coverage_complete = len(coverage) == len(expected_requests)
    affordability_confirmed = coverage_complete and all(
        row.preview.affordable
        and PreTradeBlocker.AFFORDABILITY_UNCONFIRMED not in row.preview_blockers
        for row in coverage
    )
    commission_integrity_confirmed = coverage_complete and all(
        row.preview.integrity_confirmed
        and row.preview.canonical_commission is not None
        for row in coverage
    )

    return CapacityPreTradeDecisionGateV1(
        assessed_at=gate_time,
        status=status,
        gate_ready=gate_ready,
        abstain=not gate_ready,
        base_intent_gate=base_intent_gate,
        policy=active_policy,
        no_action_option_id=base_intent_gate.no_action_option_id,
        final_option_id=final_option_id,
        final_action=final_action,
        required_preview_count=len(expected_requests),
        preview_coverage_count=len(coverage),
        preview_ready_count=sum(row.preview_ready for row in coverage),
        exact_match_count=sum(row.exact_match for row in coverage),
        coverage=tuple(coverage),
        blockers=tuple(blockers),
        warnings=(
            CapacityPreTradeDecisionGateWarning.PURCHASE_PREVIEW_ONLY,
            CapacityPreTradeDecisionGateWarning.BROKER_PREVIEW_IS_POINT_IN_TIME,
            CapacityPreTradeDecisionGateWarning.BROKER_TOTALS_NOT_RECOMPUTED_BY_GATE,
            CapacityPreTradeDecisionGateWarning.COMMISSION_AND_ACCRUED_INTEREST_FROM_PREVIEW,
            CapacityPreTradeDecisionGateWarning.REVIEW_ONLY_NO_ORDER_CREATED,
        ),
        broker_preview_coverage_complete=coverage_complete,
        affordability_confirmed=affordability_confirmed,
        commission_integrity_confirmed=commission_integrity_confirmed,
    )
