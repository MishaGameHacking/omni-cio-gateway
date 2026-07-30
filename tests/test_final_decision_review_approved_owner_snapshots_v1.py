from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, cast

import pytest

import app as gateway
from omni_cio.contracts.v1.capacity import (
    CapacityAssessmentV1,
    CapacityOrderRequestV1,
    OrderSide,
)
from omni_cio.contracts.v1.common import AccountReference, SourceReference
from omni_cio.contracts.v1.decision import DecisionSetV1
from omni_cio.contracts.v1.decision_capacity_intent import (
    CapacityIntentDecisionGateRequestV1,
)
from omni_cio.contracts.v1.final_decision_review_approved_invocation import (
    ApprovedCalculatorInvocationRequestV1,
    ApprovedCalculatorOperation,
)
from omni_cio.contracts.v1.final_decision_review_trusted_scenario import (
    TrustedScenarioPublicationDisposition,
    TrustedScenarioPublicationResultV1,
)
from omni_cio.contracts.v1.pretrade import PreTradePreviewV1
from omni_cio.contracts.v1.risk import RiskPolicyEvaluationV1
from omni_cio.contracts.v1.sell_pretrade import SellPreTradePreviewV1
from omni_cio.release.final_decision_review_approved_invocation_v1 import (
    FinalDecisionReviewApprovedInvocationError,
    FinalDecisionReviewApprovedInvocationV1,
)
from omni_cio.release.final_decision_review_approved_owner_acquisition_v1 import (
    FinalDecisionReviewApprovedServerContextV1,
)
from omni_cio.release.final_decision_review_approved_owner_snapshots_v1 import (
    FinalDecisionReviewApprovedOwnerSnapshotError,
    FinalDecisionReviewApprovedOwnerSnapshotSelectionV1,
    FinalDecisionReviewApprovedOwnerSnapshotStoreV1,
)
from omni_cio.release.final_decision_review_calculator_intent_workflow_v1 import (
    FinalDecisionReviewCalculatorIntentWorkflowError,
    FinalDecisionReviewCalculatorIntentWorkflowV1,
)


NOW = datetime.now(timezone.utc).replace(microsecond=0)
ACCOUNT = AccountReference(masked_id="account:****1234")
INSTRUMENT = "instrument:owner-snapshot:one"


def _operation(side: OrderSide) -> ApprovedCalculatorOperation:
    return (
        ApprovedCalculatorOperation.PURCHASE_REVIEW
        if side is OrderSide.BUY
        else ApprovedCalculatorOperation.SELL_REVIEW
    )


def _request(
    side: OrderSide,
    *,
    invocation_id: str = "invoke:owner-snapshot:source",
) -> ApprovedCalculatorInvocationRequestV1:
    return ApprovedCalculatorInvocationRequestV1(
        invocation_id=invocation_id,
        scenario_id=f"scenario:owner-snapshot:{side.value}",
        correlation_id=f"corr:owner-snapshot:{side.value}",
        operation=_operation(side),
        invoked_at=NOW,
    )


def _capacity_request(side: OrderSide) -> CapacityOrderRequestV1:
    return CapacityOrderRequestV1(
        request_id=f"capacity:owner-snapshot:{side.value}",
        instrument_key=INSTRUMENT,
        side=side,
        currency="RUB",
        quantity_lots=2,
        lot_size=10,
        reference_price="100",
        intended_execution_days=1,
        units=20,
        order_notional="2000",
    )


def _inputs(side: OrderSide) -> dict[str, object]:
    capacity_request = _capacity_request(side)
    decision = DecisionSetV1.model_construct(
        metadata=SimpleNamespace(account=ACCOUNT),
    )
    intent = CapacityIntentDecisionGateRequestV1(
        gate_id=f"gate:owner-snapshot:{side.value}",
        requested_option_id="option:owner-snapshot:one",
        expected_capacity_requests=(capacity_request,),
    )
    assessment = CapacityAssessmentV1.model_construct(request=capacity_request)
    risk = RiskPolicyEvaluationV1.model_construct(
        metadata=SimpleNamespace(
            account=ACCOUNT,
            retrieved_at=NOW,
        ),
    )
    if side is OrderSide.BUY:
        previews: tuple[PreTradePreviewV1, ...] | tuple[SellPreTradePreviewV1, ...]
        previews = (
            PreTradePreviewV1.model_construct(
                stable_key=INSTRUMENT,
                metadata=SimpleNamespace(account=ACCOUNT),
            ),
        )
    else:
        previews = (
            SellPreTradePreviewV1.model_construct(
                stable_key=INSTRUMENT,
                metadata=SimpleNamespace(account=ACCOUNT),
            ),
        )
    return {
        "decision": decision,
        "intent": intent,
        "assessments": (assessment,),
        "previews": previews,
        "risk": risk,
    }


