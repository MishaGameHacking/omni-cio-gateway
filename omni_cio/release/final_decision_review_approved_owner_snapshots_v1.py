from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import TYPE_CHECKING

from omni_cio.contracts.v1.capacity import CapacityAssessmentV1, OrderSide
from omni_cio.contracts.v1.decision import DecisionSetV1
from omni_cio.contracts.v1.decision_capacity_intent import (
    CapacityIntentDecisionGateRequestV1,
)
from omni_cio.contracts.v1.decision_pro_forma_risk_binding import (
    ProFormaRiskScenarioV1,
)
from omni_cio.contracts.v1.final_decision_review_approved_invocation import (
    ApprovedCalculatorInvocationRequestV1,
    ApprovedCalculatorOperation,
)
from omni_cio.contracts.v1.final_decision_review_trusted_scenario import (
    TrustedScenarioPublicationResultV1,
)
from omni_cio.contracts.v1.pretrade import PreTradePreviewV1
from omni_cio.contracts.v1.risk import RiskPolicyEvaluationV1
from omni_cio.contracts.v1.sell_pretrade import SellPreTradePreviewV1
from omni_cio.decision.pro_forma_risk_binding_v1 import (
    build_pro_forma_risk_scenario,
)
from omni_cio.release.final_decision_review_trusted_owner_composition_v1 import (
    FinalDecisionReviewTrustedCommonOwnerPortsV1,
    FinalDecisionReviewTrustedPurchaseOwnerPortsV1,
    FinalDecisionReviewTrustedSellOwnerPortsV1,
)

if TYPE_CHECKING:
    from omni_cio.release.final_decision_review_approved_owner_acquisition_v1 import (
        FinalDecisionReviewApprovedServerContextV1,
    )


class FinalDecisionReviewApprovedOwnerSnapshotError(ValueError):
    """Exact calculator snapshots cannot be retained or selected safely."""


@dataclass(frozen=True, slots=True)
class FinalDecisionReviewApprovedOwnerSnapshotCaptureV1:
    scenario_id: str
    correlation_id: str
    operation: ApprovedCalculatorOperation
    captured_at: datetime
    expires_at: datetime
    source_replaced: bool
    source_evicted: bool
    active_bundle_count: int
    internal_only: bool = True
    raw_action_payload_accepted: bool = False
    credentials_present: bool = False
    full_account_identifier_present: bool = False
    financial_snapshots_retained: bool = True
    broker_write_called: bool = False
    trade_authorized: bool = False
    order_created: bool = False
    execution_ready: bool = False
    trading_methods: bool = False


@dataclass(frozen=True, slots=True)
class FinalDecisionReviewApprovedOwnerSnapshotBundleV1:
    request: ApprovedCalculatorInvocationRequestV1
    account_masked_id: str
    captured_at: datetime
    expires_at: datetime
    purchase_owners: FinalDecisionReviewTrustedPurchaseOwnerPortsV1 | None = None
    sell_owners: FinalDecisionReviewTrustedSellOwnerPortsV1 | None = None
    internal_only: bool = True
    raw_action_payload_accepted: bool = False
    credentials_present: bool = False
    full_account_identifier_present: bool = False
    financial_snapshots_retained: bool = True
    broker_write_called: bool = False
    trade_authorized: bool = False
    order_created: bool = False
    execution_ready: bool = False
    trading_methods: bool = False

    def __post_init__(self) -> None:
        purchase_selected = self.purchase_owners is not None
        sell_selected = self.sell_owners is not None
        if purchase_selected == sell_selected:
            raise FinalDecisionReviewApprovedOwnerSnapshotError(
                "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_DIRECTION_INVALID"
            )
        if (
            self.request.operation is ApprovedCalculatorOperation.PURCHASE_REVIEW
        ) != purchase_selected:
            raise FinalDecisionReviewApprovedOwnerSnapshotError(
                "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_OPERATION_MISMATCH"
            )
        if self.expires_at <= self.captured_at:
            raise FinalDecisionReviewApprovedOwnerSnapshotError(
                "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_EXPIRY_INVALID"
            )


