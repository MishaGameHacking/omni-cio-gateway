"""Closed-installation account-cap and cost-boundary regression tests."""
from __future__ import annotations

import re
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import telegram_browser_app as backend


class PrivateUserLimitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.previous_database = backend.legacy.DATABASE_PATH
        backend.legacy.DATABASE_PATH = (
            Path(self.temp_directory.name) / "private-user-limit.db"
        )
        backend.legacy.init_db()
        self.client = TestClient(backend.app)

    def tearDown(self) -> None:
        self.client.close()
        backend.legacy.DATABASE_PATH = self.previous_database
        self.temp_directory.cleanup()

    @staticmethod
    def claims(index: int) -> dict:
        return {
            "sub": f"private-user-{index}",
            "id": 1000 + index,
            "name": f"Private User {index}",
            "preferred_username": f"private_user_{index}",
        }

    def issue_for_existing_or_new(self, index: int) -> str:
        return backend._issue_login_code(self.claims(index))

    def add_browser_transaction(self, state: str, nonce: str) -> None:
        with closing(backend.legacy.connect()) as db:
            db.execute(
                """
                INSERT INTO login_transactions(state, verifier, created_at)
                VALUES (?, ?, strftime('%s', 'now'))
                """,
                (state, nonce),
            )
            db.commit()

    def user_count(self) -> int:
        with closing(backend.legacy.connect()) as db:
            row = db.execute("SELECT COUNT(*) AS count FROM users").fetchone()
        return int(row["count"])

    def fill_private_installation(self) -> None:
        for index in range(backend.legacy.MAX_PRIVATE_USERS):
            self.issue_for_existing_or_new(index)
        self.assertEqual(self.user_count(), 5)

    def test_database_trigger_blocks_the_sixth_unique_account(self) -> None:
        self.fill_private_installation()

        with self.assertRaisesRegex(
            sqlite3.IntegrityError,
            backend.legacy.PRIVATE_USER_LIMIT_ERROR,
        ):
            self.issue_for_existing_or_new(5)

        self.assertEqual(self.user_count(), 5)

    def test_existing_account_can_sign_in_again_after_limit_is_full(self) -> None:
        self.fill_private_installation()

        code = self.issue_for_existing_or_new(0)

        self.assertTrue(code)
        self.assertEqual(self.user_count(), 5)

    def test_browser_login_returns_actionable_private_limit_response(self) -> None:
        self.fill_private_installation()
        self.add_browser_transaction("sixth-state", "sixth-nonce")

        with patch.object(
            backend,
            "verify_browser_id_token",
            return_value=self.claims(5),
        ):
            response = self.client.post(
                "/auth/telegram/complete",
                json={"state": "sixth-state", "id_token": "validated-by-test"},
                headers={"Origin": backend.legacy.BACKEND_PUBLIC_URL},
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["deep_link"],
            "analystai://auth?error=private_access_full",
        )
        self.assertIn("пять аккаунтов", response.json()["message"])
        self.assertEqual(self.user_count(), 5)

    def test_direct_insert_cannot_bypass_the_limit(self) -> None:
        self.fill_private_installation()

        with closing(backend.legacy.connect()) as db:
            with self.assertRaisesRegex(
                sqlite3.IntegrityError,
                backend.legacy.PRIVATE_USER_LIMIT_ERROR,
            ):
                db.execute(
                    """
                    INSERT INTO users(
                        telegram_sub, telegram_id, created_at, updated_at
                    ) VALUES (?, ?, 1, 1)
                    """,
                    ("direct-sixth-user", "direct-sixth-user"),
                )


class PrivateInstallationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[2]

    def test_capacity_is_fixed_to_five_accounts(self) -> None:
        self.assertEqual(backend.legacy.MAX_PRIVATE_USERS, 5)
        app_source = (self.root / "backend" / "app.py").read_text(encoding="utf-8")
        self.assertIn("CREATE TRIGGER IF NOT EXISTS users_private_limit", app_source)
        self.assertIn("PRIVATE_USER_LIMIT_DEEP_LINK_ERROR", app_source)

    def test_deployment_keeps_one_shared_backend_worker(self) -> None:
        deploy = (
            self.root
            / ".github"
            / "scripts"
            / "deploy_moscow_telegram_browser_auth_remote.sh"
        ).read_text(encoding="utf-8")
        self.assertIn("--workers 1", deploy)
        self.assertIsNone(re.search(r"--workers\s+(?:[2-9]|\d{2,})\b", deploy))

    def test_runtime_manifests_do_not_add_payment_dependencies(self) -> None:
        runtime_manifests = (
            self.root / "backend" / "requirements.txt",
            self.root / "app" / "build.gradle.kts",
            self.root / "gradle" / "libs.versions.toml",
        )
        forbidden = ("billingclient", "stripe", "yookassa", "revenuecat")
        for path in runtime_manifests:
            lowered = path.read_text(encoding="utf-8").lower()
            for token in forbidden:
                self.assertNotIn(token, lowered, f"{token} unexpectedly present in {path}")

    def test_android_explains_when_the_private_installation_is_full(self) -> None:
        activity = (
            self.root
            / "app"
            / "src"
            / "main"
            / "java"
            / "ru"
            / "omnicio"
            / "app"
            / "MainActivity.kt"
        ).read_text(encoding="utf-8")
        self.assertIn('"private_access_full"', activity)
        self.assertIn("ограничен пятью аккаунтами", activity)

    def test_owner_rules_record_closed_free_installation(self) -> None:
        rules = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("максимум для пяти уникальных Telegram-аккаунтов", rules)
        self.assertIn("не будет оплат, подписок, покупок", rules)
        self.assertIn("один общий процесс обслуживает от одного до пяти аккаунтов", rules)


if __name__ == "__main__":
    unittest.main()
