from __future__ import annotations

from datetime import datetime, timezone

from omni_cio.contracts.v1.decision_capacity import CapacityDecisionGateStatus
from omni_cio.contracts.v1.decision_pro_forma_risk_binding import (
    ProFormaRiskIntentBindingV1,
)
from omni_cio.contracts.v1.final_decision_review import (
    FinalDecisionReviewDisposition,
    FinalDecisionReviewIntentV1,
    FinalDecisionReviewResponseV1,
    FinalDecisionReviewRiskSummaryV1,
    FinalDecisionReviewShadowMismatch,
    FinalDecisionReviewShadowStatus,
    FinalDecisionReviewShadowValidationV1,
    FinalDecisionReviewSourceV1,
    FinalDecisionReviewWarning,
)


class FinalDecisionReviewError(ValueError):
    """A final read-only review response cannot be produced safely."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise FinalDecisionReviewError(
            "FINAL_DECISION_REVIEW_TIMESTAMP_MUST_BE_AWARE"
        )
    return result.astimezone(timezone.utc)


def _sanitized_provenance(
    binding: ProFormaRiskIntentBindingV1,
) -> tuple[FinalDecisionReviewSourceV1, ...]:
    current_sources = binding.base_explanation.risk_evaluation.metadata.provenance
    pro_forma_sources = binding.scenario.risk_evaluation.metadata.provenance
    result: list[FinalDecisionReviewSourceV1] = []
    seen: set[tuple[str, str, datetime]] = set()
    for source in (*current_sources, *pro_forma_sources):
        key = (source.provider, source.operation, source.retrieved_at)
        if key in seen:
            continue
        seen.add(key)
        result.append(
            FinalDecisionReviewSourceV1(
                provider=source.provider,
                operation=source.operation,
                retrieved_at=source.retrieved_at,
            )
        )
    if not result:
        raise FinalDecisionReviewError("FINAL_DECISION_REVIEW_PROVENANCE_REQUIRED")
    return tuple(result)


def adapt_pro_forma_binding_to_final_review(
    binding: ProFormaRiskIntentBindingV1,
    *,
    generated_at: datetime | None = None,
) -> FinalDecisionReviewResponseV1:
    """Produce a compact user-safe response without exposing source contracts."""

    response_time = _aware_utc(generated_at or binding.assessed_at)
    intents = tuple(
        FinalDecisionReviewIntentV1(
            request_id=row.request_id,
            instrument_key=row.instrument_key,
            side=row.side,
            currency=row.currency,
            quantity_lots=row.quantity_lots,
            lot_size=row.lot_size,
            reference_price=row.reference_price,
            intended_execution_days=row.intended_execution_days,
            units=row.units,
            order_notional=row.order_notional,
        )
        for row in binding.scenario.capacity_requests
    )
    provenance = _sanitized_provenance(binding)
    blockers = tuple(row.value for row in binding.blockers)
    source_warnings = tuple(row.value for row in binding.warnings)
    disposition = (
        FinalDecisionReviewDisposition.REVIEW_READY
        if binding.review_ready
        else FinalDecisionReviewDisposition.WAIT_FOR_DATA
    )
    primary_blocker = (
        binding.primary_blocker.value
        if binding.primary_blocker is not None
        else None
    )
    risk = FinalDecisionReviewRiskSummaryV1(
        current_status=binding.current_risk_status,
        pro_forma_status=binding.pro_forma_risk_status,
        current_breach_count=binding.current_breach_count,
        pro_forma_breach_count=binding.pro_forma_breach_count,
        breach_count_delta=binding.breach_count_delta,
        current_warning_count=binding.current_warning_count,
        pro_forma_warning_count=binding.pro_forma_warning_count,
        warning_count_delta=binding.warning_count_delta,
        current_unknown_count=binding.current_unknown_count,
        pro_forma_unknown_count=binding.pro_forma_unknown_count,
        unknown_count_delta=binding.unknown_count_delta,
        status_changed=binding.risk_status_changed,
    )
    return FinalDecisionReviewResponseV1(
        generated_at=response_time,
        status=binding.status,
        disposition=disposition,
        review_ready=binding.review_ready,
        abstain=binding.abstain,
        account=binding.scenario.account,
        requested_option_id=binding.requested_option_id,
        final_option_id=binding.final_option_id,
        final_action=binding.final_action,
        direction=binding.direction,
        intent_fingerprint=binding.intent_fingerprint,
        instrument_count=len(intents),
        intents=intents,
        risk=risk,
        risk_change_approval_confirmed=(
            binding.risk_change_approval_confirmed
        ),
        primary_blocker=primary_blocker,
        blockers=blockers,
        source_warnings=source_warnings,
        response_warnings=(
            FinalDecisionReviewWarning.SOURCE_VALUES_NOT_RECOMPUTED,
            FinalDecisionReviewWarning.PROVENANCE_SANITIZED,
            FinalDecisionReviewWarning.RISK_DELTA_NOT_RETURN_FORECAST,
            FinalDecisionReviewWarning.REVIEW_ONLY_NO_TRADE_AUTHORIZATION,
        ),
        source_count=len(provenance),
        provenance=provenance,
    )


def validate_final_decision_review_shadow(
    binding: ProFormaRiskIntentBindingV1,
    response: FinalDecisionReviewResponseV1,
    *,
    validated_at: datetime | None = None,
) -> FinalDecisionReviewShadowValidationV1:
    """Check adapter parity without adding a route or changing execution state."""

    shadow_time = _aware_utc(validated_at or response.generated_at)
    status_match = response.status is binding.status
    readiness_match = (
        response.review_ready is binding.review_ready
        and response.abstain is binding.abstain
    )
    option_match = (
        response.final_option_id == binding.final_option_id
        and response.requested_option_id == binding.requested_option_id
    )
    action_match = response.final_action is binding.final_action
    direction_match = response.direction is binding.direction
    account_match = response.account == binding.scenario.account
    fingerprint_match = (
        response.intent_fingerprint == binding.intent_fingerprint
    )
    risk_approval_match = (
        response.risk_change_approval_confirmed
        is binding.risk_change_approval_confirmed
    )
    safety_match = (
        not response.trade_authorized
        and not response.order_created
        and not response.execution_ready
        and not response.trading_methods
    )
    checks = (
        (FinalDecisionReviewShadowMismatch.STATUS, status_match),
        (FinalDecisionReviewShadowMismatch.READINESS, readiness_match),
        (FinalDecisionReviewShadowMismatch.OPTION, option_match),
        (FinalDecisionReviewShadowMismatch.ACTION, action_match),
        (FinalDecisionReviewShadowMismatch.DIRECTION, direction_match),
        (FinalDecisionReviewShadowMismatch.ACCOUNT, account_match),
        (FinalDecisionReviewShadowMismatch.FINGERPRINT, fingerprint_match),
        (FinalDecisionReviewShadowMismatch.RISK_APPROVAL, risk_approval_match),
        (FinalDecisionReviewShadowMismatch.SAFETY, safety_match),
    )
    mismatches = tuple(mismatch for mismatch, matched in checks if not matched)
    shadow_valid = not mismatches
    return FinalDecisionReviewShadowValidationV1(
        validated_at=shadow_time,
        source_binding=binding,
        response=response,
        status=(
            FinalDecisionReviewShadowStatus.MATCH
            if shadow_valid
            else FinalDecisionReviewShadowStatus.MISMATCH
        ),
        shadow_valid=shadow_valid,
        status_match=status_match,
        readiness_match=readiness_match,
        option_match=option_match,
        action_match=action_match,
        direction_match=direction_match,
        account_match=account_match,
        fingerprint_match=fingerprint_match,
        risk_approval_match=risk_approval_match,
        safety_match=safety_match,
        mismatches=mismatches,
    )


def build_final_decision_review_shadow(
    binding: ProFormaRiskIntentBindingV1,
    *,
    generated_at: datetime | None = None,
) -> FinalDecisionReviewShadowValidationV1:
    """Adapt and immediately shadow-validate one completed binding."""

    response = adapt_pro_forma_binding_to_final_review(
        binding,
        generated_at=generated_at,
    )
    return validate_final_decision_review_shadow(
        binding,
        response,
        validated_at=response.generated_at,
    )
