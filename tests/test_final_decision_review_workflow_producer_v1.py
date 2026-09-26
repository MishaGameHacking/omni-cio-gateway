from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

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
from omni_cio.contracts.v1.decision_capacity_intent import (
    CapacityIntentDecisionGateRequestV1,
    CapacityIntentDecisionGateV1,
)
from omni_cio.contracts.v1.decision_capacity_pretrade import (
    CapacityPreTradeDecisionGateV1,
)
from omni_cio.contracts.v1.decision_capacity_sell_pretrade import (
    CapacitySellPreTradeDecisionGateV1,
)
from omni_cio.contracts.v1.final_decision_review_publisher import (
    FinalDecisionReviewPublicationDisposition,
)
from omni_cio.contracts.v1.final_decision_review_workflow_producer import (
    FinalDecisionReviewWorkflowProducerResultV1,
    FinalDecisionReviewWorkflowProducerStage,
    FinalDecisionReviewWorkflowProducerStatus,
)
from omni_cio.contracts.v1.risk import RiskOverallStatus, RiskPolicyEvaluationV1
from omni_cio.release.final_decision_review_workflow_producer_v1 import (
    FinalDecisionReviewWorkflowProducerError,
    FinalDecisionReviewWorkflowProducerV1,
)
from omni_cio.risk.policy_v1 import default_conservative_risk_policy


