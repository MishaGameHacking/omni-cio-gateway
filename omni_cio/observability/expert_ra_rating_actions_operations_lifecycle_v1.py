from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from threading import RLock

from omni_cio.contracts.v1.expert_ra_alerting import (
    ExpertRaRatingActionsAlertDisposition,
    ExpertRaRatingActionsAlertEvaluationV1,
    ExpertRaRatingActionsAlertEvidenceV1,
)
from omni_cio.contracts.v1.observability import ObservabilityEventV1
from omni_cio.contracts.v1.expert_ra_ratings import (
    ExpertRaIssuerRatingActionsCacheResultV1,
    ExpertRaIssuerRatingActionsSnapshotV1,
)
from omni_cio.observability.expert_ra_rating_actions_alert_policy_v1 import (
    ExpertRaRatingActionsAlertPolicyEvaluatorV1,
)
from omni_cio.observability.expert_ra_rating_actions_events_v1 import (
    build_expert_ra_rating_actions_cache_event,
    build_expert_ra_rating_actions_source_event,
)
from omni_cio.observability.safe_events_v1 import new_trace_id


DEFAULT_EXPERT_RA_OPERATIONS_EVIDENCE_RETENTION_SECONDS = 86_400
DEFAULT_EXPERT_RA_OPERATIONS_EVIDENCE_CAPACITY = 64

EventSinkV1 = Callable[[ObservabilityEventV1], None]
EvidenceSinkV1 = Callable[[ExpertRaRatingActionsAlertEvidenceV1], None]


class ExpertRaRatingActionsOperationsLifecycleError(ValueError):
    """The internal EXPERT_RA operations lifecycle cannot run safely."""


@dataclass(frozen=True, slots=True)
class ExpertRaRatingActionsOperationsBatchV1:
    event: ObservabilityEventV1
    evaluations: tuple[ExpertRaRatingActionsAlertEvaluationV1, ...]
    evidence: tuple[ExpertRaRatingActionsAlertEvidenceV1, ...]
    sink_failure_count: int


