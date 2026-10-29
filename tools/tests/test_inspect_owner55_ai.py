"""Synthetic only: no credentials, no network and no billing effects."""
import importlib.util
import json
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "inspect_owner55_ai", Path(__file__).resolve().parents[1] / "inspect_owner55_ai.py")
inspection = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inspection)
KEY_ID = "11111111-1111-4111-8111-111111111111"
SENSITIVE = "DO_NOT_PRINT_PRIVATE_ACCOUNT_DATA"


def catalog(**changes):
    model = {"id": 108, "model_name": inspection.MODEL, "type": "llm",
             "is_stopped": False, "is_deprecated": False,
             "parameter_values": {"cost_in": Decimal("0.000001"),
                                  "cost_out": Decimal("0.000002"),
                                  "pricing_unit": "token", "context_window": 200000},
             "price_tiers": [], "description": SENSITIVE}
    model.update(changes)
    return {"models": [model], "meta": {"total": 1}, "private": SENSITIVE}


class FakeAPI:
    def __init__(self, payloads):
        self.payloads = payloads
        self.paths = []

    def get(self, path):
        self.paths.append(path)
        value = self.payloads[path]
        if isinstance(value, Exception):
            raise value
        return value


class InspectionTests(unittest.TestCase):
    def test_only_fixed_get_endpoints_and_uuid_bound_limit_paths(self):
        self.assertTrue(inspection.permitted_path(inspection.FINANCES))
        self.assertTrue(inspection.permitted_path(inspection.KEYS + "/" + KEY_ID + "/entity-limits"))
        for path in ["https://evil.invalid/", inspection.KEYS + "/regenerate",
                     inspection.KEYS + "/../../servers", inspection.KEYS + "?token=secret",
                     "/api/v1/servers", "/v1/chat/completions"]:
            with self.subTest(path=path):
                self.assertFalse(inspection.permitted_path(path))

    def test_real_transport_forces_get_without_request_body(self):
        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, limit):
                return b'{"models": [], "meta": {"total": 0}}'

        with patch.object(inspection.urllib.request, "build_opener") as factory:
            factory.return_value.open.return_value = Response()
            client = inspection.ReadOnlyAPI("synthetic-token")
            client.get(inspection.MODELS)
            request = factory.return_value.open.call_args.args[0]
            self.assertEqual(request.get_method(), "GET")
            self.assertIsNone(request.data)
            self.assertEqual(request.full_url, inspection.BASE + inspection.MODELS)
            with self.assertRaises(inspection.InspectionError):
                client.get("/api/v1/servers")
            self.assertEqual(factory.return_value.open.call_count, 1)

    def test_redirect_handler_never_forwards_bearer_credential(self):
        self.assertIsNone(inspection.NoRedirect().redirect_request(
            None, None, 302, "moved", {}, "https://evil.invalid"))

    def test_only_dedicated_metadata_and_curated_prices_are_emitted(self):
        dedicated = {"id": KEY_ID, "name": inspection.DEDICATED_PREFIX + "runtime",
                     "entity_type": "aikey", "is_readonly": False,
                     "expires_at": None, "fallback_models": [],
                     "account_id": SENSITIVE, "description": SENSITIVE, "key": SENSITIVE}
        limit_path = inspection.KEYS + "/" + KEY_ID + "/entity-limits"
        api = FakeAPI({
            inspection.FINANCES: {"finances": {"currency": "RUB", "autopay_card_info": SENSITIVE}},
            inspection.MODELS: catalog(),
            inspection.KEYS: {"ai_keys": [dedicated, {"id": KEY_ID, "name": SENSITIVE}], "meta": {"total": 2}},
            limit_path: {"ai_key_entity_limits": [{"id": KEY_ID, "ai_key_id": KEY_ID,
                        "entity_id": KEY_ID, "entity_type": "aikey", "limit_type": "day",
                        "model_id": None, "money_limit": Decimal("0"), "limit": 0,
                        "money_usage": SENSITIVE}], "meta": {"total": 1}},
        })
        report = inspection.inspect(api)
        self.assertNotIn(SENSITIVE, json.dumps(report))
        self.assertTrue(report["account_currency_rub_confirmed"])
        self.assertEqual(len(report["dedicated_keys"]), 1)
        self.assertFalse(report["create_permission_verified"])
        self.assertFalse(report["key_response_unmasked_verified"])
        self.assertTrue(report["model"]["pricing_verified"])
        self.assertEqual(report["model"]["maximum_input_rub_per_million"], "1.000000")
        self.assertEqual(report["dedicated_keys"][0]["limit_metadata"]["limits"][0]["money_limit_account_currency"], "0")
        self.assertEqual(len(api.paths), 4)
        self.assertTrue(all(inspection.permitted_path(path) for path in api.paths))

    def test_missing_price_tiers_or_stopped_model_never_imply_readiness(self):
        payload = catalog()
        del payload["models"][0]["price_tiers"]
        self.assertFalse(inspection.model_summary(payload)["pricing_verified"])
        self.assertFalse(inspection.model_summary(catalog(is_stopped=True))["availability_verified"])
        self.assertFalse(inspection.model_summary(catalog(is_stopped="false"))["availability_verified"])

    def test_price_tiers_use_full_context_ceiling_in_rub_per_million(self):
        payload = catalog(price_tiers=[{"above_context_tokens": 200000,
            "cost_in": Decimal("0.000003"), "cost_out": Decimal("0.000007")}])
        report = inspection.model_summary(payload)
        self.assertTrue(report["pricing_verified"])
        self.assertEqual(report["maximum_input_rub_per_million"], "3.000000")
        self.assertEqual(report["maximum_output_rub_per_million"], "7.000000")

    def test_invalid_decimal_and_false_currency_cannot_pass(self):
        for value in ["NaN", "Infinity", "-1", True, "0E-100000000", "1E-99"]:
            with self.subTest(value=value):
                self.assertIsNone(inspection.decimal_text(value))
        api = FakeAPI({inspection.FINANCES: {"finances": {"currency": "USD"}},
                       inspection.MODELS: catalog(),
                       inspection.KEYS: {"ai_keys": [], "meta": {"total": 0}}})
        self.assertFalse(inspection.inspect(api)["account_currency_rub_confirmed"])

    def test_permission_denied_stays_unverified_and_mask_sentinel_only_boolean(self):
        api = FakeAPI({inspection.FINANCES: inspection.InspectionError("permission_denied"),
                       inspection.MODELS: catalog(), inspection.KEYS: {
                           "ai_keys": [], "meta": {"total": 0}, "unused": inspection.MASKED}})
        report = inspection.inspect(api)
        self.assertFalse(report["read_flags"]["account_currency"]["readable"])
        self.assertFalse(report["account_currency_rub_confirmed"])
        self.assertTrue(report["hidden_policy_sentinel_observed"])
        self.assertFalse(report["key_response_unmasked_verified"])
        self.assertNotIn(inspection.MASKED, json.dumps(report))

    def test_incomplete_collections_and_duplicate_models_are_not_verified(self):
        payload = catalog()
        payload["meta"]["total"] = 2
        self.assertFalse(inspection.model_summary(payload)["availability_verified"])
        payload["models"] *= 2
        self.assertFalse(inspection.model_summary(payload)["pricing_verified"])


if __name__ == "__main__":
    unittest.main()
