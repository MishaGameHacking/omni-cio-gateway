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
        state = "s" * 32
        nonce = "n" * 32
        self.add_browser_transaction(state, nonce)

        with patch.object(
            backend,
            "verify_browser_id_token",
            return_value=self.claims(5),
        ):
            response = self.client.post(
                "/auth/telegram/complete",
                json={"state": state, "id_token": "t" * 64},
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

    def test_android_password_entry_keeps_the_prebound_single_owner_boundary(self) -> None:
        from backend.owner_access import DENIED, OwnerIdentity, bind_owner
        from backend.owner_password import OwnerAuthError, OwnerPasswordStore, initialize
        from backend.tests.test_owner_password import create_schema

        activity = (
            self.root / "app" / "src" / "main" / "java" / "ru" / "omnicio" / "app"
            / "MainActivity.kt"
        ).read_text(encoding="utf-8")
        self.assertIn("OwnerAccessScreen(", activity)
        self.assertIn("OwnerDeviceUnlock(", activity)
        self.assertNotIn("TelegramLoginScreen(", activity)
        self.assertNotIn("exchangeTelegramCode(", activity)

        # The new entry screen must not turn this private installation into
        # first-visitor signup: only the server-bound owner may be created.
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "owner-password.db"

            def connect():
                db = sqlite3.connect(database)
                db.row_factory = sqlite3.Row
                return db

            create_schema(connect)
            identity = OwnerIdentity("prebound-private-owner")
            bind_owner(connect, identity)
            initialize(connect)
            bind_owner(connect, identity)
            bootstrap = "synthetic-private-installation-bootstrap-0123456789"
            store = OwnerPasswordStore(connect, session_ttl=600,
                                       bootstrap_secret=lambda: bootstrap)
            password = "synthetic owner password"
            with self.assertRaises(OwnerAuthError) as denied:
                store.setup(password)
            self.assertEqual(denied.exception.status, 401)
            with closing(connect()) as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM users").fetchone()[0], 0)

            session = store.setup(password, bootstrap=bootstrap)
            self.assertTrue(session["access_token"])
            self.assertEqual(store.login(password)["user"]["telegram_id"], identity.subject)
            with closing(connect()) as db:
                self.assertEqual(
                    [row[0] for row in db.execute("SELECT telegram_sub FROM users")],
                    [identity.subject],
                )
                with self.assertRaisesRegex(sqlite3.IntegrityError, DENIED):
                    db.execute(
                        "INSERT INTO users(telegram_sub,created_at,updated_at) VALUES (?,1,1)",
                        ("unbound-second-owner",),
                    )

    def test_owner_rules_record_closed_free_installation(self) -> None:
        rules = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        # Historical entries may describe the retired five-user installation.
        # Validate the current owner contract without changing admission tests.
        current = rules.split("## Закрытая личная установка\n", 1)[1].split("\n## ", 1)[0]
        self.assertIn("одного ранее подтверждённого владельца", current)
        self.assertIn("по точной подтверждённой идентичности", current)
        self.assertIn("не по принципу «первый зарегистрировавшийся»", current)
        self.assertIn("Сохранить owner binding", current)
        self.assertIn("Один владелец не означает один брокерский счёт или одну сессию", current)
        self.assertIn("не будет оплат, подписок, покупок", current)


if __name__ == "__main__":
    unittest.main()

