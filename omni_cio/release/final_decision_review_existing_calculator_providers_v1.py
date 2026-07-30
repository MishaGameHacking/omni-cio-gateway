from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone

from omni_cio.contracts.v1.capacity import CapacityAssessmentV1
from omni_cio.contracts.v1.decision import DecisionSetV1
from omni_cio.contracts.v1.decision_capacity_intent import (
    CapacityIntentDecisionGateRequestV1,
)
from omni_cio.contracts.v1.final_decision_review_approved_invocation import (
    ApprovedCalculatorInvocationRequestV1,
    ApprovedCalculatorOperation,
)
from omni_cio.contracts.v1.pretrade import PreTradePreviewV1
from omni_cio.contracts.v1.risk import RiskPolicyEvaluationV1
from omni_cio.contracts.v1.sell_pretrade import SellPreTradePreviewV1
from omni_cio.release.final_decision_review_calculator_provider_registry_v1 import (
    ApprovedCalculatorProviderBundleV1,
    FinalDecisionReviewCalculatorProviderRegistryV1,
)


PURCHASE_PROVIDER_ID = "provider:existing:purchase-review"
SELL_PROVIDER_ID = "provider:existing:sell-review"


class FinalDecisionReviewExistingCalculatorProviderError(ValueError):
    """Existing read-only calculator outputs cannot form an approved bundle."""


DecisionOwnerV1 = Callable[
    [ApprovedCalculatorInvocationRequestV1],
    DecisionSetV1,
]
IntentOwnerV1 = Callable[
    [ApprovedCalculatorInvocationRequestV1],
    CapacityIntentDecisionGateRequestV1,
]
CapacityOwnerV1 = Callable[
    [ApprovedCalculatorInvocationRequestV1],
    Iterable[CapacityAssessmentV1],
]
ProFormaRiskOwnerV1 = Callable[
    [ApprovedCalculatorInvocationRequestV1],
    RiskPolicyEvaluationV1,
]
PurchasePreviewOwnerV1 = Callable[
    [ApprovedCalculatorInvocationRequestV1],
    Iterable[PreTradePreviewV1],
]
SellPreviewOwnerV1 = Callable[
    [ApprovedCalculatorInvocationRequestV1],
    Iterable[SellPreTradePreviewV1],
]


@dataclass(frozen=True, slots=True)
class ApprovedCalculatorCommonOwnersV1:
    decision: DecisionOwnerV1
    intent: IntentOwnerV1
    capacity: CapacityOwnerV1
    pro_forma_risk: ProFormaRiskOwnerV1

    def __post_init__(self) -> None:
        owners = (self.decision, self.intent, self.capacity, self.pro_forma_risk)
        if any(not callable(owner) for owner in owners):
            raise FinalDecisionReviewExistingCalculatorProviderError(
                "FINAL_DECISION_REVIEW_EXISTING_OWNER_NOT_CALLABLE"
            )


@dataclass(frozen=True, slots=True)
class ApprovedPurchaseCalculatorOwnersV1:
    common: ApprovedCalculatorCommonOwnersV1
    previews: PurchasePreviewOwnerV1

    def __post_init__(self) -> None:
        if not isinstance(self.common, ApprovedCalculatorCommonOwnersV1):
            raise FinalDecisionReviewExistingCalculatorProviderError(
                "FINAL_DECISION_REVIEW_EXISTING_COMMON_OWNERS_TYPE_INVALID"
            )
        if not callable(self.previews):
            raise FinalDecisionReviewExistingCalculatorProviderError(
                "FINAL_DECISION_REVIEW_EXISTING_PURCHASE_OWNER_NOT_CALLABLE"
            )


