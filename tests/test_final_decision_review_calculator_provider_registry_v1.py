from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from omni_cio.contracts.v1.capacity import CapacityAssessmentV1, OrderSide
from omni_cio.contracts.v1.common import AccountReference, SourceReference
from omni_cio.contracts.v1.decision import DecisionSetV1
from omni_cio.contracts.v1.decision_capacity_intent import (
    CapacityIntentDecisionGateRequestV1,
)
from omni_cio.contracts.v1.final_decision_review_approved_invocation import (
    ApprovedCalculatorInvocationRequestV1,
    ApprovedCalculatorInvocationResultV1,
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
    FinalDecisionReviewApprovedInvocationV1,
)
from omni_cio.release.final_decision_review_calculator_provider_registry_v1 import (
    ApprovedCalculatorProviderBundleV1,
    FinalDecisionReviewCalculatorProviderRegistryError,
    FinalDecisionReviewCalculatorProviderRegistryV1,
)
from omni_cio.release.final_decision_review_production_registration_v1 import (
    register_final_decision_review_production_sources,
)


NOW = datetime(2026, 7, 30, 12, 30, tzinfo=timezone.utc)
ACCOUNT = AccountReference(masked_id="****1234")


def _request(
    operation: ApprovedCalculatorOperation,
) -> ApprovedCalculatorInvocationRequestV1:
    return ApprovedCalculatorInvocationRequestV1(
        invocation_id=f"invoke:provider:{operation.value}",
        scenario_id="scenario:provider:one",
        correlation_id="corr:provider:one",
        operation=operation,
        invoked_at=NOW,
    )


def _publication(
    request: ApprovedCalculatorInvocationRequestV1,
    side: OrderSide,
) -> TrustedScenarioPublicationResultV1:
    return TrustedScenarioPublicationResultV1(
        disposition=TrustedScenarioPublicationDisposition.PUBLISHED,
        scenario_id=request.scenario_id,
        direction=side,
        account=ACCOUNT,
        gate_assessed_at=request.invoked_at,
        pro_forma_retrieved_at=request.invoked_at,
        published_at=request.invoked_at,
        expires_at=request.invoked_at + timedelta(minutes=15),
        source=SourceReference(
            provider="omni-cio",
            operation="provider-registry-test",
            retrieved_at=request.invoked_at,
        ),
        instrument_count=1,
        gate_ready=True,
        pro_forma_decision_ready=True,
        source_replaced=False,
        source_evicted=False,
        active_bundle_count=1,
    )


class _FakeInvocation(FinalDecisionReviewApprovedInvocationV1):
    def __init__(self) -> None:
        self.purchase_calls = 0
        self.sell_calls = 0

    def invoke_purchase(
        self,
        **kwargs: Any,
    ) -> ApprovedCalculatorInvocationResultV1:  # type: ignore[override]
        self.purchase_calls += 1
        request = cast(ApprovedCalculatorInvocationRequestV1, kwargs["request"])
        return ApprovedCalculatorInvocationResultV1(
            request=request,
            completed_at=request.invoked_at,
            publication=_publication(request, OrderSide.BUY),
            capacity_assessment_count=1,
            preview_count=1,
        )

    def invoke_sell(
        self,
        **kwargs: Any,
    ) -> ApprovedCalculatorInvocationResultV1:  # type: ignore[override]
        self.sell_calls += 1
        request = cast(ApprovedCalculatorInvocationRequestV1, kwargs["request"])
        return ApprovedCalculatorInvocationResultV1(
            request=request,
            completed_at=request.invoked_at,
            publication=_publication(request, OrderSide.SELL),
            capacity_assessment_count=1,
            preview_count=1,
        )


def _bundle(
    *,
    purchase: bool,
    scenario_id: str = "scenario:provider:one",
    correlation_id: str = "corr:provider:one",
    built_at: datetime = NOW,
) -> ApprovedCalculatorProviderBundleV1:
    risk = RiskPolicyEvaluationV1.model_construct(
        metadata=SimpleNamespace(retrieved_at=built_at),
    )
    return ApprovedCalculatorProviderBundleV1(
        scenario_id=scenario_id,
        correlation_id=correlation_id,
        built_at=built_at,
        decision=DecisionSetV1.model_construct(),
        intent_request=CapacityIntentDecisionGateRequestV1.model_construct(),
        capacity_assessments=(CapacityAssessmentV1.model_construct(),),
        purchase_previews=(PreTradePreviewV1.model_construct(),) if purchase else (),
        sell_previews=(SellPreTradePreviewV1.model_construct(),) if not purchase else (),
        pro_forma_risk=risk,
    )


def _registry() -> tuple[
    FinalDecisionReviewCalculatorProviderRegistryV1,
    _FakeInvocation,
]:
    invocation = _FakeInvocation()
    registry = FinalDecisionReviewCalculatorProviderRegistryV1(
        invocation=invocation,
    )
    return registry, invocation