def _publication(
    side: OrderSide,
    request: ApprovedCalculatorInvocationRequestV1,
) -> TrustedScenarioPublicationResultV1:
    return TrustedScenarioPublicationResultV1(
        disposition=TrustedScenarioPublicationDisposition.PUBLISHED,
        scenario_id=request.scenario_id,
        direction=side,
        account=ACCOUNT,
        gate_assessed_at=NOW,
        pro_forma_retrieved_at=NOW,
        published_at=request.invoked_at,
        expires_at=request.invoked_at + timedelta(minutes=15),
        source=SourceReference(
            provider="omni-cio",
            operation="owner-snapshot-test",
            retrieved_at=NOW,
        ),
        instrument_count=1,
        gate_ready=True,
        pro_forma_decision_ready=True,
        source_replaced=False,
        source_evicted=False,
        active_bundle_count=1,
    )


def _context(
    side: OrderSide,
    *,
    generated_at: datetime = NOW + timedelta(seconds=2),
    correlation_id: str | None = None,
) -> FinalDecisionReviewApprovedServerContextV1:
    source = _request(side)
    return FinalDecisionReviewApprovedServerContextV1(
        invocation_id=f"invoke:owner-snapshot:route:{side.value}",
        scenario_id=source.scenario_id,
        correlation_id=correlation_id or source.correlation_id,
        operation=source.operation,
        account=ACCOUNT,
        generated_at=generated_at,
    )


def _capture(
    store: FinalDecisionReviewApprovedOwnerSnapshotStoreV1,
    side: OrderSide,
) -> None:
    request = _request(side)
    values = _inputs(side)
    if side is OrderSide.BUY:
        store.capture_purchase(
            request=request,
            decision=cast(DecisionSetV1, values["decision"]),
            intent_request=cast(
                CapacityIntentDecisionGateRequestV1,
                values["intent"],
            ),
            capacity_assessments=cast(
                tuple[CapacityAssessmentV1, ...],
                values["assessments"],
            ),
            purchase_previews=cast(
                tuple[PreTradePreviewV1, ...],
                values["previews"],
            ),
            pro_forma_risk=cast(RiskPolicyEvaluationV1, values["risk"]),
            publication=_publication(side, request),
            captured_at=NOW + timedelta(seconds=1),
        )
    else:
        store.capture_sell(
            request=request,
            decision=cast(DecisionSetV1, values["decision"]),
            intent_request=cast(
                CapacityIntentDecisionGateRequestV1,
                values["intent"],
            ),
            capacity_assessments=cast(
                tuple[CapacityAssessmentV1, ...],
                values["assessments"],
            ),
            sell_previews=cast(
                tuple[SellPreTradePreviewV1, ...],
                values["previews"],
            ),
            pro_forma_risk=cast(RiskPolicyEvaluationV1, values["risk"]),
            publication=_publication(side, request),
            captured_at=NOW + timedelta(seconds=1),
        )


@pytest.mark.parametrize("side", (OrderSide.BUY, OrderSide.SELL))
def test_snapshot_rebinds_exact_outputs_to_authenticated_context(
    side: OrderSide,
) -> None:
    store = FinalDecisionReviewApprovedOwnerSnapshotStoreV1()
    _capture(store, side)
    context = _context(side)
    selection = store.select(context, checked_at=context.generated_at)
    assert isinstance(
        selection,
        FinalDecisionReviewApprovedOwnerSnapshotSelectionV1,
    )
    route_request = context.invocation_request()
    owners = (
        selection.purchase_owners
        if side is OrderSide.BUY
        else selection.sell_owners
    )
    assert owners is not None
    values = _inputs(side)
    assert owners.common.decision(route_request) == values["decision"]
    assert owners.common.intent(route_request) == values["intent"]
    assert owners.common.capacity(route_request) == values["assessments"]
    scenario = owners.common.pro_forma_scenario(route_request)
    assert scenario.scenario_id == context.scenario_id
    assert scenario.account == context.account
    assert scenario.direction is side
    assert scenario.generated_at == NOW
    assert tuple(owners.previews(route_request)) == values["previews"]
    with pytest.raises(
        FinalDecisionReviewApprovedOwnerSnapshotError,
        match="FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_BOUND_REQUEST_MISMATCH",
    ):
        owners.common.decision(_request(side))


