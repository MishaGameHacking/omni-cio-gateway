from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from omni_cio.contracts.v1.capacity import CapacityAssessmentV1
from omni_cio.contracts.v1.common import AccountReference
from omni_cio.contracts.v1.decision import DecisionSetV1
from omni_cio.contracts.v1.decision_capacity_intent import (
    CapacityIntentDecisionGateRequestV1,
)
from omni_cio.contracts.v1.decision_pro_forma_risk_binding import (
    ProFormaRiskScenarioV1,
)
from omni_cio.contracts.v1.final_decision_review_approved_invocation import (
    ApprovedCalculatorInvocationRequestV1,
    ApprovedCalculatorOperation,
)
from omni_cio.contracts.v1.final_decision_review_handler_shadow import (
    FinalDecisionReviewHandlerErrorCode,
    FinalDecisionReviewHandlerHttpStatus,
)
from omni_cio.contracts.v1.pretrade import PreTradePreviewV1
from omni_cio.contracts.v1.sell_pretrade import SellPreTradePreviewV1
from omni_cio.release.final_decision_review_approved_owner_acquisition_v1 import (
    FinalDecisionReviewApprovedOwnerAcquisitionStatus,
    FinalDecisionReviewApprovedOwnerAcquisitionV1,
    FinalDecisionReviewApprovedOwnerLeaseV1,
    FinalDecisionReviewApprovedOwnerLoaderV1,
    FinalDecisionReviewApprovedOwnerSourceLoadersV1,
    FinalDecisionReviewApprovedOwnerSourceSlot,
    FinalDecisionReviewApprovedOwnerSourceStatus,
    FinalDecisionReviewApprovedServerContextV1,
    unavailable_final_decision_review_approved_owner_source_loaders,
)
from omni_cio.release.final_decision_review_trusted_owner_composition_v1 import (
    FinalDecisionReviewTrustedOwnerCompositionResultV1,
    FinalDecisionReviewTrustedOwnerCompositionV1,
    FinalDecisionReviewTrustedPurchaseOwnerPortsV1,
    FinalDecisionReviewTrustedSellOwnerPortsV1,
)


NOW = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
ACCOUNT = AccountReference(masked_id="account:****1234")
OTHER_ACCOUNT = AccountReference(masked_id="account:****9999")


class _RecordingComposition(FinalDecisionReviewTrustedOwnerCompositionV1):
    def __init__(self) -> None:
        self.purchase_calls = 0
        self.sell_calls = 0

    @staticmethod
    def _result(
        request: ApprovedCalculatorInvocationRequestV1,
    ) -> FinalDecisionReviewTrustedOwnerCompositionResultV1:
        return cast(
            FinalDecisionReviewTrustedOwnerCompositionResultV1,
            SimpleNamespace(request=request),
        )

    def invoke_purchase(
        self,
        *,
        request: ApprovedCalculatorInvocationRequestV1,
        owners: FinalDecisionReviewTrustedPurchaseOwnerPortsV1,
        completed_at: datetime | None = None,
    ) -> FinalDecisionReviewTrustedOwnerCompositionResultV1:
        del completed_at
        self.purchase_calls += 1
        owners.common.decision(request)
        owners.common.intent(request)
        tuple(owners.common.capacity(request))
        owners.common.pro_forma_scenario(request)
        tuple(owners.previews(request))
        return self._result(request)

    def invoke_sell(
        self,
        *,
        request: ApprovedCalculatorInvocationRequestV1,
        owners: FinalDecisionReviewTrustedSellOwnerPortsV1,
        completed_at: datetime | None = None,
    ) -> FinalDecisionReviewTrustedOwnerCompositionResultV1:
        del completed_at
        self.sell_calls += 1
        owners.common.decision(request)
        owners.common.intent(request)
        tuple(owners.common.capacity(request))
        owners.common.pro_forma_scenario(request)
        tuple(owners.previews(request))
        return self._result(request)


