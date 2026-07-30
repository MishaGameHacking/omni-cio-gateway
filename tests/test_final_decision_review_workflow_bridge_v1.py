from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
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
from omni_cio.contracts.v1.decision_capacity_directional_pretrade import (
    CapacityDirectionalPreTradeReviewV1,
)
from omni_cio.contracts.v1.decision_capacity_intent import (
    CapacityIntentDecisionGateRequestV1,
    CapacityIntentDecisionGateV1,
)
from omni_cio.contracts.v1.decision_risk_pretrade_explanation import (
    RiskPreTradeExplanationEnvelopeV1,
)
from omni_cio.contracts.v1.final_decision_review_publisher import (
    FinalDecisionReviewPublicationDisposition,
)
from omni_cio.contracts.v1.final_decision_review_workflow_bridge import (
    FinalDecisionReviewWorkflowBridgeResultV1,
    FinalDecisionReviewWorkflowBridgeStage,
    FinalDecisionReviewWorkflowBridgeStatus,
)
from omni_cio.contracts.v1.risk import RiskOverallStatus, RiskPolicyEvaluationV1
from omni_cio.release.final_decision_review_route_v1 import (
    FinalDecisionReviewSourceRegistryV1,
)
from omni_cio.release.final_decision_review_workflow_bridge_v1 import (
    FinalDecisionReviewWorkflowBridgeError,
    FinalDecisionReviewWorkflowBridgeV1,
)
from omni_cio.risk.policy_v1 import default_conservative_risk_policy


NOW = datetime.now(timezone.utc)
ACCOUNT = AccountReference(masked_id="****1234")
OTHER_ACCOUNT = AccountReference(masked_id="****9876")
KEY = "uid:workflow-bridge-a"
OPTION = "option.limited_change"
NO_ACTION = "option.no_action"
AUTH_HEADERS = {"Authorization": "Bearer regression-test-gateway-key"}
client = TestClient(gateway_module.app)


@pytest.fixture(autouse=True)
def clear_registry() -> None:
    gateway_module.final_decision_review_registry.clear()
    yield
    gateway_module.final_decision_review_registry.clear()


def _metadata(
    operation: str,
    *,
    account: AccountReference = ACCOUNT,
) -> ContractMetadata:
    return ContractMetadata(
        schema_name="risk_policy_evaluation",
        retrieved_at=NOW,
        account=account,
        provenance=(
            SourceReference(
                provider="omni-cio",
                operation=operation,
                retrieved_at=NOW,
                source_id="workflow-bridge-test",
            ),
        ),
        quality=QualityMetadata(
            quality=DataQuality.VERIFIED,
            completeness=Completeness.COMPLETE,
        ),
    )


def _risk(
    operation: str,
    *,
    account: AccountReference = ACCOUNT,
    status: RiskOverallStatus = RiskOverallStatus.PASS,
    warnings: int = 0,
    ready: bool = True,
) -> RiskPolicyEvaluationV1:
    return RiskPolicyEvaluationV1.model_construct(
        metadata=_metadata(operation, account=account),
        policy=default_conservative_risk_policy(),
        overall_status=status,
        decision_ready=ready,
        checks=(),
        breach_count=0,
        warning_count=warnings,
        unknown_count=0,
        no_cross_currency_aggregation=True,
    )


def _request(*, quantity_lots: int = 2) -> CapacityOrderRequestV1:
    lot_size = 10
    price = Decimal("100")
    units = quantity_lots * lot_size
    return CapacityOrderRequestV1(
        request_id=f"request-workflow-{quantity_lots}",
        instrument_key=KEY,
        side=OrderSide.BUY,
        currency="RUB",
        quantity_lots=quantity_lots,
        lot_size=lot_size,
        reference_price=price,
        intended_execution_days=2,
        units=units,
        order_notional=Decimal(units) * price,
    )


def _base_explanation() -> RiskPreTradeExplanationEnvelopeV1:
    request = _request()
    intent_request = CapacityIntentDecisionGateRequestV1(
        gate_id="workflow-bridge-gate",
        requested_option_id=OPTION,
        expected_capacity_requests=(request,),
    )
    intent_gate = CapacityIntentDecisionGateV1.model_construct(
        request=intent_request,
        gate_ready=True,
    )
    directional_review = CapacityDirectionalPreTradeReviewV1.model_construct(
        direction=OrderSide.BUY,
        base_intent_gate=intent_gate,
    )
    return RiskPreTradeExplanationEnvelopeV1.model_construct(
        assessed_at=NOW,
        status=CapacityDecisionGateStatus.READY,
        review_ready=True,
        abstain=False,
        direction=OrderSide.BUY,
        risk_evaluation=_risk("current-risk"),
        directional_review=directional_review,
        no_action_option_id=NO_ACTION,
        final_option_id=OPTION,
        final_action=DecisionAction.REVIEW_LIMITED_CHANGE,
        account_context_confirmed=True,
    )


