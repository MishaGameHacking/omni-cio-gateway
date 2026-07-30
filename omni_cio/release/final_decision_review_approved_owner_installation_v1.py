from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from omni_cio.contracts.v1.final_decision_review_approved_invocation import (
    ApprovedCalculatorInvocationRequestV1,
    ApprovedCalculatorOperation,
)
from omni_cio.release.final_decision_review_approved_owner_acquisition_v1 import (
    FinalDecisionReviewApprovedOwnerAcquisitionResultV1,
    FinalDecisionReviewApprovedOwnerAcquisitionV1,
    FinalDecisionReviewApprovedOwnerLeaseV1,
    FinalDecisionReviewApprovedOwnerLoaderV1,
    FinalDecisionReviewApprovedOwnerSourceLoadersV1,
    FinalDecisionReviewApprovedOwnerSourceSlot,
    FinalDecisionReviewApprovedServerContextV1,
)
from omni_cio.release.final_decision_review_trusted_owner_composition_v1 import (
    FinalDecisionReviewTrustedOwnerCompositionV1,
    FinalDecisionReviewTrustedPurchaseOwnerPortsV1,
    FinalDecisionReviewTrustedSellOwnerPortsV1,
)


_PROVIDER = "omni-cio-existing-calculators"


class FinalDecisionReviewApprovedOwnerInstallationError(ValueError):
    """Existing typed owner ports cannot be installed into PR-79 safely."""


OwnerCallableV1 = Callable[[ApprovedCalculatorInvocationRequestV1], object]


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if (
        not isinstance(result, datetime)
        or result.tzinfo is None
        or result.utcoffset() is None
    ):
        raise FinalDecisionReviewApprovedOwnerInstallationError(
            "FINAL_DECISION_REVIEW_APPROVED_OWNER_INSTALLATION_TIME_INVALID"
        )
    return result.astimezone(timezone.utc)


def _require_context(
    context: FinalDecisionReviewApprovedServerContextV1,
    *,
    operation: ApprovedCalculatorOperation,
) -> FinalDecisionReviewApprovedServerContextV1:
    if not isinstance(context, FinalDecisionReviewApprovedServerContextV1):
        raise FinalDecisionReviewApprovedOwnerInstallationError(
            "FINAL_DECISION_REVIEW_APPROVED_OWNER_INSTALLATION_CONTEXT_TYPE_INVALID"
        )
    if context.operation is not operation:
        raise FinalDecisionReviewApprovedOwnerInstallationError(
            "FINAL_DECISION_REVIEW_APPROVED_OWNER_INSTALLATION_OPERATION_MISMATCH"
        )
    return context


def _owner_loader(
    *,
    slot: FinalDecisionReviewApprovedOwnerSourceSlot,
    expected_context: FinalDecisionReviewApprovedServerContextV1,
    owner: OwnerCallableV1 | None,
    observed_at: datetime,
) -> FinalDecisionReviewApprovedOwnerLoaderV1:
    operation = f"install-{slot.value}-owner"

    def load(
        actual_context: FinalDecisionReviewApprovedServerContextV1,
    ) -> FinalDecisionReviewApprovedOwnerLeaseV1 | None:
        if actual_context != expected_context:
            raise FinalDecisionReviewApprovedOwnerInstallationError(
                "FINAL_DECISION_REVIEW_APPROVED_OWNER_INSTALLATION_CONTEXT_MISMATCH"
            )
        if owner is None:
            return None
        return FinalDecisionReviewApprovedOwnerLeaseV1(
            slot=slot,
            owner=owner,
            observed_at=observed_at,
            provider=_PROVIDER,
            operation=operation,
        )

    return FinalDecisionReviewApprovedOwnerLoaderV1(
        slot=slot,
        provider=_PROVIDER,
        operation=operation,
        load=load,
    )


def _purchase_loaders(
    *,
    context: FinalDecisionReviewApprovedServerContextV1,
    owners: FinalDecisionReviewTrustedPurchaseOwnerPortsV1,
    observed_at: datetime,
) -> FinalDecisionReviewApprovedOwnerSourceLoadersV1:
    common = owners.common
    return FinalDecisionReviewApprovedOwnerSourceLoadersV1(
        decision=_owner_loader(
            slot=FinalDecisionReviewApprovedOwnerSourceSlot.DECISION,
            expected_context=context,
            owner=common.decision,
            observed_at=observed_at,
        ),
        intent=_owner_loader(
            slot=FinalDecisionReviewApprovedOwnerSourceSlot.INTENT,
            expected_context=context,
            owner=common.intent,
            observed_at=observed_at,
        ),
        capacity=_owner_loader(
            slot=FinalDecisionReviewApprovedOwnerSourceSlot.CAPACITY,
            expected_context=context,
            owner=common.capacity,
            observed_at=observed_at,
        ),
        pro_forma_scenario=_owner_loader(
            slot=FinalDecisionReviewApprovedOwnerSourceSlot.PRO_FORMA_SCENARIO,
            expected_context=context,
            owner=common.pro_forma_scenario,
            observed_at=observed_at,
        ),
        purchase_previews=_owner_loader(
            slot=FinalDecisionReviewApprovedOwnerSourceSlot.PURCHASE_PREVIEWS,
            expected_context=context,
            owner=owners.previews,
            observed_at=observed_at,
        ),
        sell_previews=_owner_loader(
            slot=FinalDecisionReviewApprovedOwnerSourceSlot.SELL_PREVIEWS,
            expected_context=context,
            owner=None,
            observed_at=observed_at,
        ),
    )


