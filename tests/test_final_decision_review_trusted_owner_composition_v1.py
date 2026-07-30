from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from omni_cio.contracts.v1.capacity import (
    CapacityAssessmentV1,
    CapacityOrderRequestV1,
    OrderSide,
)
from omni_cio.contracts.v1.common import AccountReference
from omni_cio.contracts.v1.decision import DecisionSetV1
from omni_cio.contracts.v1.decision_capacity_intent import (
    CapacityIntentDecisionGateRequestV1,
)
from omni_cio.contracts.v1.decision_pro_forma_risk_binding import (
    ProFormaRiskScenarioMethod,
    ProFormaRiskScenarioV1,
    calculate_pro_forma_intent_fingerprint,
)
from omni_cio.contracts.v1.final_decision_review_approved_invocation import (
    ApprovedCalculatorInvocationRequestV1,
    ApprovedCalculatorInvocationResultV1,
    ApprovedCalculatorOperation,
)
from omni_cio.contracts.v1.pretrade import PreTradePreviewV1
from omni_cio.contracts.v1.risk import RiskPolicyEvaluationV1
from omni_cio.contracts.v1.sell_pretrade import SellPreTradePreviewV1
from omni_cio.release.final_decision_review_approved_invocation_v1 import (
    FinalDecisionReviewApprovedInvocationError,
    FinalDecisionReviewApprovedInvocationV1,
)
from omni_cio.release.final_decision_review_calculator_provider_registry_v1 import (
    FinalDecisionReviewCalculatorProviderRegistryV1,
)
from omni_cio.release.final_decision_review_existing_calculator_providers_v1 import (
    PURCHASE_PROVIDER_ID,
    SELL_PROVIDER_ID,
)
from omni_cio.release.final_decision_review_production_owner_callables_v1 import (
    FinalDecisionReviewProductionOwnerCallableStoreV1,
    register_final_decision_review_production_owner_callables,
)
from omni_cio.release.final_decision_review_trusted_owner_composition_v1 import (
    FinalDecisionReviewTrustedCommonOwnerPortsV1,
    FinalDecisionReviewTrustedOwnerCompositionError,
    FinalDecisionReviewTrustedOwnerCompositionV1,
    FinalDecisionReviewTrustedPurchaseOwnerPortsV1,
    FinalDecisionReviewTrustedSellOwnerPortsV1,
)


NOW = datetime.now(timezone.utc).replace(microsecond=0)
ACCOUNT = AccountReference(masked_id="account:****1234")


class _RecordingInvocation(FinalDecisionReviewApprovedInvocationV1):
    def __init__(self) -> None:
        self.calls = 0

    def _result(self, values: dict[str, Any]) -> ApprovedCalculatorInvocationResultV1:
        self.calls += 1
        request = cast(
            ApprovedCalculatorInvocationRequestV1,
            values["request"],
        )
        return ApprovedCalculatorInvocationResultV1.model_construct(
            request=request,
        )

    def invoke_purchase(
        self,
        **values: Any,
    ) -> ApprovedCalculatorInvocationResultV1:  # type: ignore[override]
        return self._result(values)

    def invoke_sell(
        self,
        **values: Any,
    ) -> ApprovedCalculatorInvocationResultV1:  # type: ignore[override]
        return self._result(values)


class _FailingInvocation(_RecordingInvocation):
    def invoke_purchase(
        self,
        **_: Any,
    ) -> ApprovedCalculatorInvocationResultV1:  # type: ignore[override]
        self.calls += 1
        raise FinalDecisionReviewApprovedInvocationError("SAFE_DOWNSTREAM_FAILURE")


def _runtime() -> tuple[
    FinalDecisionReviewTrustedOwnerCompositionV1,
    FinalDecisionReviewProductionOwnerCallableStoreV1,
    _RecordingInvocation,
]:
    invocation = _RecordingInvocation()
    registry = FinalDecisionReviewCalculatorProviderRegistryV1(
        invocation=invocation,
    )
    store = FinalDecisionReviewProductionOwnerCallableStoreV1()
    register_final_decision_review_production_owner_callables(
        registry=registry,
        store=store,
    )
    return (
        FinalDecisionReviewTrustedOwnerCompositionV1(
            registry=registry,
            store=store,
        ),
        store,
        invocation,
    )


