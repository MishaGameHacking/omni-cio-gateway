from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import app as gateway
from omni_cio.release.final_decision_review_approved_owner_installation_v1 import (
    FinalDecisionReviewApprovedOwnerInstallationV1,
)
from omni_cio.release.final_decision_review_authenticated_route_context_v1 import (
    FinalDecisionReviewApprovedRouteContextStoreV1,
)
from omni_cio.release.final_decision_review_existing_calculator_providers_v1 import (
    PURCHASE_PROVIDER_ID,
    SELL_PROVIDER_ID,
)
from omni_cio.release.final_decision_review_production_owner_callables_v1 import (
    FinalDecisionReviewProductionOwnerCallableRegistrationV1,
    FinalDecisionReviewProductionOwnerCallableStoreV1,
)
from omni_cio.release.final_decision_review_production_registration_v1 import (
    FinalDecisionReviewProductionRuntimeV1,
    register_final_decision_review_production_sources,
)
from omni_cio.release.final_decision_review_production_sources_v1 import (
    FinalDecisionReviewProductionSourceWiringV1,
    FinalDecisionReviewScenarioSourceStoreV1,
)
from omni_cio.release.final_decision_review_trusted_owner_composition_v1 import (
    FinalDecisionReviewTrustedOwnerCompositionV1,
)
from omni_cio.release.final_decision_review_workflow_coordinator_v1 import (
    FinalDecisionReviewWorkflowCoordinatorV1,
)
from omni_cio.release.final_decision_review_workflow_producer_v1 import (
    FinalDecisionReviewWorkflowProducerV1,
)


def test_production_runtime_is_registered_without_startup_broker_call() -> None:
    runtime = gateway.final_decision_review_production_runtime
    assert isinstance(runtime, FinalDecisionReviewProductionRuntimeV1)
    assert isinstance(runtime.source_store, FinalDecisionReviewScenarioSourceStoreV1)
    assert isinstance(
        runtime.owner_callable_store,
        FinalDecisionReviewProductionOwnerCallableStoreV1,
    )
    assert isinstance(
        runtime.owner_callable_registration,
        FinalDecisionReviewProductionOwnerCallableRegistrationV1,
    )
    assert isinstance(
        runtime.trusted_owner_composition,
        FinalDecisionReviewTrustedOwnerCompositionV1,
    )
    assert isinstance(
        runtime.approved_owner_installation,
        FinalDecisionReviewApprovedOwnerInstallationV1,
    )
    assert isinstance(
        runtime.approved_route_context_store,
        FinalDecisionReviewApprovedRouteContextStoreV1,
    )
    assert isinstance(runtime.producer, FinalDecisionReviewWorkflowProducerV1)
    assert isinstance(runtime.coordinator, FinalDecisionReviewWorkflowCoordinatorV1)
    assert isinstance(
        runtime.source_wiring, FinalDecisionReviewProductionSourceWiringV1
    )
    assert runtime.producer.bridge is gateway.final_decision_review_workflow_bridge
    assert runtime.coordinator.producer is runtime.producer
    assert runtime.source_wiring.coordinator is runtime.coordinator
    assert runtime.source_wiring.source_store is runtime.source_store
    assert runtime.source_store.active_bundle_count() == 0
    assert runtime.owner_callable_store.active_bundle_count() == 0
    assert runtime.owner_callable_store.active_pin_count() == 0
    assert (
        runtime.owner_callable_registration.purchase_provider_id == PURCHASE_PROVIDER_ID
    )
    assert runtime.owner_callable_registration.sell_provider_id == SELL_PROVIDER_ID
    assert runtime.owner_callable_registration.registered_provider_count == 2
    assert runtime.owner_callable_registration.startup_owner_call_performed is False
    assert runtime.trusted_owner_composition.registry is runtime.provider_registry
    assert runtime.trusted_owner_composition.store is runtime.owner_callable_store
    assert (
        runtime.approved_owner_installation.composition
        is runtime.trusted_owner_composition
    )
    observer = gateway.final_decision_review_registry.approved_context_observer
    assert getattr(observer, "__self__", None) is runtime.approved_route_context_store
    assert runtime.internal_only is True
    assert runtime.authenticated_route_context_capture_registered is True
    assert runtime.startup_authenticated_context_count == 0
    assert runtime.startup_broker_call_performed is False
    assert runtime.startup_owner_installation_performed is False
    assert runtime.startup_owner_acquisition_performed is False
    assert runtime.public_source_publication_route_created is False
    assert runtime.production_openapi_changed is False
    assert runtime.broker_write_called is False
    assert runtime.trade_authorized is False
    assert runtime.order_created is False
    assert runtime.trading_methods is False
    assert "final_decision_review_production_sources" in gateway.base.CAPABILITIES