def _sell_loaders(
    *,
    context: FinalDecisionReviewApprovedServerContextV1,
    owners: FinalDecisionReviewTrustedSellOwnerPortsV1,
    observed_at: datetime,
) -> FinalDecisionReviewApprovedOwnerSourceLoadersV1:
    common = owners.common
    return FinalDecisionReviewApprovedOwnerSourceLoadersV1(
        decision=_owner_loader(
            slot=FinalDecisionReviewApprovedOwnerSourceSlot.DECISION,
            expected_context=context,
            owner=common.decision,
            observed_at=observed_at,
        ),
        intent=_owner_loader(
            slot=FinalDecisionReviewApprovedOwnerSourceSlot.INTENT,
            expected_context=context,
            owner=common.intent,
            observed_at=observed_at,
        ),
        capacity=_owner_loader(
            slot=FinalDecisionReviewApprovedOwnerSourceSlot.CAPACITY,
            expected_context=context,
            owner=common.capacity,
            observed_at=observed_at,
        ),
        pro_forma_scenario=_owner_loader(
            slot=FinalDecisionReviewApprovedOwnerSourceSlot.PRO_FORMA_SCENARIO,
            expected_context=context,
            owner=common.pro_forma_scenario,
            observed_at=observed_at,
        ),
        purchase_previews=_owner_loader(
            slot=FinalDecisionReviewApprovedOwnerSourceSlot.PURCHASE_PREVIEWS,
            expected_context=context,
            owner=None,
            observed_at=observed_at,
        ),
        sell_previews=_owner_loader(
            slot=FinalDecisionReviewApprovedOwnerSourceSlot.SELL_PREVIEWS,
            expected_context=context,
            owner=owners.previews,
            observed_at=observed_at,
        ),
    )


class FinalDecisionReviewApprovedOwnerInstallationV1:
    """Install exact typed owner ports into one fresh PR-79 acquisition call."""

    internal_only = True
    raw_payload_accepted = False
    credentials_accepted = False
    full_account_accepted = False
    request_body_accepted = False
    broker_write_called = False
    trade_authorized = False
    order_created = False
    execution_ready = False
    trading_methods = False

    def __init__(
        self,
        *,
        composition: FinalDecisionReviewTrustedOwnerCompositionV1,
    ) -> None:
        if not isinstance(
            composition,
            FinalDecisionReviewTrustedOwnerCompositionV1,
        ):
            raise FinalDecisionReviewApprovedOwnerInstallationError(
                "FINAL_DECISION_REVIEW_APPROVED_OWNER_INSTALLATION_COMPOSITION_INVALID"
            )
        self._composition = composition

    @property
    def composition(self) -> FinalDecisionReviewTrustedOwnerCompositionV1:
        return self._composition

    def invoke_purchase(
        self,
        *,
        context: FinalDecisionReviewApprovedServerContextV1,
        owners: FinalDecisionReviewTrustedPurchaseOwnerPortsV1,
        installed_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> FinalDecisionReviewApprovedOwnerAcquisitionResultV1:
        approved_context = _require_context(
            context,
            operation=ApprovedCalculatorOperation.PURCHASE_REVIEW,
        )
        if not isinstance(owners, FinalDecisionReviewTrustedPurchaseOwnerPortsV1):
            raise FinalDecisionReviewApprovedOwnerInstallationError(
                "FINAL_DECISION_REVIEW_APPROVED_OWNER_INSTALLATION_PURCHASE_OWNERS_INVALID"
            )
        observed_at = _aware_utc(installed_at)
        acquisition = FinalDecisionReviewApprovedOwnerAcquisitionV1(
            composition=self._composition,
            context_loader=lambda: approved_context,
            source_loaders=_purchase_loaders(
                context=approved_context,
                owners=owners,
                observed_at=observed_at,
            ),
        )
        return acquisition.acquire(
            acquired_at=observed_at,
            completed_at=completed_at,
        )

    def invoke_sell(
        self,
        *,
        context: FinalDecisionReviewApprovedServerContextV1,
        owners: FinalDecisionReviewTrustedSellOwnerPortsV1,
        installed_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> FinalDecisionReviewApprovedOwnerAcquisitionResultV1:
        approved_context = _require_context(
            context,
            operation=ApprovedCalculatorOperation.SELL_REVIEW,
        )
        if not isinstance(owners, FinalDecisionReviewTrustedSellOwnerPortsV1):
            raise FinalDecisionReviewApprovedOwnerInstallationError(
                "FINAL_DECISION_REVIEW_APPROVED_OWNER_INSTALLATION_SELL_OWNERS_INVALID"
            )
        observed_at = _aware_utc(installed_at)
        acquisition = FinalDecisionReviewApprovedOwnerAcquisitionV1(
            composition=self._composition,
            context_loader=lambda: approved_context,
            source_loaders=_sell_loaders(
                context=approved_context,
                owners=owners,
                observed_at=observed_at,
            ),
        )
        return acquisition.acquire(
            acquired_at=observed_at,
            completed_at=completed_at,
        )
