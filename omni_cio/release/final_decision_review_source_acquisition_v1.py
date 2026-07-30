from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import cast

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
    FinalDecisionReviewWorkflowSourceEvidenceV1,
    FinalDecisionReviewWorkflowSourceSlot,
)
from omni_cio.contracts.v1.risk import RiskPolicyEvaluationV1
from omni_cio.release.final_decision_review_workflow_coordinator_v1 import (
    FinalDecisionReviewWorkflowCoordinatorError,
    FinalDecisionReviewWorkflowCoordinatorV1,
    available_final_decision_review_workflow_source,
    failed_final_decision_review_workflow_source,
    missing_final_decision_review_workflow_source,
)


class FinalDecisionReviewSourceAcquisitionError(ValueError):
    """Read-only workflow sources cannot be acquired safely."""


@dataclass(frozen=True, slots=True)
class FinalDecisionReviewSourceLoaderV1:
    slot: FinalDecisionReviewWorkflowSourceSlot
    provider: str
    operation: str
    expected_type: type[object]
    load: Callable[[], object | None]
    observed_at: Callable[[object], datetime]

    def __post_init__(self) -> None:
        if not 3 <= len(self.provider) <= 128:
            raise FinalDecisionReviewSourceAcquisitionError(
                "FINAL_DECISION_REVIEW_SOURCE_PROVIDER_INVALID"
            )
        if not 3 <= len(self.operation) <= 128:
            raise FinalDecisionReviewSourceAcquisitionError(
                "FINAL_DECISION_REVIEW_SOURCE_OPERATION_INVALID"
            )


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise FinalDecisionReviewSourceAcquisitionError(
            "FINAL_DECISION_REVIEW_SOURCE_ACQUISITION_TIMESTAMP_MUST_BE_AWARE"
        )
    return result.astimezone(timezone.utc)


def _gate_timestamp(value: object) -> datetime:
    return cast(datetime, getattr(value, "assessed_at"))


def _risk_timestamp(value: object) -> datetime:
    metadata = getattr(value, "metadata")
    return cast(datetime, getattr(metadata, "retrieved_at"))


def purchase_gate_source_loader(
    *,
    provider: str,
    operation: str,
    load: Callable[[], CapacityPreTradeDecisionGateV1 | None],
) -> FinalDecisionReviewSourceLoaderV1:
    return FinalDecisionReviewSourceLoaderV1(
        slot=FinalDecisionReviewWorkflowSourceSlot.PURCHASE_GATE,
        provider=provider,
        operation=operation,
        expected_type=CapacityPreTradeDecisionGateV1,
        load=load,
        observed_at=_gate_timestamp,
    )


def sell_gate_source_loader(
    *,
    provider: str,
    operation: str,
    load: Callable[[], CapacitySellPreTradeDecisionGateV1 | None],
) -> FinalDecisionReviewSourceLoaderV1:
    return FinalDecisionReviewSourceLoaderV1(
        slot=FinalDecisionReviewWorkflowSourceSlot.SELL_GATE,
        provider=provider,
        operation=operation,
        expected_type=CapacitySellPreTradeDecisionGateV1,
        load=load,
        observed_at=_gate_timestamp,
    )


def risk_source_loader(
    *,
    slot: FinalDecisionReviewWorkflowSourceSlot,
    provider: str,
    operation: str,
    load: Callable[[], RiskPolicyEvaluationV1 | None],
) -> FinalDecisionReviewSourceLoaderV1:
    if slot not in {
        FinalDecisionReviewWorkflowSourceSlot.CURRENT_RISK,
        FinalDecisionReviewWorkflowSourceSlot.PRO_FORMA_RISK,
    }:
        raise FinalDecisionReviewSourceAcquisitionError(
            "FINAL_DECISION_REVIEW_RISK_SOURCE_SLOT_INVALID"
        )
    return FinalDecisionReviewSourceLoaderV1(
        slot=slot,
        provider=provider,
        operation=operation,
        expected_type=RiskPolicyEvaluationV1,
        load=load,
        observed_at=_risk_timestamp,
    )