def _context(
    operation: ApprovedCalculatorOperation,
    *,
    generated_at: datetime = NOW,
) -> FinalDecisionReviewApprovedServerContextV1:
    return FinalDecisionReviewApprovedServerContextV1(
        invocation_id=f"invoke:approved-owner:{operation.value}",
        scenario_id=f"scenario:approved-owner:{operation.value}",
        correlation_id=f"corr:approved-owner:{operation.value}",
        operation=operation,
        account=ACCOUNT,
        generated_at=generated_at,
    )


def _owner_values(
    *,
    account: AccountReference = ACCOUNT,
) -> dict[FinalDecisionReviewApprovedOwnerSourceSlot, object]:
    return {
        FinalDecisionReviewApprovedOwnerSourceSlot.DECISION: (
            DecisionSetV1.model_construct(
                metadata=SimpleNamespace(account=account),
            )
        ),
        FinalDecisionReviewApprovedOwnerSourceSlot.INTENT: (
            CapacityIntentDecisionGateRequestV1.model_construct()
        ),
        FinalDecisionReviewApprovedOwnerSourceSlot.CAPACITY: (
            (CapacityAssessmentV1.model_construct(),)
        ),
        FinalDecisionReviewApprovedOwnerSourceSlot.PRO_FORMA_SCENARIO: (
            ProFormaRiskScenarioV1.model_construct(account=account)
        ),
        FinalDecisionReviewApprovedOwnerSourceSlot.PURCHASE_PREVIEWS: (
            (
                PreTradePreviewV1.model_construct(
                    metadata=SimpleNamespace(account=account),
                ),
            )
        ),
        FinalDecisionReviewApprovedOwnerSourceSlot.SELL_PREVIEWS: (
            (
                SellPreTradePreviewV1.model_construct(
                    metadata=SimpleNamespace(account=account),
                ),
            )
        ),
    }


def _source_loaders(
    *,
    missing: FinalDecisionReviewApprovedOwnerSourceSlot | None = None,
    stale: FinalDecisionReviewApprovedOwnerSourceSlot | None = None,
    failing: FinalDecisionReviewApprovedOwnerSourceSlot | None = None,
    account: AccountReference = ACCOUNT,
) -> tuple[
    FinalDecisionReviewApprovedOwnerSourceLoadersV1,
    dict[FinalDecisionReviewApprovedOwnerSourceSlot, int],
    dict[FinalDecisionReviewApprovedOwnerSourceSlot, int],
]:
    values = _owner_values(account=account)
    loader_calls = {
        slot: 0
        for slot in FinalDecisionReviewApprovedOwnerSourceSlot
        if slot is not FinalDecisionReviewApprovedOwnerSourceSlot.SERVER_CONTEXT
    }
    owner_calls = dict.fromkeys(loader_calls, 0)

    def loader(
        slot: FinalDecisionReviewApprovedOwnerSourceSlot,
    ) -> FinalDecisionReviewApprovedOwnerLoaderV1:
        provider = "omni-cio"
        operation = f"load-{slot.value}-owner"

        def load(
            _: FinalDecisionReviewApprovedServerContextV1,
        ) -> FinalDecisionReviewApprovedOwnerLeaseV1 | None:
            loader_calls[slot] += 1
            if slot is failing:
                raise RuntimeError("sensitive source failure")
            if slot is missing:
                return None

            def owner(
                __: ApprovedCalculatorInvocationRequestV1,
            ) -> object:
                owner_calls[slot] += 1
                return values[slot]

            return FinalDecisionReviewApprovedOwnerLeaseV1(
                slot=slot,
                owner=owner,
                observed_at=(
                    NOW - timedelta(seconds=301) if slot is stale else NOW
                ),
                provider=provider,
                operation=operation,
            )

        return FinalDecisionReviewApprovedOwnerLoaderV1(
            slot=slot,
            provider=provider,
            operation=operation,
            load=load,
        )

    result = FinalDecisionReviewApprovedOwnerSourceLoadersV1(
        decision=loader(FinalDecisionReviewApprovedOwnerSourceSlot.DECISION),
        intent=loader(FinalDecisionReviewApprovedOwnerSourceSlot.INTENT),
        capacity=loader(FinalDecisionReviewApprovedOwnerSourceSlot.CAPACITY),
        pro_forma_scenario=loader(
            FinalDecisionReviewApprovedOwnerSourceSlot.PRO_FORMA_SCENARIO
        ),
        purchase_previews=loader(
            FinalDecisionReviewApprovedOwnerSourceSlot.PURCHASE_PREVIEWS
        ),
        sell_previews=loader(
            FinalDecisionReviewApprovedOwnerSourceSlot.SELL_PREVIEWS
        ),
    )
    return result, loader_calls, owner_calls


