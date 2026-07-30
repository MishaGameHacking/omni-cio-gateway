from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from threading import RLock

from omni_cio.contracts.v1.final_decision_review_approved_invocation import (
    ApprovedCalculatorInvocationRequestV1,
    ApprovedCalculatorOperation,
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
    register_existing_calculator_providers,
)


_SAFE_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{2,127}$")


class FinalDecisionReviewProductionOwnerCallableError(ValueError):
    """Production owner callables cannot be routed safely."""


@dataclass(frozen=True, slots=True)
class FinalDecisionReviewProductionOwnerCallableBundleV1:
    scenario_id: str
    correlation_id: str
    operation: ApprovedCalculatorOperation
    published_at: datetime
    expires_at: datetime
    purchase: ApprovedPurchaseCalculatorOwnersV1 | None = None
    sell: ApprovedSellCalculatorOwnersV1 | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.scenario_id, str)
            or _SAFE_ID.fullmatch(self.scenario_id) is None
        ):
            raise FinalDecisionReviewProductionOwnerCallableError(
                "FINAL_DECISION_REVIEW_PRODUCTION_OWNER_SCENARIO_ID_INVALID"
            )
        if (
            not isinstance(self.correlation_id, str)
            or _SAFE_ID.fullmatch(self.correlation_id) is None
        ):
            raise FinalDecisionReviewProductionOwnerCallableError(
                "FINAL_DECISION_REVIEW_PRODUCTION_OWNER_CORRELATION_ID_INVALID"
            )
        if not isinstance(self.operation, ApprovedCalculatorOperation):
            raise FinalDecisionReviewProductionOwnerCallableError(
                "FINAL_DECISION_REVIEW_PRODUCTION_OWNER_OPERATION_INVALID"
            )
        published_at = _aware_utc(self.published_at)
        expires_at = _aware_utc(self.expires_at)
        if expires_at <= published_at:
            raise FinalDecisionReviewProductionOwnerCallableError(
                "FINAL_DECISION_REVIEW_PRODUCTION_OWNER_EXPIRY_INVALID"
            )
        object.__setattr__(self, "published_at", published_at)
        object.__setattr__(self, "expires_at", expires_at)
        direction_count = int(self.purchase is not None) + int(self.sell is not None)
        if direction_count != 1:
            raise FinalDecisionReviewProductionOwnerCallableError(
                "FINAL_DECISION_REVIEW_PRODUCTION_OWNER_DIRECTION_INVALID"
            )
        if self.operation is ApprovedCalculatorOperation.PURCHASE_REVIEW:
            if not isinstance(self.purchase, ApprovedPurchaseCalculatorOwnersV1):
                raise FinalDecisionReviewProductionOwnerCallableError(
                    "FINAL_DECISION_REVIEW_PRODUCTION_PURCHASE_OWNERS_TYPE_INVALID"
                )
            if self.sell is not None:
                raise FinalDecisionReviewProductionOwnerCallableError(
                    "FINAL_DECISION_REVIEW_PRODUCTION_OWNER_DIRECTION_MISMATCH"
                )
        elif not isinstance(self.sell, ApprovedSellCalculatorOwnersV1):
            raise FinalDecisionReviewProductionOwnerCallableError(
                "FINAL_DECISION_REVIEW_PRODUCTION_SELL_OWNERS_TYPE_INVALID"
            )
        elif self.purchase is not None:
            raise FinalDecisionReviewProductionOwnerCallableError(
                "FINAL_DECISION_REVIEW_PRODUCTION_OWNER_DIRECTION_MISMATCH"
            )


@dataclass(frozen=True, slots=True)
class FinalDecisionReviewProductionOwnerCallablePublicationV1:
    scenario_id: str
    correlation_id: str
    operation: ApprovedCalculatorOperation
    published_at: datetime
    expires_at: datetime
    evicted: bool
    active_bundle_count: int
    internal_only: bool = True
    owner_called: bool = False
    broker_write_called: bool = False
    trade_authorized: bool = False
    order_created: bool = False
    trading_methods: bool = False


@dataclass(frozen=True, slots=True)
class FinalDecisionReviewProductionOwnerCallableRegistrationV1:
    purchase_provider_id: str
    sell_provider_id: str
    registered_provider_count: int
    startup_owner_call_performed: bool = False
    broker_write_called: bool = False
    trade_authorized: bool = False
    order_created: bool = False
    trading_methods: bool = False


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if (
        not isinstance(result, datetime)
        or result.tzinfo is None
        or result.utcoffset() is None
    ):
        raise FinalDecisionReviewProductionOwnerCallableError(
            "FINAL_DECISION_REVIEW_PRODUCTION_OWNER_TIMESTAMP_MUST_BE_AWARE"
        )
    return result.astimezone(timezone.utc)


def _safe_id(value: str, *, code: str) -> str:
    if not isinstance(value, str):
        raise FinalDecisionReviewProductionOwnerCallableError(code)
    result = value.strip()
    if _SAFE_ID.fullmatch(result) is None:
        raise FinalDecisionReviewProductionOwnerCallableError(code)
    return result


