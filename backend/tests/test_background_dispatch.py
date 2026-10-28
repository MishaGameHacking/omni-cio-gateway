"""N02 scenarios on isolated SQLite with explicit synthetic source fixtures."""
from contextlib import closing
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import time

import pytest
from fastapi import HTTPException

from backend import app as backend, autonomous_ai as ai, autonomous_controller as controller
from backend import background_dispatch as dispatch, event_monitor, market_schedule
from backend import volume_state as state, volume_workspace as workspace, volume_jobs as jobs
from backend.ai_jobs import AnalysisQueue, CURRENT_JOB
from backend.volume_contract import now_iso, source, section
from backend.tests.test_volume_workspace import fixture, broker_fixture


def stored(fixture, *, open_window=False, age=1800):
    now = datetime.now(timezone.utc)
    snapshot = deepcopy(fixture["snapshot"])
    snapshot["as_of"] = (now - timedelta(seconds=age)).isoformat()
    snapshot["collection"] = {"finished_at": snapshot["as_of"]}
    snapshot["attribution"] = {"complete": True, "retained_marker": "old-accounting"}
    for position in snapshot["positions"]:
        if position["instrument_type"] in {"share", "bond"}:
            position["metadata"]["exchange"] = "MOEX"
    observed = (now - timedelta(seconds=10)).isoformat()
    raw = {"timezone": "UTC", "as_of": observed, "exchanges": [{"exchange": "MOEX", "days": [{
        "date": now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(), "isTradingDay": open_window,
        "startTime": (now - timedelta(minutes=10)).isoformat(), "endTime": (now + timedelta(hours=1)).isoformat()}]}]}
    snapshot["calendar"] = section(raw, as_of=observed)
    workspace.persist(fixture["user"], snapshot)
    return state.saved_snapshot(fixture["user"])


def event_sources(fixture):
    def markets(user, checkpoint, progress):
        observed = now_iso()
        ref = source("News", "synthetic-event", observed, ttl=900)
        checkpoint["news"] = section({"items": [{"id": "new-synthetic-news", "instrument_uids": ["aaa"],
            "title": "Synthetic issuer event", "source_ids": [ref["id"]]}], "complete": True}, as_of=observed, sources=[ref])
        checkpoint["calendar"] = state.saved_snapshot(user)["calendar"]
        progress("collecting_news", checkpoint)
    fixture["patch"].setattr(workspace, "_collect_market_events", markets)
    fixture["patch"].setattr(workspace, "_collect_operations", lambda *args: ([], [], True))
    fixture["patch"].setattr(workspace, "_payment_events", lambda *args: ([], [], True))


def forbidden(*args, **kwargs):
    raise AssertionError("Unexpected quote, paid-model or unmocked network call")


def counts():
    with closing(backend.connect()) as db:
        return {name: db.execute("SELECT COUNT(*) FROM " + name).fetchone()[0]
                for name in ("ai_work_jobs", "ai_money_reservations", "insight_cards")}


def test_closed_market_still_schedules_events_with_zero_model_budget(fixture):
    stored(fixture)
    fixture["patch"].setattr(ai, "get_tinvest_portfolio", forbidden)
    fixture["patch"].setattr(controller, "enqueue_collection", forbidden)
    result = dispatch.enqueue_cycle(fixture["user"])
    assert result["market"] == "closed" and set(result["lanes"]) == {"events"}
    assert result["lanes"]["events"]["state"] == "queued"
    assert counts() == {"ai_work_jobs": 0, "ai_money_reservations": 0, "insight_cards": 0}


def test_unknown_calendar_keeps_event_lane_and_blocks_automatic_prices(fixture):
    snapshot = stored(fixture)
    snapshot.pop("calendar")
    workspace.persist(fixture["user"], snapshot)
    result = dispatch.enqueue_cycle(fixture["user"])
    assert result["market"] == "unknown" and set(result["lanes"]) == {"events"}


def test_first_connection_can_bootstrap_once_without_a_calendar(fixture):
    with closing(backend.connect()) as db:
        db.execute("DELETE FROM workspace_snapshots WHERE user_id=?", (fixture["user"]["id"],))
        db.commit()
    first, second = dispatch.enqueue_cycle(fixture["user"]), dispatch.enqueue_cycle(fixture["user"])
    assert first["lanes"]["collection"]["job_id"] == second["lanes"]["collection"]["job_id"]
    assert first["lanes"]["events"]["state"] == "awaiting_first_snapshot"
    assert counts()["ai_work_jobs"] == 0


