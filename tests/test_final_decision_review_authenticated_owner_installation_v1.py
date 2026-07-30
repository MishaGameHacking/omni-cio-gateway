from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import pytest

import app as gateway
from omni_cio.contracts.v1.common import AccountReference
from omni_cio.contracts.v1.final_decision_review_approved_invocation import (
    ApprovedCalculatorOperation,
)
from omni_cio.contracts.v1.final_decision_review_handler_shadow import (
    FinalDecisionReviewHandlerErrorCode,
    FinalDecisionReviewHandlerHttpStatus,
)
from omni_cio.release.final_decision_review_approved_owner_acquisition_v1 import (
    FinalDecisionReviewApprovedOwnerAcquisitionStatus,
    FinalDecisionReviewApprovedServerContextV1,
)
from omni_cio.release.final_decision_review_approved_owner_installation_v1 import (
    FinalDecisionReviewApprovedOwnerInstallationV1,
)
from omni_cio.release.final_decision_review_approved_owner_snapshots_v1 import (
    FinalDecisionReviewApprovedOwnerSnapshotSelectionV1,
    FinalDecisionReviewApprovedOwnerSnapshotStoreV1,
)
from omni_cio.release.final_decision_review_authenticated_owner_installation_v1 import (
    FinalDecisionReviewAuthenticatedOwnerContextStoreV1,
    FinalDecisionReviewAuthenticatedOwnerEvidenceStoreV1,
    FinalDecisionReviewAuthenticatedOwnerInstallationStatus,
    FinalDecisionReviewAuthenticatedOwnerInstallationV1,
)
from omni_cio.release.final_decision_review_production_registration_v1 import (
    register_final_decision_review_production_sources,
)
from omni_cio.release.final_decision_review_trusted_owner_composition_v1 import (
    FinalDecisionReviewTrustedCommonOwnerPortsV1,
    FinalDecisionReviewTrustedPurchaseOwnerPortsV1,
    FinalDecisionReviewTrustedSellOwnerPortsV1,
)


NOW = datetime.now(timezone.utc).replace(microsecond=0)
ACCOUNT = AccountReference(masked_id="account:****1234")


def _context(
    operation: ApprovedCalculatorOperation,
    *,
    invocation_id: str | None = None,
    generated_at: datetime = NOW,
) -> FinalDecisionReviewApprovedServerContextV1:
    suffix = "buy" if operation is ApprovedCalculatorOperation.PURCHASE_REVIEW else "sell"
    return FinalDecisionReviewApprovedServerContextV1(
        invocation_id=invocation_id or f"invoke:auth-owner:{suffix}",
        scenario_id=f"scenario:auth-owner:{suffix}",
        correlation_id=f"corr:auth-owner:{suffix}",
        operation=operation,
        account=ACCOUNT,
        generated_at=generated_at,
    )


def _common() -> FinalDecisionReviewTrustedCommonOwnerPortsV1:
    return FinalDecisionReviewTrustedCommonOwnerPortsV1(
        decision=lambda request: SimpleNamespace(request=request),  # type: ignore[arg-type]
        intent=lambda request: SimpleNamespace(request=request),  # type: ignore[arg-type]
        capacity=lambda request: (SimpleNamespace(request=request),),  # type: ignore[arg-type,return-value]
        pro_forma_scenario=lambda request: SimpleNamespace(request=request),  # type: ignore[arg-type]
    )


def _selection(
    context: FinalDecisionReviewApprovedServerContextV1,
) -> FinalDecisionReviewApprovedOwnerSnapshotSelectionV1:
    if context.operation is ApprovedCalculatorOperation.PURCHASE_REVIEW:
        return FinalDecisionReviewApprovedOwnerSnapshotSelectionV1(
            context=context,
            captured_at=context.generated_at,
            purchase_owners=FinalDecisionReviewTrustedPurchaseOwnerPortsV1(
                common=_common(),
                previews=lambda request: (SimpleNamespace(request=request),),  # type: ignore[arg-type,return-value]
            ),
        )
    return FinalDecisionReviewApprovedOwnerSnapshotSelectionV1(
        context=context,
        captured_at=context.generated_at,
        sell_owners=FinalDecisionReviewTrustedSellOwnerPortsV1(
            common=_common(),
            previews=lambda request: (SimpleNamespace(request=request),),  # type: ignore[arg-type,return-value]
        ),
    )


