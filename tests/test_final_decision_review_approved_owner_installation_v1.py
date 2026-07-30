from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

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
from omni_cio.contracts.v1.pretrade import PreTradePreviewV1
from omni_cio.contracts.v1.sell_pretrade import SellPreTradePreviewV1
from omni_cio.release.final_decision_review_approved_owner_acquisition_v1 import (
    FinalDecisionReviewApprovedOwnerAcquisitionStatus,
    FinalDecisionReviewApprovedOwnerSourceSlot,
    FinalDecisionReviewApprovedOwnerSourceStatus,
    FinalDecisionReviewApprovedServerContextV1,
)
from omni_cio.release.final_decision_review_approved_owner_installation_v1 import (
    FinalDecisionReviewApprovedOwnerInstallationError,
    FinalDecisionReviewApprovedOwnerInstallationV1,
)
from omni_cio.release.final_decision_review_trusted_owner_composition_v1 import (
    FinalDecisionReviewTrustedCommonOwnerPortsV1,
    FinalDecisionReviewTrustedOwnerCompositionResultV1,
    FinalDecisionReviewTrustedOwnerCompositionV1,
    FinalDecisionReviewTrustedPurchaseOwnerPortsV1,
    FinalDecisionReviewTrustedSellOwnerPortsV1,
)


NOW = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
ACCOUNT = AccountReference(masked_id="account:****1234")


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
        invocation_id=f"invoke:approved-installation:{operation.value}",
        scenario_id=f"scenario:approved-installation:{operation.value}",
        correlation_id=f"corr:approved-installation:{operation.value}",
        operation=operation,
        account=ACCOUNT,
        generated_at=generated_at,
    )


def _owners(
    *,
    sell: bool = False,
) -> tuple[
    FinalDecisionReviewTrustedPurchaseOwnerPortsV1
    | FinalDecisionReviewTrustedSellOwnerPortsV1,
    dict[str, int],
]:
    calls = {
        "decision": 0,
        "intent": 0,
        "capacity": 0,
        "scenario": 0,
        "previews": 0,
    }

    def decision(_: ApprovedCalculatorInvocationRequestV1) -> DecisionSetV1:
        calls["decision"] += 1
        return DecisionSetV1.model_construct(
            metadata=SimpleNamespace(account=ACCOUNT),
        )

    def intent(
        _: ApprovedCalculatorInvocationRequestV1,
    ) -> CapacityIntentDecisionGateRequestV1:
        calls["intent"] += 1
        return CapacityIntentDecisionGateRequestV1.model_construct()

    def capacity(
        _: ApprovedCalculatorInvocationRequestV1,
    ) -> tuple[CapacityAssessmentV1, ...]:
        calls["capacity"] += 1
        return (CapacityAssessmentV1.model_construct(),)

    def scenario(
        _: ApprovedCalculatorInvocationRequestV1,
    ) -> ProFormaRiskScenarioV1:
        calls["scenario"] += 1
        return ProFormaRiskScenarioV1.model_construct(account=ACCOUNT)

    common = FinalDecisionReviewTrustedCommonOwnerPortsV1(
        decision=decision,
        intent=intent,
        capacity=capacity,
        pro_forma_scenario=scenario,
    )
    if sell:

        def sell_previews(
            _: ApprovedCalculatorInvocationRequestV1,
        ) -> tuple[SellPreTradePreviewV1, ...]:
            calls["previews"] += 1
            return (
                SellPreTradePreviewV1.model_construct(
                    metadata=SimpleNamespace(account=ACCOUNT),
                ),
            )

        return (
            FinalDecisionReviewTrustedSellOwnerPortsV1(
                common=common,
                previews=sell_previews,
            ),
            calls,
        )

    def purchase_previews(
        _: ApprovedCalculatorInvocationRequestV1,
    ) -> tuple[PreTradePreviewV1, ...]:
        calls["previews"] += 1
        return (
            PreTradePreviewV1.model_construct(
                metadata=SimpleNamespace(account=ACCOUNT),
            ),
        )

    return (
        FinalDecisionReviewTrustedPurchaseOwnerPortsV1(
            common=common,
            previews=purchase_previews,
        ),
        calls,
    )


def _status_by_slot(result: Any) -> dict[
    FinalDecisionReviewApprovedOwnerSourceSlot,
    FinalDecisionReviewApprovedOwnerSourceStatus,
]:
    return {row.slot: row.status for row in result.source_evidence}


