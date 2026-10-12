"""Real-portfolio aggregation regressions; T-Invest calls are mocked."""
from __future__ import annotations

import tempfile
import unittest
from contextlib import closing
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from backend import app as backend
from backend import tinvest_portfolio


class TInvestPortfolioTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.old_path = backend.DATABASE_PATH
        backend.DATABASE_PATH = Path(self.directory.name) / "portfolio-test.db"
        backend.init_db()
        self.session_token = "session-for-portfolio-tests"
        with closing(backend.connect()) as db:
            cursor = db.execute(
                """INSERT INTO users(
                       telegram_sub, telegram_id, tinvest_token_encrypted,
                       created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?)""",
                (
                    "portfolio-sub",
                    "777",
                    backend.FERNET.encrypt(b"read-only-token"),
                    1,
                    1,
                ),
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

    @staticmethod
    def decimal_value(payload: dict[str, int]) -> Decimal:
        return Decimal(payload["units"]) + (
            Decimal(payload["nano"]) / Decimal(1_000_000_000)
        )

    def test_selected_currency_is_requested_and_returned_for_all_accounts(self) -> None:
        calls: list[tuple[str, dict]] = []

        def response_for(url: str, **kwargs):
            body = kwargs["json"]
            calls.append((url, body))
            if url == backend.TINVEST_ACCOUNTS_URL:
                return httpx.Response(
                    200,
                    json={
                        "accounts": [
                            {
                                "id": "main",
                                "name": "VIP Client",
                                "status": "ACCOUNT_STATUS_OPEN",
                                "accessLevel": "ACCOUNT_ACCESS_LEVEL_FULL_ACCESS",
                            },
                            {
                                "id": "iis",
                                "name": "ИИС",
                                "status": "ACCOUNT_STATUS_OPEN",
                                "accessLevel": "ACCOUNT_ACCESS_LEVEL_READ_ONLY",
                            },
                        ]
                    },
                )
            if url == tinvest_portfolio.TINVEST_PORTFOLIO_URL:
                self.assertEqual(body["currency"], "EUR")
                if body["accountId"] == "main":
                    return httpx.Response(
                        200,
                        json={
                            "totalAmountPortfolio": {
                                "currency": "eur",
                                "units": "52",
                                "nano": 650_000_000,
                            },
                            # These daily values intentionally differ from the
                            # all-time values and must not be shown as "за всё время".
                            "dailyYield": {
                                "currency": "eur",
                                "units": "0",
                                "nano": -370_000_000,
                            },
                            "dailyYieldRelative": {"units": "0", "nano": -100_000_000},
                            "expectedYield": {"units": "0", "nano": -680_000_000},
                            "totalAmountShares": {
                                "currency": "eur",
                                "units": "3",
                                "nano": 0,
                            },
                            "totalAmountCurrencies": {
                                "currency": "eur",
                                "units": "49",
                                "nano": 650_000_000,
                            },
                            "positions": [],
                        },
                    )
                return httpx.Response(
                    200,
                    json={
                        "totalAmountPortfolio": {
                            "currency": "eur",
                            "units": "10",
                            "nano": 570_000_000,
                        },
                        "dailyYield": {
                            "currency": "eur",
                            "units": "0",
                            "nano": -590_000_000,
                        },
                        "dailyYieldRelative": {"units": "0", "nano": -500_000_000},
                        "expectedYield": {"units": "5", "nano": 280_000_000},
                        "totalAmountShares": {
                            "currency": "eur",
                            "units": "3",
                            "nano": 20_000_000,
                        },
                        "totalAmountCurrencies": {
                            "currency": "eur",
                            "units": "7",
                            "nano": 550_000_000,
                        },
                        "positions": [
                            {
                                "instrumentUid": "sber-uid",
                                "figi": "BBG004730N88",
                                "ticker": "SBER",
                                "instrumentType": "share",
                                "quantity": {"units": "1", "nano": 0},
                                "currentPrice": {
                                    "currency": "rub",
                                    "units": "285",
                                    "nano": 350_000_000,
                                },
                            }
                        ],
                    },
                )
            if url == tinvest_portfolio.TINVEST_POSITIONS_URL:
                if body["accountId"] == "main":
                    return httpx.Response(
                        200,
                        json={
                            "money": [
                                {"currency": "rub", "units": "5000", "nano": 80_000_000}
                            ]
                        },
                    )
                return httpx.Response(
                    200,
                    json={
                        "money": [
                            {"currency": "rub", "units": "718", "nano": 610_000_000}
                        ]
                    },
                )
            raise AssertionError(f"Unexpected T-Invest URL: {url}")

        with patch.object(backend.httpx, "Client") as patched:
            upstream = patched.return_value.__enter__.return_value
            upstream.post.side_effect = response_for
            response = self.client.get(
                "/tinvest/portfolio?currency=EUR",
                headers=self.headers,
            )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["currency"], "EUR")
        self.assertEqual(payload["totalValue"]["currency"], "EUR")
        self.assertEqual(payload["totalValue"]["value"], {"units": 63, "nano": 220_000_000})
        self.assertEqual(len(payload["accounts"]), 2)
        self.assertEqual(payload["accounts"][0]["name"], "VIP Client")
        self.assertEqual(
            self.decimal_value(payload["accounts"][1]["expectedYieldPercent"]),
            Decimal("5.28"),
        )
        self.assertEqual(payload["accounts"][1]["positions"][0]["ticker"], "SBER")
        self.assertEqual(
            payload["accounts"][1]["positions"][0]["currentValue"]["currency"],
            "RUB",
        )

        # Absolute result is recovered from current value + all-time percentage;
        # it must not equal the sum of dailyYield values (-0.96 EUR).
        absolute_result = self.decimal_value(payload["expectedYieldAmount"]["value"])
        relative_result = self.decimal_value(payload["expectedYieldPercent"])
        self.assertAlmostEqual(float(absolute_result), 0.169635178, places=8)
        self.assertAlmostEqual(float(relative_result), 0.269047101, places=8)
        self.assertNotAlmostEqual(float(absolute_result), -0.96, places=2)

        portfolio_calls = [
            body for url, body in calls if url == tinvest_portfolio.TINVEST_PORTFOLIO_URL
        ]
        self.assertEqual([call["currency"] for call in portfolio_calls], ["EUR", "EUR"])

    def test_missing_connection_does_not_call_tinvest(self) -> None:
        with closing(backend.connect()) as db:
            db.execute(
                "UPDATE users SET tinvest_token_encrypted = NULL WHERE id = ?",
                (self.user_id,),
            )
            db.commit()
        with patch.object(backend.httpx, "Client") as patched:
            response = self.client.get("/tinvest/portfolio", headers=self.headers)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "tinvest_not_connected")
        patched.assert_not_called()

    def test_unsupported_currency_is_rejected_before_upstream_call(self) -> None:
        with patch.object(backend.httpx, "Client") as patched:
            response = self.client.get(
                "/tinvest/portfolio?currency=JPY",
                headers=self.headers,
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "unsupported_portfolio_currency")
        patched.assert_not_called()

    def test_revoked_stored_token_is_reported_distinctly(self) -> None:
        with patch.object(backend.httpx, "Client") as patched:
            upstream = patched.return_value.__enter__.return_value
            upstream.post.return_value = httpx.Response(401)
            response = self.client.get("/tinvest/portfolio", headers=self.headers)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], "invalid_tinvest_token")


if __name__ == "__main__":
    unittest.main()
