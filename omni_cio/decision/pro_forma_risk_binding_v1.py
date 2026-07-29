from __future__ import annotations

from datetime import datetime, timezone

from omni_cio.contracts.v1.capacity import CapacityOrderRequestV1, OrderSide
from omni_cio.contracts.v1.common import AccountReference
from omni_cio.contracts.v1.decision import DecisionAction
from omni_cio.contracts.v1.decision_capacity import CapacityDecisionGateStatus
from omni_cio.contracts.v1.decision_pro_forma_risk_binding import (
    ProFormaRiskIntentBindingBlocker,
    ProFormaRiskIntentBindingPolicyV1,
    ProFormaRiskIntentBindingV1,
    ProFormaRiskIntentBindingWarning,
    ProFormaRiskScenarioV1,
    calculate_pro_forma_intent_fingerprint,
)
from omni_cio.contracts.v1.decision_risk_pretrade_explanation import (
    RiskPreTradeExplanationEnvelopeV1,
)
from omni_cio.contracts.v1.risk import RiskPolicyEvaluationV1


class ProFormaRiskIntentBindingError(ValueError):
    """The pro-forma risk scenario cannot be bound safely."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ProFormaRiskIntentBindingError(
            "PRO_FORMA_RISK_BINDING_TIMESTAMP_MUST_BE_AWARE"
        )
    return result.astimezone(timezone.utc)


def _append_unique[T](target: list[T], value: T) -> None:
    if value not in target:
        target.append(value)


def build_pro_forma_risk_scenario(
    *,
    scenario_id: str,
    account: AccountReference,
    requested_option_id: str,
    direction: OrderSide,
    capacity_requests: tuple[CapacityOrderRequestV1, ...],
    risk_evaluation: RiskPolicyEvaluationV1,
    generated_at: datetime | None = None,
) -> ProFormaRiskScenarioV1:
    """Create a tamper-evident post-change risk scenario without execution."""

    scenario_time = _aware_utc(
        generated_at or risk_evaluation.metadata.retrieved_at
    )
    fingerprint = calculate_pro_forma_intent_fingerprint(
        account_masked_id=account.masked_id,
        requested_option_id=requested_option_id,
        direction=direction,
        capacity_requests=capacity_requests,
    )
    return ProFormaRiskScenarioV1(
        scenario_id=scenario_id,
        generated_at=scenario_time,
        account=account,
        requested_option_id=requested_option_id,
        direction=direction,
        capacity_requests=capacity_requests,
        intent_fingerprint=fingerprint,
        risk_evaluation=risk_evaluation,
    )


def bind_pro_forma_risk_to_intent(
    base_explanation: RiskPreTradeExplanationEnvelopeV1,
    scenario: ProFormaRiskScenarioV1,
    *,
    policy: ProFormaRiskIntentBindingPolicyV1 | None = None,
    assessed_at: datetime | None = None,
) -> ProFormaRiskIntentBindingV1:
    """Bind post-change risk to the exact reviewed intent without authorizing trade."""

    active_policy = policy or ProFormaRiskIntentBindingPolicyV1()
    binding_time = _aware_utc(assessed_at)
    current_risk = base_explanation.risk_evaluation
    pro_forma_risk = scenario.risk_evaluation
    base_intent = base_explanation.directional_review.base_intent_gate.request
    expected_requests = base_intent.expected_capacity_requests
    expected_keys = tuple(sorted(row.instrument_key for row in expected_requests))
    scenario_keys = tuple(
        sorted(row.instrument_key for row in scenario.capacity_requests)
    )
    expected_fingerprint = calculate_pro_forma_intent_fingerprint(
        account_masked_id=current_risk.metadata.account.masked_id,
        requested_option_id=base_intent.requested_option_id,
        direction=base_explanation.direction,
        capacity_requests=expected_requests,
    )

    account_context_confirmed = (
        base_explanation.account_context_confirmed
        and scenario.account == current_risk.metadata.account
    )
    option_binding_confirmed = (
        scenario.requested_option_id == base_intent.requested_option_id
    )
    direction_binding_confirmed = scenario.direction is base_explanation.direction
    instrument_binding_confirmed = scenario_keys == expected_keys
    intent_fingerprint_confirmed = (
        scenario.intent_fingerprint == expected_fingerprint
    )
    risk_policy_match = pro_forma_risk.policy == current_risk.policy
    pro_forma_age = (binding_time - scenario.generated_at).total_seconds()

    blockers: list[ProFormaRiskIntentBindingBlocker] = []
    if not base_explanation.review_ready:
        _append_unique(
            blockers,
            ProFormaRiskIntentBindingBlocker.BASE_EXPLANATION_NOT_READY,
        )
    if not account_context_confirmed:
        _append_unique(
            blockers,
            ProFormaRiskIntentBindingBlocker.ACCOUNT_CONTEXT_MISMATCH,
        )
    if not option_binding_confirmed:
        _append_unique(
            blockers,
            ProFormaRiskIntentBindingBlocker.OPTION_ID_MISMATCH,
        )
    if not direction_binding_confirmed:
        _append_unique(
            blockers,
            ProFormaRiskIntentBindingBlocker.DIRECTION_MISMATCH,
        )
    if not instrument_binding_confirmed:
        _append_unique(
            blockers,
            ProFormaRiskIntentBindingBlocker.INTENT_INSTRUMENTS_MISMATCH,
        )
    if not intent_fingerprint_confirmed:
        _append_unique(
            blockers,
            ProFormaRiskIntentBindingBlocker.INTENT_FINGERPRINT_MISMATCH,
        )
    if not risk_policy_match:
        _append_unique(
            blockers,
            ProFormaRiskIntentBindingBlocker.RISK_POLICY_MISMATCH,
        )
    if not pro_forma_risk.decision_ready:
        _append_unique(
            blockers,
            ProFormaRiskIntentBindingBlocker.PRO_FORMA_RISK_NOT_READY,
        )
    if pro_forma_age > active_policy.pro_forma_max_age_seconds:
        _append_unique(
            blockers,
            ProFormaRiskIntentBindingBlocker.PRO_FORMA_RISK_STALE,
        )
    if pro_forma_age < -active_policy.future_tolerance_seconds:
        _append_unique(
            blockers,
            ProFormaRiskIntentBindingBlocker.PRO_FORMA_RISK_FROM_FUTURE,
        )

    review_ready = not blockers
    if review_ready:
        status = CapacityDecisionGateStatus.READY
        final_option_id = base_explanation.final_option_id
        final_action = base_explanation.final_action
        primary_blocker = None
    else:
        status = CapacityDecisionGateStatus.ABSTAIN
        final_option_id = base_explanation.no_action_option_id
        final_action = DecisionAction.WAIT_FOR_DATA
        primary_blocker = blockers[0]

    return ProFormaRiskIntentBindingV1(
        assessed_at=binding_time,
        status=status,
        review_ready=review_ready,
        abstain=not review_ready,
        base_explanation=base_explanation,
        scenario=scenario,
        policy=active_policy,
        no_action_option_id=base_explanation.no_action_option_id,
        final_option_id=final_option_id,
        final_action=final_action,
        requested_option_id=scenario.requested_option_id,
        direction=scenario.direction,
        account_context_confirmed=account_context_confirmed,
        option_binding_confirmed=option_binding_confirmed,
        direction_binding_confirmed=direction_binding_confirmed,
        instrument_binding_confirmed=instrument_binding_confirmed,
        intent_fingerprint_confirmed=intent_fingerprint_confirmed,
        risk_policy_match=risk_policy_match,
        base_explanation_ready=base_explanation.review_ready,
        pro_forma_risk_ready=pro_forma_risk.decision_ready,
        bound_instrument_count=len(scenario.capacity_requests),
        intent_fingerprint=scenario.intent_fingerprint,
        current_risk_status=current_risk.overall_status,
        pro_forma_risk_status=pro_forma_risk.overall_status,
        current_breach_count=current_risk.breach_count,
        pro_forma_breach_count=pro_forma_risk.breach_count,
        breach_count_delta=pro_forma_risk.breach_count - current_risk.breach_count,
        current_warning_count=current_risk.warning_count,
        pro_forma_warning_count=pro_forma_risk.warning_count,
        warning_count_delta=(
            pro_forma_risk.warning_count - current_risk.warning_count
        ),
        current_unknown_count=current_risk.unknown_count,
        pro_forma_unknown_count=pro_forma_risk.unknown_count,
        unknown_count_delta=(
            pro_forma_risk.unknown_count - current_risk.unknown_count
        ),
        risk_status_changed=(
            current_risk.overall_status is not pro_forma_risk.overall_status
        ),
        primary_blocker=primary_blocker,
        blockers=tuple(blockers),
        warnings=(
            ProFormaRiskIntentBindingWarning.EXACT_INTENT_FINGERPRINT_BOUND,
            ProFormaRiskIntentBindingWarning.CURRENT_AND_PRO_FORMA_RISK_RETAINED,
            ProFormaRiskIntentBindingWarning.RISK_STATUS_DELTA_NOT_RETURN_FORECAST,
            ProFormaRiskIntentBindingWarning.PRO_FORMA_RISK_NOT_RECOMPUTED_BY_BINDING,
            ProFormaRiskIntentBindingWarning.REVIEW_ONLY_NO_ORDER_CREATED,
        ),
        risk_change_approval_confirmed=review_ready,
    )
