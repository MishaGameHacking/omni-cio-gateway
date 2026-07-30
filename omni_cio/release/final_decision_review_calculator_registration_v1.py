from __future__ import annotations

from dataclasses import dataclass

from omni_cio.release.final_decision_review_calculator_publication_v1 import (
    FinalDecisionReviewCalculatorScenarioPublisherV1,
)
from omni_cio.release.final_decision_review_production_sources_v1 import (
    FinalDecisionReviewScenarioSourceStoreV1,
)


class FinalDecisionReviewCalculatorRegistrationError(ValueError):
    """Calculator publisher registration cannot be completed safely."""


@dataclass(frozen=True, slots=True)
class FinalDecisionReviewCalculatorRegistrationV1:
    source_store: FinalDecisionReviewScenarioSourceStoreV1
    publisher: FinalDecisionReviewCalculatorScenarioPublisherV1
    internal_only: bool = True
    lazy_registration: bool = True
    startup_calculation_called: bool = False
    startup_broker_called: bool = False
    http_publication_method_created: bool = False
    trade_authorized: bool = False
    order_created: bool = False
    trading_methods: bool = False

    def __post_init__(self) -> None:
        if self.publisher.source_store is not self.source_store:
            raise FinalDecisionReviewCalculatorRegistrationError(
                "FINAL_DECISION_REVIEW_CALCULATOR_REGISTRATION_STORE_IDENTITY_MISMATCH"
            )
        if (
            not self.internal_only
            or not self.lazy_registration
            or self.startup_calculation_called
            or self.startup_broker_called
            or self.http_publication_method_created
            or self.trade_authorized
            or self.order_created
            or self.trading_methods
        ):
            raise FinalDecisionReviewCalculatorRegistrationError(
                "FINAL_DECISION_REVIEW_CALCULATOR_REGISTRATION_SAFETY_INVARIANT_FAILED"
            )


def register_final_decision_review_calculator_publisher(
    *,
    source_store: FinalDecisionReviewScenarioSourceStoreV1,
    max_source_skew_seconds: int = 30,
    max_publication_delay_seconds: int = 300,
) -> FinalDecisionReviewCalculatorRegistrationV1:
    """Create one lazy process-local calculator publisher for an existing store."""

    if not isinstance(source_store, FinalDecisionReviewScenarioSourceStoreV1):
        raise FinalDecisionReviewCalculatorRegistrationError(
            "FINAL_DECISION_REVIEW_CALCULATOR_REGISTRATION_STORE_TYPE_INVALID"
        )
    publisher = FinalDecisionReviewCalculatorScenarioPublisherV1(
        source_store=source_store,
        max_source_skew_seconds=max_source_skew_seconds,
        max_publication_delay_seconds=max_publication_delay_seconds,
    )
    return FinalDecisionReviewCalculatorRegistrationV1(
        source_store=source_store,
        publisher=publisher,
    )
