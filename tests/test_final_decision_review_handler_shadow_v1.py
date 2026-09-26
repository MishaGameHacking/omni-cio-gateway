from __future__ import annotations

from datetime import datetime, timezone
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
from omni_cio.contracts.v1.final_decision_review_handler_shadow import (
    FinalDecisionReviewHandlerErrorCode,
    FinalDecisionReviewHandlerHttpStatus,
    FinalDecisionReviewHandlerShadowResultV1,
    FinalDecisionReviewHandlerShadowStatus,
)
from omni_cio.contracts.v1.final_decision_review_input import (
    FinalDecisionReviewInputBindingV1,
    FinalDecisionReviewInputCheckCode,
    FinalDecisionReviewInputPolicyV1,
    FinalDecisionReviewInputStatus,
    FinalDecisionReviewReadOnlyQueryV1,
)
from omni_cio.contracts.v1.final_decision_review_route_plan import (
    FinalDecisionReviewAcceptanceCheckCode,
    FinalDecisionReviewRouteImplementationPlanV1,
    FinalDecisionReviewRoutePlanStatus,
)
from omni_cio.contracts.v1.final_decision_review_route_readiness import (
    FinalDecisionReviewRouteReadinessDossierV1,
)
from omni_cio.contracts.v1.observability import (
    ExternalCallStatus,
    ObservabilityOutcome,
)
from omni_cio.contracts.v1.risk import RiskOverallStatus
from omni_cio.release.final_decision_review_handler_shadow_v1 import (
    FinalDecisionReviewHandlerShadowError,
    evaluate_final_decision_review_handler_shadow,
    final_decision_review_handler_error_mapping,
)


NOW = datetime(2026, 7, 29, 23, 0, tzinfo=timezone.utc)


def _response() -> FinalDecisionReviewResponseV1:
    intent = FinalDecisionReviewIntentV1(
        request_id="request-1",
        instrument_key="uid:instrument-1",
        side=OrderSide.BUY,
        currency="RUB",
        quantity_lots=1,
        lot_size=10,
        reference_price=Decimal("100"),
        intended_execution_days=1,
        units=10,
        order_notional=Decimal("1000"),
    )
    return FinalDecisionReviewResponseV1(
        generated_at=NOW,
        status=CapacityDecisionGateStatus.READY,
        disposition=FinalDecisionReviewDisposition.REVIEW_READY,
        review_ready=True,
        abstain=False,
        account=AccountReference(masked_id="****1234"),
        requested_option_id="option.limited",
        final_option_id="option.limited",
        final_action=DecisionAction.REVIEW_LIMITED_CHANGE,
        direction=OrderSide.BUY,
        intent_fingerprint="a" * 64,
        instrument_count=1,
        intents=(intent,),
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
                retrieved_at=NOW,
            ),
        ),
    )


def _sources() -> tuple[
    FinalDecisionReviewRouteImplementationPlanV1,
    FinalDecisionReviewInputBindingV1,
]:
    response = _response()
    policy = FinalDecisionReviewInputPolicyV1()
    query = FinalDecisionReviewReadOnlyQueryV1(
        account=response.account,
        requested_option_id=response.requested_option_id,
        final_option_id=response.final_option_id,
        intent_fingerprint=response.intent_fingerprint,
        instrument_count=1,
        instrument_keys=("uid:instrument-1",),
        response_sha256="1" * 64,
        action_candidate_sha256="2" * 64,
    )
    binding = FinalDecisionReviewInputBindingV1.model_construct(
        status=FinalDecisionReviewInputStatus.VALID,
        input_valid=True,
        blockers=(),
        policy=policy,
        query=query,
        query_sha256="3" * 64,
        response_sha256="1" * 64,
        action_candidate_sha256="2" * 64,
    )
    dossier = FinalDecisionReviewRouteReadinessDossierV1.model_construct(
        response=response,
        input_binding=binding,
    )
    plan = FinalDecisionReviewRouteImplementationPlanV1.model_construct(
        status=FinalDecisionReviewRoutePlanStatus.READY_FOR_IMPLEMENTATION_REVIEW,
        ready_for_implementation_review=True,
        blockers=(),
        readiness_dossier=dossier,
    )
    return plan, binding


def test_exact_shadow_handler_returns_compact_response_and_safe_event() -> None:
    plan, binding = _sources()

    result = evaluate_final_decision_review_handler_shadow(
        plan,
        binding,
        authentication_confirmed=True,
        correlation_id="corr:12345678",
        request_id="request:12345678",
        handled_at=NOW,
    )

    assert result.status is FinalDecisionReviewHandlerShadowStatus.SUCCESS
    assert result.http_status is FinalDecisionReviewHandlerHttpStatus.OK
    assert result.response == plan.readiness_dossier.response
    assert result.error_code is None
    assert result.observability_event.outcome is ObservabilityOutcome.SUCCESS
    assert result.observability_event.account.masked_id == "****1234"
    assert result.observability_event.contains_sensitive_payload is False
    assert result.observability_event.trading_methods is False
    assert result.observability_event.external_call is not None
    assert (
        result.observability_event.external_call.status is ExternalCallStatus.NOT_CALLED
    )
    assert result.shadow_only is True
    assert result.route_registered is False
    assert result.production_openapi_changed is False
    assert result.public_action_created is False
    assert result.external_broker_called is False
    assert result.trade_authorized is False
    assert result.order_created is False
    assert result.execution_ready is False
    assert result.trading_methods is False


