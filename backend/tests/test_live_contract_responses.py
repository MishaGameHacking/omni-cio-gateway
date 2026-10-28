"""Synthetic live-sync failures: no broker, server credentials or financial data."""
import asyncio
import sqlite3
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from backend import app as backend
from backend import volume_live


def test_live_openapi_documents_unavailable_and_bounded_connection_states():
    replies = backend.app.openapi()["paths"]["/workspace/live"]["get"]["responses"]
    for code in ("401", "429", "499", "503"):
        assert replies[code]["description"]


def test_database_failure_preserves_503_and_releases_the_waiter(monkeypatch):
    user_id = 987654321
    def unavailable(*_):
        raise sqlite3.OperationalError("synthetic database failure; not a public detail")
    monkeypatch.setattr(volume_live, "snapshot", unavailable)
    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
    operation = volume_live.live(request, after=None, wait=0,
                                 authorization="Bearer synthetic-test", user={"id": user_id})
    with pytest.raises(HTTPException) as stopped:
        asyncio.run(operation)
    assert stopped.value.status_code == 503
    assert stopped.value.detail == "live_sync_unavailable"
    assert user_id not in volume_live._waiters


def test_disconnect_is_no_store_and_does_not_read_the_database(monkeypatch):
    user_id = 987654322
    def forbidden(*_):
        raise AssertionError("disconnected client must not trigger a revision read")
    monkeypatch.setattr(volume_live, "snapshot", forbidden)
    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=True))
    response = asyncio.run(volume_live.live(request, after=None, wait=0,
        authorization="Bearer synthetic-test", user={"id": user_id}))
    assert response.status_code == 499
    assert response.headers["Cache-Control"] == "no-store"
    assert user_id not in volume_live._waiters
