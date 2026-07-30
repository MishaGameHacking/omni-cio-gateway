from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock

from omni_cio.contracts.v1.capacity import OrderSide
from omni_cio.contracts.v1.decision_capacity_pretrade import (
    CapacityPreTradeDecisionGateV1,
)
from omni_cio.contracts.v1.decision_capacity_sell_pretrade import (
    CapacitySellPreTradeDecisionGateV1,
)
from omni_cio.contracts.v1.risk import RiskPolicyEvaluationV1
from omni_cio.release.final_decision_review_production_sources_v1 import (
    FinalDecisionReviewScenarioSourcePublicationV1,
    FinalDecisionReviewScenarioSourceStoreV1,
)


class FinalDecisionReviewCalculatorPublicationError(ValueError):
    """Calculator-owned scenario evidence cannot be published safely."""


@dataclass(frozen=True, slots=True)
class FinalDecisionReviewCalculatorPublicationResultV1:
    scenario_id: str
    direction: OrderSide
    calculated_at: datetime
    published_at: datetime
    source_age_seconds: int
    replaced: bool
    evicted: bool
    active_bundle_count: int
    internal_only: bool = True
    calculator_owned: bool = True
    user_controlled_publication_surface: bool = False
    http_publication_method_created: bool = False
    broker_write_called: bool = False
    trade_authorized: bool = False
    order_created: bool = False
    execution_ready: bool = False
    trading_methods: bool = False

    def __post_init__(self) -> None:
        if self.source_age_seconds < 0:
            raise FinalDecisionReviewCalculatorPublicationError(
                "FINAL_DECISION_REVIEW_CALCULATOR_PUBLICATION_SOURCE_AGE_INVALID"
            )
        if (
            not self.internal_only
            or not self.calculator_owned
            or self.user_controlled_publication_surface
            or self.http_publication_method_created
            or self.broker_write_called
            or self.trade_authorized
            or self.order_created
            or self.execution_ready
            or self.trading_methods
        ):
            raise FinalDecisionReviewCalculatorPublicationError(
                "FINAL_DECISION_REVIEW_CALCULATOR_PUBLICATION_SAFETY_INVARIANT_FAILED"
            )


