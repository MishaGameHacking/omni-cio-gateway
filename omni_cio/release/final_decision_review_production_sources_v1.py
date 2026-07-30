from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any, TypeAlias

from omni_cio.adapters.portfolio_market_v1 import portfolio_snapshot_v1_from_market_payload
from omni_cio.analytics.portfolio_v1 import build_advanced_portfolio_analytics
from omni_cio.contracts.v1.capacity import OrderSide
from omni_cio.contracts.v1.decision_capacity_pretrade import (
    CapacityPreTradeDecisionGateV1,
)
from omni_cio.contracts.v1.decision_capacity_sell_pretrade import (
    CapacitySellPreTradeDecisionGateV1,
)
from omni_cio.contracts.v1.final_decision_review_source_acquisition import (
    FinalDecisionReviewSourceAcquisitionResultV1,
)
from omni_cio.contracts.v1.risk import RiskPolicyEvaluationV1
from omni_cio.release.final_decision_review_source_acquisition_v1 import (
    FinalDecisionReviewSourceAcquisitionAdapterV1,
    purchase_gate_source_loader,
    risk_source_loader,
    sell_gate_source_loader,
)
from omni_cio.release.final_decision_review_workflow_coordinator_v1 import (
    FinalDecisionReviewWorkflowCoordinatorV1,
)
from omni_cio.risk.policy_v1 import evaluate_conservative_risk_policy
from omni_cio.contracts.v1.final_decision_review_workflow_coordinator import (
    FinalDecisionReviewWorkflowSourceSlot,
)


class FinalDecisionReviewProductionSourceError(ValueError):
    """Production read-only final-review sources cannot be wired safely."""


DirectionalGateV1: TypeAlias = (
    CapacityPreTradeDecisionGateV1 | CapacitySellPreTradeDecisionGateV1
)


@dataclass(frozen=True, slots=True)
class FinalDecisionReviewScenarioSourceBundleV1:
    scenario_id: str
    stored_at: datetime
    expires_at: datetime
    purchase_gate: CapacityPreTradeDecisionGateV1 | None
    sell_gate: CapacitySellPreTradeDecisionGateV1 | None
    pro_forma_risk: RiskPolicyEvaluationV1

    @property
    def direction(self) -> OrderSide:
        return OrderSide.BUY if self.purchase_gate is not None else OrderSide.SELL


@dataclass(frozen=True, slots=True)
class FinalDecisionReviewScenarioSourcePublicationV1:
    scenario_id: str
    published_at: datetime
    replaced: bool
    evicted: bool
    active_bundle_count: int
    internal_only: bool = True
    http_publication_method_created: bool = False
    broker_write_called: bool = False
    trade_authorized: bool = False
    order_created: bool = False
    trading_methods: bool = False



def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise FinalDecisionReviewProductionSourceError(
            "FINAL_DECISION_REVIEW_PRODUCTION_SOURCE_TIMESTAMP_MUST_BE_AWARE"
        )
    return result.astimezone(timezone.utc)



def _scenario_id(value: str) -> str:
    result = value.strip()
    if not 3 <= len(result) <= 128:
        raise FinalDecisionReviewProductionSourceError(
            "FINAL_DECISION_REVIEW_PRODUCTION_SOURCE_SCENARIO_ID_INVALID"
        )
    if not all(character.isalnum() or character in "-_.:" for character in result):
        raise FinalDecisionReviewProductionSourceError(
            "FINAL_DECISION_REVIEW_PRODUCTION_SOURCE_SCENARIO_ID_INVALID"
        )
    return result


