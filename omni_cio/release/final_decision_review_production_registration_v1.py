from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from omni_cio.release.final_decision_review_approved_invocation_v1 import (
    FinalDecisionReviewApprovedInvocationV1,
)
from omni_cio.release.final_decision_review_approved_owner_acquisition_v1 import (
    FinalDecisionReviewApprovedOwnerAcquisitionV1,
    FinalDecisionReviewApprovedOwnerSourceLoadersV1,
    FinalDecisionReviewApprovedServerContextV1,
    unavailable_final_decision_review_approved_owner_source_loaders,
)
from omni_cio.release.final_decision_review_approved_owner_installation_v1 import (
    FinalDecisionReviewApprovedOwnerInstallationV1,
)
from omni_cio.release.final_decision_review_authenticated_route_context_v1 import (
    FinalDecisionReviewApprovedRouteContextStoreV1,
)
from omni_cio.release.final_decision_review_calculator_handoff_v1 import (
    FinalDecisionReviewCalculatorScenarioHandoffV1,
)
from omni_cio.release.final_decision_review_calculator_intent_workflow_v1 import (
    FinalDecisionReviewCalculatorIntentWorkflowV1,
)
from omni_cio.release.final_decision_review_calculator_provider_registry_v1 import (
    FinalDecisionReviewCalculatorProviderRegistryV1,
)
from omni_cio.release.final_decision_review_production_owner_callables_v1 import (
    FinalDecisionReviewProductionOwnerCallableRegistrationV1,
    FinalDecisionReviewProductionOwnerCallableStoreV1,
    register_final_decision_review_production_owner_callables,
)
from omni_cio.release.final_decision_review_production_sources_v1 import (
    FinalDecisionReviewProductionSourceWiringV1,
    FinalDecisionReviewScenarioSourceStoreV1,
    build_live_current_risk_loader,
)
from omni_cio.release.final_decision_review_trusted_scenario_publisher_v1 import (
    FinalDecisionReviewTrustedScenarioPublisherV1,
)
from omni_cio.release.final_decision_review_trusted_owner_composition_v1 import (
    FinalDecisionReviewTrustedOwnerCompositionV1,
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
    scenario_publisher: FinalDecisionReviewTrustedScenarioPublisherV1
    calculator_handoff: FinalDecisionReviewCalculatorScenarioHandoffV1
    calculator_intent_workflow: FinalDecisionReviewCalculatorIntentWorkflowV1
    approved_invocation: FinalDecisionReviewApprovedInvocationV1
    provider_registry: FinalDecisionReviewCalculatorProviderRegistryV1
    owner_callable_store: FinalDecisionReviewProductionOwnerCallableStoreV1
    owner_callable_registration: (
        FinalDecisionReviewProductionOwnerCallableRegistrationV1
    )
    trusted_owner_composition: FinalDecisionReviewTrustedOwnerCompositionV1
    approved_owner_installation: FinalDecisionReviewApprovedOwnerInstallationV1
    approved_owner_acquisition: FinalDecisionReviewApprovedOwnerAcquisitionV1
    approved_route_context_store: FinalDecisionReviewApprovedRouteContextStoreV1
    producer: FinalDecisionReviewWorkflowProducerV1
    coordinator: FinalDecisionReviewWorkflowCoordinatorV1
    source_wiring: FinalDecisionReviewProductionSourceWiringV1
    internal_only: bool = True
    authenticated_route_context_capture_registered: bool = True
    startup_authenticated_context_count: int = 0
    startup_broker_call_performed: bool = False
    startup_owner_installation_performed: bool = False
    startup_owner_acquisition_performed: bool = False
    public_source_publication_route_created: bool = False
    production_openapi_changed: bool = False
    broker_write_called: bool = False
    trade_authorized: bool = False
    order_created: bool = False
    trading_methods: bool = False


def _missing_approved_owner_context(
) -> FinalDecisionReviewApprovedServerContextV1 | None:
    return None


def _route_context_store_for_bridge(
    bridge: FinalDecisionReviewWorkflowBridgeV1,
    *,
    capacity: int,
) -> FinalDecisionReviewApprovedRouteContextStoreV1:
    observer = bridge.registry.approved_context_observer
    existing_store = getattr(observer, "__self__", None)
    if isinstance(existing_store, FinalDecisionReviewApprovedRouteContextStoreV1):
        return existing_store
    if observer is not None:
        raise FinalDecisionReviewProductionRegistrationError(
            "FINAL_DECISION_REVIEW_ROUTE_CONTEXT_OBSERVER_CONFLICT"
        )
    store = FinalDecisionReviewApprovedRouteContextStoreV1(
        ttl_seconds=300,
        capacity=capacity,
    )
    bridge.registry.attach_approved_context_observer(store.capture)
    return store


def register_final_decision_review_production_sources(
    *,
    bridge: FinalDecisionReviewWorkflowBridgeV1,
    portfolio_payload_loader: Callable[[], Mapping[str, Any]],
    source_ttl_seconds: int = 900,
    source_capacity: int = 64,
    max_source_age_seconds: int = 900,
    future_tolerance_seconds: int = 60,
    approved_owner_context_loader: Callable[
        [],
        FinalDecisionReviewApprovedServerContextV1 | None,
    ]
    | None = None,
    approved_owner_source_loaders: (
        FinalDecisionReviewApprovedOwnerSourceLoadersV1 | None
    ) = None,
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
    scenario_publisher = FinalDecisionReviewTrustedScenarioPublisherV1(
        source_store=source_store,
        max_source_age_seconds=max_source_age_seconds,
        future_tolerance_seconds=future_tolerance_seconds,
    )
    calculator_handoff = FinalDecisionReviewCalculatorScenarioHandoffV1(
        publisher=scenario_publisher,
    )
    calculator_intent_workflow = FinalDecisionReviewCalculatorIntentWorkflowV1(
        handoff=calculator_handoff,
    )
    approved_invocation = FinalDecisionReviewApprovedInvocationV1(
        workflow=calculator_intent_workflow,
    )
    provider_registry = FinalDecisionReviewCalculatorProviderRegistryV1(
        invocation=approved_invocation,
    )
    owner_callable_store = FinalDecisionReviewProductionOwnerCallableStoreV1(
        ttl_seconds=source_ttl_seconds,
        capacity=source_capacity,
    )
    owner_callable_registration = (
        register_final_decision_review_production_owner_callables(
            registry=provider_registry,
            store=owner_callable_store,
        )
    )
    trusted_owner_composition = FinalDecisionReviewTrustedOwnerCompositionV1(
        registry=provider_registry,
        store=owner_callable_store,
    )
    approved_owner_installation = FinalDecisionReviewApprovedOwnerInstallationV1(
        composition=trusted_owner_composition,
    )
    approved_owner_acquisition = (
        FinalDecisionReviewApprovedOwnerAcquisitionV1(
            composition=trusted_owner_composition,
            context_loader=(
                approved_owner_context_loader
                or _missing_approved_owner_context
            ),
            source_loaders=(
                approved_owner_source_loaders
                or unavailable_final_decision_review_approved_owner_source_loaders()
            ),
        )
    )
    approved_route_context_store = _route_context_store_for_bridge(
        bridge,
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
        scenario_publisher=scenario_publisher,
        calculator_handoff=calculator_handoff,
        calculator_intent_workflow=calculator_intent_workflow,
        approved_invocation=approved_invocation,
        provider_registry=provider_registry,
        owner_callable_store=owner_callable_store,
        owner_callable_registration=owner_callable_registration,
        trusted_owner_composition=trusted_owner_composition,
        approved_owner_installation=approved_owner_installation,
        approved_owner_acquisition=approved_owner_acquisition,
        approved_route_context_store=approved_route_context_store,
        producer=producer,
        coordinator=coordinator,
        source_wiring=source_wiring,
    )
