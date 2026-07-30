from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from threading import RLock
from typing import TYPE_CHECKING, Protocol
from uuid import uuid4

from omni_cio.contracts.v1.capacity import OrderSide
from omni_cio.contracts.v1.common import AccountReference
from omni_cio.contracts.v1.decision_pro_forma_risk_binding import (
    ProFormaRiskIntentBindingV1,
)
from omni_cio.contracts.v1.final_decision_review_approved_invocation import (
    ApprovedCalculatorOperation,
)

if TYPE_CHECKING:
    from omni_cio.release.final_decision_review_approved_owner_acquisition_v1 import (
        FinalDecisionReviewApprovedServerContextV1,
    )


_SAFE_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{2,127}$")
DEFAULT_APPROVED_ROUTE_CONTEXT_MAX_AGE_SECONDS = 300
DEFAULT_APPROVED_ROUTE_CONTEXT_FUTURE_TOLERANCE_SECONDS = 30


class FinalDecisionReviewAuthenticatedRouteContextError(ValueError):
    """An authenticated route context cannot be derived or retained safely."""


@dataclass(frozen=True, slots=True)
class FinalDecisionReviewApprovedRouteContextSeedV1:
    scenario_id: str
    correlation_id: str
    operation: ApprovedCalculatorOperation
    account: AccountReference
    observed_at: datetime
    internal_only: bool = True
    authenticated: bool = False
    server_derived: bool = True
    credentials_present: bool = False
    full_account_identifier_present: bool = False
    raw_financial_payload_present: bool = False
    broker_write_called: bool = False
    trade_authorized: bool = False
    order_created: bool = False
    trading_methods: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.scenario_id, str) or _SAFE_ID.fullmatch(
            self.scenario_id
        ) is None:
            raise FinalDecisionReviewAuthenticatedRouteContextError(
                "FINAL_DECISION_REVIEW_ROUTE_CONTEXT_SCENARIO_ID_INVALID"
            )
        if not isinstance(self.correlation_id, str) or _SAFE_ID.fullmatch(
            self.correlation_id
        ) is None:
            raise FinalDecisionReviewAuthenticatedRouteContextError(
                "FINAL_DECISION_REVIEW_ROUTE_CONTEXT_CORRELATION_ID_INVALID"
            )
        if not isinstance(self.operation, ApprovedCalculatorOperation):
            raise FinalDecisionReviewAuthenticatedRouteContextError(
                "FINAL_DECISION_REVIEW_ROUTE_CONTEXT_OPERATION_INVALID"
            )
        if not isinstance(self.account, AccountReference):
            raise FinalDecisionReviewAuthenticatedRouteContextError(
                "FINAL_DECISION_REVIEW_ROUTE_CONTEXT_ACCOUNT_INVALID"
            )
        object.__setattr__(self, "observed_at", _aware_utc(self.observed_at))


@dataclass(frozen=True, slots=True)
class FinalDecisionReviewApprovedRouteContextCaptureV1:
    invocation_id: str
    scenario_id: str
    correlation_id: str
    operation: ApprovedCalculatorOperation
    captured_at: datetime
    expires_at: datetime
    active_context_count: int
    evicted: bool
    internal_only: bool = True
    credentials_present: bool = False
    full_account_identifier_present: bool = False
    raw_financial_payload_present: bool = False
    broker_write_called: bool = False
    trade_authorized: bool = False
    order_created: bool = False
    trading_methods: bool = False


class ApprovedRouteContextObserverV1(Protocol):
    def __call__(
        self,
        context: FinalDecisionReviewApprovedServerContextV1,
    ) -> object: ...


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if (
        not isinstance(result, datetime)
        or result.tzinfo is None
        or result.utcoffset() is None
    ):
        raise FinalDecisionReviewAuthenticatedRouteContextError(
            "FINAL_DECISION_REVIEW_ROUTE_CONTEXT_TIMESTAMP_INVALID"
        )
    return result.astimezone(timezone.utc)


def _operation_for_direction(direction: OrderSide) -> ApprovedCalculatorOperation:
    if direction is OrderSide.BUY:
        return ApprovedCalculatorOperation.PURCHASE_REVIEW
    if direction is OrderSide.SELL:
        return ApprovedCalculatorOperation.SELL_REVIEW
    raise FinalDecisionReviewAuthenticatedRouteContextError(
        "FINAL_DECISION_REVIEW_ROUTE_CONTEXT_DIRECTION_INVALID"
    )