def _acquisition(
    context: FinalDecisionReviewApprovedServerContextV1 | None,
    loaders: FinalDecisionReviewApprovedOwnerSourceLoadersV1,
    *,
    context_loader: Callable[
        [],
        FinalDecisionReviewApprovedServerContextV1 | None,
    ]
    | None = None,
) -> tuple[
    FinalDecisionReviewApprovedOwnerAcquisitionV1,
    _RecordingComposition,
]:
    composition = _RecordingComposition()
    return (
        FinalDecisionReviewApprovedOwnerAcquisitionV1(
            composition=composition,
            context_loader=context_loader or (lambda: context),
            source_loaders=loaders,
        ),
        composition,
    )


def _status_by_slot(result: Any) -> dict[
    FinalDecisionReviewApprovedOwnerSourceSlot,
    FinalDecisionReviewApprovedOwnerSourceStatus,
]:
    return {row.slot: row.status for row in result.source_evidence}


def test_purchase_acquires_exact_fresh_sources_then_invokes_pr78_once() -> None:
    loaders, loader_calls, owner_calls = _source_loaders()
    acquisition, composition = _acquisition(
        _context(ApprovedCalculatorOperation.PURCHASE_REVIEW),
        loaders,
    )

    result = acquisition.acquire(acquired_at=NOW, completed_at=NOW)

    assert (
        result.status
        is FinalDecisionReviewApprovedOwnerAcquisitionStatus.ACQUIRED
    )
    assert result.request is not None
    assert (
        result.request.operation
        is ApprovedCalculatorOperation.PURCHASE_REVIEW
    )
    assert result.context is not None
    assert result.context.account == ACCOUNT
    assert result.composition_called is True
    assert result.sources_fresh is True
    assert result.handler_error_code is None
    assert result.handler_http_status is None
    assert result.raw_payload_accepted is False
    assert result.credentials_accepted is False
    assert result.full_account_accepted is False
    assert result.broker_write_called is False
    assert result.trading_methods is False
    assert composition.purchase_calls == 1
    assert composition.sell_calls == 0
    assert loader_calls[
        FinalDecisionReviewApprovedOwnerSourceSlot.SELL_PREVIEWS
    ] == 0
    assert owner_calls[
        FinalDecisionReviewApprovedOwnerSourceSlot.SELL_PREVIEWS
    ] == 0
    selected = (
        FinalDecisionReviewApprovedOwnerSourceSlot.DECISION,
        FinalDecisionReviewApprovedOwnerSourceSlot.INTENT,
        FinalDecisionReviewApprovedOwnerSourceSlot.CAPACITY,
        FinalDecisionReviewApprovedOwnerSourceSlot.PRO_FORMA_SCENARIO,
        FinalDecisionReviewApprovedOwnerSourceSlot.PURCHASE_PREVIEWS,
    )
    assert all(loader_calls[slot] == 1 for slot in selected)
    assert all(owner_calls[slot] == 1 for slot in selected)
    statuses = _status_by_slot(result)
    assert statuses[
        FinalDecisionReviewApprovedOwnerSourceSlot.SELL_PREVIEWS
    ] is FinalDecisionReviewApprovedOwnerSourceStatus.NOT_SELECTED
    assert all(
        statuses[slot] is FinalDecisionReviewApprovedOwnerSourceStatus.AVAILABLE
        for slot in (
            FinalDecisionReviewApprovedOwnerSourceSlot.SERVER_CONTEXT,
            *selected,
        )
    )


