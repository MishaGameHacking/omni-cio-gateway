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
    FinalDecisionReviewActionCandidateStatus,
    FinalDecisionReviewGetActionCandidateV1,
    FinalDecisionReviewOpenApiShadowV1,
)
from omni_cio.contracts.v1.final_decision_review_release import (
    FinalDecisionReviewReleaseEligibilityV1,
    FinalDecisionReviewReleaseStatus,
)
from omni_cio.contracts.v1.final_decision_review_route_readiness import (
    FinalDecisionReviewRouteControlsV1,
    FinalDecisionReviewRouteReadinessCheckCode,
    FinalDecisionReviewRouteReadinessDossierV1,
    FinalDecisionReviewRouteReadinessStatus,
)
from omni_cio.contracts.v1.risk import RiskOverallStatus
from omni_cio.release.final_decision_review_input_v1 import (
    bind_final_decision_review_read_only_input,
    build_final_decision_review_read_only_query,
)
from omni_cio.release.final_decision_review_route_readiness_v1 import (
    FinalDecisionReviewRouteReadinessError,
    build_final_decision_review_route_readiness_dossier,
)


NOW = datetime(2026, 7, 29, 22, 0, tzinfo=timezone.utc)


def _sha256(value: object) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _response() -> FinalDecisionReviewResponseV1:
    generated_at = NOW - timedelta(seconds=30)
    intent = FinalDecisionReviewIntentV1(
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
    )
    return FinalDecisionReviewResponseV1(
        generated_at=generated_at,
        status=CapacityDecisionGateStatus.READY,
        disposition=FinalDecisionReviewDisposition.REVIEW_READY,
        review_ready=True,
        abstain=False,
        account=AccountReference(masked_id="****1234", account_type="brokerage"),
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
                retrieved_at=generated_at - timedelta(seconds=10),
            ),
        ),
    )


def _sources():  # type: ignore[no-untyped-def]
    response = _response()
    response_sha = _sha256(response.model_dump(mode="json"))
    eligibility = FinalDecisionReviewReleaseEligibilityV1.model_construct(
        status=FinalDecisionReviewReleaseStatus.ELIGIBLE,
        eligible=True,
        response_sha256=response_sha,
        route_approval_granted=False,
        public_action_created=False,
        route_added=False,
        openapi_changed=False,
        trade_authorized=False,
        order_created=False,
        execution_ready=False,
        trading_methods=False,
    )
    candidate = FinalDecisionReviewGetActionCandidateV1(
        response_schema_sha256="1" * 64,
        release_eligibility_sha256="2" * 64,
    )
    action_shadow = FinalDecisionReviewOpenApiShadowV1.model_construct(
        status=FinalDecisionReviewActionCandidateStatus.SHADOW_VALID,
        shadow_valid=True,
        candidate=candidate,
        release_eligibility=eligibility,
        blockers=(),
        production_schema_mutated=False,
        route_added=False,
        openapi_changed=False,
        public_action_created=False,
        trade_authorized=False,
        order_created=False,
        execution_ready=False,
        trading_methods=False,
    )
    query = build_final_decision_review_read_only_query(response, action_shadow)
    input_binding = bind_final_decision_review_read_only_input(
        query,
        response,
        action_shadow,
        validated_at=NOW,
    )
    return response, eligibility, action_shadow, input_binding


def test_complete_dossier_is_ready_only_for_separate_route_review() -> None:
    response, eligibility, action_shadow, input_binding = _sources()

    dossier = build_final_decision_review_route_readiness_dossier(
        response,
        eligibility,
        action_shadow,
        input_binding,
        assessed_at=NOW,
    )

    assert (
        dossier.status
        is FinalDecisionReviewRouteReadinessStatus.READY_FOR_ROUTE_REVIEW
    )
    assert dossier.ready_for_route_review is True
    assert dossier.blockers == ()
    assert dossier.authentication_controls_confirmed is True
    assert dossier.rollback_controls_confirmed is True
    assert dossier.observability_controls_confirmed is True
    assert dossier.safety_boundary_confirmed is True
    assert dossier.route_approval_granted is False
    assert dossier.production_route_added is False
    assert dossier.production_openapi_changed is False
    assert dossier.public_action_created is False
    assert dossier.trade_authorized is False
    assert dossier.order_created is False
    assert dossier.execution_ready is False
    assert dossier.trading_methods is False


