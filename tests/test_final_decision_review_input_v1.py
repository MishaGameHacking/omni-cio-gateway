from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

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
    FinalDecisionReviewSourceV1,
    FinalDecisionReviewWarning,
)
from omni_cio.contracts.v1.final_decision_review_action_candidate import (
    FinalDecisionReviewActionCandidateBlocker,
    FinalDecisionReviewActionCandidateStatus,
    FinalDecisionReviewGetActionCandidateV1,
    FinalDecisionReviewOpenApiShadowV1,
)
from omni_cio.contracts.v1.final_decision_review_input import (
    FinalDecisionReviewInputBindingV1,
    FinalDecisionReviewInputCheckCode,
    FinalDecisionReviewInputPolicyV1,
    FinalDecisionReviewInputStatus,
    FinalDecisionReviewReadOnlyQueryV1,
)
from omni_cio.contracts.v1.final_decision_review_release import (
    FinalDecisionReviewReleaseEligibilityV1,
)
from omni_cio.contracts.v1.risk import RiskOverallStatus
from omni_cio.release.final_decision_review_input_v1 import (
    FinalDecisionReviewInputError,
    bind_final_decision_review_read_only_input,
    build_final_decision_review_read_only_query,
)


NOW = datetime(2026, 7, 29, 21, 0, tzinfo=timezone.utc)


def _sha256(value: object) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _response(
    *,
    generated_at: datetime = NOW - timedelta(seconds=30),
) -> FinalDecisionReviewResponseV1:
    intents = (
        FinalDecisionReviewIntentV1(
            request_id="request-1",
            instrument_key="uid:instrument-1",
            side=OrderSide.BUY,
            currency="RUB",
            quantity_lots=2,
            lot_size=10,
            reference_price=Decimal("100"),
            intended_execution_days=1,
            units=20,
            order_notional=Decimal("2000"),
        ),
        FinalDecisionReviewIntentV1(
            request_id="request-2",
            instrument_key="uid:instrument-2",
            side=OrderSide.BUY,
            currency="RUB",
            quantity_lots=1,
            lot_size=1,
            reference_price=Decimal("50"),
            intended_execution_days=1,
            units=1,
            order_notional=Decimal("50"),
        ),
    )
    return FinalDecisionReviewResponseV1(
        generated_at=generated_at,
        status=CapacityDecisionGateStatus.READY,
        disposition=FinalDecisionReviewDisposition.REVIEW_READY,
        review_ready=True,
        abstain=False,
        account=AccountReference(
            masked_id="****1234",
            account_type="brokerage",
        ),
        requested_option_id="option.limited",
        final_option_id="option.limited",
        final_action=DecisionAction.REVIEW_LIMITED_CHANGE,
        direction=OrderSide.BUY,
        intent_fingerprint="a" * 64,
        instrument_count=2,
        intents=intents,
        risk=FinalDecisionReviewRiskSummaryV1(
            current_status=RiskOverallStatus.PASS,
            pro_forma_status=RiskOverallStatus.PASS,
            current_breach_count=0,
            pro_forma_breach_count=0,
            breach_count_delta=0,
            current_warning_count=0,
            pro_forma_warning_count=0,
            warning_count_delta=0,
            current_unknown_count=0,
            pro_forma_unknown_count=0,
            unknown_count_delta=0,
            status_changed=False,
        ),
        risk_change_approval_confirmed=True,
        response_warnings=tuple(FinalDecisionReviewWarning),
        source_count=1,
        provenance=(
            FinalDecisionReviewSourceV1(
                provider="broker",
                operation="read_only_preview",
                retrieved_at=generated_at - timedelta(seconds=10),
            ),
        ),
    )


