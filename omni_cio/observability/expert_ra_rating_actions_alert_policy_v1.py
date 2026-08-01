from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import ceil
import re
from threading import RLock

from omni_cio.contracts.v1.expert_ra_alerting import (
    ExpertRaRatingActionsAlertDisposition,
    ExpertRaRatingActionsAlertEvaluationV1,
    ExpertRaRatingActionsAlertKind,
    ExpertRaRatingActionsAlertPolicyV1,
)
from omni_cio.contracts.v1.observability import (
    CircuitBreakerState,
    ExternalCallStatus,
    FreshnessTelemetry,
    ObservabilityEventV1,
    ObservabilityOutcome,
    ObservabilitySeverity,
)
from omni_cio.contracts.v1.ratings import (
    CreditRatingCacheErrorCode,
    CreditRatingSourceErrorCode,
)


_SOURCE_EVENT_NAME = "market.expert_ra_rating_actions.source"
_CACHE_EVENT_NAME = "market.expert_ra_rating_actions.cache"
_SOURCE_COMPONENT = "market.expert_ra_rating_actions_source"
_CACHE_COMPONENT = "market.expert_ra_rating_actions_cache"
_PROVIDER = "Expert RA"
_OPERATION = "home.rating_actions"
_OPAQUE_CORRELATION_ID = re.compile(r"^corr:[a-p]{32}$")
_SOURCE_ERROR_CODES = frozenset(item.value for item in CreditRatingSourceErrorCode)
_CACHE_ERROR_CODES = frozenset(
    item.value for item in CreditRatingCacheErrorCode
) | _SOURCE_ERROR_CODES
_FIXED_METRICS = {
    "expert_ra.fixed_official_source": 1,
    "expert_ra.issuer_scope_only": 1,
    "expert_ra.identity_resolution_required": 1,
    "expert_ra.cross_agency_identity_merged": 0,
}
_SOURCE_METRICS = frozenset(
    {
        "expert_ra.record_count",
        "expert_ra.source_available",
        *_FIXED_METRICS,
    }
)
_CACHE_METRICS = frozenset(
    {
        "expert_ra.record_count",
        "expert_ra.cache_hit",
        "expert_ra.refresh_attempted",
        "expert_ra.refresh_succeeded",
        "expert_ra.stale_available",
        "expert_ra.stale_exposed",
        "expert_ra.display_allowed",
        *_FIXED_METRICS,
    }
)
_SOURCE_KIND = ExpertRaRatingActionsAlertKind.SOURCE_UNAVAILABLE
_CACHE_KINDS = (
    ExpertRaRatingActionsAlertKind.CACHE_UNAVAILABLE,
    ExpertRaRatingActionsAlertKind.STALE_RECORDS_EXPOSED,
    ExpertRaRatingActionsAlertKind.REFRESH_FAILED_USING_FRESH_CACHE,
)
_FIXED_ERROR_CODES = {
    ExpertRaRatingActionsAlertKind.SOURCE_UNAVAILABLE: (
        "EXPERT_RA_RATING_ACTIONS_SOURCE_UNAVAILABLE"
    ),
    ExpertRaRatingActionsAlertKind.CACHE_UNAVAILABLE: (
        "EXPERT_RA_RATING_ACTIONS_CACHE_UNAVAILABLE"
    ),
    ExpertRaRatingActionsAlertKind.STALE_RECORDS_EXPOSED: (
        "EXPERT_RA_RATING_ACTIONS_STALE_EXPOSED"
    ),
    ExpertRaRatingActionsAlertKind.REFRESH_FAILED_USING_FRESH_CACHE: (
        "EXPERT_RA_RATING_ACTIONS_REFRESH_FAILED"
    ),
}
_MAX_CONSECUTIVE = 1_000_000
_MAX_RECORD_COUNT = 30


class ExpertRaRatingActionsAlertPolicyError(ValueError):
    """Expert RA operational telemetry cannot be evaluated safely."""