def test_registered_purchase_provider_invokes_approved_boundary_once() -> None:
    registry, invocation = _registry()
    request = _request(ApprovedCalculatorOperation.PURCHASE_REVIEW)
    provider_calls = 0

    def provider(
        _: ApprovedCalculatorInvocationRequestV1,
    ) -> ApprovedCalculatorProviderBundleV1:
        nonlocal provider_calls
        provider_calls += 1
        return _bundle(purchase=True)

    registry.register(
        provider_id="provider:approved:purchase",
        operation=ApprovedCalculatorOperation.PURCHASE_REVIEW,
        provider=provider,
    )
    result = registry.invoke(
        provider_id="provider:approved:purchase",
        request=request,
        completed_at=NOW,
    )
    assert provider_calls == 1
    assert invocation.purchase_calls == 1
    assert invocation.sell_calls == 0
    assert result.publication.direction is OrderSide.BUY
    assert result.trading_methods is False


def test_registry_rejects_unknown_and_duplicate_provider() -> None:
    registry, invocation = _registry()
    request = _request(ApprovedCalculatorOperation.PURCHASE_REVIEW)
    with pytest.raises(
        FinalDecisionReviewCalculatorProviderRegistryError,
        match="FINAL_DECISION_REVIEW_PROVIDER_NOT_REGISTERED",
    ):
        registry.invoke(
            provider_id="provider:missing",
            request=request,
            completed_at=NOW,
        )

    provider = lambda _: _bundle(purchase=True)
    registry.register(
        provider_id="provider:duplicate",
        operation=ApprovedCalculatorOperation.PURCHASE_REVIEW,
        provider=provider,
    )
    with pytest.raises(
        FinalDecisionReviewCalculatorProviderRegistryError,
        match="FINAL_DECISION_REVIEW_PROVIDER_ALREADY_REGISTERED",
    ):
        registry.register(
            provider_id="provider:duplicate",
            operation=ApprovedCalculatorOperation.PURCHASE_REVIEW,
            provider=provider,
        )
    assert invocation.purchase_calls == 0


def test_context_and_direction_mismatches_fail_before_invocation() -> None:
    registry, invocation = _registry()
    request = _request(ApprovedCalculatorOperation.PURCHASE_REVIEW)
    cases: tuple[tuple[str, Any, str], ...] = (
        (
            "provider:scenario",
            lambda _: _bundle(purchase=True, scenario_id="scenario:other"),
            "SCENARIO_MISMATCH",
        ),
        (
            "provider:correlation",
            lambda _: _bundle(purchase=True, correlation_id="corr:other"),
            "CORRELATION_MISMATCH",
        ),
        (
            "provider:direction",
            lambda _: _bundle(purchase=False),
            "DIRECTION_MISMATCH",
        ),
    )
    for provider_id, provider, error in cases:
        registry.register(
            provider_id=provider_id,
            operation=ApprovedCalculatorOperation.PURCHASE_REVIEW,
            provider=provider,
        )
        with pytest.raises(
            FinalDecisionReviewCalculatorProviderRegistryError,
            match=error,
        ):
            registry.invoke(
                provider_id=provider_id,
                request=request,
                completed_at=NOW,
            )
    assert invocation.purchase_calls == 0


def test_stale_future_exception_and_raw_output_fail_closed() -> None:
    registry, invocation = _registry()
    request = _request(ApprovedCalculatorOperation.PURCHASE_REVIEW)

    def failed(
        _: ApprovedCalculatorInvocationRequestV1,
    ) -> ApprovedCalculatorProviderBundleV1:
        raise RuntimeError("sensitive provider detail")

    providers: tuple[tuple[str, Any, str], ...] = (
        (
            "provider:stale",
            lambda _: _bundle(
                purchase=True,
                built_at=NOW - timedelta(seconds=301),
            ),
            "BUNDLE_STALE",
        ),
        (
            "provider:future",
            lambda _: _bundle(
                purchase=True,
                built_at=NOW + timedelta(seconds=31),
            ),
            "BUNDLE_FROM_FUTURE",
        ),
        ("provider:failed", failed, "PROVIDER_CALL_FAILED"),
        ("provider:raw", lambda _: {"decision": "raw"}, "BUNDLE_TYPE_INVALID"),
    )
    for provider_id, provider, error in providers:
        registry.register(
            provider_id=provider_id,
            operation=ApprovedCalculatorOperation.PURCHASE_REVIEW,
            provider=provider,
        )
        with pytest.raises(
            FinalDecisionReviewCalculatorProviderRegistryError,
            match=error,
        ):
            registry.invoke(
                provider_id=provider_id,
                request=request,
                completed_at=NOW,
            )
    assert invocation.purchase_calls == 0


def test_runtime_registers_empty_provider_registry_without_startup_call() -> None:
    runtime = register_final_decision_review_production_sources(
        bridge=object(),  # type: ignore[arg-type]
        portfolio_payload_loader=lambda: {},
    )
    assert runtime.provider_registry.invocation is runtime.approved_invocation
    assert runtime.startup_broker_call_performed is False
    assert runtime.public_source_publication_route_created is False
    assert runtime.broker_write_called is False
    assert runtime.trading_methods is False


def test_provider_registry_has_no_public_or_broker_write_surface() -> None:
    source = Path(
        "omni_cio/release/final_decision_review_calculator_provider_registry_v1.py"
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