def _missing_outcome(
    loader: FinalDecisionReviewSourceLoaderV1,
    *,
    attempted: bool,
) -> FinalDecisionReviewSourceAcquisitionOutcomeV1:
    return FinalDecisionReviewSourceAcquisitionOutcomeV1(
        slot=loader.slot,
        status=FinalDecisionReviewSourceAcquisitionStatus.MISSING,
        attempted=attempted,
        provider=loader.provider,
        operation=loader.operation,
        artifact_present=False,
    )


def _failed_outcome(
    loader: FinalDecisionReviewSourceLoaderV1,
    error_code: str,
) -> FinalDecisionReviewSourceAcquisitionOutcomeV1:
    return FinalDecisionReviewSourceAcquisitionOutcomeV1(
        slot=loader.slot,
        status=FinalDecisionReviewSourceAcquisitionStatus.FAILED,
        attempted=True,
        provider=loader.provider,
        operation=loader.operation,
        error_code=error_code,
        artifact_present=False,
    )


def _load(
    loader: FinalDecisionReviewSourceLoaderV1,
) -> tuple[FinalDecisionReviewSourceAcquisitionOutcomeV1, object | None]:
    try:
        artifact = loader.load()
    except TimeoutError:
        return _failed_outcome(loader, "SOURCE_TIMEOUT"), None
    except Exception:
        return _failed_outcome(loader, "SOURCE_LOAD_FAILED"), None

    if artifact is None:
        return _missing_outcome(loader, attempted=True), None
    if not isinstance(artifact, loader.expected_type):
        return _failed_outcome(loader, "SOURCE_TYPE_INVALID"), None
    try:
        observed_at = _aware_utc(loader.observed_at(artifact))
    except (AttributeError, TypeError, ValueError):
        return _failed_outcome(loader, "SOURCE_TIMESTAMP_INVALID"), None
    return (
        FinalDecisionReviewSourceAcquisitionOutcomeV1(
            slot=loader.slot,
            status=FinalDecisionReviewSourceAcquisitionStatus.AVAILABLE,
            attempted=True,
            observed_at=observed_at,
            provider=loader.provider,
            operation=loader.operation,
            artifact_present=True,
        ),
        artifact,
    )


def _to_evidence(
    outcome: FinalDecisionReviewSourceAcquisitionOutcomeV1,
) -> FinalDecisionReviewWorkflowSourceEvidenceV1:
    if outcome.status is FinalDecisionReviewSourceAcquisitionStatus.AVAILABLE:
        assert outcome.observed_at is not None
        return available_final_decision_review_workflow_source(
            slot=outcome.slot,
            observed_at=outcome.observed_at,
            provider=outcome.provider,
            operation=outcome.operation,
        )
    if outcome.status is FinalDecisionReviewSourceAcquisitionStatus.FAILED:
        assert outcome.error_code is not None
        return failed_final_decision_review_workflow_source(
            slot=outcome.slot,
            error_code=outcome.error_code,
        )
    return missing_final_decision_review_workflow_source(outcome.slot)


