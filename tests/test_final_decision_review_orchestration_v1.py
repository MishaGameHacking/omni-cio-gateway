from __future__ import annotations

import os
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

os.environ.setdefault("TINVEST_TOKEN", "regression-test-tinvest-token")
os.environ.setdefault("GATEWAY_API_KEY", "regression-test-gateway-key")
os.environ.setdefault(
    "RENDER_EXTERNAL_URL",
    "https://omni-cio-gateway.onrender.com",
)

import app as gateway_module
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
from omni_cio.contracts.v1.final_decision_review_input import (
    FinalDecisionReviewInputPolicyV1,
)
from omni_cio.contracts.v1.final_decision_review_orchestration import (
    FinalDecisionReviewOrchestrationResultV1,
    FinalDecisionReviewOrchestrationStage,
    FinalDecisionReviewOrchestrationStatus,
)
from omni_cio.contracts.v1.final_decision_review_publisher import (
    FinalDecisionReviewPublicationDisposition,
)
from omni_cio.contracts.v1.final_decision_review_release import (
    FinalDecisionReviewReleasePolicyV1,
)
from omni_cio.contracts.v1.final_decision_review_route_readiness import (
    FinalDecisionReviewRouteControlsV1,
)
from omni_cio.contracts.v1.risk import RiskOverallStatus, RiskPolicyEvaluationV1
from omni_cio.release.final_decision_review_orchestration_v1 import (
    FinalDecisionReviewOrchestrationError,
    orchestrate_final_decision_review_publication,
)
from omni_cio.risk.policy_v1 import default_conservative_risk_policy


NOW = datetime(2026, 7, 30, 4, 0, tzinfo=timezone.utc)
ACCOUNT = AccountReference(masked_id="****1234")
KEY = "uid:final-review-a"
OPTION = "option.limited_change"
NO_ACTION = "option.no_action"
APPROVED_HOSTS = frozenset({"omni-cio-gateway.onrender.com"})
AUTH_HEADERS = {"Authorization": "Bearer regression-test-gateway-key"}
client = TestClient(gateway_module.app)


@pytest.fixture(autouse=True)
def clear_production_registry() -> None:
    gateway_module.final_decision_review_registry.clear()
    yield
    gateway_module.final_decision_review_registry.clear()


def _source(operation: str) -> SourceReference:
    return SourceReference(
        provider="omni-cio",
        operation=operation,
        retrieved_at=NOW,
        source_id="internal-source-id-not-exposed",
    )


def _metadata(operation: str) -> ContractMetadata:
    return ContractMetadata(
        schema_name="risk_policy_evaluation",
        retrieved_at=NOW,
        account=ACCOUNT,
        provenance=(_source(operation),),
        quality=QualityMetadata(
            quality=DataQuality.VERIFIED,
            completeness=Completeness.COMPLETE,
        ),
    )