def test_registration_keeps_portfolio_loader_and_owner_store_lazy() -> None:
    calls = 0

    def portfolio_loader() -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return {"status": "not-called-during-registration"}

    runtime = register_final_decision_review_production_sources(
        bridge=gateway.final_decision_review_workflow_bridge,
        portfolio_payload_loader=portfolio_loader,
    )
    assert calls == 0
    assert runtime.source_store.active_bundle_count() == 0
    assert runtime.owner_callable_store.active_bundle_count() == 0
    assert runtime.owner_callable_store.active_pin_count() == 0
    assert (
        runtime.approved_route_context_store
        is gateway.final_decision_review_production_runtime.approved_route_context_store
    )
    assert runtime.owner_callable_registration.registered_provider_count == 2
    assert runtime.trusted_owner_composition.registry is runtime.provider_registry
    assert runtime.trusted_owner_composition.store is runtime.owner_callable_store
    assert (
        runtime.approved_owner_installation.composition
        is runtime.trusted_owner_composition
    )
    assert runtime.startup_authenticated_context_count == 0
    assert runtime.startup_owner_installation_performed is False


def test_production_portfolio_loader_uses_existing_read_only_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = {"status": "ok", "trading_methods": False}
    captured: dict[str, object] = {}

    def fake_snapshot(**kwargs: object) -> dict[str, Any]:
        captured.update(kwargs)
        return expected

    monkeypatch.setattr(
        gateway.portfolio_market_engine,
        "get_portfolio_market_snapshot",
        fake_snapshot,
    )
    assert gateway._load_final_decision_review_portfolio_payload() is expected
    assert captured["base"] is gateway.base
    assert captured["app_version"] == gateway.APP_VERSION
    assert captured["market_dealer_session"] is gateway.legacy.market_dealer_session
    assert (
        captured["trading_flag_consistency_issues"]
        is gateway.legacy.trading_flag_consistency_issues
    )
    assert captured["depth"] == 1
    assert captured["max_instruments"] == 50


def test_registration_does_not_change_get_only_action_surface() -> None:
    schema = gateway.app.openapi()
    operations = [
        (path, method, operation)
        for path, path_item in schema["paths"].items()
        for method, operation in path_item.items()
        if method.lower() in {"get", "post", "put", "patch", "delete"}
    ]
    assert len(operations) == 14
    assert all(method.lower() == "get" for _, method, _ in operations)
    assert all("requestBody" not in operation for _, _, operation in operations)


def test_registration_source_has_no_route_or_broker_write_surface() -> None:
    sources = (
        Path("omni_cio/release/final_decision_review_production_registration_v1.py"),
        Path("omni_cio/release/final_decision_review_production_owner_callables_v1.py"),
        Path(
            "omni_cio/release/" "final_decision_review_trusted_owner_composition_v1.py"
        ),
        Path(
            "omni_cio/release/"
            "final_decision_review_approved_owner_installation_v1.py"
        ),
        Path(
            "omni_cio/release/"
            "final_decision_review_authenticated_route_context_v1.py"
        ),
        Path("app.py"),
    )
    text = "\n".join(path.read_text(encoding="utf-8").lower() for path in sources)
    forbidden = (
        "@app.post",
        "@app.put",
        "@app.patch",
        "@app.delete",
        ".post_order(",
        ".cancel_order(",
        ".replace_order(",
    )
    assert all(marker not in text for marker in forbidden)
