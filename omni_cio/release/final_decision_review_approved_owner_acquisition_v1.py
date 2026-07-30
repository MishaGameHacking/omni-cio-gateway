from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
import re
from typing import cast

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
from omni_cio.release.final_decision_review_trusted_owner_composition_v1 import (
    FinalDecisionReviewTrustedCommonOwnerPortsV1,
    FinalDecisionReviewTrustedOwnerCompositionResultV1,
    FinalDecisionReviewTrustedOwnerCompositionV1,
    FinalDecisionReviewTrustedPurchaseOwnerPortsV1,
    FinalDecisionReviewTrustedSellOwnerPortsV1,
)


DEFAULT_OWNER_MAX_AGE_SECONDS = 300
DEFAULT_OWNER_FUTURE_TOLERANCE_SECONDS = 30
_SAFE_TEXT = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{2,127}$")


class FinalDecisionReviewApprovedOwnerAcquisitionError(ValueError):
    """Approved owner sources cannot be acquired or bound safely."""


class FinalDecisionReviewApprovedOwnerAcquisitionStatus(StrEnum):
    ACQUIRED = "acquired"
    UNAVAILABLE = "unavailable"


class FinalDecisionReviewApprovedOwnerSourceSlot(StrEnum):
    SERVER_CONTEXT = "server_context"
    DECISION = "decision"
    INTENT = "intent"
    CAPACITY = "capacity"
    PRO_FORMA_SCENARIO = "pro_forma_scenario"
    PURCHASE_PREVIEWS = "purchase_previews"
    SELL_PREVIEWS = "sell_previews"


class FinalDecisionReviewApprovedOwnerSourceStatus(StrEnum):
    AVAILABLE = "available"
    MISSING = "missing"
    FAILED = "failed"
    STALE = "stale"
    NOT_SELECTED = "not_selected"
    NOT_ATTEMPTED = "not_attempted"


OwnerCallableV1 = Callable[[ApprovedCalculatorInvocationRequestV1], object]


def _aware_utc(value: datetime, *, code: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise FinalDecisionReviewApprovedOwnerAcquisitionError(code)
    return value.astimezone(timezone.utc)


def _safe_text(value: str, *, code: str) -> str:
    if not isinstance(value, str):
        raise FinalDecisionReviewApprovedOwnerAcquisitionError(code)
    result = value.strip()
    if _SAFE_TEXT.fullmatch(result) is None:
        raise FinalDecisionReviewApprovedOwnerAcquisitionError(code)
    return result


@dataclass(frozen=True, slots=True)
class FinalDecisionReviewApprovedServerContextV1:
    invocation_id: str
    scenario_id: str
    correlation_id: str
    operation: ApprovedCalculatorOperation
    account: AccountReference
    generated_at: datetime
    authenticated: bool = field(default=True, init=False)
    server_derived: bool = field(default=True, init=False)
    internal_only: bool = field(default=True, init=False)
    raw_payload_accepted: bool = field(default=False, init=False)
    credentials_accepted: bool = field(default=False, init=False)
    full_account_accepted: bool = field(default=False, init=False)
    request_body_accepted: bool = field(default=False, init=False)
    broker_write_called: bool = field(default=False, init=False)
    trade_authorized: bool = field(default=False, init=False)
    order_created: bool = field(default=False, init=False)
    execution_ready: bool = field(default=False, init=False)
    trading_methods: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "invocation_id",
            _safe_text(
                self.invocation_id,
                code="FINAL_DECISION_REVIEW_APPROVED_OWNER_INVOCATION_ID_INVALID",
            ),
        )
        object.__setattr__(
            self,
            "scenario_id",
            _safe_text(
                self.scenario_id,
                code="FINAL_DECISION_REVIEW_APPROVED_OWNER_SCENARIO_ID_INVALID",
            ),
        )
        object.__setattr__(
            self,
            "correlation_id",
            _safe_text(
                self.correlation_id,
                code="FINAL_DECISION_REVIEW_APPROVED_OWNER_CORRELATION_ID_INVALID",
            ),
        )
        if not isinstance(self.operation, ApprovedCalculatorOperation):
            raise FinalDecisionReviewApprovedOwnerAcquisitionError(
                "FINAL_DECISION_REVIEW_APPROVED_OWNER_OPERATION_INVALID"
            )
        if not isinstance(self.account, AccountReference):
            raise FinalDecisionReviewApprovedOwnerAcquisitionError(
                "FINAL_DECISION_REVIEW_APPROVED_OWNER_ACCOUNT_INVALID"
            )
        object.__setattr__(
            self,
            "generated_at",
            _aware_utc(
                self.generated_at,
                code="FINAL_DECISION_REVIEW_APPROVED_OWNER_CONTEXT_TIME_INVALID",
            ),
        )

    def invocation_request(self) -> ApprovedCalculatorInvocationRequestV1:
        return ApprovedCalculatorInvocationRequestV1(
            invocation_id=self.invocation_id,
            scenario_id=self.scenario_id,
            correlation_id=self.correlation_id,
            operation=self.operation,
            invoked_at=self.generated_at,
        )