OwnerKeyV1 = tuple[str, str, ApprovedCalculatorOperation]


class FinalDecisionReviewProductionOwnerCallableStoreV1:
    """Bounded process-local routing for scenario-specific read-only owners."""

    def __init__(self, *, ttl_seconds: int = 900, capacity: int = 64) -> None:
        if not 1 <= ttl_seconds <= 86_400:
            raise FinalDecisionReviewProductionOwnerCallableError(
                "FINAL_DECISION_REVIEW_PRODUCTION_OWNER_TTL_INVALID"
            )
        if not 1 <= capacity <= 1_024:
            raise FinalDecisionReviewProductionOwnerCallableError(
                "FINAL_DECISION_REVIEW_PRODUCTION_OWNER_CAPACITY_INVALID"
            )
        self._ttl_seconds = ttl_seconds
        self._capacity = capacity
        self._bundles: OrderedDict[
            OwnerKeyV1,
            FinalDecisionReviewProductionOwnerCallableBundleV1,
        ] = OrderedDict()
        self._lock = RLock()

    @property
    def ttl_seconds(self) -> int:
        return self._ttl_seconds

    @property
    def capacity(self) -> int:
        return self._capacity

    def _purge_expired(self, checked_at: datetime) -> None:
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
        scenario_id: str,
        correlation_id: str,
        operation: ApprovedCalculatorOperation,
        purchase: ApprovedPurchaseCalculatorOwnersV1 | None = None,
        sell: ApprovedSellCalculatorOwnersV1 | None = None,
        published_at: datetime | None = None,
    ) -> FinalDecisionReviewProductionOwnerCallablePublicationV1:
        scenario = _safe_id(
            scenario_id,
            code="FINAL_DECISION_REVIEW_PRODUCTION_OWNER_SCENARIO_ID_INVALID",
        )
        correlation = _safe_id(
            correlation_id,
            code="FINAL_DECISION_REVIEW_PRODUCTION_OWNER_CORRELATION_ID_INVALID",
        )
        now = _aware_utc(published_at)
        key = (scenario, correlation, operation)
        bundle = FinalDecisionReviewProductionOwnerCallableBundleV1(
            scenario_id=scenario,
            correlation_id=correlation,
            operation=operation,
            published_at=now,
            expires_at=now + timedelta(seconds=self._ttl_seconds),
            purchase=purchase,
            sell=sell,
        )
        with self._lock:
            self._purge_expired(now)
            if key in self._bundles:
                raise FinalDecisionReviewProductionOwnerCallableError(
                    "FINAL_DECISION_REVIEW_PRODUCTION_OWNER_ALREADY_PUBLISHED"
                )
            self._bundles[key] = bundle
            evicted = False
            while len(self._bundles) > self._capacity:
                self._bundles.popitem(last=False)
                evicted = True
            active = len(self._bundles)
        return FinalDecisionReviewProductionOwnerCallablePublicationV1(
            scenario_id=scenario,
            correlation_id=correlation,
            operation=operation,
            published_at=now,
            expires_at=bundle.expires_at,
            evicted=evicted,
            active_bundle_count=active,
        )

    def publish_purchase(
        self,
        *,
        scenario_id: str,
        correlation_id: str,
        owners: ApprovedPurchaseCalculatorOwnersV1,
        published_at: datetime | None = None,
    ) -> FinalDecisionReviewProductionOwnerCallablePublicationV1:
        if not isinstance(owners, ApprovedPurchaseCalculatorOwnersV1):
            raise FinalDecisionReviewProductionOwnerCallableError(
                "FINAL_DECISION_REVIEW_PRODUCTION_PURCHASE_OWNERS_TYPE_INVALID"
            )
        return self._publish(
            scenario_id=scenario_id,
            correlation_id=correlation_id,
            operation=ApprovedCalculatorOperation.PURCHASE_REVIEW,
            purchase=owners,
            published_at=published_at,
        )

    def publish_sell(
        self,
        *,
        scenario_id: str,
        correlation_id: str,
        owners: ApprovedSellCalculatorOwnersV1,
        published_at: datetime | None = None,
    ) -> FinalDecisionReviewProductionOwnerCallablePublicationV1:
        if not isinstance(owners, ApprovedSellCalculatorOwnersV1):
            raise FinalDecisionReviewProductionOwnerCallableError(
                "FINAL_DECISION_REVIEW_PRODUCTION_SELL_OWNERS_TYPE_INVALID"
            )
        return self._publish(
            scenario_id=scenario_id,
            correlation_id=correlation_id,
            operation=ApprovedCalculatorOperation.SELL_REVIEW,
            sell=owners,
            published_at=published_at,
        )

    def load_for_request(
        self,
        request: ApprovedCalculatorInvocationRequestV1,
        *,
        checked_at: datetime | None = None,
    ) -> FinalDecisionReviewProductionOwnerCallableBundleV1 | None:
        if not isinstance(request, ApprovedCalculatorInvocationRequestV1):
            raise FinalDecisionReviewProductionOwnerCallableError(
                "FINAL_DECISION_REVIEW_PRODUCTION_OWNER_REQUEST_TYPE_INVALID"
            )
        now = _aware_utc(checked_at)
        key = (request.scenario_id, request.correlation_id, request.operation)
        with self._lock:
            self._purge_expired(now)
            bundle = self._bundles.get(key)
            if bundle is None:
                return None
            if bundle.published_at > request.invoked_at:
                raise FinalDecisionReviewProductionOwnerCallableError(
                    "FINAL_DECISION_REVIEW_PRODUCTION_OWNER_PUBLISHED_AFTER_INVOCATION"
                )
            self._bundles.move_to_end(key)
            return bundle

    def active_bundle_count(self, *, checked_at: datetime | None = None) -> int:
        now = _aware_utc(checked_at)
        with self._lock:
            self._purge_expired(now)
            return len(self._bundles)


