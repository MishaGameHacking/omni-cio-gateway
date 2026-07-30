from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from threading import RLock

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
    FinalDecisionReviewApprovedOwnerSnapshotStoreV1,
)
from omni_cio.release.final_decision_review_authenticated_route_context_v1 import (
    FinalDecisionReviewApprovedRouteContextCaptureV1,
    FinalDecisionReviewApprovedRouteContextStoreV1,
)


DEFAULT_AUTHENTICATED_OWNER_EVIDENCE_TTL_SECONDS = 300
DEFAULT_AUTHENTICATED_OWNER_EVIDENCE_CAPACITY = 64


class FinalDecisionReviewAuthenticatedOwnerInstallationError(ValueError):
    """Authenticated owner installation lifecycle cannot be wired safely."""


class FinalDecisionReviewAuthenticatedOwnerInstallationStatus(StrEnum):
    ACQUIRED = "acquired"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class FinalDecisionReviewAuthenticatedOwnerInstallationEvidenceV1:
    invocation_id: str
    scenario_id: str
    correlation_id: str
    operation: ApprovedCalculatorOperation
    observed_at: datetime
    expires_at: datetime
    status: FinalDecisionReviewAuthenticatedOwnerInstallationStatus
    snapshot_selected: bool
    installation_called: bool
    acquisition_status: FinalDecisionReviewApprovedOwnerAcquisitionStatus | None
    primary_blocker: str | None
    handler_error_code: FinalDecisionReviewHandlerErrorCode | None
    handler_http_status: FinalDecisionReviewHandlerHttpStatus | None
    active_evidence_count: int
    evicted: bool
    internal_only: bool = True
    response_changed: bool = False
    openapi_changed: bool = False
    raw_action_payload_accepted: bool = False
    credentials_present: bool = False
    full_account_identifier_present: bool = False
    exception_text_present: bool = False
    broker_write_called: bool = False
    trade_authorized: bool = False
    order_created: bool = False
    execution_ready: bool = False
    trading_methods: bool = False

    def __post_init__(self) -> None:
        observed = _aware_utc(self.observed_at)
        expires = _aware_utc(self.expires_at)
        object.__setattr__(self, "observed_at", observed)
        object.__setattr__(self, "expires_at", expires)
        if expires <= observed:
            raise FinalDecisionReviewAuthenticatedOwnerInstallationError(
                "FINAL_DECISION_REVIEW_AUTHENTICATED_OWNER_EVIDENCE_EXPIRY_INVALID"
            )
        if self.status is FinalDecisionReviewAuthenticatedOwnerInstallationStatus.ACQUIRED:
            if (
                not self.snapshot_selected
                or not self.installation_called
                or self.acquisition_status
                is not FinalDecisionReviewApprovedOwnerAcquisitionStatus.ACQUIRED
                or self.primary_blocker is not None
                or self.handler_error_code is not None
                or self.handler_http_status is not None
            ):
                raise FinalDecisionReviewAuthenticatedOwnerInstallationError(
                    "FINAL_DECISION_REVIEW_AUTHENTICATED_OWNER_EVIDENCE_INVALID"
                )
        elif self.status is FinalDecisionReviewAuthenticatedOwnerInstallationStatus.UNAVAILABLE:
            if self.primary_blocker is None:
                raise FinalDecisionReviewAuthenticatedOwnerInstallationError(
                    "FINAL_DECISION_REVIEW_AUTHENTICATED_OWNER_EVIDENCE_INVALID"
                )
        elif self.status is FinalDecisionReviewAuthenticatedOwnerInstallationStatus.FAILED:
            if self.primary_blocker is None:
                raise FinalDecisionReviewAuthenticatedOwnerInstallationError(
                    "FINAL_DECISION_REVIEW_AUTHENTICATED_OWNER_EVIDENCE_INVALID"
                )


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if (
        not isinstance(result, datetime)
        or result.tzinfo is None
        or result.utcoffset() is None
    ):
        raise FinalDecisionReviewAuthenticatedOwnerInstallationError(
            "FINAL_DECISION_REVIEW_AUTHENTICATED_OWNER_TIMESTAMP_INVALID"
        )
    return result.astimezone(timezone.utc)