class FinalDecisionReviewScenarioSourceStoreV1:
    """Bounded process-local storage for exact scenario-specific source artifacts."""

    def __init__(self, *, ttl_seconds: int = 900, capacity: int = 64) -> None:
        if not 1 <= ttl_seconds <= 86_400:
            raise FinalDecisionReviewProductionSourceError(
                "FINAL_DECISION_REVIEW_PRODUCTION_SOURCE_TTL_INVALID"
            )
        if not 1 <= capacity <= 1_024:
            raise FinalDecisionReviewProductionSourceError(
                "FINAL_DECISION_REVIEW_PRODUCTION_SOURCE_CAPACITY_INVALID"
            )
        self._ttl_seconds = ttl_seconds
        self._capacity = capacity
        self._bundles: OrderedDict[str, FinalDecisionReviewScenarioSourceBundleV1] = (
            OrderedDict()
        )
        self._lock = RLock()

    @property
    def ttl_seconds(self) -> int:
        return self._ttl_seconds

    @property
    def capacity(self) -> int:
        return self._capacity

    def _purge_expired(self, checked_at: datetime) -> None:
        expired = [
            scenario_id
            for scenario_id, bundle in self._bundles.items()
            if bundle.expires_at <= checked_at
        ]
        for scenario_id in expired:
            self._bundles.pop(scenario_id, None)

    def publish(
        self,
        *,
        scenario_id: str,
        pro_forma_risk: RiskPolicyEvaluationV1,
        purchase_gate: CapacityPreTradeDecisionGateV1 | None = None,
        sell_gate: CapacitySellPreTradeDecisionGateV1 | None = None,
        published_at: datetime | None = None,
    ) -> FinalDecisionReviewScenarioSourcePublicationV1:
        key = _scenario_id(scenario_id)
        now = _aware_utc(published_at)
        direction_count = int(purchase_gate is not None) + int(sell_gate is not None)
        if direction_count != 1:
            raise FinalDecisionReviewProductionSourceError(
                "FINAL_DECISION_REVIEW_PRODUCTION_SOURCE_DIRECTION_INVALID"
            )
        if not isinstance(pro_forma_risk, RiskPolicyEvaluationV1):
            raise FinalDecisionReviewProductionSourceError(
                "FINAL_DECISION_REVIEW_PRODUCTION_SOURCE_PRO_FORMA_TYPE_INVALID"
            )
        if purchase_gate is not None and not isinstance(
            purchase_gate, CapacityPreTradeDecisionGateV1
        ):
            raise FinalDecisionReviewProductionSourceError(
                "FINAL_DECISION_REVIEW_PRODUCTION_SOURCE_PURCHASE_GATE_TYPE_INVALID"
            )
        if sell_gate is not None and not isinstance(
            sell_gate, CapacitySellPreTradeDecisionGateV1
        ):
            raise FinalDecisionReviewProductionSourceError(
                "FINAL_DECISION_REVIEW_PRODUCTION_SOURCE_SELL_GATE_TYPE_INVALID"
            )

        bundle = FinalDecisionReviewScenarioSourceBundleV1(
            scenario_id=key,
            stored_at=now,
            expires_at=now + timedelta(seconds=self._ttl_seconds),
            purchase_gate=purchase_gate,
            sell_gate=sell_gate,
            pro_forma_risk=pro_forma_risk,
        )
        with self._lock:
            self._purge_expired(now)
            replaced = key in self._bundles
            if replaced:
                self._bundles.pop(key)
            self._bundles[key] = bundle
            evicted = False
            while len(self._bundles) > self._capacity:
                self._bundles.popitem(last=False)
                evicted = True
            active = len(self._bundles)
        return FinalDecisionReviewScenarioSourcePublicationV1(
            scenario_id=key,
            published_at=now,
            replaced=replaced,
            evicted=evicted,
            active_bundle_count=active,
        )

    def load_bundle(
        self,
        scenario_id: str,
        *,
        checked_at: datetime | None = None,
    ) -> FinalDecisionReviewScenarioSourceBundleV1 | None:
        key = _scenario_id(scenario_id)
        now = _aware_utc(checked_at)
        with self._lock:
            self._purge_expired(now)
            bundle = self._bundles.get(key)
            if bundle is None:
                return None
            self._bundles.move_to_end(key)
            return bundle

    def active_bundle_count(self, *, checked_at: datetime | None = None) -> int:
        now = _aware_utc(checked_at)
        with self._lock:
            self._purge_expired(now)
            return len(self._bundles)



