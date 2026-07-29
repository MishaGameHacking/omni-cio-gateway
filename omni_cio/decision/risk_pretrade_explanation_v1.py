from __future__ import annotations

from datetime import datetime, timezone

from omni_cio.contracts.v1.decision import DecisionAction
from omni_cio.contracts.v1.decision_capacity import CapacityDecisionGateStatus
from omni_cio.contracts.v1.decision_capacity_directional_pretrade import (
    CapacityDirectionalPreTradeReviewV1,
)
from omni_cio.contracts.v1.decision_risk_pretrade_explanation import (
    RiskPreTradeExplanationBlocker,
    RiskPreTradeExplanationEnvelopeV1,
    RiskPreTradeExplanationLayer,
    RiskPreTradeExplanationLayerState,
    RiskPreTradeExplanationLayerV1,
    RiskPreTradeExplanationPolicyV1,
    RiskPreTradeExplanationWarning,
)
from omni_cio.contracts.v1.risk import RiskOverallStatus, RiskPolicyEvaluationV1


class RiskPreTradeExplanationError(ValueError):
    """Risk/pre-trade explanation inputs cannot be composed safely."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise RiskPreTradeExplanationError(
            "RISK_PRETRADE_EXPLANATION_TIMESTAMP_MUST_BE_AWARE"
        )
    return result.astimezone(timezone.utc)


def _append_unique[T](target: list[T], value: T) -> None:
    if value not in target:
        target.append(value)


def _layer(
    *,
    layer: RiskPreTradeExplanationLayer,
    ready: bool,
    blocker_count: int,
    warning_count: int,
    message: str,
) -> RiskPreTradeExplanationLayerV1:
    if not ready:
        state = RiskPreTradeExplanationLayerState.BLOCKED
    elif warning_count:
        state = RiskPreTradeExplanationLayerState.WARNING
    else:
        state = RiskPreTradeExplanationLayerState.READY
    return RiskPreTradeExplanationLayerV1(
        layer=layer,
        state=state,
        ready=ready,
        blocker_count=blocker_count,
        warning_count=warning_count,
        message=message,
    )


def compose_risk_pretrade_explanation(
    risk_evaluation: RiskPolicyEvaluationV1,
    directional_review: CapacityDirectionalPreTradeReviewV1,
    *,
    policy: RiskPreTradeExplanationPolicyV1 | None = None,
    assessed_at: datetime | None = None,
) -> RiskPreTradeExplanationEnvelopeV1:
    """Explain risk, capacity and broker-preview readiness without execution."""

    active_policy = policy or RiskPreTradeExplanationPolicyV1()
    envelope_time = _aware_utc(assessed_at)
    blockers: list[RiskPreTradeExplanationBlocker] = []

    source_account_ids = {
        row.preview.metadata.account.masked_id
        for row in directional_review.source_gate.coverage
    }
    risk_account_id = risk_evaluation.metadata.account.masked_id
    if not source_account_ids:
        _append_unique(
            blockers,
            RiskPreTradeExplanationBlocker.ACCOUNT_CONTEXT_UNCONFIRMED,
        )
        account_context_confirmed = False
    elif source_account_ids == {risk_account_id}:
        account_context_confirmed = True
    else:
        _append_unique(
            blockers,
            RiskPreTradeExplanationBlocker.ACCOUNT_CONTEXT_MISMATCH,
        )
        account_context_confirmed = False

    risk_age = (
        envelope_time - risk_evaluation.metadata.retrieved_at
    ).total_seconds()
    if not risk_evaluation.decision_ready:
        _append_unique(
            blockers,
            RiskPreTradeExplanationBlocker.RISK_EVALUATION_NOT_READY,
        )
    if risk_age > active_policy.risk_max_age_seconds:
        _append_unique(
            blockers,
            RiskPreTradeExplanationBlocker.RISK_EVALUATION_STALE,
        )
    if risk_age < -active_policy.future_tolerance_seconds:
        _append_unique(
            blockers,
            RiskPreTradeExplanationBlocker.RISK_EVALUATION_FROM_FUTURE,
        )

    review_age = (envelope_time - directional_review.assessed_at).total_seconds()
    if not directional_review.gate_ready:
        _append_unique(
            blockers,
            RiskPreTradeExplanationBlocker.DIRECTIONAL_REVIEW_NOT_READY,
        )
    if review_age > active_policy.directional_review_max_age_seconds:
        _append_unique(
            blockers,
            RiskPreTradeExplanationBlocker.DIRECTIONAL_REVIEW_STALE,
        )
    if review_age < -active_policy.future_tolerance_seconds:
        _append_unique(
            blockers,
            RiskPreTradeExplanationBlocker.DIRECTIONAL_REVIEW_FROM_FUTURE,
        )

    account_blockers = sum(
        blocker
        in (
            RiskPreTradeExplanationBlocker.ACCOUNT_CONTEXT_UNCONFIRMED,
            RiskPreTradeExplanationBlocker.ACCOUNT_CONTEXT_MISMATCH,
        )
        for blocker in blockers
    )
    risk_blockers = sum(
        blocker
        in (
            RiskPreTradeExplanationBlocker.RISK_EVALUATION_NOT_READY,
            RiskPreTradeExplanationBlocker.RISK_EVALUATION_STALE,
            RiskPreTradeExplanationBlocker.RISK_EVALUATION_FROM_FUTURE,
        )
        for blocker in blockers
    )
    directional_time_blockers = sum(
        blocker
        in (
            RiskPreTradeExplanationBlocker.DIRECTIONAL_REVIEW_STALE,
            RiskPreTradeExplanationBlocker.DIRECTIONAL_REVIEW_FROM_FUTURE,
        )
        for blocker in blockers
    )

    risk_ready = risk_blockers == 0
    capacity_ready = directional_review.base_intent_gate.gate_ready
    broker_ready = (
        directional_review.source_gate_ready
        and directional_review.source_coverage_complete
        and directional_review.exact_intent_binding_confirmed
    )
    directional_ready = directional_review.gate_ready and directional_time_blockers == 0
    risk_warning_count = (
        risk_evaluation.warning_count + risk_evaluation.unknown_count
    )
    layers = (
        _layer(
            layer=RiskPreTradeExplanationLayer.ACCOUNT_CONTEXT,
            ready=account_context_confirmed,
            blocker_count=account_blockers,
            warning_count=0,
            message=(
                "Risk and broker-preview sources use the same masked account."
                if account_context_confirmed
                else "Risk and broker-preview account context is not safely aligned."
            ),
        ),
        _layer(
            layer=RiskPreTradeExplanationLayer.PORTFOLIO_RISK,
            ready=risk_ready,
            blocker_count=risk_blockers,
            warning_count=risk_warning_count if risk_ready else 0,
            message=(
                "Conservative portfolio-risk context is available."
                if risk_ready
                else "Portfolio-risk context is incomplete, stale or blocking."
            ),
        ),
        _layer(
            layer=RiskPreTradeExplanationLayer.CAPACITY_INTENT,
            ready=capacity_ready,
            blocker_count=0 if capacity_ready else 1,
            warning_count=0,
            message=(
                "Capacity evidence matches the requested analytical intent."
                if capacity_ready
                else "Capacity evidence does not match the requested intent."
            ),
        ),
        _layer(
            layer=RiskPreTradeExplanationLayer.BROKER_PREVIEW,
            ready=broker_ready,
            blocker_count=0 if broker_ready else 1,
            warning_count=0,
            message=(
                "Broker preview coverage and exact binding are complete."
                if broker_ready
                else "Broker preview coverage or exact binding is incomplete."
            ),
        ),
        _layer(
            layer=RiskPreTradeExplanationLayer.DIRECTIONAL_REVIEW,
            ready=directional_ready,
            blocker_count=0 if directional_ready else 1,
            warning_count=0,
            message=(
                "Directional review is fresh and ready for user inspection."
                if directional_ready
                else "Directional review is blocked, stale or future-dated."
            ),
        ),
    )

    if not account_context_confirmed:
        primary_blocking_layer = RiskPreTradeExplanationLayer.ACCOUNT_CONTEXT
    elif not risk_ready:
        primary_blocking_layer = RiskPreTradeExplanationLayer.PORTFOLIO_RISK
    elif not capacity_ready:
        primary_blocking_layer = RiskPreTradeExplanationLayer.CAPACITY_INTENT
    elif not broker_ready:
        primary_blocking_layer = RiskPreTradeExplanationLayer.BROKER_PREVIEW
    elif not directional_ready:
        primary_blocking_layer = RiskPreTradeExplanationLayer.DIRECTIONAL_REVIEW
    else:
        primary_blocking_layer = None

    warnings = [
        RiskPreTradeExplanationWarning.RISK_EVALUATION_NOT_PRO_FORMA_BOUND,
        RiskPreTradeExplanationWarning.SOURCE_CONTRACTS_RETAINED,
        RiskPreTradeExplanationWarning.REVIEW_ONLY_NO_ORDER_CREATED,
    ]
    if not risk_evaluation.policy.personalized:
        warnings.append(
            RiskPreTradeExplanationWarning.RISK_POLICY_NON_PERSONALIZED
        )
    if (
        risk_evaluation.warning_count > 0
        or risk_evaluation.overall_status is RiskOverallStatus.WARNING
    ):
        warnings.append(RiskPreTradeExplanationWarning.RISK_WARNING_PRESENT)
    if risk_evaluation.unknown_count > 0:
        warnings.append(RiskPreTradeExplanationWarning.RISK_UNKNOWN_PRESENT)

    review_ready = not blockers and all(row.ready for row in layers)
    if review_ready:
        final_option_id = directional_review.final_option_id
        final_action = directional_review.final_action
        status = CapacityDecisionGateStatus.READY
    else:
        final_option_id = directional_review.no_action_option_id
        final_action = DecisionAction.WAIT_FOR_DATA
        status = CapacityDecisionGateStatus.ABSTAIN

    return RiskPreTradeExplanationEnvelopeV1(
        assessed_at=envelope_time,
        status=status,
        review_ready=review_ready,
        abstain=not review_ready,
        direction=directional_review.direction,
        risk_evaluation=risk_evaluation,
        directional_review=directional_review,
        policy=active_policy,
        no_action_option_id=directional_review.no_action_option_id,
        final_option_id=final_option_id,
        final_action=final_action,
        risk_overall_status=risk_evaluation.overall_status,
        risk_decision_ready=risk_evaluation.decision_ready,
        risk_breach_count=risk_evaluation.breach_count,
        risk_warning_count=risk_evaluation.warning_count,
        risk_unknown_count=risk_evaluation.unknown_count,
        account_context_confirmed=account_context_confirmed,
        source_account_count=len(source_account_ids),
        layers=layers,
        primary_blocking_layer=primary_blocking_layer,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
    )
