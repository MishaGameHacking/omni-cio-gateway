from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import ceil
from threading import RLock

from omni_cio.contracts.v1.moex_alerting import (
    MoexQuoteAlertDisposition,
    MoexQuoteAlertEvaluationV1,
    MoexQuoteAlertKind,
    MoexQuoteAlertPolicyV1,
)
from omni_cio.contracts.v1.observability import (
    ExternalCallStatus,
    FreshnessTelemetry,
    ObservabilityEventV1,
    ObservabilityOutcome,
    ObservabilitySeverity,
)


_SOURCE_EVENT_NAME = "market.moex_iss_tqbr_quote.source"
_CACHE_EVENT_NAME = "market.moex_iss_tqbr_quote.cache"
_SOURCE_COMPONENT = "market.moex_iss_tqbr_quote_source"
_CACHE_COMPONENT = "market.moex_iss_tqbr_quote_cache"
_PROVIDER = "Moscow Exchange ISS"
_OPERATION = "TQBR public quote"
_FEED_METRICS = {
    "moex.public_feed": 1,
    "moex.delayed_possible": 1,
    "moex.realtime_guaranteed": 0,
    "moex.informational_only": 1,
}
_SOURCE_METRIC_NAMES = frozenset({"moex.source_available", *_FEED_METRICS})
_CACHE_METRIC_NAMES = frozenset(
    {
        "moex.cache_hit",
        "moex.refresh_attempted",
        "moex.refresh_succeeded",
        "moex.stale_available",
        "moex.stale_exposed",
        "moex.display_allowed",
        *_FEED_METRICS,
    }
)
_SOURCE_KIND = MoexQuoteAlertKind.SOURCE_UNAVAILABLE
_CACHE_KINDS = (
    MoexQuoteAlertKind.CACHE_UNAVAILABLE,
    MoexQuoteAlertKind.STALE_VALUE_EXPOSED,
    MoexQuoteAlertKind.REFRESH_FAILED_USING_FRESH_CACHE,
)
_MAX_CONSECUTIVE_OCCURRENCES = 1_000_000
_FIXED_ERROR_CODES = {
    MoexQuoteAlertKind.SOURCE_UNAVAILABLE: "MOEX_QUOTE_SOURCE_UNAVAILABLE",
    MoexQuoteAlertKind.CACHE_UNAVAILABLE: "MOEX_QUOTE_CACHE_UNAVAILABLE",
    MoexQuoteAlertKind.STALE_VALUE_EXPOSED: "MOEX_QUOTE_STALE_EXPOSED",
    MoexQuoteAlertKind.REFRESH_FAILED_USING_FRESH_CACHE: (
        "MOEX_QUOTE_REFRESH_FAILED"
    ),
}


class MoexQuoteAlertPolicyError(ValueError):
    """MOEX quote telemetry cannot be evaluated safely."""


@dataclass
class _AlertState:
    consecutive_occurrences: int
    active: bool
    last_seen_at: datetime
    last_fired_at: datetime | None = None


def _severity_for(kind: MoexQuoteAlertKind) -> ObservabilitySeverity:
    if kind in (
        MoexQuoteAlertKind.SOURCE_UNAVAILABLE,
        MoexQuoteAlertKind.CACHE_UNAVAILABLE,
    ):
        return ObservabilitySeverity.ERROR
    return ObservabilitySeverity.WARNING


def _metric_values(event: ObservabilityEventV1) -> dict[str, int]:
    return {metric.name: metric.value for metric in event.metrics}


def _validate_common_event(event: ObservabilityEventV1) -> None:
    external_call = event.external_call
    if (
        event.account is not None
        or event.request_id is not None
        or event.action_id is not None
        or event.quality is not None
        or event.completeness is not None
        or event.exception_type is not None
        or external_call is None
        or external_call.provider != _PROVIDER
        or external_call.operation != _OPERATION
        or external_call.retry_count != 0
        or external_call.rate_limit_remaining is not None
    ):
        raise MoexQuoteAlertPolicyError("MOEX_ALERT_EVENT_CONTRACT_INVALID")