def build_live_current_risk_loader(
    *,
    portfolio_payload_loader: Callable[[], Mapping[str, Any]],
) -> Callable[[], RiskPolicyEvaluationV1 | None]:
    """Build current risk from the existing read-only portfolio-market pipeline."""

    def load() -> RiskPolicyEvaluationV1 | None:
        payload = portfolio_payload_loader()
        if not isinstance(payload, Mapping):
            raise FinalDecisionReviewProductionSourceError(
                "FINAL_DECISION_REVIEW_CURRENT_RISK_PAYLOAD_INVALID"
            )
        snapshot = portfolio_snapshot_v1_from_market_payload(payload)
        analytics = build_advanced_portfolio_analytics(
            snapshot,
            retrieved_at=snapshot.metadata.retrieved_at,
        )
        return evaluate_conservative_risk_policy(
            analytics,
            evaluated_at=analytics.metadata.retrieved_at,
        )

    return load


class FinalDecisionReviewProductionSourceWiringV1:
    """Connect PR-68 loaders to live current risk and exact scenario artifacts."""

    def __init__(
        self,
        *,
        coordinator: FinalDecisionReviewWorkflowCoordinatorV1,
        source_store: FinalDecisionReviewScenarioSourceStoreV1,
        current_risk_loader: Callable[[], RiskPolicyEvaluationV1 | None],
    ) -> None:
        self._coordinator = coordinator
        self._source_store = source_store
        self._current_risk_loader = current_risk_loader
        self._lock = RLock()

    @property
    def coordinator(self) -> FinalDecisionReviewWorkflowCoordinatorV1:
        return self._coordinator

    @property
    def source_store(self) -> FinalDecisionReviewScenarioSourceStoreV1:
        return self._source_store

    def acquire(
        self,
        *,
        direction: OrderSide,
        scenario_id: str,
        correlation_id: str,
        request_id: str | None = None,
        acquired_at: datetime | None = None,
    ) -> FinalDecisionReviewSourceAcquisitionResultV1:
        now = _aware_utc(acquired_at)
        key = _scenario_id(scenario_id)

        def bundle() -> FinalDecisionReviewScenarioSourceBundleV1 | None:
            return self._source_store.load_bundle(key, checked_at=now)

        def purchase_gate() -> CapacityPreTradeDecisionGateV1 | None:
            source = bundle()
            return source.purchase_gate if source is not None else None

        def sell_gate() -> CapacitySellPreTradeDecisionGateV1 | None:
            source = bundle()
            return source.sell_gate if source is not None else None

        def pro_forma_risk() -> RiskPolicyEvaluationV1 | None:
            source = bundle()
            return source.pro_forma_risk if source is not None else None

        adapter = FinalDecisionReviewSourceAcquisitionAdapterV1(
            coordinator=self._coordinator,
            purchase_gate_loader=purchase_gate_source_loader(
                provider="omni-cio",
                operation="load-production-purchase-gate",
                load=purchase_gate,
            ),
            sell_gate_loader=sell_gate_source_loader(
                provider="omni-cio",
                operation="load-production-sell-gate",
                load=sell_gate,
            ),
            current_risk_loader=risk_source_loader(
                slot=FinalDecisionReviewWorkflowSourceSlot.CURRENT_RISK,
                provider="t-invest",
                operation="load-live-current-risk",
                load=self._current_risk_loader,
            ),
            pro_forma_risk_loader=risk_source_loader(
                slot=FinalDecisionReviewWorkflowSourceSlot.PRO_FORMA_RISK,
                provider="omni-cio",
                operation="load-production-pro-forma-risk",
                load=pro_forma_risk,
            ),
        )
        with self._lock:
            return adapter.acquire(
                direction=direction,
                scenario_id=key,
                correlation_id=correlation_id,
                request_id=request_id,
                acquired_at=now,
            )