def _risk(
    operation: str,
    *,
    status: RiskOverallStatus,
    warnings: int = 0,
) -> RiskPolicyEvaluationV1:
    return RiskPolicyEvaluationV1.model_construct(
        metadata=_metadata(operation),
        policy=default_conservative_risk_policy(),
        overall_status=status,
        decision_ready=True,
        checks=(),
        breach_count=0,
        warning_count=warnings,
        unknown_count=0,
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


def _binding(*, ready: bool = True) -> ProFormaRiskIntentBindingV1:
    request = _request()
    fingerprint = calculate_pro_forma_intent_fingerprint(
        account_masked_id=ACCOUNT.masked_id,
        requested_option_id=OPTION,
        direction=OrderSide.BUY,
        capacity_requests=(request,),
    )
    current_risk = _risk("current-risk", status=RiskOverallStatus.PASS)
    pro_forma_risk = _risk(
        "pro-forma-risk",
        status=RiskOverallStatus.WARNING,
        warnings=1,
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


def _schema() -> dict[str, object]:
    gateway_module.app.openapi_schema = None
    return deepcopy(gateway_module.app.openapi())


def _orchestrate(**kwargs):
    return orchestrate_final_decision_review_publication(
        kwargs.pop("source_binding", _binding()),
        kwargs.pop("current_openapi_schema", _schema()),
        kwargs.pop("registry", gateway_module.final_decision_review_registry),
        expected_app_version=kwargs.pop(
            "expected_app_version",
            gateway_module.APP_VERSION,
        ),
        approved_hosts=kwargs.pop("approved_hosts", APPROVED_HOSTS),
        correlation_id=kwargs.pop("correlation_id", "corr:orchestration-0001"),
        request_id=kwargs.pop("request_id", "request:orchestration-0001"),
        orchestrated_at=kwargs.pop("orchestrated_at", NOW),
        **kwargs,
    )


def _route_params(result: FinalDecisionReviewOrchestrationResultV1):
    assert result.input_binding is not None
    query = result.input_binding.query
    values = [
        ("account", query.account.masked_id),
        ("requested_option_id", query.requested_option_id),
        ("final_option_id", query.final_option_id),
        ("intent_fingerprint", query.intent_fingerprint),
        ("instrument_count", str(query.instrument_count)),
        ("response_sha256", query.response_sha256),
        ("action_candidate_sha256", query.action_candidate_sha256),
    ]
    values.extend(("instrument_keys", item) for item in query.instrument_keys)
    return values


def test_complete_chain_publishes_and_production_route_returns_exact_response() -> None:
    result = _orchestrate()

    assert result.status is FinalDecisionReviewOrchestrationStatus.PUBLISHED
    assert result.completed_stage is FinalDecisionReviewOrchestrationStage.PUBLICATION
    assert result.published is True
    assert result.primary_blocker is None
    assert result.release_eligibility is not None
    assert result.action_shadow is not None
    assert result.input_binding is not None
    assert result.readiness_dossier is not None
    assert result.route_plan is not None
    assert result.publication is not None
    assert result.publication.disposition is FinalDecisionReviewPublicationDisposition.PUBLISHED
    assert result.internal_only is True
    assert result.production_schema_mutated is False
    assert result.http_route_created is False
    assert result.external_broker_called is False
    assert result.trade_authorized is False
    assert result.trading_methods is False

    response = client.get(
        "/decision/final-review",
        params=_route_params(result),
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    assert response.json() == result.response_shadow.response.model_dump(mode="json")


def test_safe_no_action_response_can_be_published_without_execution() -> None:
    result = _orchestrate(source_binding=_binding(ready=False))

    assert result.status is FinalDecisionReviewOrchestrationStatus.PUBLISHED
    assert result.response_shadow.response.abstain is True
    assert result.response_shadow.response.final_option_id == NO_ACTION
    assert result.response_shadow.response.trade_authorized is False
    assert result.response_shadow.response.order_created is False
    assert result.response_shadow.response.execution_ready is False
    assert result.response_shadow.response.trading_methods is False


def test_release_policy_blocks_before_action_or_registry_mutation() -> None:
    result = _orchestrate(
        release_policy=FinalDecisionReviewReleasePolicyV1(max_sources=1),
    )

    assert result.status is FinalDecisionReviewOrchestrationStatus.BLOCKED
    assert result.completed_stage is FinalDecisionReviewOrchestrationStage.RELEASE_ELIGIBILITY
    assert result.primary_blocker == "source_count"
    assert result.release_eligibility is not None
    assert result.action_shadow is None
    assert result.input_binding is None
    assert result.publication is None
    assert gateway_module.final_decision_review_registry.active_source_count() == 0


def test_missing_or_substituted_production_route_blocks_action_shadow() -> None:
    missing = _schema()
    paths = missing["paths"]
    assert isinstance(paths, dict)
    paths.pop("/decision/final-review")

    result = _orchestrate(current_openapi_schema=missing)

    assert result.status is FinalDecisionReviewOrchestrationStatus.BLOCKED
    assert result.completed_stage is FinalDecisionReviewOrchestrationStage.ACTION_SHADOW
    assert "PRODUCTION_ROUTE_REQUIRED" in result.primary_blocker
    assert result.action_shadow is None
    assert gateway_module.final_decision_review_registry.active_source_count() == 0

    changed = _schema()
    changed_paths = changed["paths"]
    assert isinstance(changed_paths, dict)
    operation = changed_paths["/decision/final-review"]["get"]
    operation["operationId"] = "getSubstitutedFinalReview"
    changed_result = _orchestrate(current_openapi_schema=changed)
    assert changed_result.completed_stage is FinalDecisionReviewOrchestrationStage.ACTION_SHADOW
    assert "OPERATION_ID_MISMATCH" in changed_result.primary_blocker


def test_input_policy_drift_blocks_before_readiness_and_publication() -> None:
    policy = FinalDecisionReviewInputPolicyV1(
        allowed_query_parameters=(
            "account",
            "requested_option_id",
            "final_option_id",
            "intent_fingerprint",
            "instrument_count",
            "instrument_keys",
            "response_sha256",
        )
    )

    result = _orchestrate(input_policy=policy)

    assert result.status is FinalDecisionReviewOrchestrationStatus.BLOCKED
    assert result.completed_stage is FinalDecisionReviewOrchestrationStage.INPUT_BINDING
    assert result.input_binding is not None
    assert result.readiness_dossier is None
    assert result.publication is None
    assert gateway_module.final_decision_review_registry.active_source_count() == 0


def test_readiness_control_drift_blocks_before_route_plan() -> None:
    controls = FinalDecisionReviewRouteControlsV1().model_copy(
        update={"correlation_id_required": False}
    )

    result = _orchestrate(route_controls=controls)

    assert result.status is FinalDecisionReviewOrchestrationStatus.BLOCKED
    assert result.completed_stage is FinalDecisionReviewOrchestrationStage.ROUTE_READINESS
    assert result.primary_blocker == "observability"
    assert result.readiness_dossier is not None
    assert result.route_plan is None
    assert result.publication is None


def test_invalid_publisher_trace_blocks_only_publication_and_leaves_registry_empty() -> None:
    result = _orchestrate(correlation_id="bad")

    assert result.status is FinalDecisionReviewOrchestrationStatus.BLOCKED
    assert result.completed_stage is FinalDecisionReviewOrchestrationStage.PUBLICATION
    assert "CORRELATION_ID_INVALID" in result.primary_blocker
    assert result.route_plan is not None
    assert result.publication is None
    assert gateway_module.final_decision_review_registry.active_source_count() == 0


def test_repeated_complete_chain_replaces_exact_active_source() -> None:
    first = _orchestrate(correlation_id="corr:orchestration-0002")
    second = _orchestrate(correlation_id="corr:orchestration-0003")

    assert first.publication is not None
    assert second.publication is not None
    assert first.publication.disposition is FinalDecisionReviewPublicationDisposition.PUBLISHED
    assert second.publication.disposition is FinalDecisionReviewPublicationDisposition.REPLACED
    assert gateway_module.final_decision_review_registry.active_source_count() == 1


def test_orchestration_does_not_mutate_production_openapi() -> None:
    before = _schema()

    result = _orchestrate(current_openapi_schema=before)

    assert result.status is FinalDecisionReviewOrchestrationStatus.PUBLISHED
    after = _schema()
    assert after == before
    operation_ids = {
        operation["operationId"]
        for path_item in after["paths"].values()
        if isinstance(path_item, dict)
        for method, operation in path_item.items()
        if method == "get" and isinstance(operation, dict)
    }
    assert all("publish" not in operation_id.lower() for operation_id in operation_ids)


def test_result_tampering_and_naive_timestamp_are_rejected() -> None:
    result = _orchestrate()
    payload = result.model_dump(mode="python")
    payload["production_schema_mutated"] = True
    with pytest.raises(ValidationError):
        FinalDecisionReviewOrchestrationResultV1.model_validate(payload)

    with pytest.raises(
        FinalDecisionReviewOrchestrationError,
        match="FINAL_DECISION_REVIEW_ORCHESTRATION_TIMESTAMP_MUST_BE_AWARE",
    ):
        _orchestrate(orchestrated_at=NOW.replace(tzinfo=None))
