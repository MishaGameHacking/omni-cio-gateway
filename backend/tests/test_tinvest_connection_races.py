"""Exercise actual HTTP handlers with real sessions, SQLite and Fernet.

Only the upstream read-only GetAccounts transport is mocked. Its callback gives
an exact interleaving while the first request is awaiting its broker response;
there are no sleeps, live tokens, model calls or broker operations.
"""
from contextlib import closing
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from backend import app as backend


class BrokerConnectionRaceTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        patcher = patch.object(backend, "DATABASE_PATH", Path(directory.name) / "backend.db")
        patcher.start()
        self.addCleanup(patcher.stop)
        backend.init_db()
        self.session = "synthetic-connection-audit-session"
        self.headers = {"Authorization": "Bearer " + self.session}
        now = int(time.time())
        with closing(backend.connect()) as db:
            self.user_id = db.execute(
                "INSERT INTO users(telegram_sub,name,created_at,updated_at) VALUES (?,?,?,?)",
                ("connection-audit-owner", "Synthetic", now, now),
            ).lastrowid
            db.execute("INSERT INTO sessions(token_hash,user_id,expires_at) VALUES (?,?,?)",
                       (backend.hash_token(self.session), self.user_id, now + 3600))
            db.commit()
        self.client = TestClient(backend.app)
        self.addCleanup(self.client.close)
        tls = patch.object(backend, "tinvest_ssl_context", return_value=True)
        tls.start()
        self.addCleanup(tls.stop)

    def mutate(self, sql, parameters=()):
        with closing(backend.connect()) as db:
            db.execute(sql, parameters)
            db.commit()

    def stored(self):
        with closing(backend.connect()) as db:
            row = db.execute("SELECT tinvest_token_encrypted FROM users WHERE id=?",
                             (self.user_id,)).fetchone()
        if row is None or row[0] is None:
            return None
        return backend.FERNET.decrypt(row[0]).decode()

    def set_stored(self, token):
        encrypted = backend.FERNET.encrypt(token.encode()) if token else None
        self.mutate("UPDATE users SET tinvest_token_encrypted=? WHERE id=?", (encrypted, self.user_id))

    def pending(self, during_validation, *, token="delayed-token"):
        def complete(*_args, **_kwargs):
            during_validation()
            return httpx.Response(200, json={"accounts": []})
        with patch.object(backend.httpx, "Client") as transport:
            transport.return_value.__enter__.return_value.post.side_effect = complete
            response = self.client.post("/tinvest/token", headers=self.headers, json={"token": token})
        self.assertEqual(transport.return_value.__enter__.return_value.post.call_count, 1)
        return response

    def assert_rejected(self, response, status, detail):
        self.assertEqual(response.status_code, status, response.text)
        self.assertEqual(response.json(), {"detail": detail})
        self.assertIn("no-store", response.headers.get("cache-control", ""))
        self.assertNotIn("delayed-token", response.text)

    def disconnect(self):
        response = self.client.delete("/tinvest/token", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {"connected": False})

    def test_disconnect_during_save_cannot_resurrect_an_existing_connection(self):
        self.set_stored("original-token")
        response = self.pending(self.disconnect)
        self.assert_rejected(response, 409, "tinvest_connection_changed")
        self.assertIsNone(self.stored())
        self.assertEqual(self.client.get("/tinvest/status", headers=self.headers).json(), {"connected": False})

    def test_disconnect_during_first_connection_handles_null_to_null_aba(self):
        self.assertIsNone(self.stored())
        response = self.pending(self.disconnect)
        self.assert_rejected(response, 409, "tinvest_connection_changed")
        self.assertIsNone(self.stored())

    def test_delayed_save_cannot_overwrite_a_newer_successful_replacement(self):
        self.set_stored("original-token")
        def complete(*_args, **kwargs):
            if kwargs["headers"]["Authorization"] == "Bearer delayed-token":
                newer = self.client.post("/tinvest/token", headers=self.headers, json={"token": "newer-token"})
                self.assertEqual(newer.status_code, 200, newer.text)
            return httpx.Response(200, json={"accounts": []})
        with patch.object(backend.httpx, "Client") as transport:
            upstream = transport.return_value.__enter__.return_value
            upstream.post.side_effect = complete
            response = self.client.post("/tinvest/token", headers=self.headers, json={"token": "delayed-token"})
        self.assertEqual(upstream.post.call_count, 2)
        self.assert_rejected(response, 409, "tinvest_connection_changed")
        self.assertEqual(self.stored(), "newer-token")

    def test_session_revoked_during_broker_validation_cannot_save(self):
        self.set_stored("original-token")
        response = self.pending(lambda: self.mutate("DELETE FROM sessions WHERE token_hash=?",
                                                   (backend.hash_token(self.session),)))
        self.assert_rejected(response, 401, "invalid_session")
        self.assertEqual(self.stored(), "original-token")

    def test_another_active_session_does_not_replace_the_revoked_one(self):
        self.mutate("INSERT INTO sessions VALUES (?,?,?)",
                    (backend.hash_token("different-device-session"), self.user_id, int(time.time()) + 3600))
        response = self.pending(lambda: self.mutate("DELETE FROM sessions WHERE token_hash=?",
                                                   (backend.hash_token(self.session),)))
        self.assert_rejected(response, 401, "invalid_session")
        self.assertIsNone(self.stored())

    def test_session_expiring_during_broker_validation_cannot_save(self):
        response = self.pending(lambda: self.mutate("UPDATE sessions SET expires_at=? WHERE token_hash=?",
                                                   (int(time.time()) - 1, backend.hash_token(self.session))))
        self.assert_rejected(response, 401, "invalid_session")
        self.assertIsNone(self.stored())

    def test_user_deleted_during_broker_validation_is_not_connected_success(self):
        response = self.pending(lambda: self.mutate("DELETE FROM users WHERE id=?", (self.user_id,)))
        self.assert_rejected(response, 401, "invalid_session")
        self.assertIsNone(self.stored())

    def test_profile_edit_during_validation_does_not_discard_valid_token(self):
        response = self.pending(lambda: self.mutate("UPDATE users SET name=?,updated_at=? WHERE id=?",
                                                   ("Renamed", int(time.time()), self.user_id)))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.stored(), "delayed-token")

    def test_normal_save_remains_encrypted_and_disconnect_remains_idempotent(self):
        response = self.pending(lambda: None, token="  readonly-token  ")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {"connected": True})
        self.assertEqual(self.stored(), "readonly-token")
        self.disconnect()
        self.disconnect()
        self.assertIsNone(self.stored())

    def test_network_validation_does_not_hold_a_sqlite_write_lock(self):
        def independent_writer():
            with closing(backend.connect()) as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("UPDATE users SET name=name WHERE id=?", (self.user_id,))
                db.commit()
        response = self.pending(independent_writer)
        self.assertEqual(response.status_code, 200, response.text)

    def test_invalid_headers_are_rejected_before_upstream_client_creation(self):
        for token in ("two tokens", "token\nsecret", "token\rsecret", "token\x00secret", "токен", "x" * 4097):
            with self.subTest(length=len(token)):
                with patch.object(backend.httpx, "Client") as transport:
                    transport.return_value.__enter__.return_value.post.return_value = httpx.Response(200, json={"accounts": []})
                    response = self.client.post("/tinvest/token", headers=self.headers, json={"token": token})
                self.assert_rejected(response, 400, "invalid_tinvest_token_format")
                transport.assert_not_called()
        self.assertIsNone(self.stored())

    def test_unauthenticated_mutations_never_call_broker(self):
        with patch.object(backend.httpx, "Client") as transport:
            save = self.client.post("/tinvest/token", json={"token": "readonly-token"})
            delete = self.client.delete("/tinvest/token")
        self.assertEqual(save.status_code, 401)
        self.assertEqual(delete.status_code, 401)
        transport.assert_not_called()
        self.assertIsNone(self.stored())

    def test_rejected_upstream_token_does_not_destroy_existing_connection(self):
        self.set_stored("original-token")
        with patch.object(backend.httpx, "Client") as transport:
            transport.return_value.__enter__.return_value.post.return_value = httpx.Response(403)
            response = self.client.post("/tinvest/token", headers=self.headers, json={"token": "rejected-token"})
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(response.json(), {"detail": "invalid_tinvest_token"})
        self.assertEqual(self.stored(), "original-token")

    def test_upstream_timeout_does_not_retry_or_destroy_existing_connection(self):
        self.set_stored("original-token")
        with patch.object(backend.httpx, "Client") as transport:
            upstream = transport.return_value.__enter__.return_value
            upstream.post.side_effect = httpx.ReadTimeout("synthetic")
            response = self.client.post("/tinvest/token", headers=self.headers, json={"token": "readonly-token"})
        self.assertEqual(response.status_code, 504, response.text)
        self.assertEqual(upstream.post.call_count, 1)
        self.assertEqual(self.stored(), "original-token")


if __name__ == "__main__":
    unittest.main()