def test_open_window_schedules_due_prices_but_not_every_tick(fixture):
    stored(fixture, open_window=True)
    first = dispatch.enqueue_cycle(fixture["user"])
    second = dispatch.enqueue_cycle(fixture["user"])
    assert set(first["lanes"]) == {"events", "collection", "analysis"}
    assert first["lanes"]["analysis"]["job_id"] == second["lanes"]["analysis"]["job_id"]
    assert counts()["ai_work_jobs"] == 1
    stored(fixture, open_window=True, age=30)
    assert "analysis" not in dispatch.enqueue_cycle(fixture["user"])["lanes"]


def test_event_job_keeps_prices_and_accounting_times_and_updates_event_freshness(fixture):
    old = stored(fixture)
    event_sources(fixture)
    fixture["patch"].setattr(workspace.details, "load_dashboard", forbidden)
    fixture["patch"].setattr(ai, "get_tinvest_portfolio", forbidden)
    fixture["patch"].setattr(ai, "analyze_if_needed", forbidden)
    job = dispatch.enqueue_events(fixture["user"])
    jobs.run_job(job["job_id"])
    assert jobs.get_job(int(fixture["user"]["id"]), job["job_id"])["state"] == "completed"
    new = state.saved_snapshot(fixture["user"])
    for name in ("as_of", "capital", "positions", "collection", "attribution"):
        assert new[name] == old[name]
    assert new["events"]["items"][0]["id"] == "new-synthetic-news"
    assert new["event_monitor"]["complete"] is True
    assert new["event_monitor"]["valuation_refreshed"] is False
    sections = workspace._snapshot_sections(new, new["as_of"], "partial", "snapshot_stale")
    assert sections["capital"]["state"] == "partial"
    assert sections["events"]["state"] == "available" and sections["events"]["reason"] is None
    assert dispatch.enqueue_events(fixture["user"]) == {"state": "current"}
    assert counts()["ai_money_reservations"] == counts()["insight_cards"] == 0


def test_event_source_failure_preserves_other_sources_and_acknowledged_cursor(fixture):
    stored(fixture)
    real_operations = workspace._collect_operations
    event_sources(fixture)
    # Restore the real paginator, then fail after its first acknowledged page.
    fixture["patch"].setattr(workspace, "_collect_operations", real_operations)
    calls, failing = [], [True]

    def read(method, body):
        assert method == "operations"
        calls.append((body["accountId"], body["cursor"]))
        if body["accountId"] == "owned-account-a" and not body["cursor"]:
            return {"items": [], "hasNext": True, "nextCursor": "acknowledged-page-2"}
        if body["accountId"] == "owned-account-a" and failing[0]:
            raise HTTPException(503, "synthetic_source_unavailable")
        return {"items": [], "hasNext": False}

    broker_fixture(fixture, read)
    first = dispatch.enqueue_events(fixture["user"])
    jobs.run_job(first["job_id"])
    assert jobs.get_job(int(fixture["user"]["id"]), first["job_id"])["state"] == "failed"
    partial = state.saved_snapshot(fixture["user"])
    assert partial["events"]["items"][0]["id"] == "new-synthetic-news"
    assert partial["event_monitor"]["complete"] is False
    assert dispatch.enqueue_events(fixture["user"]) == {"state": "current"}
    failing[0] = False
    second = dispatch.enqueue_events(fixture["user"], now=datetime.now(timezone.utc) + timedelta(seconds=601))
    jobs.run_job(second["job_id"])
    assert jobs.get_job(int(fixture["user"]["id"]), second["job_id"])["state"] == "completed"
    assert calls.count(("owned-account-a", "")) == 1
    assert calls.count(("owned-account-a", "acknowledged-page-2")) == 2
    assert state.saved_snapshot(fixture["user"])["event_monitor"]["complete"] is True


