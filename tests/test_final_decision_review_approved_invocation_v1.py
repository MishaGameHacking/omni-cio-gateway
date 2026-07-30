from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast

import pytest

from omni_cio.contracts.v1.capacity import (
    CapacityAssessmentV1,
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
from omni_cio.release.final_decision_review_approved_invocation_v1 import (
    FinalDecisionReviewApprovedInvocationError,
    FinalDecisionReviewApprovedInvocationV1,
)
from omni_cio.release.final_decision_review_calculator_intent_workflow_v1 import (
    FinalDecisionReviewCalculatorIntentWorkflowError,
    FinalDecisionReviewCalculatorIntentWorkflowV1,
)
from omni_cio.release.final_decision_review_production_registration_v1 import (
    register_final_decision_review_production_sources,
)


NOW = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
ACCOUNT = AccountReference(masked_id="****1234")


def _publication(
    *,
    side: OrderSide,
    scenario_id: str,
    published_at: datetime,
) -> TrustedScenarioPublicationResultV1:
    return TrustedScenarioPublicationResultV1(
        disposition=TrustedScenarioPublicationDisposition.PUBLISHED,
        scenario_id=scenario_id,
        direction=side,
        account=ACCOUNT,
        gate_assessed_at=published_at,
        pro_forma_retrieved_at=published_at,
        published_at=published_at,
        expires_at=published_at + timedelta(minutes=15),
        source=SourceReference(
            provider="omni-cio",
            operation="approved-invocation-test",
            retrieved_at=published_at,
        ),
        instrument_count=1,
        gate_ready=True,
        pro_forma_decision_ready=True,
        source_replaced=False,
        source_evicted=False,
        active_bundle_count=1,
    )


class _FakeWorkflow(FinalDecisionReviewCalculatorIntentWorkflowV1):
    def __init__(self) -> None:
        self.purchase_calls = 0
        self.sell_calls = 0
        self.fail = False

    def publish_purchase(self, **kwargs: Any) -> TrustedScenarioPublicationResultV1:  # type: ignore[override]
        self.purchase_calls += 1
        if self.fail:
            raise FinalDecisionReviewCalculatorIntentWorkflowError("TEST_FAILURE")
        return _publication(
            side=OrderSide.BUY,
            scenario_id=cast(str, kwargs["scenario_id"]),
            published_at=cast(datetime, kwargs["published_at"]),
        )

    def publish_sell(self, **kwargs: Any) -> TrustedScenarioPublicationResultV1:  # type: ignore[override]
        self.sell_calls += 1
        if self.fail:
            raise FinalDecisionReviewCalculatorIntentWorkflowError("TEST_FAILURE")
        return _publication(
            side=OrderSide.SELL,
            scenario_id=cast(str, kwargs["scenario_id"]),
            published_at=cast(datetime, kwargs["published_at"]),
        )


def _request(
    operation: ApprovedCalculatorOperation,
    *,
    invocation_id: str = "invoke:approved:one",
    invoked_at: datetime = NOW,
) -> ApprovedCalculatorInvocationRequestV1:
    return ApprovedCalculatorInvocationRequestV1(
        invocation_id=invocation_id,
        scenario_id="scenario:approved:one",
        correlation_id="corr:approved:one",
        operation=operation,
        invoked_at=invoked_at,
    )


def _dummy_inputs() -> dict[str, object]:
    return {
        "decision": cast(DecisionSetV1, object()),
        "intent_request": cast(CapacityIntentDecisionGateRequestV1, object()),
        "capacity_assessments": (cast(CapacityAssessmentV1, object()),),
        "previews": (cast(PreTradePreviewV1, object()),),
        "pro_forma_risk": cast(RiskPolicyEvaluationV1, object()),
    }


def _boundary() -> tuple[FinalDecisionReviewApprovedInvocationV1, _FakeWorkflow]:
    workflow = _FakeWorkflow()
    return FinalDecisionReviewApprovedInvocationV1(workflow=workflow), workflow


def test_purchase_invocation_calls_allowlisted_workflow_once() -> None:
    boundary, workflow = _boundary()
    result = boundary.invoke_purchase(
        request=_request(ApprovedCalculatorOperation.PURCHASE_REVIEW),
        completed_at=NOW,
        **_dummy_inputs(),  # type: ignore[arg-type]
    )
    assert workflow.purchase_calls == 1
    assert workflow.sell_calls == 0
    assert result.publication.direction is OrderSide.BUY
    assert result.replay_checked is True
    assert result.trade_authorized is False
    assert result.trading_methods is False


def test_wrong_operation_is_rejected_before_workflow_call() -> None:
    boundary, workflow = _boundary()
    with pytest.raises(
        FinalDecisionReviewApprovedInvocationError,
        match="FINAL_DECISION_REVIEW_INVOCATION_OPERATION_NOT_ALLOWLISTED",
    ):
        boundary.invoke_purchase(
            request=_request(ApprovedCalculatorOperation.SELL_REVIEW),
            completed_at=NOW,
            **_dummy_inputs(),  # type: ignore[arg-type]
        )
    assert workflow.purchase_calls == 0


def test_replay_is_rejected_after_one_successful_invocation() -> None:
    boundary, workflow = _boundary()
    request = _request(ApprovedCalculatorOperation.PURCHASE_REVIEW)
    boundary.invoke_purchase(
        request=request,
        completed_at=NOW,
        **_dummy_inputs(),  # type: ignore[arg-type]
    )
    with pytest.raises(
        FinalDecisionReviewApprovedInvocationError,
        match="FINAL_DECISION_REVIEW_INVOCATION_REPLAY_DETECTED",
    ):
        boundary.invoke_purchase(
            request=request,
            completed_at=NOW,
            **_dummy_inputs(),  # type: ignore[arg-type]
        )
    assert workflow.purchase_calls == 1


def test_stale_and_future_invocations_are_rejected() -> None:
    boundary, workflow = _boundary()
    with pytest.raises(
        FinalDecisionReviewApprovedInvocationError,
        match="FINAL_DECISION_REVIEW_INVOCATION_STALE",
    ):
        boundary.invoke_purchase(
            request=_request(
                ApprovedCalculatorOperation.PURCHASE_REVIEW,
                invoked_at=NOW - timedelta(seconds=301),
            ),
            completed_at=NOW,
            **_dummy_inputs(),  # type: ignore[arg-type]
        )
    with pytest.raises(
        FinalDecisionReviewApprovedInvocationError,
        match="FINAL_DECISION_REVIEW_INVOCATION_FROM_FUTURE",
    ):
        boundary.invoke_purchase(
            request=_request(
                ApprovedCalculatorOperation.PURCHASE_REVIEW,
                invocation_id="invoke:approved:future",
                invoked_at=NOW + timedelta(seconds=31),
            ),
            completed_at=NOW,
            **_dummy_inputs(),  # type: ignore[arg-type]
        )
    assert workflow.purchase_calls == 0


def test_failed_workflow_does_not_consume_invocation_id() -> None:
    boundary, workflow = _boundary()
    request = _request(ApprovedCalculatorOperation.PURCHASE_REVIEW)
    workflow.fail = True
    with pytest.raises(FinalDecisionReviewApprovedInvocationError, match="TEST_FAILURE"):
        boundary.invoke_purchase(
            request=request,
            completed_at=NOW,
            **_dummy_inputs(),  # type: ignore[arg-type]
        )
    workflow.fail = False
    result = boundary.invoke_purchase(
        request=request,
        completed_at=NOW,
        **_dummy_inputs(),  # type: ignore[arg-type]
    )
    assert result.invoked_once is True
    assert workflow.purchase_calls == 2


def test_concurrent_duplicate_invocation_completes_only_once() -> None:
    boundary, workflow = _boundary()
    request = _request(ApprovedCalculatorOperation.PURCHASE_REVIEW)

    def invoke() -> str:
        try:
            boundary.invoke_purchase(
                request=request,
                completed_at=NOW,
                **_dummy_inputs(),  # type: ignore[arg-type]
            )
            return "published"
        except FinalDecisionReviewApprovedInvocationError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = tuple(executor.map(lambda _: invoke(), range(2)))
    assert outcomes.count("published") == 1
    assert outcomes.count("FINAL_DECISION_REVIEW_INVOCATION_REPLAY_DETECTED") == 1
    assert workflow.purchase_calls == 1


def test_runtime_registers_one_boundary_over_exact_workflow() -> None:
    runtime = register_final_decision_review_production_sources(
        bridge=object(),  # type: ignore[arg-type]
        portfolio_payload_loader=lambda: {},
    )
    assert runtime.approved_invocation.workflow is runtime.calculator_intent_workflow
    assert runtime.public_source_publication_route_created is False
    assert runtime.broker_write_called is False
    assert runtime.trading_methods is False


def test_raw_request_and_public_or_write_surface_are_rejected() -> None:
    boundary, workflow = _boundary()
    with pytest.raises(
        FinalDecisionReviewApprovedInvocationError,
        match="FINAL_DECISION_REVIEW_INVOCATION_REQUEST_TYPE_INVALID",
    ):
        boundary.invoke_purchase(
            request={"operation": "purchase_review"},  # type: ignore[arg-type]
            completed_at=NOW,
            **_dummy_inputs(),  # type: ignore[arg-type]
        )
    assert workflow.purchase_calls == 0

    source = Path(
        "omni_cio/release/final_decision_review_approved_invocation_v1.py"
    ).read_text(encoding="utf-8").lower()
    forbidden = (
        "@app.get",
        "@app.post",
        "@app.put",
        "@app.delete",
        ".post_order(",
        ".replace_order(",
        ".cancel_order(",
        "request.body",
        "logger.exception",
    )
    assert all(marker not in source for marker in forbidden)