class _SnapshotStore(FinalDecisionReviewApprovedOwnerSnapshotStoreV1):
    def __init__(self) -> None:
        self.selection: FinalDecisionReviewApprovedOwnerSnapshotSelectionV1 | None = None
        self.fail = False
        self.calls = 0

    def select(  # type: ignore[override]
        self,
        context: FinalDecisionReviewApprovedServerContextV1,
        *,
        checked_at: datetime | None = None,
    ) -> FinalDecisionReviewApprovedOwnerSnapshotSelectionV1 | None:
        self.calls += 1
        assert checked_at == context.generated_at
        if self.fail:
            raise ValueError("SAFE_TEST_FAILURE")
        return self.selection


class _Installation(FinalDecisionReviewApprovedOwnerInstallationV1):
    def __init__(self) -> None:
        self.purchase_calls = 0
        self.sell_calls = 0
        self.unavailable = False
        self.fail = False

    def _result(self) -> Any:
        if self.unavailable:
            return SimpleNamespace(
                status=FinalDecisionReviewApprovedOwnerAcquisitionStatus.UNAVAILABLE,
                primary_blocker="FINAL_DECISION_REVIEW_APPROVED_OWNER_TEST_UNAVAILABLE",
                handler_error_code=FinalDecisionReviewHandlerErrorCode.SOURCE_UNAVAILABLE,
                handler_http_status=(
                    FinalDecisionReviewHandlerHttpStatus.SERVICE_UNAVAILABLE
                ),
            )
        return SimpleNamespace(
            status=FinalDecisionReviewApprovedOwnerAcquisitionStatus.ACQUIRED,
            primary_blocker=None,
            handler_error_code=None,
            handler_http_status=None,
        )

    def invoke_purchase(self, **values: Any) -> Any:  # type: ignore[override]
        self.purchase_calls += 1
        if self.fail:
            raise ValueError("SAFE_TEST_FAILURE")
        assert values["installed_at"] == values["context"].generated_at
        assert values["completed_at"] == values["context"].generated_at
        return self._result()

    def invoke_sell(self, **values: Any) -> Any:  # type: ignore[override]
        self.sell_calls += 1
        if self.fail:
            raise ValueError("SAFE_TEST_FAILURE")
        assert values["installed_at"] == values["context"].generated_at
        assert values["completed_at"] == values["context"].generated_at
        return self._result()


def _lifecycle() -> tuple[
    FinalDecisionReviewAuthenticatedOwnerInstallationV1,
    _SnapshotStore,
    _Installation,
    FinalDecisionReviewAuthenticatedOwnerEvidenceStoreV1,
]:
    snapshots = _SnapshotStore()
    installation = _Installation()
    evidence = FinalDecisionReviewAuthenticatedOwnerEvidenceStoreV1()
    return (
        FinalDecisionReviewAuthenticatedOwnerInstallationV1(
            snapshot_store=snapshots,
            installation=installation,
            evidence_store=evidence,
        ),
        snapshots,
        installation,
        evidence,
    )


