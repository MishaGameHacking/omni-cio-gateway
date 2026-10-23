"""ASGI startup boundary with real HTTP/SQLite, without any live credentials."""
from contextlib import asynccontextmanager, closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.owner_access import OwnerConfigurationError, OwnerIdentity
from backend.owner_app import configure_app


class OwnerAppTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "app.db"
        self.started, self.stopped = [], []
        @asynccontextmanager
        async def lifespan(app):
            self.started.append(True)
            with closing(self.connect()) as db:
                db.execute("CREATE TABLE IF NOT EXISTS queued (id INTEGER,user_id INTEGER)")
            try:
                yield
            finally:
                self.stopped.append(True)
        self.app = FastAPI(lifespan=lifespan)
        @self.app.get("/health")
        def health():
            return {"status": "ok"}
        @self.app.post("/auth/telegram/complete")
        def insert(subject: str):
            # The production browser does this only after signature verification.
            with closing(self.connect()) as db:
                db.execute("INSERT INTO users(telegram_sub) VALUES (?)", (subject,))
                db.commit()
            return {"created": True}
        configure_app(self.app, self.connect, self.initialize, OwnerIdentity("owner"))

    def connect(self):
        return sqlite3.connect(self.path)

    def initialize(self):
        with closing(self.connect()) as db:
            db.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,telegram_sub TEXT UNIQUE)")

    def test_lifespan_off_is_not_a_bypass(self):
        client = TestClient(self.app)
        self.addCleanup(client.close)
        self.assertEqual(client.get("/health").status_code, 503)
        self.assertEqual(client.post("/auth/telegram/complete?subject=owner").status_code, 503)

    def test_http_owner_allowed_nonowner_refused(self):
        with TestClient(self.app) as client:
            self.assertEqual(client.get("/health").status_code, 200)
            denied = client.post("/auth/telegram/complete?subject=visitor")
            self.assertEqual(denied.status_code, 403)
            self.assertEqual(denied.json()["detail"], "owner_access_denied")
            self.assertNotIn('"owner"', denied.text)
            self.assertEqual(client.post("/auth/telegram/complete?subject=owner").status_code, 200)
        self.assertEqual(self.started, [True])
        self.assertEqual(self.stopped, [True])
        self.assertFalse(self.app.state.single_owner_ready)

    def test_migration_tables_guarded(self):
        with TestClient(self.app):
            with closing(self.connect()) as db:
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute("INSERT INTO queued VALUES (1,999)")

    def test_cannot_rebind_an_existing_application(self):
        identity = OwnerIdentity("another")
        with self.assertRaises(OwnerConfigurationError):
            configure_app(self.app, self.connect, self.initialize, identity)

    def test_repeated_configuration_does_not_stack_middleware(self):
        count = len(self.app.user_middleware)
        configure_app(self.app, self.connect, self.initialize, OwnerIdentity("owner"))
        self.assertEqual(len(self.app.user_middleware), count)

    def test_conflicting_data_prevents_scheduler_start(self):
        self.initialize()
        with closing(self.connect()) as db:
            db.execute("INSERT INTO users VALUES (1,'someone-else')")
            db.commit()
        client = TestClient(self.app)
        self.addCleanup(client.close)
        with self.assertRaises(OwnerConfigurationError):
            client.__enter__()
        self.assertEqual(self.started, [])


if __name__ == "__main__":
    unittest.main()
