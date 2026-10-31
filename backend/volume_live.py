"""Authenticated live invalidation; no broker/model calls or financial payloads.

SQLite triggers change opaque stamps in the same transaction as visible data.
A bounded long poll wakes within 500 ms of a commit; reconnecting compares the
latest durable stamp, so there is no lossy in-memory event queue to replay.
"""
from __future__ import annotations

import asyncio
from contextlib import closing, contextmanager
from datetime import datetime, timezone
import hashlib
import os
import re
import sqlite3
import threading
import time
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse

try:
    from . import app as backend, research_store, server_version, volume_presentation, osint_store, osint_api
except ImportError:
    import app as backend
    import research_store
    import server_version
    import volume_presentation
    import osint_store
    import osint_api

router = APIRouter(prefix="/workspace", tags=["Live data"])
router.include_router(volume_presentation.router)
router.include_router(osint_api.router)
POLL_INTERVAL = .5
USER_TABLES = (
    "workspace_presentation_preferences",
    "workspace_snapshots", "workspace_records", "workspace_strategy_versions",
    "workspace_events", "workspace_chat_threads", "workspace_chat_messages",
    "workspace_notification_preferences", "workspace_notification_outbox",
    "workspace_plan_operations", "workspace_analysis_facts", "workspace_jobs",
    "ai_work_jobs", "analysis_profiles", "analysis_runs", "insight_cards",
    "portfolio_snapshots", "analysis_budget_usage", "ai_money_reservations",
    "broker_connection_versions",
    "automation_preferences", "automation_observations",
    "automation_discovery", "automation_events", "portfolio_decision_cycles",
)
GLOBAL_TABLES = ("market_facts", "research_revision_v1", "osint_revision_v1")
_waiters: dict[int, int] = {}
_waiter_lock = threading.Lock()


def deployment_signature() -> str:
    digest = hashlib.sha256()
    digest.update(server_version.SOURCE_REVISION.encode("ascii"))
    for name in sorted(os.environ):
        if name.startswith("AI_") and not name.endswith(("_SECRET", "_KEY", "_TOKEN")):
            digest.update(name.encode() + b"\0" + os.environ[name].encode() + b"\0")
    digest.update(hashlib.sha256(os.environ.get("TIMEWEB_AI_TOKEN", "").encode()).digest())
    return digest.hexdigest()


DEPLOYMENT = deployment_signature()


def initialize(connect=None) -> None:
    connect = backend.connect if connect is None else connect
    volume_presentation.initialize(connect)
    osint_store.initialize(connect)
    with closing(connect()) as db:
        # Reviewed evidence already has its own durable revision.
        research_store.initialize(db)
        db.execute("BEGIN IMMEDIATE")
        db.execute("""CREATE TABLE IF NOT EXISTS workspace_live_versions (
            user_id INTEGER PRIMARY KEY CHECK(user_id>0),
            stamp TEXT NOT NULL CHECK(length(stamp)=64 AND stamp NOT GLOB '*[^0-9a-f]*'))""")
        db.execute("""CREATE TABLE IF NOT EXISTS workspace_live_global (
            singleton INTEGER PRIMARY KEY CHECK(singleton=1),
            stamp TEXT NOT NULL CHECK(length(stamp)=64 AND stamp NOT GLOB '*[^0-9a-f]*'))""")
        db.execute("INSERT OR IGNORE INTO workspace_live_global VALUES (1,lower(hex(randomblob(32))))")
        existing = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table in USER_TABLES + GLOBAL_TABLES:
            if table not in existing:
                continue
            columns = [row[1] for row in db.execute('PRAGMA table_info("' + table + '")')]
            if table in USER_TABLES and "user_id" not in columns:
                raise RuntimeError("live_table_has_no_owner:" + table)
            if not all(re.fullmatch(r"[a-z_][a-z0-9_]*", name) for name in columns):
                raise RuntimeError("live_table_column_invalid")
            for operation in ("INSERT", "UPDATE", "DELETE"):
                trigger = "live_v1_" + table + "_" + operation.lower()
                owners = ("1",) if table in GLOBAL_TABLES else (
                    ("NEW.user_id", "OLD.user_id") if operation == "UPDATE"
                    else ("OLD.user_id",) if operation == "DELETE" else ("NEW.user_id",))
                when = ""
                if operation == "UPDATE":
                    when = " WHEN " + " OR ".join('OLD."' + col + '" IS NOT NEW."' + col + '"' for col in columns)
                version_table, identity = ("workspace_live_global", "singleton") if table in GLOBAL_TABLES else ("workspace_live_versions", "user_id")
                statements = "".join(
                    "INSERT INTO " + version_table + "(" + identity + ",stamp) VALUES (" + owner +
                    ",lower(hex(randomblob(32)))) ON CONFLICT(" + identity + ") DO UPDATE SET stamp=excluded.stamp;"
                    for owner in owners)
                sql = "CREATE TRIGGER " + trigger + " AFTER " + operation + " ON " + table + when + " BEGIN " + statements + " END"
                installed = db.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?", (trigger,)).fetchone()
                if installed is None or installed[0] != sql:
                    db.execute("DROP TRIGGER IF EXISTS " + trigger)
                    db.execute(sql)
        db.commit()


