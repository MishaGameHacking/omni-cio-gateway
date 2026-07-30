from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from omni_cio.contracts.v1.capacity import OrderSide
from omni_cio.contracts.v1.decision_capacity_pretrade import (
    CapacityPreTradeDecisionGateV1,
)
from omni_cio.contracts.v1.decision_capacity_sell_pretrade import (
    CapacitySellPreTradeDecisionGateV1,
)
from omni_cio.contracts.v1.final_decision_review_workflow_coordinator import (
    FinalDecisionReviewWorkflowCoordinatorResultV1,
    FinalDecisionReviewWorkflowCoordinatorStage,
    FinalDecisionReviewWorkflowCoordinatorStatus,
)
from omni_cio.contracts.v1.risk import RiskPolicyEvaluationV1
import omni_cio.release.final_decision_review_production_sources_v1 as subject


NOW = datetime(2026, 7, 30, 8, 0, tzinfo=timezone.utc)


class _FakeCoordinator:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def coordinate(self, **kwargs: object) -> FinalDecisionReviewWorkflowCoordinatorResultV1:
        self.calls.append(kwargs)
        return FinalDecisionReviewWorkflowCoordinatorResultV1.model_construct(
            status=FinalDecisionReviewWorkflowCoordinatorStatus.PUBLISHED,
            completed_stage=FinalDecisionReviewWorkflowCoordinatorStage.PRODUCER,
            published=True,
            primary_blocker=None,
        )



def _purchase_gate(timestamp: datetime = NOW) -> CapacityPreTradeDecisionGateV1:
    return CapacityPreTradeDecisionGateV1.model_construct(assessed_at=timestamp)



def _sell_gate(timestamp: datetime = NOW) -> CapacitySellPreTradeDecisionGateV1:
    return CapacitySellPreTradeDecisionGateV1.model_construct(assessed_at=timestamp)



def _risk(timestamp: datetime = NOW) -> RiskPolicyEvaluationV1:
    return RiskPolicyEvaluationV1.model_construct(
        metadata=SimpleNamespace(retrieved_at=timestamp)
    )



def test_store_publishes_exact_bundle_and_replaces_same_scenario() -> None:
    store = subject.FinalDecisionReviewScenarioSourceStoreV1(
        ttl_seconds=900,
        capacity=2,
    )
    first = store.publish(
        scenario_id="scenario-1",
        purchase_gate=_purchase_gate(),
        pro_forma_risk=_risk(),
        published_at=NOW,
    )
    assert first.replaced is False
    assert first.evicted is False
    assert first.active_bundle_count == 1
    assert first.http_publication_method_created is False
    assert first.broker_write_called is False
    assert first.trading_methods is False

    replacement = store.publish(
        scenario_id="scenario-1",
        sell_gate=_sell_gate(),
        pro_forma_risk=_risk(),
        published_at=NOW + timedelta(seconds=1),
    )
    bundle = store.load_bundle(
        "scenario-1",
        checked_at=NOW + timedelta(seconds=1),
    )
    assert replacement.replaced is True
    assert bundle is not None
    assert bundle.direction is OrderSide.SELL
    assert bundle.purchase_gate is None
    assert bundle.sell_gate is not None



def test_store_expires_and_evicts_oldest_bundle() -> None:
    store = subject.FinalDecisionReviewScenarioSourceStoreV1(
        ttl_seconds=10,
        capacity=1,
    )
    store.publish(
        scenario_id="scenario-a",
        purchase_gate=_purchase_gate(),
        pro_forma_risk=_risk(),
        published_at=NOW,
    )
    second = store.publish(
        scenario_id="scenario-b",
        sell_gate=_sell_gate(),
        pro_forma_risk=_risk(),
        published_at=NOW + timedelta(seconds=1),
    )
    assert second.evicted is True
    assert store.load_bundle("scenario-a", checked_at=NOW + timedelta(seconds=1)) is None
    assert store.active_bundle_count(checked_at=NOW + timedelta(seconds=1)) == 1
    assert store.load_bundle("scenario-b", checked_at=NOW + timedelta(seconds=12)) is None
    assert store.active_bundle_count(checked_at=NOW + timedelta(seconds=12)) == 0