def test_concurrent_newer_snapshot_cannot_be_overwritten_by_event_commit(fixture):
    old = stored(fixture)
    event_sources(fixture)
    original = workspace.persist
    newer = deepcopy(old)
    newer["as_of"] = now_iso()
    newer["capital"]["total"]["value"] = "201"

    def racing(user, snapshot, *, expected_snapshot=None):
        assert expected_snapshot is not None
        original(user, newer)
        return original(user, snapshot, expected_snapshot=expected_snapshot)

    fixture["patch"].setattr(workspace, "persist", racing)
    job = dispatch.enqueue_events(fixture["user"])
    jobs.run_job(job["job_id"])
    result = jobs.get_job(int(fixture["user"]["id"]), job["job_id"])
    assert result["state"] == "failed" and result["error_code"] == "workspace_snapshot_changed"
    current = state.saved_snapshot(fixture["user"])
    assert current["as_of"] == newer["as_of"] and current["capital"] == newer["capital"]
    assert "event_monitor" not in current


def test_reconnection_rejects_queued_old_event_work_before_source_access(fixture):
    stored(fixture)
    job = dispatch.enqueue_events(fixture["user"])
    with closing(backend.connect()) as db:
        db.execute("UPDATE users SET tinvest_token_encrypted=? WHERE id=?", (b"changed-connection", fixture["user"]["id"]))
        db.commit()
    fixture["patch"].setattr(workspace, "_collect_market_events", forbidden)
    jobs.run_job(job["job_id"])
    result = jobs.get_job(int(fixture["user"]["id"]), job["job_id"])
    assert result["state"] == "failed" and result["error_code"] == "workspace_broker_connection_changed"


def test_pause_cancels_automatic_events_without_cancelling_manual_refresh(fixture):
    stored(fixture)
    automatic = dispatch.enqueue_events(fixture["user"])
    manual = jobs.enqueue(int(fixture["user"]["id"]), "manual-refresh-preserved", "refresh", {"currency": "RUB"})
    controller.update_preferences(controller.PreferenceUpdate(enabled=False, expected_version=0), fixture["user"])
    assert jobs.get_job(int(fixture["user"]["id"]), automatic["job_id"])["state"] == "cancelled"
    assert jobs.get_job(int(fixture["user"]["id"]), manual["job_id"])["state"] == "queued"
    assert dispatch.enqueue_cycle(fixture["user"]) == {"state": "paused"}


def test_automatic_analysis_rechecks_closure_at_execution_before_broker_or_model(fixture):
    stored(fixture, open_window=True)
    dispatch.enqueue_cycle(fixture["user"])
    stored(fixture, open_window=False)
    fixture["patch"].setattr(ai, "get_tinvest_portfolio", forbidden)
    queue = AnalysisQueue(backend.connect)
    job = queue.claim()
    marker = CURRENT_JOB.set((job["id"], job["owner"]))
    try:
        result = ai.run_user_analysis(int(fixture["user"]["id"]))
    finally:
        CURRENT_JOB.reset(marker)
    assert result["state"] == "waiting"
    assert result["tier"] == "none"
    assert counts()["ai_money_reservations"] == 0


def test_manual_request_coalescing_removes_only_its_automatic_calendar_restriction(fixture):
    stored(fixture, open_window=True)
    automatic = dispatch.enqueue_cycle(fixture["user"])["lanes"]["analysis"]
    stored(fixture, open_window=False)
    manual = dispatch.enqueue_manual_analysis(fixture["user"])
    assert manual["job_id"] == automatic["job_id"] and manual["coalesced"] is True
    assert dispatch.automatic_analysis_gate(fixture["user"], (manual["job_id"], "synthetic-owner"), datetime.now(timezone.utc)) is None


def test_automatic_collection_rechecks_calendar_after_waiting_in_queue(fixture):
    stored(fixture, open_window=True)
    automatic = dispatch.enqueue_cycle(fixture["user"])["lanes"]["collection"]
    old = stored(fixture, open_window=False)
    fixture["patch"].setattr(workspace.details, "load_dashboard", forbidden)
    jobs.run_job(automatic["job_id"])
    result = jobs.get_job(int(fixture["user"]["id"]), automatic["job_id"])
    assert result["state"] == "completed" and result["result"]["state"] == "waiting"
    assert result["result"]["valuation_refreshed"] is False
    assert state.saved_snapshot(fixture["user"])["as_of"] == old["as_of"]


