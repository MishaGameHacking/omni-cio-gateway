from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from omni_cio.contracts.v1.capacity import CapacityAssessmentV1
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
    TrustedScenarioPublicationResultV1,
)
from omni_cio.contracts.v1.pretrade import PreTradePreviewV1
from omni_cio.contracts.v1.risk import RiskPolicyEvaluationV1
from omni_cio.contracts.v1.sell_pretrade import SellPreTradePreviewV1
from omni_cio.release.final_decision_review_approved_invocation_v1 import (
    FinalDecisionReviewApprovedInvocationV1,
)
from omni_cio.release.final_decision_review_calculator_provider_registry_v1 import (
    FinalDecisionReviewCalculatorProviderRegistryV1,
)
from omni_cio.release.final_decision_review_existing_calculator_providers_v1 import (
    PURCHASE_PROVIDER_ID,
    SELL_PROVIDER_ID,
    ApprovedCalculatorCommonOwnersV1,
    ApprovedPurchaseCalculatorOwnersV1,
    ApprovedSellCalculatorOwnersV1,
    FinalDecisionReviewExistingCalculatorProviderError,
    build_existing_purchase_provider,
    build_existing_sell_provider,
    register_existing_calculator_providers,
)


NOW = datetime(2026, 7, 30, 13, 0, tzinfo=timezone.utc)


def _request(
    operation: ApprovedCalculatorOperation,
) -> ApprovedCalculatorInvocationRequestV1:
    return ApprovedCalculatorInvocationRequestV1(
        invocation_id=f"invoke:existing:{operation.value}",
        scenario_id="scenario:existing:one",
        correlation_id="corr:existing:one",
        operation=operation,
        invoked_at=NOW,
    )


def _risk() -> RiskPolicyEvaluationV1:
    return RiskPolicyEvaluationV1.model_construct(
        metadata=SimpleNamespace(retrieved_at=NOW),
    )


def _common(calls: dict[str, int]) -> ApprovedCalculatorCommonOwnersV1:
    def decision(_: ApprovedCalculatorInvocationRequestV1) -> DecisionSetV1:
        calls["decision"] += 1
        return DecisionSetV1.model_construct()

    def intent(
        _: ApprovedCalculatorInvocationRequestV1,
    ) -> CapacityIntentDecisionGateRequestV1:
        calls["intent"] += 1
        return CapacityIntentDecisionGateRequestV1.model_construct()

    def capacity(
        _: ApprovedCalculatorInvocationRequestV1,
    ) -> tuple[CapacityAssessmentV1, ...]:
        calls["capacity"] += 1
        return (CapacityAssessmentV1.model_construct(),)

    def risk(_: ApprovedCalculatorInvocationRequestV1) -> RiskPolicyEvaluationV1:
        calls["risk"] += 1
        return _risk()

    return ApprovedCalculatorCommonOwnersV1(
        decision=decision,
        intent=intent,
        capacity=capacity,
        pro_forma_risk=risk,
    )


def test_purchase_adapter_preserves_typed_owner_outputs() -> None:
    calls = {"decision": 0, "intent": 0, "capacity": 0, "risk": 0, "preview": 0}

    def previews(
        _: ApprovedCalculatorInvocationRequestV1,
    ) -> tuple[PreTradePreviewV1, ...]:
        calls["preview"] += 1
        return (PreTradePreviewV1.model_construct(),)

    provider = build_existing_purchase_provider(
        ApprovedPurchaseCalculatorOwnersV1(
            common=_common(calls),
            previews=previews,
        )
    )
    bundle = provider(_request(ApprovedCalculatorOperation.PURCHASE_REVIEW))
    assert bundle.scenario_id == "scenario:existing:one"
    assert bundle.correlation_id == "corr:existing:one"
    assert bundle.built_at == NOW
    assert len(bundle.purchase_previews) == 1
    assert bundle.sell_previews == ()
    assert calls == {
        "decision": 1,
        "intent": 1,
        "capacity": 1,
        "risk": 1,
        "preview": 1,
    }


def test_sell_adapter_preserves_typed_owner_outputs() -> None:
    calls = {"decision": 0, "intent": 0, "capacity": 0, "risk": 0, "preview": 0}

    def previews(
        _: ApprovedCalculatorInvocationRequestV1,
    ) -> tuple[SellPreTradePreviewV1, ...]:
        calls["preview"] += 1
        return (SellPreTradePreviewV1.model_construct(),)

    provider = build_existing_sell_provider(
        ApprovedSellCalculatorOwnersV1(
            common=_common(calls),
            previews=previews,
        )
    )
    bundle = provider(_request(ApprovedCalculatorOperation.SELL_REVIEW))
    assert bundle.purchase_previews == ()
    assert len(bundle.sell_previews) == 1
    assert calls["preview"] == 1