def _publish(**kwargs):
    return gateway_module.final_decision_review_workflow_bridge.publish(
        scenario_id=kwargs.pop("scenario_id", "scenario-workflow-bridge-1"),
        base_explanation=kwargs.pop("base_explanation", _base_explanation()),
        capacity_requests=kwargs.pop("capacity_requests", (_request(),)),
        pro_forma_risk_evaluation=kwargs.pop(
            "pro_forma_risk_evaluation",
            _risk(
                "pro-forma-risk",
                status=RiskOverallStatus.WARNING,
                warnings=1,
            ),
        ),
        correlation_id=kwargs.pop("correlation_id", "corr:workflow-bridge-0001"),
        request_id=kwargs.pop("request_id", "request:workflow-bridge-0001"),
        bridged_at=kwargs.pop("bridged_at", NOW),
        **kwargs,
    )


def _route_params(result: FinalDecisionReviewWorkflowBridgeResultV1):
    assert result.orchestration is not None
    assert result.orchestration.input_binding is not None
    query = result.orchestration.input_binding.query
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


def test_production_bridge_is_registered_without_new_action() -> None:
    assert isinstance(
        gateway_module.final_decision_review_workflow_bridge,
        FinalDecisionReviewWorkflowBridgeV1,
    )
    assert "final_decision_review_workflow_bridge" in gateway_module.base.CAPABILITIES

    schema = gateway_module.app.openapi()
    methods = {
        method
        for path_item in schema["paths"].values()
        if isinstance(path_item, dict)
        for method in path_item
        if method in {"get", "post", "put", "patch", "delete"}
    }
    operation_ids = {
        operation["operationId"]
        for path_item in schema["paths"].values()
        if isinstance(path_item, dict)
        for method, operation in path_item.items()
        if method == "get" and isinstance(operation, dict)
    }
    assert methods == {"get"}
    assert len(operation_ids) == 14
    assert all("publish" not in operation_id.lower() for operation_id in operation_ids)