@dataclass
class _AlertState:
    consecutive_occurrences: int
    active: bool
    last_seen_at: datetime
    last_fired_at: datetime | None = None


def _contract_error() -> ExpertRaRatingActionsAlertPolicyError:
    return ExpertRaRatingActionsAlertPolicyError(
        "EXPERT_RA_RATING_ALERT_EVENT_CONTRACT_INVALID"
    )


def _policy_error() -> ExpertRaRatingActionsAlertPolicyError:
    return ExpertRaRatingActionsAlertPolicyError(
        "EXPERT_RA_RATING_ALERT_POLICY_INVALID"
    )


def _validated_policy(
    policy: ExpertRaRatingActionsAlertPolicyV1,
) -> ExpertRaRatingActionsAlertPolicyV1:
    if not isinstance(policy, ExpertRaRatingActionsAlertPolicyV1):
        raise ExpertRaRatingActionsAlertPolicyError(
            "EXPERT_RA_RATING_ALERT_POLICY_TYPE_INVALID"
        )
    try:
        validated = ExpertRaRatingActionsAlertPolicyV1.model_validate(
            policy.model_dump(mode="python", warnings="error")
        )
    except Exception:
        raise _policy_error() from None
    if validated != policy:
        raise _policy_error()
    return validated


def _event_contract_revalidates(event: ObservabilityEventV1) -> bool:
    try:
        validated = ObservabilityEventV1.model_validate(
            event.model_dump(mode="python", warnings="error")
        )
    except Exception:
        return False
    return validated == event


def _metric_values(event: ObservabilityEventV1) -> dict[str, int]:
    values = {metric.name: metric.value for metric in event.metrics}
    if len(values) != len(event.metrics):
        raise _contract_error()
    return values


def _severity(
    kind: ExpertRaRatingActionsAlertKind,
) -> ObservabilitySeverity:
    if kind in (
        ExpertRaRatingActionsAlertKind.SOURCE_UNAVAILABLE,
        ExpertRaRatingActionsAlertKind.CACHE_UNAVAILABLE,
    ):
        return ObservabilitySeverity.ERROR
    return ObservabilitySeverity.WARNING


def _validate_common(event: ObservabilityEventV1) -> None:
    call = event.external_call
    if (
        not _event_contract_revalidates(event)
        or _OPAQUE_CORRELATION_ID.fullmatch(event.correlation_id) is None
        or event.account is not None
        or event.request_id is not None
        or event.action_id is not None
        or event.quality is not None
        or event.completeness is not None
        or event.exception_type is not None
        or event.contains_sensitive_payload is not False
        or event.trading_methods is not False
        or call is None
        or call.provider != _PROVIDER
        or call.operation != _OPERATION
        or call.retry_count != 0
        or call.rate_limit_remaining is not None
        or call.circuit_breaker_state
        is not CircuitBreakerState.NOT_APPLICABLE
    ):
        raise _contract_error()
    if call.status is ExternalCallStatus.NOT_CALLED:
        if call.latency_ms is not None:
            raise _contract_error()
    elif call.latency_ms != event.duration_ms:
        raise _contract_error()


def _validate_source(event: ObservabilityEventV1) -> None:
    _validate_common(event)
    values = _metric_values(event)
    call = event.external_call
    assert call is not None
    record_count = values.get("expert_ra.record_count", -1)
    if (
        event.event_name != _SOURCE_EVENT_NAME
        or event.component != _SOURCE_COMPONENT
        or frozenset(values) != _SOURCE_METRICS
        or any(
            values.get(name) != value
            for name, value in _FIXED_METRICS.items()
        )
        or values["expert_ra.source_available"] not in (0, 1)
        or not 0 <= record_count <= _MAX_RECORD_COUNT
    ):
        raise _contract_error()

    available = values["expert_ra.source_available"] == 1
    if available:
        valid = (
            record_count >= 1
            and event.outcome is ObservabilityOutcome.SUCCESS
            and event.severity is ObservabilitySeverity.INFO
            and event.error_code is None
            and call.status is ExternalCallStatus.SUCCESS
            and call.freshness is FreshnessTelemetry.FRESH
        )
    else:
        valid = (
            record_count == 0
            and event.outcome is ObservabilityOutcome.FAILURE
            and event.severity is ObservabilitySeverity.ERROR
            and event.error_code in _SOURCE_ERROR_CODES
            and call.status is ExternalCallStatus.FAILURE
            and call.freshness is FreshnessTelemetry.UNKNOWN
        )
    if not valid:
        raise _contract_error()