@pytest.mark.parametrize(
    ("source_name", "field_name", "value", "blocker"),
    (
        (
            "eligibility",
            "response_sha256",
            "b" * 64,
            FinalDecisionReviewRouteReadinessCheckCode.RESPONSE_IDENTITY,
        ),
        (
            "input_binding",
            "action_candidate_sha256",
            "c" * 64,
            FinalDecisionReviewRouteReadinessCheckCode.CANDIDATE_IDENTITY,
        ),
        (
            "input_binding",
            "query_sha256",
            "d" * 64,
            FinalDecisionReviewRouteReadinessCheckCode.QUERY_IDENTITY,
        ),
    ),
)
def test_digest_substitution_blocks_route_review(
    source_name: str,
    field_name: str,
    value: str,
    blocker: FinalDecisionReviewRouteReadinessCheckCode,
) -> None:
    response, eligibility, action_shadow, input_binding = _sources()
    if source_name == "eligibility":
        eligibility = eligibility.model_copy(update={field_name: value})
    else:
        input_binding = input_binding.model_copy(update={field_name: value})

    dossier = build_final_decision_review_route_readiness_dossier(
        response,
        eligibility,
        action_shadow,
        input_binding,
        assessed_at=NOW,
    )

    assert dossier.ready_for_route_review is False
    assert blocker in dossier.blockers


def test_context_substitution_blocks_route_review() -> None:
    response, eligibility, action_shadow, input_binding = _sources()
    substituted_response = response.model_copy(
        update={"final_option_id": "option.substituted"}
    )

    dossier = build_final_decision_review_route_readiness_dossier(
        substituted_response,
        eligibility,
        action_shadow,
        input_binding,
        assessed_at=NOW,
    )

    assert dossier.ready_for_route_review is False
    assert FinalDecisionReviewRouteReadinessCheckCode.RESPONSE_IDENTITY in (
        dossier.blockers
    )
    assert FinalDecisionReviewRouteReadinessCheckCode.CONTEXT_PARITY in (
        dossier.blockers
    )


def test_missing_server_authorization_control_blocks_route_review() -> None:
    response, eligibility, action_shadow, input_binding = _sources()
    controls = FinalDecisionReviewRouteControlsV1(
        server_authorization_documented=False
    )

    dossier = build_final_decision_review_route_readiness_dossier(
        response,
        eligibility,
        action_shadow,
        input_binding,
        controls=controls,
        assessed_at=NOW,
    )

    assert dossier.ready_for_route_review is False
    assert FinalDecisionReviewRouteReadinessCheckCode.AUTHENTICATION in (
        dossier.blockers
    )


def test_wrong_rollback_reference_blocks_route_review() -> None:
    response, eligibility, action_shadow, input_binding = _sources()
    controls = FinalDecisionReviewRouteControlsV1(
        rollback_runbook_reference="docs/operations/other.md"
    )

    dossier = build_final_decision_review_route_readiness_dossier(
        response,
        eligibility,
        action_shadow,
        input_binding,
        controls=controls,
        assessed_at=NOW,
    )

    assert dossier.ready_for_route_review is False
    assert FinalDecisionReviewRouteReadinessCheckCode.ROLLBACK in dossier.blockers


def test_missing_safe_observability_control_blocks_route_review() -> None:
    response, eligibility, action_shadow, input_binding = _sources()
    controls = FinalDecisionReviewRouteControlsV1(
        correlation_id_required=False
    )

    dossier = build_final_decision_review_route_readiness_dossier(
        response,
        eligibility,
        action_shadow,
        input_binding,
        controls=controls,
        assessed_at=NOW,
    )

    assert dossier.ready_for_route_review is False
    assert FinalDecisionReviewRouteReadinessCheckCode.OBSERVABILITY in (
        dossier.blockers
    )


def test_route_already_marked_reviewed_is_fail_closed() -> None:
    response, eligibility, action_shadow, input_binding = _sources()
    controls = FinalDecisionReviewRouteControlsV1.model_construct(
        production_route_reviewed=True,
        route_approval_granted=False,
    )

    dossier = build_final_decision_review_route_readiness_dossier(
        response,
        eligibility,
        action_shadow,
        input_binding,
        controls=controls,
        assessed_at=NOW,
    )

    assert dossier.ready_for_route_review is False
    assert FinalDecisionReviewRouteReadinessCheckCode.SAFETY_BOUNDARY in (
        dossier.blockers
    )


def test_dossier_tampering_is_rejected() -> None:
    response, eligibility, action_shadow, input_binding = _sources()
    dossier = build_final_decision_review_route_readiness_dossier(
        response,
        eligibility,
        action_shadow,
        input_binding,
        assessed_at=NOW,
    )
    payload = dict(dossier.__dict__)
    payload["ready_for_route_review"] = False

    with pytest.raises(ValidationError):
        FinalDecisionReviewRouteReadinessDossierV1.model_validate(payload)


def test_naive_dossier_timestamp_is_rejected() -> None:
    response, eligibility, action_shadow, input_binding = _sources()

    with pytest.raises(
        FinalDecisionReviewRouteReadinessError,
        match="FINAL_DECISION_REVIEW_ROUTE_READINESS_TIMESTAMP_MUST_BE_AWARE",
    ):
        build_final_decision_review_route_readiness_dossier(
            response,
            eligibility,
            action_shadow,
            input_binding,
            assessed_at=NOW.replace(tzinfo=None),
        )