def _request(
    operation: ApprovedCalculatorOperation,
) -> ApprovedCalculatorInvocationRequestV1:
    return ApprovedCalculatorInvocationRequestV1(
        invocation_id=f"invoke:trusted-owner:{operation.value}",
        scenario_id=f"scenario:trusted-owner:{operation.value}",
        correlation_id=f"corr:trusted-owner:{operation.value}",
        operation=operation,
        invoked_at=NOW,
    )


def _capacity_request(side: OrderSide) -> CapacityOrderRequestV1:
    return CapacityOrderRequestV1(
        request_id=f"capacity:trusted-owner:{side.value}",
        instrument_key="instrument:trusted-owner:one",
        side=side,
        currency="RUB",
        quantity_lots=2,
        lot_size=10,
        reference_price=Decimal("100"),
        intended_execution_days=1,
        units=20,
        order_notional=Decimal("2000"),
    )


def _owners(
    *,
    request: ApprovedCalculatorInvocationRequestV1,
    calls: dict[str, int],
    scenario_id: str | None = None,
) -> FinalDecisionReviewTrustedPurchaseOwnerPortsV1 | (
    FinalDecisionReviewTrustedSellOwnerPortsV1
):
    side = (
        OrderSide.BUY
        if request.operation is ApprovedCalculatorOperation.PURCHASE_REVIEW
        else OrderSide.SELL
    )
    capacity_request = _capacity_request(side)
    decision = DecisionSetV1.model_construct(
        metadata=SimpleNamespace(account=ACCOUNT),
    )
    intent = CapacityIntentDecisionGateRequestV1(
        gate_id=f"gate:trusted-owner:{side.value}",
        requested_option_id="option:trusted-owner:one",
        expected_capacity_requests=(capacity_request,),
    )
    assessment = CapacityAssessmentV1.model_construct(
        request=capacity_request,
    )
    risk = RiskPolicyEvaluationV1.model_construct(
        metadata=SimpleNamespace(
            account=ACCOUNT,
            retrieved_at=NOW,
        ),
        policy=SimpleNamespace(
            allow_margin=False,
            allow_short_sales=False,
            allow_derivatives=False,
            allow_currency_operations=False,
        ),
    )
    fingerprint = calculate_pro_forma_intent_fingerprint(
        account_masked_id=ACCOUNT.masked_id,
        requested_option_id=intent.requested_option_id,
        direction=side,
        capacity_requests=intent.expected_capacity_requests,
    )
    scenario = ProFormaRiskScenarioV1.model_construct(
        scenario_id=scenario_id or request.scenario_id,
        generated_at=NOW,
        account=ACCOUNT,
        requested_option_id=intent.requested_option_id,
        direction=side,
        capacity_requests=intent.expected_capacity_requests,
        intent_fingerprint=fingerprint,
        risk_evaluation=risk,
        method=ProFormaRiskScenarioMethod.EXACT_CAPACITY_INTENT_POST_CHANGE,
        current_portfolio_risk=False,
        pro_forma_post_change=True,
        order_created=False,
        execution_ready=False,
        trading_methods=False,
    )

    def decision_owner(
        _: ApprovedCalculatorInvocationRequestV1,
    ) -> DecisionSetV1:
        calls["decision"] += 1
        return decision

    def intent_owner(
        _: ApprovedCalculatorInvocationRequestV1,
    ) -> CapacityIntentDecisionGateRequestV1:
        calls["intent"] += 1
        return intent

    def capacity_owner(
        _: ApprovedCalculatorInvocationRequestV1,
    ) -> tuple[CapacityAssessmentV1, ...]:
        calls["capacity"] += 1
        return (assessment,)

    def scenario_owner(
        _: ApprovedCalculatorInvocationRequestV1,
    ) -> ProFormaRiskScenarioV1:
        calls["scenario"] += 1
        return scenario

    common = FinalDecisionReviewTrustedCommonOwnerPortsV1(
        decision=decision_owner,
        intent=intent_owner,
        capacity=capacity_owner,
        pro_forma_scenario=scenario_owner,
    )
    if side is OrderSide.BUY:

        def purchase_previews(
            _: ApprovedCalculatorInvocationRequestV1,
        ) -> tuple[PreTradePreviewV1, ...]:
            calls["preview"] += 1
            return (
                PreTradePreviewV1.model_construct(
                    stable_key=capacity_request.instrument_key,
                    metadata=SimpleNamespace(account=ACCOUNT),
                ),
            )

        return FinalDecisionReviewTrustedPurchaseOwnerPortsV1(
            common=common,
            previews=purchase_previews,
        )

    def sell_previews(
        _: ApprovedCalculatorInvocationRequestV1,
    ) -> tuple[SellPreTradePreviewV1, ...]:
        calls["preview"] += 1
        return (
            SellPreTradePreviewV1.model_construct(
                stable_key=capacity_request.instrument_key,
                metadata=SimpleNamespace(account=ACCOUNT),
            ),
        )

    return FinalDecisionReviewTrustedSellOwnerPortsV1(
        common=common,
        previews=sell_previews,
    )