def _action_shadow(
    response: FinalDecisionReviewResponseV1,
    *,
    valid: bool = True,
) -> FinalDecisionReviewOpenApiShadowV1:
    response_sha256 = _sha256(response.model_dump(mode="json"))
    eligibility = FinalDecisionReviewReleaseEligibilityV1.model_construct(
        response_sha256=response_sha256,
    )
    candidate = FinalDecisionReviewGetActionCandidateV1(
        response_schema_sha256="1" * 64,
        release_eligibility_sha256="2" * 64,
    )
    return FinalDecisionReviewOpenApiShadowV1.model_construct(
        status=(
            FinalDecisionReviewActionCandidateStatus.SHADOW_VALID
            if valid
            else FinalDecisionReviewActionCandidateStatus.SHADOW_BLOCKED
        ),
        shadow_valid=valid,
        candidate=candidate,
        release_eligibility=eligibility,
        blockers=(
            ()
            if valid
            else (
                FinalDecisionReviewActionCandidateBlocker.RELEASE_NOT_ELIGIBLE,
            )
        ),
        production_schema_mutated=False,
        route_added=False,
        openapi_changed=False,
        public_action_created=False,
        trade_authorized=False,
        order_created=False,
        execution_ready=False,
        trading_methods=False,
    )


def _valid_objects() -> tuple[
    FinalDecisionReviewResponseV1,
    FinalDecisionReviewOpenApiShadowV1,
    FinalDecisionReviewReadOnlyQueryV1,
]:
    response = _response()
    shadow = _action_shadow(response)
    query = build_final_decision_review_read_only_query(response, shadow)
    return response, shadow, query


def test_exact_query_binding_is_valid_and_remains_read_only() -> None:
    response, shadow, query = _valid_objects()

    result = bind_final_decision_review_read_only_input(
        query,
        response,
        shadow,
        validated_at=NOW,
    )

    assert result.status is FinalDecisionReviewInputStatus.VALID
    assert result.input_valid is True
    assert result.blockers == ()
    assert result.action_shadow_confirmed is True
    assert result.response_identity_confirmed is True
    assert result.action_candidate_identity_confirmed is True
    assert result.account_confirmed is True
    assert result.options_confirmed is True
    assert result.fingerprint_confirmed is True
    assert result.instruments_confirmed is True
    assert result.request_body_absent is True
    assert result.route_added is False
    assert result.openapi_changed is False
    assert result.public_action_created is False
    assert result.trade_authorized is False
    assert result.order_created is False
    assert result.execution_ready is False
    assert result.trading_methods is False


def test_masked_account_substitution_is_blocked() -> None:
    response, shadow, query = _valid_objects()
    substituted = query.model_copy(
        update={"account": AccountReference(masked_id="****9999")}
    )

    result = bind_final_decision_review_read_only_input(
        substituted,
        response,
        shadow,
        validated_at=NOW,
    )

    assert result.input_valid is False
    assert FinalDecisionReviewInputCheckCode.ACCOUNT in result.blockers


@pytest.mark.parametrize(
    ("field", "value", "blocker"),
    (
        (
            "requested_option_id",
            "option.substituted",
            FinalDecisionReviewInputCheckCode.OPTIONS,
        ),
        (
            "intent_fingerprint",
            "b" * 64,
            FinalDecisionReviewInputCheckCode.INTENT_FINGERPRINT,
        ),
        (
            "response_sha256",
            "c" * 64,
            FinalDecisionReviewInputCheckCode.RESPONSE_IDENTITY,
        ),
        (
            "action_candidate_sha256",
            "d" * 64,
            FinalDecisionReviewInputCheckCode.ACTION_CANDIDATE_IDENTITY,
        ),
    ),
)
def test_identity_substitution_is_blocked(
    field: str,
    value: str,
    blocker: FinalDecisionReviewInputCheckCode,
) -> None:
    response, shadow, query = _valid_objects()
    substituted = query.model_copy(update={field: value})

    result = bind_final_decision_review_read_only_input(
        substituted,
        response,
        shadow,
        validated_at=NOW,
    )

    assert result.input_valid is False
    assert blocker in result.blockers


