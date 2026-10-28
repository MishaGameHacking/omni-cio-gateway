"""Unchanged source polling must not duplicate operation payload history."""
from datetime import timedelta
import json

import pytest

from backend import operations_ledger as ledger
from backend.tests.test_operations_ledger import db, NOW, operation, snapshot, save, movements


def test_one_hundred_unchanged_observations_keep_one_payload_version_and_current_proof(db):
    for index in range(100):
        at = NOW + timedelta(minutes=index * 10)
        pair = operation(at=at)
        receipt = save(db, snapshot(pair, at=at), at=at)
    assert movements(receipt) == {("RUB", "coupon_income"): 10}
    assert db.execute("SELECT COUNT(*) FROM broker_operation_history_v1").fetchone()[0] == 1
    row = db.execute("SELECT observed_at,evidence,received_at FROM broker_operation_current_v1").fetchone()
    assert tuple(row) == (at.isoformat(), json.dumps([pair[1]["id"]], separators=(",", ":")), at.isoformat())
    assert db.execute("SELECT observed_at FROM broker_operation_history_v1").fetchone()[0] == NOW.isoformat()


def test_a_b_a_preserves_return_transition_despite_unchanged_repeats(db):
    for index, amount in enumerate(["10", "10", "20", "20", "10", "10"]):
        at = NOW + timedelta(minutes=index)
        receipt = save(db, snapshot(operation(amount=amount, at=at), at=at), at=at)
    rows = db.execute("SELECT amount,observed_at FROM broker_operation_history_v1 ORDER BY observed_at").fetchall()
    assert [row[0] for row in rows] == ["10", "10", "20", "20", "10"]
    assert [row[1] for row in rows] == [(NOW + timedelta(minutes=i)).isoformat() for i in (0, 1, 2, 3, 4)]
    assert movements(receipt) == {("RUB", "coupon_income"): 10}


def test_three_consecutive_different_versions_preserve_a_b_a_return(db):
    for index, amount in enumerate(["10", "20", "10"]):
        at = NOW + timedelta(minutes=index)
        receipt = save(db, snapshot(operation(amount=amount, at=at), at=at), at=at)
    rows = db.execute("SELECT amount FROM broker_operation_history_v1 ORDER BY observed_at").fetchall()
    assert [row[0] for row in rows] == ["10", "20", "10"]
    assert movements(receipt) == {("RUB", "coupon_income"): 10}


def test_conflict_at_coalesced_timestamp_preserves_both_proofs_and_cannot_be_replayed_away(db):
    first = snapshot(operation())
    save(db, first)
    at = NOW + timedelta(minutes=1)
    same = operation(at=at)
    save(db, snapshot(same, at=at), at=at)
    conflicted = save(db, snapshot(operation(amount="20", at=at), at=at), at=at)
    assert conflicted["cash_movements"] == [] and conflicted["operation_counts"]["conflicted"] == 1
    proofs = db.execute("SELECT amount,evidence FROM broker_operation_history_v1 WHERE observed_at=? ORDER BY amount", (at.isoformat(),)).fetchall()
    assert len(proofs) == 2
    assert json.loads(proofs[0][1]) == [same[1]["id"]]
    old_replay = save(db, first, at=at + timedelta(minutes=1))
    equal_replay = save(db, snapshot(same, at=at), at=at + timedelta(minutes=2))
    assert old_replay["cash_movements"] == equal_replay["cash_movements"] == []
    assert equal_replay["operation_counts"]["conflicted"] == 1


def test_late_intermediate_b_materializes_already_confirmed_return_to_a(db):
    save(db, snapshot(operation()))
    latest = NOW + timedelta(minutes=2)
    a = operation(at=latest)
    save(db, snapshot(a, at=latest), at=latest)
    middle = NOW + timedelta(minutes=1)
    b = snapshot(operation(amount="20", at=middle), at=middle)
    receipt = save(db, b, at=latest + timedelta(minutes=1))
    assert movements(receipt) == {("RUB", "coupon_income"): 10}
    rows = db.execute("SELECT amount,observed_at FROM broker_operation_history_v1 ORDER BY observed_at").fetchall()
    assert [row[0] for row in rows] == ["10", "20", "10"]
    assert [row[1] for row in rows] == [NOW.isoformat(), middle.isoformat(), latest.isoformat()]
    current = db.execute("SELECT c.observed_at,c.evidence,h.observed_at FROM broker_operation_current_v1 c "
        "JOIN broker_operation_history_v1 h ON h.id=c.history_id").fetchone()
    assert current[0] == current[2] == latest.isoformat()
    assert json.loads(current[1]) == [a[1]["id"]]
    save(db, b, at=latest + timedelta(minutes=2))
    assert db.execute("SELECT COUNT(*) FROM broker_operation_history_v1").fetchone()[0] == 3


def test_late_change_after_newer_revision_preserves_last_previous_attestation(db):
    save(db, snapshot(operation()))
    last_a = NOW + timedelta(minutes=5)
    a = operation(at=last_a)
    save(db, snapshot(a, at=last_a), at=last_a)
    newest = NOW + timedelta(minutes=6)
    b = operation(amount="20", at=newest)
    save(db, snapshot(b, at=newest), at=newest)
    middle = NOW + timedelta(minutes=3)
    receipt = save(db, snapshot(operation(amount="20", at=middle), at=middle), at=newest + timedelta(minutes=1))
    assert movements(receipt) == {("RUB", "coupon_income"): 20}
    rows = db.execute("SELECT amount,observed_at,evidence FROM broker_operation_history_v1 ORDER BY observed_at").fetchall()
    assert [(row[0], row[1]) for row in rows] == [
        ("10", NOW.isoformat()), ("20", middle.isoformat()),
        ("10", last_a.isoformat()), ("20", newest.isoformat()),
    ]
    assert json.loads(rows[2][2]) == [a[1]["id"]]
    current = db.execute("SELECT c.observed_at,c.evidence,h.amount FROM broker_operation_current_v1 c "
        "JOIN broker_operation_history_v1 h ON h.id=c.history_id").fetchone()
    assert tuple(current) == (newest.isoformat(), json.dumps([b[1]["id"]], separators=(",", ":")), "20")


def test_coalescing_columns_migrate_atomically_without_deleting_legacy_rows(db):
    db.execute("CREATE TABLE broker_operation_current_v1 (user_id INTEGER NOT NULL,broker_key TEXT NOT NULL,"
        "account_id TEXT NOT NULL,operation_id TEXT NOT NULL,observed_at TEXT NOT NULL,history_id TEXT,"
        "disposition TEXT NOT NULL,reason TEXT,PRIMARY KEY(user_id,broker_key,account_id,operation_id))")
    db.execute("INSERT INTO broker_operation_current_v1 VALUES (1,'old-connection','old-account','old-op',?,NULL,'conflicted','old-conflict')", (NOW.isoformat(),))
    db.commit()
    with pytest.raises(RuntimeError):
        with db:
            db.execute("BEGIN IMMEDIATE")
            ledger.initialize_in(db)
            raise RuntimeError("synthetic_transaction_failure")
    assert len(db.execute("PRAGMA table_info(broker_operation_current_v1)").fetchall()) == 8
    with db:
        db.execute("BEGIN IMMEDIATE")
        ledger.initialize_in(db)
    assert len(db.execute("PRAGMA table_info(broker_operation_current_v1)").fetchall()) == 10
    row = db.execute("SELECT operation_id,disposition,evidence FROM broker_operation_current_v1").fetchone()
    assert tuple(row) == ("old-op", "conflicted", "[]")
