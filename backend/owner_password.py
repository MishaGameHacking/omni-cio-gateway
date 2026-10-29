"""Single-owner password credentials over the existing opaque session store.

No public signup and no identity replacement. Enrollment needs an existing owner
session or a separately provisioned bootstrap secret. A password never leaves
the request as plaintext and is never stored in the database or audit events.
"""
from __future__ import annotations

from contextlib import closing, contextmanager
import hashlib
import hmac
import secrets
import time
from typing import Callable

MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_BYTES = 128
MAX_FAILURES = 5
LOCK_SECONDS = 15 * 60
PASSWORD_SCHEME = "scrypt-n32768-r8-p3-v1"


class OwnerAuthError(Exception):
    def __init__(self, code: str, status: int, retry_after: int | None = None):
        super().__init__(code)
        self.code, self.status, self.retry_after = code, status, retry_after


def password_bytes(password: str, *, new: bool = False) -> bytes:
    if not isinstance(password, str):
        raise OwnerAuthError("owner_password_invalid", 422)
    try:
        value = password.encode("utf-8")
    except UnicodeError as exc:
        raise OwnerAuthError("owner_password_invalid", 422) from exc
    if len(value) > MAX_PASSWORD_BYTES:
        raise OwnerAuthError("owner_password_invalid", 422)
    if new and (len(password) < MIN_PASSWORD_LENGTH or not password.isprintable()
                or not password.strip()):
        raise OwnerAuthError("owner_password_invalid", 422)
    return value


def _derive(password: bytes, salt: bytes) -> bytes:
    return hashlib.scrypt(password, salt=salt, n=32768, r=8, p=3,
                          maxmem=64 * 1024 * 1024, dklen=32)


def _hash_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def initialize(connect: Callable) -> None:
    """Atomic migration. Existing user IDs, portfolios and broker secrets stay put."""
    with closing(connect()) as db:
        try:
            db.execute("BEGIN IMMEDIATE")
            db.execute("""CREATE TABLE IF NOT EXISTS owner_password_credentials (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                user_id INTEGER NOT NULL UNIQUE, salt BLOB NOT NULL,
                password_hash BLOB NOT NULL, scheme TEXT NOT NULL,
                configured_at INTEGER NOT NULL, updated_at INTEGER NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS owner_password_attempts (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                failures INTEGER NOT NULL, window_start INTEGER NOT NULL,
                locked_until INTEGER NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS owner_password_sessions (
                token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
                created_at INTEGER NOT NULL)""")
            # Cover in-flight legacy callbacks/exchanges that began before
            # enrollment. HTTP routing alone does not close that race.
            db.execute("""CREATE TRIGGER IF NOT EXISTS owner_password_legacy_codes
                BEFORE INSERT ON login_codes
                WHEN EXISTS (SELECT 1 FROM owner_password_credentials)
                BEGIN SELECT RAISE(ABORT, 'owner_password_login_required'); END""")
            db.execute("""CREATE TRIGGER IF NOT EXISTS owner_password_session_guard
                BEFORE INSERT ON sessions
                WHEN EXISTS (SELECT 1 FROM owner_password_credentials)
                AND NOT EXISTS (SELECT 1 FROM owner_password_sessions
                    WHERE token_hash=NEW.token_hash AND user_id=NEW.user_id)
                BEGIN SELECT RAISE(ABORT, 'owner_password_login_required'); END""")
            db.execute("""CREATE TRIGGER IF NOT EXISTS owner_password_session_cleanup
                AFTER DELETE ON sessions
                BEGIN DELETE FROM owner_password_sessions WHERE token_hash=OLD.token_hash; END""")
            db.commit()
        except BaseException:
            db.rollback()
            raise


