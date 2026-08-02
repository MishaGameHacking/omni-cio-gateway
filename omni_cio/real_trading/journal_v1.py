from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
import hashlib
from threading import RLock
from typing import Any, Protocol, cast
from zoneinfo import ZoneInfo

from .models_v1 import ProposalState, RealTradeProposalV1


MOSCOW = ZoneInfo("Europe/Moscow")


class JournalStateConflict(RuntimeError):
    pass


class JournalDailyCapExceeded(RuntimeError):
    pass


class RealExecutionJournalV1(Protocol):
    """Journal contract required by real-money execution.

    `reserve_submission` is atomic: daily-budget validation and prepared ->
    submitting transition happen together so concurrent confirmations cannot
    both consume the same remaining daily budget.
    """

    durable: bool

    def put(self, proposal: RealTradeProposalV1) -> None: ...

    def get(self, proposal_id: str) -> RealTradeProposalV1: ...

    def transition(
        self,
        proposal_id: str,
        *,
        allowed_from: frozenset[str],
        state: ProposalState,
        **changes: Any,
    ) -> RealTradeProposalV1: ...

    def submitted_notional_for_moscow_date(self, day: date) -> Decimal: ...

    def reserve_submission(
        self,
        proposal_id: str,
        *,
        submitted_at: datetime,
        max_daily_rub: Decimal,
        confirmation_evidence_hash: str | None = None,
    ) -> RealTradeProposalV1: ...


class InMemoryRealExecutionJournalV1:
    """Test-only journal. It must never satisfy production enable checks."""

    durable = False

    def __init__(self) -> None:
        self._lock = RLock()
        self._items: dict[str, RealTradeProposalV1] = {}

    def put(self, proposal: RealTradeProposalV1) -> None:
        with self._lock:
            if proposal.proposal_id in self._items:
                raise RuntimeError("duplicate proposal id")
            self._items[proposal.proposal_id] = proposal

    def get(self, proposal_id: str) -> RealTradeProposalV1:
        with self._lock:
            try:
                return self._items[proposal_id]
            except KeyError as exc:
                raise KeyError("real-trading proposal not found") from exc

    def transition(
        self,
        proposal_id: str,
        *,
        allowed_from: frozenset[str],
        state: ProposalState,
        **changes: Any,
    ) -> RealTradeProposalV1:
        with self._lock:
            current = self.get(proposal_id)
            if current.state not in allowed_from:
                raise JournalStateConflict(f"proposal state conflict: {current.state}")
            updated = replace(current, state=state, **changes)
            self._items[proposal_id] = updated
            return updated

    def submitted_notional_for_moscow_date(self, day: date) -> Decimal:
        with self._lock:
            return self._submitted_notional_for_moscow_date_unlocked(day)

    def reserve_submission(
        self,
        proposal_id: str,
        *,
        submitted_at: datetime,
        max_daily_rub: Decimal,
        confirmation_evidence_hash: str | None = None,
    ) -> RealTradeProposalV1:
        if submitted_at.tzinfo is None:
            raise ValueError("journal timestamps must be timezone-aware")
        with self._lock:
            current = self.get(proposal_id)
            if current.state != "prepared":
                raise JournalStateConflict(f"proposal state conflict: {current.state}")
            day = _moscow_date(submitted_at)
            already = self._submitted_notional_for_moscow_date_unlocked(day)
            if already + current.preview_total_rub > max_daily_rub:
                raise JournalDailyCapExceeded("daily submission cap exceeded")
            evidence = confirmation_evidence_hash or hashlib.sha256(
                (
                    f"{current.proposal_id}\n{current.order_id}\n"
                    f"{current.confirmation_phrase}"
                ).encode("utf-8")
            ).hexdigest()
            updated = replace(
                current,
                state=cast(ProposalState, "submitting"),
                submitted_at=submitted_at,
                confirmation_evidence_hash=evidence,
            )
            self._items[proposal_id] = updated
            return updated

    def _submitted_notional_for_moscow_date_unlocked(self, day: date) -> Decimal:
        total = Decimal("0")
        for proposal in self._items.values():
            submitted_at = proposal.submitted_at
            if submitted_at is None:
                continue
            if proposal.state not in {"submitting", "submitted", "unknown"}:
                continue
            if _moscow_date(submitted_at) == day:
                total += proposal.preview_total_rub
        return total


def _moscow_date(value: datetime) -> date:
    if value.tzinfo is None:
        raise ValueError("journal timestamps must be timezone-aware")
    return value.astimezone(MOSCOW).date()
