from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import TYPE_CHECKING

from omni_cio.contracts.v1.capacity import CapacityAssessmentV1, OrderSide
from omni_cio.contracts.v1.common import AccountReference
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


DEFAULT_OWNER_SNAPSHOT_TTL_SECONDS = 300
DEFAULT_OWNER_SNAPSHOT_CAPACITY = 64
DEFAULT_OWNER_SNAPSHOT_MAX_SCENARIO_AGE_SECONDS = 300
DEFAULT_OWNER_SNAPSHOT_FUTURE_TOLERANCE_SECONDS = 30


class FinalDecisionReviewApprovedOwnerSnapshotError(ValueError):
    """Exact calculator snapshots cannot be retained or rebound safely."""


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
    source_request: ApprovedCalculatorInvocationRequestV1
    account: AccountReference
    captured_at: datetime
    expires_at: datetime
    decision: DecisionSetV1
    intent_request: CapacityIntentDecisionGateRequestV1
    capacity_assessments: tuple[CapacityAssessmentV1, ...]
    pro_forma_scenario: ProFormaRiskScenarioV1
    purchase_previews: tuple[PreTradePreviewV1, ...] = ()
    sell_previews: tuple[SellPreTradePreviewV1, ...] = ()
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
        purchase_selected = bool(self.purchase_previews)
        sell_selected = bool(self.sell_previews)
        if purchase_selected == sell_selected:
            raise FinalDecisionReviewApprovedOwnerSnapshotError(
                "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_DIRECTION_INVALID"
            )
        expected_purchase = (
            self.source_request.operation
            is ApprovedCalculatorOperation.PURCHASE_REVIEW
        )
        if expected_purchase != purchase_selected:
            raise FinalDecisionReviewApprovedOwnerSnapshotError(
                "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_OPERATION_MISMATCH"
            )
        if self.expires_at <= self.captured_at:
            raise FinalDecisionReviewApprovedOwnerSnapshotError(
                "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_EXPIRY_INVALID"
            )


