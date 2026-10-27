"""Independent source failures must not indefinitely freeze completed lanes."""
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from backend import app as backend
from backend import background_dispatch as dispatch, event_monitor
from backend import volume_jobs as jobs, volume_state as state, volume_workspace as workspace
from backend.tests.test_background_dispatch import stored
from backend.tests.test_volume_workspace import fixture, broker_fixture
from backend.volume_contract import section


def source_clock(fixture):
    clock = [datetime.now(timezone.utc)]

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock[0]

    fixture["patch"].setattr(event_monitor, "datetime", Clock)
    fixture["patch"].setattr(event_monitor, "now_iso", lambda: clock[0].isoformat())
    fixture["patch"].setattr(workspace, "now_iso", lambda: clock[0].isoformat())
    return clock


def market_sources(fixture, *, news_available):
    def collect(user, checkpoint, progress):
        checkpoint["news"] = section({"items": [], "complete": news_available},
            state="available" if news_available else "unavailable", as_of=event_monitor.now_iso())
        checkpoint["calendar"] = state.saved_snapshot(user)["calendar"]
        progress("collecting_news", checkpoint)
    fixture["patch"].setattr(workspace, "_collect_market_events", collect)


def test_persistent_news_failure_does_not_freeze_completed_operations_or_payouts(fixture):
    stored(fixture)
    clock = source_clock(fixture)
    market_sources(fixture, news_available=False)
    calls, generation = [], [0]

    def read(method, body):
        calls.append((method, dict(body)))
        if method == "operations":
            items = [] if generation[0] == 0 else [{
                "id": "new-income-" + body["accountId"], "type": "OPERATION_TYPE_DIVIDEND",
                "date": clock[0].isoformat(), "state": "OPERATION_STATE_EXECUTED",
                "payment": {"units": "3", "nano": 0, "currency": "rub"}, "quantity": "1"}]
            return {"items": items, "hasNext": False}
        assert method == "dividends"
        return {"dividends": [] if generation[0] == 0 else [{
            "paymentDate": (clock[0] + timedelta(days=3)).isoformat(),
            "recordDate": (clock[0] + timedelta(days=2)).isoformat(),
            "dividendNet": {"units": "2", "nano": 0, "currency": "rub"}}]}

    broker_fixture(fixture, read)
    first = dispatch.enqueue_events(fixture["user"], now=clock[0])
    jobs.run_job(first["job_id"])
    assert jobs.get_job(int(fixture["user"]["id"]), first["job_id"])["state"] == "failed"
    first_horizon = state.saved_snapshot(fixture["user"])["operations"]["end"]
    assert len(calls) == 4
    clock[0] += timedelta(seconds=3601)
    generation[0] = 1
    second = dispatch.enqueue_events(fixture["user"], now=clock[0])
    jobs.run_job(second["job_id"])
    assert jobs.get_job(int(fixture["user"]["id"]), second["job_id"])["state"] == "failed"
    current = state.saved_snapshot(fixture["user"])
    assert len(calls) == 8
    assert current["operations"]["end"] > first_horizon
    assert {row["id"] for row in current["operations"]["items"]} == {
        "new-income-owned-account-a", "new-income-owned-account-b"}
    assert current["payouts"]["items"]
    assert current["event_monitor"]["complete"] is False
    assert current["event_monitor"]["news"] == "incomplete"


def test_unfinished_operation_cursor_keeps_original_horizon_during_retry(fixture):
    stored(fixture)
    clock = source_clock(fixture)
    market_sources(fixture, news_available=True)
    fixture["patch"].setattr(workspace, "_payment_events", lambda *args: ([], [], True))
    calls, failing = [], [True]

    def read(method, body):
        assert method == "operations"
        calls.append((body["accountId"], body["cursor"], body["to"]))
        if body["accountId"] == "owned-account-a" and not body["cursor"]:
            return {"items": [], "hasNext": True, "nextCursor": "page-two"}
        if body["accountId"] == "owned-account-a" and failing[0]:
            raise HTTPException(503, "synthetic_page_unavailable")
        return {"items": [], "hasNext": False}

    broker_fixture(fixture, read)
    first = dispatch.enqueue_events(fixture["user"], now=clock[0])
    jobs.run_job(first["job_id"])
    first_horizon = calls[0][2]
    clock[0] += timedelta(seconds=3601)
    failing[0] = False
    second = dispatch.enqueue_events(fixture["user"], now=clock[0])
    jobs.run_job(second["job_id"])
    assert jobs.get_job(int(fixture["user"]["id"]), second["job_id"])["state"] == "completed"
    assert calls.count(("owned-account-a", "", first_horizon)) == 1
    assert calls.count(("owned-account-a", "page-two", first_horizon)) == 2
    assert {row[2] for row in calls} == {first_horizon}
    assert state.saved_snapshot(fixture["user"])["operations"]["end"] == first_horizon
