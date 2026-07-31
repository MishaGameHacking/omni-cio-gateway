from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import ceil
from threading import RLock

from omni_cio.contracts.v1.acra_alerting import (
    AcraRatingActionsAlertDisposition,
    AcraRatingActionsAlertEvaluationV1,
    AcraRatingActionsAlertKind,
    AcraRatingActionsAlertPolicyV1,
)
from omni_cio.contracts.v1.observability import (
    ExternalCallStatus,
    FreshnessTelemetry,
    ObservabilityEventV1,
    ObservabilityOutcome,
    ObservabilitySeverity,
)

_SOURCE_EVENT_NAME = "market.acra_rating_actions.source"
_CACHE_EVENT_NAME = "market.acra_rating_actions.cache"
_SOURCE_COMPONENT = "market.acra_rating_actions_source"
_CACHE_COMPONENT = "market.acra_rating_actions_cache"
_PROVIDER = "ACRA"
_OPERATION = "press_releases.issuer_rating_actions"
_FIXED_METRICS = {"acra.fixed_official_source": 1, "acra.issuer_scope_only": 1}
_SOURCE_METRICS = frozenset({"acra.record_count", "acra.source_available", *_FIXED_METRICS})
_CACHE_METRICS = frozenset({
    "acra.record_count",
    "acra.cache_hit",
    "acra.refresh_attempted",
    "acra.refresh_succeeded",
    "acra.stale_available",
    "acra.stale_exposed",
    "acra.display_allowed",
    *_FIXED_METRICS,
})
_SOURCE_KIND = AcraRatingActionsAlertKind.SOURCE_UNAVAILABLE
_CACHE_KINDS = (
    AcraRatingActionsAlertKind.CACHE_UNAVAILABLE,
    AcraRatingActionsAlertKind.STALE_RECORDS_EXPOSED,
    AcraRatingActionsAlertKind.REFRESH_FAILED_USING_FRESH_CACHE,
)
_FIXED_ERROR_CODES = {
    AcraRatingActionsAlertKind.SOURCE_UNAVAILABLE: "ACRA_RATING_ACTIONS_SOURCE_UNAVAILABLE",
    AcraRatingActionsAlertKind.CACHE_UNAVAILABLE: "ACRA_RATING_ACTIONS_CACHE_UNAVAILABLE",
    AcraRatingActionsAlertKind.STALE_RECORDS_EXPOSED: "ACRA_RATING_ACTIONS_STALE_EXPOSED",
    AcraRatingActionsAlertKind.REFRESH_FAILED_USING_FRESH_CACHE: "ACRA_RATING_ACTIONS_REFRESH_FAILED",
}
_MAX_CONSECUTIVE = 1_000_000


class AcraRatingActionsAlertPolicyError(ValueError):
    """ACRA operational telemetry cannot be evaluated safely."""


@dataclass
class _AlertState:
    consecutive_occurrences: int
    active: bool
    last_seen_at: datetime
    last_fired_at: datetime | None = None


def _metric_values(event: ObservabilityEventV1) -> dict[str, int]:
    return {metric.name: metric.value for metric in event.metrics}


def _severity(kind: AcraRatingActionsAlertKind) -> ObservabilitySeverity:
    if kind in (
        AcraRatingActionsAlertKind.SOURCE_UNAVAILABLE,
        AcraRatingActionsAlertKind.CACHE_UNAVAILABLE,
    ):
        return ObservabilitySeverity.ERROR
    return ObservabilitySeverity.WARNING


def _validate_common(event: ObservabilityEventV1) -> None:
    call = event.external_call
    if (
        event.account is not None
        or event.request_id is not None
        or event.action_id is not None
        or event.quality is not None
        or event.completeness is not None
        or event.exception_type is not None
        or call is None
        or call.provider != _PROVIDER
        or call.operation != _OPERATION
        or call.retry_count != 0
        or call.rate_limit_remaining is not None
    ):
        raise AcraRatingActionsAlertPolicyError("ACRA_ALERT_EVENT_CONTRACT_INVALID")


