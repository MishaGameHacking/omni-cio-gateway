"""HTTP contract tests without live credentials or external requests."""
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.owner_access import OwnerIdentity
from backend.owner_app import configure_app
from backend.owner_password_routes import install
from backend.tests.test_owner_password import BOOTSTRAP, PASSWORD, create_schema, token_hash


class OwnerPasswordRouteTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "http.db"
        self.identity = OwnerIdentity("fixed-owner")
        self.app = FastAPI()
        self.legacy = SimpleNamespace(connect=self.connect, SESSION_TTL=3600,
            BACKEND_PUBLIC_URL="https://analyst.invalid", TELEGRAM_CLIENT_ID="12345",
            TELEGRAM_CLIENT_SECRET="test-not-real")
        self.calls = []
        @self.app.get("/auth/telegram/start")
        def legacy_start():
            self.calls.append("legacy")
            return {"legacy": True}
        @self.app.post("/auth/session")
        def legacy_exchange():
            self.calls.append("exchange")
            return {"legacy": True}
        configure_app(self.app, self.connect, self.initialize, self.identity)
        install(self.app, self.legacy, self.identity)
        self.environment = patch.dict(os.environ, {"ANALYST_OWNER_BOOTSTRAP_SECRET": BOOTSTRAP})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def initialize(self):
        create_schema(self.connect)

    def setup_password(self):
        return self.client.post("/auth/owner/setup", json={"password": PASSWORD},
                                headers={"X-Owner-Bootstrap": BOOTSTRAP})

    def test_status_exposes_no_owner_or_secret_and_is_not_cached(self):
        response = self.client.get("/auth/owner/status")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["configured"])
        self.assertEqual(response.headers["Cache-Control"], "no-store, private")
        self.assertNotIn("fixed-owner", response.text)
        self.assertNotIn(BOOTSTRAP, response.text)

    def test_legacy_paths_work_before_enrollment_and_are_blocked_after(self):
        self.assertEqual(self.client.get("/auth/telegram/start").status_code, 200)
        response = self.setup_password()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store, private")
        self.assertTrue(self.client.get("/auth/owner/status").json()["configured"])
        self.assertEqual(self.client.get("/auth/telegram/start").status_code, 401)
        self.assertEqual(self.client.post("/auth/session", json={"code": "old-code"}).status_code, 401)
        self.assertEqual(self.calls, ["legacy"])
        login = self.client.post("/auth/owner/login", json={"password": PASSWORD, "device_name": "Phone"})
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.json()["access_token"])
        self.assertTrue(login.json()["device_id"])

    def test_missing_telegram_credentials_does_not_disable_password_auth(self):
        self.legacy.TELEGRAM_CLIENT_ID = ""
        self.legacy.TELEGRAM_CLIENT_SECRET = ""
        self.assertEqual(self.client.get("/auth/telegram/start").status_code, 401)
        self.assertEqual(self.setup_password().status_code, 200)
        self.assertEqual(self.client.post("/auth/owner/login", json={"password": PASSWORD}).status_code, 200)

    def test_anonymous_setup_is_denied_even_with_existing_owner(self):
        with closing(self.connect()) as db:
            now = int(time.time())
            db.execute("INSERT INTO users VALUES(1,'fixed-owner','old-id','Owner',NULL,NULL,NULL,?,?)", (now, now))
            db.commit()
        response = self.client.post("/auth/owner/setup", json={"password": PASSWORD})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "owner_credentials_invalid"})

    def test_existing_owner_session_can_enroll_without_bootstrap(self):
        now = int(time.time())
        with closing(self.connect()) as db:
            db.execute("INSERT INTO users VALUES(1,'fixed-owner','old-id','Owner',NULL,NULL,NULL,?,?)", (now, now))
            db.execute("INSERT INTO sessions VALUES (?,1,?)", (token_hash("existing-owner-session"), now + 60))
            db.execute("INSERT INTO workspace_session_devices VALUES (?,'registered-phone','Phone',?,?)",
                       (token_hash("existing-owner-session"), now, now))
            db.commit()
        with patch.dict(os.environ, {"ANALYST_OWNER_BOOTSTRAP_SECRET": ""}):
            response = self.client.post("/auth/owner/setup", json={"password": PASSWORD},
                                       headers={"Authorization": "Bearer existing-owner-session"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["telegram_id"], "old-id")

    def test_cross_origin_mutations_rejected_before_password_check(self):
        response = self.client.post("/auth/owner/setup", json={"password": PASSWORD},
            headers={"Origin": "https://untrusted.invalid", "X-Owner-Bootstrap": BOOTSTRAP})
        self.assertEqual(response.status_code, 401)
        self.assertFalse(self.client.get("/auth/owner/status").json()["configured"])

    def test_invalid_payload_never_echoes_submitted_credentials(self):
        for payload in ({"password": {"secret": PASSWORD}}, {"password": PASSWORD, "unknown": PASSWORD},
                        {"password": PASSWORD * 150}, {"device_name": PASSWORD}):
            with self.subTest(payload_type=type(payload)):
                response = self.client.post("/auth/owner/setup", json=payload)
                self.assertEqual(response.status_code, 422)
                self.assertNotIn(PASSWORD, response.text)
        response = self.client.post("/auth/owner/login", content=b"invalid-json")
        self.assertEqual(response.json(), {"detail": "owner_auth_payload_invalid"})

    def test_http_throttle_has_retry_after_and_generic_errors(self):
        self.assertEqual(self.setup_password().status_code, 200)
        for _ in range(4):
            response = self.client.post("/auth/owner/login", json={"password": "incorrect"})
            self.assertEqual(response.status_code, 401)
        response = self.client.post("/auth/owner/login", json={"password": "incorrect"})
        self.assertEqual(response.status_code, 429)
        self.assertGreater(int(response.headers["Retry-After"]), 0)
        self.assertNotIn(PASSWORD, response.text)

    def test_deeply_nested_json_is_rejected_without_server_error(self):
        payload = b"[" * 1000 + b"0" + b"]" * 1000
        response = self.client.post("/auth/owner/login", content=payload,
                                    headers={"Content-Type": "application/json"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json(), {"detail": "owner_auth_payload_invalid"})

    def test_password_rotation_returns_new_existing_session_shape(self):
        session = self.setup_password().json()
        response = self.client.post("/auth/owner/password", json={"current_password": PASSWORD,
            "new_password": "changed owner password", "device_name": "Phone"},
            headers={"Authorization": "Bearer " + session["access_token"]})
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.json()["access_token"], session["access_token"])
        with closing(self.connect()) as db:
            self.assertIsNone(db.execute("SELECT 1 FROM sessions WHERE token_hash=?", (token_hash(session["access_token"]),)).fetchone())


if __name__ == "__main__":
    unittest.main()