def test_event_compare_and_swap_detects_changes_with_same_snapshot_id(fixture):
    original = stored(fixture)
    concurrent = deepcopy(original)
    concurrent["events"] = {"items": [{"id": "concurrent-event"}], "complete": True}
    workspace.persist(fixture["user"], concurrent)
    assert state.saved_snapshot(fixture["user"])["snapshot_id"] == original["snapshot_id"]
    with pytest.raises(HTTPException) as caught:
        workspace.persist(fixture["user"], original, expected_snapshot=original)
    assert caught.value.status_code == 409 and caught.value.detail == "workspace_snapshot_changed"
    assert state.saved_snapshot(fixture["user"])["events"] == concurrent["events"]


def test_calendar_and_event_status_are_read_only_and_survive_in_memory_reset(fixture):
    stored(fixture, open_window=True)
    fixture["patch"].setattr(workspace.market, "calendar", forbidden)
    fixture["patch"].setattr(workspace.market, "load_news", forbidden)
    with closing(backend.connect()) as db:
        before = db.execute("SELECT COUNT(*),SUM(version) FROM workspace_records").fetchone()
    first = dispatch.schedule(fixture["user"])
    second = dispatch.schedule(fixture["user"])
    with closing(backend.connect()) as db:
        after = db.execute("SELECT COUNT(*),SUM(version) FROM workspace_records").fetchone()
    assert tuple(before) == tuple(after)
    assert first["as_of"] == second["as_of"] and first["regular_price_polling_allowed"] is True
    assert first["trade_permission"] is False


def finish_claim(job):
    with closing(backend.connect()) as db:
        db.execute("UPDATE workspace_jobs SET state='completed' WHERE id=?", (job["id"],))
        db.commit()


def test_queue_priority_aging_and_reconciliation_order(fixture):
    uid = int(fixture["user"]["id"])
    oldest = jobs.enqueue(uid, "auto.full.synthetic", "refresh", {})
    event = jobs.enqueue(uid, "auto.events.synthetic", "events", {})
    reconcile = jobs.enqueue(uid, "synthetic-reconcile", "reconcile", {})
    with closing(backend.connect()) as db:
        db.execute("UPDATE workspace_jobs SET created_at=? WHERE id=?", (int(time.time()) - 901, oldest["job_id"]))
        db.commit()
    first = jobs._claim()
    assert first["id"] == reconcile["job_id"]
    finish_claim(first)
    second = jobs._claim()
    assert second["id"] == oldest["job_id"]
    finish_claim(second)
    assert jobs._claim()["id"] == event["job_id"]


def test_new_events_precede_background_work_but_preserve_per_user_lease(fixture):
    uid = int(fixture["user"]["id"])
    jobs.enqueue(uid, "auto.full.fresh", "refresh", {})
    event = jobs.enqueue(uid, "auto.events.fresh", "events", {})
    assert jobs._claim()["id"] == event["job_id"]
    other = jobs.enqueue(int(fixture["other"]["id"]), "other-user-fresh", "refresh", {})
    assert jobs._claim()["id"] == other["job_id"]
    assert jobs._claim() is None


def test_expired_event_worker_preserves_its_checkpoint_and_receives_new_owner(fixture):
    uid = int(fixture["user"]["id"])
    item = jobs.enqueue(uid, "auto.events.expired", "events", {}, checkpoint={"acknowledged_cursor": "page-2"})
    with closing(backend.connect()) as db:
        db.execute("UPDATE workspace_jobs SET state='running',owner='old-worker',expires_at=? WHERE id=?", (int(time.time()) - 1, item["job_id"]))
        db.commit()
    claimed = jobs._claim()
    assert claimed["id"] == item["job_id"] and claimed["owner"] != "old-worker"
    assert json.loads(claimed["checkpoint_json"]) == {"acknowledged_cursor": "page-2"}


def test_failure_or_full_queue_for_one_user_does_not_abort_other_dispatch_lanes(fixture):
    stored(fixture, open_window=True)
    uid = int(fixture["user"]["id"])
    for index in range(5):
        jobs.enqueue(uid, "queue-full-" + str(index), "refresh", {})
    result = dispatch.enqueue_cycle(fixture["user"])
    assert result["lanes"]["events"]["http_status"] == 429
    assert result["lanes"]["collection"]["http_status"] == 429
    assert result["lanes"]["analysis"]["state"] == "queued"
