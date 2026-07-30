from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.capacity import OrderSide
from omni_cio.contracts.v1.decision_capacity_pretrade import (
    CapacityPreTradeDecisionGateV1,
)
from omni_cio.contracts.v1.decision_capacity_sell_pretrade import (
    CapacitySellPreTradeDecisionGateV1,
)
from omni_cio.contracts.v1.final_decision_review_source_acquisition import (
    FinalDecisionReviewSourceAcquisitionOutcomeV1,
    FinalDecisionReviewSourceAcquisitionResultV1,
    FinalDecisionReviewSourceAcquisitionStatus,
)
from omni_cio.contracts.v1.final_decision_review_workflow_coordinator import (
    FinalDecisionReviewWorkflowCoordinatorResultV1,
    FinalDecisionReviewWorkflowCoordinatorStage,
    FinalDecisionReviewWorkflowCoordinatorStatus,
    FinalDecisionReviewWorkflowSourceSlot,
)
from omni_cio.contracts.v1.risk import RiskPolicyEvaluationV1
from omni_cio.release.final_decision_review_source_acquisition_v1 import (
    FinalDecisionReviewSourceAcquisitionAdapterV1,
    FinalDecisionReviewSourceAcquisitionError,
    FinalDecisionReviewSourceLoaderV1,
    purchase_gate_source_loader,
    risk_source_loader,
    sell_gate_source_loader,
)


NOW = datetime(2026, 7, 30, 8, 0, tzinfo=timezone.utc)


class _Loader:
    def __init__(self, value: object | None = None, error: BaseException | None = None):
        self.value = value
        self.error = error
        self.calls = 0

    def __call__(self) -> object | None:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.value


class _FakeCoordinator:
    def __init__(self, *, published: bool = True) -> None:
        self.calls: list[dict[str, object]] = []
        self.published = published

    def coordinate(self, **kwargs: object) -> FinalDecisionReviewWorkflowCoordinatorResultV1:
        self.calls.append(kwargs)
        return FinalDecisionReviewWorkflowCoordinatorResultV1.model_construct(
            status=(
                FinalDecisionReviewWorkflowCoordinatorStatus.PUBLISHED
                if self.published
                else FinalDecisionReviewWorkflowCoordinatorStatus.BLOCKED
            ),
            completed_stage=FinalDecisionReviewWorkflowCoordinatorStage.PRODUCER,
            published=self.published,
            primary_blocker=(None if self.published else "source_evidence_incomplete"),
        )


def _purchase_gate(timestamp: datetime = NOW) -> CapacityPreTradeDecisionGateV1:
    return CapacityPreTradeDecisionGateV1.model_construct(assessed_at=timestamp)


def _sell_gate(timestamp: datetime = NOW) -> CapacitySellPreTradeDecisionGateV1:
    return CapacitySellPreTradeDecisionGateV1.model_construct(assessed_at=timestamp)


def _risk(timestamp: datetime = NOW) -> RiskPolicyEvaluationV1:
    return RiskPolicyEvaluationV1.model_construct(
        metadata=SimpleNamespace(retrieved_at=timestamp)
    )


def _adapter(
    *,
    coordinator: _FakeCoordinator | None = None,
    purchase: _Loader | None = None,
    sell: _Loader | None = None,
    current: _Loader | None = None,
    pro_forma: _Loader | None = None,
):
    coordinator = coordinator or _FakeCoordinator()
    purchase = purchase or _Loader(_purchase_gate())
    sell = sell or _Loader(_sell_gate())
    current = current or _Loader(_risk())
    pro_forma = pro_forma or _Loader(_risk())
    adapter = FinalDecisionReviewSourceAcquisitionAdapterV1(
        coordinator=coordinator,  # type: ignore[arg-type]
        purchase_gate_loader=purchase_gate_source_loader(
            provider="omni-cio",
            operation="load-purchase-gate",
            load=purchase,  # type: ignore[arg-type]
        ),
        sell_gate_loader=sell_gate_source_loader(
            provider="omni-cio",
            operation="load-sell-gate",
            load=sell,  # type: ignore[arg-type]
        ),
        current_risk_loader=risk_source_loader(
            slot=FinalDecisionReviewWorkflowSourceSlot.CURRENT_RISK,
            provider="omni-cio",
            operation="load-current-risk",
            load=current,  # type: ignore[arg-type]
        ),
        pro_forma_risk_loader=risk_source_loader(
            slot=FinalDecisionReviewWorkflowSourceSlot.PRO_FORMA_RISK,
            provider="omni-cio",
            operation="load-pro-forma-risk",
            load=pro_forma,  # type: ignore[arg-type]
        ),
    )
    return adapter, coordinator, purchase, sell, current, pro_forma


