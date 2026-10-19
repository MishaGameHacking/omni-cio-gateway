"""Exact-money and real SQLite concurrency regressions; no paid API calls."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal, Inexact, Rounded, ROUND_DOWN, localcontext
from fractions import Fraction
import sqlite3

import pytest

from backend.ai_budget import BudgetDenied, MoneyLedger, micro_rub, token_cost


@pytest.mark.parametrize("value", [
    "0", "0.000001", "0.0000010000000000000000000000000000001",
    "0.100000000000000000000000000000000001", "1234.5",
    "999999.999999000000000000000000000001", "1000000", "1e-80",
])
def test_micro_rub_is_exact_upward_rounding(value):
    exact = Fraction(value) * 1_000_000
    expected = -(-exact.numerator // exact.denominator)
    assert micro_rub(value) == expected


@pytest.mark.parametrize("precision", [2, 6, 28, 60])
def test_conversion_does_not_inherit_callers_precision_or_traps(precision):
    with localcontext() as context:
        context.prec = precision
        context.rounding = ROUND_DOWN
        context.Emax = 2
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        result = micro_rub("1234.500000000000000000000000000001")
        assert result == 1_234_500_001
        assert context.prec == precision
        assert context.rounding == ROUND_DOWN
        assert not any(context.flags.values())


@pytest.mark.parametrize("value", ["NaN", "sNaN", "Infinity", "-0.1", "1000000.0000001", "bad", None])
def test_invalid_amounts_remain_controlled_rejections(value):
    with pytest.raises(BudgetDenied):
        micro_rub(value)


def ledger_for(path):
    def connect():
        return sqlite3.connect(path, timeout=10)
    ledger = MoneyLedger(connect)
    ledger.initialize()
    return ledger, connect


def test_parallel_reservations_cannot_overspend_shared_project_cap(tmp_path):
    ledger, connect = ledger_for(tmp_path / "parallel.sqlite")
    now = 1_792_400_000

    def reserve(index):
        try:
            ledger.reserve(user_id=1 + index % 5, key=f"request-{index}",
                           route=f"route-{index}", model="synthetic/model", ceiling=7,
                           user_cap=60, project_cap=60, at=now)
            return "reserved"
        except BudgetDenied as error:
            return str(error)

    # SQLite connections belong to their own worker threads. No in-memory
    # stand-in for the real BEGIN IMMEDIATE reservation transaction is used.
    with ThreadPoolExecutor(max_workers=8) as workers:
        outcomes = list(workers.map(reserve, range(40)))
    assert outcomes.count("reserved") == 8
    assert outcomes.count("ai_project_budget_exhausted") == 32
    with closing(connect()) as db:
        count, charge = db.execute("SELECT COUNT(*), SUM(charge) FROM ai_money_reservations").fetchone()
    assert (count, charge) == (8, 56)


def test_parallel_duplicate_request_is_reserved_only_once(tmp_path):
    ledger, connect = ledger_for(tmp_path / "duplicates.sqlite")

    def reserve(index):
        try:
            ledger.reserve(user_id=1, key="same-request", route=f"route-{index}",
                           model="synthetic/model", ceiling=7, user_cap=60,
                           project_cap=60, at=1_792_400_000)
            return "reserved"
        except BudgetDenied as error:
            return str(error)

    with ThreadPoolExecutor(max_workers=8) as workers:
        outcomes = list(workers.map(reserve, range(16)))
    assert outcomes.count("reserved") == 1
    assert outcomes.count("ai_budget_duplicate_attempt") == 15
    with closing(connect()) as db:
        assert db.execute("SELECT COUNT(*) FROM ai_money_reservations").fetchone()[0] == 1


@pytest.mark.parametrize("uncertain", [False, True], ids=["reserved", "uncertain"])
def test_unresolved_reservation_still_counts_after_moscow_midnight(tmp_path, uncertain):
    ledger, _ = ledger_for(tmp_path / "midnight.sqlite")
    before = int(datetime(2026, 10, 19, 20, 59, 59, tzinfo=timezone.utc).timestamp())
    ledger.reserve(user_id=1, key="first", route="first-route", model="synthetic/model",
                   ceiling=7, user_cap=10, project_cap=10, at=before)
    if uncertain:
        ledger.uncertain("first")
    summary = ledger.user_summary(1, at=before + 2)
    assert summary["day"] == "2026-10-20"
    assert Decimal(summary["estimated_and_reserved_rub"]) == Decimal("0.000007")
    with pytest.raises(BudgetDenied, match="ai_user_budget_exhausted"):
        ledger.reserve(user_id=1, key="second", route="second-route", model="synthetic/model",
                       ceiling=4, user_cap=10, project_cap=10, at=before + 2)


def test_token_cost_ceil_is_applied_once_to_combined_numerator():
    assert token_cost(1, 1, 1, 1) == 1
    assert token_cost(1_000_001, 1_000_001, 1, 1) == 3