class ExpertRaRatingActionsOperationsLifecycleV1:
    """Build safe events, evaluate global alerts and retain bounded evidence."""

    internal_only = True
    global_scope_only = True
    outbound_notification_transport = False
    contains_sensitive_payload = False
    issuer_identity_present = False
    rating_values_present = False
    action_identity_present = False
    financial_values_present = False
    rating_thresholds_present = False
    financial_thresholds_present = False
    external_notification_sent = False
    broker_write_called = False
    trading_methods = False

    def __init__(
        self,
        *,
        evaluator: ExpertRaRatingActionsAlertPolicyEvaluatorV1 | None = None,
        event_sink: EventSinkV1 | None = None,
        evidence_sink: EvidenceSinkV1 | None = None,
        retention_seconds: int = DEFAULT_EXPERT_RA_OPERATIONS_EVIDENCE_RETENTION_SECONDS,
        capacity: int = DEFAULT_EXPERT_RA_OPERATIONS_EVIDENCE_CAPACITY,
    ) -> None:
        selected_evaluator = (
            ExpertRaRatingActionsAlertPolicyEvaluatorV1()
            if evaluator is None
            else evaluator
        )
        if type(selected_evaluator) is not ExpertRaRatingActionsAlertPolicyEvaluatorV1:
            raise ExpertRaRatingActionsOperationsLifecycleError(
                "EXPERT_RA_OPERATIONS_EVALUATOR_INVALID"
            )
        if event_sink is not None and not callable(event_sink):
            raise ExpertRaRatingActionsOperationsLifecycleError(
                "EXPERT_RA_OPERATIONS_EVENT_SINK_INVALID"
            )
        if evidence_sink is not None and not callable(evidence_sink):
            raise ExpertRaRatingActionsOperationsLifecycleError(
                "EXPERT_RA_OPERATIONS_EVIDENCE_SINK_INVALID"
            )
        if (
            type(retention_seconds) is not int
            or not 60 <= retention_seconds <= 604_800
        ):
            raise ExpertRaRatingActionsOperationsLifecycleError(
                "EXPERT_RA_OPERATIONS_RETENTION_INVALID"
            )
        if type(capacity) is not int or not 1 <= capacity <= 256:
            raise ExpertRaRatingActionsOperationsLifecycleError(
                "EXPERT_RA_OPERATIONS_CAPACITY_INVALID"
            )
        self._evaluator = selected_evaluator
        self._event_sink = event_sink
        self._evidence_sink = evidence_sink
        self._retention = timedelta(seconds=retention_seconds)
        self._capacity = capacity
        self._evidence: OrderedDict[
            str,
            ExpertRaRatingActionsAlertEvidenceV1,
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
        snapshot: ExpertRaIssuerRatingActionsSnapshotV1,
        *,
        duration_ms: Decimal | None = None,
        occurred_at: datetime | None = None,
        correlation_id: str | None = None,
    ) -> ExpertRaRatingActionsOperationsBatchV1:
        event = build_expert_ra_rating_actions_source_event(
            snapshot,
            duration_ms=duration_ms,
            occurred_at=(snapshot.retrieved_at if occurred_at is None else occurred_at),
            correlation_id=correlation_id,
        )
        return self._process(event)

    def observe_cache(
        self,
        result: ExpertRaIssuerRatingActionsCacheResultV1,
        *,
        duration_ms: Decimal | None = None,
        occurred_at: datetime | None = None,
        correlation_id: str | None = None,
    ) -> ExpertRaRatingActionsOperationsBatchV1:
        event = build_expert_ra_rating_actions_cache_event(
            result,
            duration_ms=duration_ms,
            occurred_at=(result.checked_at if occurred_at is None else occurred_at),
            correlation_id=correlation_id,
        )
        return self._process(event)

    def evidence(
        self,
        *,
        checked_at: datetime | None = None,
    ) -> tuple[ExpertRaRatingActionsAlertEvidenceV1, ...]:
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
    ) -> ExpertRaRatingActionsOperationsBatchV1:
        with self._lock:
            self._prune(event.occurred_at)
            evaluations = self._evaluator.evaluate(event)
            evidence = tuple(
                self._record(event, evaluation)
                for evaluation in evaluations
                if evaluation.disposition
                in (
                    ExpertRaRatingActionsAlertDisposition.FIRED,
                    ExpertRaRatingActionsAlertDisposition.RECOVERED,
                )
            )
            sink_failures = self._emit(event, evidence)
            return ExpertRaRatingActionsOperationsBatchV1(
                event=event,
                evaluations=evaluations,
                evidence=evidence,
                sink_failure_count=sink_failures,
            )

    def _emit(
        self,
        event: ObservabilityEventV1,
        evidence: tuple[ExpertRaRatingActionsAlertEvidenceV1, ...],
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
        evaluation: ExpertRaRatingActionsAlertEvaluationV1,
    ) -> ExpertRaRatingActionsAlertEvidenceV1:
        if not isinstance(
            evaluation,
            ExpertRaRatingActionsAlertEvaluationV1,
        ):
            raise ExpertRaRatingActionsOperationsLifecycleError(
                "EXPERT_RA_OPERATIONS_EVALUATION_TYPE_INVALID"
            )
        try:
            safe_evaluation = ExpertRaRatingActionsAlertEvaluationV1.model_validate(
                evaluation.model_dump(mode="python", warnings="error")
            )
        except Exception:
            raise ExpertRaRatingActionsOperationsLifecycleError(
                "EXPERT_RA_OPERATIONS_EVALUATION_INVALID"
            ) from None
        if safe_evaluation != evaluation:
            raise ExpertRaRatingActionsOperationsLifecycleError(
                "EXPERT_RA_OPERATIONS_EVALUATION_INVALID"
            )
        if safe_evaluation.kind is None or safe_evaluation.severity is None:
            raise ExpertRaRatingActionsOperationsLifecycleError(
                "EXPERT_RA_OPERATIONS_ALERT_IDENTITY_MISSING"
            )
        item = ExpertRaRatingActionsAlertEvidenceV1(
            evidence_id=new_trace_id("expert-ra-alert-evidence"),
            recorded_at=safe_evaluation.evaluated_at,
            correlation_id=event.correlation_id,
            source_event_name=safe_evaluation.source_event_name,
            disposition=safe_evaluation.disposition,
            kind=safe_evaluation.kind,
            severity=safe_evaluation.severity,
            consecutive_occurrences=safe_evaluation.consecutive_occurrences,
            threshold=safe_evaluation.threshold,
            error_code=safe_evaluation.error_code,
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
            raise ExpertRaRatingActionsOperationsLifecycleError(
                "EXPERT_RA_OPERATIONS_TIMESTAMP_INVALID"
            )
        return selected.astimezone(timezone.utc)
