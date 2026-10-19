"""Fence broker credential changes across network waits and session revocation.

The database stamp is an internal change marker, not an authentication token.
Even NULL -> NULL disconnects change it; comparing ciphertext or second-resolution
updated_at alone cannot detect that ABA case. Network work stays outside write
transactions. No broker operation, retry, encryption key or raw token is stored
in a change ticket. Existing users and encrypted credentials are preserved.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass, field
import hashlib
import sqlite3
import time
from typing import Callable

Connect = Callable[[], sqlite3.Connection]
MAX_TOKEN_CHARACTERS = 4096
BEGIN_WRITE = "BEGIN IMMEDIATE"


class ConnectionChangeError(RuntimeError):
    """A fixed public diagnostic without credential or upstream response data."""

    def __init__(self, code: str, status_code: int):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def validated_token(value: str) -> str:
    """Reject invalid HTTP header values before TLS setup or a broker request."""
    if not isinstance(value, str) or len(value) > MAX_TOKEN_CHARACTERS:
        raise ConnectionChangeError("invalid_tinvest_token_format", 400)
    token = value.strip()
    if not token:
        raise ConnectionChangeError("empty_tinvest_token", 400)
    if not token.isascii() or any(not 33 <= ord(c) <= 126 for c in token):
        raise ConnectionChangeError("invalid_tinvest_token_format", 400)
    return token


def initialize(connect: Connect) -> None:
    """Atomic, idempotent migration; trigger all credential writes, not logins."""
    with closing(connect()) as db:
        db.execute(BEGIN_WRITE)
        db.execute("""
            CREATE TABLE IF NOT EXISTS broker_connection_versions (
                user_id INTEGER PRIMARY KEY,
                stamp TEXT NOT NULL CHECK (
                    typeof(stamp) = 'text' AND length(stamp) = 64
                    AND stamp NOT GLOB '*[^0-9a-f]*'
                )
            )
        """)
        # SQL identifiers/events below are fixed source constants, never input.
        # randomblob creates a version identity, not a secret granting access.
        for name, event in (
            ("broker_connection_user_insert", "INSERT"),
            ("broker_connection_token_update", "UPDATE OF tinvest_token_encrypted"),
        ):
            db.execute(f"""
                CREATE TRIGGER IF NOT EXISTS {name} AFTER {event} ON users
                BEGIN
                    INSERT INTO broker_connection_versions(user_id, stamp)
                    VALUES (NEW.id, lower(hex(randomblob(32))))
                    ON CONFLICT(user_id) DO UPDATE SET stamp = excluded.stamp;
                END
            """)
        db.execute("""
            CREATE TRIGGER IF NOT EXISTS broker_connection_user_delete
            AFTER DELETE ON users
            BEGIN
                DELETE FROM broker_connection_versions WHERE user_id = OLD.id;
            END
        """)
        db.execute("""
            INSERT OR IGNORE INTO broker_connection_versions(user_id, stamp)
            SELECT id, lower(hex(randomblob(32))) FROM users
        """)
        db.commit()


def _session_hash(authorization: str | None) -> str:
    if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
        raise ConnectionChangeError("invalid_session", 401)
    token = authorization[7:].strip()
    if not token or len(token) > MAX_TOKEN_CHARACTERS or not token.isascii():
        raise ConnectionChangeError("invalid_session", 401)
    return hashlib.sha256(token.encode("ascii")).hexdigest()


@dataclass(frozen=True)
class ConnectionChange:
    user_id: int
    subject: str = field(repr=False)
    stamp: str = field(repr=False)
    session_hash: str = field(repr=False)


def _current_change(db: sqlite3.Connection, user_id: int, session_hash: str) -> ConnectionChange:
    if type(user_id) is not int or user_id <= 0:
        raise ConnectionChangeError("invalid_session", 401)
    # Compute time after the caller acquired its write reservation, not before a
    # possible lock wait. The credential and authorizing session are user-bound.
    row = db.execute("""
        SELECT users.telegram_sub, versions.stamp
        FROM users JOIN sessions ON sessions.user_id = users.id
        LEFT JOIN broker_connection_versions AS versions ON versions.user_id = users.id
        WHERE users.id = ? AND sessions.token_hash = ? AND sessions.expires_at > ?
    """, (user_id, session_hash, int(time.time()))).fetchone()
    if row is None:
        raise ConnectionChangeError("invalid_session", 401)
    if row[1] is None:
        raise ConnectionChangeError("tinvest_connection_version_missing", 503)
    return ConnectionChange(user_id, row[0], row[1], session_hash)


def begin_change(connect: Connect, user_id: int, authorization: str | None) -> ConnectionChange:
    """Capture a live session and version before sending the read-only request."""
    digest = _session_hash(authorization)
    with closing(connect()) as db:
        return _current_change(db, user_id, digest)


def commit_change(connect: Connect, change: ConnectionChange, encrypted_token: bytes) -> None:
    """Publish once only if the connection and its authorizing session survived."""
    if not isinstance(change, ConnectionChange):
        raise ValueError("invalid_connection_change")
    if not isinstance(encrypted_token, bytes) or not 1 <= len(encrypted_token) <= 16_384:
        raise ValueError("invalid_encrypted_broker_token")
    with closing(connect()) as db:
        db.execute(BEGIN_WRITE)
        current = _current_change(db, change.user_id, change.session_hash)
        if current != change:
            raise ConnectionChangeError("tinvest_connection_changed", 409)
        db.execute("UPDATE users SET tinvest_token_encrypted = ?, updated_at = ? WHERE id = ?",
                   (encrypted_token, int(time.time()), change.user_id))
        db.commit()


def disconnect(connect: Connect, user_id: int, authorization: str | None) -> None:
    """An explicit disconnect invalidates pending changes even if already NULL."""
    digest = _session_hash(authorization)
    with closing(connect()) as db:
        db.execute(BEGIN_WRITE)
        _current_change(db, user_id, digest)
        db.execute("UPDATE users SET tinvest_token_encrypted = NULL, updated_at = ? WHERE id = ?",
                   (int(time.time()), user_id))
        db.commit()