def _validate_cache(event: ObservabilityEventV1) -> None:
    _validate_common(event)
    values = _metric_values(event)
    call = event.external_call
    assert call is not None
    record_count = values.get("expert_ra.record_count", -1)
    boolean_names = _CACHE_METRICS - {"expert_ra.record_count"}
    if (
        event.event_name != _CACHE_EVENT_NAME
        or event.component != _CACHE_COMPONENT
        or frozenset(values) != _CACHE_METRICS
        or any(
            values.get(name) != value
            for name, value in _FIXED_METRICS.items()
        )
        or any(values[name] not in (0, 1) for name in boolean_names)
        or not 0 <= record_count <= _MAX_RECORD_COUNT
        or values["expert_ra.stale_exposed"]
        > values["expert_ra.stale_available"]
        or (
            event.error_code is not None
            and event.error_code not in _CACHE_ERROR_CODES
        )
    ):
        raise _contract_error()

    profile = (
        event.outcome,
        event.severity,
        call.status,
        call.freshness,
        values["expert_ra.cache_hit"],
        values["expert_ra.refresh_attempted"],
        values["expert_ra.refresh_succeeded"],
        values["expert_ra.stale_available"],
        values["expert_ra.stale_exposed"],
        values["expert_ra.display_allowed"],
        event.error_code is not None,
        record_count > 0,
    )
    allowed = {
        (
            ObservabilityOutcome.SUCCESS,
            ObservabilitySeverity.INFO,
            ExternalCallStatus.NOT_CALLED,
            FreshnessTelemetry.FRESH,
            1,
            0,
            0,
            0,
            0,
            1,
            False,
            True,
        ),
        (
            ObservabilityOutcome.SUCCESS,
            ObservabilitySeverity.INFO,
            ExternalCallStatus.SUCCESS,
            FreshnessTelemetry.FRESH,
            0,
            1,
            1,
            0,
            0,
            1,
            False,
            True,
        ),
        (
            ObservabilityOutcome.DEGRADED,
            ObservabilitySeverity.WARNING,
            ExternalCallStatus.FAILURE,
            FreshnessTelemetry.FRESH,
            1,
            1,
            0,
            0,
            0,
            1,
            True,
            True,
        ),
        (
            ObservabilityOutcome.DEGRADED,
            ObservabilitySeverity.WARNING,
            ExternalCallStatus.FAILURE,
            FreshnessTelemetry.STALE,
            1,
            1,
            0,
            1,
            1,
            1,
            True,
            True,
        ),
        (
            ObservabilityOutcome.FAILURE,
            ObservabilitySeverity.ERROR,
            ExternalCallStatus.FAILURE,
            FreshnessTelemetry.UNKNOWN,
            0,
            1,
            0,
            0,
            0,
            0,
            True,
            False,
        ),
        (
            ObservabilityOutcome.FAILURE,
            ObservabilitySeverity.ERROR,
            ExternalCallStatus.FAILURE,
            FreshnessTelemetry.UNKNOWN,
            0,
            1,
            0,
            1,
            0,
            0,
            True,
            False,
        ),
    }
    if profile not in allowed:
        raise _contract_error()


def _validate_known(event: ObservabilityEventV1) -> None:
    if event.event_name == _SOURCE_EVENT_NAME:
        _validate_source(event)
    elif event.event_name == _CACHE_EVENT_NAME:
        _validate_cache(event)


