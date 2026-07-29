from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.capacity import CapacityOrderRequestV1, OrderSide
from omni_cio.contracts.v1.common import (
    AccountReference,
    Completeness,
    ContractMetadata,
    DataQuality,
    QualityMetadata,
    SourceReference,
)
from omni_cio.contracts.v1.decision import DecisionAction
from omni_cio.contracts.v1.decision_capacity import CapacityDecisionGateStatus
from omni_cio.contracts.v1.decision_pro_forma_risk_binding import (
    ProFormaRiskIntentBindingBlocker,
    ProFormaRiskIntentBindingV1,
    ProFormaRiskIntentBindingWarning,
    ProFormaRiskScenarioV1,
    calculate_pro_forma_intent_fingerprint,
)
from omni_cio.contracts.v1.decision_risk_pretrade_explanation import (
    RiskPreTradeExplanationEnvelopeV1,
)
from omni_cio.contracts.v1.final_decision_review import (
    FinalDecisionReviewDisposition,
    FinalDecisionReviewResponseV1,
    FinalDecisionReviewShadowMismatch,
    FinalDecisionReviewShadowStatus,
    FinalDecisionReviewWarning,
)
from omni_cio.contracts.v1.risk import RiskOverallStatus, RiskPolicyEvaluationV1
from omni_cio.decision.final_decision_review_v1 import (
    FinalDecisionReviewError,
    adapt_pro_forma_binding_to_final_review,
    build_final_decision_review_shadow,
    validate_final_decision_review_shadow,
)
from omni_cio.risk.policy_v1 import default_conservative_risk_policy


NOW = datetime(2026, 7, 29, 22, 30, tzinfo=timezone.utc)
ACCOUNT = AccountReference(masked_id="****1234")
KEY = "uid:final-review-a"
OPTION = "option.limited_change"
NO_ACTION = "option.no_action"
FINGERPRINT_PATTERN = r"^[0-9a-f]{64}$"


def _source(operation: str, *, source_time: datetime = NOW) -> SourceReference:
    return SourceReference(
        provider="omni-cio",
        operation=operation,
        retrieved_at=source_time,
        source_id="internal-source-id-not-exposed",
    )


def _metadata(
    operation: str,
    *,
    provenance: tuple[SourceReference, ...] | None = None,
) -> ContractMetadata:
    return ContractMetadata(
        schema_name="risk_policy_evaluation",
        retrieved_at=NOW,
        account=ACCOUNT,
        provenance=provenance or (_source(operation),),
        quality=QualityMetadata(
            quality=DataQuality.VERIFIED,
            completeness=Completeness.COMPLETE,
        ),
    )


def _risk(
    operation: str,
    *,
    status: RiskOverallStatus,
    breaches: int = 0,
    warnings: int = 0,
    unknowns: int = 0,
    provenance: tuple[SourceReference, ...] | None = None,
) -> RiskPolicyEvaluationV1:
    return RiskPolicyEvaluationV1.model_construct(
        metadata=_metadata(operation, provenance=provenance),
        policy=default_conservative_risk_policy(),
        overall_status=status,
        decision_ready=True,
        checks=(),
        breach_count=breaches,
        warning_count=warnings,
        unknown_count=unknowns,
        no_cross_currency_aggregation=True,
    )


def _request() -> CapacityOrderRequestV1:
    return CapacityOrderRequestV1(
        request_id="request-final-review-a",
        instrument_key=KEY,
        side=OrderSide.BUY,
        currency="RUB",
        quantity_lots=2,
        lot_size=10,
        reference_price=Decimal("100"),
        intended_execution_days=2,
        units=20,
        order_notional=Decimal("2000"),
    )


