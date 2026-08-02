from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import sqlite3
from threading import Barrier, Thread
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from omni_cio.real_trading.journal_v1 import JournalDailyCapExceeded
from omni_cio.real_trading.models_v1 import RealTradeProposalV1
from omni_cio.real_trading.sqlite_journal_v1 import (
    JournalIntegrityError,
    JournalStorageError,
    SQLiteRealExecutionJournalV1,
)


BASE_TIME = datetime(2026, 8, 3, 7, 0, tzinfo=timezone.utc)
MOSCOW = ZoneInfo("Europe/Moscow")


def proposal() -> RealTradeProposalV1:
    return RealTradeProposalV1(
        proposal_id=str(uuid4()),
        order_id=str(uuid4()),
        account_id="test-account",
        instrument_uid="test-instrument",
        ticker="SBER",
        isin="TEST-ISIN",
        direction="BUY",
        quantity_lots=1,
        limit_price=Decimal("270"),
        rationale="durable journal acceptance",
        preview_total_rub=Decimal("1000"),
        preview_commission_rub=Decimal("1"),
        available_lots=10,
        market_retrieved_at=BASE_TIME - timedelta(seconds=1),
        created_at=BASE_TIME,
        expires_at=BASE_TIME + timedelta(seconds=120),
        confirmation_code="TESTCODE",
    )


def journal(path: Path) -> SQLiteRealExecutionJournalV1:
    return SQLiteRealExecutionJournalV1(
        path,
        gateway_secret="unit-test-journal-key",  # pragma: allowlist secret
    )


def test_durable_journal_survives_restart_and_unknown_counts(tmp_path: Path) -> None:
    path = tmp_path / "real.sqlite3"
    item = proposal()
    first = journal(path)
    first.put(item)
    submitted_at = BASE_TIME + timedelta(seconds=10)
    first.reserve_submission(
        item.proposal_id,
        submitted_at=submitted_at,
        max_daily_rub=Decimal("5000"),
    )
    first.transition(
        item.proposal_id,
        allowed_from=frozenset({"submitting"}),
        state="unknown",
        failure_code="TRANSPORT_AMBIGUOUS",
    )

    second = journal(path)
    recovered = second.get(item.proposal_id)
    assert second.durable is True
    assert recovered.state == "unknown"
    assert recovered.order_id == item.order_id
    assert recovered.confirmation_evidence_hash is not None
    assert len(recovered.confirmation_evidence_hash) == 64
    assert second.integrity_check() == 1
    assert second.submitted_notional_for_moscow_date(
        submitted_at.astimezone(MOSCOW).date()
    ) == Decimal("1000")


def test_relative_and_missing_parent_paths_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(JournalStorageError):
        SQLiteRealExecutionJournalV1(
            "relative.sqlite3",
            gateway_secret="unit-test-journal-key",  # pragma: allowlist secret
        )
    with pytest.raises(JournalStorageError):
        journal(tmp_path / "missing" / "real.sqlite3")


def test_offline_payload_tamper_fails_integrity(tmp_path: Path) -> None:
    path = tmp_path / "real.sqlite3"
    store = journal(path)
    item = proposal()
    store.put(item)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE proposals SET payload_json=replace(payload_json,'270','999') "
            "WHERE proposal_id=?",
            (item.proposal_id,),
        )
        connection.commit()
    with pytest.raises(JournalIntegrityError):
        store.get(item.proposal_id)


def test_definitive_failure_releases_daily_budget(tmp_path: Path) -> None:
    store = journal(tmp_path / "real.sqlite3")
    item = proposal()
    store.put(item)
    submitted_at = BASE_TIME + timedelta(seconds=10)
    store.reserve_submission(
        item.proposal_id,
        submitted_at=submitted_at,
        max_daily_rub=Decimal("1500"),
    )
    store.transition(
        item.proposal_id,
        allowed_from=frozenset({"submitting"}),
        state="failed",
        failure_code="BROKER_REJECTED",
    )
    assert store.submitted_notional_for_moscow_date(
        submitted_at.astimezone(MOSCOW).date()
    ) == Decimal("0")


def test_daily_reservation_is_atomic_across_connections(tmp_path: Path) -> None:
    path = tmp_path / "real.sqlite3"
    writer = journal(path)
    first = proposal()
    second = proposal()
    writer.put(first)
    writer.put(second)
    barrier = Barrier(2)
    successes: list[str] = []
    failures: list[str] = []

    def reserve(proposal_id: str) -> None:
        local = journal(path)
        barrier.wait()
        try:
            local.reserve_submission(
                proposal_id,
                submitted_at=BASE_TIME + timedelta(seconds=10),
                max_daily_rub=Decimal("1500"),
            )
            successes.append(proposal_id)
        except JournalDailyCapExceeded:
            failures.append(proposal_id)

    threads = [
        Thread(target=reserve, args=(first.proposal_id,)),
        Thread(target=reserve, args=(second.proposal_id,)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(successes) == 1
    assert len(failures) == 1
    states = {writer.get(first.proposal_id).state, writer.get(second.proposal_id).state}
    assert states == {"prepared", "submitting"}
