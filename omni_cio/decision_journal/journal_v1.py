from __future__ import annotations

from threading import RLock
from typing import Protocol

from omni_cio.contracts.v1.decision_journal import (
    DecisionEvaluationRecordV1,
    DecisionJournalRecordV1,
    DecisionOutcomeRecordV1,
)


class DecisionJournalError(RuntimeError):
    pass


class DecisionJournalConflict(DecisionJournalError):
    pass


class DecisionJournalIntegrityError(DecisionJournalError):
    pass


class DecisionJournalStorageError(DecisionJournalError):
    pass


class DecisionJournalV1(Protocol):
    durable: bool

    def put_decision(self, record: DecisionJournalRecordV1) -> DecisionJournalRecordV1: ...

    def get_decision(self, decision_id: str) -> DecisionJournalRecordV1: ...

    def put_outcome(self, record: DecisionOutcomeRecordV1) -> DecisionOutcomeRecordV1: ...

    def get_outcome(self, outcome_id: str) -> DecisionOutcomeRecordV1: ...

    def put_evaluation(
        self,
        record: DecisionEvaluationRecordV1,
    ) -> DecisionEvaluationRecordV1: ...

    def get_evaluation(self, evaluation_id: str) -> DecisionEvaluationRecordV1: ...

    def integrity_check(self) -> tuple[int, int, int]: ...


class InMemoryDecisionJournalV1:
    """Append-only journal used by deterministic WP14 tests and offline replay."""

    durable = False

    def __init__(self) -> None:
        self._decisions: dict[str, DecisionJournalRecordV1] = {}
        self._outcomes: dict[str, DecisionOutcomeRecordV1] = {}
        self._evaluations: dict[str, DecisionEvaluationRecordV1] = {}
        self._lock = RLock()

    @staticmethod
    def _append[T](target: dict[str, T], key: str, record: T) -> T:
        current = target.get(key)
        if current is None:
            target[key] = record
            return record
        if current == record:
            return current
        raise DecisionJournalConflict("append-only journal identity already has different payload")

    def put_decision(self, record: DecisionJournalRecordV1) -> DecisionJournalRecordV1:
        with self._lock:
            return self._append(self._decisions, record.decision_id, record)

    def get_decision(self, decision_id: str) -> DecisionJournalRecordV1:
        with self._lock:
            try:
                return self._decisions[decision_id]
            except KeyError as exc:
                raise KeyError("decision journal record not found") from exc

    def put_outcome(self, record: DecisionOutcomeRecordV1) -> DecisionOutcomeRecordV1:
        with self._lock:
            if record.decision_id not in self._decisions:
                raise DecisionJournalConflict("outcome cannot precede its immutable decision record")
            return self._append(self._outcomes, record.outcome_id, record)

    def get_outcome(self, outcome_id: str) -> DecisionOutcomeRecordV1:
        with self._lock:
            try:
                return self._outcomes[outcome_id]
            except KeyError as exc:
                raise KeyError("decision outcome record not found") from exc

    def put_evaluation(
        self,
        record: DecisionEvaluationRecordV1,
    ) -> DecisionEvaluationRecordV1:
        with self._lock:
            decision = self._decisions.get(record.decision_id)
            if decision is None or decision.record_sha256 != record.decision_record_sha256:
                raise DecisionJournalConflict("evaluation decision binding is unavailable")
            matching_outcome = any(
                row.outcome_sha256 == record.outcome_record_sha256
                and row.decision_id == record.decision_id
                for row in self._outcomes.values()
            )
            if not matching_outcome:
                raise DecisionJournalConflict("evaluation outcome binding is unavailable")
            return self._append(self._evaluations, record.evaluation_id, record)

    def get_evaluation(self, evaluation_id: str) -> DecisionEvaluationRecordV1:
        with self._lock:
            try:
                return self._evaluations[evaluation_id]
            except KeyError as exc:
                raise KeyError("decision evaluation record not found") from exc

    def integrity_check(self) -> tuple[int, int, int]:
        with self._lock:
            for key, row in self._decisions.items():
                if row.decision_id != key:
                    raise DecisionJournalIntegrityError("decision journal identity mismatch")
                DecisionJournalRecordV1.model_validate(row.model_dump(mode="python"))
            for key, row in self._outcomes.items():
                if row.outcome_id != key or row.decision_id not in self._decisions:
                    raise DecisionJournalIntegrityError("outcome journal identity mismatch")
                DecisionOutcomeRecordV1.model_validate(row.model_dump(mode="python"))
            decision_hashes = {
                row.record_sha256: row.decision_id for row in self._decisions.values()
            }
            outcome_hashes = {
                row.outcome_sha256: row.decision_id for row in self._outcomes.values()
            }
            for key, row in self._evaluations.items():
                if row.evaluation_id != key:
                    raise DecisionJournalIntegrityError("evaluation journal identity mismatch")
                if decision_hashes.get(row.decision_record_sha256) != row.decision_id:
                    raise DecisionJournalIntegrityError("evaluation decision hash mismatch")
                if outcome_hashes.get(row.outcome_record_sha256) != row.decision_id:
                    raise DecisionJournalIntegrityError("evaluation outcome hash mismatch")
                DecisionEvaluationRecordV1.model_validate(row.model_dump(mode="python"))
            return (
                len(self._decisions),
                len(self._outcomes),
                len(self._evaluations),
            )