@dataclass(frozen=True, slots=True)
class FinalDecisionReviewApprovedOwnerLeaseV1:
    slot: FinalDecisionReviewApprovedOwnerSourceSlot
    owner: OwnerCallableV1
    observed_at: datetime
    provider: str
    operation: str
    internal_only: bool = field(default=True, init=False)
    raw_payload_included: bool = field(default=False, init=False)
    credentials_included: bool = field(default=False, init=False)
    full_account_included: bool = field(default=False, init=False)
    broker_write_called: bool = field(default=False, init=False)
    trading_methods: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.slot, FinalDecisionReviewApprovedOwnerSourceSlot)
            or self.slot
            is FinalDecisionReviewApprovedOwnerSourceSlot.SERVER_CONTEXT
        ):
            raise FinalDecisionReviewApprovedOwnerAcquisitionError(
                "FINAL_DECISION_REVIEW_APPROVED_OWNER_LEASE_SLOT_INVALID"
            )
        if not callable(self.owner):
            raise FinalDecisionReviewApprovedOwnerAcquisitionError(
                "FINAL_DECISION_REVIEW_APPROVED_OWNER_LEASE_NOT_CALLABLE"
            )
        object.__setattr__(
            self,
            "observed_at",
            _aware_utc(
                self.observed_at,
                code="FINAL_DECISION_REVIEW_APPROVED_OWNER_LEASE_TIME_INVALID",
            ),
        )
        object.__setattr__(
            self,
            "provider",
            _safe_text(
                self.provider,
                code="FINAL_DECISION_REVIEW_APPROVED_OWNER_PROVIDER_INVALID",
            ),
        )
        object.__setattr__(
            self,
            "operation",
            _safe_text(
                self.operation,
                code="FINAL_DECISION_REVIEW_APPROVED_OWNER_SOURCE_OPERATION_INVALID",
            ),
        )


ApprovedOwnerLeaseLoaderV1 = Callable[
    [FinalDecisionReviewApprovedServerContextV1],
    FinalDecisionReviewApprovedOwnerLeaseV1 | None,
]


@dataclass(frozen=True, slots=True)
class FinalDecisionReviewApprovedOwnerLoaderV1:
    slot: FinalDecisionReviewApprovedOwnerSourceSlot
    provider: str
    operation: str
    load: ApprovedOwnerLeaseLoaderV1

    def __post_init__(self) -> None:
        if (
            not isinstance(self.slot, FinalDecisionReviewApprovedOwnerSourceSlot)
            or self.slot
            is FinalDecisionReviewApprovedOwnerSourceSlot.SERVER_CONTEXT
        ):
            raise FinalDecisionReviewApprovedOwnerAcquisitionError(
                "FINAL_DECISION_REVIEW_APPROVED_OWNER_LOADER_SLOT_INVALID"
            )
        object.__setattr__(
            self,
            "provider",
            _safe_text(
                self.provider,
                code="FINAL_DECISION_REVIEW_APPROVED_OWNER_PROVIDER_INVALID",
            ),
        )
        object.__setattr__(
            self,
            "operation",
            _safe_text(
                self.operation,
                code="FINAL_DECISION_REVIEW_APPROVED_OWNER_SOURCE_OPERATION_INVALID",
            ),
        )
        if not callable(self.load):
            raise FinalDecisionReviewApprovedOwnerAcquisitionError(
                "FINAL_DECISION_REVIEW_APPROVED_OWNER_LOADER_NOT_CALLABLE"
            )


@dataclass(frozen=True, slots=True)
class FinalDecisionReviewApprovedOwnerSourceLoadersV1:
    decision: FinalDecisionReviewApprovedOwnerLoaderV1
    intent: FinalDecisionReviewApprovedOwnerLoaderV1
    capacity: FinalDecisionReviewApprovedOwnerLoaderV1
    pro_forma_scenario: FinalDecisionReviewApprovedOwnerLoaderV1
    purchase_previews: FinalDecisionReviewApprovedOwnerLoaderV1
    sell_previews: FinalDecisionReviewApprovedOwnerLoaderV1

    def __post_init__(self) -> None:
        expected = (
            (
                self.decision,
                FinalDecisionReviewApprovedOwnerSourceSlot.DECISION,
            ),
            (
                self.intent,
                FinalDecisionReviewApprovedOwnerSourceSlot.INTENT,
            ),
            (
                self.capacity,
                FinalDecisionReviewApprovedOwnerSourceSlot.CAPACITY,
            ),
            (
                self.pro_forma_scenario,
                FinalDecisionReviewApprovedOwnerSourceSlot.PRO_FORMA_SCENARIO,
            ),
            (
                self.purchase_previews,
                FinalDecisionReviewApprovedOwnerSourceSlot.PURCHASE_PREVIEWS,
            ),
            (
                self.sell_previews,
                FinalDecisionReviewApprovedOwnerSourceSlot.SELL_PREVIEWS,
            ),
        )
        if any(
            not isinstance(loader, FinalDecisionReviewApprovedOwnerLoaderV1)
            or loader.slot is not slot
            for loader, slot in expected
        ):
            raise FinalDecisionReviewApprovedOwnerAcquisitionError(
                "FINAL_DECISION_REVIEW_APPROVED_OWNER_LOADER_SET_INVALID"
            )

    def by_slot(
        self,
    ) -> dict[
        FinalDecisionReviewApprovedOwnerSourceSlot,
        FinalDecisionReviewApprovedOwnerLoaderV1,
    ]:
        return {
            self.decision.slot: self.decision,
            self.intent.slot: self.intent,
            self.capacity.slot: self.capacity,
            self.pro_forma_scenario.slot: self.pro_forma_scenario,
            self.purchase_previews.slot: self.purchase_previews,
            self.sell_previews.slot: self.sell_previews,
        }


