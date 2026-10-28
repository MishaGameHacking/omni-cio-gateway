"""Synthetic persisted broker window for existing real-scheduler regressions."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from backend import volume_workspace as workspace, volume_monitor as monitor
from backend.volume_contract import digest, section, source
from backend.tests.test_autonomous_ai import sample_snapshot


@contextmanager
def open_dispatch_market(*users, now=None):
    clock = now or datetime.now(timezone.utc)
    observed = (clock - timedelta(seconds=1)).isoformat()
    calendar = {"timezone": "UTC", "as_of": observed,
        "source": source("TradingSchedules", "synthetic-scheduler-calendar", observed, ttl=900),
        "exchanges": [{"exchange": "MOEX", "days": [{"date": clock.isoformat(), "isTradingDay": True,
            "startTime": (clock - timedelta(hours=1)).isoformat(), "endTime": (clock + timedelta(hours=1)).isoformat()}]}]}
    for user in users:
        raw = sample_snapshot()
        raw["asOf"] = (clock - timedelta(seconds=600)).isoformat()
        for account in raw["accounts"]:
            for position in account["positions"]:
                position["instrumentType"] = "cash" if position["id"].startswith("cash:") else "share"
        snapshot = workspace.normalize_snapshot(user, raw)
        for position in snapshot["positions"]:
            if position["instrument_type"] in {"share", "bond"}:
                position["metadata"]["exchange"] = "MOEX"
        snapshot.update(snapshot_id=digest({"fixture": "open-dispatch", "user": int(user["id"]), "as_of": raw["asOf"]}),
            calendar=section(calendar, as_of=observed, sources=[calendar["source"]]),
            collection={"finished_at": observed},
            event_monitor={"checked_at": observed, "last_successful_at": observed, "complete": True})
        workspace.persist(user, snapshot)
    # Real analysis also enriches a previously configured workspace. Keep that
    # broker calendar read synthetic instead of permitting a network request.
    with patch.object(monitor.market, "calendar", return_value=calendar):
        yield