NOW = datetime.now(timezone.utc)
ACCOUNT = AccountReference(masked_id="****1234")
OTHER_ACCOUNT = AccountReference(masked_id="****9876")
KEY = "uid:workflow-producer-a"
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
    retrieved_at: datetime = NOW,
) -> ContractMetadata:
    return ContractMetadata(
        schema_name="risk_policy_evaluation",
        retrieved_at=retrieved_at,
        account=account,
        provenance=(
            SourceReference(
                provider="omni-cio",
                operation=operation,
                retrieved_at=retrieved_at,
                source_id="workflow-producer-test",
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
    retrieved_at: datetime = NOW,
    status: RiskOverallStatus = RiskOverallStatus.PASS,
    warnings: int = 0,
    ready: bool = True,
) -> RiskPolicyEvaluationV1:
    return RiskPolicyEvaluationV1.model_construct(
        metadata=_metadata(
            operation,
            account=account,
            retrieved_at=retrieved_at,
        ),
        policy=default_conservative_risk_policy(),
        overall_status=status,
        decision_ready=ready,
        checks=(),
        breach_count=0,
        warning_count=warnings,
        unknown_count=0,
        no_cross_currency_aggregation=True,
    )


def _request(side: OrderSide) -> CapacityOrderRequestV1:
    quantity_lots = 2
    lot_size = 10
    price = Decimal("100")
    units = quantity_lots * lot_size
    return CapacityOrderRequestV1(
        request_id=f"request-producer-{side.value}",
        instrument_key=KEY,
        side=side,
        currency="RUB",
        quantity_lots=quantity_lots,
        lot_size=lot_size,
        reference_price=price,
        intended_execution_days=2,
        units=units,
        order_notional=Decimal(units) * price,
    )


def _intent_gate(side: OrderSide) -> CapacityIntentDecisionGateV1:
    request = CapacityIntentDecisionGateRequestV1(
        gate_id=f"producer-gate-{side.value}",
        requested_option_id=OPTION,
        expected_capacity_requests=(_request(side),),
    )
    return CapacityIntentDecisionGateV1.model_construct(
        request=request,
        gate_ready=True,
        no_action_option_id=NO_ACTION,
    )


def _preview_coverage(
    *,
    account: AccountReference = ACCOUNT,
    retrieved_at: datetime = NOW,
):
    preview = SimpleNamespace(
        metadata=_metadata(
            "broker-preview",
            account=account,
            retrieved_at=retrieved_at,
        )
    )
    return (SimpleNamespace(preview=preview),)


def _purchase_gate(
    *,
    account: AccountReference = ACCOUNT,
    ready: bool = True,
    assessed_at: datetime = NOW,
) -> CapacityPreTradeDecisionGateV1:
    gate = _intent_gate(OrderSide.BUY)
    return CapacityPreTradeDecisionGateV1.model_construct(
        assessed_at=assessed_at,
        status=(
            CapacityDecisionGateStatus.READY
            if ready
            else CapacityDecisionGateStatus.ABSTAIN
        ),
        gate_ready=ready,
        abstain=not ready,
        base_intent_gate=gate,
        no_action_option_id=NO_ACTION,
        final_option_id=OPTION if ready else NO_ACTION,
        final_action=(
            DecisionAction.REVIEW_LIMITED_CHANGE
            if ready
            else DecisionAction.WAIT_FOR_DATA
        ),
        required_preview_count=1,
        preview_coverage_count=1,
        preview_ready_count=1,
        exact_match_count=1,
        coverage=_preview_coverage(account=account, retrieved_at=assessed_at),
        broker_preview_coverage_complete=True,
        affordability_confirmed=True,
        commission_integrity_confirmed=True,
    )


def _sell_gate() -> CapacitySellPreTradeDecisionGateV1:
    gate = _intent_gate(OrderSide.SELL)
    return CapacitySellPreTradeDecisionGateV1.model_construct(
        assessed_at=NOW,
        status=CapacityDecisionGateStatus.READY,
        gate_ready=True,
        abstain=False,
        base_intent_gate=gate,
        no_action_option_id=NO_ACTION,
        final_option_id=OPTION,
        final_action=DecisionAction.REVIEW_LIMITED_CHANGE,
        required_preview_count=1,
        preview_coverage_count=1,
        preview_ready_count=1,
        exact_match_count=1,
        coverage=_preview_coverage(),
        broker_preview_coverage_complete=True,
        position_availability_confirmed=True,
        open_orders_confirmed=True,
        tax_basis_confirmed=True,
        commission_integrity_confirmed=True,
    )


def _producer() -> FinalDecisionReviewWorkflowProducerV1:
    return FinalDecisionReviewWorkflowProducerV1(
        bridge=gateway_module.final_decision_review_workflow_bridge,
    )


def _produce(**kwargs) -> FinalDecisionReviewWorkflowProducerResultV1:
    return _producer().produce(
        scenario_id=kwargs.pop("scenario_id", "scenario-workflow-producer-1"),
        current_risk_evaluation=kwargs.pop(
            "current_risk_evaluation",
            _risk("current-risk"),
        ),
        pro_forma_risk_evaluation=kwargs.pop(
            "pro_forma_risk_evaluation",
            _risk(
                "pro-forma-risk",
                status=RiskOverallStatus.WARNING,
                warnings=1,
            ),
        ),
        purchase_gate=kwargs.pop("purchase_gate", _purchase_gate()),
        sell_gate=kwargs.pop("sell_gate", None),
        correlation_id=kwargs.pop("correlation_id", "corr:workflow-producer-0001"),
        request_id=kwargs.pop("request_id", "request:workflow-producer-0001"),
        produced_at=kwargs.pop("produced_at", NOW),
        **kwargs,
    )


def _route_params(result: FinalDecisionReviewWorkflowProducerResultV1):
    assert result.workflow_bridge is not None
    assert result.workflow_bridge.orchestration is not None
    binding = result.workflow_bridge.orchestration.input_binding
    assert binding is not None
    query = binding.query
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


def test_ready_buy_workflow_publishes_and_route_returns_200() -> None:
    result = _produce()

    assert result.status is FinalDecisionReviewWorkflowProducerStatus.PUBLISHED
    assert result.completed_stage is FinalDecisionReviewWorkflowProducerStage.WORKFLOW_BRIDGE
    assert result.published is True
    assert result.primary_blocker is None
    assert result.directional_review is not None
    assert result.directional_review.direction is OrderSide.BUY
    assert result.risk_explanation is not None
    assert result.risk_explanation.review_ready is True
    assert result.workflow_bridge is not None
    assert result.registry_active_sources == 1
    assert result.source_authority_rechecked is True
    assert result.freshness_rechecked is True
    assert result.account_context_rechecked is True
    assert result.exact_intent_rechecked is True
    assert result.http_route_created is False
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


def test_ready_sell_workflow_uses_same_read_only_chain() -> None:
    result = _produce(
        purchase_gate=None,
        sell_gate=_sell_gate(),
        scenario_id="scenario-workflow-producer-sell",
    )

    assert result.published is True
    assert result.directional_review is not None
    assert result.directional_review.direction is OrderSide.SELL
    assert result.directional_review.position_availability_confirmed is True
    assert result.directional_review.open_orders_confirmed is True
    assert result.directional_review.tax_basis_confirmed is True
    assert result.workflow_bridge is not None
    assert result.workflow_bridge.trade_authorized is False
    assert result.trading_methods is False


def test_stale_risk_and_account_mismatch_publish_safe_no_action() -> None:
    stale = _produce(
        current_risk_evaluation=_risk(
            "stale-current-risk",
            retrieved_at=NOW - timedelta(hours=1),
        ),
        scenario_id="scenario-workflow-stale",
    )
    assert stale.published is True
    assert stale.risk_explanation is not None
    assert stale.risk_explanation.abstain is True
    assert stale.workflow_bridge is not None
    assert stale.workflow_bridge.source_binding is not None
    assert stale.workflow_bridge.source_binding.final_option_id == NO_ACTION

    mismatch = _produce(
        purchase_gate=_purchase_gate(account=OTHER_ACCOUNT),
        scenario_id="scenario-workflow-account-mismatch",
    )
    assert mismatch.published is True
    assert mismatch.risk_explanation is not None
    assert mismatch.risk_explanation.account_context_confirmed is False
    assert mismatch.risk_explanation.abstain is True
    assert mismatch.workflow_bridge is not None
    assert mismatch.workflow_bridge.source_binding is not None
    assert mismatch.workflow_bridge.source_binding.final_option_id == NO_ACTION
    assert mismatch.workflow_bridge.trade_authorized is False


def test_zero_or_two_directional_inputs_block_before_explanation() -> None:
    zero = _produce(purchase_gate=None, sell_gate=None)
    assert zero.status is FinalDecisionReviewWorkflowProducerStatus.BLOCKED
    assert zero.completed_stage is FinalDecisionReviewWorkflowProducerStage.DIRECTIONAL_REVIEW
    assert zero.input_direction_count == 0
    assert zero.directional_review is None
    assert zero.risk_explanation is None
    assert zero.workflow_bridge is None

    two = _produce(sell_gate=_sell_gate())
    assert two.status is FinalDecisionReviewWorkflowProducerStatus.BLOCKED
    assert two.completed_stage is FinalDecisionReviewWorkflowProducerStage.DIRECTIONAL_REVIEW
    assert two.input_direction_count == 2
    assert gateway_module.final_decision_review_registry.active_source_count() == 0


def test_invalid_trace_blocks_at_bridge_without_registry_mutation() -> None:
    result = _produce(correlation_id="bad")

    assert result.status is FinalDecisionReviewWorkflowProducerStatus.BLOCKED
    assert result.completed_stage is FinalDecisionReviewWorkflowProducerStage.WORKFLOW_BRIDGE
    assert result.workflow_bridge is not None
    assert "CORRELATION_ID_INVALID" in result.primary_blocker
    assert result.registry_active_sources == 0


def test_concurrent_exact_workflows_publish_then_replace() -> None:
    producer = _producer()

    def run(index: int) -> FinalDecisionReviewWorkflowProducerResultV1:
        return producer.produce(
            scenario_id="scenario-workflow-concurrent",
            current_risk_evaluation=_risk("current-risk"),
            pro_forma_risk_evaluation=_risk("pro-forma-risk"),
            purchase_gate=_purchase_gate(),
            correlation_id=f"corr:workflow-producer-{index:04d}",
            request_id=f"request:workflow-producer-{index:04d}",
            produced_at=NOW,
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = tuple(executor.map(run, range(4)))

    assert all(result.published for result in results)
    assert gateway_module.final_decision_review_registry.active_source_count(
        checked_at=NOW
    ) == 1
    dispositions = [
        result.workflow_bridge.orchestration.publication.disposition
        for result in results
        if result.workflow_bridge is not None
        and result.workflow_bridge.orchestration is not None
        and result.workflow_bridge.orchestration.publication is not None
    ]
    assert dispositions.count(FinalDecisionReviewPublicationDisposition.PUBLISHED) == 1
    assert dispositions.count(FinalDecisionReviewPublicationDisposition.REPLACED) == 3


def test_producer_does_not_change_openapi_or_action_count() -> None:
    before = deepcopy(gateway_module.app.openapi())
    result = _produce()
    assert result.published is True
    after = deepcopy(gateway_module.app.openapi())
    assert after == before

    operation_ids = {
        operation["operationId"]
        for path_item in after["paths"].values()
        if isinstance(path_item, dict)
        for method, operation in path_item.items()
        if method == "get" and isinstance(operation, dict)
    }
    assert len(operation_ids) == 14
    assert all("produce" not in operation_id.lower() for operation_id in operation_ids)


def test_producer_result_and_timestamp_are_fail_closed() -> None:
    result = _produce()
    payload = {
        field_name: getattr(result, field_name)
        for field_name in type(result).model_fields
    }
    payload["trade_authorized"] = True
    with pytest.raises(ValidationError):
        FinalDecisionReviewWorkflowProducerResultV1.model_validate(payload)

    with pytest.raises(
        FinalDecisionReviewWorkflowProducerError,
        match="FINAL_DECISION_REVIEW_WORKFLOW_PRODUCER_TIMESTAMP_MUST_BE_AWARE",
    ):
        _produce(produced_at=NOW.replace(tzinfo=None))
