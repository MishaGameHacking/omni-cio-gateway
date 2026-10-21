from __future__ import annotations

import os
import tempfile
import unittest
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("TELEGRAM_CLIENT_ID", "123456")
os.environ.setdefault("TELEGRAM_CLIENT_SECRET", "test-only")
os.environ.setdefault("BACKEND_PUBLIC_URL", "https://example.invalid")
os.environ.setdefault("FERNET_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
os.environ["ANALYSIS_SCHEDULER_ENABLED"] = "false"
os.environ.pop("TIMEWEB_AI_TOKEN", None)
os.environ.pop("TIMEWEB_CLOUD_API_KEY", None)

from backend import app as backend  # noqa: E402
from backend import autonomous_ai as ai  # noqa: E402


def sample_snapshot(*, cash_share: float = 20.0, stock_share: float = 35.0) -> dict:
    fund_share = 0.0 if stock_share + cash_share > 85.0 else 15.0
    bond_share = max(0.0, 100.0 - stock_share - cash_share - fund_share)
    return {
        "currency": "RUB",
        "totalValue": {
            "value": {"units": 100_000, "nano": 0},
            "currency": "RUB",
        },
        "expectedYieldAmount": {
            "value": {"units": 5_000, "nano": 0},
            "currency": "RUB",
        },
        "expectedYieldPercent": {"units": 5, "nano": 0},
        "accounts": [
            {
                "id": "account-1",
                "name": "Брокерский счёт",
                "totalValue": {
                    "value": {"units": 100_000, "nano": 0},
                    "currency": "RUB",
                },
                "expectedYieldPercent": {"units": 5, "nano": 0},
                "positions": [
                    {
                        "id": "share-1",
                        "title": "Проверенный актив",
                        "ticker": "TEST",
                        "quantity": {"units": 10, "nano": 0},
                        "currentValue": {
                            "value": {"units": int(stock_share * 1000), "nano": 0},
                            "currency": "RUB",
                        },
                        "expectedYieldPercent": None,
                    },
                    {
                        "id": "cash:RUB",
                        "title": "Рубль",
                        "ticker": "RUB",
                        "quantity": {"units": 20_000, "nano": 0},
                        "currentValue": {
                            "value": {"units": 20_000, "nano": 0},
                            "currency": "RUB",
                        },
                        "expectedYieldPercent": None,
                    },
                ],
            }
        ],
        "allocations": [
            {
                "title": "Акции",
                "sharePercent": {"units": int(stock_share), "nano": 0},
            },
            {
                "title": "Облигации",
                "sharePercent": {"units": int(bond_share), "nano": 0},
            },
            {
                "title": "Фонды",
                "sharePercent": {"units": int(fund_share), "nano": 0},
            },
            {
                "title": "Валюта и деньги",
                "sharePercent": {"units": int(cash_share), "nano": 0},
            },
        ],
    }


class AutonomousAITests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        backend.DATABASE_PATH = Path(self.temp_dir.name) / "backend.sqlite3"
        backend.init_db()
        ai.init_autonomous_db()
        with closing(backend.connect()) as db:
            cursor = db.execute(
                """
                INSERT INTO users(
                    telegram_sub, telegram_id, name, username, picture,
                    tinvest_token_encrypted, created_at, updated_at
                ) VALUES ('sub-1', '1', 'Test', NULL, NULL, ?, 1, 1)
                """,
                (b"encrypted-placeholder",),
            )
            self.user_id = int(cursor.lastrowid)
            db.commit()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def user_row(self):
        with closing(backend.connect()) as db:
            return db.execute("SELECT * FROM users WHERE id = ?", (self.user_id,)).fetchone()

    def test_manual_refresh_does_not_invent_a_transaction(self) -> None:
        with patch.object(ai, "get_tinvest_portfolio", return_value=sample_snapshot()):
            result = ai.run_user_analysis(
                self.user_id,
                now=datetime(2026, 10, 12, 9, 0, tzinfo=UTC),
            )
        self.assertEqual(result["state"], "skipped")
        self.assertIsNone(result["card_id"])
        payload = ai.feed(limit=10, user=self.user_row())
        self.assertEqual(payload["unread_count"], 0)
        self.assertEqual(payload["cards"], [])

    def test_same_material_snapshot_is_skipped_outside_schedule(self) -> None:
        snapshot = sample_snapshot()
        with patch.object(ai, "get_tinvest_portfolio", return_value=snapshot):
            ai.run_user_analysis(
                self.user_id,
                now=datetime(2026, 10, 12, 9, 0, tzinfo=UTC),
            )
            result = ai.run_user_analysis(
                self.user_id,
                now=datetime(2026, 10, 12, 12, 0, tzinfo=UTC),
            )
        self.assertEqual(result["state"], "skipped")

    def test_profile_and_ideas_are_algorithmic_not_specific_security_advice(self) -> None:
        user = self.user_row()
        profile = ai.update_profile(
            ai.ProfileUpdate(
                risk_level="moderate",
                horizon="medium",
                allowed_markets=["RU"],
                max_position_percent=30,
                min_cash_percent=5,
                notify_critical=True,
                notify_briefs=True,
            ),
            user=user,
        )
        self.assertTrue(profile["configured"])
        ai._save_snapshot(self.user_id, sample_snapshot(cash_share=20, stock_share=20))
        payload = ai.ideas(user=user)
        self.assertEqual(payload["state"], "ready")
        self.assertGreater(len(payload["ideas"]), 0)
        self.assertIn("asset_class", payload["ideas"][0])
        self.assertNotIn("ticker", payload["ideas"][0])

    def test_critical_concentration_bypasses_cooldown(self) -> None:
        snapshot = sample_snapshot(cash_share=5, stock_share=90)
        with patch.object(ai, "get_tinvest_portfolio", return_value=snapshot):
            result = ai.run_user_analysis(
                self.user_id,
                now=datetime(2026, 10, 12, 12, 0, tzinfo=UTC),
            )
        self.assertEqual(result["tier"], "premium")
        self.assertEqual(result["reason"], "risk_event")

    def test_unchanged_critical_risk_is_not_repeated_within_six_hours(self) -> None:
        snapshot = sample_snapshot(cash_share=5, stock_share=90)
        with patch.object(ai, "get_tinvest_portfolio", return_value=snapshot):
            first = ai.run_user_analysis(
                self.user_id,
                now=datetime(2026, 10, 12, 12, 0, tzinfo=UTC),
            )
            second = ai.run_user_analysis(
                self.user_id,
                now=datetime(2026, 10, 12, 13, 0, tzinfo=UTC),
            )
        self.assertEqual(first["reason"], "risk_event")
        self.assertEqual(second["state"], "skipped")


if __name__ == "__main__":
    unittest.main()