def _validate_source_event(event: ObservabilityEventV1) -> None:
    _validate_common_event(event)
    values = _metric_values(event)
    external_call = event.external_call
    assert external_call is not None
    if (
        event.component != _SOURCE_COMPONENT
        or frozenset(values) != _SOURCE_METRIC_NAMES
        or any(values.get(name) != value for name, value in _FEED_METRICS.items())
        or values["moex.source_available"] not in (0, 1)
        or external_call.freshness is not FreshnessTelemetry.UNKNOWN
    ):
        raise MoexQuoteAlertPolicyError("MOEX_ALERT_EVENT_CONTRACT_INVALID")
    available = values["moex.source_available"] == 1
    if available:
        valid = (
            event.outcome is ObservabilityOutcome.SUCCESS
            and event.severity is ObservabilitySeverity.INFO
            and event.error_code is None
            and external_call.status is ExternalCallStatus.SUCCESS
        )
    else:
        valid = (
            event.outcome is ObservabilityOutcome.FAILURE
            and event.severity is ObservabilitySeverity.ERROR
            and event.error_code is not None
            and external_call.status is ExternalCallStatus.FAILURE
        )
    if not valid:
        raise MoexQuoteAlertPolicyError("MOEX_ALERT_EVENT_CONTRACT_INVALID")


def _validate_cache_event(event: ObservabilityEventV1) -> None:
    _validate_common_event(event)
    values = _metric_values(event)
    external_call = event.external_call
    assert external_call is not None
    if (
        event.component != _CACHE_COMPONENT
        or frozenset(values) != _CACHE_METRIC_NAMES
        or any(values.get(name) != value for name, value in _FEED_METRICS.items())
        or any(value not in (0, 1) for value in values.values())
    ):
        raise MoexQuoteAlertPolicyError("MOEX_ALERT_EVENT_CONTRACT_INVALID")

    profile = (
        event.outcome,
        event.severity,
        external_call.status,
        external_call.freshness,
        values["moex.cache_hit"],
        values["moex.refresh_attempted"],
        values["moex.refresh_succeeded"],
        values["moex.stale_exposed"],
        values["moex.display_allowed"],
        event.error_code is not None,
    )
    allowed_profiles = {
        (
            ObservabilityOutcome.SUCCESS,
            ObservabilitySeverity.INFO,
            ExternalCallStatus.NOT_CALLED,
            FreshnessTelemetry.FRESH,
            1,
            0,
            0,
            0,
            1,
            False,
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
            1,
            False,
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
            1,
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
            True,
        ),
    }
    if profile not in allowed_profiles:
        raise MoexQuoteAlertPolicyError("MOEX_ALERT_EVENT_CONTRACT_INVALID")
    if values["moex.stale_exposed"] > values["moex.stale_available"]:
        raise MoexQuoteAlertPolicyError("MOEX_ALERT_EVENT_CONTRACT_INVALID")


def _validate_known_event(event: ObservabilityEventV1) -> None:
    if event.event_name == _SOURCE_EVENT_NAME:
        _validate_source_event(event)
    elif event.event_name == _CACHE_EVENT_NAME:
        _validate_cache_event(event)


def _signal_from_event(event: ObservabilityEventV1) -> MoexQuoteAlertKind | None:
    if event.event_name == _SOURCE_EVENT_NAME:
        if event.outcome is ObservabilityOutcome.FAILURE:
            return MoexQuoteAlertKind.SOURCE_UNAVAILABLE
        return None
    if event.event_name != _CACHE_EVENT_NAME:
        return None
    if event.outcome is ObservabilityOutcome.FAILURE:
        return MoexQuoteAlertKind.CACHE_UNAVAILABLE
    external_call = event.external_call
    if external_call is None:
        return None
    if external_call.freshness is FreshnessTelemetry.STALE:
        return MoexQuoteAlertKind.STALE_VALUE_EXPOSED
    if (
        event.outcome is ObservabilityOutcome.DEGRADED
        and external_call.status is ExternalCallStatus.FAILURE
        and external_call.freshness is FreshnessTelemetry.FRESH
    ):
        return MoexQuoteAlertKind.REFRESH_FAILED_USING_FRESH_CACHE
    return None


def _recovery_domain(event_name: str) -> tuple[MoexQuoteAlertKind, ...]:
    if event_name == _SOURCE_EVENT_NAME:
        return (_SOURCE_KIND,)
    if event_name == _CACHE_EVENT_NAME:
        return _CACHE_KINDS
    return ()


