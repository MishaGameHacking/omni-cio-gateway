"""Real SQLite connection fences; no application import, credentials or network."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
from pathlib import Path
import hashlib
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from backend import broker_connections as connections


class ConnectionVersionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "connections.db"
        with closing(self.connect()) as db:
            db.executescript("""
                CREATE TABLE users(id INTEGER PRIMARY KEY, telegram_sub TEXT NOT NULL,
                    tinvest_token_encrypted BLOB, updated_at INTEGER NOT NULL);
                CREATE TABLE sessions(token_hash TEXT PRIMARY KEY, user_id INTEGER,
                    expires_at INTEGER NOT NULL);
            """)
            for user_id in (1, 2):
                db.execute("INSERT INTO users VALUES (?,?,?,?)", (user_id, str(user_id), b"original", 1))
                db.execute("INSERT INTO sessions VALUES (?,?,?)", (self.digest(user_id), user_id, 4102444800))
            db.commit()
        connections.initialize(self.connect)

    def connect(self):
        return sqlite3.connect(self.path, timeout=5)

    @staticmethod
    def authorization(user_id=1):
        return "Bearer synthetic-session-" + str(user_id)

    def digest(self, user_id=1):
        return hashlib.sha256(self.authorization(user_id)[7:].encode()).hexdigest()

    def capture(self, user_id=1):
        return connections.begin_change(self.connect, user_id, self.authorization(user_id))

    def stored(self, user_id=1):
        with closing(self.connect()) as db:
            return db.execute("SELECT tinvest_token_encrypted FROM users WHERE id=?", (user_id,)).fetchone()[0]

    def mutate(self, sql, parameters=()):
        with closing(self.connect()) as db:
            db.execute(sql, parameters)
            db.commit()

    def test_migration_preserves_credentials_sessions_and_existing_versions(self):
        before = self.capture()
        connections.initialize(self.connect)
        self.assertEqual(self.capture(), before)
        self.assertEqual(self.stored(), b"original")
        self.assertEqual(len(before.stamp), 64)

    def test_concurrent_initialization_is_idempotent(self):
        before = self.capture()
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _: connections.initialize(self.connect), range(8)))
        self.assertEqual(self.capture(), before)

    def test_success_invalidates_replay_of_the_same_ticket(self):
        change = self.capture()
        connections.commit_change(self.connect, change, b"validated-ciphertext")
        self.assertEqual(self.stored(), b"validated-ciphertext")
        with self.assertRaisesRegex(connections.ConnectionChangeError, "tinvest_connection_changed"):
            connections.commit_change(self.connect, change, b"late-ciphertext")
        self.assertEqual(self.stored(), b"validated-ciphertext")

    def test_disconnect_invalidates_pending_save(self):
        change = self.capture()
        connections.disconnect(self.connect, 1, self.authorization())
        with self.assertRaisesRegex(connections.ConnectionChangeError, "tinvest_connection_changed"):
            connections.commit_change(self.connect, change, b"late")
        self.assertIsNone(self.stored())

    def test_already_disconnected_null_aba_is_not_a_noop(self):
        connections.disconnect(self.connect, 1, self.authorization())
        change = self.capture()
        connections.disconnect(self.connect, 1, self.authorization())
        with self.assertRaisesRegex(connections.ConnectionChangeError, "tinvest_connection_changed"):
            connections.commit_change(self.connect, change, b"late")
        self.assertIsNone(self.stored())

    def test_other_user_update_does_not_invalidate_my_change(self):
        change = self.capture()
        connections.disconnect(self.connect, 2, self.authorization(2))
        connections.commit_change(self.connect, change, b"new")
        self.assertEqual(self.stored(), b"new")
        self.assertIsNone(self.stored(2))

    def test_profile_timestamp_change_is_not_a_connection_change(self):
        change = self.capture()
        self.mutate("UPDATE users SET updated_at=updated_at+1 WHERE id=1")
        connections.commit_change(self.connect, change, b"new")
        self.assertEqual(self.stored(), b"new")

    def test_direct_same_ciphertext_update_still_invalidates(self):
        change = self.capture()
        self.mutate("UPDATE users SET tinvest_token_encrypted=tinvest_token_encrypted WHERE id=1")
        with self.assertRaisesRegex(connections.ConnectionChangeError, "tinvest_connection_changed"):
            connections.commit_change(self.connect, change, b"late")
        self.assertEqual(self.stored(), b"original")

    def test_revocation_during_validation_prevents_save(self):
        change = self.capture()
        self.mutate("DELETE FROM sessions WHERE token_hash=?", (self.digest(),))
        with self.assertRaisesRegex(connections.ConnectionChangeError, "invalid_session"):
            connections.commit_change(self.connect, change, b"late")
        self.assertEqual(self.stored(), b"original")

    def test_other_active_session_does_not_replace_revoked_authorization(self):
        change = self.capture()
        self.mutate("INSERT INTO sessions VALUES ('other-session-hash',1,4102444800)")
        self.mutate("DELETE FROM sessions WHERE token_hash=?", (self.digest(),))
        with self.assertRaisesRegex(connections.ConnectionChangeError, "invalid_session"):
            connections.commit_change(self.connect, change, b"late")

    def test_expiry_is_checked_again_including_exact_boundary(self):
        change = self.capture()
        self.mutate("UPDATE sessions SET expires_at=1000 WHERE user_id=1")
        with patch.object(connections.time, "time", return_value=1000):
            with self.assertRaisesRegex(connections.ConnectionChangeError, "invalid_session"):
                connections.commit_change(self.connect, change, b"late")
        self.assertEqual(self.stored(), b"original")

    def test_missing_user_is_not_a_false_success(self):
        change = self.capture()
        self.mutate("DELETE FROM users WHERE id=1")
        with self.assertRaisesRegex(connections.ConnectionChangeError, "invalid_session"):
            connections.commit_change(self.connect, change, b"late")
        with closing(self.connect()) as db:
            self.assertIsNone(db.execute("SELECT 1 FROM broker_connection_versions WHERE user_id=1").fetchone())

    def test_recreated_same_user_id_cannot_reuse_old_ticket(self):
        change = self.capture()
        self.mutate("DELETE FROM users WHERE id=1")
        self.mutate("INSERT INTO users VALUES (1,'1',NULL,1)")
        with self.assertRaisesRegex(connections.ConnectionChangeError, "tinvest_connection_changed"):
            connections.commit_change(self.connect, change, b"late")
        self.assertIsNone(self.stored())

    def test_missing_version_fails_closed(self):
        change = self.capture()
        self.mutate("DELETE FROM broker_connection_versions WHERE user_id=1")
        with self.assertRaisesRegex(connections.ConnectionChangeError, "tinvest_connection_version_missing"):
            connections.commit_change(self.connect, change, b"late")
        self.assertEqual(self.stored(), b"original")

    def test_cross_user_session_cannot_capture_or_disconnect(self):
        authorization = self.authorization()
        for action in (connections.begin_change, connections.disconnect):
            with self.subTest(action=action.__name__):
                with self.assertRaisesRegex(connections.ConnectionChangeError, "invalid_session"):
                    action(self.connect, 2, authorization)
        self.assertEqual(self.stored(2), b"original")

    def test_ticket_user_tampering_does_not_change_session_ownership(self):
        change = replace(self.capture(), user_id=2)
        with self.assertRaisesRegex(connections.ConnectionChangeError, "invalid_session"):
            connections.commit_change(self.connect, change, b"late")
        self.assertEqual(self.stored(2), b"original")

    def test_rolled_back_token_write_also_rolls_back_version(self):
        before = self.capture()
        with closing(self.connect()) as db:
            db.execute("UPDATE users SET tinvest_token_encrypted=? WHERE id=1", (b"rolled-back",))
            db.rollback()
        self.assertEqual(self.capture(), before)
        connections.commit_change(self.connect, before, b"committed")
        self.assertEqual(self.stored(), b"committed")

    def test_parallel_saves_have_exactly_one_winner(self):
        changes = [self.capture() for _ in range(4)]
        barrier = threading.Barrier(4)
        def publish(index):
            barrier.wait(timeout=5)
            try:
                connections.commit_change(self.connect, changes[index], str(index).encode())
                return "success", index
            except connections.ConnectionChangeError as error:
                return error.code, index
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(publish, range(4)))
        winners = [index for status, index in results if status == "success"]
        self.assertEqual(len(winners), 1)
        self.assertEqual(self.stored(), str(winners[0]).encode())
        self.assertEqual(sum(status == "tinvest_connection_changed" for status, _ in results), 3)

    def test_session_time_is_read_after_waiting_for_write_lock(self):
        change = self.capture()
        clock = [1000]
        started = threading.Event()
        class ObservedConnection(sqlite3.Connection):
            def execute(self, statement, parameters=()):
                if statement == connections.BEGIN_WRITE:
                    started.set()
                return super().execute(statement, parameters)
        def waiting_connect():
            return sqlite3.connect(self.path, timeout=5, factory=ObservedConnection)
        with closing(self.connect()) as writer, patch.object(connections.time, "time", side_effect=lambda: clock[0]):
            writer.execute("BEGIN IMMEDIATE")
            writer.execute("UPDATE sessions SET expires_at=1500 WHERE user_id=1")
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(connections.commit_change, waiting_connect, change, b"late")
                try:
                    self.assertTrue(started.wait(timeout=5))
                    clock[0] = 2000
                finally:
                    writer.commit()
                with self.assertRaisesRegex(connections.ConnectionChangeError, "invalid_session"):
                    future.result(timeout=5)
        self.assertEqual(self.stored(), b"original")

    def test_invalid_session_inputs_are_fixed_errors(self):
        for value in (None, "", "Basic x", "Bearer ", "Bearer я", "Bearer " + "x" * 4097):
            with self.subTest(length=len(value) if isinstance(value, str) else None):
                with self.assertRaisesRegex(connections.ConnectionChangeError, "invalid_session"):
                    connections.begin_change(self.connect, 1, value)

    def test_invalid_user_types_cannot_be_coerced(self):
        authorization = self.authorization()
        for user_id in (True, 0, -1, 1.0, "1", None):
            with self.subTest(user_id=user_id):
                with self.assertRaisesRegex(connections.ConnectionChangeError, "invalid_session"):
                    connections.begin_change(self.connect, user_id, authorization)

    def test_token_validation_does_not_echo_or_accept_header_controls(self):
        values = [None, "x" * 4097, "token\nsecret", "token\rsecret", "token\x00secret",
                  "token\tsecret", "token\x7fsecret", "токен", "\ud800", "two tokens"]
        for value in values:
            with self.subTest(type_name=type(value).__name__):
                with self.assertRaises(connections.ConnectionChangeError) as caught:
                    connections.validated_token(value)
                self.assertEqual(str(caught.exception), "invalid_tinvest_token_format")

    def test_empty_and_padded_tokens_preserve_existing_contract(self):
        with self.assertRaisesRegex(connections.ConnectionChangeError, "empty_tinvest_token"):
            connections.validated_token(" \t ")
        self.assertEqual(connections.validated_token("  readonly-token  "), "readonly-token")
        self.assertEqual(connections.validated_token("x" * 4096), "x" * 4096)

    def test_ticket_repr_does_not_expose_session_hash_or_subject(self):
        ticket = self.capture()
        self.assertNotIn(ticket.session_hash, repr(ticket))
        self.assertNotIn(ticket.stamp, repr(ticket))
        self.assertNotIn("subject", repr(ticket))

    def test_invalid_ciphertext_cannot_mutate_connection(self):
        ticket = self.capture()
        for value in (None, "raw-token", b"", b"x" * 16385):
            with self.subTest(type_name=type(value).__name__):
                with self.assertRaisesRegex(ValueError, "invalid_encrypted_broker_token"):
                    connections.commit_change(self.connect, ticket, value)
        self.assertEqual(self.capture(), ticket)


if __name__ == "__main__":
    unittest.main()
