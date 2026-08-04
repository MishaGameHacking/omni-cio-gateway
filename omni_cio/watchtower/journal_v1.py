from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from omni_cio.contracts.v1.watchtower import WatchtowerStateV1


class WatchtowerJournalError(RuntimeError):
    pass


class WatchtowerJournalConflict(WatchtowerJournalError):
    pass


class WatchtowerJournalV1(Protocol):
    @property
    def durable(self) -> bool: ...

    def get(self, watch_id: str) -> WatchtowerStateV1 | None: ...

    def put(self, state: WatchtowerStateV1) -> WatchtowerStateV1: ...

    def compare_and_swap(
        self,
        watch_id: str,
        *,
        expected_revision: int,
        updated: WatchtowerStateV1,
    ) -> WatchtowerStateV1: ...


@dataclass
class InMemoryWatchtowerJournalV1:
    """Deterministic test journal. Production Watchtower must use durable storage."""

    _states: dict[str, WatchtowerStateV1] = field(default_factory=dict)

    @property
    def durable(self) -> bool:
        return False

    def get(self, watch_id: str) -> WatchtowerStateV1 | None:
        return self._states.get(watch_id)

    def put(self, state: WatchtowerStateV1) -> WatchtowerStateV1:
        if state.watch_id in self._states:
            raise WatchtowerJournalConflict("watchtower state already exists")
        self._states[state.watch_id] = state
        return state

    def compare_and_swap(
        self,
        watch_id: str,
        *,
        expected_revision: int,
        updated: WatchtowerStateV1,
    ) -> WatchtowerStateV1:
        current = self._states.get(watch_id)
        if current is None:
            raise WatchtowerJournalConflict("watchtower state is missing")
        if current.revision != expected_revision:
            raise WatchtowerJournalConflict("watchtower state revision changed")
        if updated.watch_id != watch_id or updated.revision != expected_revision + 1:
            raise WatchtowerJournalConflict("watchtower CAS update is inconsistent")
        self._states[watch_id] = updated
        return updated
