"""Password enrollment, persistence, replay and concurrent session boundaries."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, contextmanager
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from backend.owner_access import OwnerIdentity, bind_owner
from backend.owner_password import (LOCK_SECONDS, MAX_FAILURES, OwnerAuthError,
                                    OwnerPasswordStore, initialize)

PASSWORD = "owner test password 2026"
BOOTSTRAP = "test-bootstrap-not-a-real-secret-0123456789"


def create_schema(connect):
    with closing(connect()) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,telegram_sub TEXT NOT NULL UNIQUE,
            telegram_id TEXT,name TEXT,username TEXT,picture TEXT,
            tinvest_token_encrypted BLOB,created_at INTEGER,updated_at INTEGER)""")
        db.execute("CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER,expires_at INTEGER)")
        db.execute("CREATE TABLE IF NOT EXISTS workspace_session_devices(token_hash TEXT PRIMARY KEY,device_id TEXT UNIQUE,device_name TEXT,created_at INTEGER,last_seen_at INTEGER)")
        db.execute("CREATE TABLE IF NOT EXISTS login_codes(code_hash TEXT PRIMARY KEY,user_id INTEGER,expires_at INTEGER,used INTEGER)")
        db.execute("CREATE TABLE IF NOT EXISTS login_transactions(state TEXT PRIMARY KEY,verifier TEXT,created_at INTEGER)")
        db.commit()