def snapshot(user_id: int, token_hash: str, connect=None) -> dict:
    connect = backend.connect if connect is None else connect
    with closing(connect()) as db:
        db.execute("BEGIN")
        user = db.execute("""SELECT CASE WHEN u.tinvest_token_encrypted IS NOT NULL
                AND length(u.tinvest_token_encrypted)>0 THEN 1 ELSE 0 END
            FROM sessions s JOIN users u ON u.id=s.user_id
            WHERE s.token_hash=? AND s.user_id=? AND s.expires_at>=?""",
            (token_hash, user_id, int(time.time()))).fetchone()
        if user is None:
            raise HTTPException(401, "invalid_session")
        global_stamp = db.execute("SELECT stamp FROM workspace_live_global WHERE singleton=1").fetchone()
        own_stamp = db.execute("SELECT stamp FROM workspace_live_versions WHERE user_id=?", (user_id,)).fetchone()
        if global_stamp is None:
            raise RuntimeError("live_revision_missing")
        broker = db.execute("SELECT stamp FROM broker_connection_versions WHERE user_id=?", (user_id,)).fetchone()
        broker_revision = hashlib.sha256(("broker:" + (broker[0] if broker else "")).encode()).hexdigest()
        source = DEPLOYMENT + ":" + str(user_id) + ":" + global_stamp[0] + ":" + (own_stamp[0] if own_stamp else "")
        return {"revision": hashlib.sha256(source.encode()).hexdigest(),
                "broker_revision": broker_revision, "broker_connected": bool(user[0])}


@contextmanager
def watcher(user_id: int):
    with _waiter_lock:
        if _waiters.get(user_id, 0) >= 3 or sum(_waiters.values()) >= 24:
            raise HTTPException(429, "live_connection_limit", headers={"Retry-After": "5"})
        _waiters[user_id] = _waiters.get(user_id, 0) + 1
    try:
        yield
    finally:
        with _waiter_lock:
            remaining = _waiters[user_id] - 1
            if remaining:
                _waiters[user_id] = remaining
            else:
                _waiters.pop(user_id, None)


@router.get("/live")
async def live(request: Request, after: str | None = Query(default=None, pattern=r"^[a-f0-9]{64}$"),
               wait: int = Query(default=20, ge=0, le=20),
               authorization: str | None = Header(default=None),
               user: Any = Depends(backend.current_user)):
    user_id = int(user["id"])
    # The dependency enforces current app/session policy. Recheck session
    # revocation and expiry on every wait iteration without changing last_seen.
    token_hash = backend.hash_token((authorization or "")[7:].strip())
    deadline = time.monotonic() + wait
    with watcher(user_id):
        while True:
            if await request.is_disconnected():
                return JSONResponse({}, status_code=499, headers={"Cache-Control": "no-store"})
            try:
                current = await asyncio.to_thread(snapshot, user_id, token_hash)
            except sqlite3.Error:
                raise HTTPException(503, "live_sync_unavailable") from None
            if current["revision"] != after or time.monotonic() >= deadline:
                return JSONResponse({**current, "changed": current["revision"] != after,
                    "server_time": datetime.now(timezone.utc).isoformat()},
                    headers={"Cache-Control": "no-store", "ETag": '"' + current["revision"] + '"'})
            await asyncio.sleep(min(POLL_INTERVAL, max(0, deadline - time.monotonic())))


@router.get("/version")
def version(user: Any = Depends(backend.current_user)):
    """Authenticated code identity; this read never starts background work."""
    return JSONResponse(server_version.current(), headers={"Cache-Control": "no-store, private"})