def test_wrong_operation_fails_before_owner_calls() -> None:
    calls = {"decision": 0, "intent": 0, "capacity": 0, "risk": 0, "preview": 0}

    def previews(
        _: ApprovedCalculatorInvocationRequestV1,
    ) -> tuple[PreTradePreviewV1, ...]:
        calls["preview"] += 1
        return (PreTradePreviewV1.model_construct(),)

    provider = build_existing_purchase_provider(
        ApprovedPurchaseCalculatorOwnersV1(
            common=_common(calls),
            previews=previews,
        )
    )
    with pytest.raises(
        FinalDecisionReviewExistingCalculatorProviderError,
        match="FINAL_DECISION_REVIEW_EXISTING_OPERATION_MISMATCH",
    ):
        provider(_request(ApprovedCalculatorOperation.SELL_REVIEW))
    assert all(value == 0 for value in calls.values())


def test_owner_exception_and_wrong_type_fail_closed() -> None:
    def failed(_: ApprovedCalculatorInvocationRequestV1) -> DecisionSetV1:
        raise RuntimeError("sensitive calculator detail")

    owners = ApprovedCalculatorCommonOwnersV1(
        decision=failed,
        intent=lambda _: CapacityIntentDecisionGateRequestV1.model_construct(),
        capacity=lambda _: (CapacityAssessmentV1.model_construct(),),
        pro_forma_risk=lambda _: _risk(),
    )
    provider = build_existing_purchase_provider(
        ApprovedPurchaseCalculatorOwnersV1(
            common=owners,
            previews=lambda _: (PreTradePreviewV1.model_construct(),),
        )
    )
    with pytest.raises(
        FinalDecisionReviewExistingCalculatorProviderError,
        match="FINAL_DECISION_REVIEW_EXISTING_OWNER_CALL_FAILED",
    ):
        provider(_request(ApprovedCalculatorOperation.PURCHASE_REVIEW))

    raw_owners = ApprovedCalculatorCommonOwnersV1(
        decision=lambda _: cast(DecisionSetV1, {"decision": "raw"}),
        intent=lambda _: CapacityIntentDecisionGateRequestV1.model_construct(),
        capacity=lambda _: (CapacityAssessmentV1.model_construct(),),
        pro_forma_risk=lambda _: _risk(),
    )
    raw_provider = build_existing_purchase_provider(
        ApprovedPurchaseCalculatorOwnersV1(
            common=raw_owners,
            previews=lambda _: (PreTradePreviewV1.model_construct(),),
        )
    )
    with pytest.raises(
        FinalDecisionReviewExistingCalculatorProviderError,
        match="FINAL_DECISION_REVIEW_EXISTING_DECISION_TYPE_INVALID",
    ):
        raw_provider(_request(ApprovedCalculatorOperation.PURCHASE_REVIEW))


class _UnusedInvocation(FinalDecisionReviewApprovedInvocationV1):
    def __init__(self) -> None:
        self.calls = 0

    def invoke_purchase(self, **_: Any) -> ApprovedCalculatorInvocationResultV1:  # type: ignore[override]
        self.calls += 1
        return cast(ApprovedCalculatorInvocationResultV1, object())

    def invoke_sell(self, **_: Any) -> ApprovedCalculatorInvocationResultV1:  # type: ignore[override]
        self.calls += 1
        return cast(ApprovedCalculatorInvocationResultV1, object())


def test_registration_uses_fixed_ids_without_startup_owner_calls() -> None:
    calls = {"decision": 0, "intent": 0, "capacity": 0, "risk": 0, "preview": 0}
    common = _common(calls)

    def purchase_preview(
        _: ApprovedCalculatorInvocationRequestV1,
    ) -> tuple[PreTradePreviewV1, ...]:
        calls["preview"] += 1
        return (PreTradePreviewV1.model_construct(),)

    def sell_preview(
        _: ApprovedCalculatorInvocationRequestV1,
    ) -> tuple[SellPreTradePreviewV1, ...]:
        calls["preview"] += 1
        return (SellPreTradePreviewV1.model_construct(),)

    invocation = _UnusedInvocation()
    registry = FinalDecisionReviewCalculatorProviderRegistryV1(
        invocation=invocation,
    )
    register_existing_calculator_providers(
        registry=registry,
        purchase=ApprovedPurchaseCalculatorOwnersV1(
            common=common,
            previews=purchase_preview,
        ),
        sell=ApprovedSellCalculatorOwnersV1(
            common=common,
            previews=sell_preview,
        ),
    )
    assert PURCHASE_PROVIDER_ID == "provider:existing:purchase-review"
    assert SELL_PROVIDER_ID == "provider:existing:sell-review"
    assert all(value == 0 for value in calls.values())
    assert invocation.calls == 0


def test_existing_provider_adapter_has_no_http_or_broker_write_surface() -> None:
    source = Path(
        "omni_cio/release/final_decision_review_existing_calculator_providers_v1.py"
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
