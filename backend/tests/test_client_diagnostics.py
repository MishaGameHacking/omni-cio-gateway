"""Synthetic observations in an isolated temporary DB; no phone/runtime proof."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest

from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient
from backend import client_diagnostics as diagnostics


class ClientDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "isolated.db"
        diagnostics.initialize(self.connect)
        app = FastAPI()
        def authenticate(authorization: str | None = Header(default=None)):
            if authorization == "Bearer owner":
                return {"id": 1}
            if authorization == "Bearer other":
                return {"id": 2}
            raise HTTPException(401, "missing_session")
        diagnostics.install_routes(app, authenticate, self.connect)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.headers = {"Authorization": "Bearer owner"}

    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def event(self, number=1, **changes):
        return {"event_id": f"{number:064x}", "kind": "uncaught_exception",
                "timestamp_ms": int(time.time()) * 1000, "capture_version": 38,
                "process_version": 38, "capture_api": 37, "reason": None,
                "status": None, "stage": "workspace", "exception_code": "security",
                "frames": [{"class": "ru.omnicio.app.MainActivity", "method": "onCreate", "line": 42}],
                **changes}

    def submit(self, events, headers=None):
        return self.client.post("/client/diagnostics", json={"schema_version": 1, "events": events},
                                headers=self.headers if headers is None else headers)

    def count(self, user=1):
        with closing(self.connect()) as db:
            return db.execute("SELECT COUNT(*) FROM client_diagnostic_events WHERE user_id=?", (user,)).fetchone()[0]

    def test_requires_session_for_ingestion_and_status(self):
        self.assertEqual(self.submit([self.event()], {}).status_code, 401)
        self.assertEqual(self.client.get("/client/diagnostics/status").status_code, 401)
        self.assertEqual(self.count(), 0)

    def test_current_release_header_is_not_required_to_report_failure(self):
        # Session-only dependency allows diagnosis of blocked/old clients; this
        # isolated module has no ready/enforce/job or broker integration.
        response = self.submit([self.event()], {**self.headers, "X-Analyst-Version-Code": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["accepted_ids"], [self.event()["event_id"]])
        self.assertEqual(response.headers["cache-control"], "no-store, private")

    def test_duplicate_retry_preserves_first_record(self):
        event = self.event()
        self.assertEqual(self.submit([event]).status_code, 200)
        changed = {**event, "stage": "settings"}
        self.assertEqual(self.submit([changed]).status_code, 200)
        self.assertEqual(self.count(), 1)
        with closing(self.connect()) as db:
            saved = json.loads(db.execute("SELECT payload_json FROM client_diagnostic_events").fetchone()[0])
        self.assertEqual(saved["stage"], "workspace")

    def test_owner_partition_is_taken_from_authentication(self):
        event = self.event()
        self.submit([event])
        response = self.client.get("/client/diagnostics/status", headers={"Authorization": "Bearer other"})
        self.assertEqual(response.json()["observations"], 0)
        self.assertEqual(self.submit([event], {"Authorization": "Bearer other"}).status_code, 200)
        self.assertEqual((self.count(1), self.count(2)), (1, 1))
        self.assertNotIn("frames", response.text)
        self.assertNotIn("user_id", response.text)

    def test_historical_version_stays_unknown(self):
        event = self.event(kind="historical_exit", process_version=None, reason=4,
                           status=0, exception_code=None, frames=[], stage="unknown")
        self.assertEqual(self.submit([event]).status_code, 200)
        response = self.client.get("/client/diagnostics/status", headers=self.headers).json()
        self.assertEqual(response["unknown_process_version"], 1)
        self.assertEqual(response["by_kind"]["historical_exit"], 1)

    def test_arbitrary_fields_or_frame_text_are_neither_saved_nor_echoed(self):
        secret = "https://example.invalid/?token=DO_NOT_LOG"
        cases = [self.event(message=secret), self.event(user_id=2),
                 self.event(frames=[{"class": secret, "method": "onCreate", "line": 1}]),
                 self.event(frames=[{"class": "ru.omnicio.app.MainActivity", "method": secret, "line": 1}])]
        for event in cases:
            with self.subTest(keys=sorted(event)):
                response = self.submit([event])
                self.assertEqual(response.status_code, 422)
                self.assertNotIn(secret, response.text)
        self.assertEqual(self.count(), 0)

    def test_strict_types_bounds_and_kind_consistency(self):
        invalid = [self.event(capture_version=True), self.event(process_version=37),
                   self.event(timestamp_ms=(int(time.time()) + 90000) * 1000),
                   self.event(reason=4), self.event(exception_code="Throwable"),
                   self.event(frames=self.event()["frames"] * 9),
                   self.event(kind="historical_exit", reason=4, status=0, exception_code=None)]
        for event in invalid:
            with self.subTest(event_id=event["event_id"], changes=event["kind"]):
                self.assertEqual(self.submit([event]).status_code, 422)
        self.assertEqual(self.count(), 0)

    def test_batch_failure_is_atomic(self):
        response = self.submit([self.event(1), self.event(2, message="not allowed")])
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.count(), 0)
        self.assertEqual(self.submit([self.event(), self.event()]).status_code, 422)
        self.assertEqual(self.submit([]).status_code, 422)
        self.assertEqual(self.submit([self.event(i) for i in range(9)]).status_code, 422)

    def test_raw_and_chunked_body_are_bounded_before_parsing(self):
        headers = {**self.headers, "Content-Type": "application/json"}
        too_large = b" " * (diagnostics.MAX_BODY_BYTES + 1)
        self.assertEqual(self.client.post("/client/diagnostics", content=too_large, headers=headers).status_code, 413)
        chunks = (b" " * 4096 for _ in range(9))
        self.assertEqual(self.client.post("/client/diagnostics", content=chunks, headers=headers).status_code, 413)
        self.assertEqual(self.count(), 0)

    def test_non_json_content_type_and_malformed_json(self):
        self.assertEqual(self.client.post("/client/diagnostics", content=b"{}", headers=self.headers).status_code, 415)
        response = self.client.post("/client/diagnostics", content=b"{bad", headers={**self.headers, "Content-Type": "application/json"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json(), {"detail": "invalid_client_diagnostic"})

    def test_retention_and_limit_do_not_remove_other_owner_rows(self):
        now = int(time.time())
        diagnostics.store_batch(self.connect, 2, [self.event(900)], now)
        diagnostics.store_batch(self.connect, 1, [self.event(901)], now - diagnostics.RETENTION_SECONDS - 1)
        for offset in range(0, 136, 8):
            events = [self.event(i) for i in range(offset, offset + 8)]
            self.assertEqual(self.submit(events).status_code, 200)
        self.assertEqual(self.count(), diagnostics.MAX_PER_USER)
        self.assertEqual(self.count(2), 1)
        with closing(self.connect()) as db:
            self.assertIsNone(db.execute("SELECT 1 FROM client_diagnostic_events WHERE user_id=1 AND event_id=?",
                                         (self.event(901)["event_id"],)).fetchone())

    def test_initialize_is_idempotent(self):
        self.submit([self.event()])
        diagnostics.initialize(self.connect)
        self.assertEqual(self.count(), 1)


if __name__ == "__main__":
    unittest.main()
