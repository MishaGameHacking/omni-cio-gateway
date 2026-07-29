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
from omni_cio.contracts.v1.final_decision_review_input import (
    FinalDecisionReviewInputBindingV1,
    FinalDecisionReviewInputPolicyV1,
    FinalDecisionReviewReadOnlyQueryV1,
)
from omni_cio.contracts.v1.final_decision_review_route_plan import (
    FinalDecisionReviewAcceptanceCheckCode,
    FinalDecisionReviewAcceptanceStage,
    FinalDecisionReviewProposedRouteV1,
    FinalDecisionReviewRouteImplementationPlanV1,
    FinalDecisionReviewRoutePlanStatus,
)
from omni_cio.contracts.v1.final_decision_review_route_readiness import (
    FinalDecisionReviewRouteControlsV1,
    FinalDecisionReviewRouteReadinessCheckCode,
    FinalDecisionReviewRouteReadinessDossierV1,
    FinalDecisionReviewRouteReadinessStatus,
)
from omni_cio.contracts.v1.risk import RiskOverallStatus
from omni_cio.release.final_decision_review_route_plan_v1 import (
    FinalDecisionReviewRoutePlanError,
    build_final_decision_review_route_implementation_plan,
    default_final_decision_review_acceptance_cases,
)


NOW = datetime(2026, 7, 29, 22, 30, tzinfo=timezone.utc)


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


def _dossier() -> FinalDecisionReviewRouteReadinessDossierV1:
    response = _response()
    policy = FinalDecisionReviewInputPolicyV1()
    query = FinalDecisionReviewReadOnlyQueryV1(
        account=response.account,
        requested_option_id=response.requested_option_id,
        final_option_id=response.final_option_id,
        intent_fingerprint=response.intent_fingerprint,
        instrument_count=response.instrument_count,
        instrument_keys=tuple(row.instrument_key for row in response.intents),
        response_sha256="1" * 64,
        action_candidate_sha256="2" * 64,
    )
    binding = FinalDecisionReviewInputBindingV1.model_construct(
        policy=policy,
        query=query,
    )
    controls = FinalDecisionReviewRouteControlsV1()
    return FinalDecisionReviewRouteReadinessDossierV1.model_construct(
        status=FinalDecisionReviewRouteReadinessStatus.READY_FOR_ROUTE_REVIEW,
        ready_for_route_review=True,
        blockers=(),
        response=response,
        input_binding=binding,
        controls=controls,
        authentication_controls_confirmed=True,
        observability_controls_confirmed=True,
        route_approval_granted=False,
        production_route_added=False,
        production_openapi_changed=False,
    )


def test_default_plan_is_complete_but_does_not_authorize_implementation() -> None:
    dossier = _dossier()

    plan = build_final_decision_review_route_implementation_plan(
        dossier,
        prepared_at=NOW,
    )

    assert (
        plan.status
        is FinalDecisionReviewRoutePlanStatus.READY_FOR_IMPLEMENTATION_REVIEW
    )
    assert plan.ready_for_implementation_review is True
    assert plan.blockers == ()
    assert len(plan.acceptance_cases) == 13
    assert {case.stage for case in plan.acceptance_cases} == set(
        FinalDecisionReviewAcceptanceStage
    )
    assert all(case.blocking for case in plan.acceptance_cases)
    assert all(not case.executed and not case.passed for case in plan.acceptance_cases)
    assert plan.implementation_authorized is False
    assert plan.route_approval_granted is False
    assert plan.production_route_added is False
    assert plan.production_openapi_changed is False
    assert plan.deployment_performed is False
    assert plan.gpt_preview_performed is False
    assert plan.trade_authorized is False
    assert plan.order_created is False
    assert plan.execution_ready is False
    assert plan.trading_methods is False


def test_blocked_readiness_dossier_blocks_implementation_review() -> None:
    dossier = _dossier().model_copy(
        update={
            "status": FinalDecisionReviewRouteReadinessStatus.BLOCKED,
            "ready_for_route_review": False,
            "blockers": (
                FinalDecisionReviewRouteReadinessCheckCode.SOURCE_STATUSES,
            ),
        }
    )

    plan = build_final_decision_review_route_implementation_plan(
        dossier,
        prepared_at=NOW,
    )

    assert plan.ready_for_implementation_review is False
    assert FinalDecisionReviewAcceptanceCheckCode.SOURCE_DOSSIER in plan.blockers


def test_changed_route_contract_is_blocked() -> None:
    route = FinalDecisionReviewProposedRouteV1().model_copy(
        update={"method": "post"}
    )

    plan = build_final_decision_review_route_implementation_plan(
        _dossier(),
        proposed_route=route,
        prepared_at=NOW,
    )

    assert plan.ready_for_implementation_review is False
    assert FinalDecisionReviewAcceptanceCheckCode.PROPOSED_CONTRACT in plan.blockers


def test_query_allowlist_drift_is_blocked() -> None:
    route = FinalDecisionReviewProposedRouteV1().model_copy(
        update={"query_parameters": ("account",)}
    )

    plan = build_final_decision_review_route_implementation_plan(
        _dossier(),
        proposed_route=route,
        prepared_at=NOW,
    )

    assert plan.ready_for_implementation_review is False
    assert FinalDecisionReviewAcceptanceCheckCode.QUERY_ALLOWLIST in plan.blockers


def test_missing_observability_control_is_blocked() -> None:
    dossier = _dossier()
    controls = dossier.controls.model_copy(update={"correlation_id_required": False})
    dossier = dossier.model_copy(
        update={
            "controls": controls,
            "observability_controls_confirmed": False,
        }
    )

    plan = build_final_decision_review_route_implementation_plan(
        dossier,
        prepared_at=NOW,
    )

    assert plan.ready_for_implementation_review is False
    assert FinalDecisionReviewAcceptanceCheckCode.OBSERVABILITY in plan.blockers


def test_acceptance_cases_cannot_claim_execution_or_success() -> None:
    cases = list(default_final_decision_review_acceptance_cases())
    cases[0] = cases[0].model_construct(
        **cases[0].model_dump(),
        executed=True,
        passed=True,
    )

    with pytest.raises(ValidationError):
        build_final_decision_review_route_implementation_plan(
            _dossier(),
            acceptance_cases=tuple(cases),
            prepared_at=NOW,
        )


def test_plan_tampering_is_rejected() -> None:
    plan = build_final_decision_review_route_implementation_plan(
        _dossier(),
        prepared_at=NOW,
    )
    payload = dict(plan.__dict__)
    payload["ready_for_implementation_review"] = False

    with pytest.raises(ValidationError):
        FinalDecisionReviewRouteImplementationPlanV1.model_validate(payload)


def test_naive_plan_timestamp_is_rejected() -> None:
    with pytest.raises(
        FinalDecisionReviewRoutePlanError,
        match="FINAL_DECISION_REVIEW_ROUTE_PLAN_TIMESTAMP_MUST_BE_AWARE",
    ):
        build_final_decision_review_route_implementation_plan(
            _dossier(),
            prepared_at=NOW.replace(tzinfo=None),
        )