def _validate_source(event: ObservabilityEventV1) -> None:
    _validate_common(event)
    values = _metric_values(event)
    call = event.external_call
    assert call is not None
    if (
        event.component != _SOURCE_COMPONENT
        or frozenset(values) != _SOURCE_METRICS
        or any(values.get(name) != value for name, value in _FIXED_METRICS.items())
        or values["acra.source_available"] not in (0, 1)
        or values["acra.record_count"] < 0
    ):
        raise AcraRatingActionsAlertPolicyError("ACRA_ALERT_EVENT_CONTRACT_INVALID")
    available = values["acra.source_available"] == 1
    valid = (
        event.outcome is ObservabilityOutcome.SUCCESS
        and event.severity is ObservabilitySeverity.INFO
        and event.error_code is None
        and call.status is ExternalCallStatus.SUCCESS
        and call.freshness is FreshnessTelemetry.FRESH
        and values["acra.record_count"] > 0
    ) if available else (
        event.outcome is ObservabilityOutcome.FAILURE
        and event.severity is ObservabilitySeverity.ERROR
        and event.error_code is not None
        and call.status is ExternalCallStatus.FAILURE
        and call.freshness is FreshnessTelemetry.UNKNOWN
        and values["acra.record_count"] == 0
    )
    if not valid:
        raise AcraRatingActionsAlertPolicyError("ACRA_ALERT_EVENT_CONTRACT_INVALID")


def _validate_cache(event: ObservabilityEventV1) -> None:
    _validate_common(event)
    values = _metric_values(event)
    call = event.external_call
    assert call is not None
    if (
        event.component != _CACHE_COMPONENT
        or frozenset(values) != _CACHE_METRICS
        or any(values.get(name) != value for name, value in _FIXED_METRICS.items())
        or values["acra.record_count"] < 0
        or any(values[name] not in (0, 1) for name in _CACHE_METRICS if name != "acra.record_count")
        or values["acra.stale_exposed"] > values["acra.stale_available"]
    ):
        raise AcraRatingActionsAlertPolicyError("ACRA_ALERT_EVENT_CONTRACT_INVALID")
    profile = (
        event.outcome,
        event.severity,
        call.status,
        call.freshness,
        values["acra.cache_hit"],
        values["acra.refresh_attempted"],
        values["acra.refresh_succeeded"],
        values["acra.stale_exposed"],
        values["acra.display_allowed"],
        event.error_code is not None,
    )
    allowed = {
        (ObservabilityOutcome.SUCCESS, ObservabilitySeverity.INFO, ExternalCallStatus.NOT_CALLED, FreshnessTelemetry.FRESH, 1, 0, 0, 0, 1, False),
        (ObservabilityOutcome.SUCCESS, ObservabilitySeverity.INFO, ExternalCallStatus.SUCCESS, FreshnessTelemetry.FRESH, 0, 1, 1, 0, 1, False),
        (ObservabilityOutcome.DEGRADED, ObservabilitySeverity.WARNING, ExternalCallStatus.FAILURE, FreshnessTelemetry.FRESH, 1, 1, 0, 0, 1, True),
        (ObservabilityOutcome.DEGRADED, ObservabilitySeverity.WARNING, ExternalCallStatus.FAILURE, FreshnessTelemetry.STALE, 1, 1, 0, 1, 1, True),
        (ObservabilityOutcome.FAILURE, ObservabilitySeverity.ERROR, ExternalCallStatus.FAILURE, FreshnessTelemetry.UNKNOWN, 0, 1, 0, 0, 0, True),
    }
    if profile not in allowed:
        raise AcraRatingActionsAlertPolicyError("ACRA_ALERT_EVENT_CONTRACT_INVALID")


def _validate_known(event: ObservabilityEventV1) -> None:
    if event.event_name == _SOURCE_EVENT_NAME:
        _validate_source(event)
    elif event.event_name == _CACHE_EVENT_NAME:
        _validate_cache(event)


def _signal(event: ObservabilityEventV1) -> AcraRatingActionsAlertKind | None:
    if event.event_name == _SOURCE_EVENT_NAME:
        return _SOURCE_KIND if event.outcome is ObservabilityOutcome.FAILURE else None
    if event.event_name != _CACHE_EVENT_NAME:
        return None
    if event.outcome is ObservabilityOutcome.FAILURE:
        return AcraRatingActionsAlertKind.CACHE_UNAVAILABLE
    call = event.external_call
    if call is None:
        return None
    if call.freshness is FreshnessTelemetry.STALE:
        return AcraRatingActionsAlertKind.STALE_RECORDS_EXPOSED
    if event.outcome is ObservabilityOutcome.DEGRADED and call.status is ExternalCallStatus.FAILURE:
        return AcraRatingActionsAlertKind.REFRESH_FAILED_USING_FRESH_CACHE
    return None


def _domain(event_name: str) -> tuple[AcraRatingActionsAlertKind, ...]:
    if event_name == _SOURCE_EVENT_NAME:
        return (_SOURCE_KIND,)
    if event_name == _CACHE_EVENT_NAME:
        return _CACHE_KINDS
    return ()


