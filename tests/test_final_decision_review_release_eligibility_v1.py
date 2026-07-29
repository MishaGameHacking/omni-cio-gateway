from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, cast

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.capacity import OrderSide
from omni_cio.contracts.v1.common import AccountReference
from omni_cio.contracts.v1.decision import DecisionAction
from omni_cio.contracts.v1.decision_capacity import CapacityDecisionGateStatus
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
from omni_cio.contracts.v1.final_decision_review_release import (
    FinalDecisionReviewReleaseCheckCode,
    FinalDecisionReviewReleaseEligibilityV1,
    FinalDecisionReviewReleasePolicyV1,
    FinalDecisionReviewReleaseStatus,
)
from omni_cio.contracts.v1.risk import RiskOverallStatus
from omni_cio.release.final_decision_review_eligibility_v1 import (
    FinalDecisionReviewReleaseEligibilityError,
    assess_final_decision_review_release_eligibility,
)


NOW = datetime(2026, 7, 29, 19, 45, tzinfo=timezone.utc)
ACCOUNT = AccountReference(masked_id="****1234")


def _intent(
    request_id: str = "request-release-a",
    instrument_key: str = "uid:release-a",
) -> FinalDecisionReviewIntentV1:
    return FinalDecisionReviewIntentV1(
        request_id=request_id,
        instrument_key=instrument_key,
        side=OrderSide.BUY,
        currency="RUB",
        quantity_lots=2,
        lot_size=10,
        reference_price=Decimal("100"),
        intended_execution_days=2,
        units=20,
        order_notional=Decimal("2000"),
    )


def _risk() -> FinalDecisionReviewRiskSummaryV1:
    return FinalDecisionReviewRiskSummaryV1(
        current_status=RiskOverallStatus.PASS,
        pro_forma_status=RiskOverallStatus.WARNING,
        current_breach_count=0,
        pro_forma_breach_count=0,
        breach_count_delta=0,
        current_warning_count=0,
        pro_forma_warning_count=1,
        warning_count_delta=1,
        current_unknown_count=0,
        pro_forma_unknown_count=0,
        unknown_count_delta=0,
        status_changed=True,
    )


def _source(
    operation: str = "final-review-release-test",
    retrieved_at: datetime = NOW,
) -> FinalDecisionReviewSourceV1:
    return FinalDecisionReviewSourceV1(
        provider="omni-cio",
        operation=operation,
        retrieved_at=retrieved_at,
    )


def _response(
    *,
    account: AccountReference = ACCOUNT,
    intents: tuple[FinalDecisionReviewIntentV1, ...] | None = None,
    provenance: tuple[FinalDecisionReviewSourceV1, ...] | None = None,
) -> FinalDecisionReviewResponseV1:
    intent_rows = intents or (_intent(),)
    source_rows = provenance or (_source(),)
    return FinalDecisionReviewResponseV1(
        generated_at=NOW,
        status=CapacityDecisionGateStatus.READY,
        disposition=FinalDecisionReviewDisposition.REVIEW_READY,
        review_ready=True,
        abstain=False,
        account=account,
        requested_option_id="option.limited_change",
        final_option_id="option.limited_change",
        final_action=DecisionAction.REVIEW_LIMITED_CHANGE,
        direction=OrderSide.BUY,
        intent_fingerprint="1" * 64,
        instrument_count=len(intent_rows),
        intents=intent_rows,
        risk=_risk(),
        risk_change_approval_confirmed=True,
        blockers=(),
        source_warnings=("exact_intent_fingerprint_bound",),
        response_warnings=tuple(FinalDecisionReviewWarning),
        source_count=len(source_rows),
        provenance=source_rows,
    )


def _shadow(
    response: FinalDecisionReviewResponseV1,
    *,
    status: FinalDecisionReviewShadowStatus = FinalDecisionReviewShadowStatus.MATCH,
    valid: bool = True,
    mismatches: tuple[FinalDecisionReviewShadowMismatch, ...] = (),
) -> FinalDecisionReviewShadowValidationV1:
    return FinalDecisionReviewShadowValidationV1.model_construct(
        validated_at=NOW,
        source_binding=cast(Any, object()),
        response=response,
        status=status,
        shadow_valid=valid,
        status_match=valid,
        readiness_match=valid,
        option_match=valid,
        action_match=valid,
        direction_match=valid,
        account_match=valid,
        fingerprint_match=valid,
        risk_approval_match=valid,
        safety_match=valid,
        mismatches=mismatches,
    )


def test_ready_response_is_eligible_only_for_future_get_contract_review() -> None:
    response = _response()
    result = assess_final_decision_review_release_eligibility(
        response,
        _shadow(response),
        assessed_at=NOW,
    )

    assert result.status is FinalDecisionReviewReleaseStatus.ELIGIBLE
    assert result.eligible is True
    assert result.shadow_parity_confirmed is True
    assert result.schema_compatible is True
    assert result.account_masking_confirmed is True
    assert result.payload_bounds_confirmed is True
    assert result.provenance_confirmed is True
    assert result.sensitive_data_absent is True
    assert result.execution_surface_absent is True
    assert result.mutation_surface_absent is True
    assert result.get_read_only_compatible is True
    assert result.blockers == ()
    assert len(result.response_sha256) == 64
    assert result.payload_size_bytes > 0
    assert result.route_approval_granted is False
    assert result.public_action_created is False
    assert result.route_added is False
    assert result.openapi_changed is False
    assert result.trade_authorized is False
    assert result.order_created is False
    assert result.execution_ready is False
    assert result.trading_methods is False