def test_sell_selects_only_fixed_sell_preview_owner() -> None:
    loaders, loader_calls, owner_calls = _source_loaders()
    acquisition, composition = _acquisition(
        _context(ApprovedCalculatorOperation.SELL_REVIEW),
        loaders,
    )

    result = acquisition.acquire(acquired_at=NOW, completed_at=NOW)

    assert (
        result.status
        is FinalDecisionReviewApprovedOwnerAcquisitionStatus.ACQUIRED
    )
    assert composition.purchase_calls == 0
    assert composition.sell_calls == 1
    assert loader_calls[
        FinalDecisionReviewApprovedOwnerSourceSlot.PURCHASE_PREVIEWS
    ] == 0
    assert owner_calls[
        FinalDecisionReviewApprovedOwnerSourceSlot.PURCHASE_PREVIEWS
    ] == 0
    assert loader_calls[
        FinalDecisionReviewApprovedOwnerSourceSlot.SELL_PREVIEWS
    ] == 1
    assert owner_calls[
        FinalDecisionReviewApprovedOwnerSourceSlot.SELL_PREVIEWS
    ] == 1


def test_missing_source_maps_to_existing_safe_unavailable_without_owner_calls() -> None:
    missing = FinalDecisionReviewApprovedOwnerSourceSlot.CAPACITY
    loaders, _, owner_calls = _source_loaders(missing=missing)
    acquisition, composition = _acquisition(
        _context(ApprovedCalculatorOperation.PURCHASE_REVIEW),
        loaders,
    )

    result = acquisition.acquire(acquired_at=NOW)

    assert (
        result.status
        is FinalDecisionReviewApprovedOwnerAcquisitionStatus.UNAVAILABLE
    )
    assert result.primary_blocker == (
        "FINAL_DECISION_REVIEW_APPROVED_OWNER_SOURCE_MISSING"
    )
    assert (
        result.handler_error_code
        is FinalDecisionReviewHandlerErrorCode.SOURCE_UNAVAILABLE
    )
    assert (
        result.handler_http_status
        is FinalDecisionReviewHandlerHttpStatus.SERVICE_UNAVAILABLE
    )
    assert result.composition_called is False
    assert composition.purchase_calls == 0
    assert composition.sell_calls == 0
    assert all(value == 0 for value in owner_calls.values())
    assert (
        _status_by_slot(result)[missing]
        is FinalDecisionReviewApprovedOwnerSourceStatus.MISSING
    )


def test_stale_source_blocks_pr78_before_any_financial_owner_call() -> None:
    stale = FinalDecisionReviewApprovedOwnerSourceSlot.DECISION
    loaders, _, owner_calls = _source_loaders(stale=stale)
    acquisition, composition = _acquisition(
        _context(ApprovedCalculatorOperation.PURCHASE_REVIEW),
        loaders,
    )

    result = acquisition.acquire(acquired_at=NOW)

    assert result.primary_blocker == (
        "FINAL_DECISION_REVIEW_APPROVED_OWNER_SOURCE_STALE"
    )
    assert result.composition_called is False
    assert composition.purchase_calls == 0
    assert all(value == 0 for value in owner_calls.values())
    assert (
        _status_by_slot(result)[stale]
        is FinalDecisionReviewApprovedOwnerSourceStatus.STALE
    )


def test_stale_server_context_skips_every_owner_loader() -> None:
    loaders, loader_calls, owner_calls = _source_loaders()
    acquisition, composition = _acquisition(
        _context(
            ApprovedCalculatorOperation.PURCHASE_REVIEW,
            generated_at=NOW - timedelta(seconds=301),
        ),
        loaders,
    )

    result = acquisition.acquire(acquired_at=NOW)

    assert result.primary_blocker == (
        "FINAL_DECISION_REVIEW_APPROVED_OWNER_CONTEXT_STALE"
    )
    assert all(value == 0 for value in loader_calls.values())
    assert all(value == 0 for value in owner_calls.values())
    assert composition.purchase_calls == 0
    statuses = _status_by_slot(result)
    assert statuses[
        FinalDecisionReviewApprovedOwnerSourceSlot.SERVER_CONTEXT
    ] is FinalDecisionReviewApprovedOwnerSourceStatus.STALE
    assert all(
        statuses[slot]
        is FinalDecisionReviewApprovedOwnerSourceStatus.NOT_ATTEMPTED
        for slot in loader_calls
    )


