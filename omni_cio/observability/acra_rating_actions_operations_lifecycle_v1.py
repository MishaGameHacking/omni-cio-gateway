from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from threading import RLock

from omni_cio.contracts.v1.acra_alerting import (
    AcraRatingActionsAlertDisposition,
    AcraRatingActionsAlertEvaluationV1,
    AcraRatingActionsAlertEvidenceV1,
)
from omni_cio.contracts.v1.observability import ObservabilityEventV1
from omni_cio.contracts.v1.ratings import (
    AcraIssuerRatingActionsCacheResultV1,
    AcraIssuerRatingActionsSnapshotV1,
)
from omni_cio.observability.acra_rating_actions_alert_policy_v1 import (
    AcraRatingActionsAlertPolicyEvaluatorV1,
)
from omni_cio.observability.acra_rating_actions_events_v1 import (
    build_acra_rating_actions_cache_event,
    build_acra_rating_actions_source_event,
)
from omni_cio.observability.safe_events_v1 import new_trace_id


DEFAULT_ACRA_OPERATIONS_EVIDENCE_RETENTION_SECONDS = 86_400
DEFAULT_ACRA_OPERATIONS_EVIDENCE_CAPACITY = 64

EventSinkV1 = Callable[[ObservabilityEventV1], None]
EvidenceSinkV1 = Callable[[AcraRatingActionsAlertEvidenceV1], None]


class AcraRatingActionsOperationsLifecycleError(ValueError):
    """The internal ACRA operations lifecycle cannot run safely."""


@dataclass(frozen=True, slots=True)
class AcraRatingActionsOperationsBatchV1:
    event: ObservabilityEventV1
    evaluations: tuple[AcraRatingActionsAlertEvaluationV1, ...]
    evidence: tuple[AcraRatingActionsAlertEvidenceV1, ...]
    sink_failure_count: int