def test_snapshot_selection_requires_exact_trusted_identity() -> None:
    store = FinalDecisionReviewApprovedOwnerSnapshotStoreV1()
    _capture(store, OrderSide.BUY)
    mismatched = _context(
        OrderSide.BUY,
        correlation_id="corr:owner-snapshot:mismatch",
    )
    assert store.select(mismatched, checked_at=mismatched.generated_at) is None


def test_snapshot_expires_before_pro_forma_scenario_becomes_stale() -> None:
    store = FinalDecisionReviewApprovedOwnerSnapshotStoreV1()
    _capture(store, OrderSide.BUY)
    stale_context = _context(
        OrderSide.BUY,
        generated_at=NOW + timedelta(seconds=301),
    )
    assert (
        store.select(stale_context, checked_at=stale_context.generated_at)
        is None
    )
    assert store.active_bundle_count(checked_at=stale_context.generated_at) == 0


class _RecordingSnapshotStore:
    def __init__(self) -> None:
        self.purchase_calls = 0
        self.sell_calls = 0

    def capture_purchase(self, **_: Any) -> None:
        self.purchase_calls += 1

    def capture_sell(self, **_: Any) -> None:
        self.sell_calls += 1


class _FakeWorkflow(FinalDecisionReviewCalculatorIntentWorkflowV1):
    def __init__(self) -> None:
        self.fail = False

    def publish_purchase(  # type: ignore[override]
        self,
        **kwargs: Any,
    ) -> TrustedScenarioPublicationResultV1:
        if self.fail:
            raise FinalDecisionReviewCalculatorIntentWorkflowError("TEST_FAILURE")
        request = cast(
            ApprovedCalculatorInvocationRequestV1,
            kwargs["request"] if "request" in kwargs else _request(OrderSide.BUY),
        )
        request = request.model_copy(
            update={
                "scenario_id": cast(str, kwargs["scenario_id"]),
                "invoked_at": cast(datetime, kwargs["published_at"]),
            }
        )
        return _publication(OrderSide.BUY, request)

    def publish_sell(  # type: ignore[override]
        self,
        **kwargs: Any,
    ) -> TrustedScenarioPublicationResultV1:
        if self.fail:
            raise FinalDecisionReviewCalculatorIntentWorkflowError("TEST_FAILURE")
        request = _request(OrderSide.SELL).model_copy(
            update={
                "scenario_id": cast(str, kwargs["scenario_id"]),
                "invoked_at": cast(datetime, kwargs["published_at"]),
            }
        )
        return _publication(OrderSide.SELL, request)


def _dummy_inputs(side: OrderSide) -> dict[str, object]:
    values = _inputs(side)
    return {
        "decision": values["decision"],
        "intent_request": values["intent"],
        "capacity_assessments": values["assessments"],
        "previews": values["previews"],
        "pro_forma_risk": values["risk"],
    }


def test_approved_invocation_captures_only_after_success() -> None:
    workflow = _FakeWorkflow()
    store = _RecordingSnapshotStore()
    boundary = FinalDecisionReviewApprovedInvocationV1(
        workflow=workflow,
        snapshot_store=store,
    )
    request = _request(OrderSide.BUY)
    boundary.invoke_purchase(
        request=request,
        completed_at=NOW + timedelta(seconds=1),
        **_dummy_inputs(OrderSide.BUY),  # type: ignore[arg-type]
    )
    assert store.purchase_calls == 1
    assert store.sell_calls == 0

    workflow.fail = True
    with pytest.raises(
        FinalDecisionReviewApprovedInvocationError,
        match="TEST_FAILURE",
    ):
        boundary.invoke_sell(
            request=_request(
                OrderSide.SELL,
                invocation_id="invoke:owner-snapshot:failed",
            ),
            completed_at=NOW + timedelta(seconds=1),
            **_dummy_inputs(OrderSide.SELL),  # type: ignore[arg-type]
        )
    assert store.sell_calls == 0


def test_production_runtime_registers_empty_snapshot_store_lazily() -> None:
    runtime = gateway.final_decision_review_production_runtime
    assert isinstance(
        runtime.approved_owner_snapshot_store,
        FinalDecisionReviewApprovedOwnerSnapshotStoreV1,
    )
    assert (
        runtime.approved_invocation.snapshot_store
        is runtime.approved_owner_snapshot_store
    )
    assert runtime.startup_approved_owner_snapshot_count == 0
    assert runtime.broker_write_called is False
    assert runtime.trade_authorized is False
    assert runtime.order_created is False
    assert runtime.trading_methods is False
