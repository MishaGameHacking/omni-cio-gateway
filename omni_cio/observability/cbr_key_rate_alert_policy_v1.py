from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from math import ceil
from threading import RLock

from omni_cio.contracts.v1.alerting import (
    CbrKeyRateAlertDisposition,
    CbrKeyRateAlertEvaluationV1,
    CbrKeyRateAlertKind,
    CbrKeyRateAlertPolicyV1,
)
from omni_cio.contracts.v1.observability import (
    ExternalCallStatus,
    FreshnessTelemetry,
    ObservabilityEventV1,
    ObservabilityOutcome,
    ObservabilitySeverity,
)


_SOURCE_EVENT_NAME = "macro.cbr_key_rate.source"
_CACHE_EVENT_NAME = "macro.cbr_key_rate.cache"
_SOURCE_KIND = CbrKeyRateAlertKind.SOURCE_UNAVAILABLE
_CACHE_KINDS = (
    CbrKeyRateAlertKind.CACHE_UNAVAILABLE,
    CbrKeyRateAlertKind.STALE_VALUE_EXPOSED,
    CbrKeyRateAlertKind.REFRESH_FAILED_USING_FRESH_CACHE,
)
_FIXED_ERROR_CODES = {
    CbrKeyRateAlertKind.SOURCE_UNAVAILABLE: "CBR_KEY_RATE_SOURCE_UNAVAILABLE",
    CbrKeyRateAlertKind.CACHE_UNAVAILABLE: "CBR_KEY_RATE_CACHE_UNAVAILABLE",
    CbrKeyRateAlertKind.STALE_VALUE_EXPOSED: "CBR_KEY_RATE_STALE_EXPOSED",
    CbrKeyRateAlertKind.REFRESH_FAILED_USING_FRESH_CACHE: (
        "CBR_KEY_RATE_REFRESH_FAILED"
    ),
}


class CbrKeyRateAlertPolicyError(ValueError):
    """CBR telemetry cannot be evaluated by the bounded alert policy."""


@dataclass
class _AlertState:
    consecutive_occurrences: int
    active: bool
    last_seen_at: datetime
    last_fired_at: datetime | None = None


def _severity_for(kind: CbrKeyRateAlertKind) -> ObservabilitySeverity:
    if kind in (
        CbrKeyRateAlertKind.SOURCE_UNAVAILABLE,
        CbrKeyRateAlertKind.CACHE_UNAVAILABLE,
    ):
        return ObservabilitySeverity.ERROR
    return ObservabilitySeverity.WARNING


def _signal_from_event(event: ObservabilityEventV1) -> CbrKeyRateAlertKind | None:
    if event.event_name == _SOURCE_EVENT_NAME:
        if event.outcome is ObservabilityOutcome.FAILURE:
            return CbrKeyRateAlertKind.SOURCE_UNAVAILABLE
        return None
    if event.event_name != _CACHE_EVENT_NAME:
        return None
    if event.outcome is ObservabilityOutcome.FAILURE:
        return CbrKeyRateAlertKind.CACHE_UNAVAILABLE
    external_call = event.external_call
    if external_call is None:
        return None
    if external_call.freshness is FreshnessTelemetry.STALE:
        return CbrKeyRateAlertKind.STALE_VALUE_EXPOSED
    if (
        event.outcome is ObservabilityOutcome.DEGRADED
        and external_call.status is ExternalCallStatus.FAILURE
        and external_call.freshness is FreshnessTelemetry.FRESH
    ):
        return CbrKeyRateAlertKind.REFRESH_FAILED_USING_FRESH_CACHE
    return None


def _recovery_domain(event_name: str) -> tuple[CbrKeyRateAlertKind, ...]:
    if event_name == _SOURCE_EVENT_NAME:
        return (_SOURCE_KIND,)
    if event_name == _CACHE_EVENT_NAME:
        return _CACHE_KINDS
    return ()