def _calls() -> dict[str, int]:
    return {
        "decision": 0,
        "intent": 0,
        "capacity": 0,
        "scenario": 0,
        "preview": 0,
    }


def test_purchase_composition_materializes_once_and_cleans_up() -> None:
    composition, store, invocation = _runtime()
    request = _request(ApprovedCalculatorOperation.PURCHASE_REVIEW)
    calls = _calls()
    owners = _owners(request=request, calls=calls)
    assert isinstance(owners, FinalDecisionReviewTrustedPurchaseOwnerPortsV1)
    result = composition.invoke_purchase(
        request=request,
        owners=owners,
        completed_at=NOW,
    )
    assert result.provider_id == PURCHASE_PROVIDER_ID
    assert result.request is request
    assert result.invocation.request is request
    assert result.materialized_owner_call_count == 5
    assert result.owner_bundle_discarded is True
    assert result.owner_pin_present_after_cleanup is False
    assert result.broker_write_called is False
    assert result.trade_authorized is False
    assert result.order_created is False
    assert result.trading_methods is False
    assert calls == {
        "decision": 1,
        "intent": 1,
        "capacity": 1,
        "scenario": 1,
        "preview": 1,
    }
    assert invocation.calls == 1
    assert store.active_bundle_count() == 0
    assert store.active_pin_count() == 0


def test_sell_composition_uses_fixed_sell_provider() -> None:
    composition, store, invocation = _runtime()
    request = _request(ApprovedCalculatorOperation.SELL_REVIEW)
    calls = _calls()
    owners = _owners(request=request, calls=calls)
    assert isinstance(owners, FinalDecisionReviewTrustedSellOwnerPortsV1)
    result = composition.invoke_sell(
        request=request,
        owners=owners,
        completed_at=NOW,
    )
    assert result.provider_id == SELL_PROVIDER_ID
    assert invocation.calls == 1
    assert all(value == 1 for value in calls.values())
    assert store.active_bundle_count() == 0
    assert store.active_pin_count() == 0


def test_wrong_operation_fails_before_owner_calls() -> None:
    composition, store, invocation = _runtime()
    request = _request(ApprovedCalculatorOperation.SELL_REVIEW)
    calls = _calls()
    sell_owners = _owners(request=request, calls=calls)
    assert isinstance(sell_owners, FinalDecisionReviewTrustedSellOwnerPortsV1)
    purchase_owners = FinalDecisionReviewTrustedPurchaseOwnerPortsV1(
        common=sell_owners.common,
        previews=lambda _: (PreTradePreviewV1.model_construct(),),
    )
    with pytest.raises(
        FinalDecisionReviewTrustedOwnerCompositionError,
        match="FINAL_DECISION_REVIEW_TRUSTED_OWNER_OPERATION_MISMATCH",
    ):
        composition.invoke_purchase(
            request=request,
            owners=purchase_owners,
        )
    assert all(value == 0 for value in calls.values())
    assert invocation.calls == 0
    assert store.active_bundle_count() == 0


def test_scenario_identity_mismatch_fails_before_publication() -> None:
    composition, store, invocation = _runtime()
    request = _request(ApprovedCalculatorOperation.PURCHASE_REVIEW)
    calls = _calls()
    owners = _owners(
        request=request,
        calls=calls,
        scenario_id="scenario:trusted-owner:other",
    )
    assert isinstance(owners, FinalDecisionReviewTrustedPurchaseOwnerPortsV1)
    with pytest.raises(
        FinalDecisionReviewTrustedOwnerCompositionError,
        match="FINAL_DECISION_REVIEW_TRUSTED_OWNER_OUTPUT_BINDING_INVALID",
    ):
        composition.invoke_purchase(
            request=request,
            owners=owners,
        )
    assert all(value == 1 for value in calls.values())
    assert invocation.calls == 0
    assert store.active_bundle_count() == 0
    assert store.active_pin_count() == 0


