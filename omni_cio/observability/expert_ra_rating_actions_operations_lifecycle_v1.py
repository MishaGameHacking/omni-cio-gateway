from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from threading import RLock
from typing import cast

from omni_cio.contracts.v1.expert_ra_alerting import (
    ExpertRaRatingActionsAlertDisposition,
    ExpertRaRatingActionsAlertEvaluationV1,
    ExpertRaRatingActionsAlertEvidenceV1,
    ExpertRaSourceEventName,
)
from omni_cio.contracts.v1.expert_ra_ratings import (
    ExpertRaIssuerRatingActionsCacheResultV1,
    ExpertRaIssuerRatingActionsSnapshotV1,
)
from omni_cio.contracts.v1.observability import ObservabilityEventV1
from omni_cio.contracts.v1.ratings import (
    CreditRatingCacheErrorCode,
    CreditRatingSourceErrorCode,
)
from omni_cio.observability.expert_ra_rating_actions_alert_policy_v1 import (
    ExpertRaRatingActionsAlertPolicyEvaluatorV1,
)
from omni_cio.observability.expert_ra_rating_actions_events_v1 import (
    build_expert_ra_rating_actions_cache_event,
    build_expert_ra_rating_actions_source_event,
)


DEFAULT_EXPERT_RA_OPERATIONS_EVIDENCE_RETENTION_SECONDS = 86_400
DEFAULT_EXPERT_RA_OPERATIONS_EVIDENCE_CAPACITY = 64
_EVIDENCE_ID_PREFIX = "expert-ra-evidence:"
_NIBBLE_ALPHABET = "abcdefghijklmnop"
_TERMINAL_DISPOSITIONS = frozenset(
    {
        ExpertRaRatingActionsAlertDisposition.FIRED,
        ExpertRaRatingActionsAlertDisposition.RECOVERED,
    }
)
_FIXED_ALERT_ERROR_CODES = frozenset(
    {
        "EXPERT_RA_RATING_ACTIONS_SOURCE_UNAVAILABLE",
        "EXPERT_RA_RATING_ACTIONS_CACHE_UNAVAILABLE",
        "EXPERT_RA_RATING_ACTIONS_STALE_EXPOSED",
        "EXPERT_RA_RATING_ACTIONS_REFRESH_FAILED",
    }
)
_ALLOWED_FIRED_ERROR_CODES = (
    frozenset(item.value for item in CreditRatingSourceErrorCode)
    | frozenset(item.value for item in CreditRatingCacheErrorCode)
    | _FIXED_ALERT_ERROR_CODES
)

EvidenceSinkV1 = Callable[[ExpertRaRatingActionsAlertEvidenceV1], None]


class ExpertRaRatingActionsOperationsLifecycleError(ValueError):
    """The internal Expert RA operations lifecycle cannot run safely."""


@dataclass(frozen=True, slots=True)
class ExpertRaRatingActionsOperationsBatchV1:
    source_event_name: str
    evaluations: tuple[ExpertRaRatingActionsAlertEvaluationV1, ...]
    evidence: tuple[ExpertRaRatingActionsAlertEvidenceV1, ...]
    sink_failure_count: int