class OwnerPasswordStore:
    def __init__(self, connect: Callable, *, session_ttl: int,
                 bootstrap_secret: Callable[[], str] = lambda: "",
                 clock: Callable[[], float] = time.time):
        self.connect = connect
        self.session_ttl = session_ttl
        self.bootstrap_secret = bootstrap_secret
        self.clock = clock

    @contextmanager
    def _transaction(self):
        with closing(self.connect()) as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    def configured(self) -> bool:
        with closing(self.connect()) as db:
            return db.execute("SELECT 1 FROM owner_password_credentials").fetchone() is not None

    def status(self) -> dict:
        return {"configured": self.configured(), "method": "password",
                "setup_requires": "existing_owner_session_or_bootstrap",
                "min_password_length": MIN_PASSWORD_LENGTH,
                "max_password_bytes": MAX_PASSWORD_BYTES}

    @staticmethod
    def _device_name(value: str | None) -> str:
        if value is None:
            return "Android"
        if not isinstance(value, str) or len(value) > 100 or not value.isprintable():
            raise OwnerAuthError("invalid_device_name", 422)
        return value.strip() or "Android"

    @staticmethod
    def _check_throttle(db, now: int) -> None:
        row = db.execute("SELECT locked_until FROM owner_password_attempts WHERE singleton=1").fetchone()
        if row and int(row[0]) > now:
            raise OwnerAuthError("owner_auth_throttled", 429, int(row[0]) - now)

    @staticmethod
    def _failed(db, now: int) -> None:
        row = db.execute("SELECT failures,window_start FROM owner_password_attempts WHERE singleton=1").fetchone()
        failures = int(row[0]) + 1 if row and now - int(row[1]) < LOCK_SECONDS else 1
        started = int(row[1]) if row and now - int(row[1]) < LOCK_SECONDS else now
        locked = now + LOCK_SECONDS if failures >= MAX_FAILURES else 0
        db.execute("INSERT OR REPLACE INTO owner_password_attempts VALUES (1,?,?,?)",
                   (failures, started, locked))
        # An authentication denial must survive rollback of its HTTP request.
        # No other mutations precede this function in any authentication flow.
        db.commit()
        if locked:
            raise OwnerAuthError("owner_auth_throttled", 429, LOCK_SECONDS)
        raise OwnerAuthError("owner_credentials_invalid", 401)

    @staticmethod
    def _owner(db):
        rows = db.execute("""SELECT users.* FROM users JOIN installation_owner
            ON users.telegram_sub=installation_owner.telegram_sub WHERE singleton=1""").fetchall()
        if len(rows) != 1:
            raise OwnerAuthError("owner_installation_not_ready", 503)
        return rows[0]

    @staticmethod
    def _session_owner(db, authorization: str | None, now: int):
        if not authorization or not authorization.startswith("Bearer "):
            return None
        token = authorization[7:].strip()
        if not token or len(token) > 512:
            return None
        return db.execute("""SELECT users.* FROM sessions JOIN users ON users.id=sessions.user_id
            JOIN workspace_session_devices ON workspace_session_devices.token_hash=sessions.token_hash
            JOIN installation_owner ON users.telegram_sub=installation_owner.telegram_sub
            WHERE sessions.token_hash=? AND sessions.expires_at>=? AND singleton=1""",
                          (_hash_token(token), now)).fetchone()

    def _bootstrap_valid(self, supplied: str | None) -> bool:
        expected = self.bootstrap_secret()
        if not isinstance(expected, str) or len(expected) < 32 or len(expected) > 512:
            return False
        if not isinstance(supplied, str) or len(supplied) > 512:
            return False
        return hmac.compare_digest(_hash_token(expected), _hash_token(supplied))

    @staticmethod
    def _bootstrap_owner(db, now: int):
        if db.execute("SELECT 1 FROM users").fetchone() is None:
            row = db.execute("SELECT telegram_sub FROM installation_owner WHERE singleton=1").fetchone()
            if row is None:
                raise OwnerAuthError("owner_installation_not_ready", 503)
            db.execute("""INSERT INTO users(telegram_sub,telegram_id,name,created_at,updated_at)
                VALUES (?,?,'Владелец',?,?)""", (row[0], row[0], now, now))
        return OwnerPasswordStore._owner(db)

    @staticmethod
    def _clear_sessions(db, user_id: int) -> None:
        db.execute("DELETE FROM workspace_session_devices WHERE token_hash IN (SELECT token_hash FROM sessions WHERE user_id=?)", (user_id,))
        db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        db.execute("DELETE FROM owner_password_sessions WHERE user_id=?", (user_id,))
        db.execute("DELETE FROM login_codes WHERE user_id=?", (user_id,))
        db.execute("DELETE FROM login_transactions")

    def _grant(self, db, user, device_name: str, now: int) -> dict:
        session, device_id = secrets.token_urlsafe(48), secrets.token_hex(16)
        token_hash, user_id = _hash_token(session), int(user["id"])
        db.execute("INSERT INTO owner_password_sessions VALUES (?,?,?)", (token_hash, user_id, now))
        db.execute("INSERT INTO sessions(token_hash,user_id,expires_at) VALUES (?,?,?)",
                   (token_hash, user_id, now + self.session_ttl))
        db.execute("INSERT INTO workspace_session_devices VALUES (?,?,?,?,?)",
                   (token_hash, device_id, device_name, now, now))
        db.execute("DELETE FROM owner_password_attempts")
        return {"access_token": session, "expires_in": self.session_ttl, "device_id": device_id,
                "user": {"telegram_id": str(user["telegram_id"] or user["telegram_sub"]),
                         "name": user["name"], "username": user["username"], "picture": user["picture"]}}

    def setup(self, password: str, *, authorization: str | None = None,
              bootstrap: str | None = None, device_name: str | None = None) -> dict:
        value, device = password_bytes(password, new=True), self._device_name(device_name)
        now = int(self.clock())
        with self._transaction() as db:
            self._check_throttle(db, now)
            if db.execute("SELECT 1 FROM owner_password_credentials").fetchone():
                raise OwnerAuthError("owner_password_already_configured", 409)
            user = self._session_owner(db, authorization, now)
            if user is None:
                if not self._bootstrap_valid(bootstrap):
                    self._failed(db, now)
                user = self._bootstrap_owner(db, now)
            salt = secrets.token_bytes(16)
            db.execute("INSERT INTO owner_password_credentials VALUES (1,?,?,?,?,?,?)",
                       (int(user["id"]), salt, _derive(value, salt), PASSWORD_SCHEME, now, now))
            self._clear_sessions(db, int(user["id"]))
            return self._grant(db, user, device, now)

    @staticmethod
    def _matches(row, value: bytes) -> bool:
        return bool(row and row["scheme"] == PASSWORD_SCHEME
                    and hmac.compare_digest(_derive(value, row["salt"]), row["password_hash"]))

    def login(self, password: str, *, device_name: str | None = None) -> dict:
        value, device = password_bytes(password), self._device_name(device_name)
        now = int(self.clock())
        with self._transaction() as db:
            self._check_throttle(db, now)
            row = db.execute("SELECT * FROM owner_password_credentials WHERE singleton=1").fetchone()
            if not self._matches(row, value):
                self._failed(db, now)
            user = self._owner(db)
            if int(row["user_id"]) != int(user["id"]):
                raise OwnerAuthError("owner_installation_not_ready", 503)
            return self._grant(db, user, device, now)

    def change(self, current_password: str, new_password: str, *,
               authorization: str | None, device_name: str | None = None) -> dict:
        old_value, new_value = password_bytes(current_password), password_bytes(new_password, new=True)
        device, now = self._device_name(device_name), int(self.clock())
        with self._transaction() as db:
            self._check_throttle(db, now)
            user = self._session_owner(db, authorization, now)
            row = db.execute("SELECT * FROM owner_password_credentials WHERE singleton=1").fetchone()
            if user is None or not self._matches(row, old_value):
                self._failed(db, now)
            if int(row["user_id"]) != int(user["id"]):
                raise OwnerAuthError("owner_installation_not_ready", 503)
            salt = secrets.token_bytes(16)
            db.execute("UPDATE owner_password_credentials SET salt=?,password_hash=?,updated_at=? WHERE singleton=1",
                       (salt, _derive(new_value, salt), now))
            self._clear_sessions(db, int(user["id"]))
            return self._grant(db, user, device, now)