@dataclass(frozen=True, slots=True)
class FinalDecisionReviewApprovedOwnerSourceEvidenceV1:
    slot: FinalDecisionReviewApprovedOwnerSourceSlot
    status: FinalDecisionReviewApprovedOwnerSourceStatus
    attempted: bool
    provider: str
    operation: str
    observed_at: datetime | None = None
    error_code: str | None = None
    payload_logged: bool = field(default=False, init=False)
    credentials_logged: bool = field(default=False, init=False)
    full_account_logged: bool = field(default=False, init=False)
    exception_text_logged: bool = field(default=False, init=False)
    broker_write_called: bool = field(default=False, init=False)
    trading_methods: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.slot, FinalDecisionReviewApprovedOwnerSourceSlot):
            raise FinalDecisionReviewApprovedOwnerAcquisitionError(
                "FINAL_DECISION_REVIEW_APPROVED_OWNER_EVIDENCE_SLOT_INVALID"
            )
        if not isinstance(self.status, FinalDecisionReviewApprovedOwnerSourceStatus):
            raise FinalDecisionReviewApprovedOwnerAcquisitionError(
                "FINAL_DECISION_REVIEW_APPROVED_OWNER_EVIDENCE_STATUS_INVALID"
            )
        object.__setattr__(
            self,
            "provider",
            _safe_text(
                self.provider,
                code="FINAL_DECISION_REVIEW_APPROVED_OWNER_PROVIDER_INVALID",
            ),
        )
        object.__setattr__(
            self,
            "operation",
            _safe_text(
                self.operation,
                code="FINAL_DECISION_REVIEW_APPROVED_OWNER_SOURCE_OPERATION_INVALID",
            ),
        )
        if self.observed_at is not None:
            object.__setattr__(
                self,
                "observed_at",
                _aware_utc(
                    self.observed_at,
                    code="FINAL_DECISION_REVIEW_APPROVED_OWNER_EVIDENCE_TIME_INVALID",
                ),
            )
        if self.error_code is not None:
            object.__setattr__(
                self,
                "error_code",
                _safe_text(
                    self.error_code,
                    code="FINAL_DECISION_REVIEW_APPROVED_OWNER_ERROR_CODE_INVALID",
                ),
            )
        observed_required = self.status in {
            FinalDecisionReviewApprovedOwnerSourceStatus.AVAILABLE,
            FinalDecisionReviewApprovedOwnerSourceStatus.STALE,
        }
        attempted_required = self.status not in {
            FinalDecisionReviewApprovedOwnerSourceStatus.NOT_SELECTED,
            FinalDecisionReviewApprovedOwnerSourceStatus.NOT_ATTEMPTED,
        }
        if observed_required is not (self.observed_at is not None):
            raise FinalDecisionReviewApprovedOwnerAcquisitionError(
                "FINAL_DECISION_REVIEW_APPROVED_OWNER_EVIDENCE_TIME_MISMATCH"
            )
        if self.attempted is not attempted_required:
            raise FinalDecisionReviewApprovedOwnerAcquisitionError(
                "FINAL_DECISION_REVIEW_APPROVED_OWNER_EVIDENCE_ATTEMPT_MISMATCH"
            )


