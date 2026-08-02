from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from threading import Barrier, Thread
from zoneinfo import ZoneInfo

from omni_cio.real_trading.journal_v1 import (
    InMemoryRealExecutionJournalV1,
    JournalDailyCapExceeded,
)
from omni_cio.real_trading.models_v1 import RealTradeProposalV1


BASE_TIME = datetime(2026, 8, 3, 7, 0, tzinfo=timezone.utc)
MOSCOW = ZoneInfo("Europe/Moscow")


def proposal(proposal_id: str, order_id: str) -> RealTradeProposalV1:
    return RealTradeProposalV1(
        proposal_id=proposal_id,
        order_id=order_id,
        account_id="account-1234",
        instrument_uid="instrument",
        ticker="SBER",
        isin="RU0009029540",
        direction="BUY",
        quantity_lots=1,
        limit_price=Decimal("270"),
        rationale="atomic reservation test",
        preview_total_rub=Decimal("1000"),
        preview_commission_rub=Decimal("1"),
        available_lots=10,
        market_retrieved_at=BASE_TIME - timedelta(seconds=1),
        created_at=BASE_TIME,
        expires_at=BASE_TIME + timedelta(seconds=120),
        confirmation_code="TESTCODE",
    )


def test_daily_cap_reservation_is_atomic_under_concurrency() -> None:
    journal = InMemoryRealExecutionJournalV1()
    first = proposal(
        "11111111-1111-4111-8111-111111111111",
        "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    )
    second = proposal(
        "22222222-2222-4222-8222-222222222222",
        "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    )
    journal.put(first)
    journal.put(second)

    barrier = Barrier(2)
    successes: list[str] = []
    failures: list[str] = []

    def reserve(proposal_id: str) -> None:
        barrier.wait()
        try:
            journal.reserve_submission(
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
    day = (BASE_TIME + timedelta(seconds=10)).astimezone(MOSCOW).date()
    assert journal.submitted_notional_for_moscow_date(day) == Decimal("1000")

    states = {journal.get(first.proposal_id).state, journal.get(second.proposal_id).state}
    assert states == {"prepared", "submitting"}