class AcraRatingActionsOperationsLifecycleV1:
    """Build safe events, evaluate global alerts and retain bounded evidence."""

    internal_only = True
    global_scope_only = True
    outbound_notification_transport = False
    contains_sensitive_payload = False
    issuer_identity_present = False
    rating_values_present = False
    financial_values_present = False
    broker_write_called = False
    trading_methods = False

    def __init__(
        self,
        *,
        evaluator: AcraRatingActionsAlertPolicyEvaluatorV1 | None = None,
        event_sink: EventSinkV1 | None = None,
        evidence_sink: EvidenceSinkV1 | None = None,
        retention_seconds: int = DEFAULT_ACRA_OPERATIONS_EVIDENCE_RETENTION_SECONDS,
        capacity: int = DEFAULT_ACRA_OPERATIONS_EVIDENCE_CAPACITY,
    ) -> None:
        selected_evaluator = evaluator or AcraRatingActionsAlertPolicyEvaluatorV1()
        if not isinstance(
            selected_evaluator,
            AcraRatingActionsAlertPolicyEvaluatorV1,
        ):
            raise AcraRatingActionsOperationsLifecycleError(
                "ACRA_OPERATIONS_EVALUATOR_INVALID"
            )
        if event_sink is not None and not callable(event_sink):
            raise AcraRatingActionsOperationsLifecycleError(
                "ACRA_OPERATIONS_EVENT_SINK_INVALID"
            )
        if evidence_sink is not None and not callable(evidence_sink):
            raise AcraRatingActionsOperationsLifecycleError(
                "ACRA_OPERATIONS_EVIDENCE_SINK_INVALID"
            )
        if (
            type(retention_seconds) is not int
            or not 60 <= retention_seconds <= 604_800
        ):
            raise AcraRatingActionsOperationsLifecycleError(
                "ACRA_OPERATIONS_RETENTION_INVALID"
            )
        if type(capacity) is not int or not 1 <= capacity <= 256:
            raise AcraRatingActionsOperationsLifecycleError(
                "ACRA_OPERATIONS_CAPACITY_INVALID"
            )
        self._evaluator = selected_evaluator
        self._event_sink = event_sink
        self._evidence_sink = evidence_sink
        self._retention = timedelta(seconds=retention_seconds)
        self._capacity = capacity
        self._evidence: OrderedDict[
            str,
            AcraRatingActionsAlertEvidenceV1,
        ] = OrderedDict()
        self._lock = RLock()

    @property
    def retention_seconds(self) -> int:
        return int(self._retention.total_seconds())

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def evidence_count(self) -> int:
        with self._lock:
            return len(self._evidence)

    def observe_source(
        self,
        snapshot: AcraIssuerRatingActionsSnapshotV1,
        *,
        duration_ms: Decimal | None = None,
        occurred_at: datetime | None = None,
        correlation_id: str | None = None,
    ) -> AcraRatingActionsOperationsBatchV1:
        event = build_acra_rating_actions_source_event(
            snapshot,
            duration_ms=duration_ms,
            occurred_at=occurred_at or snapshot.retrieved_at,
            correlation_id=correlation_id,
        )
        return self._process(event)

    def observe_cache(
        self,
        result: AcraIssuerRatingActionsCacheResultV1,
        *,
        duration_ms: Decimal | None = None,
        occurred_at: datetime | None = None,
        correlation_id: str | None = None,
    ) -> AcraRatingActionsOperationsBatchV1:
        event = build_acra_rating_actions_cache_event(
            result,
            duration_ms=duration_ms,
            occurred_at=occurred_at or result.checked_at,
            correlation_id=correlation_id,
        )
        return self._process(event)

    def evidence(
        self,
        *,
        checked_at: datetime | None = None,
    ) -> tuple[AcraRatingActionsAlertEvidenceV1, ...]:
        now = self._aware_utc(checked_at)
        with self._lock:
            self._prune(now)
            return tuple(self._evidence.values())

    def clear(self) -> None:
        with self._lock:
            self._evaluator.clear()
            self._evidence.clear()

    def _process(
        self,
        event: ObservabilityEventV1,
    ) -> AcraRatingActionsOperationsBatchV1:
        with self._lock:
            self._prune(event.occurred_at)
            evaluations = self._evaluator.evaluate(event)
            evidence = tuple(
                self._record(event, evaluation)
                for evaluation in evaluations
                if evaluation.disposition
                in (
                    AcraRatingActionsAlertDisposition.FIRED,
                    AcraRatingActionsAlertDisposition.RECOVERED,
                )
            )
            sink_failures = self._emit(event, evidence)
            return AcraRatingActionsOperationsBatchV1(
                event=event,
                evaluations=evaluations,
                evidence=evidence,
                sink_failure_count=sink_failures,
            )

    def _emit(
        self,
        event: ObservabilityEventV1,
        evidence: tuple[AcraRatingActionsAlertEvidenceV1, ...],
    ) -> int:
        sink_failures = 0
        if self._event_sink is not None:
            try:
                self._event_sink(event)
            except Exception:
                sink_failures += 1
        if self._evidence_sink is not None:
            for item in evidence:
                try:
                    self._evidence_sink(item)
                except Exception:
                    sink_failures += 1
        return sink_failures

    def _record(
        self,
        event: ObservabilityEventV1,
        evaluation: AcraRatingActionsAlertEvaluationV1,
    ) -> AcraRatingActionsAlertEvidenceV1:
        if evaluation.kind is None or evaluation.severity is None:
            raise AcraRatingActionsOperationsLifecycleError(
                "ACRA_OPERATIONS_ALERT_IDENTITY_MISSING"
            )
        item = AcraRatingActionsAlertEvidenceV1(
            evidence_id=new_trace_id("acra-alert-evidence"),
            recorded_at=evaluation.evaluated_at,
            correlation_id=event.correlation_id,
            source_event_name=evaluation.source_event_name,
            disposition=evaluation.disposition,
            kind=evaluation.kind,
            severity=evaluation.severity,
            consecutive_occurrences=evaluation.consecutive_occurrences,
            threshold=evaluation.threshold,
            error_code=evaluation.error_code,
        )
        self._evidence[item.evidence_id] = item
        self._evidence.move_to_end(item.evidence_id)
        while len(self._evidence) > self._capacity:
            self._evidence.popitem(last=False)
        return item

    def _prune(self, checked_at: datetime) -> None:
        expired = [
            evidence_id
            for evidence_id, item in self._evidence.items()
            if checked_at >= item.recorded_at
            and checked_at - item.recorded_at > self._retention
        ]
        for evidence_id in expired:
            del self._evidence[evidence_id]

    @staticmethod
    def _aware_utc(value: datetime | None) -> datetime:
        selected = value or datetime.now(timezone.utc)
        if (
            not isinstance(selected, datetime)
            or selected.tzinfo is None
            or selected.utcoffset() is None
        ):
            raise AcraRatingActionsOperationsLifecycleError(
                "ACRA_OPERATIONS_TIMESTAMP_INVALID"
            )
        return selected.astimezone(timezone.utc)