OwnerSnapshotKeyV1 = tuple[
    str,
    str,
    ApprovedCalculatorOperation,
    str,
]


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if (
        not isinstance(result, datetime)
        or result.tzinfo is None
        or result.utcoffset() is None
    ):
        raise FinalDecisionReviewApprovedOwnerSnapshotError(
            "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_TIMESTAMP_INVALID"
        )
    return result.astimezone(timezone.utc)


def _key(
    *,
    scenario_id: str,
    correlation_id: str,
    operation: ApprovedCalculatorOperation,
    account_masked_id: str,
) -> OwnerSnapshotKeyV1:
    return (scenario_id, correlation_id, operation, account_masked_id)


def _require_exact_request(
    actual: ApprovedCalculatorInvocationRequestV1,
    expected: ApprovedCalculatorInvocationRequestV1,
) -> None:
    if actual != expected:
        raise FinalDecisionReviewApprovedOwnerSnapshotError(
            "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_REQUEST_MISMATCH"
        )


def _validate_common(
    *,
    request: ApprovedCalculatorInvocationRequestV1,
    decision: DecisionSetV1,
    intent_request: CapacityIntentDecisionGateRequestV1,
    capacity_assessments: tuple[CapacityAssessmentV1, ...],
    pro_forma_risk: RiskPolicyEvaluationV1,
    publication: TrustedScenarioPublicationResultV1,
    direction: OrderSide,
) -> None:
    if not isinstance(request, ApprovedCalculatorInvocationRequestV1):
        raise FinalDecisionReviewApprovedOwnerSnapshotError(
            "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_REQUEST_INVALID"
        )
    if not isinstance(decision, DecisionSetV1):
        raise FinalDecisionReviewApprovedOwnerSnapshotError(
            "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_DECISION_INVALID"
        )
    if not isinstance(intent_request, CapacityIntentDecisionGateRequestV1):
        raise FinalDecisionReviewApprovedOwnerSnapshotError(
            "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_INTENT_INVALID"
        )
    if not capacity_assessments or not all(
        isinstance(row, CapacityAssessmentV1) for row in capacity_assessments
    ):
        raise FinalDecisionReviewApprovedOwnerSnapshotError(
            "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_CAPACITY_INVALID"
        )
    if not isinstance(pro_forma_risk, RiskPolicyEvaluationV1):
        raise FinalDecisionReviewApprovedOwnerSnapshotError(
            "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_RISK_INVALID"
        )
    if not isinstance(publication, TrustedScenarioPublicationResultV1):
        raise FinalDecisionReviewApprovedOwnerSnapshotError(
            "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_PUBLICATION_INVALID"
        )
    expected_operation = (
        ApprovedCalculatorOperation.PURCHASE_REVIEW
        if direction is OrderSide.BUY
        else ApprovedCalculatorOperation.SELL_REVIEW
    )
    exact = (
        request.operation is expected_operation
        and publication.scenario_id == request.scenario_id
        and publication.direction is direction
        and publication.account == decision.metadata.account
        and intent_request.decision == decision.metadata
        and intent_request.direction is direction
        and pro_forma_risk.metadata.account == decision.metadata.account
        and publication.pro_forma_retrieved_at
        == pro_forma_risk.metadata.retrieved_at
    )
    if not exact:
        raise FinalDecisionReviewApprovedOwnerSnapshotError(
            "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_IDENTITY_MISMATCH"
        )