@dataclass(frozen=True, slots=True)
class ApprovedSellCalculatorOwnersV1:
    common: ApprovedCalculatorCommonOwnersV1
    previews: SellPreviewOwnerV1

    def __post_init__(self) -> None:
        if not isinstance(self.common, ApprovedCalculatorCommonOwnersV1):
            raise FinalDecisionReviewExistingCalculatorProviderError(
                "FINAL_DECISION_REVIEW_EXISTING_COMMON_OWNERS_TYPE_INVALID"
            )
        if not callable(self.previews):
            raise FinalDecisionReviewExistingCalculatorProviderError(
                "FINAL_DECISION_REVIEW_EXISTING_SELL_OWNER_NOT_CALLABLE"
            )


def _require_request(
    value: ApprovedCalculatorInvocationRequestV1,
    *,
    operation: ApprovedCalculatorOperation,
) -> ApprovedCalculatorInvocationRequestV1:
    if not isinstance(value, ApprovedCalculatorInvocationRequestV1):
        raise FinalDecisionReviewExistingCalculatorProviderError(
            "FINAL_DECISION_REVIEW_EXISTING_REQUEST_TYPE_INVALID"
        )
    if value.operation is not operation:
        raise FinalDecisionReviewExistingCalculatorProviderError(
            "FINAL_DECISION_REVIEW_EXISTING_OPERATION_MISMATCH"
        )
    return value


def _build_common(
    request: ApprovedCalculatorInvocationRequestV1,
    owners: ApprovedCalculatorCommonOwnersV1,
) -> tuple[
    DecisionSetV1,
    CapacityIntentDecisionGateRequestV1,
    tuple[CapacityAssessmentV1, ...],
    RiskPolicyEvaluationV1,
    datetime,
]:
    try:
        decision = owners.decision(request)
        intent = owners.intent(request)
        capacity = tuple(owners.capacity(request))
        risk = owners.pro_forma_risk(request)
    except Exception as exc:
        raise FinalDecisionReviewExistingCalculatorProviderError(
            "FINAL_DECISION_REVIEW_EXISTING_OWNER_CALL_FAILED"
        ) from exc
    if not isinstance(decision, DecisionSetV1):
        raise FinalDecisionReviewExistingCalculatorProviderError(
            "FINAL_DECISION_REVIEW_EXISTING_DECISION_TYPE_INVALID"
        )
    if not isinstance(intent, CapacityIntentDecisionGateRequestV1):
        raise FinalDecisionReviewExistingCalculatorProviderError(
            "FINAL_DECISION_REVIEW_EXISTING_INTENT_TYPE_INVALID"
        )
    if not capacity or any(not isinstance(row, CapacityAssessmentV1) for row in capacity):
        raise FinalDecisionReviewExistingCalculatorProviderError(
            "FINAL_DECISION_REVIEW_EXISTING_CAPACITY_TYPE_INVALID"
        )
    if not isinstance(risk, RiskPolicyEvaluationV1):
        raise FinalDecisionReviewExistingCalculatorProviderError(
            "FINAL_DECISION_REVIEW_EXISTING_PRO_FORMA_TYPE_INVALID"
        )
    built_at = risk.metadata.retrieved_at
    if built_at.tzinfo is None or built_at.utcoffset() is None:
        raise FinalDecisionReviewExistingCalculatorProviderError(
            "FINAL_DECISION_REVIEW_EXISTING_PRO_FORMA_TIMESTAMP_INVALID"
        )
    return decision, intent, capacity, risk, built_at.astimezone(timezone.utc)


