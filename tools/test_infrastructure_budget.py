"""Synthetic fixtures only; no credentials or live cloud calls in verification."""
import importlib.util
import json
from decimal import Decimal, localcontext
from pathlib import Path
import unittest
from unittest.mock import MagicMock

spec = importlib.util.spec_from_file_location("budget_inspection", Path(__file__).with_name("inspect_infrastructure_budget.py"))
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)


def finance(**changes):
    return {"finances": {"currency": "RUB", "monthly_cost": "3000", "monthly_fee": "2900",
                         "hourly_cost": "4", "hourly_fee": "3.9", **changes}}


class ProjectionTests(unittest.TestCase):
    def test_month_longer_than_tariff_uses_larger_envelope(self):
        report = subject.costs(finance(hourly_cost="5"))
        self.assertEqual(report["conservative_31_day_rub"], "3720.00")
        self.assertEqual(report["headroom_before_variable_charges_rub"], "6280.00")

    def test_ending_discount_never_reduces_cost_to_discounted_fee(self):
        self.assertEqual(subject.costs(finance())["conservative_31_day_rub"], "3000.00")

    def test_exact_cap_and_fractional_overrun(self):
        self.assertTrue(subject.costs(finance(monthly_cost="10000"))["recurring_within_infrastructure_cap"])
        result = subject.costs(finance(monthly_cost="10000.000000000001"))
        self.assertFalse(result["recurring_within_infrastructure_cap"])
        self.assertEqual(result["headroom_before_variable_charges_rub"], "0.00")

    def test_headroom_rounds_down(self):
        result = subject.costs(finance(monthly_cost="3000.000001"))
        self.assertEqual(result["headroom_before_variable_charges_rub"], "6999.99")
        self.assertEqual(result["conservative_31_day_rub"], "3000.01")

    def test_invalid_money_never_becomes_zero(self):
        for value in (True, False, None, "", "NaN", "Infinity", "-1", "1e-13", 3.4, {}, [], "1" * 49):
            with self.subTest(value=str(value)):
                self.assertFalse(subject.costs(finance(monthly_cost=value))["verified"])

    def test_currency_and_missing_fields_fail_closed(self):
        for currency in (None, "USD", "rub", True):
            self.assertFalse(subject.costs(finance(currency=currency))["verified"])
        self.assertFalse(subject.costs({})["verified"])
        self.assertFalse(subject.costs(finance(hourly_fee=None))["verified"])

    def test_caller_decimal_precision_cannot_reduce_envelope(self):
        with localcontext() as context:
            context.prec = 2
            result = subject.costs(finance(monthly_cost="9999.000001"))
        self.assertEqual(result["conservative_31_day_rub"], "9999.01")
        self.assertEqual(result["headroom_before_variable_charges_rub"], "0.99")

    def test_projection_excludes_account_balance_and_payment_card(self):
        raw = finance(balance="PRIVATE", autopay_card_info="PRIVATE", total_paid="PRIVATE")
        self.assertNotIn("PRIVATE", json.dumps(subject.costs(raw)))

    def test_inspection_does_not_grant_spend_or_future_price_guarantee(self):
        result = subject.costs(finance())
        self.assertFalse(result["includes_future_variable_charges"])
        self.assertFalse(result["provisioning_authorized_by_this_report"])
        self.assertEqual(result["total_cap_rub"], "13000.00")

    def test_server_projection_excludes_sensitive_fields(self):
        result = subject.server_summary({"server": {"id": subject.SERVER_ID, "cpu": 4, "ram": 8192,
            "gpu": 0, "preset_id": 100, "name": "PRIVATE", "root_pass": "PRIVATE",
            "vnc_pass": "PRIVATE", "networks": ["PRIVATE"], "cloud_init": "PRIVATE"}})
        self.assertTrue(result["hardware_complete"])
        self.assertNotIn("PRIVATE", json.dumps(result))

    def test_wrong_server_rejected(self):
        for value in (True, 1, None, str(subject.SERVER_ID)):
            with self.assertRaises(subject.InspectionError):
                subject.server_summary({"server": {"id": value}})

    def test_missing_gpu_is_not_assumed_zero(self):
        self.assertFalse(subject.server_summary({"server": {"id": subject.SERVER_ID, "cpu": 4, "ram": 8192}})["hardware_complete"])

    def test_project_counts_only(self):
        raw = {name: [] for name in subject.RESOURCE_TYPES}
        raw["servers"] = [{"id": subject.SERVER_ID, "name": "PRIVATE", "root_pass": "PRIVATE"}]
        result = subject.project_summary(raw)
        self.assertTrue(result["complete"])
        self.assertTrue(result["expected_server_present"])
        self.assertNotIn("PRIVATE", json.dumps(result))

    def test_missing_resource_collection_not_zero(self):
        result = subject.project_summary({})
        self.assertFalse(result["complete"])
        self.assertIsNone(result["resource_counts"]["servers"])

    def test_preset_catalogue_is_not_capacity_or_addon_quote(self):
        result = subject.preset_summary({"meta": {"total": 1}, "server_presets": [
            {"id": 1, "cpu": 4, "ram": 16384, "gpu": 0, "disk": 100000, "price": "5000", "name": "PRIVATE"}]})
        self.assertTrue(result["complete"])
        self.assertFalse(result["availability_verified"])
        self.assertFalse(result["addons_included_verified"])
        self.assertNotIn("PRIVATE", json.dumps(result))

    def test_incomplete_preset_page(self):
        self.assertFalse(subject.preset_summary({"meta": {"total": 2}, "server_presets": []})["complete"])

    def test_expensive_small_and_malformed_candidates_excluded(self):
        base = {"id": 1, "cpu": 4, "ram": 16384, "gpu": 0, "disk": 100000, "price": "5000"}
        rows = [{**base, **change} for change in ({"price": "10001"}, {"ram": 4096}, {"price": "NaN"}, {"cpu": True})]
        self.assertEqual(subject.preset_summary({"meta": {"total": 4}, "server_presets": rows})["candidates"], [])

    def test_only_four_fixed_get_calls(self):
        api = MagicMock()
        def get(path):
            return {subject.PATHS["server"]: {"server": {"id": subject.SERVER_ID}},
                    subject.PATHS["finances"]: finance()}.get(path, {})
        api.get.side_effect = get
        report = subject.inspect(api)
        self.assertEqual([call.args[0] for call in api.get.call_args_list], list(subject.PATHS.values()))
        self.assertFalse(report["resource_changes"])
        self.assertFalse(report["model_inference_called"])

    def test_transport_method_and_host_are_fixed(self):
        api = subject.ReadOnlyAPI("TEST_SENTINEL")
        api._opener = MagicMock()
        response = api._opener.open.return_value.__enter__.return_value
        response.status = 200
        response.read.return_value = b'{"finances": {}}'
        api.get(subject.PATHS["finances"])
        request = api._opener.open.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.full_url, subject.BASE + subject.PATHS["finances"])

    def test_unknown_path_blocked_before_network(self):
        api = subject.ReadOnlyAPI("TEST_SENTINEL")
        api._opener = MagicMock()
        for path in ("/api/v1/servers", "https://example.invalid", "/api/v1/servers/9417612"):
            with self.assertRaises(subject.InspectionError):
                api.get(path)
        api._opener.open.assert_not_called()

    def test_response_bound(self):
        api = subject.ReadOnlyAPI("TEST_SENTINEL")
        api._opener = MagicMock()
        response = api._opener.open.return_value.__enter__.return_value
        response.status = 200
        response.read.return_value = b"x" * (subject.MAX_BYTES + 1)
        with self.assertRaisesRegex(subject.InspectionError, "response_limit_exceeded"):
            api.get(subject.PATHS["finances"])


if __name__ == "__main__":
    unittest.main()