def test_store_rejects_invalid_direction_and_timestamp() -> None:
    store = subject.FinalDecisionReviewScenarioSourceStoreV1()
    with pytest.raises(
        subject.FinalDecisionReviewProductionSourceError,
        match="FINAL_DECISION_REVIEW_PRODUCTION_SOURCE_DIRECTION_INVALID",
    ):
        store.publish(
            scenario_id="scenario-invalid",
            purchase_gate=_purchase_gate(),
            sell_gate=_sell_gate(),
            pro_forma_risk=_risk(),
            published_at=NOW,
        )
    with pytest.raises(
        subject.FinalDecisionReviewProductionSourceError,
        match="FINAL_DECISION_REVIEW_PRODUCTION_SOURCE_TIMESTAMP_MUST_BE_AWARE",
    ):
        store.publish(
            scenario_id="scenario-invalid-time",
            purchase_gate=_purchase_gate(),
            pro_forma_risk=_risk(),
            published_at=NOW.replace(tzinfo=None),
        )



def test_live_current_risk_loader_uses_existing_contract_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, object]] = []
    snapshot = SimpleNamespace(metadata=SimpleNamespace(retrieved_at=NOW))
    analytics = SimpleNamespace(metadata=SimpleNamespace(retrieved_at=NOW))
    expected = _risk()

    def adapt(payload: object) -> object:
        calls.append(("adapt", payload))
        return snapshot

    def analyze(value: object, *, retrieved_at: datetime) -> object:
        calls.append(("analyze", (value, retrieved_at)))
        return analytics

    def evaluate(value: object, *, evaluated_at: datetime) -> RiskPolicyEvaluationV1:
        calls.append(("evaluate", (value, evaluated_at)))
        return expected

    monkeypatch.setattr(subject, "portfolio_snapshot_v1_from_market_payload", adapt)
    monkeypatch.setattr(subject, "build_advanced_portfolio_analytics", analyze)
    monkeypatch.setattr(subject, "evaluate_conservative_risk_policy", evaluate)

    loader = subject.build_live_current_risk_loader(
        portfolio_payload_loader=lambda: {"status": "ok"}
    )
    assert loader() is expected
    assert calls == [
        ("adapt", {"status": "ok"}),
        ("analyze", (snapshot, NOW)),
        ("evaluate", (analytics, NOW)),
    ]



def test_production_wiring_loads_selected_direction_live_risk_and_pro_forma() -> None:
    coordinator = _FakeCoordinator()
    store = subject.FinalDecisionReviewScenarioSourceStoreV1()
    current_risk = _risk()
    pro_forma_risk = _risk()
    purchase_gate = _purchase_gate()
    store.publish(
        scenario_id="scenario-ready",
        purchase_gate=purchase_gate,
        pro_forma_risk=pro_forma_risk,
        published_at=NOW,
    )
    wiring = subject.FinalDecisionReviewProductionSourceWiringV1(
        coordinator=coordinator,  # type: ignore[arg-type]
        source_store=store,
        current_risk_loader=lambda: current_risk,
    )

    result = wiring.acquire(
        direction=OrderSide.BUY,
        scenario_id="scenario-ready",
        correlation_id="corr:production-source-0001",
        request_id="request:production-source-0001",
        acquired_at=NOW,
    )

    assert result.published is True
    assert result.available_source_count == 3
    assert result.missing_source_count == 1
    assert result.failed_source_count == 0
    assert len(coordinator.calls) == 1
    call = coordinator.calls[0]
    assert call["purchase_gate"] is purchase_gate
    assert call["sell_gate"] is None
    assert call["current_risk_evaluation"] is current_risk
    assert call["pro_forma_risk_evaluation"] is pro_forma_risk
    assert result.user_controlled_publication_surface is False
    assert result.broker_write_called is False
    assert result.trade_authorized is False
    assert result.trading_methods is False



def test_production_wiring_reports_missing_scenario_without_fabricating_sources() -> None:
    coordinator = _FakeCoordinator()
    wiring = subject.FinalDecisionReviewProductionSourceWiringV1(
        coordinator=coordinator,  # type: ignore[arg-type]
        source_store=subject.FinalDecisionReviewScenarioSourceStoreV1(),
        current_risk_loader=lambda: _risk(),
    )
    result = wiring.acquire(
        direction=OrderSide.SELL,
        scenario_id="scenario-missing",
        correlation_id="corr:production-source-0002",
        acquired_at=NOW,
    )
    assert result.available_source_count == 1
    assert result.missing_source_count == 3
    call = coordinator.calls[0]
    assert call["purchase_gate"] is None
    assert call["sell_gate"] is None
    assert call["pro_forma_risk_evaluation"] is None



def test_source_module_contains_no_broker_write_or_public_route_surface() -> None:
    source = open(
        "omni_cio/release/final_decision_review_production_sources_v1.py",
        encoding="utf-8",
    ).read().lower()
    forbidden = (
        ".post_order(",
        ".cancel_order(",
        ".replace_order(",
        "@app.post",
        "@app.put",
        "@app.delete",
        "logger.exception",
    )
    assert all(marker not in source for marker in forbidden)
