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
        self.assertEqual(report["headroom_before_variable_charges_rub"], "7280.00")

    def test_ending_discount_never_reduces_cost_to_discounted_fee(self):
        self.assertEqual(subject.costs(finance())["conservative_31_day_rub"], "3000.00")

    def test_exact_cap_and_fractional_overrun(self):
        self.assertTrue(subject.costs(finance(monthly_cost="11000"))["recurring_within_infrastructure_cap"])
        result = subject.costs(finance(monthly_cost="11000.000000000001"))
        self.assertFalse(result["recurring_within_infrastructure_cap"])
        self.assertEqual(result["headroom_before_variable_charges_rub"], "0.00")

    def test_headroom_rounds_down(self):
        result = subject.costs(finance(monthly_cost="3000.000001"))
        self.assertEqual(result["headroom_before_variable_charges_rub"], "7999.99")
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
            result = subject.costs(finance(monthly_cost="10999.000001"))
        self.assertEqual(result["conservative_31_day_rub"], "10999.01")
        self.assertEqual(result["headroom_before_variable_charges_rub"], "0.99")

    def test_projection_excludes_account_balance_and_payment_card(self):
        raw = finance(balance="PRIVATE", autopay_card_info="PRIVATE", total_paid="PRIVATE")
        self.assertNotIn("PRIVATE", json.dumps(subject.costs(raw)))

    def test_inspection_does_not_grant_spend_or_future_price_guarantee(self):
        result = subject.costs(finance())
        self.assertFalse(result["includes_future_variable_charges"])
        self.assertFalse(result["provisioning_authorized_by_this_report"])
        self.assertEqual(result["total_cap_rub"], "14000.00")
        self.assertEqual(result["selected_budget_profile"], "hybrid")
        self.assertEqual(result["alternative_local_only"]["ai_cap_rub"], "0.00")
        self.assertFalse(result["alternative_local_only"]["selected"])

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

    def test_cheaper_other_location_does_not_hide_local_candidate(self):
        base = {"cpu": 4, "ram": 8192, "gpu": 0, "disk": 100000, "disk_type": "nvme"}
        rows = [{**base, "id": 1, "price": "1800", "location": "other"},
                {**base, "id": 2, "price": "5000", "location": "current"}]
        result = subject.preset_summary({"meta": {"total": 2}, "server_presets": rows}, {"location": "current"})
        self.assertEqual([row["same_location"] for row in result["candidates"]], [False, True])
        self.assertFalse(result["in_place_resize_verified"])

    def test_unknown_location_never_proves_compatibility(self):
        row = {"id": 1, "cpu": 4, "ram": 8192, "disk": 100000, "price": "1800"}
        result = subject.preset_summary({"server_presets": [row]}, {"location": "current"})
        self.assertIsNone(result["candidates"][0]["same_location"])
        self.assertIsNone(subject.label("PRIVATE"))
        self.assertIsNone(subject.label({"secret": "PRIVATE"}))

    def test_current_configurator_projection_never_exposes_raw_objects(self):
        row = {"id": 153, "location": "ru-1", "disk_type": "nvme", "description": "PRIVATE",
               "requirements": {"ram_min": 1024, "ram_max": 32768, "ram_step": 1024, "other": "PRIVATE"},
               "cpu_price": "800", "price": {"secret": "PRIVATE"}}
        result = subject.configurator_summary({"server_configurators": [row], "meta": {"total": 1}}, {"configurator_id": 153})
        self.assertTrue(result["complete"])
        self.assertEqual(result["current"]["requirements"]["ram_step"], 1024)
        self.assertEqual(result["current"]["numeric_pricing_fields_unverified"]["cpu_price"], "800.00")
        self.assertIsNone(result["current"]["numeric_pricing_fields_unverified"]["price"])
        self.assertNotIn("PRIVATE", json.dumps(result))
        self.assertFalse(result["resize_quote"])
        self.assertFalse(result["pricing_period_verified"])

    def test_configurator_dictionary_collection_and_wrong_id(self):
        document = {"server_configurators": {"153": {"id": 153}}, "meta": {"total": 1}}
        self.assertEqual(subject.configurator_summary(document, {"configurator_id": 153})["current"]["id"], 153)
        self.assertIsNone(subject.configurator_summary(document, {"configurator_id": 154})["current"])

    def test_duplicate_configurator_fails_closed(self):
        document = {"server_configurators": [{"id": 153}, {"id": 153}], "meta": {"total": 2}}
        result = subject.configurator_summary(document, {"configurator_id": 153})
        self.assertIsNone(result["current"])
        self.assertEqual(result["reason"], "current_configurator_not_unique_or_missing")

    def test_unknown_configurator_limits_and_cost_not_assumed(self):
        row = {"id": 153, "cpu_price": True, "ram_price": "NaN", "requirements": {"ram_step": False}}
        result = subject.configurator_summary({"server_configurators": [row]}, {"configurator_id": 153})
        self.assertFalse(result["complete"])
        self.assertIsNone(result["current"]["requirements"]["ram_step"])
        self.assertEqual(result["current"]["numeric_pricing_fields_unverified"], {"cpu_price": None, "ram_price": None})

    def test_server_disks_and_cpu_projection_only(self):
        row = {"id": subject.SERVER_ID, "is_dedicated_cpu": True, "location": "ru-1",
               "disks": [{"size": 30720, "type": "nvme", "data": "PRIVATE"}], "root_pass": "PRIVATE"}
        result = subject.server_summary({"server": row})
        self.assertTrue(result["is_dedicated_cpu"])
        self.assertEqual(result["disks"], [{"size_reported": 30720, "type": "nvme"}])
        self.assertNotIn("PRIVATE", json.dumps(result))

    def test_malformed_configurators_never_authorize_resize(self):
        for value in (None, True, "PRIVATE", []):
            result = subject.configurator_summary({"server_configurators": value}, {"configurator_id": 153})
            self.assertIsNone(result["current"])
            self.assertFalse(result["resize_quote"])

    def test_public_price_shape_retains_numbers_but_not_strings_or_deep_data(self):
        raw = {"cpu": "850.25", "ram": {"price": 425, "currency": "PRIVATE"},
               "deep": {"a": {"b": {"secret": "PRIVATE"}}}, "-secret": "PRIVATE"}
        result = subject.public_numeric_shape(raw)
        self.assertEqual(result["cpu"], {"number_reported": "850.25"})
        self.assertEqual(result["ram"]["price"], {"number_reported": "425"})
        self.assertNotIn("PRIVATE", json.dumps(result))
        self.assertNotIn("-secret", result)

    def test_invalid_public_prices_never_become_numeric_zero(self):
        for value in (True, "NaN", "Infinity", "-1", "PRIVATE", [], None):
            self.assertNotIn("number_reported", subject.public_numeric_shape(value))

    def test_expensive_small_and_malformed_candidates_excluded(self):
        base = {"id": 1, "cpu": 4, "ram": 16384, "gpu": 0, "disk": 100000, "price": "5000"}
        rows = [{**base, **change} for change in ({"price": "11001"}, {"ram": 4096}, {"price": "NaN"}, {"cpu": True})]
        self.assertEqual(subject.preset_summary({"meta": {"total": 4}, "server_presets": rows})["candidates"], [])

    def test_only_fixed_get_calls(self):
        api = MagicMock()
        def get(path):
            return {subject.PATHS["server"]: {"server": {"id": subject.SERVER_ID}},
                    subject.PATHS["finances"]: finance()}.get(path, {})
        api.get.side_effect = get
        report = subject.inspect(api)
        self.assertEqual([call.args[0] for call in api.get.call_args_list], list(subject.PATHS.values()))
        self.assertFalse(report["resource_changes"])
        self.assertFalse(report["model_inference_called"])

    def test_service_costs_exclude_other_resources_and_private_descriptions(self):
        rows = [{"service_id": subject.SERVER_ID, "project_id": subject.PROJECT_ID,
                 "cost": "1000", "total_cost": "1100", "info": {"name": "PRIVATE"},
                 "services": [{"description": "PRIVATE"}],
                 "configuration": {"cpu": 2, "ram": 4096, "disk": 40}},
                {"service_id": 1, "project_id": 2, "cost": "PRIVATE"}]
        result = subject.service_cost_summary({"services_costs": rows, "meta": {"total": 2}})
        self.assertTrue(result["complete"])
        self.assertEqual(len(result["target_services"]), 1)
        self.assertEqual(result["target_services"][0]["including_addons_reported"], "1100.00")
        self.assertNotIn("PRIVATE", json.dumps(result))
        self.assertFalse(result["billing_period_verified"])
        self.assertFalse(result["resize_quote"])

    def test_service_cost_missing_or_partial_is_not_complete(self):
        for raw in ({}, {"services_costs": [], "meta": {"total": 2}},
                    {"services_costs": [None], "meta": {"total": 1}}):
            self.assertFalse(subject.service_cost_summary(raw)["complete"])

    def test_unknown_service_cost_is_not_zero(self):
        row = {"service_id": subject.SERVER_ID, "project_id": subject.PROJECT_ID,
               "cost": "NaN", "total_cost": True}
        result = subject.service_cost_summary({"services_costs": [row], "meta": {"total": 1}})
        self.assertFalse(result["complete"])
        self.assertIsNone(result["target_services"][0]["including_addons_reported"])

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