def test_non_get_method_is_ineligible() -> None:
    response = _response()
    result = assess_final_decision_review_release_eligibility(
        response,
        _shadow(response),
        intended_http_method="POST",
        assessed_at=NOW,
    )

    assert result.status is FinalDecisionReviewReleaseStatus.INELIGIBLE
    assert result.eligible is False
    assert result.get_read_only_compatible is False
    assert FinalDecisionReviewReleaseCheckCode.HTTP_METHOD in result.blockers


def test_shadow_mismatch_blocks_release_eligibility() -> None:
    response = _response()
    shadow = _shadow(
        response,
        status=FinalDecisionReviewShadowStatus.MISMATCH,
        valid=False,
        mismatches=(FinalDecisionReviewShadowMismatch.OPTION,),
    )
    result = assess_final_decision_review_release_eligibility(
        response,
        shadow,
        assessed_at=NOW,
    )

    assert result.shadow_parity_confirmed is False
    assert FinalDecisionReviewReleaseCheckCode.SHADOW_PARITY in result.blockers
    assert result.primary_blocker is FinalDecisionReviewReleaseCheckCode.SHADOW_PARITY


def test_schema_substitution_is_blocked() -> None:
    response = _response().model_copy(update={"schema_version": "2.0"})
    result = assess_final_decision_review_release_eligibility(
        response,
        _shadow(response),
        assessed_at=NOW,
    )

    assert result.schema_compatible is False
    assert FinalDecisionReviewReleaseCheckCode.SCHEMA_VERSION in result.blockers


def test_unmasked_account_and_execution_flag_are_blocked() -> None:
    unmasked = AccountReference.model_construct(masked_id="123456789012")
    response = _response().model_copy(
        update={"account": unmasked, "trade_authorized": True}
    )
    result = assess_final_decision_review_release_eligibility(
        response,
        _shadow(response),
        assessed_at=NOW,
    )

    assert result.account_masking_confirmed is False
    assert result.execution_surface_absent is False
    assert FinalDecisionReviewReleaseCheckCode.ACCOUNT_MASKING in result.blockers
    assert FinalDecisionReviewReleaseCheckCode.EXECUTION_SURFACE in result.blockers


def test_payload_and_source_bounds_are_fail_closed() -> None:
    sources = (_source("source-a"), _source("source-b"))
    response = _response(provenance=sources)
    policy = FinalDecisionReviewReleasePolicyV1(
        max_payload_bytes=1_024,
        max_sources=1,
    )
    result = assess_final_decision_review_release_eligibility(
        response,
        _shadow(response),
        policy=policy,
        assessed_at=NOW,
    )

    assert result.payload_bounds_confirmed is False
    assert FinalDecisionReviewReleaseCheckCode.PAYLOAD_SIZE in result.blockers
    assert FinalDecisionReviewReleaseCheckCode.SOURCE_COUNT in result.blockers


def test_future_provenance_is_blocked() -> None:
    future_source = _source(retrieved_at=NOW + timedelta(minutes=10))
    response = _response(provenance=(future_source,))
    result = assess_final_decision_review_release_eligibility(
        response,
        _shadow(response),
        assessed_at=NOW,
    )

    assert result.provenance_confirmed is False
    assert FinalDecisionReviewReleaseCheckCode.PROVENANCE in result.blockers


def test_digest_is_deterministic_for_the_same_response() -> None:
    response = _response()
    first = assess_final_decision_review_release_eligibility(
        response,
        _shadow(response),
        assessed_at=NOW,
    )
    second = assess_final_decision_review_release_eligibility(
        response,
        _shadow(response),
        assessed_at=NOW,
    )

    assert first.response_sha256 == second.response_sha256
    assert first.payload_size_bytes == second.payload_size_bytes


def test_eligibility_result_tampering_is_rejected() -> None:
    response = _response()
    result = assess_final_decision_review_release_eligibility(
        response,
        _shadow(response),
        assessed_at=NOW,
    )
    payload = result.model_dump(mode="python")
    payload["eligible"] = False

    with pytest.raises(ValidationError):
        FinalDecisionReviewReleaseEligibilityV1.model_validate(payload)


def test_naive_assessment_timestamp_is_rejected() -> None:
    response = _response()
    with pytest.raises(
        FinalDecisionReviewReleaseEligibilityError,
        match="FINAL_DECISION_REVIEW_RELEASE_TIMESTAMP_MUST_BE_AWARE",
    ):
        assess_final_decision_review_release_eligibility(
            response,
            _shadow(response),
            assessed_at=NOW.replace(tzinfo=None),
        )