class MoexQuoteAlertPolicyEvaluatorV1:
    """Evaluate global MOEX feed health without financial thresholds."""

    internal_only = True
    global_scope_only = True
    instrument_identity_present = False
    financial_thresholds_present = False
    external_notifications_enabled = False
    broker_write_called = False
    trading_methods = False

    def __init__(self, policy: MoexQuoteAlertPolicyV1 | None = None) -> None:
        self._policy = policy or MoexQuoteAlertPolicyV1()
        self._states: OrderedDict[MoexQuoteAlertKind, _AlertState] = OrderedDict()
        self._lock = RLock()

    @property
    def policy(self) -> MoexQuoteAlertPolicyV1:
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
    ) -> tuple[MoexQuoteAlertEvaluationV1, ...]:
        if not isinstance(event, ObservabilityEventV1):
            raise MoexQuoteAlertPolicyError("MOEX_ALERT_EVENT_TYPE_INVALID")
        _validate_known_event(event)
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
        expired: list[MoexQuoteAlertKind] = []
        for kind, state in self._states.items():
            if evaluated_at < state.last_seen_at:
                continue
            if state.active and state.last_fired_at is not None:
                cooldown_end = state.last_fired_at + timedelta(
                    seconds=self._policy.cooldown_seconds
                )
                if evaluated_at < cooldown_end:
                    continue
            age_seconds = (evaluated_at - state.last_seen_at).total_seconds()
            if age_seconds > self._policy.state_retention_seconds:
                expired.append(kind)
        for kind in expired:
            del self._states[kind]

    def _recover_siblings(
        self,
        *,
        event: ObservabilityEventV1,
        evaluated_at: datetime,
        domain: tuple[MoexQuoteAlertKind, ...],
        keep: MoexQuoteAlertKind | None,
    ) -> list[MoexQuoteAlertEvaluationV1]:
        recovered: list[MoexQuoteAlertEvaluationV1] = []
        for kind in domain:
            if kind is keep:
                continue
            state = self._states.get(kind)
            if state is None:
                continue
            if evaluated_at < state.last_seen_at:
                raise MoexQuoteAlertPolicyError("MOEX_ALERT_EVENT_OUT_OF_ORDER")
            del self._states[kind]
            if state.active:
                recovered.append(
                    MoexQuoteAlertEvaluationV1(
                        evaluated_at=evaluated_at,
                        source_event_name=event.event_name,
                        disposition=MoexQuoteAlertDisposition.RECOVERED,
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
        kind: MoexQuoteAlertKind,
    ) -> MoexQuoteAlertEvaluationV1:
        state = self._states.get(kind)
        if state is not None and evaluated_at < state.last_seen_at:
            raise MoexQuoteAlertPolicyError("MOEX_ALERT_EVENT_OUT_OF_ORDER")
        if state is None:
            state = _AlertState(
                consecutive_occurrences=0,
                active=False,
                last_seen_at=evaluated_at,
            )
            self._states[kind] = state
        state.consecutive_occurrences = min(
            state.consecutive_occurrences + 1,
            _MAX_CONSECUTIVE_OCCURRENCES,
        )
        state.last_seen_at = evaluated_at
        self._states.move_to_end(kind)
        self._enforce_capacity()

        threshold = self._policy.threshold_for(kind)
        if state.consecutive_occurrences < threshold:
            disposition = MoexQuoteAlertDisposition.PENDING
            cooldown_remaining = 0
        else:
            cooldown_remaining = self._cooldown_remaining(state, evaluated_at)
            if cooldown_remaining > 0:
                disposition = MoexQuoteAlertDisposition.SUPPRESSED_COOLDOWN
            else:
                disposition = MoexQuoteAlertDisposition.FIRED
                state.active = True
                state.last_fired_at = evaluated_at

        error_code = event.error_code or _FIXED_ERROR_CODES[kind]
        return MoexQuoteAlertEvaluationV1(
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
            raise MoexQuoteAlertPolicyError("MOEX_ALERT_EVENT_OUT_OF_ORDER")
        remaining = self._policy.cooldown_seconds - elapsed
        return max(0, ceil(remaining))

    def _enforce_capacity(self) -> None:
        while len(self._states) > self._policy.capacity:
            self._states.popitem(last=False)

    @staticmethod
    def _ignored(
        event: ObservabilityEventV1,
        evaluated_at: datetime,
    ) -> MoexQuoteAlertEvaluationV1:
        return MoexQuoteAlertEvaluationV1(
            evaluated_at=evaluated_at,
            source_event_name=event.event_name,
            disposition=MoexQuoteAlertDisposition.IGNORED,
        )