def _aware_utc(value: datetime, *, code: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise FinalDecisionReviewCalculatorPublicationError(code)
    return value.astimezone(timezone.utc)


def _risk_timestamp(value: RiskPolicyEvaluationV1) -> datetime:
    timestamp = getattr(getattr(value, "metadata", None), "retrieved_at", None)
    if not isinstance(timestamp, datetime):
        raise FinalDecisionReviewCalculatorPublicationError(
            "FINAL_DECISION_REVIEW_CALCULATOR_PUBLICATION_RISK_TIMESTAMP_MISSING"
        )
    return _aware_utc(
        timestamp,
        code="FINAL_DECISION_REVIEW_CALCULATOR_PUBLICATION_RISK_TIMESTAMP_INVALID",
    )


def _gate_timestamp(
    purchase_gate: CapacityPreTradeDecisionGateV1 | None,
    sell_gate: CapacitySellPreTradeDecisionGateV1 | None,
) -> tuple[OrderSide, datetime]:
    direction_count = int(purchase_gate is not None) + int(sell_gate is not None)
    if direction_count != 1:
        raise FinalDecisionReviewCalculatorPublicationError(
            "FINAL_DECISION_REVIEW_CALCULATOR_PUBLICATION_DIRECTION_INVALID"
        )
    if purchase_gate is not None:
        if not isinstance(purchase_gate, CapacityPreTradeDecisionGateV1):
            raise FinalDecisionReviewCalculatorPublicationError(
                "FINAL_DECISION_REVIEW_CALCULATOR_PUBLICATION_PURCHASE_GATE_INVALID"
            )
        timestamp = purchase_gate.assessed_at
        direction = OrderSide.BUY
    else:
        if not isinstance(sell_gate, CapacitySellPreTradeDecisionGateV1):
            raise FinalDecisionReviewCalculatorPublicationError(
                "FINAL_DECISION_REVIEW_CALCULATOR_PUBLICATION_SELL_GATE_INVALID"
            )
        timestamp = sell_gate.assessed_at
        direction = OrderSide.SELL
    if not isinstance(timestamp, datetime):
        raise FinalDecisionReviewCalculatorPublicationError(
            "FINAL_DECISION_REVIEW_CALCULATOR_PUBLICATION_GATE_TIMESTAMP_MISSING"
        )
    return direction, _aware_utc(
        timestamp,
        code="FINAL_DECISION_REVIEW_CALCULATOR_PUBLICATION_GATE_TIMESTAMP_INVALID",
    )


class FinalDecisionReviewCalculatorScenarioPublisherV1:
    """Publish exact calculator-owned pre-trade and pro-forma risk artifacts."""

    def __init__(
        self,
        *,
        source_store: FinalDecisionReviewScenarioSourceStoreV1,
        max_source_skew_seconds: int = 30,
        max_publication_delay_seconds: int = 300,
    ) -> None:
        if not 0 <= max_source_skew_seconds <= 300:
            raise FinalDecisionReviewCalculatorPublicationError(
                "FINAL_DECISION_REVIEW_CALCULATOR_PUBLICATION_SOURCE_SKEW_POLICY_INVALID"
            )
        if not 1 <= max_publication_delay_seconds <= 3_600:
            raise FinalDecisionReviewCalculatorPublicationError(
                "FINAL_DECISION_REVIEW_CALCULATOR_PUBLICATION_DELAY_POLICY_INVALID"
            )
        self._source_store = source_store
        self._max_source_skew = timedelta(seconds=max_source_skew_seconds)
        self._max_publication_delay = timedelta(seconds=max_publication_delay_seconds)
        self._lock = RLock()

    @property
    def source_store(self) -> FinalDecisionReviewScenarioSourceStoreV1:
        return self._source_store

    def publish(
        self,
        *,
        scenario_id: str,
        pro_forma_risk: RiskPolicyEvaluationV1,
        purchase_gate: CapacityPreTradeDecisionGateV1 | None = None,
        sell_gate: CapacitySellPreTradeDecisionGateV1 | None = None,
        published_at: datetime | None = None,
    ) -> FinalDecisionReviewCalculatorPublicationResultV1:
        if not isinstance(pro_forma_risk, RiskPolicyEvaluationV1):
            raise FinalDecisionReviewCalculatorPublicationError(
                "FINAL_DECISION_REVIEW_CALCULATOR_PUBLICATION_RISK_TYPE_INVALID"
            )
        direction, gate_at = _gate_timestamp(purchase_gate, sell_gate)
        risk_at = _risk_timestamp(pro_forma_risk)
        if abs(gate_at - risk_at) > self._max_source_skew:
            raise FinalDecisionReviewCalculatorPublicationError(
                "FINAL_DECISION_REVIEW_CALCULATOR_PUBLICATION_SOURCE_SKEW_EXCEEDED"
            )

        now = _aware_utc(
            published_at or datetime.now(timezone.utc),
            code="FINAL_DECISION_REVIEW_CALCULATOR_PUBLICATION_TIMESTAMP_INVALID",
        )
        calculated_at = max(gate_at, risk_at)
        if now < calculated_at:
            raise FinalDecisionReviewCalculatorPublicationError(
                "FINAL_DECISION_REVIEW_CALCULATOR_PUBLICATION_FUTURE_SOURCE"
            )
        delay = now - calculated_at
        if delay > self._max_publication_delay:
            raise FinalDecisionReviewCalculatorPublicationError(
                "FINAL_DECISION_REVIEW_CALCULATOR_PUBLICATION_SOURCE_STALE"
            )

        with self._lock:
            receipt: FinalDecisionReviewScenarioSourcePublicationV1 = (
                self._source_store.publish(
                    scenario_id=scenario_id,
                    purchase_gate=purchase_gate,
                    sell_gate=sell_gate,
                    pro_forma_risk=pro_forma_risk,
                    published_at=now,
                )
            )
        return FinalDecisionReviewCalculatorPublicationResultV1(
            scenario_id=receipt.scenario_id,
            direction=direction,
            calculated_at=calculated_at,
            published_at=receipt.published_at,
            source_age_seconds=int(delay.total_seconds()),
            replaced=receipt.replaced,
            evicted=receipt.evicted,
            active_bundle_count=receipt.active_bundle_count,
        )
