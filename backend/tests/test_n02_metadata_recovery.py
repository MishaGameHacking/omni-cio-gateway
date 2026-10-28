"""A failed instrument lookup must not permanently disable automatic polling."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend import app as backend
from backend import autonomous_ai as ai, background_dispatch as dispatch, event_monitor, market_schedule
from backend import volume_jobs as jobs, volume_state as state, volume_workspace as workspace
from backend import volume_monitor as monitor
from backend.tests.test_background_dispatch import stored, event_sources, forbidden
from backend.tests.test_volume_workspace import fixture
from backend.volume_contract import now_iso, source


def missing_exchange(fixture):
    snapshot = stored(fixture, open_window=True)
    target = next(row for row in snapshot["positions"] if row["instrument_type"] == "share")
    target["metadata"].pop("exchange", None)
    workspace.persist(fixture["user"], snapshot)
    return state.saved_snapshot(fixture["user"]), target["instrument_uid"]


def recovered_instrument(uid):
    return {"uid": uid, "exchange": "MOEX",
            "_source": source("GetInstrumentBy", uid, now_iso(), ttl=86400)}


def test_missing_exchange_recovers_in_event_lane_without_refreshing_valuation(fixture):
    old, uid = missing_exchange(fixture)
    assert dispatch.schedule(fixture["user"])["reason"] == "instrument_exchange_unknown"
    event_sources(fixture)
    fixture["patch"].setattr(workspace.details, "load_dashboard", forbidden)
    fixture["patch"].setattr(ai, "get_tinvest_portfolio", forbidden)
    calls = []

    def read(user, identifier):
        calls.append(identifier)
        return recovered_instrument(identifier)

    fixture["patch"].setattr(workspace.market, "instrument", read)
    job = dispatch.enqueue_events(fixture["user"])
    jobs.run_job(job["job_id"])
    assert calls == [uid]
    assert jobs.get_job(int(fixture["user"]["id"]), job["job_id"])["state"] == "completed"
    current = state.saved_snapshot(fixture["user"])
    for name in ("as_of", "capital", "accounts", "collection", "attribution"):
        assert current[name] == old[name]
    for prior, present in zip(old["positions"], current["positions"]):
        assert {key: value for key, value in present.items() if key != "metadata"} == {
            key: value for key, value in prior.items() if key != "metadata"}
    repaired = next(row for row in current["positions"] if row["instrument_uid"] == uid)
    assert repaired["metadata"]["exchange"] == "MOEX"
    assert repaired["metadata"]["exchange_source"]["id"] in {ref["id"] for ref in current["sources"]}
    prior_metadata = next(row["metadata"] for row in old["positions"] if row["instrument_uid"] == uid)
    assert {key: value for key, value in repaired["metadata"].items() if key not in {"exchange", "exchange_source"}} == prior_metadata
    assert current["snapshot_id"] != old["snapshot_id"]
    assert dispatch.schedule(fixture["user"])["regular_price_polling_allowed"] is True
    previous = {(row["account_id"], row["instrument_uid"]): row for row in current["positions"]}
    _, metadata = monitor._monitor_accounts(fixture["dashboard"], previous)
    later = workspace.normalize_snapshot(fixture["user"], fixture["dashboard"], metadata)
    retained = next(row for row in later["positions"] if row["instrument_uid"] == uid)
    assert retained["metadata"]["exchange_source"] == repaired["metadata"]["exchange_source"]


def test_unavailable_metadata_does_not_open_polling_or_discard_successful_events(fixture):
    old, uid = missing_exchange(fixture)
    event_sources(fixture)
    fixture["patch"].setattr(workspace.details, "load_dashboard", forbidden)

    def unavailable(user, identifier):
        assert identifier == uid
        raise HTTPException(503, "synthetic_instrument_unavailable")

    fixture["patch"].setattr(workspace.market, "instrument", unavailable)
    job = dispatch.enqueue_events(fixture["user"])
    jobs.run_job(job["job_id"])
    result = jobs.get_job(int(fixture["user"]["id"]), job["job_id"])
    assert result["state"] == "failed"
    current = state.saved_snapshot(fixture["user"])
    assert current["positions"] == old["positions"]
    assert current["events"]["items"][0]["id"] == "new-synthetic-news"
    assert current["event_monitor"]["complete"] is False
    assert dispatch.schedule(fixture["user"])["regular_price_polling_allowed"] is False
    assert dispatch.enqueue_events(fixture["user"]) == {"state": "current"}


def test_bounded_metadata_retries_survive_changed_holdings_without_starving_later_instruments(fixture):
    old = stored(fixture, open_window=True)
    template = next(row for row in old["positions"] if row["instrument_type"] == "share")
    old["positions"] = []
    for index in range(7):
        row = deepcopy(template)
        row["instrument_uid"] = "retry-" + str(index).zfill(2)
        row["metadata"].pop("exchange", None)
        old["positions"].append(row)
    workspace.persist(fixture["user"], old)
    event_sources(fixture)
    calls = []

    def read(user, identifier):
        calls.append(identifier)
        if int(identifier[-2:]) < 3:
            raise HTTPException(503, "synthetic_permanently_unavailable")
        return recovered_instrument(identifier)

    fixture["patch"].setattr(workspace.market, "instrument", read)
    first = dispatch.enqueue_events(fixture["user"])
    jobs.run_job(first["job_id"])
    assert len(calls) == 5
    assert jobs.get_job(int(fixture["user"]["id"]), first["job_id"])["state"] == "failed"
    changed = state.saved_snapshot(fixture["user"])
    changed["positions"][0]["quantity"] = "2"
    workspace.persist(fixture["user"], changed)
    second = dispatch.enqueue_events(fixture["user"], now=datetime.now(timezone.utc) + timedelta(seconds=601))
    jobs.run_job(second["job_id"])
    assert calls[5:7] == ["retry-05", "retry-06"]
    current = state.saved_snapshot(fixture["user"])
    assert all(row["metadata"].get("exchange") == "MOEX" for row in current["positions"] if int(row["instrument_uid"][-2:]) >= 3)
    assert current["event_monitor"]["complete"] is False
    assert dispatch.schedule(fixture["user"])["regular_price_polling_allowed"] is False


@pytest.mark.parametrize("exchange", [None, "", " ", " MOEX ", "x" * 101])
def test_metadata_response_without_valid_exchange_never_guesses_moex(fixture, exchange):
    old, uid = missing_exchange(fixture)
    event_sources(fixture)
    fixture["patch"].setattr(workspace.market, "instrument", lambda user, identifier: {"uid": identifier, "exchange": exchange})
    job = dispatch.enqueue_events(fixture["user"])
    jobs.run_job(job["job_id"])
    assert jobs.get_job(int(fixture["user"]["id"]), job["job_id"])["state"] == "failed"
    current = state.saved_snapshot(fixture["user"])
    assert current["positions"] == old["positions"]
    assert dispatch.schedule(fixture["user"])["reason"] == "instrument_exchange_unknown"
    assert market_schedule.required_exchanges({"positions": [{"instrument_type": "share", "metadata": {"exchange": exchange}}]}) == ()


def test_metadata_budget_stops_scheduling_after_a_slow_source(fixture):
    old = stored(fixture)
    for row in old["positions"]:
        if row["instrument_type"] == "share":
            row["metadata"].pop("exchange", None)
    workspace.persist(fixture["user"], old)
    event_sources(fixture)
    elapsed, calls = [0.0], []
    fixture["patch"].setattr(event_monitor, "time", SimpleNamespace(monotonic=lambda: elapsed[0]), raising=False)

    def read(user, uid):
        calls.append(uid)
        elapsed[0] += 20
        return recovered_instrument(uid)

    fixture["patch"].setattr(workspace.market, "instrument", read)
    item = dispatch.enqueue_events(fixture["user"])
    jobs.run_job(item["job_id"])
    assert len(calls) == 1
    assert jobs.get_job(int(fixture["user"]["id"]), item["job_id"])["state"] == "failed"
    assert state.saved_snapshot(fixture["user"])["event_monitor"]["complete"] is False