class AcraRatingActionsAlertPolicyEvaluatorV1:
    internal_only = True
    global_scope_only = True
    issuer_identity_present = False
    rating_thresholds_present = False
    financial_thresholds_present = False
    external_notifications_enabled = False
    broker_write_called = False
    trading_methods = False

    def __init__(self, policy: AcraRatingActionsAlertPolicyV1 | None = None) -> None:
        self._policy = policy or AcraRatingActionsAlertPolicyV1()
        self._states: OrderedDict[AcraRatingActionsAlertKind, _AlertState] = OrderedDict()
        self._lock = RLock()

    @property
    def policy(self) -> AcraRatingActionsAlertPolicyV1:
        return self._policy

    @property
    def state_count(self) -> int:
        with self._lock:
            return len(self._states)

    def clear(self) -> None:
        with self._lock:
            self._states.clear()

    def evaluate(self, event: ObservabilityEventV1) -> tuple[AcraRatingActionsAlertEvaluationV1, ...]:
        if not isinstance(event, ObservabilityEventV1):
            raise AcraRatingActionsAlertPolicyError("ACRA_ALERT_EVENT_TYPE_INVALID")
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
        expired: list[AcraRatingActionsAlertKind] = []
        for kind, state in self._states.items():
            if at < state.last_seen_at:
                continue
            if state.active and state.last_fired_at is not None and at < state.last_fired_at + timedelta(seconds=self._policy.cooldown_seconds):
                continue
            if (at - state.last_seen_at).total_seconds() > self._policy.state_retention_seconds:
                expired.append(kind)
        for kind in expired:
            del self._states[kind]

    def _recover(self, event: ObservabilityEventV1, at: datetime, domain: tuple[AcraRatingActionsAlertKind, ...], keep: AcraRatingActionsAlertKind | None) -> list[AcraRatingActionsAlertEvaluationV1]:
        results: list[AcraRatingActionsAlertEvaluationV1] = []
        for kind in domain:
            if kind is keep:
                continue
            state = self._states.get(kind)
            if state is None:
                continue
            if at < state.last_seen_at:
                raise AcraRatingActionsAlertPolicyError("ACRA_ALERT_EVENT_OUT_OF_ORDER")
            del self._states[kind]
            if state.active:
                results.append(AcraRatingActionsAlertEvaluationV1(
                    evaluated_at=at,
                    source_event_name=event.event_name,
                    disposition=AcraRatingActionsAlertDisposition.RECOVERED,
                    kind=kind,
                    severity=_severity(kind),
                    consecutive_occurrences=state.consecutive_occurrences,
                    threshold=self._policy.threshold_for(kind),
                ))
        return results

    def _evaluate_signal(self, event: ObservabilityEventV1, at: datetime, kind: AcraRatingActionsAlertKind) -> AcraRatingActionsAlertEvaluationV1:
        state = self._states.get(kind)
        if state is not None and at < state.last_seen_at:
            raise AcraRatingActionsAlertPolicyError("ACRA_ALERT_EVENT_OUT_OF_ORDER")
        if state is None:
            state = _AlertState(0, False, at)
            self._states[kind] = state
        state.consecutive_occurrences = min(state.consecutive_occurrences + 1, _MAX_CONSECUTIVE)
        state.last_seen_at = at
        self._states.move_to_end(kind)
        while len(self._states) > self._policy.capacity:
            self._states.popitem(last=False)
        threshold = self._policy.threshold_for(kind)
        if state.consecutive_occurrences < threshold:
            disposition = AcraRatingActionsAlertDisposition.PENDING
            remaining = 0
        else:
            remaining = self._cooldown_remaining(state, at)
            if remaining:
                disposition = AcraRatingActionsAlertDisposition.SUPPRESSED_COOLDOWN
            else:
                disposition = AcraRatingActionsAlertDisposition.FIRED
                state.active = True
                state.last_fired_at = at
        return AcraRatingActionsAlertEvaluationV1(
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

    def _cooldown_remaining(self, state: _AlertState, at: datetime) -> int:
        if state.last_fired_at is None or self._policy.cooldown_seconds == 0:
            return 0
        elapsed = (at - state.last_fired_at).total_seconds()
        if elapsed < 0:
            raise AcraRatingActionsAlertPolicyError("ACRA_ALERT_EVENT_OUT_OF_ORDER")
        return max(0, ceil(self._policy.cooldown_seconds - elapsed))

    @staticmethod
    def _ignored(event: ObservabilityEventV1, at: datetime) -> AcraRatingActionsAlertEvaluationV1:
        return AcraRatingActionsAlertEvaluationV1(
            evaluated_at=at,
            source_event_name=event.event_name,
            disposition=AcraRatingActionsAlertDisposition.IGNORED,
        )
