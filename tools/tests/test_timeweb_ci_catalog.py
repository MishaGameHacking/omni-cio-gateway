"""Catalog selection must not leak unrelated fields or accept invalid prices."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import timeweb_actions_probe as probe
import timeweb_ci_catalog as catalog


class CatalogTests(unittest.TestCase):
    def test_ip_audit_never_emits_addresses_or_accepts_incomplete_inventory(self):
        payload = {"ips": [{"ip": "private-output", "resource_id": None},
                           {"ip": "private-output", "resource_id": 17}], "meta": {"total": 2}}
        self.assertEqual(catalog.floating_ip_summary(payload), {
            "count": 2, "complete": True, "unbound_count": 1, "server_ids": [17]})
        payload["meta"]["total"] = 3
        with self.assertRaisesRegex(probe.ProbeError, "incomplete_ip_inventory"):
            catalog.floating_ip_summary(payload)

    def test_filters_capacity_orders_price_and_only_emits_safe_fields(self):
        good = {"id": 2, "cpu": 4, "ram": 8192, "disk": 81920, "price": 2000}
        larger = dict(good, id=3, ram=16384, price=3000, root_pass="not-for-output")
        small = dict(good, id=1, disk=40960, price=100)
        result = catalog.candidate_presets({"server_presets": [larger, small, good]})
        self.assertEqual(result, [good, {k: larger[k] for k in good}])

    def test_invalid_price_cannot_become_an_offer(self):
        base = {"id": 1, "cpu": 4, "ram": 8192, "disk": 81920, "price": 1000}
        for price in (False, 0, -1, float("inf"), float("nan"), "1000"):
            payload = {"server_presets": [dict(base, price=price)]}
            with self.subTest(price=price), self.assertRaises(probe.ProbeError):
                catalog.candidate_presets(payload)

    def test_only_supported_ubuntu_image_identity_is_emitted(self):
        payload = {"servers_os": [
            {"id": 1, "name": "ubuntu", "version": "22.04"},
            {"id": 2, "name": "ubuntu", "version": "24.04", "password": "redact"},
            {"id": 3, "name": "windows", "version": "26.04"},
        ]}
        self.assertEqual(catalog.ubuntu_images(payload), [
            {"id": 2, "name": "ubuntu", "version": "24.04"}])

    def test_catalog_transport_rejects_arbitrary_paths(self):
        with patch.object(probe.urllib.request, "build_opener") as build:
            with self.assertRaises(probe.ProbeError):
                probe.read_catalog("synthetic-token", "/api/v1/account")
            with self.assertRaises(probe.ProbeError):
                probe.read_path("synthetic-token", "https://example.invalid/")
        build.assert_not_called()


if __name__ == "__main__":
    unittest.main()