def _signal(
    event: ObservabilityEventV1,
) -> ExpertRaRatingActionsAlertKind | None:
    if event.event_name == _SOURCE_EVENT_NAME:
        return (
            _SOURCE_KIND
            if event.outcome is ObservabilityOutcome.FAILURE
            else None
        )
    if event.event_name != _CACHE_EVENT_NAME:
        return None
    if event.outcome is ObservabilityOutcome.FAILURE:
        return ExpertRaRatingActionsAlertKind.CACHE_UNAVAILABLE
    call = event.external_call
    if call is None:
        return None
    if call.freshness is FreshnessTelemetry.STALE:
        return ExpertRaRatingActionsAlertKind.STALE_RECORDS_EXPOSED
    if (
        event.outcome is ObservabilityOutcome.DEGRADED
        and call.status is ExternalCallStatus.FAILURE
        and call.freshness is FreshnessTelemetry.FRESH
    ):
        return ExpertRaRatingActionsAlertKind.REFRESH_FAILED_USING_FRESH_CACHE
    return None


def _domain(
    event_name: str,
) -> tuple[ExpertRaRatingActionsAlertKind, ...]:
    if event_name == _SOURCE_EVENT_NAME:
        return (_SOURCE_KIND,)
    if event_name == _CACHE_EVENT_NAME:
        return _CACHE_KINDS
    return ()