def build_final_decision_review_approved_route_context_seed(
    source_binding: ProFormaRiskIntentBindingV1,
    *,
    correlation_id: str,
    observed_at: datetime | None = None,
) -> FinalDecisionReviewApprovedRouteContextSeedV1:
    """Retain only exact safe identity from a trusted publication source."""
    if not isinstance(source_binding, ProFormaRiskIntentBindingV1):
        raise FinalDecisionReviewAuthenticatedRouteContextError(
            "FINAL_DECISION_REVIEW_ROUTE_CONTEXT_BINDING_INVALID"
        )
    scenario = source_binding.scenario
    if (
        scenario.account != source_binding.base_explanation.risk_evaluation.metadata.account
        or scenario.direction is not source_binding.direction
        or scenario.intent_fingerprint != source_binding.intent_fingerprint
    ):
        raise FinalDecisionReviewAuthenticatedRouteContextError(
            "FINAL_DECISION_REVIEW_ROUTE_CONTEXT_BINDING_MISMATCH"
        )
    return FinalDecisionReviewApprovedRouteContextSeedV1(
        scenario_id=scenario.scenario_id,
        correlation_id=correlation_id,
        operation=_operation_for_direction(source_binding.direction),
        account=scenario.account,
        observed_at=_aware_utc(observed_at),
    )


def build_final_decision_review_authenticated_server_context(
    seed: FinalDecisionReviewApprovedRouteContextSeedV1,
    *,
    account: AccountReference,
    direction: OrderSide,
    authentication_confirmed: bool,
    authenticated_at: datetime | None = None,
    invocation_id: str | None = None,
    max_seed_age_seconds: int = DEFAULT_APPROVED_ROUTE_CONTEXT_MAX_AGE_SECONDS,
    future_tolerance_seconds: int = (
        DEFAULT_APPROVED_ROUTE_CONTEXT_FUTURE_TOLERANCE_SECONDS
    ),
) -> FinalDecisionReviewApprovedServerContextV1:
    """Create one approved context only after the existing Bearer gate passed."""
    from omni_cio.release.final_decision_review_approved_owner_acquisition_v1 import (
        FinalDecisionReviewApprovedServerContextV1,
    )

    if not isinstance(seed, FinalDecisionReviewApprovedRouteContextSeedV1):
        raise FinalDecisionReviewAuthenticatedRouteContextError(
            "FINAL_DECISION_REVIEW_ROUTE_CONTEXT_SEED_INVALID"
        )
    if authentication_confirmed is not True:
        raise FinalDecisionReviewAuthenticatedRouteContextError(
            "FINAL_DECISION_REVIEW_ROUTE_CONTEXT_AUTHENTICATION_REQUIRED"
        )
    if not 1 <= max_seed_age_seconds <= 86_400:
        raise FinalDecisionReviewAuthenticatedRouteContextError(
            "FINAL_DECISION_REVIEW_ROUTE_CONTEXT_MAX_AGE_INVALID"
        )
    if not 0 <= future_tolerance_seconds <= 3_600:
        raise FinalDecisionReviewAuthenticatedRouteContextError(
            "FINAL_DECISION_REVIEW_ROUTE_CONTEXT_FUTURE_TOLERANCE_INVALID"
        )
    if not isinstance(account, AccountReference) or account != seed.account:
        raise FinalDecisionReviewAuthenticatedRouteContextError(
            "FINAL_DECISION_REVIEW_ROUTE_CONTEXT_ACCOUNT_MISMATCH"
        )
    if _operation_for_direction(direction) is not seed.operation:
        raise FinalDecisionReviewAuthenticatedRouteContextError(
            "FINAL_DECISION_REVIEW_ROUTE_CONTEXT_OPERATION_MISMATCH"
        )
    now = _aware_utc(authenticated_at)
    age_seconds = (now - seed.observed_at).total_seconds()
    if age_seconds > max_seed_age_seconds:
        raise FinalDecisionReviewAuthenticatedRouteContextError(
            "FINAL_DECISION_REVIEW_ROUTE_CONTEXT_SEED_STALE"
        )
    if age_seconds < -future_tolerance_seconds:
        raise FinalDecisionReviewAuthenticatedRouteContextError(
            "FINAL_DECISION_REVIEW_ROUTE_CONTEXT_SEED_FROM_FUTURE"
        )
    invocation = invocation_id or f"invoke:{uuid4().hex}"
    if not isinstance(invocation, str) or _SAFE_ID.fullmatch(invocation) is None:
        raise FinalDecisionReviewAuthenticatedRouteContextError(
            "FINAL_DECISION_REVIEW_ROUTE_CONTEXT_INVOCATION_ID_INVALID"
        )
    return FinalDecisionReviewApprovedServerContextV1(
        invocation_id=invocation,
        scenario_id=seed.scenario_id,
        correlation_id=seed.correlation_id,
        operation=seed.operation,
        account=seed.account,
        generated_at=now,
    )


