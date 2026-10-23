"""Synthetic fixtures only: no external API calls or real account tokens."""
from __future__ import annotations

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from backend import app as backend
from backend import portfolio_details as details


def cash(value: str, currency: str = "rub") -> dict:
    decimal = Decimal(value)
    units = int(decimal)
    return {"currency": currency, "units": str(units), "nano": int((decimal - units) * 10**9)}


def operation(identifier: str, kind: str, value: str, currency: str = "rub", state: str = "OPERATION_STATE_EXECUTED") -> dict:
    return {"id": identifier, "type": "OPERATION_TYPE_" + kind, "payment": cash(value, currency), "state": state}


class ValueTests(unittest.TestCase):
    def test_missing_value_is_not_zero(self):
        self.assertIsNone(details.number(None))
        self.assertIsNone(details.money(None))
        self.assertIsNone(details.money({"units": "0"}))

    def test_protobuf_omitted_zero_fields_are_zero(self):
        self.assertEqual(details.number({"nano": 20}), Decimal("0.000000020"))
        self.assertEqual(details.money({"currency": "rub"})["value"], {"units": 0, "nano": 0})

    def test_nonfinite_values_are_rejected(self):
        self.assertIsNone(details.number({"units": "NaN"}))
        self.assertIsNone(details.number({"units": "Infinity"}))

    def test_negative_subunit_preserved(self):
        self.assertEqual(details.number(cash("-0.37")), Decimal("-0.37"))

    def test_shares_count_units_not_lots(self):
        value = details.position_value({"instrumentType": "share", "currentPrice": cash("285.35"), "quantity": {"units": "10"}})
        self.assertEqual(details.number(value["value"]), Decimal("2853.5"))

    def test_bond_value_includes_accrued_interest(self):
        value = details.position_value({"instrumentType": "bond", "currentPrice": cash("990"),
                                        "currentNkd": cash("10.15"), "quantity": {"units": "2"}})
        self.assertEqual(details.number(value["value"]), Decimal("2000.30"))

    def test_bond_missing_accrued_not_invented(self):
        self.assertIsNone(details.position_value({"instrumentType": "bond", "currentPrice": cash("990"), "quantity": {"units": "2"}}))

    def test_futures_are_not_valued_like_shares(self):
        self.assertIsNone(details.position_value({"instrumentType": "futures", "currentPrice": cash("2000"), "quantity": {"units": "5"}}))

    def test_cash_native_currency_and_blocked_balance(self):
        rows = details.cash_positions({"money": [cash("8", "usd")], "blocked": [cash("2", "usd")]})
        self.assertEqual(rows[0]["currentValue"]["currency"], "USD")
        self.assertEqual(details.number(rows[0]["blockedQuantity"]), Decimal(2))

    def test_summary_keeps_currencies_separate_and_only_executed(self):
        raw = [operation("1", "DIVIDEND", "10"), operation("2", "DIVIDEND", "3", "usd"),
               operation("3", "INPUT", "1000"), operation("4", "OUTPUT", "-500"),
               operation("5", "BUY", "-100"), operation("6", "SELL", "110"),
               operation("7", "COUPON", "100", state="OPERATION_STATE_CANCELED")]
        result = {(r["category"], r["amount"]["currency"]): details.number(r["amount"]["value"]) for r in details.summarize_operations(raw + raw)}
        self.assertEqual(result[("dividends", "RUB")], 10)
        self.assertEqual(result[("dividends", "USD")], 3)
        self.assertEqual(result[("trades", "RUB")], 210)
        self.assertNotIn(("coupons", "RUB"), result)
        self.assertNotIn(("totalIncome", "RUB"), result)

    def test_tax_dividends_not_double_counted_as_dividends(self):
        self.assertEqual(details.operation_group("OPERATION_TYPE_TAX_DIVIDEND"), "tax")

    def test_future_dates_and_reverse_period_rejected(self):
        first, last = date(2024, 2, 2), date(2024, 2, 1)
        with self.assertRaises(HTTPException):
            details.period_bounds(first, last, {})
        first, last = date(2035, 1, 1), date(2035, 1, 2)
        with self.assertRaises(HTTPException):
            details.period_bounds(first, last, {})

    def test_moscow_calendar_converted_to_utc(self):
        start, end = details.period_bounds(date(2024, 1, 1), date(2024, 1, 1), {})
        self.assertEqual(start, "2023-12-31T21:00:00+00:00")
        self.assertEqual(end, "2024-01-01T21:00:00+00:00")

    def test_dividend_past_record_date_not_guaranteed(self):
        now = datetime(2024, 5, 1, tzinfo=timezone.utc)
        raw = {"dividends": [{"paymentDate": "2024-06-01T00:00:00Z", "recordDate": "2024-04-20T00:00:00Z", "dividendNet": cash("10")} ]}
        result = details.payment_rows(raw, {"quantity": {"units": "4"}}, "share", now)
        self.assertTrue(result[0]["eligibilityUnknown"])
        self.assertIsNone(result[0]["estimate"])

    def test_unknown_payment_date_is_not_faked(self):
        now = datetime(2024, 5, 1, tzinfo=timezone.utc)
        raw = {"dividends": [{"recordDate": "2024-06-01T00:00:00Z", "dividendNet": cash("10")} ]}
        row = details.payment_rows(raw, {"quantity": {"units": "4"}}, "share", now)[0]
        self.assertTrue(row["dateUnknown"])
        self.assertIsNone(row["estimate"])

    def test_cancelled_dividends_excluded(self):
        raw = {"dividends": [{"paymentDate": "2024-06-01T00:00:00Z", "dividendType": "Cancelled", "dividendNet": cash("10")} ]}
        self.assertEqual(details.payment_rows(raw, {"quantity": {"units": "4"}}, "share", datetime(2024, 5, 1, tzinfo=timezone.utc)), [])

    def test_bond_record_date_used_for_entitlement(self):
        raw = {"events": [{"couponDate": "2024-06-01T00:00:00Z", "fixDate": "2024-04-20T00:00:00Z", "payOneBond": cash("15")} ]}
        row = details.payment_rows(raw, {"quantity": {"units": "4"}}, "bond", datetime(2024, 5, 1, tzinfo=timezone.utc))[0]
        self.assertTrue(row["eligibilityUnknown"])
        self.assertIsNone(row["estimate"])


class DashboardApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_path = backend.DATABASE_PATH
        backend.DATABASE_PATH = Path(self.temp.name) / "details.sqlite3"
        backend.init_db()
        self.headers = {"Authorization": "Bearer details-session"}
        with closing(backend.connect()) as db:
            self.user_id = db.execute("INSERT INTO users(telegram_sub,tinvest_token_encrypted,created_at,updated_at) VALUES(?,?,?,?)",
                ("details-user", backend.FERNET.encrypt(b"fixture-token"), 1, 1)).lastrowid
            db.execute("INSERT INTO sessions VALUES(?,?,?)", (backend.hash_token("details-session"), self.user_id, 4102444800))
            db.commit()
        self.client = TestClient(backend.app)
        self.calls = []
        # These scenarios replace BrokerReader.read with synthetic responses.
        # Do not initialize a real proxy transport from the host environment.
        transport = patch.object(backend.httpx, "Client", autospec=True)
        self.broker_transport = transport.start()
        self.addCleanup(transport.stop)
        self.broker_transport.return_value.post.side_effect = AssertionError(
            "Synthetic portfolio scenario unexpectedly reached the broker transport"
        )

    def tearDown(self):
        self.client.close()
        backend.DATABASE_PATH = self.old_path
        self.temp.cleanup()

    def respond(self, reader, method, body):
        self.calls.append((method, body))
        if method == "accounts":
            return {"accounts": [{"id": "own", "name": "Fixture", "status": "ACCOUNT_STATUS_OPEN", "accessLevel": "ACCOUNT_ACCESS_LEVEL_READ_ONLY", "openedDate": "2024-01-01T00:00:00Z"}]}
        if method == "portfolio":
            currency = body["currency"].lower()
            return {"totalAmountPortfolio": cash("110", currency), "totalAmountCurrencies": cash("100", currency),
                    "totalAmountShares": cash("10", currency), "expectedYield": {"nano": 500000000},
                    "dailyYield": cash("1", "rub"), "positions": [
                        {"instrumentUid": "cash-uid", "instrumentType": "currency", "quantity": {"units": "100"}, "currentPrice": cash("1")},
                        {"instrumentUid": "asset-uid", "ticker": "TEST", "instrumentType": "share", "quantity": {"units": "1"}, "currentPrice": cash("10")} ]}
        if method == "positions":
            return {"money": [cash("100")], "securities": [{"instrumentUid": "asset-uid", "balance": "1"},
                    {"instrumentUid": "blocked-only", "balance": "0", "blocked": "3", "exchangeBlocked": True, "instrumentType": "share"}]}
        if method == "instrument":
            return {"instrument": {"name": "Synthetic instrument", "ticker": "TEST", "sector": "financial"}}
        if method == "operations":
            return {"items": [operation("fixture-op", "INPUT", "100")], "hasNext": False}
        if method == "orders":
            raise HTTPException(503, "tinvest_upstream_unavailable")
        if method == "stops":
            return {"stopOrders": []}
        if method == "withdraw":
            return {"money": [cash("90")]}
        raise AssertionError(method)

    def test_dashboard_currency_cash_dedup_and_unpriced_blocked_position(self):
        with patch.object(details.BrokerReader, "read", autospec=True, side_effect=self.respond):
            response = self.client.get("/tinvest/dashboard?currency=EUR", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["totalValue"]["currency"], "EUR")
        self.assertIsNone(data["expectedYieldAmount"])
        rows = data["accounts"][0]["positions"]
        self.assertEqual(len(rows), 3)
        self.assertEqual(sum(row["instrumentType"] == "cash" for row in rows), 1)
        blocked = next(row for row in rows if row["id"] == "blocked-only")
        self.assertIsNone(blocked["currentValue"])
        self.assertEqual(details.number(blocked["quantity"]), 3)
        self.assertEqual(data["accounts"][0]["dailyYieldAmount"]["currency"], "RUB")

    def test_foreign_account_is_denied_before_account_reads(self):
        with patch.object(details.BrokerReader, "read", autospec=True, side_effect=self.respond):
            response = self.client.get("/tinvest/accounts/foreign/operations", headers=self.headers)
        self.assertEqual(response.status_code, 404)
        self.assertEqual([method for method, _ in self.calls], ["accounts"])

    def test_unauthenticated_requests_do_not_call_broker(self):
        with patch.object(details.BrokerReader, "read") as read:
            response = self.client.get("/tinvest/dashboard")
        self.assertEqual(response.status_code, 401)
        read.assert_not_called()

    def test_orders_failure_is_not_false_empty_list(self):
        with patch.object(details.BrokerReader, "read", autospec=True, side_effect=self.respond):
            response = self.client.get("/tinvest/accounts/own/orders", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["orders"]["available"])
        self.assertTrue(response.json()["stopOrders"]["available"])

    def test_analytics_does_not_invent_prior_history(self):
        with patch.object(details.BrokerReader, "read", autospec=True, side_effect=self.respond):
            response = self.client.get("/tinvest/accounts/own/analytics?start=2024-01-01&end=2024-01-02", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["complete"])
        self.assertEqual(response.json()["history"], [])
        self.assertIsNone(response.json()["totalIncome"])

    def test_recorded_history_is_user_and_currency_scoped(self):
        account = {"id": "own", "totalValue": details.money(cash("123"))}
        details.record_history(self.user_id, [account], "2024-01-01T10:00:00+00:00")
        details.record_history(self.user_id + 1, [{"id": "own", "totalValue": details.money(cash("999"))}], "2024-01-01T10:00:00+00:00")
        with patch.object(details.BrokerReader, "read", autospec=True, side_effect=self.respond):
            response = self.client.get("/tinvest/accounts/own/analytics?start=2024-01-01&end=2024-01-02", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual([r["value"] for r in response.json()["history"]], ["123"])

    def test_cached_mutations_do_not_leak_to_next_caller(self):
        key = ("test", self.temp.name)
        first = details.cached(key, 10, lambda: {"data": [1]})
        first["data"].append(2)
        self.assertEqual(details.cached(key, 10, lambda: None), {"data": [1]})

    def test_cache_single_flight(self):
        calls = []
        def load():
            calls.append(1)
            return {"value": 1}
        with ThreadPoolExecutor(4) as executor:
            results = list(executor.map(lambda _: details.cached(("concurrent", self.temp.name), 10, load), range(10)))
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(results), 10)


if __name__ == "__main__":
    unittest.main()