def _binding(
    *,
    ready: bool = True,
    shared_provenance: bool = False,
) -> ProFormaRiskIntentBindingV1:
    request = _request()
    fingerprint = calculate_pro_forma_intent_fingerprint(
        account_masked_id=ACCOUNT.masked_id,
        requested_option_id=OPTION,
        direction=OrderSide.BUY,
        capacity_requests=(request,),
    )
    shared_source = (_source("shared-risk-source"),)
    current_risk = _risk(
        "current-risk",
        status=RiskOverallStatus.PASS,
        provenance=shared_source if shared_provenance else None,
    )
    pro_forma_risk = _risk(
        "pro-forma-risk",
        status=RiskOverallStatus.WARNING,
        warnings=1,
        provenance=shared_source if shared_provenance else None,
    )
    base = RiskPreTradeExplanationEnvelopeV1.model_construct(
        risk_evaluation=current_risk,
    )
    scenario = ProFormaRiskScenarioV1.model_construct(
        scenario_id="scenario-final-review-a",
        generated_at=NOW,
        account=ACCOUNT,
        requested_option_id=OPTION,
        direction=OrderSide.BUY,
        capacity_requests=(request,),
        intent_fingerprint=fingerprint,
        risk_evaluation=pro_forma_risk,
    )
    blockers = (
        ()
        if ready
        else (ProFormaRiskIntentBindingBlocker.PRO_FORMA_RISK_NOT_READY,)
    )
    return ProFormaRiskIntentBindingV1.model_construct(
        assessed_at=NOW,
        status=(
            CapacityDecisionGateStatus.READY
            if ready
            else CapacityDecisionGateStatus.ABSTAIN
        ),
        review_ready=ready,
        abstain=not ready,
        base_explanation=base,
        scenario=scenario,
        no_action_option_id=NO_ACTION,
        requested_option_id=OPTION,
        final_option_id=OPTION if ready else NO_ACTION,
        final_action=(
            DecisionAction.REVIEW_LIMITED_CHANGE
            if ready
            else DecisionAction.WAIT_FOR_DATA
        ),
        direction=OrderSide.BUY,
        intent_fingerprint=fingerprint,
        current_risk_status=RiskOverallStatus.PASS,
        pro_forma_risk_status=RiskOverallStatus.WARNING,
        current_breach_count=0,
        pro_forma_breach_count=0,
        breach_count_delta=0,
        current_warning_count=0,
        pro_forma_warning_count=1,
        warning_count_delta=1,
        current_unknown_count=0,
        pro_forma_unknown_count=0,
        unknown_count_delta=0,
        risk_status_changed=True,
        primary_blocker=blockers[0] if blockers else None,
        blockers=blockers,
        warnings=(
            ProFormaRiskIntentBindingWarning.EXACT_INTENT_FINGERPRINT_BOUND,
            ProFormaRiskIntentBindingWarning.CURRENT_AND_PRO_FORMA_RISK_RETAINED,
            ProFormaRiskIntentBindingWarning.RISK_STATUS_DELTA_NOT_RETURN_FORECAST,
            ProFormaRiskIntentBindingWarning.PRO_FORMA_RISK_NOT_RECOMPUTED_BY_BINDING,
            ProFormaRiskIntentBindingWarning.REVIEW_ONLY_NO_ORDER_CREATED,
        ),
        risk_change_approval_confirmed=ready,
    )


def test_ready_binding_becomes_compact_user_safe_response() -> None:
    response = adapt_pro_forma_binding_to_final_review(
        _binding(),
        generated_at=NOW,
    )

    assert response.status is CapacityDecisionGateStatus.READY
    assert response.disposition is FinalDecisionReviewDisposition.REVIEW_READY
    assert response.review_ready is True
    assert response.abstain is False
    assert response.account.masked_id == "****1234"
    assert response.requested_option_id == OPTION
    assert response.final_option_id == OPTION
    assert response.final_action is DecisionAction.REVIEW_LIMITED_CHANGE
    assert response.direction is OrderSide.BUY
    assert response.instrument_count == 1
    assert response.intents[0].instrument_key == KEY
    assert response.intents[0].quantity_lots == 2
    assert response.intents[0].units == 20
    assert response.intents[0].order_notional == Decimal("2000")
    assert response.risk.current_status is RiskOverallStatus.PASS
    assert response.risk.pro_forma_status is RiskOverallStatus.WARNING
    assert response.risk.warning_count_delta == 1
    assert response.risk.status_changed is True
    assert response.risk_change_approval_confirmed is True
    assert response.primary_blocker is None
    assert response.blockers == ()
    assert response.source_count == 2
    assert all(not hasattr(row, "source_id") for row in response.provenance)
    assert response.full_account_identifier_present is False
    assert response.source_contracts_exposed is False
    assert response.public_action_exposed is False
    assert response.source_values_recomputed is False
    assert response.option_selected_by_adapter is False
    assert response.trade_authorized is False
    assert response.order_created is False
    assert response.execution_ready is False
    assert response.trading_methods is False
    assert (
        FinalDecisionReviewWarning.REVIEW_ONLY_NO_TRADE_AUTHORIZATION
        in response.response_warnings
    )