class FinalDecisionReviewAuthenticatedOwnerEvidenceStoreV1:
    """Bounded process-local evidence for one post-auth installation attempt."""

    def __init__(
        self,
        *,
        ttl_seconds: int = DEFAULT_AUTHENTICATED_OWNER_EVIDENCE_TTL_SECONDS,
        capacity: int = DEFAULT_AUTHENTICATED_OWNER_EVIDENCE_CAPACITY,
    ) -> None:
        if not 1 <= ttl_seconds <= 3_600:
            raise FinalDecisionReviewAuthenticatedOwnerInstallationError(
                "FINAL_DECISION_REVIEW_AUTHENTICATED_OWNER_EVIDENCE_TTL_INVALID"
            )
        if not 1 <= capacity <= 1_024:
            raise FinalDecisionReviewAuthenticatedOwnerInstallationError(
                "FINAL_DECISION_REVIEW_AUTHENTICATED_OWNER_EVIDENCE_CAPACITY_INVALID"
            )
        self._ttl = timedelta(seconds=ttl_seconds)
        self._capacity = capacity
        self._rows: OrderedDict[
            str,
            FinalDecisionReviewAuthenticatedOwnerInstallationEvidenceV1,
        ] = OrderedDict()
        self._lock = RLock()

    @property
    def ttl_seconds(self) -> int:
        return int(self._ttl.total_seconds())

    @property
    def capacity(self) -> int:
        return self._capacity

    def _prune(self, checked_at: datetime) -> None:
        expired = [
            invocation_id
            for invocation_id, row in self._rows.items()
            if row.expires_at <= checked_at
        ]
        for invocation_id in expired:
            self._rows.pop(invocation_id, None)

    def publish(
        self,
        *,
        context: FinalDecisionReviewApprovedServerContextV1,
        status: FinalDecisionReviewAuthenticatedOwnerInstallationStatus,
        snapshot_selected: bool,
        installation_called: bool,
        acquisition_status: FinalDecisionReviewApprovedOwnerAcquisitionStatus | None,
        primary_blocker: str | None,
        handler_error_code: FinalDecisionReviewHandlerErrorCode | None,
        handler_http_status: FinalDecisionReviewHandlerHttpStatus | None,
        observed_at: datetime | None = None,
    ) -> FinalDecisionReviewAuthenticatedOwnerInstallationEvidenceV1:
        if not isinstance(context, FinalDecisionReviewApprovedServerContextV1):
            raise FinalDecisionReviewAuthenticatedOwnerInstallationError(
                "FINAL_DECISION_REVIEW_AUTHENTICATED_OWNER_CONTEXT_INVALID"
            )
        now = _aware_utc(observed_at or context.generated_at)
        with self._lock:
            self._prune(now)
            if context.invocation_id in self._rows:
                raise FinalDecisionReviewAuthenticatedOwnerInstallationError(
                    "FINAL_DECISION_REVIEW_AUTHENTICATED_OWNER_EVIDENCE_DUPLICATE"
                )
            evicted = False
            projected_count = len(self._rows) + 1
            if projected_count > self._capacity:
                self._rows.popitem(last=False)
                evicted = True
            row = FinalDecisionReviewAuthenticatedOwnerInstallationEvidenceV1(
                invocation_id=context.invocation_id,
                scenario_id=context.scenario_id,
                correlation_id=context.correlation_id,
                operation=context.operation,
                observed_at=now,
                expires_at=now + self._ttl,
                status=status,
                snapshot_selected=snapshot_selected,
                installation_called=installation_called,
                acquisition_status=acquisition_status,
                primary_blocker=primary_blocker,
                handler_error_code=handler_error_code,
                handler_http_status=handler_http_status,
                active_evidence_count=len(self._rows) + 1,
                evicted=evicted,
            )
            self._rows[context.invocation_id] = row
            return row

    def get(
        self,
        invocation_id: str,
        *,
        checked_at: datetime | None = None,
    ) -> FinalDecisionReviewAuthenticatedOwnerInstallationEvidenceV1 | None:
        now = _aware_utc(checked_at)
        with self._lock:
            self._prune(now)
            row = self._rows.get(invocation_id)
            if row is None:
                return None
            self._rows.move_to_end(invocation_id)
            return row

    def active_evidence_count(self, *, checked_at: datetime | None = None) -> int:
        now = _aware_utc(checked_at)
        with self._lock:
            self._prune(now)
            return len(self._rows)

    def clear(self) -> None:
        with self._lock:
            self._rows.clear()