def test_account_mismatch_is_sanitized_as_unavailable() -> None:
    loaders, _, owner_calls = _source_loaders(account=OTHER_ACCOUNT)
    acquisition, composition = _acquisition(
        _context(ApprovedCalculatorOperation.PURCHASE_REVIEW),
        loaders,
    )

    result = acquisition.acquire(acquired_at=NOW)

    assert result.primary_blocker == (
        "FINAL_DECISION_REVIEW_APPROVED_OWNER_COMPOSITION_FAILED"
    )
    assert result.composition_called is True
    assert result.sources_fresh is True
    assert result.composition_result is None
    assert composition.purchase_calls == 1
    assert owner_calls[
        FinalDecisionReviewApprovedOwnerSourceSlot.DECISION
    ] == 1
    assert (
        result.handler_error_code
        is FinalDecisionReviewHandlerErrorCode.SOURCE_UNAVAILABLE
    )


def test_source_exception_text_is_never_returned_or_logged() -> None:
    failing = FinalDecisionReviewApprovedOwnerSourceSlot.INTENT
    loaders, _, owner_calls = _source_loaders(failing=failing)
    acquisition, composition = _acquisition(
        _context(ApprovedCalculatorOperation.PURCHASE_REVIEW),
        loaders,
    )

    result = acquisition.acquire(acquired_at=NOW)

    assert result.primary_blocker == (
        "FINAL_DECISION_REVIEW_APPROVED_OWNER_SOURCE_FAILED"
    )
    assert "sensitive source failure" not in repr(result)
    assert composition.purchase_calls == 0
    assert all(value == 0 for value in owner_calls.values())
    failed_row = next(row for row in result.source_evidence if row.slot is failing)
    assert failed_row.error_code == "SOURCE_LOAD_FAILED"
    assert failed_row.exception_text_logged is False


def test_fail_closed_startup_loaders_never_fabricate_an_owner() -> None:
    loaders = unavailable_final_decision_review_approved_owner_source_loaders()
    context = _context(ApprovedCalculatorOperation.PURCHASE_REVIEW)
    for loader in loaders.by_slot().values():
        assert loader.load(context) is None


def test_production_runtime_registers_acquisition_without_startup_calls() -> None:
    import app as gateway

    runtime = gateway.final_decision_review_production_runtime
    acquisition = runtime.approved_owner_acquisition
    assert isinstance(
        acquisition,
        FinalDecisionReviewApprovedOwnerAcquisitionV1,
    )
    assert acquisition.composition is runtime.trusted_owner_composition
    assert runtime.startup_owner_acquisition_performed is False
    result = acquisition.acquire(acquired_at=NOW)
    assert (
        result.status
        is FinalDecisionReviewApprovedOwnerAcquisitionStatus.UNAVAILABLE
    )
    assert result.primary_blocker == (
        "FINAL_DECISION_REVIEW_APPROVED_OWNER_CONTEXT_UNAVAILABLE"
    )
    assert runtime.owner_callable_store.active_bundle_count() == 0
    assert runtime.owner_callable_store.active_pin_count() == 0
    assert runtime.source_store.active_bundle_count() == 0


def test_approved_owner_acquisition_has_no_http_or_broker_write_surface() -> None:
    source = (
        Path(
            "omni_cio/release/"
            "final_decision_review_approved_owner_acquisition_v1.py"
        )
        .read_text(encoding="utf-8")
        .lower()
    )
    forbidden = (
        "@app.get",
        "@app.post",
        "@app.put",
        "@app.patch",
        "@app.delete",
        ".post_order(",
        ".replace_order(",
        ".cancel_order(",
        "request.body",
        "logger.exception",
        "authorization",
        "tinvest_token",
        "gateway_api_key",
    )
    assert all(marker not in source for marker in forbidden)