def build_existing_purchase_provider(
    owners: ApprovedPurchaseCalculatorOwnersV1,
) -> Callable[
    [ApprovedCalculatorInvocationRequestV1],
    ApprovedCalculatorProviderBundleV1,
]:
    if not isinstance(owners, ApprovedPurchaseCalculatorOwnersV1):
        raise FinalDecisionReviewExistingCalculatorProviderError(
            "FINAL_DECISION_REVIEW_EXISTING_PURCHASE_OWNERS_TYPE_INVALID"
        )

    def provider(
        request: ApprovedCalculatorInvocationRequestV1,
    ) -> ApprovedCalculatorProviderBundleV1:
        approved = _require_request(
            request,
            operation=ApprovedCalculatorOperation.PURCHASE_REVIEW,
        )
        decision, intent, capacity, risk, built_at = _build_common(
            approved,
            owners.common,
        )
        try:
            previews = tuple(owners.previews(approved))
        except Exception as exc:
            raise FinalDecisionReviewExistingCalculatorProviderError(
                "FINAL_DECISION_REVIEW_EXISTING_PURCHASE_OWNER_CALL_FAILED"
            ) from exc
        if not previews or any(not isinstance(row, PreTradePreviewV1) for row in previews):
            raise FinalDecisionReviewExistingCalculatorProviderError(
                "FINAL_DECISION_REVIEW_EXISTING_PURCHASE_PREVIEW_TYPE_INVALID"
            )
        return ApprovedCalculatorProviderBundleV1(
            scenario_id=approved.scenario_id,
            correlation_id=approved.correlation_id,
            built_at=built_at,
            decision=decision,
            intent_request=intent,
            capacity_assessments=capacity,
            purchase_previews=previews,
            sell_previews=(),
            pro_forma_risk=risk,
        )

    return provider


def build_existing_sell_provider(
    owners: ApprovedSellCalculatorOwnersV1,
) -> Callable[
    [ApprovedCalculatorInvocationRequestV1],
    ApprovedCalculatorProviderBundleV1,
]:
    if not isinstance(owners, ApprovedSellCalculatorOwnersV1):
        raise FinalDecisionReviewExistingCalculatorProviderError(
            "FINAL_DECISION_REVIEW_EXISTING_SELL_OWNERS_TYPE_INVALID"
        )

    def provider(
        request: ApprovedCalculatorInvocationRequestV1,
    ) -> ApprovedCalculatorProviderBundleV1:
        approved = _require_request(
            request,
            operation=ApprovedCalculatorOperation.SELL_REVIEW,
        )
        decision, intent, capacity, risk, built_at = _build_common(
            approved,
            owners.common,
        )
        try:
            previews = tuple(owners.previews(approved))
        except Exception as exc:
            raise FinalDecisionReviewExistingCalculatorProviderError(
                "FINAL_DECISION_REVIEW_EXISTING_SELL_OWNER_CALL_FAILED"
            ) from exc
        if not previews or any(
            not isinstance(row, SellPreTradePreviewV1) for row in previews
        ):
            raise FinalDecisionReviewExistingCalculatorProviderError(
                "FINAL_DECISION_REVIEW_EXISTING_SELL_PREVIEW_TYPE_INVALID"
            )
        return ApprovedCalculatorProviderBundleV1(
            scenario_id=approved.scenario_id,
            correlation_id=approved.correlation_id,
            built_at=built_at,
            decision=decision,
            intent_request=intent,
            capacity_assessments=capacity,
            purchase_previews=(),
            sell_previews=previews,
            pro_forma_risk=risk,
        )

    return provider


def register_existing_calculator_providers(
    *,
    registry: FinalDecisionReviewCalculatorProviderRegistryV1,
    purchase: ApprovedPurchaseCalculatorOwnersV1 | None = None,
    sell: ApprovedSellCalculatorOwnersV1 | None = None,
) -> None:
    if not isinstance(registry, FinalDecisionReviewCalculatorProviderRegistryV1):
        raise FinalDecisionReviewExistingCalculatorProviderError(
            "FINAL_DECISION_REVIEW_EXISTING_REGISTRY_TYPE_INVALID"
        )
    if purchase is None and sell is None:
        raise FinalDecisionReviewExistingCalculatorProviderError(
            "FINAL_DECISION_REVIEW_EXISTING_NO_PROVIDERS"
        )
    if purchase is not None:
        registry.register(
            provider_id=PURCHASE_PROVIDER_ID,
            operation=ApprovedCalculatorOperation.PURCHASE_REVIEW,
            provider=build_existing_purchase_provider(purchase),
        )
    if sell is not None:
        registry.register(
            provider_id=SELL_PROVIDER_ID,
            operation=ApprovedCalculatorOperation.SELL_REVIEW,
            provider=build_existing_sell_provider(sell),
        )