class FinalDecisionReviewAuthenticatedOwnerInstallationV1:
    """Select one exact snapshot and invoke PR-80 once after auth context capture."""

    def __init__(
        self,
        *,
        snapshot_store: FinalDecisionReviewApprovedOwnerSnapshotStoreV1,
        installation: FinalDecisionReviewApprovedOwnerInstallationV1,
        evidence_store: FinalDecisionReviewAuthenticatedOwnerEvidenceStoreV1,
    ) -> None:
        if not isinstance(
            snapshot_store,
            FinalDecisionReviewApprovedOwnerSnapshotStoreV1,
        ):
            raise FinalDecisionReviewAuthenticatedOwnerInstallationError(
                "FINAL_DECISION_REVIEW_AUTHENTICATED_OWNER_SNAPSHOT_STORE_INVALID"
            )
        if not isinstance(installation, FinalDecisionReviewApprovedOwnerInstallationV1):
            raise FinalDecisionReviewAuthenticatedOwnerInstallationError(
                "FINAL_DECISION_REVIEW_AUTHENTICATED_OWNER_INSTALLATION_INVALID"
            )
        if not isinstance(
            evidence_store,
            FinalDecisionReviewAuthenticatedOwnerEvidenceStoreV1,
        ):
            raise FinalDecisionReviewAuthenticatedOwnerInstallationError(
                "FINAL_DECISION_REVIEW_AUTHENTICATED_OWNER_EVIDENCE_STORE_INVALID"
            )
        self._snapshot_store = snapshot_store
        self._installation = installation
        self._evidence_store = evidence_store

    @property
    def snapshot_store(self) -> FinalDecisionReviewApprovedOwnerSnapshotStoreV1:
        return self._snapshot_store

    @property
    def installation(self) -> FinalDecisionReviewApprovedOwnerInstallationV1:
        return self._installation

    @property
    def evidence_store(self) -> FinalDecisionReviewAuthenticatedOwnerEvidenceStoreV1:
        return self._evidence_store

    def __call__(
        self,
        context: FinalDecisionReviewApprovedServerContextV1,
    ) -> FinalDecisionReviewAuthenticatedOwnerInstallationEvidenceV1:
        if not isinstance(context, FinalDecisionReviewApprovedServerContextV1):
            raise FinalDecisionReviewAuthenticatedOwnerInstallationError(
                "FINAL_DECISION_REVIEW_AUTHENTICATED_OWNER_CONTEXT_INVALID"
            )
        try:
            selection = self._snapshot_store.select(
                context,
                checked_at=context.generated_at,
            )
        except Exception:
            return self._evidence_store.publish(
                context=context,
                status=FinalDecisionReviewAuthenticatedOwnerInstallationStatus.FAILED,
                snapshot_selected=False,
                installation_called=False,
                acquisition_status=None,
                primary_blocker=(
                    "FINAL_DECISION_REVIEW_AUTHENTICATED_OWNER_SNAPSHOT_SELECTION_FAILED"
                ),
                handler_error_code=None,
                handler_http_status=None,
            )
        if selection is None:
            return self._evidence_store.publish(
                context=context,
                status=(
                    FinalDecisionReviewAuthenticatedOwnerInstallationStatus.UNAVAILABLE
                ),
                snapshot_selected=False,
                installation_called=False,
                acquisition_status=None,
                primary_blocker=(
                    "FINAL_DECISION_REVIEW_AUTHENTICATED_OWNER_SNAPSHOT_UNAVAILABLE"
                ),
                handler_error_code=FinalDecisionReviewHandlerErrorCode.SOURCE_UNAVAILABLE,
                handler_http_status=(
                    FinalDecisionReviewHandlerHttpStatus.SERVICE_UNAVAILABLE
                ),
            )
        try:
            if context.operation is ApprovedCalculatorOperation.PURCHASE_REVIEW:
                if selection.purchase_owners is None:
                    raise FinalDecisionReviewAuthenticatedOwnerInstallationError(
                        "FINAL_DECISION_REVIEW_AUTHENTICATED_OWNER_DIRECTION_MISMATCH"
                    )
                acquisition = self._installation.invoke_purchase(
                    context=context,
                    owners=selection.purchase_owners,
                    installed_at=context.generated_at,
                    completed_at=context.generated_at,
                )
            else:
                if selection.sell_owners is None:
                    raise FinalDecisionReviewAuthenticatedOwnerInstallationError(
                        "FINAL_DECISION_REVIEW_AUTHENTICATED_OWNER_DIRECTION_MISMATCH"
                    )
                acquisition = self._installation.invoke_sell(
                    context=context,
                    owners=selection.sell_owners,
                    installed_at=context.generated_at,
                    completed_at=context.generated_at,
                )
        except Exception:
            return self._evidence_store.publish(
                context=context,
                status=FinalDecisionReviewAuthenticatedOwnerInstallationStatus.FAILED,
                snapshot_selected=True,
                installation_called=True,
                acquisition_status=None,
                primary_blocker=(
                    "FINAL_DECISION_REVIEW_AUTHENTICATED_OWNER_INSTALLATION_FAILED"
                ),
                handler_error_code=FinalDecisionReviewHandlerErrorCode.SOURCE_UNAVAILABLE,
                handler_http_status=(
                    FinalDecisionReviewHandlerHttpStatus.SERVICE_UNAVAILABLE
                ),
            )
        acquired = (
            acquisition.status
            is FinalDecisionReviewApprovedOwnerAcquisitionStatus.ACQUIRED
        )
        return self._evidence_store.publish(
            context=context,
            status=(
                FinalDecisionReviewAuthenticatedOwnerInstallationStatus.ACQUIRED
                if acquired
                else FinalDecisionReviewAuthenticatedOwnerInstallationStatus.UNAVAILABLE
            ),
            snapshot_selected=True,
            installation_called=True,
            acquisition_status=acquisition.status,
            primary_blocker=acquisition.primary_blocker,
            handler_error_code=acquisition.handler_error_code,
            handler_http_status=acquisition.handler_http_status,
        )