def _scenario(
    *,
    request: ApprovedCalculatorInvocationRequestV1,
    decision: DecisionSetV1,
    intent_request: CapacityIntentDecisionGateRequestV1,
    pro_forma_risk: RiskPolicyEvaluationV1,
    direction: OrderSide,
    publication: TrustedScenarioPublicationResultV1,
) -> ProFormaRiskScenarioV1:
    return build_pro_forma_risk_scenario(
        scenario_id=request.scenario_id,
        account=decision.metadata.account,
        requested_option_id=intent_request.requested_option_id,
        direction=direction,
        capacity_requests=intent_request.requests,
        pro_forma_risk=pro_forma_risk,
        generated_at=publication.published_at,
    )


def _purchase_ports(
    *,
    request: ApprovedCalculatorInvocationRequestV1,
    decision: DecisionSetV1,
    intent_request: CapacityIntentDecisionGateRequestV1,
    capacity_assessments: tuple[CapacityAssessmentV1, ...],
    scenario: ProFormaRiskScenarioV1,
    previews: tuple[PreTradePreviewV1, ...],
) -> FinalDecisionReviewTrustedPurchaseOwnerPortsV1:
    def decision_owner(
        actual: ApprovedCalculatorInvocationRequestV1,
    ) -> DecisionSetV1:
        _require_exact_request(actual, request)
        return decision

    def intent_owner(
        actual: ApprovedCalculatorInvocationRequestV1,
    ) -> CapacityIntentDecisionGateRequestV1:
        _require_exact_request(actual, request)
        return intent_request

    def capacity_owner(
        actual: ApprovedCalculatorInvocationRequestV1,
    ) -> tuple[CapacityAssessmentV1, ...]:
        _require_exact_request(actual, request)
        return capacity_assessments

    def scenario_owner(
        actual: ApprovedCalculatorInvocationRequestV1,
    ) -> ProFormaRiskScenarioV1:
        _require_exact_request(actual, request)
        return scenario

    def preview_owner(
        actual: ApprovedCalculatorInvocationRequestV1,
    ) -> tuple[PreTradePreviewV1, ...]:
        _require_exact_request(actual, request)
        return previews

    return FinalDecisionReviewTrustedPurchaseOwnerPortsV1(
        common=FinalDecisionReviewTrustedCommonOwnerPortsV1(
            decision=decision_owner,
            intent=intent_owner,
            capacity=capacity_owner,
            pro_forma_scenario=scenario_owner,
        ),
        previews=preview_owner,
    )


def _sell_ports(
    *,
    request: ApprovedCalculatorInvocationRequestV1,
    decision: DecisionSetV1,
    intent_request: CapacityIntentDecisionGateRequestV1,
    capacity_assessments: tuple[CapacityAssessmentV1, ...],
    scenario: ProFormaRiskScenarioV1,
    previews: tuple[SellPreTradePreviewV1, ...],
) -> FinalDecisionReviewTrustedSellOwnerPortsV1:
    def decision_owner(
        actual: ApprovedCalculatorInvocationRequestV1,
    ) -> DecisionSetV1:
        _require_exact_request(actual, request)
        return decision

    def intent_owner(
        actual: ApprovedCalculatorInvocationRequestV1,
    ) -> CapacityIntentDecisionGateRequestV1:
        _require_exact_request(actual, request)
        return intent_request

    def capacity_owner(
        actual: ApprovedCalculatorInvocationRequestV1,
    ) -> tuple[CapacityAssessmentV1, ...]:
        _require_exact_request(actual, request)
        return capacity_assessments

    def scenario_owner(
        actual: ApprovedCalculatorInvocationRequestV1,
    ) -> ProFormaRiskScenarioV1:
        _require_exact_request(actual, request)
        return scenario

    def preview_owner(
        actual: ApprovedCalculatorInvocationRequestV1,
    ) -> tuple[SellPreTradePreviewV1, ...]:
        _require_exact_request(actual, request)
        return previews

    return FinalDecisionReviewTrustedSellOwnerPortsV1(
        common=FinalDecisionReviewTrustedCommonOwnerPortsV1(
            decision=decision_owner,
            intent=intent_owner,
            capacity=capacity_owner,
            pro_forma_scenario=scenario_owner,
        ),
        previews=preview_owner,
    )