class FinalDecisionReviewApprovedRouteContextStoreV1:
    """Bounded process-local evidence that authenticated contexts were produced."""

    def __init__(self, *, ttl_seconds: int = 300, capacity: int = 64) -> None:
        if not 1 <= ttl_seconds <= 3_600:
            raise FinalDecisionReviewAuthenticatedRouteContextError(
                "FINAL_DECISION_REVIEW_ROUTE_CONTEXT_STORE_TTL_INVALID"
            )
        if not 1 <= capacity <= 1_024:
            raise FinalDecisionReviewAuthenticatedRouteContextError(
                "FINAL_DECISION_REVIEW_ROUTE_CONTEXT_STORE_CAPACITY_INVALID"
            )
        self._ttl = timedelta(seconds=ttl_seconds)
        self._capacity = capacity
        self._contexts: OrderedDict[
            str,
            tuple[FinalDecisionReviewApprovedServerContextV1, datetime],
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
            for invocation_id, (_, expires_at) in self._contexts.items()
            if expires_at <= checked_at
        ]
        for invocation_id in expired:
            self._contexts.pop(invocation_id, None)

    def capture(
        self,
        context: FinalDecisionReviewApprovedServerContextV1,
        *,
        captured_at: datetime | None = None,
    ) -> FinalDecisionReviewApprovedRouteContextCaptureV1:
        from omni_cio.release.final_decision_review_approved_owner_acquisition_v1 import (
            FinalDecisionReviewApprovedServerContextV1,
        )

        if not isinstance(context, FinalDecisionReviewApprovedServerContextV1):
            raise FinalDecisionReviewAuthenticatedRouteContextError(
                "FINAL_DECISION_REVIEW_ROUTE_CONTEXT_CAPTURE_TYPE_INVALID"
            )
        now = _aware_utc(captured_at or context.generated_at)
        if now != context.generated_at:
            raise FinalDecisionReviewAuthenticatedRouteContextError(
                "FINAL_DECISION_REVIEW_ROUTE_CONTEXT_CAPTURE_TIME_MISMATCH"
            )
        expires_at = now + self._ttl
        with self._lock:
            self._prune(now)
            if context.invocation_id in self._contexts:
                raise FinalDecisionReviewAuthenticatedRouteContextError(
                    "FINAL_DECISION_REVIEW_ROUTE_CONTEXT_ALREADY_CAPTURED"
                )
            self._contexts[context.invocation_id] = (context, expires_at)
            evicted = False
            while len(self._contexts) > self._capacity:
                self._contexts.popitem(last=False)
                evicted = True
            active = len(self._contexts)
        return FinalDecisionReviewApprovedRouteContextCaptureV1(
            invocation_id=context.invocation_id,
            scenario_id=context.scenario_id,
            correlation_id=context.correlation_id,
            operation=context.operation,
            captured_at=now,
            expires_at=expires_at,
            active_context_count=active,
            evicted=evicted,
        )

    def get(
        self,
        invocation_id: str,
        *,
        checked_at: datetime | None = None,
    ) -> FinalDecisionReviewApprovedServerContextV1 | None:
        now = _aware_utc(checked_at)
        with self._lock:
            self._prune(now)
            item = self._contexts.get(invocation_id)
            if item is None:
                return None
            self._contexts.move_to_end(invocation_id)
            return item[0]

    def active_context_count(self, *, checked_at: datetime | None = None) -> int:
        now = _aware_utc(checked_at)
        with self._lock:
            self._prune(now)
            return len(self._contexts)

    def clear(self) -> None:
        with self._lock:
            self._contexts.clear()
