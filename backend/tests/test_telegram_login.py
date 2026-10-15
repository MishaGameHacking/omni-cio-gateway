"""Regression tests for the Telegram browser-to-Android login handoff."""
from __future__ import annotations

import json
import re
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt.utils import base64url_encode

from backend import telegram_browser_app as backend


def integer_b64(value: int) -> str:
    length = max(1, (value.bit_length() + 7) // 8)
    return base64url_encode(value.to_bytes(length, "big")).decode("ascii")


class TelegramLoginTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.previous_database = backend.legacy.DATABASE_PATH
        self.previous_jwks = backend.TELEGRAM_JWKS_PATH
        root = Path(self.temp_directory.name)
        backend.legacy.DATABASE_PATH = root / "test.db"
        backend.TELEGRAM_JWKS_PATH = root / "telegram-jwks.json"

        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        numbers = self.private_key.public_key().public_numbers()
        backend.TELEGRAM_JWKS_PATH.write_text(
            json.dumps(
                {
                    "keys": [
                        {
                            "kty": "RSA",
                            "kid": "test-key",
                            "alg": "RS256",
                            "use": "sig",
                            "key_ops": ["verify"],
                            "n": integer_b64(numbers.n),
                            "e": integer_b64(numbers.e),
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        backend.legacy.init_db()
        self.client = TestClient(backend.app)

    def tearDown(self) -> None:
        self.client.close()
        backend.legacy.DATABASE_PATH = self.previous_database
        backend.TELEGRAM_JWKS_PATH = self.previous_jwks
        self.temp_directory.cleanup()

    def start_login(self) -> tuple[str, str]:
        response = self.client.get("/auth/telegram/start")
        self.assertEqual(response.status_code, 200)
        self.assertIn("https://oauth.telegram.org/js/telegram-login.js?3", response.text)
        self.assertIn("Продолжить в Telegram", response.text)
        self.assertNotIn(backend.legacy.TELEGRAM_CLIENT_SECRET, response.text)
        self.assertIn("same-origin-allow-popups", response.headers["cross-origin-opener-policy"])
        self.assertIn("no-store", response.headers["cache-control"])
        self.assertIn("https://oauth.telegram.org", response.headers["content-security-policy"])
        state_match = re.search(r"const state = \"([^\"]+)\";", response.text)
        nonce_match = re.search(r"const loginNonce = \"([^\"]+)\";", response.text)
        self.assertIsNotNone(state_match)
        self.assertIsNotNone(nonce_match)
        state = state_match.group(1)
        nonce = nonce_match.group(1)
        with backend.closing(backend.legacy.connect()) as db:
            row = db.execute(
                "SELECT verifier FROM login_transactions WHERE state = ?",
                (state,),
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["verifier"], nonce)
        return state, nonce

    def token(self, nonce: str, **overrides) -> str:
        now = int(time.time())
        claims = {
            "iss": backend.legacy.TELEGRAM_ISSUER,
            "aud": backend.legacy.TELEGRAM_CLIENT_ID,
            "sub": "stable-telegram-sub",
            "id": 1234567,
            "name": "Test User",
            "preferred_username": "testuser",
            "picture": "https://example.invalid/avatar.png",
            "iat": now,
            "exp": now + 300,
            "nonce": nonce,
        }
        claims.update(overrides)
        return jwt.encode(
            claims,
            self.private_key,
            algorithm="RS256",
            headers={"kid": "test-key"},
        )

    def complete(self, state: str, token: str, origin: str | None = None):
        headers = {"Origin": origin or backend.legacy.BACKEND_PUBLIC_URL}
        return self.client.post(
            "/auth/telegram/complete",
            json={"state": state, "id_token": token},
            headers=headers,
        )

    def test_successful_browser_login_code_can_be_exchanged_once(self) -> None:
        state, nonce = self.start_login()
        with patch.object(backend.legacy.httpx, "Client") as network_client:
            callback = self.complete(state, self.token(nonce))
        network_client.assert_not_called()
        self.assertEqual(callback.status_code, 200)
        deep_link = callback.json()["deep_link"]
        self.assertTrue(deep_link.startswith("analystai://auth?code="))
        login_code = parse_qs(urlsplit(deep_link).query)["code"][0]

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

    def test_nonce_mismatch_fails_closed_and_consumes_transaction(self) -> None:
        state, nonce = self.start_login()
        failed = self.complete(state, self.token("different-nonce"))
        self.assertEqual(failed.status_code, 401)
        self.assertIn("error=telegram_invalid_token", failed.json()["deep_link"])
        replay = self.complete(state, self.token(nonce))
        self.assertEqual(replay.status_code, 400)
        self.assertIn("error=telegram_expired", replay.json()["deep_link"])

    def test_signature_tampering_is_rejected(self) -> None:
        state, nonce = self.start_login()
        token = self.token(nonce)
        header, payload, signature = token.split(".")
        replacement = ("A" if signature[0] != "A" else "B") + signature[1:]
        failed = self.complete(state, ".".join((header, payload, replacement)))
        self.assertEqual(failed.status_code, 401)
        self.assertIn("telegram_invalid_token", failed.json()["deep_link"])

    def test_unknown_signing_key_is_reported_without_network_fallback(self) -> None:
        state, nonce = self.start_login()
        token = jwt.encode(
            {
                "iss": backend.legacy.TELEGRAM_ISSUER,
                "aud": backend.legacy.TELEGRAM_CLIENT_ID,
                "sub": "subject",
                "iat": int(time.time()),
                "exp": int(time.time()) + 300,
                "nonce": nonce,
            },
            self.private_key,
            algorithm="RS256",
            headers={"kid": "rotated-key"},
        )
        with patch.object(backend.legacy.httpx, "Client") as network_client:
            failed = self.complete(state, token)
        network_client.assert_not_called()
        self.assertEqual(failed.status_code, 503)
        self.assertIn("telegram_unavailable", failed.json()["deep_link"])

    def test_wrong_origin_is_rejected_without_consuming_state(self) -> None:
        state, nonce = self.start_login()
        rejected = self.complete(state, self.token(nonce), origin="https://attacker.invalid")
        self.assertEqual(rejected.status_code, 400)
        accepted = self.complete(state, self.token(nonce))
        self.assertEqual(accepted.status_code, 200)

    def test_expired_token_is_rejected(self) -> None:
        state, nonce = self.start_login()
        now = int(time.time())
        failed = self.complete(state, self.token(nonce, iat=now - 900, exp=now - 300))
        self.assertEqual(failed.status_code, 401)

    def test_denied_legacy_callback_still_returns_actionable_android_link(self) -> None:
        response = self.client.get(
            "/auth/telegram/callback",
            params={"error": "access_denied", "state": "any"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("analystai://auth?error=telegram_denied", response.text)
        self.assertIn("Открыть Analyst AI", response.text)
        self.assertIn("no-store", response.headers["cache-control"])


if __name__ == "__main__":
    unittest.main()
