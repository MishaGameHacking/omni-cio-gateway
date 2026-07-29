from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

from omni_cio.contracts.v1.capacity import CapacityAssessmentV1
from omni_cio.contracts.v1.decision import (
    DecisionAction,
    DecisionOptionKind,
    DecisionOptionStatus,
    DecisionSetV1,
)
from omni_cio.contracts.v1.decision_capacity import (
    CapacityDecisionCoverageV1,
    CapacityDecisionGateBlocker,
    CapacityDecisionGatePolicyV1,
    CapacityDecisionGateRequestV1,
    CapacityDecisionGateStatus,
    CapacityDecisionGateV1,
    CapacityDecisionGateWarning,
)


class CapacityDecisionGateError(ValueError):
    """The supplied capacity gate inputs are structurally invalid."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise CapacityDecisionGateError(
            "CAPACITY_DECISION_GATE_TIMESTAMP_MUST_BE_AWARE"
        )
    return result.astimezone(timezone.utc)


def _append_unique[T](target: list[T], value: T) -> None:
    if value not in target:
        target.append(value)


def _time_blockers(
    *,
    value_at: datetime,
    assessed_at: datetime,
    maximum_age_seconds: int,
    future_tolerance_seconds: int,
    stale_blocker: CapacityDecisionGateBlocker,
    future_blocker: CapacityDecisionGateBlocker,
    blockers: list[CapacityDecisionGateBlocker],
) -> None:
    age_seconds = (assessed_at - value_at).total_seconds()
    if age_seconds > maximum_age_seconds:
        _append_unique(blockers, stale_blocker)
    if age_seconds < -future_tolerance_seconds:
        _append_unique(blockers, future_blocker)


def apply_capacity_decision_gate(
    decision: DecisionSetV1,
    request: CapacityDecisionGateRequestV1,
    capacity_assessments: Iterable[CapacityAssessmentV1],
    *,
    policy: CapacityDecisionGatePolicyV1 | None = None,
    assessed_at: datetime | None = None,
) -> CapacityDecisionGateV1:
    """Gate one analytical change option on complete, fresh capacity evidence."""

    active_policy = policy or CapacityDecisionGatePolicyV1()
    gate_time = _aware_utc(assessed_at)
    capacities = tuple(capacity_assessments)
    blockers: list[CapacityDecisionGateBlocker] = []
    warnings: list[CapacityDecisionGateWarning] = [
        CapacityDecisionGateWarning.CAPACITY_GATE_DOES_NOT_SELECT_OPTION,
        CapacityDecisionGateWarning.CAPACITY_IS_POINT_IN_TIME,
        CapacityDecisionGateWarning.REVIEW_ONLY_NO_ORDER_CREATED,
    ]

    if not decision.recommendation_ready or decision.abstain:
        _append_unique(
            blockers,
            CapacityDecisionGateBlocker.BASE_DECISION_NOT_READY,
        )
    _time_blockers(
        value_at=decision.metadata.retrieved_at,
        assessed_at=gate_time,
        maximum_age_seconds=active_policy.base_decision_max_age_seconds,
        future_tolerance_seconds=active_policy.future_tolerance_seconds,
        stale_blocker=CapacityDecisionGateBlocker.BASE_DECISION_STALE,
        future_blocker=CapacityDecisionGateBlocker.BASE_DECISION_FROM_FUTURE,
        blockers=blockers,
    )

    option = next(
        (
            row
            for row in decision.options
            if row.option_id == request.requested_option_id
        ),
        None,
    )
    if option is None:
        _append_unique(
            blockers,
            CapacityDecisionGateBlocker.REQUESTED_OPTION_NOT_FOUND,
        )
    elif option.kind is DecisionOptionKind.NO_ACTION:
        _append_unique(
            blockers,
            CapacityDecisionGateBlocker.REQUESTED_OPTION_NO_ACTION,
        )
    elif option.status is DecisionOptionStatus.BLOCKED:
        _append_unique(
            blockers,
            CapacityDecisionGateBlocker.REQUESTED_OPTION_BLOCKED,
        )

    capacity_by_key: dict[str, CapacityAssessmentV1] = {}
    for capacity_assessment in capacities:
        key = capacity_assessment.request.instrument_key
        if key in capacity_by_key:
            raise CapacityDecisionGateError(
                "DUPLICATE_CAPACITY_ASSESSMENT_INSTRUMENT"
            )
        capacity_by_key[key] = capacity_assessment

    requested_keys = set(request.required_instrument_keys)
    extra_keys = set(capacity_by_key) - requested_keys
    if extra_keys:
        raise CapacityDecisionGateError("UNREQUESTED_CAPACITY_ASSESSMENT_INSTRUMENT")

    coverage: list[CapacityDecisionCoverageV1] = []
    for instrument_key in request.required_instrument_keys:
        matched_assessment = capacity_by_key.get(instrument_key)
        if matched_assessment is None:
            continue
        coverage.append(
            CapacityDecisionCoverageV1(
                instrument_key=instrument_key,
                capacity_request_id=matched_assessment.request.request_id,
                currency=matched_assessment.request.currency,
                order_notional=matched_assessment.request.order_notional,
                safe_notional=(
                    matched_assessment.metrics.safe_notional_for_requested_window
                ),
                safe_lots=matched_assessment.metrics.safe_lots_for_requested_window,
                capacity_ready=matched_assessment.capacity_ready,
                capacity_assessed_at=matched_assessment.assessed_at,
                capacity_blockers=matched_assessment.blockers,
            )
        )
        _time_blockers(
            value_at=matched_assessment.assessed_at,
            assessed_at=gate_time,
            maximum_age_seconds=active_policy.capacity_max_age_seconds,
            future_tolerance_seconds=active_policy.future_tolerance_seconds,
            stale_blocker=CapacityDecisionGateBlocker.CAPACITY_STALE,
            future_blocker=CapacityDecisionGateBlocker.CAPACITY_FROM_FUTURE,
            blockers=blockers,
        )
        if not matched_assessment.capacity_ready:
            _append_unique(
                blockers,
                CapacityDecisionGateBlocker.CAPACITY_NOT_READY,
            )

    if len(coverage) != len(request.required_instrument_keys):
        _append_unique(
            blockers,
            CapacityDecisionGateBlocker.CAPACITY_COVERAGE_INCOMPLETE,
        )

    no_action = next(
        row for row in decision.options if row.kind is DecisionOptionKind.NO_ACTION
    )
    gate_ready = not blockers
    if gate_ready:
        assert option is not None
        final_option_id = option.option_id
        final_action = option.action
        status = CapacityDecisionGateStatus.READY
    else:
        final_option_id = no_action.option_id
        final_action = DecisionAction.WAIT_FOR_DATA
        status = CapacityDecisionGateStatus.ABSTAIN

    return CapacityDecisionGateV1(
        assessed_at=gate_time,
        status=status,
        gate_ready=gate_ready,
        abstain=not gate_ready,
        request=request,
        policy=active_policy,
        base_decision_recommendation_ready=decision.recommendation_ready,
        base_preferred_option_id=decision.preferred_option_id,
        requested_option_kind=option.kind if option is not None else None,
        requested_option_status=option.status if option is not None else None,
        requested_action=option.action if option is not None else None,
        final_option_id=final_option_id,
        final_action=final_action,
        required_capacity_count=len(request.required_instrument_keys),
        capacity_coverage_count=len(coverage),
        capacity_ready_count=sum(row.capacity_ready for row in coverage),
        coverage=tuple(coverage),
        blockers=tuple(blockers),
        warnings=tuple(warnings),
    )
