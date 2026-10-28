"""Real-portfolio aggregation regressions; T-Invest calls are mocked."""
from __future__ import annotations

import tempfile
import unittest
from contextlib import closing
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend import app as backend
from backend import tinvest_portfolio
from backend import autonomous_ai, purchase_policy, volume_monitor, volume_state
from backend.volume_contract import decimal as money_decimal


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

    @staticmethod
    def cash_observation() -> tuple[dict, dict]:
        quantity = {"units": "12", "nano": 345_678_901}
        cash = {"currency": "rub", **quantity}
        portfolio = {
            "totalAmountPortfolio": dict(cash),
            "positions": [{
                "instrumentUid": "currency-instrument-uid",
                "instrumentType": "currency",
                "quantity": dict(quantity),
                "currentPrice": {"currency": "rub", "units": "1", "nano": 0},
            }],
        }
        return portfolio, {"money": [cash]}

    def test_cash_overlap_reconciles_through_endpoint_monitor_and_saved_snapshot(self) -> None:
        autonomous_ai.init_autonomous_db()
        with closing(backend.connect()) as db:
            user = db.execute("SELECT * FROM users WHERE id=?", (self.user_id,)).fetchone()
        raw, balances = self.cash_observation()
        # A blocked subset is not extra cash and must not be deducted from its
        # total valuation. This change preserves the existing blocked semantics.
        balances["blocked"] = [{"currency": "rub", "units": "2", "nano": 100_000_000}]
        account = {"id": "cash-account", "status": "ACCOUNT_STATUS_OPEN",
                   "accessLevel": "ACCOUNT_ACCESS_LEVEL_READ_ONLY"}

        def response_for(url: str, **kwargs):
            if url == backend.TINVEST_ACCOUNTS_URL:
                return httpx.Response(200, json={"accounts": [account]})
            self.assertEqual(kwargs["json"]["accountId"], account["id"])
            if url == tinvest_portfolio.TINVEST_PORTFOLIO_URL:
                self.assertEqual(kwargs["json"]["currency"], "RUB")
                return httpx.Response(200, json=raw)
            if url == tinvest_portfolio.TINVEST_POSITIONS_URL:
                return httpx.Response(200, json=balances)
            raise AssertionError("Unexpected broker method in cash regression")

        for loading in (False, True):
            with self.subTest(limits_loading=loading):
                balances["limitsLoadingInProgress"] = loading
                with patch.object(backend.httpx, "Client") as patched:
                    upstream = patched.return_value.__enter__.return_value
                    upstream.post.side_effect = response_for
                    response = self.client.get("/tinvest/portfolio", headers=self.headers)
                    self.assertEqual(response.status_code, 200, response.text)
                    payload = response.json()
                    positions = payload["accounts"][0]["positions"]
                    self.assertEqual([row["id"] for row in positions], ["cash:RUB"])
                    self.assertEqual(money_decimal(positions[0]["currentValue"]), Decimal("12.345678901"))
                    self.assertEqual(money_decimal(payload["totalValue"]), Decimal("12.345678901"))
                    now = datetime.now(timezone.utc)
                    volume_monitor.ingest(user, payload, now)
                    self.assertEqual(upstream.post.call_count, 3)
                saved = volume_state.saved_snapshot(user)
                self.assertIsNotNone(saved)
                self.assertEqual([row["instrument_type"] for row in saved["positions"]], ["cash"])
                self.assertEqual(money_decimal(saved["capital"]["total"]), Decimal("12.345678901"))
                exposures, reasons = purchase_policy.exposure_amounts(saved, now)
                self.assertEqual(reasons, [])
                self.assertEqual(exposures["currency"], {"RUB": Decimal("12.345678901")})
                self.assertEqual(saved["position_coverage"]["complete"], not loading)
                if loading:
                    self.assertIn("broker_limits_loading", saved["position_coverage"]["incomplete_reasons"])

    def test_cash_presence_distinguishes_missing_null_empty_and_blocked_only(self) -> None:
        raw, _ = self.cash_observation()
        cases = (
            ({}, ["currency-instrument-uid"]),
            ({"money": None}, ["currency-instrument-uid"]),
            ({"blocked": [{"currency": "rub", "units": "2", "nano": 0}]}, ["currency-instrument-uid"]),
            ({"money": []}, []),
            ({"money": [{"currency": "rub", "units": "0", "nano": 0}]}, []),
        )
        for balances, expected in cases:
            with self.subTest(balances=balances):
                actual = tinvest_portfolio._portfolio_positions(deepcopy(raw), balances)
                self.assertEqual([row["id"] for row in actual], expected)
                if expected:
                    self.assertEqual(money_decimal(actual[0]["currentValue"]), Decimal("12.345678901"))

    def test_non_currency_position_with_the_same_value_is_retained(self) -> None:
        raw, balances = self.cash_observation()
        share = {**deepcopy(raw["positions"][0]), "instrumentUid": "share-same-value", "instrumentType": "share"}
        raw["positions"].append(share)
        actual = tinvest_portfolio._portfolio_positions(raw, balances)
        self.assertEqual([row["id"] for row in actual], ["share-same-value", "cash:RUB"])
        self.assertEqual([money_decimal(row["currentValue"]) for row in actual],
                         [Decimal("12.345678901"), Decimal("12.345678901")])

    def test_malformed_supplied_money_fails_instead_of_silently_erasing_currency(self) -> None:
        raw, _ = self.cash_observation()
        malformed = (
            "unavailable",
            {"currency": "rub", "units": "12", "nano": 0},
            [None],
            [{"currency": "rub", "units": "invalid", "nano": 0}],
            [{"units": "12", "nano": 0}],
            [{"currency": "rub", "units": "12", "nano": 1_000_000_000}],
            [{"currency": "not-a-currency", "units": "12", "nano": 0}],
        )
        for money in malformed:
            with self.subTest(money=money):
                with self.assertRaises(HTTPException) as failure:
                    tinvest_portfolio._portfolio_positions(deepcopy(raw), {"money": money})
                self.assertEqual(failure.exception.status_code, 502)

    def test_positions_service_failure_does_not_return_a_partial_cash_fallback(self) -> None:
        raw, _ = self.cash_observation()
        with patch.object(backend.httpx, "Client") as patched:
            upstream = patched.return_value.__enter__.return_value
            upstream.post.side_effect = [
                httpx.Response(200, json={"accounts": [{"id": "cash-account", "status": "ACCOUNT_STATUS_OPEN",
                                                       "accessLevel": "ACCOUNT_ACCESS_LEVEL_READ_ONLY"}]}),
                httpx.Response(200, json=raw),
                httpx.Response(503),
            ]
            response = self.client.get("/tinvest/portfolio", headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "tinvest_upstream_unavailable")
        self.assertEqual(upstream.post.call_count, 3)

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