@pytest.mark.parametrize(
    "operation",
    (
        ApprovedCalculatorOperation.PURCHASE_REVIEW,
        ApprovedCalculatorOperation.SELL_REVIEW,
    ),
)
def test_post_auth_lifecycle_selects_direction_and_invokes_once(
    operation: ApprovedCalculatorOperation,
) -> None:
    lifecycle, snapshots, installation, evidence = _lifecycle()
    context = _context(operation)
    snapshots.selection = _selection(context)
    row = lifecycle(context)
    assert row.status is FinalDecisionReviewAuthenticatedOwnerInstallationStatus.ACQUIRED
    assert row.snapshot_selected is True
    assert row.installation_called is True
    assert row.acquisition_status is FinalDecisionReviewApprovedOwnerAcquisitionStatus.ACQUIRED
    assert snapshots.calls == 1
    assert installation.purchase_calls == int(
        operation is ApprovedCalculatorOperation.PURCHASE_REVIEW
    )
    assert installation.sell_calls == int(
        operation is ApprovedCalculatorOperation.SELL_REVIEW
    )
    assert evidence.get(context.invocation_id, checked_at=NOW) is row
    assert row.response_changed is False
    assert row.openapi_changed is False
    assert row.broker_write_called is False
    assert row.trading_methods is False


def test_missing_snapshot_records_safe_unavailable_without_installation() -> None:
    lifecycle, snapshots, installation, _ = _lifecycle()
    context = _context(ApprovedCalculatorOperation.PURCHASE_REVIEW)
    row = lifecycle(context)
    assert snapshots.calls == 1
    assert installation.purchase_calls == 0
    assert row.status is FinalDecisionReviewAuthenticatedOwnerInstallationStatus.UNAVAILABLE
    assert row.snapshot_selected is False
    assert row.installation_called is False
    assert row.handler_error_code is FinalDecisionReviewHandlerErrorCode.SOURCE_UNAVAILABLE
    assert (
        row.handler_http_status
        is FinalDecisionReviewHandlerHttpStatus.SERVICE_UNAVAILABLE
    )


def test_selection_and_installation_failures_are_redacted() -> None:
    lifecycle, snapshots, installation, _ = _lifecycle()
    first = _context(ApprovedCalculatorOperation.PURCHASE_REVIEW)
    snapshots.fail = True
    selection_failure = lifecycle(first)
    assert selection_failure.status is FinalDecisionReviewAuthenticatedOwnerInstallationStatus.FAILED
    assert selection_failure.exception_text_present is False

    snapshots.fail = False
    second = _context(
        ApprovedCalculatorOperation.PURCHASE_REVIEW,
        invocation_id="invoke:auth-owner:failure-two",
    )
    snapshots.selection = _selection(second)
    installation.fail = True
    installation_failure = lifecycle(second)
    assert installation_failure.status is FinalDecisionReviewAuthenticatedOwnerInstallationStatus.FAILED
    assert installation_failure.snapshot_selected is True
    assert installation_failure.installation_called is True
    assert installation_failure.exception_text_present is False


def test_unavailable_acquisition_is_retained_without_response_change() -> None:
    lifecycle, snapshots, installation, _ = _lifecycle()
    context = _context(ApprovedCalculatorOperation.SELL_REVIEW)
    snapshots.selection = _selection(context)
    installation.unavailable = True
    row = lifecycle(context)
    assert row.status is FinalDecisionReviewAuthenticatedOwnerInstallationStatus.UNAVAILABLE
    assert row.acquisition_status is FinalDecisionReviewApprovedOwnerAcquisitionStatus.UNAVAILABLE
    assert row.primary_blocker == "FINAL_DECISION_REVIEW_APPROVED_OWNER_TEST_UNAVAILABLE"
    assert row.response_changed is False
    assert row.openapi_changed is False


def test_context_store_captures_then_runs_lifecycle() -> None:
    lifecycle, snapshots, installation, evidence = _lifecycle()
    context = _context(ApprovedCalculatorOperation.PURCHASE_REVIEW)
    snapshots.selection = _selection(context)
    store = FinalDecisionReviewAuthenticatedOwnerContextStoreV1(
        lifecycle=lifecycle,
    )
    capture = store.capture(context)
    assert capture.invocation_id == context.invocation_id
    assert store.get(context.invocation_id, checked_at=NOW) is context
    assert installation.purchase_calls == 1
    row = evidence.get(context.invocation_id, checked_at=NOW)
    assert row is not None
    assert row.status is FinalDecisionReviewAuthenticatedOwnerInstallationStatus.ACQUIRED


