from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
)
from omni_cio.release.final_decision_review_production_owner_callables_v1 import (
    FinalDecisionReviewProductionOwnerCallableError,
    FinalDecisionReviewProductionOwnerCallableRouterV1,
    FinalDecisionReviewProductionOwnerCallableStoreV1,
    register_final_decision_review_production_owner_callables,
)

NOW = datetime.now(timezone.utc).replace(microsecond=0)


class _UnusedInvocation(FinalDecisionReviewApprovedInvocationV1):
    def __init__(self) -> None:
        self.calls = 0

    def invoke_purchase(
        self,
        **_: Any,
    ) -> ApprovedCalculatorInvocationResultV1:  # type: ignore[override]
        self.calls += 1
        return cast(ApprovedCalculatorInvocationResultV1, object())

    def invoke_sell(
        self,
        **_: Any,
    ) -> ApprovedCalculatorInvocationResultV1:  # type: ignore[override]
        self.calls += 1
        return cast(ApprovedCalculatorInvocationResultV1, object())


def _request(
    *,
    correlation_id: str = "corr:production-owner:one",
    operation: ApprovedCalculatorOperation = (
        ApprovedCalculatorOperation.PURCHASE_REVIEW
    ),
) -> ApprovedCalculatorInvocationRequestV1:
    return ApprovedCalculatorInvocationRequestV1(
        invocation_id=(
            f"invoke:production-owner:{operation.value}:"
            f"{correlation_id.rsplit(':', maxsplit=1)[-1]}"
        ),
        scenario_id="scenario:production-owner:one",
        correlation_id=correlation_id,
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


def _purchase_owners(
    calls: dict[str, int],
) -> ApprovedPurchaseCalculatorOwnersV1:
    def previews(
        _: ApprovedCalculatorInvocationRequestV1,
    ) -> tuple[PreTradePreviewV1, ...]:
        calls["preview"] += 1
        return (PreTradePreviewV1.model_construct(),)

    return ApprovedPurchaseCalculatorOwnersV1(
        common=_common(calls),
        previews=previews,
    )


def _sell_owners(
    calls: dict[str, int],
) -> ApprovedSellCalculatorOwnersV1:
    def previews(
        _: ApprovedCalculatorInvocationRequestV1,
    ) -> tuple[SellPreTradePreviewV1, ...]:
        calls["preview"] += 1
        return (SellPreTradePreviewV1.model_construct(),)

    return ApprovedSellCalculatorOwnersV1(
        common=_common(calls),
        previews=previews,
    )


def test_publish_is_internal_bounded_and_does_not_call_owners() -> None:
    calls = {"decision": 0, "intent": 0, "capacity": 0, "risk": 0, "preview": 0}
    store = FinalDecisionReviewProductionOwnerCallableStoreV1(
        ttl_seconds=900,
        capacity=1,
    )
    publication = store.publish_purchase(
        scenario_id="scenario:production-owner:one",
        correlation_id="corr:production-owner:one",
        owners=_purchase_owners(calls),
        published_at=NOW,
    )
    assert publication.active_bundle_count == 1
    assert publication.internal_only is True
    assert publication.owner_called is False
    assert publication.broker_write_called is False
    assert publication.trade_authorized is False
    assert publication.order_created is False
    assert publication.trading_methods is False
    assert store.active_bundle_count(checked_at=NOW) == 1
    assert store.active_pin_count(checked_at=NOW) == 0
    assert all(value == 0 for value in calls.values())


def test_exact_duplicate_is_rejected_until_bundle_expires() -> None:
    calls = {"decision": 0, "intent": 0, "capacity": 0, "risk": 0, "preview": 0}
    store = FinalDecisionReviewProductionOwnerCallableStoreV1(ttl_seconds=60)
    owners = _purchase_owners(calls)
    store.publish_purchase(
        scenario_id="scenario:production-owner:one",
        correlation_id="corr:production-owner:one",
        owners=owners,
        published_at=NOW,
    )
    with pytest.raises(
        FinalDecisionReviewProductionOwnerCallableError,
        match="FINAL_DECISION_REVIEW_PRODUCTION_OWNER_ALREADY_PUBLISHED",
    ):
        store.publish_purchase(
            scenario_id="scenario:production-owner:one",
            correlation_id="corr:production-owner:one",
            owners=owners,
            published_at=NOW + timedelta(seconds=30),
        )
    assert (
        store.active_bundle_count(
            checked_at=NOW + timedelta(seconds=61),
        )
        == 0
    )
    assert all(value == 0 for value in calls.values())


def test_router_dispatches_only_the_exact_scenario_bundle() -> None:
    calls = {"decision": 0, "intent": 0, "capacity": 0, "risk": 0, "preview": 0}
    store = FinalDecisionReviewProductionOwnerCallableStoreV1()
    store.publish_purchase(
        scenario_id="scenario:production-owner:one",
        correlation_id="corr:production-owner:one",
        owners=_purchase_owners(calls),
        published_at=NOW,
    )
    router = FinalDecisionReviewProductionOwnerCallableRouterV1(store=store)
    provider = build_existing_purchase_provider(router.purchase_owners())
    bundle = provider(_request())
    assert bundle.scenario_id == "scenario:production-owner:one"
    assert bundle.correlation_id == "corr:production-owner:one"
    assert len(bundle.purchase_previews) == 1
    assert bundle.sell_previews == ()
    assert store.active_pin_count(checked_at=NOW) == 0
    assert calls == {
        "decision": 1,
        "intent": 1,
        "capacity": 1,
        "risk": 1,
        "preview": 1,
    }


def test_wrong_correlation_fails_before_any_owner_call() -> None:
    calls = {"decision": 0, "intent": 0, "capacity": 0, "risk": 0, "preview": 0}
    store = FinalDecisionReviewProductionOwnerCallableStoreV1()
    store.publish_purchase(
        scenario_id="scenario:production-owner:one",
        correlation_id="corr:production-owner:one",
        owners=_purchase_owners(calls),
        published_at=NOW,
    )
    router = FinalDecisionReviewProductionOwnerCallableRouterV1(store=store)
    provider = build_existing_purchase_provider(router.purchase_owners())
    with pytest.raises(
        FinalDecisionReviewExistingCalculatorProviderError,
        match="FINAL_DECISION_REVIEW_EXISTING_OWNER_CALL_FAILED",
    ):
        provider(_request(correlation_id="corr:production-owner:other"))
    assert all(value == 0 for value in calls.values())


def test_registration_uses_fixed_ids_without_owner_or_invocation_calls() -> None:
    invocation = _UnusedInvocation()
    registry = FinalDecisionReviewCalculatorProviderRegistryV1(
        invocation=invocation,
    )
    store = FinalDecisionReviewProductionOwnerCallableStoreV1()
    registration = register_final_decision_review_production_owner_callables(
        registry=registry,
        store=store,
    )
    assert registration.purchase_provider_id == PURCHASE_PROVIDER_ID
    assert registration.sell_provider_id == SELL_PROVIDER_ID
    assert registration.registered_provider_count == 2
    assert registration.startup_owner_call_performed is False
    assert registration.broker_write_called is False
    assert registration.trade_authorized is False
    assert registration.order_created is False
    assert registration.trading_methods is False
    assert store.active_bundle_count() == 0
    assert invocation.calls == 0
    assert store.active_pin_count() == 0


def test_invocation_pin_prevents_owner_mix_after_lru_eviction() -> None:
    original_calls = {
        "decision": 0,
        "intent": 0,
        "capacity": 0,
        "risk": 0,
        "preview": 0,
    }
    replacement_calls = dict(original_calls)
    unrelated_calls = dict(original_calls)
    store = FinalDecisionReviewProductionOwnerCallableStoreV1(capacity=1)
    store.publish_purchase(
        scenario_id="scenario:production-owner:one",
        correlation_id="corr:production-owner:one",
        owners=_purchase_owners(original_calls),
        published_at=NOW,
    )
    routed = FinalDecisionReviewProductionOwnerCallableRouterV1(
        store=store,
    ).purchase_owners()
    request = _request()

    routed.common.decision(request)
    assert store.active_pin_count(checked_at=NOW) == 1

    store.publish_purchase(
        scenario_id="scenario:production-owner:other",
        correlation_id="corr:production-owner:other",
        owners=_purchase_owners(unrelated_calls),
        published_at=NOW,
    )
    store.publish_purchase(
        scenario_id="scenario:production-owner:one",
        correlation_id="corr:production-owner:one",
        owners=_purchase_owners(replacement_calls),
        published_at=NOW,
    )

    routed.common.intent(request)
    tuple(routed.previews(request))
    assert original_calls["decision"] == 1
    assert original_calls["intent"] == 1
    assert original_calls["preview"] == 1
    assert all(value == 0 for value in replacement_calls.values())
    assert all(value == 0 for value in unrelated_calls.values())
    assert store.active_pin_count(checked_at=NOW) == 0


def test_invocation_pin_rejects_timestamp_rebinding() -> None:
    calls = {"decision": 0, "intent": 0, "capacity": 0, "risk": 0, "preview": 0}
    store = FinalDecisionReviewProductionOwnerCallableStoreV1()
    store.publish_purchase(
        scenario_id="scenario:production-owner:one",
        correlation_id="corr:production-owner:one",
        owners=_purchase_owners(calls),
        published_at=NOW,
    )
    request = _request()
    assert store.load_for_request(request, checked_at=NOW) is not None
    rebound = request.model_copy(
        update={"invoked_at": NOW + timedelta(seconds=1)},
    )
    with pytest.raises(
        FinalDecisionReviewProductionOwnerCallableError,
        match="FINAL_DECISION_REVIEW_PRODUCTION_OWNER_PIN_MISMATCH",
    ):
        store.load_for_request(rebound, checked_at=NOW)
    assert store.release_for_request(request) is True
    assert all(value == 0 for value in calls.values())


def test_purchase_and_sell_publications_are_direction_isolated() -> None:
    purchase_calls = {
        "decision": 0,
        "intent": 0,
        "capacity": 0,
        "risk": 0,
        "preview": 0,
    }
    sell_calls = dict(purchase_calls)
    store = FinalDecisionReviewProductionOwnerCallableStoreV1()
    store.publish_purchase(
        scenario_id="scenario:production-owner:one",
        correlation_id="corr:production-owner:one",
        owners=_purchase_owners(purchase_calls),
        published_at=NOW,
    )
    store.publish_sell(
        scenario_id="scenario:production-owner:one",
        correlation_id="corr:production-owner:one",
        owners=_sell_owners(sell_calls),
        published_at=NOW,
    )
    purchase = store.load_for_request(_request(), checked_at=NOW)
    sell = store.load_for_request(
        _request(operation=ApprovedCalculatorOperation.SELL_REVIEW),
        checked_at=NOW,
    )
    assert purchase is not None and purchase.purchase is not None
    assert purchase.sell is None
    assert sell is not None and sell.sell is not None
    assert sell.purchase is None
    assert store.active_pin_count(checked_at=NOW) == 2
    assert store.release_for_request(_request()) is True
    assert (
        store.release_for_request(
            _request(operation=ApprovedCalculatorOperation.SELL_REVIEW),
        )
        is True
    )
    assert store.active_pin_count(checked_at=NOW) == 0
    assert all(value == 0 for value in purchase_calls.values())
    assert all(value == 0 for value in sell_calls.values())


def test_owner_routing_has_no_http_or_broker_write_surface() -> None:
    source = (
        Path("omni_cio/release/final_decision_review_production_owner_callables_v1.py")
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
