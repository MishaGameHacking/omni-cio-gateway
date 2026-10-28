"""Synthetic event/notification regressions; no broker, model, phone or cloud calls."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import sqlite3
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from backend import app as backend
from backend import event_monitor as events, volume_live as live

NOW = datetime(2026, 10, 28, 6, tzinfo=timezone.utc)


@pytest.mark.parametrize("status", [401, 403, 409])
def test_optional_lane_never_downgrades_authorization_or_binding_failure(status):
    failure = HTTPException(status, "synthetic_binding_failure")
    collect = Mock(side_effect=failure)
    with pytest.raises(HTTPException) as caught:
        events._optional_lane(collect, "synthetic-argument")
    assert caught.value is failure
    collect.assert_called_once_with("synthetic-argument")


@pytest.mark.parametrize("status", [400, 429, 500, 502, 503, 504])
def test_unavailable_lane_preserves_explicit_incomplete_result(status):
    collect = Mock(side_effect=HTTPException(status, "synthetic_source_outage"))
    assert events._optional_lane(collect) == ([], [], False)
    collect.assert_called_once_with()


def test_unexpected_internal_error_is_not_disguised_as_source_outage():
    collect = Mock(side_effect=RuntimeError("synthetic_internal_failure"))
    with pytest.raises(RuntimeError, match="synthetic_internal_failure"):
        events._optional_lane(collect)


@pytest.mark.parametrize("age,expected", [(0, True), (599, True), (600, False), (-1, False)])
def test_event_cache_age_has_the_original_inclusive_exclusive_bounds(age, expected):
    row = {"state": "available", "as_of": (NOW - timedelta(seconds=age)).isoformat()}
    assert events._source_reusable(row, NOW) is expected


@pytest.mark.parametrize("state", ["partial", "unavailable", "pending"])
def test_nonavailable_source_is_not_reused_even_with_a_fresh_timestamp(state):
    row = {"state": state, "as_of": NOW.isoformat()}
    assert events._source_reusable(row, NOW) is False


def test_incomplete_paginator_keeps_original_acknowledged_horizon():
    old = {"currency": "RUB", "accounts": [{"id": "synthetic-account"}], "positions": []}
    start = NOW - timedelta(hours=1)
    checkpoint = {"broker_key": "synthetic-binding", "event_basis": events._basis(old),
        "event_started_at": start.isoformat(), "event_operations_begin": "2026-09-01T00:00:00+00:00",
        "operations": {"synthetic-account": {"complete": False, "cursor": "acknowledged-page"}}}
    before = deepcopy(checkpoint)
    assert events._prepare_checkpoint(checkpoint, old, "synthetic-binding", NOW) == start
    assert checkpoint == before


def test_metadata_repair_preserves_prices_valuation_and_other_metadata(monkeypatch):
    position = {"instrument_type": "bond", "instrument_uid": "synthetic-bond",
        "quantity": "4", "price": "99.95", "metadata": {"coupon": "10.00"}}
    old = {"as_of": "2026-10-27T12:00:00+00:00", "snapshot_id": "previous",
        "capital": {"value": "400"}, "positions": [position], "position_coverage": {"complete": True}}
    before = deepcopy(old)
    read = Mock(return_value={"exchange": "MOEX", "_source": {"id": "synthetic-venue-evidence"}})
    monkeypatch.setattr(events.workspace.market, "instrument", read)
    progress = Mock()
    result = events._repair_exchange_metadata({}, old, {}, progress)
    assert result == (1, True, {})
    assert old["as_of"] == before["as_of"]
    assert old["capital"] == before["capital"]
    assert old["positions"][0]["price"] == before["positions"][0]["price"]
    assert old["positions"][0]["quantity"] == before["positions"][0]["quantity"]
    assert old["positions"][0]["metadata"]["coupon"] == "10.00"
    assert old["positions"][0]["metadata"]["exchange"] == "MOEX"
    assert old["snapshot_id"] != before["snapshot_id"]
    assert progress.call_count == 2
    read.assert_called_once_with({}, "synthetic-bond")


def test_metadata_attempt_budget_is_bounded_and_does_not_starve_untried_instruments(monkeypatch):
    rows = [{"instrument_type": "share", "instrument_uid": f"synthetic-{i}", "metadata": {}}
            for i in range(7)]
    snapshot = {"positions": rows, "event_monitor": {
        "metadata_last_attempted": {"synthetic-0": NOW.isoformat(), "synthetic-1": NOW.isoformat()}}}
    read = Mock(side_effect=HTTPException(503, "synthetic_venue_outage"))
    monkeypatch.setattr(events.workspace.market, "instrument", read)
    repaired, complete, attempted = events._repair_exchange_metadata({}, snapshot, {}, Mock())
    assert repaired == 0
    assert complete is False
    assert read.call_count == events.MAX_METADATA_REPAIRS
    assert [call.args[1] for call in read.call_args_list] == [f"synthetic-{i}" for i in range(2, 7)]
    assert set(attempted) == {f"synthetic-{i}" for i in range(7)}


def test_successful_event_monitor_never_relabels_the_portfolio_valuation(monkeypatch):
    old = {"as_of": "2026-10-27T12:00:00+00:00"}
    monkeypatch.setattr(events, "now_iso", lambda: NOW.isoformat())
    flags = dict.fromkeys(("news", "calendar", "operations", "payouts"), True)
    result = events._monitor_result(old, "synthetic-binding", NOW, flags, (0, True, {}))
    assert result["complete"] is True
    assert result["checked_at"] == NOW.isoformat()
    assert result["valuation_as_of"] == old["as_of"]
    assert result["valuation_refreshed"] is False
    assert result["new_rating_sources_fetched"] is False


def test_partial_event_monitor_keeps_previous_success_timestamp(monkeypatch):
    prior = "2026-10-27T12:30:00+00:00"
    old = {"as_of": "2026-10-27T12:00:00+00:00", "event_monitor": {"last_successful_at": prior}}
    monkeypatch.setattr(events, "now_iso", lambda: NOW.isoformat())
    flags = {"news": True, "calendar": False, "operations": True, "payouts": True}
    result = events._monitor_result(old, "synthetic-binding", NOW, flags, (0, True, {}))
    assert result["complete"] is False
    assert result["last_successful_at"] == prior
    assert result["calendar"] == "unavailable"
    assert result["operations"] == "available"


@pytest.fixture
def revisions():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE workspace_records (user_id INTEGER, id TEXT, payload TEXT, PRIMARY KEY(user_id,id))")
    db.execute("CREATE TABLE market_facts (id TEXT PRIMARY KEY, payload TEXT)")
    live._revision_tables(db)
    live._reconcile_table_triggers(db, "workspace_records")
    live._reconcile_table_triggers(db, "market_facts")
    db.commit()
    try:
        yield db
    finally:
        db.close()


def stamps(db):
    return dict(db.execute("SELECT user_id,stamp FROM workspace_live_versions"))


def test_committed_changes_invalidate_only_the_affected_owner(revisions):
    revisions.execute("INSERT INTO workspace_records VALUES (1,'one','v1'),(2,'two','v1')")
    revisions.commit()
    before = stamps(revisions)
    revisions.execute("UPDATE workspace_records SET payload='v2' WHERE user_id=1")
    revisions.commit()
    after = stamps(revisions)
    assert after[1] != before[1]
    assert after[2] == before[2]


def test_noop_and_rolled_back_writes_do_not_emit_live_changes(revisions):
    revisions.execute("INSERT INTO workspace_records VALUES (1,'one','v1')")
    revisions.commit()
    before = stamps(revisions)
    revisions.execute("UPDATE workspace_records SET payload=payload")
    revisions.commit()
    assert stamps(revisions) == before
    revisions.execute("UPDATE workspace_records SET payload='uncommitted'")
    revisions.rollback()
    assert stamps(revisions) == before


def test_moving_an_owned_row_invalidates_old_and_new_owner(revisions):
    revisions.execute("INSERT INTO workspace_records VALUES (1,'one','v1'),(2,'two','v1')")
    revisions.commit()
    before = stamps(revisions)
    revisions.execute("UPDATE workspace_records SET user_id=2 WHERE user_id=1")
    revisions.commit()
    after = stamps(revisions)
    assert after[1] != before[1]
    assert after[2] != before[2]


def test_global_facts_invalidate_shared_stamp_without_inventing_owner_rows(revisions):
    before = revisions.execute("SELECT stamp FROM workspace_live_global WHERE singleton=1").fetchone()[0]
    revisions.execute("INSERT INTO market_facts VALUES ('synthetic','new')")
    revisions.commit()
    after = revisions.execute("SELECT stamp FROM workspace_live_global WHERE singleton=1").fetchone()[0]
    assert after != before
    assert stamps(revisions) == {}


def test_repeated_trigger_reconciliation_does_not_replace_identical_sql(revisions):
    before = list(revisions.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' ORDER BY name"))
    statements = []
    revisions.set_trace_callback(statements.append)
    live._reconcile_table_triggers(revisions, "workspace_records")
    after = list(revisions.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' ORDER BY name"))
    assert after == before
    assert not any(sql.startswith("DROP TRIGGER") for sql in statements)
    assert not any(sql.startswith("CREATE TRIGGER") for sql in statements)


@pytest.mark.parametrize("table", ["users", "sessions", "workspace_records; DROP TABLE market_facts", ""])
def test_nonallowlisted_table_never_becomes_trigger_sql(table):
    with pytest.raises(RuntimeError, match="live_table_not_allowed"):
        live._trigger_definition(table, "INSERT", ["user_id"])


def test_missing_owner_or_invalid_column_prevents_trigger_creation():
    with sqlite3.connect(":memory:") as db:
        db.execute("CREATE TABLE workspace_records (id TEXT)")
        with pytest.raises(RuntimeError, match="live_table_has_no_owner"):
            live._reconcile_table_triggers(db, "workspace_records")
        db.execute("DROP TABLE workspace_records")
        db.execute('CREATE TABLE workspace_records (user_id INTEGER, "bad-name" TEXT)')
        with pytest.raises(RuntimeError, match="live_table_column_invalid"):
            live._reconcile_table_triggers(db, "workspace_records")
        assert list(db.execute("SELECT name FROM sqlite_master WHERE type='trigger'")) == []
