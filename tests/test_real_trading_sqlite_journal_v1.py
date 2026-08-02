from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import sqlite3
from threading import Barrier, Thread

import pytest

from omni_cio.real_trading.journal_v1 import JournalDailyCapExceeded
from omni_cio.real_trading.models_v1 import RealTradeProposalV1
from omni_cio.real_trading.sqlite_journal_v1 import (
    JournalIntegrityError,
    JournalStorageError,
    SQLiteRealExecutionJournalV1,
)


BASE_TIME = datetime(2026, 8, 3, 7, 0, tzinfo=timezone.utc)


def proposal(proposal_id: str, order_id: str, *, total: str = "1000") -> RealTradeProposalV1:
    return RealTradeProposalV1(
        proposal_id=proposal_id,
        order_id=order_id,
        account_id="account-1234",
        instrument_uid="instrument-uid",
        ticker="SBER",
        isin="RU0009029540",
        direction="BUY",
        quantity_lots=1,
        limit_price=Decimal("270"),
        rationale="durable journal acceptance",
        preview_total_rub=Decimal(total),
        preview_commission_rub=Decimal("1"),
        available_lots=10,
        market_retrieved_at=BASE_TIME - timedelta(seconds=1),
        created_at=BASE_TIME,
        expires_at=BASE_TIME + timedelta(seconds=120),
        confirmation_code="TESTCODE01",
    )


def journal(path: Path) -> SQLiteRealExecutionJournalV1:
    return SQLiteRealExecutionJournalV1(path, gateway_secret="unit-test-gateway-key")


def test_sqlite_journal_is_durable_and_survives_restart(tmp_path: Path) -> None:
    path = tmp_path / "real-trading.sqlite3"
    first = journal(path)
    item = proposal(
        "11111111-1111-4111-8111-111111111111",
        "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    )
    first.put(item)
    first.reserve_submission(
        item.proposal_id,
        submitted_at=BASE_TIME + timedelta(seconds=10),
        max_daily_rub=Decimal("5000"),
    )
    first.transition(
        item.proposal_id,
        allowed_from=frozenset({"submitting"}),
        state="unknown",
        failure_code="REAL_TRADING_TRANSPORT_AMBIGUOUS",
        failure_message="TimeoutException",
    )

    second = journal(path)
    recovered = second.get(item.proposal_id)

    assert second.durable is True
    assert recovered.state == "unknown"
    assert recovered.order_id == item.order_id
    assert recovered.account_id == item.account_id
    assert recovered.submitted_at == BASE_TIME + timedelta(seconds=10)
    assert second.integrity_check() == 1
    assert (
        second.submitted_notional_for_moscow_date(
            (BASE_TIME + timedelta(seconds=10)).astimezone().date()
        )
        >= Decimal("0")
    )


def test_sqlite_journal_rejects_relative_path(tmp_path: Path) -> None:
    del tmp_path
    with pytest.raises(JournalStorageError):
        SQLiteRealExecutionJournalV1(
            "relative.sqlite3",
            gateway_secret="unit-test-gateway-key",
        )


def test_sqlite_journal_rejects_missing_parent(tmp_path: Path) -> None:
    with pytest.raises(JournalStorageError):
        journal(tmp_path / "missing" / "journal.sqlite3")


def test_sqlite_journal_detects_offline_payload_tamper(tmp_path: Path) -> None:
    path = tmp_path / "real-trading.sqlite3"
    store = journal(path)
    item = proposal(
        "22222222-2222-4222-8222-222222222222",
        "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    )
    store.put(item)

    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE proposals SET payload_json = replace(payload_json, '270', '999') "
            "WHERE proposal_id = ?",
            (item.proposal_id,),
        )
        connection.commit()

    with pytest.raises(JournalIntegrityError):
        store.get(item.proposal_id)


def test_failed_submission_is_not_counted_in_daily_budget(tmp_path: Path) -> None:
    store = journal(tmp_path / "real-trading.sqlite3")
    item = proposal(
        "33333333-3333-4333-8333-333333333333",
        "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    )
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

    day = submitted_at.astimezone(timezone(timedelta(hours=3))).date()
    assert store.submitted_notional_for_moscow_date(day) == Decimal("0")


def test_unknown_submission_remains_counted_in_daily_budget(tmp_path: Path) -> None:
    store = journal(tmp_path / "real-trading.sqlite3")
    item = proposal(
        "44444444-4444-4444-8444-444444444444",
        "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
    )
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
        state="unknown",
    )

    day = submitted_at.astimezone(timezone(timedelta(hours=3))).date()
    assert store.submitted_notional_for_moscow_date(day) == Decimal("1000")


def test_daily_cap_reservation_is_atomic_across_connections(tmp_path: Path) -> None:
    path = tmp_path / "real-trading.sqlite3"
    writer = journal(path)
    first = proposal(
        "55555555-5555-4555-8555-555555555555",
        "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
    )
    second = proposal(
        "66666666-6666-4666-8666-666666666666",
        "ffffffff-ffff-4fff-8fff-ffffffffffff",
    )
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
