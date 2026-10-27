"""Authenticated, bounded Android observations; never a trading/job permission.

Only allowlisted codes and application frame symbols are accepted. Payloads are
not logged. Historical process_version may be unknown; capture_version is not
proof of the version that exited. Rows expire on startup or subsequent ingestion.
"""
from __future__ import annotations

from contextlib import closing
import json
import re
import time

from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

try:
    from .ai_budget import transaction
    from .schema_migrations import execute_schema
except ImportError:
    from ai_budget import transaction
    from schema_migrations import execute_schema

MAX_BODY_BYTES = 32 * 1024
MAX_RECORD_BYTES = 4096
MAX_BATCH = 8
MAX_PER_USER = 128
RETENTION_SECONDS = 30 * 24 * 60 * 60
PRIVATE_HEADERS = {"Cache-Control": "no-store, private"}
KINDS = {"historical_exit", "uncaught_exception"}
STAGES = {"process_start", "bootstrap", "login", "workspace", "settings", "background", "unknown"}
EXCEPTIONS = {"security", "argument", "state", "null", "bounds", "memory", "stack", "linkage", "other"}
EVENT_KEYS = {"event_id", "kind", "timestamp_ms", "capture_version", "process_version", "capture_api", "reason", "status", "stage", "exception_code", "frames"}
EVENT_ID = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
CLASS_NAME = re.compile(r"ru\.omnicio\.app\.[A-Za-z_$][A-Za-z0-9_.$]{0,135}\Z", re.ASCII)
METHOD_NAME = re.compile(r"(?:[A-Za-z_$][A-Za-z0-9_$-]{0,95}|<init>|<clinit>)\Z", re.ASCII)


def initialize(connect) -> None:
    # Schema and retention cleanup share one rollback boundary. A refused DELETE
    # or COMMIT must not leave a partially initialized diagnostic registry.
    with transaction(connect) as db:
        execute_schema(db, """
            CREATE TABLE IF NOT EXISTS client_diagnostic_events (
                user_id INTEGER NOT NULL,
                event_id TEXT NOT NULL,
                received_at INTEGER NOT NULL,
                occurred_at_ms INTEGER NOT NULL,
                kind TEXT NOT NULL,
                capture_version INTEGER NOT NULL,
                process_version INTEGER,
                payload_json TEXT NOT NULL,
                PRIMARY KEY (user_id, event_id)
            );
            CREATE INDEX IF NOT EXISTS client_diagnostic_received
                ON client_diagnostic_events(received_at);
            CREATE INDEX IF NOT EXISTS client_diagnostic_user_received
                ON client_diagnostic_events(user_id, received_at);
        """)
        db.execute("DELETE FROM client_diagnostic_events WHERE received_at < ?",
                   (int(time.time()) - RETENTION_SECONDS,))


def _integer(value, low, high):
    return type(value) is int and low <= value <= high


def _member(value, allowed):
    return type(value) is str and value in allowed


def validate_batch(payload, now: int) -> list[dict]:
    """Strict schema deliberately has no free-form message, URL or token field."""
    if type(payload) is not dict or set(payload) != {"schema_version", "events"}:
        raise ValueError("invalid_diagnostic")
    if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
        raise ValueError("invalid_diagnostic")
    events = payload["events"]
    if type(events) is not list or not 1 <= len(events) <= MAX_BATCH:
        raise ValueError("invalid_diagnostic")
    seen = set()
    for event in events:
        if type(event) is not dict or set(event) != EVENT_KEYS:
            raise ValueError("invalid_diagnostic")
        event_id = event["event_id"]
        if type(event_id) is not str or not EVENT_ID.fullmatch(event_id) or event_id in seen:
            raise ValueError("invalid_diagnostic")
        seen.add(event_id)
        if not _member(event["kind"], KINDS) or not _member(event["stage"], STAGES):
            raise ValueError("invalid_diagnostic")
        if not _integer(event["timestamp_ms"], 1577836800000, (now + 86400) * 1000):
            raise ValueError("invalid_diagnostic")
        if not _integer(event["capture_version"], 1, 2147483647) or not _integer(event["capture_api"], 30, 100):
            raise ValueError("invalid_diagnostic")
        if event["process_version"] is not None and not _integer(event["process_version"], 1, 2147483647):
            raise ValueError("invalid_diagnostic")
        frames = event["frames"]
        if type(frames) is not list or len(frames) > 8:
            raise ValueError("invalid_diagnostic")
        for frame in frames:
            if type(frame) is not dict or set(frame) != {"class", "method", "line"}:
                raise ValueError("invalid_diagnostic")
            if (type(frame["class"]) is not str or not CLASS_NAME.fullmatch(frame["class"])
                    or type(frame["method"]) is not str or not METHOD_NAME.fullmatch(frame["method"])
                    or not _integer(frame["line"], -2, 10000000)):
                raise ValueError("invalid_diagnostic")
        if event["kind"] == "historical_exit":
            if (not _integer(event["reason"], 0, 64)
                    or not _integer(event["status"], -2147483648, 2147483647)
                    or event["exception_code"] is not None or frames):
                raise ValueError("invalid_diagnostic")
        elif (event["reason"] is not None or event["status"] is not None
              or event["process_version"] != event["capture_version"]
              or not _member(event["exception_code"], EXCEPTIONS)):
            raise ValueError("invalid_diagnostic")
        if len(json.dumps(event, separators=(",", ":"), sort_keys=True).encode()) > MAX_RECORD_BYTES:
            raise ValueError("invalid_diagnostic")
    return events