class FinalDecisionReviewSourceAcquisitionAdapterV1:
    """Acquire typed read-only sources and hand exact outcomes to PR-67."""

    def __init__(
        self,
        *,
        coordinator: FinalDecisionReviewWorkflowCoordinatorV1,
        purchase_gate_loader: FinalDecisionReviewSourceLoaderV1,
        sell_gate_loader: FinalDecisionReviewSourceLoaderV1,
        current_risk_loader: FinalDecisionReviewSourceLoaderV1,
        pro_forma_risk_loader: FinalDecisionReviewSourceLoaderV1,
    ) -> None:
        loaders = (
            purchase_gate_loader,
            sell_gate_loader,
            current_risk_loader,
            pro_forma_risk_loader,
        )
        slots = tuple(loader.slot for loader in loaders)
        if len(set(slots)) != len(slots) or set(slots) != set(
            FinalDecisionReviewWorkflowSourceSlot
        ):
            raise FinalDecisionReviewSourceAcquisitionError(
                "FINAL_DECISION_REVIEW_SOURCE_LOADER_SET_INVALID"
            )
        self._coordinator = coordinator
        self._loaders = {loader.slot: loader for loader in loaders}
        self._lock = RLock()

    @property
    def coordinator(self) -> FinalDecisionReviewWorkflowCoordinatorV1:
        return self._coordinator

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
        selected_slot = (
            FinalDecisionReviewWorkflowSourceSlot.PURCHASE_GATE
            if direction is OrderSide.BUY
            else FinalDecisionReviewWorkflowSourceSlot.SELL_GATE
        )
        unselected_slot = (
            FinalDecisionReviewWorkflowSourceSlot.SELL_GATE
            if direction is OrderSide.BUY
            else FinalDecisionReviewWorkflowSourceSlot.PURCHASE_GATE
        )
        with self._lock:
            outcomes_by_slot: dict[
                FinalDecisionReviewWorkflowSourceSlot,
                FinalDecisionReviewSourceAcquisitionOutcomeV1,
            ] = {
                unselected_slot: _missing_outcome(
                    self._loaders[unselected_slot],
                    attempted=False,
                )
            }
            artifacts: dict[FinalDecisionReviewWorkflowSourceSlot, object | None] = {
                unselected_slot: None
            }
            for slot in (
                selected_slot,
                FinalDecisionReviewWorkflowSourceSlot.CURRENT_RISK,
                FinalDecisionReviewWorkflowSourceSlot.PRO_FORMA_RISK,
            ):
                outcome, artifact = _load(self._loaders[slot])
                outcomes_by_slot[slot] = outcome
                artifacts[slot] = artifact

            outcomes = tuple(
                outcomes_by_slot[slot]
                for slot in FinalDecisionReviewWorkflowSourceSlot
            )
            evidence = tuple(_to_evidence(outcome) for outcome in outcomes)
            try:
                coordinator_result = self._coordinator.coordinate(
                    scenario_id=scenario_id,
                    source_evidence=evidence,
                    current_risk_evaluation=cast(
                        RiskPolicyEvaluationV1 | None,
                        artifacts[FinalDecisionReviewWorkflowSourceSlot.CURRENT_RISK],
                    ),
                    pro_forma_risk_evaluation=cast(
                        RiskPolicyEvaluationV1 | None,
                        artifacts[FinalDecisionReviewWorkflowSourceSlot.PRO_FORMA_RISK],
                    ),
                    purchase_gate=cast(
                        CapacityPreTradeDecisionGateV1 | None,
                        artifacts.get(
                            FinalDecisionReviewWorkflowSourceSlot.PURCHASE_GATE
                        ),
                    ),
                    sell_gate=cast(
                        CapacitySellPreTradeDecisionGateV1 | None,
                        artifacts.get(FinalDecisionReviewWorkflowSourceSlot.SELL_GATE),
                    ),
                    correlation_id=correlation_id,
                    request_id=request_id,
                    coordinated_at=now,
                )
            except FinalDecisionReviewWorkflowCoordinatorError as exc:
                raise FinalDecisionReviewSourceAcquisitionError(
                    "FINAL_DECISION_REVIEW_SOURCE_COORDINATION_INVALID"
                ) from exc

        attempted = sum(outcome.attempted for outcome in outcomes)
        available = sum(
            outcome.status is FinalDecisionReviewSourceAcquisitionStatus.AVAILABLE
            for outcome in outcomes
        )
        missing = sum(
            outcome.status is FinalDecisionReviewSourceAcquisitionStatus.MISSING
            for outcome in outcomes
        )
        failed = sum(
            outcome.status is FinalDecisionReviewSourceAcquisitionStatus.FAILED
            for outcome in outcomes
        )
        timed_out = sum(outcome.error_code == "SOURCE_TIMEOUT" for outcome in outcomes)
        correspondence = all(
            outcome.artifact_present is (artifacts[outcome.slot] is not None)
            for outcome in outcomes
        )
        return FinalDecisionReviewSourceAcquisitionResultV1(
            acquired_at=now,
            published=coordinator_result.published,
            primary_blocker=coordinator_result.primary_blocker,
            outcomes=outcomes,
            coordinator_result=coordinator_result,
            selected_direction_count=1,
            attempted_source_count=attempted,
            available_source_count=available,
            missing_source_count=missing,
            failed_source_count=failed,
            timeout_source_count=timed_out,
            exact_slot_set_confirmed=True,
            evidence_artifact_correspondence_confirmed=correspondence,
        )