def test_current_risk_substitution_is_rejected() -> None:
    composition, store, invocation = _runtime()
    request = _request(ApprovedCalculatorOperation.PURCHASE_REVIEW)
    calls = _calls()
    owners = _owners(request=request, calls=calls)
    assert isinstance(owners, FinalDecisionReviewTrustedPurchaseOwnerPortsV1)
    original_owner = owners.common.pro_forma_scenario

    def current_risk_scenario(
        value: ApprovedCalculatorInvocationRequestV1,
    ) -> ProFormaRiskScenarioV1:
        scenario = original_owner(value)
        return scenario.model_copy(
            update={
                "current_portfolio_risk": True,
                "pro_forma_post_change": False,
            },
        )

    unsafe_common = FinalDecisionReviewTrustedCommonOwnerPortsV1(
        decision=owners.common.decision,
        intent=owners.common.intent,
        capacity=owners.common.capacity,
        pro_forma_scenario=current_risk_scenario,
    )
    with pytest.raises(
        FinalDecisionReviewTrustedOwnerCompositionError,
        match="FINAL_DECISION_REVIEW_TRUSTED_OWNER_OUTPUT_BINDING_INVALID",
    ):
        composition.invoke_purchase(
            request=request,
            owners=FinalDecisionReviewTrustedPurchaseOwnerPortsV1(
                common=unsafe_common,
                previews=owners.previews,
            ),
        )
    assert invocation.calls == 0
    assert store.active_bundle_count() == 0


def test_owner_failure_is_sanitized_without_publication() -> None:
    composition, store, invocation = _runtime()
    request = _request(ApprovedCalculatorOperation.PURCHASE_REVIEW)

    def failed(_: ApprovedCalculatorInvocationRequestV1) -> DecisionSetV1:
        raise RuntimeError("sensitive calculator detail")

    common = FinalDecisionReviewTrustedCommonOwnerPortsV1(
        decision=failed,
        intent=lambda _: cast(CapacityIntentDecisionGateRequestV1, object()),
        capacity=lambda _: (),
        pro_forma_scenario=lambda _: cast(ProFormaRiskScenarioV1, object()),
    )
    with pytest.raises(
        FinalDecisionReviewTrustedOwnerCompositionError,
        match="FINAL_DECISION_REVIEW_TRUSTED_OWNER_CALL_FAILED",
    ) as raised:
        composition.invoke_purchase(
            request=request,
            owners=FinalDecisionReviewTrustedPurchaseOwnerPortsV1(
                common=common,
                previews=lambda _: (),
            ),
        )
    assert "sensitive calculator detail" not in str(raised.value)
    assert invocation.calls == 0
    assert store.active_bundle_count() == 0


def test_downstream_failure_still_discards_owner_bundle_and_pin() -> None:
    invocation = _FailingInvocation()
    registry = FinalDecisionReviewCalculatorProviderRegistryV1(
        invocation=invocation,
    )
    store = FinalDecisionReviewProductionOwnerCallableStoreV1()
    register_final_decision_review_production_owner_callables(
        registry=registry,
        store=store,
    )
    composition = FinalDecisionReviewTrustedOwnerCompositionV1(
        registry=registry,
        store=store,
    )
    request = _request(ApprovedCalculatorOperation.PURCHASE_REVIEW)
    calls = _calls()
    owners = _owners(request=request, calls=calls)
    assert isinstance(owners, FinalDecisionReviewTrustedPurchaseOwnerPortsV1)
    with pytest.raises(
        FinalDecisionReviewTrustedOwnerCompositionError,
        match="FINAL_DECISION_REVIEW_TRUSTED_OWNER_INVOCATION_FAILED",
    ):
        composition.invoke_purchase(
            request=request,
            owners=owners,
            completed_at=NOW,
        )
    assert invocation.calls == 1
    assert store.active_bundle_count() == 0
    assert store.active_pin_count() == 0


def test_trusted_composition_has_no_http_or_broker_write_surface() -> None:
    source = (
        Path(
            "omni_cio/release/" "final_decision_review_trusted_owner_composition_v1.py"
        )
        .read_text(encoding="utf-8")
        .lower()
    )
    forbidden = (
        "@app.get",
        "@app.post",
        "@app.put",
        "@app.patch",
        "@app.delete",
        ".post_order(",
        ".replace_order(",
        ".cancel_order(",
        "request.body",
        "logger.exception",
    )
    assert all(marker not in source for marker in forbidden)