@dataclass(frozen=True, slots=True)
class FinalDecisionReviewApprovedOwnerAcquisitionResultV1:
    acquired_at: datetime
    status: FinalDecisionReviewApprovedOwnerAcquisitionStatus
    source_evidence: tuple[
        FinalDecisionReviewApprovedOwnerSourceEvidenceV1,
        ...,
    ]
    context: FinalDecisionReviewApprovedServerContextV1 | None
    request: ApprovedCalculatorInvocationRequestV1 | None
    composition_result: FinalDecisionReviewTrustedOwnerCompositionResultV1 | None
    primary_blocker: str | None
    handler_error_code: FinalDecisionReviewHandlerErrorCode | None
    handler_http_status: FinalDecisionReviewHandlerHttpStatus | None
    composition_called: bool
    sources_fresh: bool
    internal_only: bool = field(default=True, init=False)
    raw_payload_accepted: bool = field(default=False, init=False)
    credentials_accepted: bool = field(default=False, init=False)
    full_account_accepted: bool = field(default=False, init=False)
    request_body_accepted: bool = field(default=False, init=False)
    http_route_created: bool = field(default=False, init=False)
    production_openapi_changed: bool = field(default=False, init=False)
    broker_write_called: bool = field(default=False, init=False)
    trade_authorized: bool = field(default=False, init=False)
    order_created: bool = field(default=False, init=False)
    execution_ready: bool = field(default=False, init=False)
    trading_methods: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "acquired_at",
            _aware_utc(
                self.acquired_at,
                code="FINAL_DECISION_REVIEW_APPROVED_OWNER_RESULT_TIME_INVALID",
            ),
        )
        slots = tuple(row.slot for row in self.source_evidence)
        if slots != tuple(FinalDecisionReviewApprovedOwnerSourceSlot):
            raise FinalDecisionReviewApprovedOwnerAcquisitionError(
                "FINAL_DECISION_REVIEW_APPROVED_OWNER_EVIDENCE_SET_INVALID"
            )
        if self.primary_blocker is not None:
            object.__setattr__(
                self,
                "primary_blocker",
                _safe_text(
                    self.primary_blocker,
                    code="FINAL_DECISION_REVIEW_APPROVED_OWNER_BLOCKER_INVALID",
                ),
            )
        if self.status is FinalDecisionReviewApprovedOwnerAcquisitionStatus.ACQUIRED:
            if (
                self.context is None
                or self.request is None
                or self.composition_result is None
                or not self.composition_called
                or not self.sources_fresh
                or self.primary_blocker is not None
                or self.handler_error_code is not None
                or self.handler_http_status is not None
                or self.composition_result.request != self.request
            ):
                raise FinalDecisionReviewApprovedOwnerAcquisitionError(
                    "FINAL_DECISION_REVIEW_APPROVED_OWNER_RESULT_INVALID"
                )
        elif (
            self.composition_result is not None
            or self.primary_blocker is None
            or self.handler_error_code
            is not FinalDecisionReviewHandlerErrorCode.SOURCE_UNAVAILABLE
            or self.handler_http_status
            is not FinalDecisionReviewHandlerHttpStatus.SERVICE_UNAVAILABLE
        ):
            raise FinalDecisionReviewApprovedOwnerAcquisitionError(
                "FINAL_DECISION_REVIEW_APPROVED_OWNER_UNAVAILABLE_RESULT_INVALID"
            )


