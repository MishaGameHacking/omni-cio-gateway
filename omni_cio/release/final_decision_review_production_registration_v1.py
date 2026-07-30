from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from omni_cio.release.final_decision_review_production_sources_v1 import (
    FinalDecisionReviewProductionSourceWiringV1,
    FinalDecisionReviewScenarioSourceStoreV1,
    build_live_current_risk_loader,
)
from omni_cio.release.final_decision_review_workflow_bridge_v1 import (
    FinalDecisionReviewWorkflowBridgeV1,
)
from omni_cio.release.final_decision_review_workflow_coordinator_v1 import (
    FinalDecisionReviewWorkflowCoordinatorV1,
)
from omni_cio.release.final_decision_review_workflow_producer_v1 import (
    FinalDecisionReviewWorkflowProducerV1,
)


class FinalDecisionReviewProductionRegistrationError(ValueError):
    """Production final-review source wiring cannot be registered safely."""


@dataclass(frozen=True, slots=True)
class FinalDecisionReviewProductionRuntimeV1:
    source_store: FinalDecisionReviewScenarioSourceStoreV1
    producer: FinalDecisionReviewWorkflowProducerV1
    coordinator: FinalDecisionReviewWorkflowCoordinatorV1
    source_wiring: FinalDecisionReviewProductionSourceWiringV1
    internal_only: bool = True
    startup_broker_call_performed: bool = False
    public_source_publication_route_created: bool = False
    production_openapi_changed: bool = False
    broker_write_called: bool = False
    trade_authorized: bool = False
    order_created: bool = False
    trading_methods: bool = False


def register_final_decision_review_production_sources(
    *,
    bridge: FinalDecisionReviewWorkflowBridgeV1,
    portfolio_payload_loader: Callable[[], Mapping[str, Any]],
    source_ttl_seconds: int = 900,
    source_capacity: int = 64,
    max_source_age_seconds: int = 900,
    future_tolerance_seconds: int = 60,
) -> FinalDecisionReviewProductionRuntimeV1:
    """Register lazy, internal-only final-review source wiring for production."""
    if not callable(portfolio_payload_loader):
        raise FinalDecisionReviewProductionRegistrationError(
            "FINAL_DECISION_REVIEW_PORTFOLIO_LOADER_NOT_CALLABLE"
        )

    source_store = FinalDecisionReviewScenarioSourceStoreV1(
        ttl_seconds=source_ttl_seconds,
        capacity=source_capacity,
    )
    producer = FinalDecisionReviewWorkflowProducerV1(bridge=bridge)
    coordinator = FinalDecisionReviewWorkflowCoordinatorV1(
        producer=producer,
        max_source_age_seconds=max_source_age_seconds,
        future_tolerance_seconds=future_tolerance_seconds,
    )
    current_risk_loader = build_live_current_risk_loader(
        portfolio_payload_loader=portfolio_payload_loader,
    )
    source_wiring = FinalDecisionReviewProductionSourceWiringV1(
        coordinator=coordinator,
        source_store=source_store,
        current_risk_loader=current_risk_loader,
    )
    return FinalDecisionReviewProductionRuntimeV1(
        source_store=source_store,
        producer=producer,
        coordinator=coordinator,
        source_wiring=source_wiring,
    )