class CbrKeyRateAlertPolicyEvaluatorV1:
    """Evaluate CBR telemetry with thresholds, deduplication and cooldown."""

    def __init__(self, policy: CbrKeyRateAlertPolicyV1 | None = None) -> None:
        self._policy = policy or CbrKeyRateAlertPolicyV1()
        self._states: OrderedDict[CbrKeyRateAlertKind, _AlertState] = OrderedDict()
        self._lock = RLock()

    @property
    def policy(self) -> CbrKeyRateAlertPolicyV1:
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
    ) -> tuple[CbrKeyRateAlertEvaluationV1, ...]:
        if not isinstance(event, ObservabilityEventV1):
            raise CbrKeyRateAlertPolicyError("CBR_ALERT_EVENT_TYPE_INVALID")
        evaluated_at = event.occurred_at.astimezone(timezone.utc)
        with self._lock:
            self._prune(evaluated_at)
            signal = _signal_from_event(event)
            domain = _recovery_domain(event.event_name)
            if not domain:
                return (self._ignored(event, evaluated_at),)
            evaluations = self._recover_siblings(
                event=event,
                evaluated_at=evaluated_at,
                domain=domain,
                keep=signal,
            )
            if signal is None:
                if evaluations:
                    return tuple(evaluations)
                return (self._ignored(event, evaluated_at),)
            evaluations.append(self._evaluate_signal(event, evaluated_at, signal))
            return tuple(evaluations)

    def _prune(self, evaluated_at: datetime) -> None:
        retention = self._policy.state_retention_seconds
        expired = [
            kind
            for kind, state in self._states.items()
            if evaluated_at >= state.last_seen_at
            and (evaluated_at - state.last_seen_at).total_seconds() > retention
        ]
        for kind in expired:
            del self._states[kind]

    def _recover_siblings(
        self,
        *,
        event: ObservabilityEventV1,
        evaluated_at: datetime,
        domain: tuple[CbrKeyRateAlertKind, ...],
        keep: CbrKeyRateAlertKind | None,
    ) -> list[CbrKeyRateAlertEvaluationV1]:
        recovered: list[CbrKeyRateAlertEvaluationV1] = []
        for kind in domain:
            if kind is keep:
                continue
            state = self._states.get(kind)
            if state is None:
                continue
            if evaluated_at < state.last_seen_at:
                raise CbrKeyRateAlertPolicyError("CBR_ALERT_EVENT_OUT_OF_ORDER")
            del self._states[kind]
            if state.active:
                recovered.append(
                    CbrKeyRateAlertEvaluationV1(
                        evaluated_at=evaluated_at,
                        source_event_name=event.event_name,
                        disposition=CbrKeyRateAlertDisposition.RECOVERED,
                        kind=kind,
                        severity=_severity_for(kind),
                        consecutive_occurrences=state.consecutive_occurrences,
                        threshold=self._policy.threshold_for(kind),
                    )
                )
        return recovered

    def _evaluate_signal(
        self,
        event: ObservabilityEventV1,
        evaluated_at: datetime,
        kind: CbrKeyRateAlertKind,
    ) -> CbrKeyRateAlertEvaluationV1:
        state = self._states.get(kind)
        if state is not None and evaluated_at < state.last_seen_at:
            raise CbrKeyRateAlertPolicyError("CBR_ALERT_EVENT_OUT_OF_ORDER")
        if state is None:
            state = _AlertState(
                consecutive_occurrences=0,
                active=False,
                last_seen_at=evaluated_at,
            )
            self._states[kind] = state
        state.consecutive_occurrences += 1
        state.last_seen_at = evaluated_at
        self._states.move_to_end(kind)
        self._enforce_capacity()

        threshold = self._policy.threshold_for(kind)
        if state.consecutive_occurrences < threshold:
            disposition = CbrKeyRateAlertDisposition.PENDING
            cooldown_remaining = 0
        else:
            cooldown_remaining = self._cooldown_remaining(state, evaluated_at)
            if cooldown_remaining > 0:
                disposition = CbrKeyRateAlertDisposition.SUPPRESSED_COOLDOWN
            else:
                disposition = CbrKeyRateAlertDisposition.FIRED
                state.active = True
                state.last_fired_at = evaluated_at

        error_code = event.error_code or _FIXED_ERROR_CODES[kind]
        return CbrKeyRateAlertEvaluationV1(
            evaluated_at=evaluated_at,
            source_event_name=event.event_name,
            disposition=disposition,
            kind=kind,
            severity=_severity_for(kind),
            consecutive_occurrences=state.consecutive_occurrences,
            threshold=threshold,
            cooldown_remaining_seconds=cooldown_remaining,
            error_code=error_code,
        )

    def _cooldown_remaining(self, state: _AlertState, evaluated_at: datetime) -> int:
        if state.last_fired_at is None or self._policy.cooldown_seconds == 0:
            return 0
        elapsed = (evaluated_at - state.last_fired_at).total_seconds()
        if elapsed < 0:
            raise CbrKeyRateAlertPolicyError("CBR_ALERT_EVENT_OUT_OF_ORDER")
        remaining = self._policy.cooldown_seconds - elapsed
        return max(0, ceil(remaining))

    def _enforce_capacity(self) -> None:
        while len(self._states) > self._policy.capacity:
            self._states.popitem(last=False)

    @staticmethod
    def _ignored(
        event: ObservabilityEventV1,
        evaluated_at: datetime,
    ) -> CbrKeyRateAlertEvaluationV1:
        return CbrKeyRateAlertEvaluationV1(
            evaluated_at=evaluated_at,
            source_event_name=event.event_name,
            disposition=CbrKeyRateAlertDisposition.IGNORED,
        )
