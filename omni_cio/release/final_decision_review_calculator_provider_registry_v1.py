from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import re
from threading import RLock

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
    FinalDecisionReviewApprovedInvocationError,
    FinalDecisionReviewApprovedInvocationV1,
)


_SAFE_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{2,127}$")


class FinalDecisionReviewCalculatorProviderRegistryError(ValueError):
    """An approved calculator provider cannot be registered or invoked safely."""


@dataclass(frozen=True, slots=True)
class ApprovedCalculatorProviderBundleV1:
    scenario_id: str
    correlation_id: str
    built_at: datetime
    decision: DecisionSetV1
    intent_request: CapacityIntentDecisionGateRequestV1
    capacity_assessments: tuple[CapacityAssessmentV1, ...]
    purchase_previews: tuple[PreTradePreviewV1, ...]
    sell_previews: tuple[SellPreTradePreviewV1, ...]
    pro_forma_risk: RiskPolicyEvaluationV1

    def __post_init__(self) -> None:
        if not _SAFE_ID.fullmatch(self.scenario_id):
            raise FinalDecisionReviewCalculatorProviderRegistryError(
                "FINAL_DECISION_REVIEW_PROVIDER_SCENARIO_ID_INVALID"
            )
        if not _SAFE_ID.fullmatch(self.correlation_id):
            raise FinalDecisionReviewCalculatorProviderRegistryError(
                "FINAL_DECISION_REVIEW_PROVIDER_CORRELATION_ID_INVALID"
            )
        if self.built_at.tzinfo is None or self.built_at.utcoffset() is None:
            raise FinalDecisionReviewCalculatorProviderRegistryError(
                "FINAL_DECISION_REVIEW_PROVIDER_TIMESTAMP_MUST_BE_AWARE"
            )
        object.__setattr__(self, "built_at", self.built_at.astimezone(timezone.utc))
        if not isinstance(self.decision, DecisionSetV1):
            raise FinalDecisionReviewCalculatorProviderRegistryError(
                "FINAL_DECISION_REVIEW_PROVIDER_DECISION_TYPE_INVALID"
            )
        if not isinstance(self.intent_request, CapacityIntentDecisionGateRequestV1):
            raise FinalDecisionReviewCalculatorProviderRegistryError(
                "FINAL_DECISION_REVIEW_PROVIDER_INTENT_TYPE_INVALID"
            )
        if not self.capacity_assessments or any(
            not isinstance(row, CapacityAssessmentV1)
            for row in self.capacity_assessments
        ):
            raise FinalDecisionReviewCalculatorProviderRegistryError(
                "FINAL_DECISION_REVIEW_PROVIDER_CAPACITY_TYPE_INVALID"
            )
        if any(not isinstance(row, PreTradePreviewV1) for row in self.purchase_previews):
            raise FinalDecisionReviewCalculatorProviderRegistryError(
                "FINAL_DECISION_REVIEW_PROVIDER_PURCHASE_PREVIEW_TYPE_INVALID"
            )
        if any(
            not isinstance(row, SellPreTradePreviewV1) for row in self.sell_previews
        ):
            raise FinalDecisionReviewCalculatorProviderRegistryError(
                "FINAL_DECISION_REVIEW_PROVIDER_SELL_PREVIEW_TYPE_INVALID"
            )
        if bool(self.purchase_previews) is bool(self.sell_previews):
            raise FinalDecisionReviewCalculatorProviderRegistryError(
                "FINAL_DECISION_REVIEW_PROVIDER_DIRECTION_AMBIGUOUS"
            )
        if not isinstance(self.pro_forma_risk, RiskPolicyEvaluationV1):
            raise FinalDecisionReviewCalculatorProviderRegistryError(
                "FINAL_DECISION_REVIEW_PROVIDER_PRO_FORMA_TYPE_INVALID"
            )
        risk_time = self.pro_forma_risk.metadata.retrieved_at
        if risk_time.tzinfo is None or risk_time.utcoffset() is None:
            raise FinalDecisionReviewCalculatorProviderRegistryError(
                "FINAL_DECISION_REVIEW_PROVIDER_RISK_TIMESTAMP_INVALID"
            )
        if self.built_at != risk_time.astimezone(timezone.utc):
            raise FinalDecisionReviewCalculatorProviderRegistryError(
                "FINAL_DECISION_REVIEW_PROVIDER_TIMESTAMP_MISMATCH"
            )


ApprovedCalculatorProviderV1 = Callable[
    [ApprovedCalculatorInvocationRequestV1],
    ApprovedCalculatorProviderBundleV1,
]


