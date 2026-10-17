"""Opaque, user-scoped session devices; migrations preserve existing sessions."""
from contextlib import closing
from datetime import datetime, timezone
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException

try:
    from . import app as backend
    from .ai_budget import transaction
except ImportError:
    import app as backend
    from ai_budget import transaction

try:
    from .volume_contract import HTTP_ERRORS
except ImportError:
    from volume_contract import HTTP_ERRORS

router = APIRouter(prefix="/workspace/devices", tags=["Session devices"])


def migrate(db) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS workspace_session_devices (
        token_hash TEXT PRIMARY KEY, device_id TEXT NOT NULL UNIQUE,
        device_name TEXT NOT NULL, created_at INTEGER NOT NULL,last_seen_at INTEGER NOT NULL)""")
    now = int(time.time())
    db.execute("DELETE FROM workspace_session_devices WHERE token_hash NOT IN (SELECT token_hash FROM sessions)")
    for row in db.execute("SELECT token_hash,expires_at FROM sessions WHERE token_hash NOT IN (SELECT token_hash FROM workspace_session_devices)").fetchall():
        created = min(now, max(0, row["expires_at"] - backend.SESSION_TTL))
        db.execute("INSERT INTO workspace_session_devices VALUES (?,?,'Ранее подключённое устройство',?,?)",
                   (row["token_hash"], uuid.uuid4().hex, created, created))


def _iso(value: int | None) -> str | None:
    return datetime.fromtimestamp(value, timezone.utc).isoformat() if value is not None else None


@router.get("", responses=HTTP_ERRORS)
def devices(user: Any = Depends(backend.current_user), authorization: str | None = Header(default=None)) -> dict:
    current_hash = backend.hash_token((authorization or "")[7:].strip())
    with transaction(backend.connect) as db:
        migrate(db)
        rows = db.execute("SELECT s.token_hash,s.expires_at,d.* FROM sessions s JOIN workspace_session_devices d ON d.token_hash=s.token_hash WHERE s.user_id=? AND s.expires_at>=? ORDER BY d.last_seen_at DESC,d.device_id", (int(user["id"]), int(time.time()))).fetchall()
    current = next((row["device_id"] for row in rows if row["token_hash"] == current_hash), None)
    return {"items": [{"id": row["device_id"], "label": row["device_name"], "created_at": _iso(row["created_at"]),
                       "last_seen_at": _iso(row["last_seen_at"]), "expires_at": _iso(row["expires_at"]),
                       "current": row["device_id"] == current} for row in rows], "current_device_id": current}


@router.delete("/{identifier}", responses=HTTP_ERRORS)
def revoke(identifier: str, user: Any = Depends(backend.current_user)) -> dict:
    with transaction(backend.connect) as db:
        # Idempotent acknowledgement never reveals another user's device.
        rows = db.execute("SELECT s.token_hash FROM sessions s JOIN workspace_session_devices d ON d.token_hash=s.token_hash WHERE d.device_id=? AND s.user_id=?", (identifier, int(user["id"]))).fetchall()
        for row in rows:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (row[0],))
            db.execute("DELETE FROM workspace_session_devices WHERE token_hash=?", (row[0],))
    return {"id": identifier, "revoked": True, "revoked_at": _iso(int(time.time()))}