def test_missing_authentication_maps_to_401_without_response() -> None:
    plan, binding = _sources()

    result = evaluate_final_decision_review_handler_shadow(
        plan,
        binding,
        authentication_confirmed=False,
        correlation_id="corr:12345678",
        handled_at=NOW,
    )

    assert result.status is FinalDecisionReviewHandlerShadowStatus.REJECTED
    assert result.http_status is FinalDecisionReviewHandlerHttpStatus.UNAUTHORIZED
    assert result.error_code is FinalDecisionReviewHandlerErrorCode.AUTHENTICATION_REQUIRED
    assert result.response is None


def test_blocked_input_binding_maps_to_409() -> None:
    plan, binding = _sources()
    blocked = binding.model_copy(
        update={
            "status": FinalDecisionReviewInputStatus.BLOCKED,
            "input_valid": False,
            "blockers": (FinalDecisionReviewInputCheckCode.ACCOUNT,),
        }
    )

    result = evaluate_final_decision_review_handler_shadow(
        plan,
        blocked,
        authentication_confirmed=True,
        correlation_id="corr:12345678",
        handled_at=NOW,
    )

    assert result.status is FinalDecisionReviewHandlerShadowStatus.REJECTED
    assert result.http_status is FinalDecisionReviewHandlerHttpStatus.CONFLICT
    assert result.error_code is FinalDecisionReviewHandlerErrorCode.SOURCE_CONFLICT
    assert result.response is None


def test_identity_substitution_maps_to_409() -> None:
    plan, binding = _sources()
    substituted = binding.model_copy(update={"query_sha256": "4" * 64})

    result = evaluate_final_decision_review_handler_shadow(
        plan,
        substituted,
        authentication_confirmed=True,
        correlation_id="corr:12345678",
        handled_at=NOW,
    )

    assert result.http_status is FinalDecisionReviewHandlerHttpStatus.CONFLICT
    assert result.error_code is FinalDecisionReviewHandlerErrorCode.SOURCE_CONFLICT


def test_unavailable_source_maps_to_503() -> None:
    plan, binding = _sources()

    result = evaluate_final_decision_review_handler_shadow(
        plan,
        binding,
        authentication_confirmed=True,
        source_available=False,
        correlation_id="corr:12345678",
        handled_at=NOW,
    )

    assert result.status is FinalDecisionReviewHandlerShadowStatus.UNAVAILABLE
    assert (
        result.http_status is FinalDecisionReviewHandlerHttpStatus.SERVICE_UNAVAILABLE
    )
    assert result.error_code is FinalDecisionReviewHandlerErrorCode.SOURCE_UNAVAILABLE


def test_blocked_route_plan_maps_to_503() -> None:
    plan, binding = _sources()
    blocked_plan = plan.model_copy(
        update={
            "status": FinalDecisionReviewRoutePlanStatus.BLOCKED,
            "ready_for_implementation_review": False,
            "blockers": (FinalDecisionReviewAcceptanceCheckCode.SOURCE_DOSSIER,),
        }
    )

    result = evaluate_final_decision_review_handler_shadow(
        blocked_plan,
        binding,
        authentication_confirmed=True,
        correlation_id="corr:12345678",
        handled_at=NOW,
    )

    assert (
        result.http_status is FinalDecisionReviewHandlerHttpStatus.SERVICE_UNAVAILABLE
    )


def test_error_mapping_is_complete_and_fixed() -> None:
    mappings = final_decision_review_handler_error_mapping()

    assert {row.error_code for row in mappings} == set(
        FinalDecisionReviewHandlerErrorCode
    )
    assert {row.http_status for row in mappings} == {
        FinalDecisionReviewHandlerHttpStatus.BAD_REQUEST,
        FinalDecisionReviewHandlerHttpStatus.UNAUTHORIZED,
        FinalDecisionReviewHandlerHttpStatus.CONFLICT,
        FinalDecisionReviewHandlerHttpStatus.UNPROCESSABLE_ENTITY,
        FinalDecisionReviewHandlerHttpStatus.SERVICE_UNAVAILABLE,
    }


def test_shadow_result_tampering_is_rejected() -> None:
    plan, binding = _sources()
    result = evaluate_final_decision_review_handler_shadow(
        plan,
        binding,
        authentication_confirmed=True,
        correlation_id="corr:12345678",
        handled_at=NOW,
    )
    payload = dict(result.__dict__)
    payload["route_registered"] = True

    with pytest.raises(ValidationError):
        FinalDecisionReviewHandlerShadowResultV1.model_validate(payload)


def test_naive_shadow_timestamp_is_rejected() -> None:
    plan, binding = _sources()

    with pytest.raises(
        FinalDecisionReviewHandlerShadowError,
        match="FINAL_DECISION_REVIEW_HANDLER_SHADOW_TIMESTAMP_MUST_BE_AWARE",
    ):
        evaluate_final_decision_review_handler_shadow(
            plan,
            binding,
            authentication_confirmed=True,
            correlation_id="corr:12345678",
            handled_at=NOW.replace(tzinfo=None),
        )