def _acquire(adapter: FinalDecisionReviewSourceAcquisitionAdapterV1, direction: OrderSide):
    return adapter.acquire(
        direction=direction,
        scenario_id="scenario-acquisition-1",
        correlation_id="corr:acquisition-0001",
        request_id="request:acquisition-0001",
        acquired_at=NOW,
    )


def test_buy_acquisition_calls_only_three_selected_ports() -> None:
    adapter, coordinator, purchase, sell, current, pro_forma = _adapter()
    result = _acquire(adapter, OrderSide.BUY)

    assert result.published is True
    assert purchase.calls == 1
    assert sell.calls == 0
    assert current.calls == 1
    assert pro_forma.calls == 1
    assert len(coordinator.calls) == 1
    call = coordinator.calls[0]
    assert call["purchase_gate"] is purchase.value
    assert call["sell_gate"] is None
    assert call["current_risk_evaluation"] is current.value
    assert call["pro_forma_risk_evaluation"] is pro_forma.value
    assert result.attempted_source_count == 3
    assert result.available_source_count == 3
    assert result.missing_source_count == 1
    assert result.failed_source_count == 0
    assert result.timeout_source_count == 0
    assert result.exact_slot_set_confirmed is True
    assert result.evidence_artifact_correspondence_confirmed is True
    assert result.payload_logged is False
    assert result.credentials_logged is False
    assert result.full_account_logged is False
    assert result.exception_text_logged is False
    assert result.broker_write_called is False
    assert result.trade_authorized is False
    assert result.trading_methods is False


def test_sell_acquisition_never_calls_purchase_port() -> None:
    adapter, coordinator, purchase, sell, current, pro_forma = _adapter()
    result = _acquire(adapter, OrderSide.SELL)

    assert result.published is True
    assert purchase.calls == 0
    assert sell.calls == 1
    assert current.calls == 1
    assert pro_forma.calls == 1
    call = coordinator.calls[0]
    assert call["purchase_gate"] is None
    assert call["sell_gate"] is sell.value


def test_missing_source_is_explicit_and_coordinator_receives_none() -> None:
    coordinator = _FakeCoordinator(published=False)
    missing_current = _Loader(None)
    adapter, _, _, sell, _, _ = _adapter(
        coordinator=coordinator,
        current=missing_current,
    )
    result = _acquire(adapter, OrderSide.BUY)

    assert result.published is False
    assert sell.calls == 0
    assert result.available_source_count == 2
    assert result.missing_source_count == 2
    assert result.failed_source_count == 0
    current_outcome = next(
        row
        for row in result.outcomes
        if row.slot is FinalDecisionReviewWorkflowSourceSlot.CURRENT_RISK
    )
    assert current_outcome.status is FinalDecisionReviewSourceAcquisitionStatus.MISSING
    assert current_outcome.attempted is True
    assert current_outcome.artifact_present is False
    assert coordinator.calls[0]["current_risk_evaluation"] is None


def test_timeout_exception_and_wrong_type_are_safe_failed_outcomes() -> None:
    coordinator = _FakeCoordinator(published=False)
    adapter, _, _, _, _, _ = _adapter(
        coordinator=coordinator,
        purchase=_Loader(error=TimeoutError("private timeout detail")),
        current=_Loader(error=RuntimeError("private source detail")),
        pro_forma=_Loader(object()),
    )
    result = _acquire(adapter, OrderSide.BUY)

    assert result.published is False
    assert result.failed_source_count == 3
    assert result.timeout_source_count == 1
    codes = {row.slot: row.error_code for row in result.outcomes}
    assert codes[FinalDecisionReviewWorkflowSourceSlot.PURCHASE_GATE] == "SOURCE_TIMEOUT"
    assert codes[FinalDecisionReviewWorkflowSourceSlot.CURRENT_RISK] == "SOURCE_LOAD_FAILED"
    assert codes[FinalDecisionReviewWorkflowSourceSlot.PRO_FORMA_RISK] == "SOURCE_TYPE_INVALID"
    assert "private" not in result.model_dump_json().lower()
    assert result.exception_text_logged is False