def test_blocked_binding_preserves_wait_for_data() -> None:
    response = adapt_pro_forma_binding_to_final_review(
        _binding(ready=False),
        generated_at=NOW,
    )

    assert response.status is CapacityDecisionGateStatus.ABSTAIN
    assert response.disposition is FinalDecisionReviewDisposition.WAIT_FOR_DATA
    assert response.review_ready is False
    assert response.abstain is True
    assert response.final_option_id == NO_ACTION
    assert response.final_action is DecisionAction.WAIT_FOR_DATA
    assert response.risk_change_approval_confirmed is False
    assert response.primary_blocker == "pro_forma_risk_not_ready"
    assert response.blockers == ("pro_forma_risk_not_ready",)


def test_shadow_adapter_confirms_complete_parity() -> None:
    result = build_final_decision_review_shadow(
        _binding(),
        generated_at=NOW,
    )

    assert result.status is FinalDecisionReviewShadowStatus.MATCH
    assert result.shadow_valid is True
    assert result.mismatches == ()
    assert result.status_match is True
    assert result.readiness_match is True
    assert result.option_match is True
    assert result.action_match is True
    assert result.direction_match is True
    assert result.account_match is True
    assert result.fingerprint_match is True
    assert result.risk_approval_match is True
    assert result.safety_match is True
    assert result.shadow_only is True
    assert result.route_added is False
    assert result.trade_authorized is False
    assert result.order_created is False
    assert result.execution_ready is False
    assert result.trading_methods is False


def test_shadow_detects_post_adapter_option_substitution() -> None:
    binding = _binding()
    response = adapt_pro_forma_binding_to_final_review(binding, generated_at=NOW)
    substituted = response.model_copy(
        update={"final_option_id": "option.strategic_rebalance"}
    )

    result = validate_final_decision_review_shadow(
        binding,
        substituted,
        validated_at=NOW,
    )

    assert result.status is FinalDecisionReviewShadowStatus.MISMATCH
    assert result.shadow_valid is False
    assert result.option_match is False
    assert result.mismatches == (FinalDecisionReviewShadowMismatch.OPTION,)
    assert result.trade_authorized is False


def test_provenance_is_deduplicated_and_source_ids_are_removed() -> None:
    response = adapt_pro_forma_binding_to_final_review(
        _binding(shared_provenance=True),
        generated_at=NOW,
    )

    assert response.source_count == 1
    assert response.provenance[0].provider == "omni-cio"
    assert response.provenance[0].operation == "shared-risk-source"
    assert response.model_dump(mode="json")["provenance"] == [
        {
            "provider": "omni-cio",
            "operation": "shared-risk-source",
            "retrieved_at": NOW.isoformat().replace("+00:00", "Z"),
        }
    ]


def test_response_contract_rejects_safety_and_arithmetic_tampering() -> None:
    response = adapt_pro_forma_binding_to_final_review(
        _binding(),
        generated_at=NOW,
    )
    payload = dict(response.__dict__)
    payload["trade_authorized"] = True
    with pytest.raises(ValidationError):
        FinalDecisionReviewResponseV1.model_validate(payload)

    payload = dict(response.__dict__)
    risk_payload = dict(response.risk.__dict__)
    risk_payload["warning_count_delta"] = 99
    payload["risk"] = risk_payload
    with pytest.raises(ValidationError):
        FinalDecisionReviewResponseV1.model_validate(payload)


def test_naive_adapter_and_shadow_timestamps_are_rejected() -> None:
    binding = _binding()
    with pytest.raises(
        FinalDecisionReviewError,
        match="FINAL_DECISION_REVIEW_TIMESTAMP_MUST_BE_AWARE",
    ):
        adapt_pro_forma_binding_to_final_review(
            binding,
            generated_at=NOW.replace(tzinfo=None),
        )

    response = adapt_pro_forma_binding_to_final_review(binding, generated_at=NOW)
    with pytest.raises(
        FinalDecisionReviewError,
        match="FINAL_DECISION_REVIEW_TIMESTAMP_MUST_BE_AWARE",
    ):
        validate_final_decision_review_shadow(
            binding,
            response,
            validated_at=NOW.replace(tzinfo=None),
        )