def token_hash(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


class OwnerPasswordTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "owner.db"
        self.now = 1800000000
        create_schema(self.connect)
        self.identity = OwnerIdentity("fixed-owner")
        bind_owner(self.connect, self.identity)
        initialize(self.connect)
        bind_owner(self.connect, self.identity)
        self.store = self.new_store()

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def new_store(self):
        return OwnerPasswordStore(self.connect, session_ttl=3600,
                                  bootstrap_secret=lambda: BOOTSTRAP, clock=lambda: self.now)

    def existing_owner(self, *, expired=False, registered=True):
        with closing(self.connect()) as db:
            db.execute("INSERT INTO users VALUES (7,'fixed-owner','old-id','Owner',NULL,NULL,?,1,1)",
                       (b"encrypted-broker-token-preserved",))
            db.execute("INSERT INTO sessions VALUES (?,7,?)", (token_hash("old-session"), self.now - 1 if expired else self.now + 500))
            if registered:
                db.execute("INSERT INTO workspace_session_devices VALUES (?, 'old-device','Phone',1,1)",
                           (token_hash("old-session"),))
            db.commit()
        return "Bearer old-session"

    def enroll(self):
        return self.store.setup(PASSWORD, bootstrap=BOOTSTRAP)

    def assert_error(self, code, callback, *args, **kwargs):
        with self.assertRaises(OwnerAuthError) as caught:
            callback(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_first_anonymous_visitor_cannot_enroll_or_create_owner(self):
        self.assert_error("owner_credentials_invalid", self.store.setup, PASSWORD)
        self.assertFalse(self.store.configured())
        with closing(self.connect()) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users").fetchone()[0], 0)

    def test_bootstrap_creates_only_the_prebound_owner_and_is_one_time(self):
        result = self.enroll()
        self.assertTrue(result["access_token"])
        self.assert_error("owner_password_already_configured", self.store.setup, "replacement password", bootstrap=BOOTSTRAP)
        with closing(self.connect()) as db:
            row = db.execute("SELECT telegram_sub FROM users").fetchone()
            self.assertEqual(row[0], "fixed-owner")
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)
        self.assertTrue(self.store.login(PASSWORD)["access_token"])

    def test_session_migration_preserves_portfolio_identity_and_broker_secret(self):
        auth = self.existing_owner()
        result = self.store.setup(PASSWORD, authorization=auth, device_name="Owner phone")
        with closing(self.connect()) as db:
            user = db.execute("SELECT * FROM users").fetchone()
            self.assertEqual(user["id"], 7)
            self.assertEqual(user["tinvest_token_encrypted"], b"encrypted-broker-token-preserved")
            self.assertIsNone(db.execute("SELECT 1 FROM sessions WHERE token_hash=?", (token_hash("old-session"),)).fetchone())
            session = db.execute("SELECT * FROM sessions").fetchone()
            self.assertEqual(session["token_hash"], token_hash(result["access_token"]))
            self.assertEqual(session["user_id"], 7)
        self.assertEqual(result["user"]["telegram_id"], "old-id")

    def test_expired_session_cannot_enroll(self):
        auth = self.existing_owner(expired=True)
        self.assert_error("owner_credentials_invalid", self.store.setup, PASSWORD, authorization=auth)
        self.assertFalse(self.store.configured())

    def test_unregistered_device_session_cannot_enroll(self):
        auth = self.existing_owner(registered=False)
        self.assert_error("owner_credentials_invalid", self.store.setup, PASSWORD, authorization=auth)
        self.assertFalse(self.store.configured())

    def test_different_or_malformed_bearer_cannot_enroll(self):
        self.existing_owner()
        for authorization in ("Bearer other-session", "Basic old-session", None):
            self.assert_error("owner_credentials_invalid", self.store.setup, PASSWORD, authorization=authorization)

    def test_hash_is_salted_and_never_stores_plaintext(self):
        self.enroll()
        with closing(self.connect()) as db:
            row = db.execute("SELECT * FROM owner_password_credentials").fetchone()
            self.assertEqual(len(row["salt"]), 16)
            self.assertEqual(len(row["password_hash"]), 32)
            self.assertNotEqual(row["password_hash"], PASSWORD.encode())
            self.assertNotIn(PASSWORD, "\n".join(db.iterdump()))
        self.assertTrue(self.new_store().login(PASSWORD)["access_token"])

    def test_global_throttle_persists_across_store_restarts(self):
        self.enroll()
        for _ in range(MAX_FAILURES - 1):
            self.assert_error("owner_credentials_invalid", self.new_store().login, "incorrect")
        error = self.assert_error("owner_auth_throttled", self.new_store().login, "incorrect")
        self.assertEqual(error.retry_after, LOCK_SECONDS)
        self.assert_error("owner_auth_throttled", self.new_store().login, PASSWORD)
        self.now += LOCK_SECONDS
        self.assertTrue(self.new_store().login(PASSWORD)["access_token"])

    def test_success_resets_failure_window(self):
        self.enroll()
        self.assert_error("owner_credentials_invalid", self.store.login, "incorrect")
        self.store.login(PASSWORD)
        with closing(self.connect()) as db:
            self.assertIsNone(db.execute("SELECT * FROM owner_password_attempts").fetchone())

    def lock_anonymous_login(self):
        for attempt in range(MAX_FAILURES):
            code = "owner_auth_throttled" if attempt == MAX_FAILURES - 1 else "owner_credentials_invalid"
            self.assert_error(code, self.new_store().login, "incorrect")

    def test_anonymous_failures_cannot_block_valid_owner_session_enrollment(self):
        auth = self.existing_owner()
        self.lock_anonymous_login()
        for attempt in range(MAX_FAILURES):
            code = "owner_auth_throttled" if attempt == MAX_FAILURES - 1 else "owner_credentials_invalid"
            self.assert_error(code, self.new_store().setup, PASSWORD)
        self.assertTrue(self.store.setup(PASSWORD, authorization=auth)["access_token"])

    def test_anonymous_failures_cannot_block_valid_bootstrap_enrollment(self):
        self.lock_anonymous_login()
        for attempt in range(MAX_FAILURES):
            code = "owner_auth_throttled" if attempt == MAX_FAILURES - 1 else "owner_credentials_invalid"
            self.assert_error(code, self.new_store().setup, PASSWORD, bootstrap="wrong")
        self.assertTrue(self.store.setup(PASSWORD, bootstrap=BOOTSTRAP)["access_token"])

    def test_protected_login_recovers_from_anonymous_lock_but_still_checks_password(self):
        session = self.enroll()
        self.lock_anonymous_login()
        auth = "Bearer " + session["access_token"]
        self.assert_error("owner_auth_throttled", self.store.login, PASSWORD, authorization="Bearer unknown")
        self.assert_error("owner_credentials_invalid", self.store.login, "incorrect", authorization=auth)
        self.assertTrue(self.new_store().login(PASSWORD, authorization=auth)["access_token"])

    def test_protected_login_has_its_own_persistent_guess_limit(self):
        session = self.enroll()
        auth = "Bearer " + session["access_token"]
        for attempt in range(MAX_FAILURES):
            code = "owner_auth_throttled" if attempt == MAX_FAILURES - 1 else "owner_credentials_invalid"
            self.assert_error(code, self.new_store().login, "incorrect", authorization=auth)
        self.assert_error("owner_auth_throttled", self.new_store().login, PASSWORD, authorization=auth)

    def test_expired_session_cannot_bypass_anonymous_login_lock(self):
        session = self.enroll()
        with closing(self.connect()) as db:
            db.execute("UPDATE sessions SET expires_at=?", (self.now - 1,))
            db.commit()
        self.lock_anonymous_login()
        self.assert_error("owner_auth_throttled", self.store.login, PASSWORD,
                          authorization="Bearer " + session["access_token"])

    def test_anonymous_failures_cannot_lock_password_change_for_owner_session(self):
        session = self.enroll()
        self.lock_anonymous_login()
        for attempt in range(MAX_FAILURES):
            code = "owner_auth_throttled" if attempt == MAX_FAILURES - 1 else "owner_credentials_invalid"
            self.assert_error(code, self.store.change, PASSWORD, "new owner password", authorization="Bearer unknown")
        result = self.store.change(PASSWORD, "new owner password",
                                    authorization="Bearer " + session["access_token"])
        self.assertTrue(result["access_token"])

    def test_password_change_throttles_wrong_password_on_the_valid_session(self):
        session = self.enroll()
        auth = "Bearer " + session["access_token"]
        for attempt in range(MAX_FAILURES):
            code = "owner_auth_throttled" if attempt == MAX_FAILURES - 1 else "owner_credentials_invalid"
            self.assert_error(code, self.new_store().change, "incorrect", "new owner password", authorization=auth)
        self.assert_error("owner_auth_throttled", self.new_store().change, PASSWORD, "new owner password", authorization=auth)

    def test_session_expiry_is_checked_after_acquiring_database_lock(self):
        auth = self.existing_owner()
        original = self.store._transaction
        @contextmanager
        def delayed_transaction():
            with original() as db:
                self.now += 600
                yield db
        with patch.object(self.store, "_transaction", delayed_transaction):
            self.assert_error("owner_credentials_invalid", self.store.setup, PASSWORD, authorization=auth)

    def test_weak_or_oversized_password_is_not_accepted(self):
        for password in ("1234", "         ", "a" * 129, "a\n" * 10, "а" * 65):
            with self.subTest(length=len(password)):
                self.assert_error("owner_password_invalid", self.store.setup, password, bootstrap=BOOTSTRAP)
        self.assertFalse(self.store.configured())

    def test_password_change_revokes_all_devices_and_bootstrap_cannot_reset(self):
        first = self.enroll()
        second = self.store.login(PASSWORD)
        changed = self.store.change(PASSWORD, "a new longer owner password", authorization="Bearer " + first["access_token"])
        with closing(self.connect()) as db:
            sessions = db.execute("SELECT token_hash FROM sessions").fetchall()
            self.assertEqual([row[0] for row in sessions], [token_hash(changed["access_token"])])
        self.assert_error("owner_credentials_invalid", self.store.login, PASSWORD)
        self.assert_error("owner_credentials_invalid", self.store.change, "a new longer owner password", "some other password", authorization="Bearer " + second["access_token"])
        self.assert_error("owner_password_already_configured", self.store.setup, PASSWORD, bootstrap=BOOTSTRAP)

    def test_legacy_callback_and_session_exchange_cannot_race_enrollment(self):
        self.enroll()
        with closing(self.connect()) as db:
            user_id = db.execute("SELECT id FROM users").fetchone()[0]
            with self.assertRaisesRegex(sqlite3.IntegrityError, "owner_password_login_required"):
                db.execute("INSERT INTO login_codes VALUES ('late-code',?,?,0)", (user_id, self.now + 100))
            with self.assertRaisesRegex(sqlite3.IntegrityError, "owner_password_login_required"):
                db.execute("INSERT INTO sessions VALUES ('late-session',?,?)", (user_id, self.now + 100))

    def test_failed_grant_rolls_back_credential_change_and_preserves_existing_session(self):
        auth = self.existing_owner()
        with patch.object(self.store, "_grant", side_effect=sqlite3.OperationalError("synthetic write error")):
            with self.assertRaises(sqlite3.OperationalError):
                self.store.setup(PASSWORD, authorization=auth)
        self.assertFalse(self.store.configured())
        with closing(self.connect()) as db:
            self.assertIsNotNone(db.execute("SELECT 1 FROM sessions WHERE token_hash=?", (token_hash("old-session"),)).fetchone())

    def test_concurrent_bootstrap_requests_cannot_replace_password(self):
        def enroll_once():
            try:
                self.new_store().setup(PASSWORD, bootstrap=BOOTSTRAP)
                return "created"
            except OwnerAuthError as error:
                return error.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: enroll_once(), range(2)))
        self.assertCountEqual(results, ["created", "owner_password_already_configured"])

    def test_schema_reinitialization_preserves_credentials_and_live_sessions(self):
        result = self.enroll()
        initialize(self.connect)
        bind_owner(self.connect, self.identity)
        with closing(self.connect()) as db:
            self.assertIsNotNone(db.execute("SELECT 1 FROM sessions WHERE token_hash=?", (token_hash(result["access_token"]),)).fetchone())
        self.assertTrue(self.store.login(PASSWORD)["access_token"])


if __name__ == "__main__":
    unittest.main()