class FinalDecisionReviewProductionOwnerCallableRouterV1:
    """Route fixed PR-76 provider ports to exact scenario-specific owners."""

    def __init__(
        self,
        *,
        store: FinalDecisionReviewProductionOwnerCallableStoreV1,
    ) -> None:
        if not isinstance(store, FinalDecisionReviewProductionOwnerCallableStoreV1):
            raise FinalDecisionReviewProductionOwnerCallableError(
                "FINAL_DECISION_REVIEW_PRODUCTION_OWNER_STORE_TYPE_INVALID"
            )
        self._store = store

    @property
    def store(self) -> FinalDecisionReviewProductionOwnerCallableStoreV1:
        return self._store

    def _purchase(
        self,
        request: ApprovedCalculatorInvocationRequestV1,
    ) -> ApprovedPurchaseCalculatorOwnersV1:
        bundle = self._store.load_for_request(request)
        if bundle is None or not isinstance(
            bundle.purchase,
            ApprovedPurchaseCalculatorOwnersV1,
        ):
            raise FinalDecisionReviewProductionOwnerCallableError(
                "FINAL_DECISION_REVIEW_PRODUCTION_PURCHASE_OWNERS_UNAVAILABLE"
            )
        return bundle.purchase

    def _sell(
        self,
        request: ApprovedCalculatorInvocationRequestV1,
    ) -> ApprovedSellCalculatorOwnersV1:
        bundle = self._store.load_for_request(request)
        if bundle is None or not isinstance(
            bundle.sell,
            ApprovedSellCalculatorOwnersV1,
        ):
            raise FinalDecisionReviewProductionOwnerCallableError(
                "FINAL_DECISION_REVIEW_PRODUCTION_SELL_OWNERS_UNAVAILABLE"
            )
        return bundle.sell

    def purchase_owners(self) -> ApprovedPurchaseCalculatorOwnersV1:
        common = ApprovedCalculatorCommonOwnersV1(
            decision=lambda request: self._purchase(request).common.decision(request),
            intent=lambda request: self._purchase(request).common.intent(request),
            capacity=lambda request: self._purchase(request).common.capacity(request),
            pro_forma_risk=lambda request: (
                self._purchase(request).common.pro_forma_risk(request)
            ),
        )
        return ApprovedPurchaseCalculatorOwnersV1(
            common=common,
            previews=lambda request: self._purchase(request).previews(request),
        )

    def sell_owners(self) -> ApprovedSellCalculatorOwnersV1:
        common = ApprovedCalculatorCommonOwnersV1(
            decision=lambda request: self._sell(request).common.decision(request),
            intent=lambda request: self._sell(request).common.intent(request),
            capacity=lambda request: self._sell(request).common.capacity(request),
            pro_forma_risk=lambda request: (
                self._sell(request).common.pro_forma_risk(request)
            ),
        )
        return ApprovedSellCalculatorOwnersV1(
            common=common,
            previews=lambda request: self._sell(request).previews(request),
        )


def register_final_decision_review_production_owner_callables(
    *,
    registry: FinalDecisionReviewCalculatorProviderRegistryV1,
    store: FinalDecisionReviewProductionOwnerCallableStoreV1,
) -> FinalDecisionReviewProductionOwnerCallableRegistrationV1:
    """Register fixed purchase/sell dispatchers without invoking an owner."""
    if not isinstance(registry, FinalDecisionReviewCalculatorProviderRegistryV1):
        raise FinalDecisionReviewProductionOwnerCallableError(
            "FINAL_DECISION_REVIEW_PRODUCTION_OWNER_REGISTRY_TYPE_INVALID"
        )
    if not isinstance(store, FinalDecisionReviewProductionOwnerCallableStoreV1):
        raise FinalDecisionReviewProductionOwnerCallableError(
            "FINAL_DECISION_REVIEW_PRODUCTION_OWNER_STORE_TYPE_INVALID"
        )
    router = FinalDecisionReviewProductionOwnerCallableRouterV1(store=store)
    register_existing_calculator_providers(
        registry=registry,
        purchase=router.purchase_owners(),
        sell=router.sell_owners(),
    )
    return FinalDecisionReviewProductionOwnerCallableRegistrationV1(
        purchase_provider_id=PURCHASE_PROVIDER_ID,
        sell_provider_id=SELL_PROVIDER_ID,
        registered_provider_count=2,
    )