def store_batch(connect, user_id: int, events: list[dict], now: int) -> list[str]:
    """The authenticated caller owns the partition; retries never overwrite it."""
    with closing(connect()) as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("DELETE FROM client_diagnostic_events WHERE received_at < ?", (now - RETENTION_SECONDS,))
        for event in events:
            db.execute("""INSERT OR IGNORE INTO client_diagnostic_events
                (user_id,event_id,received_at,occurred_at_ms,kind,capture_version,process_version,payload_json)
                VALUES (?,?,?,?,?,?,?,?)""",
                (user_id, event["event_id"], now, event["timestamp_ms"], event["kind"],
                 event["capture_version"], event["process_version"],
                 json.dumps(event, separators=(",", ":"), sort_keys=True)))
        db.execute("""DELETE FROM client_diagnostic_events WHERE user_id=? AND event_id NOT IN
            (SELECT event_id FROM client_diagnostic_events WHERE user_id=?
             ORDER BY received_at DESC,rowid DESC LIMIT ?)""", (user_id, user_id, MAX_PER_USER))
        db.commit()
    return [event["event_id"] for event in events]


def summarize(connect, user_id: int, now: int | None = None) -> dict:
    """Aggregate observation counts, never claim phone attestation/crash totals."""
    now = int(time.time()) if now is None else now
    with closing(connect()) as db:
        rows = db.execute("""SELECT kind,COUNT(*),MAX(received_at),
            SUM(CASE WHEN process_version IS NULL THEN 1 ELSE 0 END)
            FROM client_diagnostic_events WHERE user_id=? AND received_at>=? GROUP BY kind""",
            (user_id, now - RETENTION_SECONDS)).fetchall()
    counts = {kind: 0 for kind in sorted(KINDS)}
    latest = None
    unknown = 0
    for kind, count, received, unknown_count in rows:
        counts[kind] = count
        latest = received if latest is None else max(latest, received)
        unknown += unknown_count
    return {"observations": sum(counts.values()), "by_kind": counts,
            "unknown_process_version": unknown, "last_received_at": latest,
            "retention_days": 30, "max_records": MAX_PER_USER}


def install_routes(app, require_user, connect) -> None:
    @app.post("/client/diagnostics")
    async def receive(request: Request, user=Depends(require_user)):
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
            raise HTTPException(415, "diagnostic_json_required", headers=PRIVATE_HEADERS)
        raw = bytearray()
        async for chunk in request.stream():
            if len(raw) + len(chunk) > MAX_BODY_BYTES:
                raise HTTPException(413, "diagnostic_too_large", headers=PRIVATE_HEADERS)
            raw.extend(chunk)
        now = int(time.time())
        try:
            events = validate_batch(json.loads(raw), now)
        except (ValueError, TypeError, RecursionError):
            raise HTTPException(422, "invalid_client_diagnostic", headers=PRIVATE_HEADERS) from None
        accepted = await run_in_threadpool(store_batch, connect, int(user["id"]), events, now)
        return JSONResponse({"accepted_ids": accepted}, headers=PRIVATE_HEADERS)

    @app.get("/client/diagnostics/status")
    def status(user=Depends(require_user)):
        return JSONResponse(summarize(connect, int(user["id"])), headers=PRIVATE_HEADERS)
