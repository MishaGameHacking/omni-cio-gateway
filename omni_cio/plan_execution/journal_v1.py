from __future__ import annotations

from threading import RLock
from typing import Protocol

from omni_cio.contracts.v1.plan_execution import PlanExecutionSessionV1


class PlanExecutionJournalConflict(RuntimeError):
    pass


class PlanExecutionJournalIntegrityError(RuntimeError):
    pass


class PlanExecutionJournalStorageError(RuntimeError):
    pass


class PlanExecutionJournalV1(Protocol):
    durable: bool

    def put(self, session: PlanExecutionSessionV1) -> PlanExecutionSessionV1: ...

    def get(self, execution_id: str) -> PlanExecutionSessionV1: ...

    def compare_and_swap(
        self,
        execution_id: str,
        *,
        expected_revision: int,
        updated: PlanExecutionSessionV1,
    ) -> PlanExecutionSessionV1: ...

    def integrity_check(self) -> int: ...


class InMemoryPlanExecutionJournalV1:
    durable = False

    def __init__(self) -> None:
        self._lock = RLock()
        self._items: dict[str, PlanExecutionSessionV1] = {}

    def put(self, session: PlanExecutionSessionV1) -> PlanExecutionSessionV1:
        with self._lock:
            current = self._items.get(session.execution_id)
            if current is not None:
                if current == session:
                    return current
                raise PlanExecutionJournalConflict(
                    "execution id already exists with different payload"
                )
            self._items[session.execution_id] = session
            return session

    def get(self, execution_id: str) -> PlanExecutionSessionV1:
        with self._lock:
            try:
                return self._items[execution_id]
            except KeyError as exc:
                raise KeyError("plan execution session not found") from exc

    def compare_and_swap(
        self,
        execution_id: str,
        *,
        expected_revision: int,
        updated: PlanExecutionSessionV1,
    ) -> PlanExecutionSessionV1:
        with self._lock:
            current = self.get(execution_id)
            if current.revision != expected_revision:
                raise PlanExecutionJournalConflict(
                    f"execution revision conflict: {current.revision}"
                )
            if updated.execution_id != execution_id:
                raise PlanExecutionJournalConflict("execution id mutation is forbidden")
            if updated.revision != expected_revision + 1:
                raise PlanExecutionJournalConflict(
                    "execution revision must advance by exactly one"
                )
            self._items[execution_id] = updated
            return updated

    def integrity_check(self) -> int:
        with self._lock:
            for key, session in self._items.items():
                canonical = PlanExecutionSessionV1.model_validate(
                    session.model_dump(mode="python")
                )
                if canonical.execution_id != key:
                    raise PlanExecutionJournalIntegrityError(
                        "in-memory execution journal identity mismatch"
                    )
            return len(self._items)