class FinalDecisionReviewApprovedOwnerSnapshotStoreV1:
    """Bounded exact owner snapshots captured only after approved calculation."""

    def __init__(self, *, ttl_seconds: int = 300, capacity: int = 64) -> None:
        if not 1 <= ttl_seconds <= 3_600:
            raise FinalDecisionReviewApprovedOwnerSnapshotError(
                "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_TTL_INVALID"
            )
        if not 1 <= capacity <= 1_024:
            raise FinalDecisionReviewApprovedOwnerSnapshotError(
                "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_CAPACITY_LIMIT_INVALID"
            )
        self._ttl = timedelta(seconds=ttl_seconds)
        self._capacity = capacity
        self._bundles: OrderedDict[
            OwnerSnapshotKeyV1,
            FinalDecisionReviewApprovedOwnerSnapshotBundleV1,
        ] = OrderedDict()
        self._lock = RLock()

    @property
    def ttl_seconds(self) -> int:
        return int(self._ttl.total_seconds())

    @property
    def capacity(self) -> int:
        return self._capacity

    def _prune(self, checked_at: datetime) -> None:
        expired = [
            key
            for key, bundle in self._bundles.items()
            if bundle.expires_at <= checked_at
        ]
        for key in expired:
            self._bundles.pop(key, None)

    def _publish(
        self,
        *,
        bundle: FinalDecisionReviewApprovedOwnerSnapshotBundleV1,
    ) -> FinalDecisionReviewApprovedOwnerSnapshotCaptureV1:
        key = _key(
            scenario_id=bundle.request.scenario_id,
            correlation_id=bundle.request.correlation_id,
            operation=bundle.request.operation,
            account_masked_id=bundle.account_masked_id,
        )
        with self._lock:
            self._prune(bundle.captured_at)
            replaced = key in self._bundles
            self._bundles[key] = bundle
            self._bundles.move_to_end(key)
            evicted = False
            while len(self._bundles) > self._capacity:
                self._bundles.popitem(last=False)
                evicted = True
            active = len(self._bundles)
        return FinalDecisionReviewApprovedOwnerSnapshotCaptureV1(
            scenario_id=bundle.request.scenario_id,
            correlation_id=bundle.request.correlation_id,
            operation=bundle.request.operation,
            captured_at=bundle.captured_at,
            expires_at=bundle.expires_at,
            source_replaced=replaced,
            source_evicted=evicted,
            active_bundle_count=active,
        )

    def capture_purchase(
        self,
        *,
        request: ApprovedCalculatorInvocationRequestV1,
        decision: DecisionSetV1,
        intent_request: CapacityIntentDecisionGateRequestV1,
        capacity_assessments: tuple[CapacityAssessmentV1, ...],
        purchase_previews: tuple[PreTradePreviewV1, ...],
        pro_forma_risk: RiskPolicyEvaluationV1,
        publication: TrustedScenarioPublicationResultV1,
        captured_at: datetime | None = None,
    ) -> FinalDecisionReviewApprovedOwnerSnapshotCaptureV1:
        _validate_common(
            request=request,
            decision=decision,
            intent_request=intent_request,
            capacity_assessments=capacity_assessments,
            pro_forma_risk=pro_forma_risk,
            publication=publication,
            direction=OrderSide.BUY,
        )
        if not purchase_previews or not all(
            isinstance(row, PreTradePreviewV1) for row in purchase_previews
        ):
            raise FinalDecisionReviewApprovedOwnerSnapshotError(
                "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_PURCHASE_PREVIEWS_INVALID"
            )
        now = _aware_utc(captured_at or publication.published_at)
        if now != publication.published_at:
            raise FinalDecisionReviewApprovedOwnerSnapshotError(
                "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_CAPTURE_TIME_MISMATCH"
            )
        scenario = _scenario(
            request=request,
            decision=decision,
            intent_request=intent_request,
            pro_forma_risk=pro_forma_risk,
            direction=OrderSide.BUY,
            publication=publication,
        )
        return self._publish(
            bundle=FinalDecisionReviewApprovedOwnerSnapshotBundleV1(
                request=request,
                account_masked_id=decision.metadata.account.masked_id,
                captured_at=now,
                expires_at=now + self._ttl,
                purchase_owners=_purchase_ports(
                    request=request,
                    decision=decision,
                    intent_request=intent_request,
                    capacity_assessments=capacity_assessments,
                    scenario=scenario,
                    previews=purchase_previews,
                ),
            )
        )

    def capture_sell(
        self,
        *,
        request: ApprovedCalculatorInvocationRequestV1,
        decision: DecisionSetV1,
        intent_request: CapacityIntentDecisionGateRequestV1,
        capacity_assessments: tuple[CapacityAssessmentV1, ...],
        sell_previews: tuple[SellPreTradePreviewV1, ...],
        pro_forma_risk: RiskPolicyEvaluationV1,
        publication: TrustedScenarioPublicationResultV1,
        captured_at: datetime | None = None,
    ) -> FinalDecisionReviewApprovedOwnerSnapshotCaptureV1:
        _validate_common(
            request=request,
            decision=decision,
            intent_request=intent_request,
            capacity_assessments=capacity_assessments,
            pro_forma_risk=pro_forma_risk,
            publication=publication,
            direction=OrderSide.SELL,
        )
        if not sell_previews or not all(
            isinstance(row, SellPreTradePreviewV1) for row in sell_previews
        ):
            raise FinalDecisionReviewApprovedOwnerSnapshotError(
                "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_SELL_PREVIEWS_INVALID"
            )
        now = _aware_utc(captured_at or publication.published_at)
        if now != publication.published_at:
            raise FinalDecisionReviewApprovedOwnerSnapshotError(
                "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_CAPTURE_TIME_MISMATCH"
            )
        scenario = _scenario(
            request=request,
            decision=decision,
            intent_request=intent_request,
            pro_forma_risk=pro_forma_risk,
            direction=OrderSide.SELL,
            publication=publication,
        )
        return self._publish(
            bundle=FinalDecisionReviewApprovedOwnerSnapshotBundleV1(
                request=request,
                account_masked_id=decision.metadata.account.masked_id,
                captured_at=now,
                expires_at=now + self._ttl,
                sell_owners=_sell_ports(
                    request=request,
                    decision=decision,
                    intent_request=intent_request,
                    capacity_assessments=capacity_assessments,
                    scenario=scenario,
                    previews=sell_previews,
                ),
            )
        )

    def select(
        self,
        context: FinalDecisionReviewApprovedServerContextV1,
        *,
        checked_at: datetime | None = None,
    ) -> FinalDecisionReviewApprovedOwnerSnapshotBundleV1 | None:
        from omni_cio.release.final_decision_review_approved_owner_acquisition_v1 import (
            FinalDecisionReviewApprovedServerContextV1,
        )

        if not isinstance(context, FinalDecisionReviewApprovedServerContextV1):
            raise FinalDecisionReviewApprovedOwnerSnapshotError(
                "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_CONTEXT_INVALID"
            )
        now = _aware_utc(checked_at or context.generated_at)
        key = _key(
            scenario_id=context.scenario_id,
            correlation_id=context.correlation_id,
            operation=context.operation,
            account_masked_id=context.account.masked_id,
        )
        with self._lock:
            self._prune(now)
            bundle = self._bundles.get(key)
            if bundle is None:
                return None
            self._bundles.move_to_end(key)
            return bundle

    def active_bundle_count(self, *, checked_at: datetime | None = None) -> int:
        now = _aware_utc(checked_at)
        with self._lock:
            self._prune(now)
            return len(self._bundles)

    def clear(self) -> None:
        with self._lock:
            self._bundles.clear()