@dataclass(frozen=True, slots=True)
class FinalDecisionReviewApprovedOwnerSnapshotSelectionV1:
    context: FinalDecisionReviewApprovedServerContextV1
    captured_at: datetime
    purchase_owners: FinalDecisionReviewTrustedPurchaseOwnerPortsV1 | None = None
    sell_owners: FinalDecisionReviewTrustedSellOwnerPortsV1 | None = None
    internal_only: bool = True
    rebound_to_authenticated_context: bool = True
    raw_action_payload_accepted: bool = False
    credentials_present: bool = False
    full_account_identifier_present: bool = False
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
                "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_SELECTION_INVALID"
            )
        expected_purchase = (
            self.context.operation is ApprovedCalculatorOperation.PURCHASE_REVIEW
        )
        if expected_purchase != purchase_selected:
            raise FinalDecisionReviewApprovedOwnerSnapshotError(
                "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_SELECTION_OPERATION_MISMATCH"
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


def _direction(operation: ApprovedCalculatorOperation) -> OrderSide:
    if operation is ApprovedCalculatorOperation.PURCHASE_REVIEW:
        return OrderSide.BUY
    if operation is ApprovedCalculatorOperation.SELL_REVIEW:
        return OrderSide.SELL
    raise FinalDecisionReviewApprovedOwnerSnapshotError(
        "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_OPERATION_INVALID"
    )


def _request_identity(
    values: tuple[CapacityAssessmentV1, ...],
) -> dict[str, object]:
    return {row.request.instrument_key: row.request for row in values}


def _preview_identity(
    values: tuple[PreTradePreviewV1, ...] | tuple[SellPreTradePreviewV1, ...],
) -> tuple[set[str], tuple[AccountReference, ...]]:
    return (
        {row.stable_key for row in values},
        tuple(row.metadata.account for row in values),
    )


def _validate_capture(
    *,
    request: ApprovedCalculatorInvocationRequestV1,
    decision: DecisionSetV1,
    intent_request: CapacityIntentDecisionGateRequestV1,
    capacity_assessments: tuple[CapacityAssessmentV1, ...],
    previews: tuple[PreTradePreviewV1, ...] | tuple[SellPreTradePreviewV1, ...],
    pro_forma_risk: RiskPolicyEvaluationV1,
    publication: TrustedScenarioPublicationResultV1,
    captured_at: datetime,
    direction: OrderSide,
) -> None:
    expected_operation = (
        ApprovedCalculatorOperation.PURCHASE_REVIEW
        if direction is OrderSide.BUY
        else ApprovedCalculatorOperation.SELL_REVIEW
    )
    if not isinstance(request, ApprovedCalculatorInvocationRequestV1):
        raise FinalDecisionReviewApprovedOwnerSnapshotError(
            "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_REQUEST_INVALID"
        )
    if request.operation is not expected_operation:
        raise FinalDecisionReviewApprovedOwnerSnapshotError(
            "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_OPERATION_MISMATCH"
        )
    if not isinstance(decision, DecisionSetV1):
        raise FinalDecisionReviewApprovedOwnerSnapshotError(
            "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_DECISION_INVALID"
        )
    if not isinstance(intent_request, CapacityIntentDecisionGateRequestV1):
        raise FinalDecisionReviewApprovedOwnerSnapshotError(
            "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_INTENT_INVALID"
        )
    if not capacity_assessments or any(
        not isinstance(row, CapacityAssessmentV1) for row in capacity_assessments
    ):
        raise FinalDecisionReviewApprovedOwnerSnapshotError(
            "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_CAPACITY_INVALID"
        )
    if not previews:
        raise FinalDecisionReviewApprovedOwnerSnapshotError(
            "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_PREVIEWS_EMPTY"
        )
    if not isinstance(pro_forma_risk, RiskPolicyEvaluationV1):
        raise FinalDecisionReviewApprovedOwnerSnapshotError(
            "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_RISK_INVALID"
        )
    if not isinstance(publication, TrustedScenarioPublicationResultV1):
        raise FinalDecisionReviewApprovedOwnerSnapshotError(
            "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_PUBLICATION_INVALID"
        )

    expected_requests = intent_request.expected_capacity_requests
    expected_by_key = {row.instrument_key: row for row in expected_requests}
    actual_by_key = _request_identity(capacity_assessments)
    preview_keys, preview_accounts = _preview_identity(previews)
    account = decision.metadata.account
    exact = all(
        (
            publication.scenario_id == request.scenario_id,
            publication.direction is direction,
            publication.account == account,
            publication.published_at == request.invoked_at,
            publication.gate_assessed_at == pro_forma_risk.metadata.retrieved_at,
            publication.pro_forma_retrieved_at
            == pro_forma_risk.metadata.retrieved_at,
            pro_forma_risk.metadata.account == account,
            bool(expected_requests),
            all(row.side is direction for row in expected_requests),
            len(expected_by_key) == len(expected_requests),
            len(actual_by_key) == len(capacity_assessments),
            actual_by_key == expected_by_key,
            len(preview_keys) == len(previews),
            preview_keys == set(expected_by_key),
            all(candidate == account for candidate in preview_accounts),
            captured_at >= publication.published_at,
        )
    )
    if not exact:
        raise FinalDecisionReviewApprovedOwnerSnapshotError(
            "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_IDENTITY_MISMATCH"
        )


def _build_scenario(
    *,
    request: ApprovedCalculatorInvocationRequestV1,
    account: AccountReference,
    intent_request: CapacityIntentDecisionGateRequestV1,
    pro_forma_risk: RiskPolicyEvaluationV1,
    direction: OrderSide,
) -> ProFormaRiskScenarioV1:
    return build_pro_forma_risk_scenario(
        scenario_id=request.scenario_id,
        account=account,
        requested_option_id=intent_request.requested_option_id,
        direction=direction,
        capacity_requests=intent_request.expected_capacity_requests,
        risk_evaluation=pro_forma_risk,
        generated_at=pro_forma_risk.metadata.retrieved_at,
    )


def _require_bound_request(
    actual: ApprovedCalculatorInvocationRequestV1,
    expected: ApprovedCalculatorInvocationRequestV1,
) -> None:
    if not isinstance(actual, ApprovedCalculatorInvocationRequestV1):
        raise FinalDecisionReviewApprovedOwnerSnapshotError(
            "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_BOUND_REQUEST_INVALID"
        )
    if actual != expected:
        raise FinalDecisionReviewApprovedOwnerSnapshotError(
            "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_BOUND_REQUEST_MISMATCH"
        )


def _common_ports(
    *,
    request: ApprovedCalculatorInvocationRequestV1,
    bundle: FinalDecisionReviewApprovedOwnerSnapshotBundleV1,
) -> FinalDecisionReviewTrustedCommonOwnerPortsV1:
    def decision_owner(
        actual: ApprovedCalculatorInvocationRequestV1,
    ) -> DecisionSetV1:
        _require_bound_request(actual, request)
        return bundle.decision

    def intent_owner(
        actual: ApprovedCalculatorInvocationRequestV1,
    ) -> CapacityIntentDecisionGateRequestV1:
        _require_bound_request(actual, request)
        return bundle.intent_request

    def capacity_owner(
        actual: ApprovedCalculatorInvocationRequestV1,
    ) -> tuple[CapacityAssessmentV1, ...]:
        _require_bound_request(actual, request)
        return bundle.capacity_assessments

    def scenario_owner(
        actual: ApprovedCalculatorInvocationRequestV1,
    ) -> ProFormaRiskScenarioV1:
        _require_bound_request(actual, request)
        return bundle.pro_forma_scenario

    return FinalDecisionReviewTrustedCommonOwnerPortsV1(
        decision=decision_owner,
        intent=intent_owner,
        capacity=capacity_owner,
        pro_forma_scenario=scenario_owner,
    )


def _purchase_ports(
    *,
    request: ApprovedCalculatorInvocationRequestV1,
    bundle: FinalDecisionReviewApprovedOwnerSnapshotBundleV1,
) -> FinalDecisionReviewTrustedPurchaseOwnerPortsV1:
    def preview_owner(
        actual: ApprovedCalculatorInvocationRequestV1,
    ) -> tuple[PreTradePreviewV1, ...]:
        _require_bound_request(actual, request)
        return bundle.purchase_previews

    return FinalDecisionReviewTrustedPurchaseOwnerPortsV1(
        common=_common_ports(request=request, bundle=bundle),
        previews=preview_owner,
    )


def _sell_ports(
    *,
    request: ApprovedCalculatorInvocationRequestV1,
    bundle: FinalDecisionReviewApprovedOwnerSnapshotBundleV1,
) -> FinalDecisionReviewTrustedSellOwnerPortsV1:
    def preview_owner(
        actual: ApprovedCalculatorInvocationRequestV1,
    ) -> tuple[SellPreTradePreviewV1, ...]:
        _require_bound_request(actual, request)
        return bundle.sell_previews

    return FinalDecisionReviewTrustedSellOwnerPortsV1(
        common=_common_ports(request=request, bundle=bundle),
        previews=preview_owner,
    )


class FinalDecisionReviewApprovedOwnerSnapshotStoreV1:
    """Retain exact typed inputs and rebind them to a fresh server context."""

    def __init__(
        self,
        *,
        ttl_seconds: int = DEFAULT_OWNER_SNAPSHOT_TTL_SECONDS,
        capacity: int = DEFAULT_OWNER_SNAPSHOT_CAPACITY,
        max_scenario_age_seconds: int = (
            DEFAULT_OWNER_SNAPSHOT_MAX_SCENARIO_AGE_SECONDS
        ),
        future_tolerance_seconds: int = (
            DEFAULT_OWNER_SNAPSHOT_FUTURE_TOLERANCE_SECONDS
        ),
    ) -> None:
        if not 1 <= ttl_seconds <= 3_600:
            raise FinalDecisionReviewApprovedOwnerSnapshotError(
                "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_TTL_INVALID"
            )
        if not 1 <= capacity <= 1_024:
            raise FinalDecisionReviewApprovedOwnerSnapshotError(
                "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_CAPACITY_INVALID"
            )
        if not 1 <= max_scenario_age_seconds <= 86_400:
            raise FinalDecisionReviewApprovedOwnerSnapshotError(
                "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_MAX_AGE_INVALID"
            )
        if not 0 <= future_tolerance_seconds <= 3_600:
            raise FinalDecisionReviewApprovedOwnerSnapshotError(
                "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_FUTURE_TOLERANCE_INVALID"
            )
        self._ttl = timedelta(seconds=ttl_seconds)
        self._capacity = capacity
        self._max_scenario_age_seconds = max_scenario_age_seconds
        self._future_tolerance_seconds = future_tolerance_seconds
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
        bundle: FinalDecisionReviewApprovedOwnerSnapshotBundleV1,
    ) -> FinalDecisionReviewApprovedOwnerSnapshotCaptureV1:
        key = _key(
            scenario_id=bundle.source_request.scenario_id,
            correlation_id=bundle.source_request.correlation_id,
            operation=bundle.source_request.operation,
            account_masked_id=bundle.account.masked_id,
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
            scenario_id=bundle.source_request.scenario_id,
            correlation_id=bundle.source_request.correlation_id,
            operation=bundle.source_request.operation,
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
        now = _aware_utc(captured_at)
        _validate_capture(
            request=request,
            decision=decision,
            intent_request=intent_request,
            capacity_assessments=capacity_assessments,
            previews=purchase_previews,
            pro_forma_risk=pro_forma_risk,
            publication=publication,
            captured_at=now,
            direction=OrderSide.BUY,
        )
        scenario = _build_scenario(
            request=request,
            account=publication.account,
            intent_request=intent_request,
            pro_forma_risk=pro_forma_risk,
            direction=OrderSide.BUY,
        )
        expires_at = min(
            now + self._ttl,
            scenario.generated_at
            + timedelta(seconds=self._max_scenario_age_seconds),
        )
        if expires_at <= now:
            raise FinalDecisionReviewApprovedOwnerSnapshotError(
                "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_ALREADY_STALE"
            )
        return self._publish(
            FinalDecisionReviewApprovedOwnerSnapshotBundleV1(
                source_request=request,
                account=publication.account,
                captured_at=now,
                expires_at=expires_at,
                decision=decision,
                intent_request=intent_request,
                capacity_assessments=capacity_assessments,
                pro_forma_scenario=scenario,
                purchase_previews=purchase_previews,
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
        now = _aware_utc(captured_at)
        _validate_capture(
            request=request,
            decision=decision,
            intent_request=intent_request,
            capacity_assessments=capacity_assessments,
            previews=sell_previews,
            pro_forma_risk=pro_forma_risk,
            publication=publication,
            captured_at=now,
            direction=OrderSide.SELL,
        )
        scenario = _build_scenario(
            request=request,
            account=publication.account,
            intent_request=intent_request,
            pro_forma_risk=pro_forma_risk,
            direction=OrderSide.SELL,
        )
        expires_at = min(
            now + self._ttl,
            scenario.generated_at
            + timedelta(seconds=self._max_scenario_age_seconds),
        )
        if expires_at <= now:
            raise FinalDecisionReviewApprovedOwnerSnapshotError(
                "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_ALREADY_STALE"
            )
        return self._publish(
            FinalDecisionReviewApprovedOwnerSnapshotBundleV1(
                source_request=request,
                account=publication.account,
                captured_at=now,
                expires_at=expires_at,
                decision=decision,
                intent_request=intent_request,
                capacity_assessments=capacity_assessments,
                pro_forma_scenario=scenario,
                sell_previews=sell_previews,
            )
        )

    def select(
        self,
        context: FinalDecisionReviewApprovedServerContextV1,
        *,
        checked_at: datetime | None = None,
    ) -> FinalDecisionReviewApprovedOwnerSnapshotSelectionV1 | None:
        from omni_cio.release.final_decision_review_approved_owner_acquisition_v1 import (
            FinalDecisionReviewApprovedServerContextV1,
        )

        if not isinstance(context, FinalDecisionReviewApprovedServerContextV1):
            raise FinalDecisionReviewApprovedOwnerSnapshotError(
                "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_CONTEXT_INVALID"
            )
        now = _aware_utc(checked_at or context.generated_at)
        if now < context.generated_at - timedelta(
            seconds=self._future_tolerance_seconds
        ):
            raise FinalDecisionReviewApprovedOwnerSnapshotError(
                "FINAL_DECISION_REVIEW_OWNER_SNAPSHOT_CHECK_TIME_INVALID"
            )
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
            scenario_age = (
                context.generated_at - bundle.pro_forma_scenario.generated_at
            ).total_seconds()
            capture_age = (context.generated_at - bundle.captured_at).total_seconds()
            if (
                scenario_age > self._max_scenario_age_seconds
                or scenario_age < -self._future_tolerance_seconds
                or capture_age < -self._future_tolerance_seconds
            ):
                return None
            self._bundles.move_to_end(key)

        request = context.invocation_request()
        if context.operation is ApprovedCalculatorOperation.PURCHASE_REVIEW:
            return FinalDecisionReviewApprovedOwnerSnapshotSelectionV1(
                context=context,
                captured_at=bundle.captured_at,
                purchase_owners=_purchase_ports(
                    request=request,
                    bundle=bundle,
                ),
            )
        return FinalDecisionReviewApprovedOwnerSnapshotSelectionV1(
            context=context,
            captured_at=bundle.captured_at,
            sell_owners=_sell_ports(
                request=request,
                bundle=bundle,
            ),
        )

    def active_bundle_count(self, *, checked_at: datetime | None = None) -> int:
        now = _aware_utc(checked_at)
        with self._lock:
            self._prune(now)
            return len(self._bundles)

    def clear(self) -> None:
        with self._lock:
            self._bundles.clear()
