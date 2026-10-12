"""Regression tests for the Telegram browser-to-Android login handoff."""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient

from backend import app as backend


class TelegramLoginTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.previous_database = backend.DATABASE_PATH
        backend.DATABASE_PATH = Path(self.temp_directory.name) / "test.db"
        backend.init_db()
        self.client = TestClient(backend.app)

    def tearDown(self) -> None:
        self.client.close()
        backend.DATABASE_PATH = self.previous_database
        self.temp_directory.cleanup()

    def start_login(self) -> str:
        response = self.client.get("/auth/telegram/start", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        url = urlsplit(response.headers["location"])
        self.assertEqual(url.netloc, "oauth.telegram.org")
        params = parse_qs(url.query)
        self.assertEqual(params["redirect_uri"], [backend.TELEGRAM_REDIRECT_URI])
        self.assertEqual(params["response_type"], ["code"])
        self.assertEqual(params["code_challenge_method"], ["S256"])
        return params["state"][0]

    def test_denied_login_returns_actionable_android_link(self) -> None:
        response = self.client.get(
            "/auth/telegram/callback",
            params={"error": "access_denied", "state": "any"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("analystai://auth?error=telegram_denied", response.text)
        self.assertIn("Открыть Analyst AI", response.text)
        self.assertIn("no-store", response.headers["cache-control"])

    def test_invalid_or_expired_state_returns_to_android(self) -> None:
        response = self.client.get(
            "/auth/telegram/callback",
            params={"code": "unexpected", "state": "not-in-database"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("analystai://auth?error=telegram_expired", response.text)

    def test_successful_login_code_can_be_exchanged_once(self) -> None:
        state = self.start_login()
        with patch.object(backend.httpx, "Client") as http:
            client = http.return_value.__enter__.return_value
            client.post.return_value.status_code = 200
            client.post.return_value.json.return_value = {"id_token": "signed.jwt"}
            with patch.object(backend.jwks_client, "get_signing_key_from_jwt") as key:
                key.return_value.key = "test-public-key"
                with patch.object(
                    backend.jwt,
                    "decode",
                    return_value={
                        "sub": "stable-telegram-sub",
                        "id": 1234567,
                        "name": "Test User",
                        "preferred_username": "testuser",
                    },
                ):
                    callback = self.client.get(
                        "/auth/telegram/callback",
                        params={"code": "telegram-oauth-code", "state": state},
                    )

        self.assertEqual(callback.status_code, 200)
        self.assertIn("window.location.replace", callback.text)
        match = re.search(r'href="analystai://auth\\?code=([^"]+)"', callback.text)
        self.assertIsNotNone(match)
        login_code = match.group(1)
        exchange = self.client.post("/auth/session", json={"code": login_code})
        self.assertEqual(exchange.status_code, 200)
        session = exchange.json()
        self.assertEqual(session["user"]["telegram_id"], "1234567")
        profile = self.client.get(
            "/me",
            headers={"Authorization": "Bearer " + session["access_token"]},
        )
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.json()["username"], "testuser")
        self.assertEqual(
            self.client.post("/auth/session", json={"code": login_code}).status_code,
            401,
        )

    def test_token_exchange_failure_is_reported_in_android(self) -> None:
        state = self.start_login()
        with patch.object(backend.httpx, "Client") as http:
            http.return_value.__enter__.return_value.post.return_value.status_code = 401
            callback = self.client.get(
                "/auth/telegram/callback",
                params={"code": "invalid-token", "state": state},
            )
        self.assertEqual(callback.status_code, 401)
        self.assertIn("analystai://auth?error=telegram_exchange_failed", callback.text)


if __name__ == "__main__":
    unittest.main()