class FinalDecisionReviewAuthenticatedOwnerContextStoreV1(
    FinalDecisionReviewApprovedRouteContextStoreV1
):
    """PR-81 context store with one safe PR-83 post-capture lifecycle."""

    def __init__(
        self,
        *,
        lifecycle: FinalDecisionReviewAuthenticatedOwnerInstallationV1,
        ttl_seconds: int = 300,
        capacity: int = 64,
    ) -> None:
        if not isinstance(
            lifecycle,
            FinalDecisionReviewAuthenticatedOwnerInstallationV1,
        ):
            raise FinalDecisionReviewAuthenticatedOwnerInstallationError(
                "FINAL_DECISION_REVIEW_AUTHENTICATED_OWNER_LIFECYCLE_INVALID"
            )
        super().__init__(ttl_seconds=ttl_seconds, capacity=capacity)
        self._lifecycle = lifecycle

    @property
    def lifecycle(self) -> FinalDecisionReviewAuthenticatedOwnerInstallationV1:
        return self._lifecycle

    def capture(
        self,
        context: FinalDecisionReviewApprovedServerContextV1,
        *,
        captured_at: datetime | None = None,
    ) -> FinalDecisionReviewApprovedRouteContextCaptureV1:
        result = super().capture(context, captured_at=captured_at)
        self._lifecycle(context)
        return result