def _missing_owner_source_loaders(
) -> FinalDecisionReviewApprovedOwnerSourceLoadersV1:
    def missing(
        _: FinalDecisionReviewApprovedServerContextV1,
    ) -> FinalDecisionReviewApprovedOwnerLeaseV1 | None:
        return None

    def loader(
        slot: FinalDecisionReviewApprovedOwnerSourceSlot,
    ) -> FinalDecisionReviewApprovedOwnerLoaderV1:
        return FinalDecisionReviewApprovedOwnerLoaderV1(
            slot=slot,
            provider="omni-cio",
            operation=f"load-{slot.value}-owner",
            load=missing,
        )

    return FinalDecisionReviewApprovedOwnerSourceLoadersV1(
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


def unavailable_final_decision_review_approved_owner_source_loaders(
) -> FinalDecisionReviewApprovedOwnerSourceLoadersV1:
    """Return fixed missing loaders for fail-closed production startup."""
    return _missing_owner_source_loaders()


def _fresh(
    observed_at: datetime,
    *,
    checked_at: datetime,
    max_age_seconds: int,
    future_tolerance_seconds: int,
) -> bool:
    age_seconds = (checked_at - observed_at).total_seconds()
    return (
        age_seconds <= max_age_seconds
        and age_seconds >= -future_tolerance_seconds
    )


def _evidence(
    *,
    slot: FinalDecisionReviewApprovedOwnerSourceSlot,
    status: FinalDecisionReviewApprovedOwnerSourceStatus,
    attempted: bool,
    provider: str,
    operation: str,
    observed_at: datetime | None = None,
    error_code: str | None = None,
) -> FinalDecisionReviewApprovedOwnerSourceEvidenceV1:
    return FinalDecisionReviewApprovedOwnerSourceEvidenceV1(
        slot=slot,
        status=status,
        attempted=attempted,
        provider=provider,
        operation=operation,
        observed_at=observed_at,
        error_code=error_code,
    )


def _ordered_evidence(
    values: dict[
        FinalDecisionReviewApprovedOwnerSourceSlot,
        FinalDecisionReviewApprovedOwnerSourceEvidenceV1,
    ],
) -> tuple[FinalDecisionReviewApprovedOwnerSourceEvidenceV1, ...]:
    return tuple(values[slot] for slot in FinalDecisionReviewApprovedOwnerSourceSlot)


def _not_attempted_evidence(
    loaders: FinalDecisionReviewApprovedOwnerSourceLoadersV1,
) -> dict[
    FinalDecisionReviewApprovedOwnerSourceSlot,
    FinalDecisionReviewApprovedOwnerSourceEvidenceV1,
]:
    return {
        slot: _evidence(
            slot=slot,
            status=FinalDecisionReviewApprovedOwnerSourceStatus.NOT_ATTEMPTED,
            attempted=False,
            provider=loader.provider,
            operation=loader.operation,
        )
        for slot, loader in loaders.by_slot().items()
    }


def _unavailable(
    *,
    acquired_at: datetime,
    evidence: dict[
        FinalDecisionReviewApprovedOwnerSourceSlot,
        FinalDecisionReviewApprovedOwnerSourceEvidenceV1,
    ],
    blocker: str,
    context: FinalDecisionReviewApprovedServerContextV1 | None = None,
    request: ApprovedCalculatorInvocationRequestV1 | None = None,
    composition_called: bool = False,
    sources_fresh: bool = False,
) -> FinalDecisionReviewApprovedOwnerAcquisitionResultV1:
    return FinalDecisionReviewApprovedOwnerAcquisitionResultV1(
        acquired_at=acquired_at,
        status=FinalDecisionReviewApprovedOwnerAcquisitionStatus.UNAVAILABLE,
        source_evidence=_ordered_evidence(evidence),
        context=context,
        request=request,
        composition_result=None,
        primary_blocker=blocker,
        handler_error_code=FinalDecisionReviewHandlerErrorCode.SOURCE_UNAVAILABLE,
        handler_http_status=(
            FinalDecisionReviewHandlerHttpStatus.SERVICE_UNAVAILABLE
        ),
        composition_called=composition_called,
        sources_fresh=sources_fresh,
    )


def _load_lease(
    *,
    loader: FinalDecisionReviewApprovedOwnerLoaderV1,
    context: FinalDecisionReviewApprovedServerContextV1,
    acquired_at: datetime,
    max_age_seconds: int,
    future_tolerance_seconds: int,
) -> tuple[
    FinalDecisionReviewApprovedOwnerSourceEvidenceV1,
    FinalDecisionReviewApprovedOwnerLeaseV1 | None,
]:
    try:
        lease = loader.load(context)
    except TimeoutError:
        return (
            _evidence(
                slot=loader.slot,
                status=FinalDecisionReviewApprovedOwnerSourceStatus.FAILED,
                attempted=True,
                provider=loader.provider,
                operation=loader.operation,
                error_code="SOURCE_TIMEOUT",
            ),
            None,
        )
    except Exception:
        return (
            _evidence(
                slot=loader.slot,
                status=FinalDecisionReviewApprovedOwnerSourceStatus.FAILED,
                attempted=True,
                provider=loader.provider,
                operation=loader.operation,
                error_code="SOURCE_LOAD_FAILED",
            ),
            None,
        )
    if lease is None:
        return (
            _evidence(
                slot=loader.slot,
                status=FinalDecisionReviewApprovedOwnerSourceStatus.MISSING,
                attempted=True,
                provider=loader.provider,
                operation=loader.operation,
                error_code="SOURCE_MISSING",
            ),
            None,
        )
    if (
        not isinstance(lease, FinalDecisionReviewApprovedOwnerLeaseV1)
        or lease.slot is not loader.slot
        or lease.provider != loader.provider
        or lease.operation != loader.operation
    ):
        return (
            _evidence(
                slot=loader.slot,
                status=FinalDecisionReviewApprovedOwnerSourceStatus.FAILED,
                attempted=True,
                provider=loader.provider,
                operation=loader.operation,
                error_code="SOURCE_BINDING_INVALID",
            ),
            None,
        )
    if not _fresh(
        lease.observed_at,
        checked_at=acquired_at,
        max_age_seconds=max_age_seconds,
        future_tolerance_seconds=future_tolerance_seconds,
    ):
        return (
            _evidence(
                slot=loader.slot,
                status=FinalDecisionReviewApprovedOwnerSourceStatus.STALE,
                attempted=True,
                provider=loader.provider,
                operation=loader.operation,
                observed_at=lease.observed_at,
                error_code="SOURCE_STALE",
            ),
            None,
        )
    return (
        _evidence(
            slot=loader.slot,
            status=FinalDecisionReviewApprovedOwnerSourceStatus.AVAILABLE,
            attempted=True,
            provider=loader.provider,
            operation=loader.operation,
            observed_at=lease.observed_at,
        ),
        lease,
    )


def _exact_request(
    expected: ApprovedCalculatorInvocationRequestV1,
    actual: ApprovedCalculatorInvocationRequestV1,
) -> None:
    if actual != expected:
        raise FinalDecisionReviewApprovedOwnerAcquisitionError(
            "FINAL_DECISION_REVIEW_APPROVED_OWNER_REQUEST_MISMATCH"
        )


def _bound_decision_owner(
    owner: OwnerCallableV1,
    *,
    request: ApprovedCalculatorInvocationRequestV1,
    account: AccountReference,
) -> Callable[[ApprovedCalculatorInvocationRequestV1], DecisionSetV1]:
    def load(actual: ApprovedCalculatorInvocationRequestV1) -> DecisionSetV1:
        _exact_request(request, actual)
        value = owner(actual)
        if (
            not isinstance(value, DecisionSetV1)
            or value.metadata.account != account
        ):
            raise FinalDecisionReviewApprovedOwnerAcquisitionError(
                "FINAL_DECISION_REVIEW_APPROVED_OWNER_ACCOUNT_MISMATCH"
            )
        return value

    return load


def _bound_intent_owner(
    owner: OwnerCallableV1,
    *,
    request: ApprovedCalculatorInvocationRequestV1,
) -> Callable[
    [ApprovedCalculatorInvocationRequestV1],
    CapacityIntentDecisionGateRequestV1,
]:
    def load(
        actual: ApprovedCalculatorInvocationRequestV1,
    ) -> CapacityIntentDecisionGateRequestV1:
        _exact_request(request, actual)
        return cast(CapacityIntentDecisionGateRequestV1, owner(actual))

    return load


def _bound_capacity_owner(
    owner: OwnerCallableV1,
    *,
    request: ApprovedCalculatorInvocationRequestV1,
) -> Callable[
    [ApprovedCalculatorInvocationRequestV1],
    Iterable[CapacityAssessmentV1],
]:
    def load(
        actual: ApprovedCalculatorInvocationRequestV1,
    ) -> Iterable[CapacityAssessmentV1]:
        _exact_request(request, actual)
        return cast(Iterable[CapacityAssessmentV1], owner(actual))

    return load


def _bound_scenario_owner(
    owner: OwnerCallableV1,
    *,
    request: ApprovedCalculatorInvocationRequestV1,
    account: AccountReference,
) -> Callable[
    [ApprovedCalculatorInvocationRequestV1],
    ProFormaRiskScenarioV1,
]:
    def load(
        actual: ApprovedCalculatorInvocationRequestV1,
    ) -> ProFormaRiskScenarioV1:
        _exact_request(request, actual)
        value = owner(actual)
        if (
            not isinstance(value, ProFormaRiskScenarioV1)
            or value.account != account
        ):
            raise FinalDecisionReviewApprovedOwnerAcquisitionError(
                "FINAL_DECISION_REVIEW_APPROVED_OWNER_ACCOUNT_MISMATCH"
            )
        return value

    return load


def _bound_purchase_preview_owner(
    owner: OwnerCallableV1,
    *,
    request: ApprovedCalculatorInvocationRequestV1,
    account: AccountReference,
) -> Callable[
    [ApprovedCalculatorInvocationRequestV1],
    Iterable[PreTradePreviewV1],
]:
    def load(
        actual: ApprovedCalculatorInvocationRequestV1,
    ) -> Iterable[PreTradePreviewV1]:
        _exact_request(request, actual)
        values = cast(Iterable[PreTradePreviewV1], owner(actual))

        def checked() -> Iterable[PreTradePreviewV1]:
            for value in values:
                if (
                    not isinstance(value, PreTradePreviewV1)
                    or value.metadata.account != account
                ):
                    raise FinalDecisionReviewApprovedOwnerAcquisitionError(
                        "FINAL_DECISION_REVIEW_APPROVED_OWNER_ACCOUNT_MISMATCH"
                    )
                yield value

        return checked()

    return load


def _bound_sell_preview_owner(
    owner: OwnerCallableV1,
    *,
    request: ApprovedCalculatorInvocationRequestV1,
    account: AccountReference,
) -> Callable[
    [ApprovedCalculatorInvocationRequestV1],
    Iterable[SellPreTradePreviewV1],
]:
    def load(
        actual: ApprovedCalculatorInvocationRequestV1,
    ) -> Iterable[SellPreTradePreviewV1]:
        _exact_request(request, actual)
        values = cast(Iterable[SellPreTradePreviewV1], owner(actual))

        def checked() -> Iterable[SellPreTradePreviewV1]:
            for value in values:
                if (
                    not isinstance(value, SellPreTradePreviewV1)
                    or value.metadata.account != account
                ):
                    raise FinalDecisionReviewApprovedOwnerAcquisitionError(
                        "FINAL_DECISION_REVIEW_APPROVED_OWNER_ACCOUNT_MISMATCH"
                    )
                yield value

        return checked()

    return load


def _source_blocker(
    evidence: tuple[FinalDecisionReviewApprovedOwnerSourceEvidenceV1, ...],
) -> str:
    for row in evidence:
        if row.status is FinalDecisionReviewApprovedOwnerSourceStatus.MISSING:
            return "FINAL_DECISION_REVIEW_APPROVED_OWNER_SOURCE_MISSING"
        if row.status is FinalDecisionReviewApprovedOwnerSourceStatus.STALE:
            return "FINAL_DECISION_REVIEW_APPROVED_OWNER_SOURCE_STALE"
        if row.status is FinalDecisionReviewApprovedOwnerSourceStatus.FAILED:
            return "FINAL_DECISION_REVIEW_APPROVED_OWNER_SOURCE_FAILED"
    return "FINAL_DECISION_REVIEW_APPROVED_OWNER_SOURCE_UNAVAILABLE"


class FinalDecisionReviewApprovedOwnerAcquisitionV1:
    """Acquire fresh server-owned ports before one trusted PR-78 invocation."""

    def __init__(
        self,
        *,
        composition: FinalDecisionReviewTrustedOwnerCompositionV1,
        context_loader: Callable[
            [],
            FinalDecisionReviewApprovedServerContextV1 | None,
        ],
        source_loaders: FinalDecisionReviewApprovedOwnerSourceLoadersV1,
        max_source_age_seconds: int = DEFAULT_OWNER_MAX_AGE_SECONDS,
        future_tolerance_seconds: int = (
            DEFAULT_OWNER_FUTURE_TOLERANCE_SECONDS
        ),
    ) -> None:
        if not isinstance(
            composition,
            FinalDecisionReviewTrustedOwnerCompositionV1,
        ):
            raise FinalDecisionReviewApprovedOwnerAcquisitionError(
                "FINAL_DECISION_REVIEW_APPROVED_OWNER_COMPOSITION_TYPE_INVALID"
            )
        if not callable(context_loader):
            raise FinalDecisionReviewApprovedOwnerAcquisitionError(
                "FINAL_DECISION_REVIEW_APPROVED_OWNER_CONTEXT_LOADER_NOT_CALLABLE"
            )
        if not isinstance(
            source_loaders,
            FinalDecisionReviewApprovedOwnerSourceLoadersV1,
        ):
            raise FinalDecisionReviewApprovedOwnerAcquisitionError(
                "FINAL_DECISION_REVIEW_APPROVED_OWNER_LOADER_SET_INVALID"
            )
        if not 1 <= max_source_age_seconds <= 86_400:
            raise FinalDecisionReviewApprovedOwnerAcquisitionError(
                "FINAL_DECISION_REVIEW_APPROVED_OWNER_MAX_AGE_INVALID"
            )
        if not 0 <= future_tolerance_seconds <= 3_600:
            raise FinalDecisionReviewApprovedOwnerAcquisitionError(
                "FINAL_DECISION_REVIEW_APPROVED_OWNER_FUTURE_TOLERANCE_INVALID"
            )
        self._composition = composition
        self._context_loader = context_loader
        self._source_loaders = source_loaders
        self._max_source_age_seconds = max_source_age_seconds
        self._future_tolerance_seconds = future_tolerance_seconds

    @property
    def composition(self) -> FinalDecisionReviewTrustedOwnerCompositionV1:
        return self._composition

    @property
    def source_loaders(self) -> FinalDecisionReviewApprovedOwnerSourceLoadersV1:
        return self._source_loaders

    def acquire(
        self,
        *,
        acquired_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> FinalDecisionReviewApprovedOwnerAcquisitionResultV1:
        now = (
            datetime.now(timezone.utc)
            if acquired_at is None
            else _aware_utc(
                acquired_at,
                code="FINAL_DECISION_REVIEW_APPROVED_OWNER_ACQUIRED_AT_INVALID",
            )
        )
        evidence = _not_attempted_evidence(self._source_loaders)
        try:
            context = self._context_loader()
        except Exception:
            evidence[
                FinalDecisionReviewApprovedOwnerSourceSlot.SERVER_CONTEXT
            ] = _evidence(
                slot=FinalDecisionReviewApprovedOwnerSourceSlot.SERVER_CONTEXT,
                status=FinalDecisionReviewApprovedOwnerSourceStatus.FAILED,
                attempted=True,
                provider="omni-cio",
                operation="load-server-context",
                error_code="CONTEXT_LOAD_FAILED",
            )
            return _unavailable(
                acquired_at=now,
                evidence=evidence,
                blocker="FINAL_DECISION_REVIEW_APPROVED_OWNER_CONTEXT_UNAVAILABLE",
            )
        if context is None:
            evidence[
                FinalDecisionReviewApprovedOwnerSourceSlot.SERVER_CONTEXT
            ] = _evidence(
                slot=FinalDecisionReviewApprovedOwnerSourceSlot.SERVER_CONTEXT,
                status=FinalDecisionReviewApprovedOwnerSourceStatus.MISSING,
                attempted=True,
                provider="omni-cio",
                operation="load-server-context",
                error_code="CONTEXT_MISSING",
            )
            return _unavailable(
                acquired_at=now,
                evidence=evidence,
                blocker="FINAL_DECISION_REVIEW_APPROVED_OWNER_CONTEXT_UNAVAILABLE",
            )
        if not isinstance(context, FinalDecisionReviewApprovedServerContextV1):
            evidence[
                FinalDecisionReviewApprovedOwnerSourceSlot.SERVER_CONTEXT
            ] = _evidence(
                slot=FinalDecisionReviewApprovedOwnerSourceSlot.SERVER_CONTEXT,
                status=FinalDecisionReviewApprovedOwnerSourceStatus.FAILED,
                attempted=True,
                provider="omni-cio",
                operation="load-server-context",
                error_code="CONTEXT_TYPE_INVALID",
            )
            return _unavailable(
                acquired_at=now,
                evidence=evidence,
                blocker="FINAL_DECISION_REVIEW_APPROVED_OWNER_CONTEXT_UNAVAILABLE",
            )
        if not _fresh(
            context.generated_at,
            checked_at=now,
            max_age_seconds=self._max_source_age_seconds,
            future_tolerance_seconds=self._future_tolerance_seconds,
        ):
            evidence[
                FinalDecisionReviewApprovedOwnerSourceSlot.SERVER_CONTEXT
            ] = _evidence(
                slot=FinalDecisionReviewApprovedOwnerSourceSlot.SERVER_CONTEXT,
                status=FinalDecisionReviewApprovedOwnerSourceStatus.STALE,
                attempted=True,
                provider="omni-cio",
                operation="load-server-context",
                observed_at=context.generated_at,
                error_code="CONTEXT_STALE",
            )
            return _unavailable(
                acquired_at=now,
                evidence=evidence,
                blocker="FINAL_DECISION_REVIEW_APPROVED_OWNER_CONTEXT_STALE",
                context=context,
                request=context.invocation_request(),
            )

        evidence[
            FinalDecisionReviewApprovedOwnerSourceSlot.SERVER_CONTEXT
        ] = _evidence(
            slot=FinalDecisionReviewApprovedOwnerSourceSlot.SERVER_CONTEXT,
            status=FinalDecisionReviewApprovedOwnerSourceStatus.AVAILABLE,
            attempted=True,
            provider="omni-cio",
            operation="load-server-context",
            observed_at=context.generated_at,
        )
        request = context.invocation_request()
        preview_slot = (
            FinalDecisionReviewApprovedOwnerSourceSlot.PURCHASE_PREVIEWS
            if context.operation
            is ApprovedCalculatorOperation.PURCHASE_REVIEW
            else FinalDecisionReviewApprovedOwnerSourceSlot.SELL_PREVIEWS
        )
        unselected_preview_slot = (
            FinalDecisionReviewApprovedOwnerSourceSlot.SELL_PREVIEWS
            if preview_slot
            is FinalDecisionReviewApprovedOwnerSourceSlot.PURCHASE_PREVIEWS
            else FinalDecisionReviewApprovedOwnerSourceSlot.PURCHASE_PREVIEWS
        )
        loaders_by_slot = self._source_loaders.by_slot()
        unselected_loader = loaders_by_slot[unselected_preview_slot]
        evidence[unselected_preview_slot] = _evidence(
            slot=unselected_preview_slot,
            status=FinalDecisionReviewApprovedOwnerSourceStatus.NOT_SELECTED,
            attempted=False,
            provider=unselected_loader.provider,
            operation=unselected_loader.operation,
        )
        selected_slots = (
            FinalDecisionReviewApprovedOwnerSourceSlot.DECISION,
            FinalDecisionReviewApprovedOwnerSourceSlot.INTENT,
            FinalDecisionReviewApprovedOwnerSourceSlot.CAPACITY,
            FinalDecisionReviewApprovedOwnerSourceSlot.PRO_FORMA_SCENARIO,
            preview_slot,
        )
        leases: dict[
            FinalDecisionReviewApprovedOwnerSourceSlot,
            FinalDecisionReviewApprovedOwnerLeaseV1,
        ] = {}
        for slot in selected_slots:
            row, lease = _load_lease(
                loader=loaders_by_slot[slot],
                context=context,
                acquired_at=now,
                max_age_seconds=self._max_source_age_seconds,
                future_tolerance_seconds=self._future_tolerance_seconds,
            )
            evidence[slot] = row
            if lease is not None:
                leases[slot] = lease

        ordered = _ordered_evidence(evidence)
        if len(leases) != len(selected_slots):
            return _unavailable(
                acquired_at=now,
                evidence=evidence,
                blocker=_source_blocker(ordered),
                context=context,
                request=request,
            )

        common = FinalDecisionReviewTrustedCommonOwnerPortsV1(
            decision=_bound_decision_owner(
                leases[
                    FinalDecisionReviewApprovedOwnerSourceSlot.DECISION
                ].owner,
                request=request,
                account=context.account,
            ),
            intent=_bound_intent_owner(
                leases[
                    FinalDecisionReviewApprovedOwnerSourceSlot.INTENT
                ].owner,
                request=request,
            ),
            capacity=_bound_capacity_owner(
                leases[
                    FinalDecisionReviewApprovedOwnerSourceSlot.CAPACITY
                ].owner,
                request=request,
            ),
            pro_forma_scenario=_bound_scenario_owner(
                leases[
                    FinalDecisionReviewApprovedOwnerSourceSlot.PRO_FORMA_SCENARIO
                ].owner,
                request=request,
                account=context.account,
            ),
        )
        try:
            if (
                context.operation
                is ApprovedCalculatorOperation.PURCHASE_REVIEW
            ):
                composition_result = self._composition.invoke_purchase(
                    request=request,
                    owners=FinalDecisionReviewTrustedPurchaseOwnerPortsV1(
                        common=common,
                        previews=_bound_purchase_preview_owner(
                            leases[preview_slot].owner,
                            request=request,
                            account=context.account,
                        ),
                    ),
                    completed_at=completed_at,
                )
            else:
                composition_result = self._composition.invoke_sell(
                    request=request,
                    owners=FinalDecisionReviewTrustedSellOwnerPortsV1(
                        common=common,
                        previews=_bound_sell_preview_owner(
                            leases[preview_slot].owner,
                            request=request,
                            account=context.account,
                        ),
                    ),
                    completed_at=completed_at,
                )
        except Exception:
            return _unavailable(
                acquired_at=now,
                evidence=evidence,
                blocker=(
                    "FINAL_DECISION_REVIEW_APPROVED_OWNER_COMPOSITION_FAILED"
                ),
                context=context,
                request=request,
                composition_called=True,
                sources_fresh=True,
            )

        return FinalDecisionReviewApprovedOwnerAcquisitionResultV1(
            acquired_at=now,
            status=FinalDecisionReviewApprovedOwnerAcquisitionStatus.ACQUIRED,
            source_evidence=ordered,
            context=context,
            request=request,
            composition_result=composition_result,
            primary_blocker=None,
            handler_error_code=None,
            handler_http_status=None,
            composition_called=True,
            sources_fresh=True,
        )