def test_instrument_order_substitution_is_blocked() -> None:
    response, shadow, query = _valid_objects()
    substituted = query.model_copy(
        update={"instrument_keys": tuple(reversed(query.instrument_keys))}
    )

    result = bind_final_decision_review_read_only_input(
        substituted,
        response,
        shadow,
        validated_at=NOW,
    )

    assert result.input_valid is False
    assert FinalDecisionReviewInputCheckCode.INSTRUMENTS in result.blockers


def test_blocked_action_shadow_cannot_bind_query() -> None:
    response = _response()
    valid_shadow = _action_shadow(response)
    query = build_final_decision_review_read_only_query(response, valid_shadow)
    blocked_shadow = _action_shadow(response, valid=False)

    result = bind_final_decision_review_read_only_input(
        query,
        response,
        blocked_shadow,
        validated_at=NOW,
    )

    assert result.input_valid is False
    assert FinalDecisionReviewInputCheckCode.ACTION_SHADOW in result.blockers


@pytest.mark.parametrize(
    "generated_at",
    (
        NOW - timedelta(seconds=901),
        NOW + timedelta(seconds=61),
    ),
)
def test_stale_or_future_response_is_blocked(generated_at: datetime) -> None:
    response = _response(generated_at=generated_at)
    shadow = _action_shadow(response)
    query = build_final_decision_review_read_only_query(response, shadow)

    result = bind_final_decision_review_read_only_input(
        query,
        response,
        shadow,
        validated_at=NOW,
    )

    assert result.input_valid is False
    assert FinalDecisionReviewInputCheckCode.RESPONSE_FRESHNESS in result.blockers


def test_instrument_policy_bound_is_fail_closed() -> None:
    response, shadow, query = _valid_objects()
    policy = FinalDecisionReviewInputPolicyV1(max_instruments=1)

    result = bind_final_decision_review_read_only_input(
        query,
        response,
        shadow,
        policy=policy,
        validated_at=NOW,
    )

    assert result.input_valid is False
    assert FinalDecisionReviewInputCheckCode.INSTRUMENTS in result.blockers
    assert FinalDecisionReviewInputCheckCode.PAYLOAD_BOUNDS in result.blockers


def test_extra_credentials_and_request_body_are_rejected_by_contract() -> None:
    _, _, query = _valid_objects()
    payload = query.model_dump(mode="python")
    payload["unexpected_auth_input"] = "not-accepted"

    with pytest.raises(ValidationError):
        FinalDecisionReviewReadOnlyQueryV1.model_validate(payload)

    payload = query.model_dump(mode="python")
    payload["request_body_present"] = True
    with pytest.raises(ValidationError):
        FinalDecisionReviewReadOnlyQueryV1.model_validate(payload)


def test_query_and_source_digests_are_deterministic() -> None:
    response, shadow, query = _valid_objects()

    first = bind_final_decision_review_read_only_input(
        query,
        response,
        shadow,
        validated_at=NOW,
    )
    second = bind_final_decision_review_read_only_input(
        query,
        response,
        shadow,
        validated_at=NOW,
    )

    assert first.query_sha256 == second.query_sha256
    assert first.response_sha256 == second.response_sha256
    assert first.action_candidate_sha256 == second.action_candidate_sha256


def test_binding_result_tampering_is_rejected() -> None:
    response, shadow, query = _valid_objects()
    result = bind_final_decision_review_read_only_input(
        query,
        response,
        shadow,
        validated_at=NOW,
    )
    payload = dict(result.__dict__)
    payload["input_valid"] = False

    with pytest.raises(ValidationError):
        FinalDecisionReviewInputBindingV1.model_validate(payload)


def test_naive_binding_timestamp_is_rejected() -> None:
    response, shadow, query = _valid_objects()

    with pytest.raises(
        FinalDecisionReviewInputError,
        match="FINAL_DECISION_REVIEW_INPUT_TIMESTAMP_MUST_BE_AWARE",
    ):
        bind_final_decision_review_read_only_input(
            query,
            response,
            shadow,
            validated_at=NOW.replace(tzinfo=None),
        )