class FinalDecisionReviewCalculatorProviderRegistryV1:
    """Allowlisted internal provider registry over the PR-74 invocation boundary."""

    def __init__(
        self,
        *,
        invocation: FinalDecisionReviewApprovedInvocationV1,
        max_bundle_age_seconds: int = 300,
        future_tolerance_seconds: int = 30,
    ) -> None:
        if not isinstance(invocation, FinalDecisionReviewApprovedInvocationV1):
            raise FinalDecisionReviewCalculatorProviderRegistryError(
                "FINAL_DECISION_REVIEW_PROVIDER_INVOCATION_TYPE_INVALID"
            )
        if not 1 <= max_bundle_age_seconds <= 86_400:
            raise FinalDecisionReviewCalculatorProviderRegistryError(
                "FINAL_DECISION_REVIEW_PROVIDER_MAX_AGE_INVALID"
            )
        if not 0 <= future_tolerance_seconds <= 3_600:
            raise FinalDecisionReviewCalculatorProviderRegistryError(
                "FINAL_DECISION_REVIEW_PROVIDER_FUTURE_TOLERANCE_INVALID"
            )
        self._invocation = invocation
        self._max_bundle_age_seconds = max_bundle_age_seconds
        self._future_tolerance_seconds = future_tolerance_seconds
        self._providers: dict[
            tuple[str, ApprovedCalculatorOperation],
            ApprovedCalculatorProviderV1,
        ] = {}
        self._lock = RLock()

    @property
    def invocation(self) -> FinalDecisionReviewApprovedInvocationV1:
        return self._invocation

    def register(
        self,
        *,
        provider_id: str,
        operation: ApprovedCalculatorOperation,
        provider: ApprovedCalculatorProviderV1,
    ) -> None:
        if not _SAFE_ID.fullmatch(provider_id):
            raise FinalDecisionReviewCalculatorProviderRegistryError(
                "FINAL_DECISION_REVIEW_PROVIDER_ID_INVALID"
            )
        if not isinstance(operation, ApprovedCalculatorOperation):
            raise FinalDecisionReviewCalculatorProviderRegistryError(
                "FINAL_DECISION_REVIEW_PROVIDER_OPERATION_INVALID"
            )
        if not callable(provider):
            raise FinalDecisionReviewCalculatorProviderRegistryError(
                "FINAL_DECISION_REVIEW_PROVIDER_NOT_CALLABLE"
            )
        key = (provider_id, operation)
        with self._lock:
            if key in self._providers:
                raise FinalDecisionReviewCalculatorProviderRegistryError(
                    "FINAL_DECISION_REVIEW_PROVIDER_ALREADY_REGISTERED"
                )
            self._providers[key] = provider

    def invoke(
        self,
        *,
        provider_id: str,
        request: ApprovedCalculatorInvocationRequestV1,
        completed_at: datetime | None = None,
    ) -> ApprovedCalculatorInvocationResultV1:
        if not _SAFE_ID.fullmatch(provider_id):
            raise FinalDecisionReviewCalculatorProviderRegistryError(
                "FINAL_DECISION_REVIEW_PROVIDER_ID_INVALID"
            )
        if not isinstance(request, ApprovedCalculatorInvocationRequestV1):
            raise FinalDecisionReviewCalculatorProviderRegistryError(
                "FINAL_DECISION_REVIEW_PROVIDER_REQUEST_TYPE_INVALID"
            )
        with self._lock:
            provider = self._providers.get((provider_id, request.operation))
        if provider is None:
            raise FinalDecisionReviewCalculatorProviderRegistryError(
                "FINAL_DECISION_REVIEW_PROVIDER_NOT_REGISTERED"
            )
        try:
            bundle = provider(request)
        except Exception as exc:
            raise FinalDecisionReviewCalculatorProviderRegistryError(
                "FINAL_DECISION_REVIEW_PROVIDER_CALL_FAILED"
            ) from exc
        if not isinstance(bundle, ApprovedCalculatorProviderBundleV1):
            raise FinalDecisionReviewCalculatorProviderRegistryError(
                "FINAL_DECISION_REVIEW_PROVIDER_BUNDLE_TYPE_INVALID"
            )
        if bundle.scenario_id != request.scenario_id:
            raise FinalDecisionReviewCalculatorProviderRegistryError(
                "FINAL_DECISION_REVIEW_PROVIDER_SCENARIO_MISMATCH"
            )
        if bundle.correlation_id != request.correlation_id:
            raise FinalDecisionReviewCalculatorProviderRegistryError(
                "FINAL_DECISION_REVIEW_PROVIDER_CORRELATION_MISMATCH"
            )
        age_seconds = (request.invoked_at - bundle.built_at).total_seconds()
        if age_seconds > self._max_bundle_age_seconds:
            raise FinalDecisionReviewCalculatorProviderRegistryError(
                "FINAL_DECISION_REVIEW_PROVIDER_BUNDLE_STALE"
            )
        if age_seconds < -self._future_tolerance_seconds:
            raise FinalDecisionReviewCalculatorProviderRegistryError(
                "FINAL_DECISION_REVIEW_PROVIDER_BUNDLE_FROM_FUTURE"
            )
        if request.operation is ApprovedCalculatorOperation.PURCHASE_REVIEW:
            if not bundle.purchase_previews or bundle.sell_previews:
                raise FinalDecisionReviewCalculatorProviderRegistryError(
                    "FINAL_DECISION_REVIEW_PROVIDER_DIRECTION_MISMATCH"
                )
            try:
                return self._invocation.invoke_purchase(
                    request=request,
                    decision=bundle.decision,
                    intent_request=bundle.intent_request,
                    capacity_assessments=bundle.capacity_assessments,
                    previews=bundle.purchase_previews,
                    pro_forma_risk=bundle.pro_forma_risk,
                    completed_at=completed_at,
                )
            except FinalDecisionReviewApprovedInvocationError as exc:
                raise FinalDecisionReviewCalculatorProviderRegistryError(str(exc)) from exc
        if not bundle.sell_previews or bundle.purchase_previews:
            raise FinalDecisionReviewCalculatorProviderRegistryError(
                "FINAL_DECISION_REVIEW_PROVIDER_DIRECTION_MISMATCH"
            )
        try:
            return self._invocation.invoke_sell(
                request=request,
                decision=bundle.decision,
                intent_request=bundle.intent_request,
                capacity_assessments=bundle.capacity_assessments,
                previews=bundle.sell_previews,
                pro_forma_risk=bundle.pro_forma_risk,
                completed_at=completed_at,
            )
        except FinalDecisionReviewApprovedInvocationError as exc:
            raise FinalDecisionReviewCalculatorProviderRegistryError(str(exc)) from exc