def test_evidence_store_expires_and_evicts() -> None:
    store = FinalDecisionReviewAuthenticatedOwnerEvidenceStoreV1(
        ttl_seconds=2,
        capacity=1,
    )
    first = _context(ApprovedCalculatorOperation.PURCHASE_REVIEW)
    store.publish(
        context=first,
        status=FinalDecisionReviewAuthenticatedOwnerInstallationStatus.UNAVAILABLE,
        snapshot_selected=False,
        installation_called=False,
        acquisition_status=None,
        primary_blocker="FINAL_DECISION_REVIEW_AUTHENTICATED_OWNER_TEST_MISSING",
        handler_error_code=FinalDecisionReviewHandlerErrorCode.SOURCE_UNAVAILABLE,
        handler_http_status=FinalDecisionReviewHandlerHttpStatus.SERVICE_UNAVAILABLE,
    )
    second = _context(
        ApprovedCalculatorOperation.SELL_REVIEW,
        invocation_id="invoke:auth-owner:evidence-two",
    )
    second_row = store.publish(
        context=second,
        status=FinalDecisionReviewAuthenticatedOwnerInstallationStatus.UNAVAILABLE,
        snapshot_selected=False,
        installation_called=False,
        acquisition_status=None,
        primary_blocker="FINAL_DECISION_REVIEW_AUTHENTICATED_OWNER_TEST_MISSING",
        handler_error_code=FinalDecisionReviewHandlerErrorCode.SOURCE_UNAVAILABLE,
        handler_http_status=FinalDecisionReviewHandlerHttpStatus.SERVICE_UNAVAILABLE,
    )
    assert second_row.evicted is True
    assert store.get(first.invocation_id, checked_at=NOW) is None
    assert (
        store.active_evidence_count(checked_at=NOW + timedelta(seconds=3))
        == 0
    )


def test_production_runtime_registers_post_auth_lifecycle_lazily() -> None:
    runtime = gateway.final_decision_review_production_runtime
    assert isinstance(
        runtime.approved_route_context_store,
        FinalDecisionReviewAuthenticatedOwnerContextStoreV1,
    )
    assert (
        runtime.approved_route_context_store.lifecycle
        is runtime.authenticated_owner_installation
    )
    assert (
        runtime.authenticated_owner_installation.snapshot_store
        is runtime.approved_owner_snapshot_store
    )
    assert (
        runtime.authenticated_owner_installation.installation
        is runtime.approved_owner_installation
    )
    assert (
        runtime.authenticated_owner_installation.evidence_store
        is runtime.authenticated_owner_evidence_store
    )
    observer = gateway.final_decision_review_registry.approved_context_observer
    assert getattr(observer, "__self__", None) is runtime.approved_route_context_store
    assert runtime.authenticated_owner_installation_registered is True
    assert runtime.startup_authenticated_context_count == 0
    assert runtime.startup_approved_owner_snapshot_count == 0
    assert runtime.startup_authenticated_owner_evidence_count == 0
    assert runtime.startup_owner_installation_performed is False
    assert runtime.startup_owner_acquisition_performed is False
    assert runtime.broker_write_called is False
    assert runtime.trade_authorized is False
    assert runtime.order_created is False
    assert runtime.trading_methods is False


def test_re_registration_reuses_exact_production_runtime() -> None:
    calls = 0

    def loader() -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {}

    runtime = register_final_decision_review_production_sources(
        bridge=gateway.final_decision_review_workflow_bridge,
        portfolio_payload_loader=loader,
    )
    assert runtime is gateway.final_decision_review_production_runtime
    assert calls == 0