def test_purchase_installs_exact_typed_owners_for_one_pr79_call() -> None:
    composition = _RecordingComposition()
    installation = FinalDecisionReviewApprovedOwnerInstallationV1(
        composition=composition,
    )
    owners, calls = _owners()
    assert isinstance(owners, FinalDecisionReviewTrustedPurchaseOwnerPortsV1)

    result = installation.invoke_purchase(
        context=_context(ApprovedCalculatorOperation.PURCHASE_REVIEW),
        owners=owners,
        installed_at=NOW,
        completed_at=NOW,
    )

    assert (
        result.status
        is FinalDecisionReviewApprovedOwnerAcquisitionStatus.ACQUIRED
    )
    assert composition.purchase_calls == 1
    assert composition.sell_calls == 0
    assert all(value == 1 for value in calls.values())
    statuses = _status_by_slot(result)
    assert statuses[
        FinalDecisionReviewApprovedOwnerSourceSlot.SELL_PREVIEWS
    ] is FinalDecisionReviewApprovedOwnerSourceStatus.NOT_SELECTED
    selected = (
        FinalDecisionReviewApprovedOwnerSourceSlot.SERVER_CONTEXT,
        FinalDecisionReviewApprovedOwnerSourceSlot.DECISION,
        FinalDecisionReviewApprovedOwnerSourceSlot.INTENT,
        FinalDecisionReviewApprovedOwnerSourceSlot.CAPACITY,
        FinalDecisionReviewApprovedOwnerSourceSlot.PRO_FORMA_SCENARIO,
        FinalDecisionReviewApprovedOwnerSourceSlot.PURCHASE_PREVIEWS,
    )
    assert all(
        statuses[slot] is FinalDecisionReviewApprovedOwnerSourceStatus.AVAILABLE
        for slot in selected
    )
    assert all(
        row.provider == "omni-cio-existing-calculators"
        for row in result.source_evidence
        if row.slot is not FinalDecisionReviewApprovedOwnerSourceSlot.SERVER_CONTEXT
    )
    assert installation.raw_payload_accepted is False
    assert installation.credentials_accepted is False
    assert installation.full_account_accepted is False
    assert installation.broker_write_called is False
    assert installation.trading_methods is False


def test_sell_installs_only_sell_direction() -> None:
    composition = _RecordingComposition()
    installation = FinalDecisionReviewApprovedOwnerInstallationV1(
        composition=composition,
    )
    owners, calls = _owners(sell=True)
    assert isinstance(owners, FinalDecisionReviewTrustedSellOwnerPortsV1)

    result = installation.invoke_sell(
        context=_context(ApprovedCalculatorOperation.SELL_REVIEW),
        owners=owners,
        installed_at=NOW,
        completed_at=NOW,
    )

    assert (
        result.status
        is FinalDecisionReviewApprovedOwnerAcquisitionStatus.ACQUIRED
    )
    assert composition.purchase_calls == 0
    assert composition.sell_calls == 1
    assert all(value == 1 for value in calls.values())
    assert _status_by_slot(result)[
        FinalDecisionReviewApprovedOwnerSourceSlot.PURCHASE_PREVIEWS
    ] is FinalDecisionReviewApprovedOwnerSourceStatus.NOT_SELECTED


def test_operation_mismatch_fails_before_any_owner_call() -> None:
    composition = _RecordingComposition()
    installation = FinalDecisionReviewApprovedOwnerInstallationV1(
        composition=composition,
    )
    owners, calls = _owners()
    assert isinstance(owners, FinalDecisionReviewTrustedPurchaseOwnerPortsV1)

    with pytest.raises(
        FinalDecisionReviewApprovedOwnerInstallationError,
        match="FINAL_DECISION_REVIEW_APPROVED_OWNER_INSTALLATION_OPERATION_MISMATCH",
    ):
        installation.invoke_purchase(
            context=_context(ApprovedCalculatorOperation.SELL_REVIEW),
            owners=owners,
            installed_at=NOW,
        )

    assert composition.purchase_calls == 0
    assert composition.sell_calls == 0
    assert all(value == 0 for value in calls.values())


def test_stale_authenticated_context_keeps_pr79_fail_closed() -> None:
    composition = _RecordingComposition()
    installation = FinalDecisionReviewApprovedOwnerInstallationV1(
        composition=composition,
    )
    owners, calls = _owners()
    assert isinstance(owners, FinalDecisionReviewTrustedPurchaseOwnerPortsV1)

    result = installation.invoke_purchase(
        context=_context(
            ApprovedCalculatorOperation.PURCHASE_REVIEW,
            generated_at=NOW - timedelta(seconds=301),
        ),
        owners=owners,
        installed_at=NOW,
    )

    assert (
        result.status
        is FinalDecisionReviewApprovedOwnerAcquisitionStatus.UNAVAILABLE
    )
    assert result.primary_blocker == (
        "FINAL_DECISION_REVIEW_APPROVED_OWNER_CONTEXT_STALE"
    )
    assert composition.purchase_calls == 0
    assert all(value == 0 for value in calls.values())


def test_production_runtime_registers_installer_without_startup_calls() -> None:
    import app as gateway

    runtime = gateway.final_decision_review_production_runtime
    installation = runtime.approved_owner_installation
    assert isinstance(
        installation,
        FinalDecisionReviewApprovedOwnerInstallationV1,
    )
    assert installation.composition is runtime.trusted_owner_composition
    assert runtime.startup_owner_installation_performed is False
    assert runtime.startup_owner_acquisition_performed is False
    assert runtime.owner_callable_store.active_bundle_count() == 0
    assert runtime.owner_callable_store.active_pin_count() == 0
    assert runtime.source_store.active_bundle_count() == 0


def test_approved_owner_installation_has_no_http_or_broker_write_surface() -> None:
    source = Path(
        "omni_cio/release/"
        "final_decision_review_approved_owner_installation_v1.py"
    ).read_text(encoding="utf-8").lower()
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