def test_naive_or_missing_artifact_timestamp_is_failed_without_payload() -> None:
    coordinator = _FakeCoordinator(published=False)
    naive = _Loader(_purchase_gate(NOW.replace(tzinfo=None)))
    adapter, _, _, _, _, _ = _adapter(
        coordinator=coordinator,
        purchase=naive,
    )
    result = _acquire(adapter, OrderSide.BUY)
    purchase_outcome = next(
        row
        for row in result.outcomes
        if row.slot is FinalDecisionReviewWorkflowSourceSlot.PURCHASE_GATE
    )
    assert purchase_outcome.error_code == "SOURCE_TIMESTAMP_INVALID"
    assert purchase_outcome.artifact_present is False


def test_loader_set_and_risk_slot_are_validated() -> None:
    loader = _Loader(_risk())
    with pytest.raises(
        FinalDecisionReviewSourceAcquisitionError,
        match="FINAL_DECISION_REVIEW_RISK_SOURCE_SLOT_INVALID",
    ):
        risk_source_loader(
            slot=FinalDecisionReviewWorkflowSourceSlot.PURCHASE_GATE,
            provider="omni-cio",
            operation="invalid-risk-slot",
            load=loader,  # type: ignore[arg-type]
        )

    coordinator = _FakeCoordinator()
    purchase_loader = purchase_gate_source_loader(
        provider="omni-cio",
        operation="load-purchase-gate",
        load=_Loader(_purchase_gate()),  # type: ignore[arg-type]
    )
    with pytest.raises(
        FinalDecisionReviewSourceAcquisitionError,
        match="FINAL_DECISION_REVIEW_SOURCE_LOADER_SET_INVALID",
    ):
        FinalDecisionReviewSourceAcquisitionAdapterV1(
            coordinator=coordinator,  # type: ignore[arg-type]
            purchase_gate_loader=purchase_loader,
            sell_gate_loader=purchase_loader,
            current_risk_loader=risk_source_loader(
                slot=FinalDecisionReviewWorkflowSourceSlot.CURRENT_RISK,
                provider="omni-cio",
                operation="load-current-risk",
                load=_Loader(_risk()),  # type: ignore[arg-type]
            ),
            pro_forma_risk_loader=risk_source_loader(
                slot=FinalDecisionReviewWorkflowSourceSlot.PRO_FORMA_RISK,
                provider="omni-cio",
                operation="load-pro-forma-risk",
                load=_Loader(_risk()),  # type: ignore[arg-type]
            ),
        )


def test_result_and_outcome_tampering_are_rejected() -> None:
    adapter, _, _, _, _, _ = _adapter()
    result = _acquire(adapter, OrderSide.BUY)
    payload = result.model_dump(mode="python")
    payload["trade_authorized"] = True
    with pytest.raises(ValidationError):
        FinalDecisionReviewSourceAcquisitionResultV1.model_validate(payload)

    outcome = result.outcomes[0]
    outcome_payload = outcome.model_dump(mode="python")
    outcome_payload["artifact_present"] = not outcome.artifact_present
    with pytest.raises(ValidationError):
        FinalDecisionReviewSourceAcquisitionOutcomeV1.model_validate(outcome_payload)


def test_adapter_source_has_no_broker_write_or_exception_logging_surface() -> None:
    source = Path(
        "omni_cio/release/final_decision_review_source_acquisition_v1.py"
    ).read_text(encoding="utf-8").lower()
    forbidden = (
        ".post_order(",
        ".cancel_order(",
        ".replace_order(",
        "logger.exception",
        "traceback",
    )
    assert all(marker not in source for marker in forbidden)
