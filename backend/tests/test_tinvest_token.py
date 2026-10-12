"""T-Invest token verification regressions; all upstream calls are mocked."""
from __future__ import annotations

import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from backend import app as backend


class TInvestTokenTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.old_path = backend.DATABASE_PATH
        backend.DATABASE_PATH = Path(self.directory.name) / "tinvest-test.db"
        backend.init_db()
        self.session_token = "session-for-tinvest-tests"
        with closing(backend.connect()) as db:
            cursor = db.execute(
                """INSERT INTO users(
                       telegram_sub, telegram_id, created_at, updated_at
                   ) VALUES (?, ?, ?, ?)""",
                ("telegram-sub-test", "12345", 1, 1),
            )
            self.user_id = cursor.lastrowid
            db.execute(
                "INSERT INTO sessions(token_hash, user_id, expires_at) VALUES (?, ?, ?)",
                (backend.hash_token(self.session_token), self.user_id, 4102444800),
            )
            db.commit()
        self.client = TestClient(backend.app)

    def tearDown(self) -> None:
        self.client.close()
        backend.DATABASE_PATH = self.old_path
        self.directory.cleanup()

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.session_token}"}

    def stored_token(self) -> bytes | None:
        with closing(backend.connect()) as db:
            row = db.execute(
                "SELECT tinvest_token_encrypted FROM users WHERE id = ?", (self.user_id,),
            ).fetchone()
        return row["tinvest_token_encrypted"]

    def call(self, response: httpx.Response | None = None,
             exception: Exception | None = None) -> tuple:
        with patch.object(backend.httpx, "Client") as patched:
            client = patched.return_value.__enter__.return_value
            client.post.return_value = response
            client.post.side_effect = exception
            result = self.client.post(
                "/tinvest/token",
                headers=self.headers,
                json={"token": "test-read-only-token"},
            )
            return result, patched, client

    def test_scoped_certificate_bundle_matches_trusted_root(self) -> None:
        context = backend.tinvest_ssl_context()
        self.assertTrue(context.verify_mode)
        self.assertTrue(context.check_hostname)
        self.assertEqual(backend.TINVEST_ROOT_CA_SHA256,
                         "d26d2d0231b7c39f92cc738512ba54103519e4405d68b5bd703e9788ca8ecf31")

    def test_validated_token_is_stored_encrypted(self) -> None:
        response, patched, client = self.call(httpx.Response(200, json={"accounts": []}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"connected": True})
        encrypted = self.stored_token()
        self.assertIsNotNone(encrypted)
        self.assertNotEqual(encrypted, b"test-read-only-token")
        self.assertEqual(backend.FERNET.decrypt(encrypted), b"test-read-only-token")
        request_headers = client.post.call_args.kwargs["headers"]
        self.assertEqual(request_headers["Authorization"], "Bearer test-read-only-token")
        self.assertEqual(client.post.call_args.args[0], backend.TINVEST_ACCOUNTS_URL)
        self.assertNotEqual(patched.call_args.kwargs["verify"], False)

    def test_rejected_tinvest_token_is_not_confused_with_session_expiry(self) -> None:
        for code in (401, 403):
            with self.subTest(code=code):
                response, _, _ = self.call(httpx.Response(code))
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()["detail"], "invalid_tinvest_token")
                self.assertIsNone(self.stored_token())

    def test_tinvest_errors_do_not_destroy_previously_saved_token(self) -> None:
        good, _, _ = self.call(httpx.Response(200, json={"accounts": []}))
        self.assertEqual(good.status_code, 200)
        existing = self.stored_token()
        failure, _, _ = self.call(httpx.Response(503))
        self.assertEqual(failure.status_code, 503)
        self.assertEqual(failure.json()["detail"], "tinvest_upstream_unavailable")
        self.assertEqual(self.stored_token(), existing)

    def test_connection_errors_are_classified_without_leaking_token(self) -> None:
        cases = [
            (httpx.ConnectError("certificate verify failed"), 503, "tinvest_tls_error"),
            (httpx.ConnectError("connection refused"), 503, "tinvest_connection_failed"),
            (httpx.ReadTimeout("timed out"), 504, "tinvest_timeout"),
        ]
        for problem, expected_status, expected_detail in cases:
            with self.subTest(problem=type(problem).__name__, detail=expected_detail):
                response, _, _ = self.call(exception=problem)
                self.assertEqual(response.status_code, expected_status)
                self.assertEqual(response.json()["detail"], expected_detail)
                self.assertNotIn("test-read-only-token", response.text)
                self.assertIsNone(self.stored_token())

    def test_unexpected_upstream_response_is_not_stored(self) -> None:
        result, _, _ = self.call(httpx.Response(200, json={"message": "ok"}))
        self.assertEqual(result.status_code, 502)
        self.assertEqual(result.json()["detail"], "tinvest_invalid_response")
        self.assertIsNone(self.stored_token())

    def test_rate_limit_is_distinct_from_invalid_token(self) -> None:
        result, _, _ = self.call(httpx.Response(429))
        self.assertEqual(result.status_code, 503)
        self.assertEqual(result.json()["detail"], "tinvest_rate_limited")

    def test_invalid_analyst_session_is_401(self) -> None:
        response = self.client.post(
            "/tinvest/token",
            json={"token": "anything"},
            headers={"Authorization": "Bearer invalid-session"},
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "invalid_session")


if __name__ == "__main__":
    unittest.main()
