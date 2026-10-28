"""Cash observation regression contracts on isolated SQLite, no broker calls."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
import sqlite3

import pytest

import backend.app  # Initialize existing app wiring before its adapter modules.
from backend import operations_ledger as ledger
from backend.portfolio_details import normalize_operation
from backend.volume_contract import source

NOW = datetime(2026, 10, 27, 12, tzinfo=timezone.utc)


@pytest.fixture
def db(tmp_path):
    connection = sqlite3.connect(tmp_path / "ledger.sqlite3")
    connection.row_factory = sqlite3.Row
    yield connection
    connection.close()


def operation(identifier="op-1", amount="10", kind="COUPON", account="account-a", *, status="EXECUTED", at=NOW):
    # Exercise the real project's normalized MoneyValue shape, not a guessed
    # amount scalar. Commission is an annotation and must not be added again.
    item = normalize_operation({"id": identifier, "date": (NOW - timedelta(days=1)).isoformat(),
        "type": "OPERATION_TYPE_" + kind, "state": "OPERATION_STATE_" + status,
        "payment": {"units": amount, "nano": 0, "currency": "rub"},
        "commission": {"units": "-1", "nano": 0, "currency": "rub"}, "quantity": "1"})
    ref = source("GetOperationsByCursor", account, at.isoformat())
    return {**item, "account_id": account, "source_ids": [ref["id"]]}, ref


def snapshot(*pairs, at=NOW, complete=True, begin=None, end=None, account_ids=None):
    items = [deepcopy(pair[0]) for pair in pairs]
    refs = {pair[1]["id"]: deepcopy(pair[1]) for pair in pairs}
    accounts = account_ids or sorted({item["account_id"] for item in items}) or ["account-a"]
    return {"snapshot_id": "synthetic-snapshot", "as_of": at.isoformat(),
        "accounts": [{"id": account} for account in accounts], "sources": list(refs.values()),
        "operations": {"items": items, "complete": complete,
            "start": (begin or at - timedelta(days=60)).isoformat(), "end": (end or at).isoformat()}}


def save(db, value, *, user=1, broker="connection-a", at=NOW):
    with db:
        db.execute("BEGIN IMMEDIATE")
        return ledger.record_snapshot_in(db, user_id=user, broker_key=broker, snapshot=value, at=at)


def movements(receipt):
    return {(row["currency"], row["category"]): Decimal(row["amount"]) for row in receipt["cash_movements"]}


def test_real_normalized_shape_separates_income_principal_and_fee_annotations(db):
    value = snapshot(operation("coupon", "10"), operation("dividend", "20", "DIVIDEND"),
        operation("redemption", "100", "BOND_REPAYMENT_FULL"), operation("deposit", "200", "INPUT"),
        operation("fee", "-1", "BROKER_FEE"), operation("tax", "-2", "TAX"), operation("purchase", "-50", "BUY"))
    receipt = save(db, value)
    assert receipt["state"] == "observed"
    assert movements(receipt) == {("RUB", "coupon_income"): 10, ("RUB", "dividend_income"): 20,
        ("RUB", "principal_repayment"): 100, ("RUB", "external_deposit"): 200,
        ("RUB", "fee_cash"): -1, ("RUB", "observed_tax_cash"): -2, ("RUB", "trade_cash"): -50}
    assert receipt["commission_annotations_added"] is receipt["principal_repayments_are_income"] is False
    assert receipt["performance_calculated"] is receipt["tax_liability_estimated"] is False


def test_replaying_same_operation_and_duplicate_rows_is_idempotent(db):
    pair = operation()
    value = snapshot(pair, pair)
    first = save(db, value)
    second = save(db, value, at=NOW + timedelta(minutes=1))
    assert movements(first) == movements(second) == {("RUB", "coupon_income"): 10}
    assert db.execute("SELECT COUNT(*) FROM broker_operation_history_v1").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM broker_operation_current_v1").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM broker_operation_windows_v1").fetchone()[0] == 1


def test_pending_becomes_executed_and_late_pending_cannot_overwrite_it(db):
    pending = snapshot(operation(status="PROGRESS"))
    first = save(db, pending)
    assert first["cash_movements"] == [] and first["operation_counts"]["pending"] == 1
    later = NOW + timedelta(minutes=1)
    executed = snapshot(operation(at=later), at=later)
    second = save(db, executed, at=later)
    assert movements(second) == {("RUB", "coupon_income"): 10}
    stale = save(db, pending, at=later + timedelta(minutes=1))
    assert movements(stale) == movements(second)
    assert stale["operation_counts"]["accepted"] == 1
    assert db.execute("SELECT COUNT(*) FROM broker_operation_history_v1").fetchone()[0] == 2


def test_same_time_conflicts_quarantine_until_newer_independent_observation(db):
    first = operation(amount="10")
    second = operation(amount="12")
    receipt = save(db, snapshot(first, second))
    assert receipt["cash_movements"] == [] and receipt["state"] == "partial"
    assert receipt["operation_counts"]["conflicted"] == 1
    assert receipt["coverage"][0]["latest_observation_complete"] is False
    replay = save(db, snapshot(first))
    assert replay["cash_movements"] == []
    later = NOW + timedelta(minutes=1)
    repaired = save(db, snapshot(operation(amount="12", at=later), at=later), at=later)
    assert repaired["operation_counts"]["accepted"] == 1
    assert movements(repaired) == {("RUB", "coupon_income"): 12}


@pytest.mark.parametrize("payment", [None, {}, {"currency": "RUB", "value": {}},
    {"currency": "RUB", "value": {"units": True, "nano": 0}},
    {"currency": "RUB", "value": {"units": "1", "nano": -1}},
    {"currency": "RUB", "amount": "NaN"}, {"currency": "RUB", "amount": 3.1},
    {"currency": "RUB", "amount": "0.0000000001"}, {"currency": "WRONG", "amount": "3"}])
def test_missing_or_malformed_payment_is_quarantined_without_fake_zero(db, payment):
    pair = operation()
    pair[0]["payment"] = payment
    receipt = save(db, snapshot(pair))
    assert receipt["cash_movements"] == [] and receipt["state"] == "partial"
    assert receipt["operation_counts"]["quarantined"] == 1
    assert db.execute("SELECT amount FROM broker_operation_history_v1").fetchone()[0] is None


def test_user_reconnection_and_account_ids_scope_identical_operation_ids(db):
    save(db, snapshot(operation(amount="10")))
    save(db, snapshot(operation(amount="20", account="account-b")))
    save(db, snapshot(operation(amount="30")), broker="connection-b")
    save(db, snapshot(operation(amount="40")), user=2)
    assert movements(ledger.summary_in(db, user_id=1, broker_key="connection-a", account_ids=["account-a"])) == {("RUB", "coupon_income"): 10}
    assert movements(ledger.summary_in(db, user_id=1, broker_key="connection-a", account_ids=["account-b"])) == {("RUB", "coupon_income"): 20}
    assert db.execute("SELECT COUNT(*) FROM broker_operation_current_v1").fetchone()[0] == 4


def test_history_survives_rolling_range_and_does_not_assume_missing_operation_cancelled(db):
    old = operation("old", "10")
    old[0]["date"] = (NOW - timedelta(days=50)).isoformat()
    save(db, snapshot(old))
    later = NOW + timedelta(days=1)
    new = operation("new", "5", at=later)
    receipt = save(db, snapshot(new, at=later, begin=later - timedelta(days=10)), at=later)
    assert movements(receipt) == {("RUB", "coupon_income"): 15}
    assert receipt["operation_counts"]["accepted"] == 2
    assert receipt["history_preserved"] is True
    assert receipt["coverage"][0]["outside_observed_ranges_unknown"] is True


def test_source_and_window_failures_do_not_fabricate_empty_complete_history(db):
    empty = snapshot()
    missing = save(db, empty)
    assert missing["state"] == "partial"
    assert missing["coverage"][0]["complete_observed_ranges"] == []
    assert missing["coverage"][0]["latest_observed_at"] is None
    assert "operation_account_observation_missing" in missing["coverage"][0]["latest_issues"]
    later = NOW + timedelta(minutes=1)
    proven = snapshot(at=later)
    proven["sources"] = [source("GetOperationsByCursor", "account-a", later.isoformat())]
    receipt = save(db, proven, at=later)
    assert receipt["state"] == "observed"
    assert receipt["cash_movements"] == []


def test_invalid_and_missing_operation_timestamps_preserve_snapshot_transaction(db):
    pair = operation()
    value = snapshot(pair)
    value["sources"][0]["observed_at"] = "not-a-timestamp"
    value["section_as_of"] = {"operations": "bad-explicit-time"}
    receipt = save(db, value)
    assert receipt["state"] == "partial" and receipt["cash_movements"] == []
    row = db.execute("SELECT observed_at,disposition FROM broker_operation_history_v1").fetchone()
    assert tuple(row) == ("", "quarantined")
    # The recent valuation timestamp must not fill the missing operation clock.
    assert receipt["coverage"][0]["latest_observed_at"] is None


def test_operations_outside_declared_range_are_quarantined(db):
    pair = operation()
    pair[0]["date"] = (NOW - timedelta(days=100)).isoformat()
    receipt = save(db, snapshot(pair))
    assert receipt["cash_movements"] == [] and receipt["state"] == "partial"
    assert db.execute("SELECT reason FROM broker_operation_current_v1").fetchone()[0] == "operation_outside_observed_range"


def test_simultaneous_conflicting_coverage_is_conservative_in_any_insert_order(db):
    complete = snapshot(operation())
    incomplete = snapshot(operation(), complete=False)
    save(db, incomplete)
    receipt = save(db, complete)
    assert receipt["coverage"][0]["latest_observation_complete"] is False
    assert receipt["state"] == "partial"


def test_disjoint_windows_report_gap_and_partial_collection_does_not_erase_ranges(db):
    early = operation("early")
    early[0]["date"] = (NOW - timedelta(days=55)).isoformat()
    save(db, snapshot(early, begin=NOW - timedelta(days=60), end=NOW - timedelta(days=50)))
    middle = operation("middle")
    middle[0]["date"] = (NOW - timedelta(days=10)).isoformat()
    receipt = save(db, snapshot(middle, begin=NOW - timedelta(days=30)))
    assert receipt["coverage"][0]["known_gaps"] == [[(NOW - timedelta(days=50)).isoformat(), (NOW - timedelta(days=30)).isoformat()]]
    assert receipt["state"] == "partial"
    later = NOW + timedelta(minutes=1)
    partial = snapshot(operation("latest", at=later), at=later, complete=False)
    retained = save(db, partial, at=later)
    assert retained["coverage"][0]["complete_observed_ranges"] == receipt["coverage"][0]["complete_observed_ranges"]
    assert retained["coverage"][0]["latest_observation_complete"] is False


def test_snapshot_failure_rolls_back_ledger_revisions_and_cash_totals(db):
    save(db, snapshot(operation()))
    db.execute("CREATE TABLE snapshot_marker (value TEXT)")
    db.commit()
    later = NOW + timedelta(minutes=1)
    with pytest.raises(RuntimeError, match="synthetic_snapshot_failure"):
        with db:
            db.execute("BEGIN IMMEDIATE")
            ledger.record_snapshot_in(db, user_id=1, broker_key="connection-a",
                snapshot=snapshot(operation(amount="99", at=later), at=later), at=later)
            db.execute("INSERT INTO snapshot_marker VALUES ('new snapshot')")
            raise RuntimeError("synthetic_snapshot_failure")
    assert db.execute("SELECT COUNT(*) FROM snapshot_marker").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM broker_operation_history_v1").fetchone()[0] == 1
    assert movements(ledger.summary_in(db, user_id=1, broker_key="connection-a", account_ids=["account-a"])) == {("RUB", "coupon_income"): 10}


def test_payment_precision_is_independent_of_caller_decimal_context(db):
    pair = operation()
    pair[0]["payment"] = {"currency": "RUB", "value": {"units": "999999999999999", "nano": 1}}
    with localcontext() as context:
        context.prec = 3
        receipt = save(db, snapshot(pair))
    assert movements(receipt) == {("RUB", "coupon_income"): Decimal("999999999999999.000000001")}


def test_ledger_refuses_independent_commit_boundary(db):
    with pytest.raises(ledger.LedgerError, match="operation_ledger_transaction_required"):
        ledger.record_snapshot_in(db, user_id=1, broker_key="connection-a", snapshot=snapshot(operation()), at=NOW)


def test_retained_historical_source_does_not_invalidate_new_account_window(db):
    value = snapshot(operation())
    old = source("GetOperationsByCursor", "account-a", (NOW - timedelta(hours=3)).isoformat())
    value["sources"].append(old)
    receipt = save(db, value)
    assert receipt["state"] == "observed"
    assert receipt["coverage"][0]["latest_observation_complete"] is True
    assert receipt["coverage"][0]["latest_observed_at"] == NOW.isoformat()
    assert receipt["coverage"][0]["latest_issues"] == []


def test_cancelled_revision_removes_current_cash_but_keeps_executed_history(db):
    save(db, snapshot(operation()))
    later = NOW + timedelta(minutes=1)
    receipt = save(db, snapshot(operation(status="CANCELED", at=later), at=later), at=later)
    assert receipt["cash_movements"] == []
    assert receipt["operation_counts"]["cancelled"] == 1
    assert db.execute("SELECT COUNT(*) FROM broker_operation_history_v1").fetchone()[0] == 2
    assert db.execute("SELECT COUNT(*) FROM broker_operation_history_v1 WHERE disposition='accepted'").fetchone()[0] == 1


@pytest.mark.parametrize("explicit_operation_clock", [False, True])
def test_new_unproven_cash_never_replaces_history_with_accepted_amount(db, explicit_operation_clock):
    save(db, snapshot(operation(amount="10")))
    later = NOW + timedelta(minutes=1)
    value = snapshot(operation(amount="99", at=later), at=later)
    value["sources"] = []
    value["operations"]["items"][0]["source_ids"] = []
    if explicit_operation_clock:
        value["section_as_of"] = {"operations": later.isoformat()}
    receipt = save(db, value, at=later)
    assert receipt["state"] == "partial"
    assert movements(receipt) == ({} if explicit_operation_clock else {("RUB", "coupon_income"): 10})
    assert db.execute("SELECT COUNT(*) FROM broker_operation_history_v1 WHERE disposition='quarantined'").fetchone()[0] == 1
    assert receipt["coverage"][0]["latest_observation_complete"] is False


@pytest.mark.parametrize("status", ["UNSPECIFIED", "UNKNOWN", ""])
def test_unknown_operation_status_cannot_be_counted_as_received_income(db, status):
    receipt = save(db, snapshot(operation(status=status)))
    assert receipt["cash_movements"] == []
    assert receipt["operation_counts"]["quarantined"] == 1
    assert db.execute("SELECT reason FROM broker_operation_current_v1").fetchone()[0] == "operation_state_unknown"
