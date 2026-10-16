"""Connection-bound background work, independent of Android sessions.

Only the encrypted broker-connection fingerprint is retained in this context.
Revocation or replacement prevents subsequent collection, model calls and writes.
Already-sent network requests cannot be recalled; their results are discarded.
"""
from __future__ import annotations

from contextlib import closing, contextmanager
from contextvars import ContextVar
import hashlib
import hmac
import sqlite3

from fastapi import HTTPException

_CONNECTION: ContextVar[tuple[int, bytes] | None] = ContextVar(
    "analyst_monitoring_connection", default=None
)


@contextmanager
def monitoring_connection(user_id: int, encrypted_token: bytes):
    binding = (user_id, hashlib.sha256(encrypted_token).digest())
    marker = _CONNECTION.set(binding)
    try:
        yield
    finally:
        _CONNECTION.reset(marker)


def assert_monitoring_access_in(db: sqlite3.Connection) -> None:
    """Check inside the caller's write transaction before saving private data."""
    binding = _CONNECTION.get()
    if binding is None:
        return  # Interactive callers have their own authenticated request scope.
    user_id, expected = binding
    row = db.execute(
        "SELECT tinvest_token_encrypted FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if row is None or row[0] is None or not hmac.compare_digest(
        hashlib.sha256(row[0]).digest(), expected
    ):
        raise HTTPException(status_code=409, detail="monitoring_connection_changed")


def monitoring_active() -> bool:
    return _CONNECTION.get() is not None


def assert_monitoring_access(connect) -> None:
    if not monitoring_active():
        return
    with closing(connect()) as db:
        assert_monitoring_access_in(db)