class ExpertRaRatingActionsOperationsLifecycleV1:
    """Build safe events, evaluate global alerts and retain terminal evidence."""

    internal_only = True
    global_scope_only = True
    deterministic_evidence_ids = True
    event_payload_retained = False
    correlation_id_retained = False
    outbound_notification_transport = False
    contains_sensitive_payload = False
    issuer_identity_present = False
    rating_values_present = False
    action_identity_present = False
    release_identity_present = False
    publication_date_present = False
    financial_values_present = False
    raw_source_payload_present = False
    rating_thresholds_present = False
    financial_thresholds_present = False
    external_notification_sent = False
    broker_write_called = False
    trading_methods = False

    def __init__(
        self,
        *,
        evaluator: ExpertRaRatingActionsAlertPolicyEvaluatorV1 | None = None,
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
        if (
            selected_evaluator.global_scope_only is not True
            or selected_evaluator.issuer_identity_present is not False
            or selected_evaluator.rating_values_present is not False
            or selected_evaluator.action_identity_present is not False
            or selected_evaluator.rating_thresholds_present is not False
            or selected_evaluator.financial_thresholds_present is not False
            or selected_evaluator.external_notifications_enabled is not False
            or selected_evaluator.broker_write_called is not False
            or selected_evaluator.trading_methods is not False
        ):
            raise ExpertRaRatingActionsOperationsLifecycleError(
                "EXPERT_RA_OPERATIONS_EVALUATOR_SAFETY_INVALID"
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
        if not isinstance(snapshot, ExpertRaIssuerRatingActionsSnapshotV1):
            raise ExpertRaRatingActionsOperationsLifecycleError(
                "EXPERT_RA_OPERATIONS_SOURCE_TYPE_INVALID"
            )
        event = build_expert_ra_rating_actions_source_event(
            snapshot,
            duration_ms=duration_ms,
            occurred_at=(
                snapshot.retrieved_at if occurred_at is None else occurred_at
            ),
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
        if not isinstance(result, ExpertRaIssuerRatingActionsCacheResultV1):
            raise ExpertRaRatingActionsOperationsLifecycleError(
                "EXPERT_RA_OPERATIONS_CACHE_TYPE_INVALID"
            )
        event = build_expert_ra_rating_actions_cache_event(
            result,
            duration_ms=duration_ms,
            occurred_at=(
                result.checked_at if occurred_at is None else occurred_at
            ),
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
            evidence_items: list[ExpertRaRatingActionsAlertEvidenceV1] = []
            new_items: list[ExpertRaRatingActionsAlertEvidenceV1] = []
            for evaluation in evaluations:
                if evaluation.disposition not in _TERMINAL_DISPOSITIONS:
                    continue
                item, is_new = self._record(event, evaluation)
                evidence_items.append(item)
                if is_new:
                    new_items.append(item)
            sink_failures = self._emit_evidence(tuple(new_items))
            return ExpertRaRatingActionsOperationsBatchV1(
                source_event_name=event.event_name,
                evaluations=evaluations,
                evidence=tuple(evidence_items),
                sink_failure_count=sink_failures,
            )

    def _emit_evidence(
        self,
        evidence: tuple[ExpertRaRatingActionsAlertEvidenceV1, ...],
    ) -> int:
        if self._evidence_sink is None:
            return 0
        sink_failures = 0
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
    ) -> tuple[ExpertRaRatingActionsAlertEvidenceV1, bool]:
        safe_evaluation = self._validated_terminal_evaluation(event, evaluation)
        kind = safe_evaluation.kind
        severity = safe_evaluation.severity
        if kind is None or severity is None:
            raise ExpertRaRatingActionsOperationsLifecycleError(
                "EXPERT_RA_OPERATIONS_ALERT_IDENTITY_MISSING"
            )
        item = ExpertRaRatingActionsAlertEvidenceV1(
            evidence_id=self._evidence_id(safe_evaluation),
            recorded_at=safe_evaluation.evaluated_at,
            source_event_name=cast(
                ExpertRaSourceEventName,
                safe_evaluation.source_event_name,
            ),
            disposition=safe_evaluation.disposition,
            kind=kind,
            severity=severity,
            consecutive_occurrences=safe_evaluation.consecutive_occurrences,
            threshold=safe_evaluation.threshold,
            error_code=safe_evaluation.error_code,
        )
        existing = self._evidence.get(item.evidence_id)
        if existing is not None:
            if existing != item:
                raise ExpertRaRatingActionsOperationsLifecycleError(
                    "EXPERT_RA_OPERATIONS_EVIDENCE_ID_COLLISION"
                )
            return existing, False
        self._evidence[item.evidence_id] = item
        while len(self._evidence) > self._capacity:
            self._evidence.popitem(last=False)
        return item, True

    @staticmethod
    def _validated_terminal_evaluation(
        event: ObservabilityEventV1,
        evaluation: ExpertRaRatingActionsAlertEvaluationV1,
    ) -> ExpertRaRatingActionsAlertEvaluationV1:
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
        if (
            safe_evaluation.disposition not in _TERMINAL_DISPOSITIONS
            or safe_evaluation.kind is None
            or safe_evaluation.severity is None
            or safe_evaluation.evaluated_at != event.occurred_at
            or safe_evaluation.source_event_name != event.event_name
        ):
            raise ExpertRaRatingActionsOperationsLifecycleError(
                "EXPERT_RA_OPERATIONS_EVALUATION_BINDING_INVALID"
            )
        if (
            safe_evaluation.disposition
            is ExpertRaRatingActionsAlertDisposition.FIRED
            and safe_evaluation.error_code not in _ALLOWED_FIRED_ERROR_CODES
        ):
            raise ExpertRaRatingActionsOperationsLifecycleError(
                "EXPERT_RA_OPERATIONS_EVALUATION_ERROR_CODE_INVALID"
            )
        if (
            safe_evaluation.disposition
            is ExpertRaRatingActionsAlertDisposition.RECOVERED
            and safe_evaluation.error_code is not None
        ):
            raise ExpertRaRatingActionsOperationsLifecycleError(
                "EXPERT_RA_OPERATIONS_RECOVERY_ERROR_CODE_INVALID"
            )
        return safe_evaluation

    @staticmethod
    def _evidence_id(
        evaluation: ExpertRaRatingActionsAlertEvaluationV1,
    ) -> str:
        if evaluation.kind is None or evaluation.severity is None:
            raise ExpertRaRatingActionsOperationsLifecycleError(
                "EXPERT_RA_OPERATIONS_ALERT_IDENTITY_MISSING"
            )
        canonical = "\x1f".join(
            (
                evaluation.evaluated_at.astimezone(timezone.utc).isoformat(
                    timespec="microseconds"
                ),
                evaluation.source_event_name,
                evaluation.scope,
                evaluation.disposition.value,
                evaluation.kind.value,
                evaluation.severity.value,
                str(evaluation.consecutive_occurrences),
                str(evaluation.threshold),
                evaluation.error_code or "",
            )
        ).encode("utf-8")
        digest = sha256(canonical).digest()
        token = "".join(
            _NIBBLE_ALPHABET[byte >> 4]
            + _NIBBLE_ALPHABET[byte & 0x0F]
            for byte in digest
        )
        return _EVIDENCE_ID_PREFIX + token

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
        selected = datetime.now(timezone.utc) if value is None else value
        if (
            not isinstance(selected, datetime)
            or selected.tzinfo is None
            or selected.utcoffset() is None
        ):
            raise ExpertRaRatingActionsOperationsLifecycleError(
                "EXPERT_RA_OPERATIONS_TIMESTAMP_INVALID"
            )
        return selected.astimezone(timezone.utc)