class ExpertRaRatingActionsAlertPolicyEvaluatorV1:
    """Evaluate global Expert RA feed health without rating thresholds."""

    internal_only = True
    global_scope_only = True
    issuer_identity_present = False
    rating_values_present = False
    action_identity_present = False
    rating_thresholds_present = False
    financial_thresholds_present = False
    external_notifications_enabled = False
    broker_write_called = False
    trading_methods = False

    def __init__(
        self,
        policy: ExpertRaRatingActionsAlertPolicyV1 | None = None,
    ) -> None:
        candidate = (
            ExpertRaRatingActionsAlertPolicyV1()
            if policy is None
            else policy
        )
        self._policy = _validated_policy(candidate)
        self._states: OrderedDict[
            ExpertRaRatingActionsAlertKind,
            _AlertState,
        ] = OrderedDict()
        self._lock = RLock()

    @property
    def policy(self) -> ExpertRaRatingActionsAlertPolicyV1:
        return self._policy

    @property
    def state_count(self) -> int:
        with self._lock:
            return len(self._states)

    def clear(self) -> None:
        with self._lock:
            self._states.clear()

    def evaluate(
        self,
        event: ObservabilityEventV1,
    ) -> tuple[ExpertRaRatingActionsAlertEvaluationV1, ...]:
        if not isinstance(event, ObservabilityEventV1):
            raise ExpertRaRatingActionsAlertPolicyError(
                "EXPERT_RA_RATING_ALERT_EVENT_TYPE_INVALID"
            )
        if not _event_contract_revalidates(event):
            raise _contract_error()
        _validate_known(event)
        at = event.occurred_at.astimezone(timezone.utc)
        with self._lock:
            self._prune(at)
            signal = _signal(event)
            domain = _domain(event.event_name)
            if not domain:
                return (self._ignored(event, at),)
            results = self._recover(event, at, domain, signal)
            if signal is None:
                return tuple(results) if results else (self._ignored(event, at),)
            results.append(self._evaluate_signal(event, at, signal))
            return tuple(results)

    def _prune(self, at: datetime) -> None:
        expired: list[ExpertRaRatingActionsAlertKind] = []
        for kind, state in self._states.items():
            if at < state.last_seen_at:
                continue
            if state.active and state.last_fired_at is not None:
                cooldown_end = state.last_fired_at + timedelta(
                    seconds=self._policy.cooldown_seconds
                )
                if at < cooldown_end:
                    continue
            if (
                at - state.last_seen_at
            ).total_seconds() > self._policy.state_retention_seconds:
                expired.append(kind)
        for kind in expired:
            del self._states[kind]

    def _recover(
        self,
        event: ObservabilityEventV1,
        at: datetime,
        domain: tuple[ExpertRaRatingActionsAlertKind, ...],
        keep: ExpertRaRatingActionsAlertKind | None,
    ) -> list[ExpertRaRatingActionsAlertEvaluationV1]:
        results: list[ExpertRaRatingActionsAlertEvaluationV1] = []
        for kind in domain:
            if kind is keep:
                continue
            state = self._states.get(kind)
            if state is None:
                continue
            if at < state.last_seen_at:
                raise ExpertRaRatingActionsAlertPolicyError(
                    "EXPERT_RA_RATING_ALERT_EVENT_OUT_OF_ORDER"
                )
            del self._states[kind]
            if state.active:
                results.append(
                    ExpertRaRatingActionsAlertEvaluationV1(
                        evaluated_at=at,
                        source_event_name=event.event_name,
                        disposition=(
                            ExpertRaRatingActionsAlertDisposition.RECOVERED
                        ),
                        kind=kind,
                        severity=_severity(kind),
                        consecutive_occurrences=state.consecutive_occurrences,
                        threshold=self._policy.threshold_for(kind),
                    )
                )
        return results

    def _evaluate_signal(
        self,
        event: ObservabilityEventV1,
        at: datetime,
        kind: ExpertRaRatingActionsAlertKind,
    ) -> ExpertRaRatingActionsAlertEvaluationV1:
        state = self._states.get(kind)
        if state is not None and at < state.last_seen_at:
            raise ExpertRaRatingActionsAlertPolicyError(
                "EXPERT_RA_RATING_ALERT_EVENT_OUT_OF_ORDER"
            )
        if state is None:
            state = _AlertState(0, False, at)
            self._states[kind] = state
        state.consecutive_occurrences = min(
            state.consecutive_occurrences + 1,
            _MAX_CONSECUTIVE,
        )
        state.last_seen_at = at
        self._states.move_to_end(kind)
        while len(self._states) > self._policy.capacity:
            self._states.popitem(last=False)

        threshold = self._policy.threshold_for(kind)
        if state.consecutive_occurrences < threshold:
            disposition = ExpertRaRatingActionsAlertDisposition.PENDING
            remaining = 0
        else:
            remaining = self._cooldown_remaining(state, at)
            if remaining:
                disposition = (
                    ExpertRaRatingActionsAlertDisposition.SUPPRESSED_COOLDOWN
                )
            else:
                disposition = ExpertRaRatingActionsAlertDisposition.FIRED
                state.active = True
                state.last_fired_at = at
        return ExpertRaRatingActionsAlertEvaluationV1(
            evaluated_at=at,
            source_event_name=event.event_name,
            disposition=disposition,
            kind=kind,
            severity=_severity(kind),
            consecutive_occurrences=state.consecutive_occurrences,
            threshold=threshold,
            cooldown_remaining_seconds=remaining,
            error_code=event.error_code or _FIXED_ERROR_CODES[kind],
        )

    def _cooldown_remaining(
        self,
        state: _AlertState,
        at: datetime,
    ) -> int:
        if state.last_fired_at is None or self._policy.cooldown_seconds == 0:
            return 0
        elapsed = (at - state.last_fired_at).total_seconds()
        if elapsed < 0:
            raise ExpertRaRatingActionsAlertPolicyError(
                "EXPERT_RA_RATING_ALERT_EVENT_OUT_OF_ORDER"
            )
        return max(0, ceil(self._policy.cooldown_seconds - elapsed))

    @staticmethod
    def _ignored(
        event: ObservabilityEventV1,
        at: datetime,
    ) -> ExpertRaRatingActionsAlertEvaluationV1:
        return ExpertRaRatingActionsAlertEvaluationV1(
            evaluated_at=at,
            source_event_name=event.event_name,
            disposition=ExpertRaRatingActionsAlertDisposition.IGNORED,
        )