def test_bridge_publishes_and_exact_route_returns_reviewed_response() -> None:
    result = _publish()

    assert result.status is FinalDecisionReviewWorkflowBridgeStatus.PUBLISHED
    assert result.completed_stage is FinalDecisionReviewWorkflowBridgeStage.ORCHESTRATION
    assert result.published is True
    assert result.primary_blocker is None
    assert result.source_binding is not None
    assert result.source_binding.review_ready is True
    assert result.orchestration is not None
    assert result.registry_active_sources == 1
    assert result.internal_only is True
    assert result.http_route_created is False
    assert result.production_schema_mutated is False
    assert result.external_broker_called is False
    assert result.trade_authorized is False
    assert result.order_created is False
    assert result.execution_ready is False
    assert result.trading_methods is False

    response = client.get(
        "/decision/final-review",
        params=_route_params(result),
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    assert response.json() == result.orchestration.response_shadow.response.model_dump(
        mode="json"
    )


def test_substituted_capacity_request_publishes_safe_no_action() -> None:
    result = _publish(capacity_requests=(_request(quantity_lots=3),))

    assert result.status is FinalDecisionReviewWorkflowBridgeStatus.PUBLISHED
    assert result.source_binding is not None
    assert result.source_binding.abstain is True
    assert result.source_binding.final_option_id == NO_ACTION
    assert result.source_binding.risk_change_approval_confirmed is False
    assert result.orchestration is not None
    response = result.orchestration.response_shadow.response
    assert response.abstain is True
    assert response.final_option_id == NO_ACTION
    assert response.trade_authorized is False
    assert response.order_created is False
    assert response.execution_ready is False
    assert response.trading_methods is False


def test_invalid_scenario_and_https_host_fail_closed() -> None:
    invalid_scenario = _publish(capacity_requests=())
    assert invalid_scenario.status is FinalDecisionReviewWorkflowBridgeStatus.BLOCKED
    assert invalid_scenario.completed_stage is FinalDecisionReviewWorkflowBridgeStage.SCENARIO
    assert invalid_scenario.scenario is None
    assert invalid_scenario.primary_blocker == (
        "FINAL_DECISION_REVIEW_WORKFLOW_SCENARIO_INVALID"
    )
    assert gateway_module.final_decision_review_registry.active_source_count() == 0

    schema = deepcopy(gateway_module.app.openapi())
    schema["servers"] = [{"url": "http://localhost:8000"}]
    isolated_registry = FinalDecisionReviewSourceRegistryV1()
    bridge = FinalDecisionReviewWorkflowBridgeV1(
        registry=isolated_registry,
        openapi_provider=lambda: schema,
        expected_app_version=gateway_module.APP_VERSION,
    )
    invalid_host = bridge.publish(
        scenario_id="scenario-invalid-host",
        base_explanation=_base_explanation(),
        capacity_requests=(_request(),),
        pro_forma_risk_evaluation=_risk("pro-forma-risk"),
        correlation_id="corr:workflow-bridge-0002",
        bridged_at=NOW,
    )
    assert invalid_host.status is FinalDecisionReviewWorkflowBridgeStatus.BLOCKED
    assert invalid_host.completed_stage is FinalDecisionReviewWorkflowBridgeStage.ORCHESTRATION
    assert invalid_host.primary_blocker == (
        "FINAL_DECISION_REVIEW_WORKFLOW_BRIDGE_HTTPS_HOST_REQUIRED"
    )
    assert isolated_registry.active_source_count(checked_at=NOW) == 0


def test_invalid_trace_is_blocked_by_downstream_publication() -> None:
    result = _publish(correlation_id="bad")

    assert result.status is FinalDecisionReviewWorkflowBridgeStatus.BLOCKED
    assert result.completed_stage is FinalDecisionReviewWorkflowBridgeStage.ORCHESTRATION
    assert result.orchestration is not None
    assert "CORRELATION_ID_INVALID" in result.primary_blocker
    assert result.registry_active_sources == 0


def test_concurrent_bridge_calls_share_registry_and_replace_exact_source() -> None:
    def run(index: int):
        return _publish(
            correlation_id=f"corr:workflow-bridge-{index:04d}",
            request_id=f"request:workflow-bridge-{index:04d}",
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = tuple(executor.map(run, range(4)))

    assert all(result.published for result in results)
    assert gateway_module.final_decision_review_registry.active_source_count(
        checked_at=NOW
    ) == 1
    dispositions = [
        result.orchestration.publication.disposition
        for result in results
        if result.orchestration is not None
        and result.orchestration.publication is not None
    ]
    assert dispositions.count(FinalDecisionReviewPublicationDisposition.PUBLISHED) == 1
    assert dispositions.count(FinalDecisionReviewPublicationDisposition.REPLACED) == 3


def test_bridge_preserves_ttl_restart_and_openapi_state() -> None:
    before = deepcopy(gateway_module.app.openapi())
    result = _publish()
    assert result.published is True
    after = deepcopy(gateway_module.app.openapi())
    assert after == before

    short_registry = FinalDecisionReviewSourceRegistryV1(ttl_seconds=1)
    bridge = FinalDecisionReviewWorkflowBridgeV1(
        registry=short_registry,
        openapi_provider=lambda: before,
        expected_app_version=gateway_module.APP_VERSION,
    )
    short_result = bridge.publish(
        scenario_id="scenario-short-ttl",
        base_explanation=_base_explanation(),
        capacity_requests=(_request(),),
        pro_forma_risk_evaluation=_risk("pro-forma-risk"),
        correlation_id="corr:workflow-bridge-ttl1",
        bridged_at=NOW,
    )
    assert short_result.published is True
    assert short_registry.active_source_count(checked_at=NOW) == 1
    assert short_registry.active_source_count(
        checked_at=NOW + timedelta(seconds=2)
    ) == 0

    restarted_registry = FinalDecisionReviewSourceRegistryV1()
    assert restarted_registry.active_source_count(checked_at=NOW) == 0


def test_bridge_result_and_timestamp_are_fail_closed() -> None:
    result = _publish()
    payload = result.model_dump(mode="python")
    payload["trade_authorized"] = True
    with pytest.raises(ValidationError):
        FinalDecisionReviewWorkflowBridgeResultV1.model_validate(payload)

    with pytest.raises(
        FinalDecisionReviewWorkflowBridgeError,
        match="FINAL_DECISION_REVIEW_WORKFLOW_BRIDGE_TIMESTAMP_MUST_BE_AWARE",
    ):
        _publish(bridged_at=NOW.replace(tzinfo=None))
