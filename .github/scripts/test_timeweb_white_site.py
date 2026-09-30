#!/usr/bin/env python3
"""Regression tests for the Timeweb white-site reconciler."""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest
from decimal import Decimal
from typing import Any

MODULE_PATH = pathlib.Path(__file__).with_name("timeweb_white_site.py")
SPEC = importlib.util.spec_from_file_location("timeweb_white_site", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load timeweb_white_site.py for tests.")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FakeClient:
    def __init__(self, create_results: list[Any]) -> None:
        self.create_results = list(create_results)
        self.create_payloads: list[dict[str, Any]] = []

    def create_server(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.create_payloads.append(payload)
        result = self.create_results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result

    def get_servers(self) -> list[dict[str, Any]]:
        return []


class TimewebWhiteSiteTests(unittest.TestCase):
    def test_budget_filter_keeps_only_compatible_presets(self) -> None:
        os_info = {
            "requirements": {
                "cpu_min": 1,
                "ram_min": 1024,
                "disk_min": 15,
                "bandwidth_min": 100,
            }
        }
        presets = [
            {
                "id": 2573,
                "location": "ru-1",
                "price": 149,
                "cpu": 1,
                "ram": 1024,
                "disk": 15360,
                "bandwidth": 100,
            },
            {
                "id": 3000,
                "location": "ru-3",
                "price": 199,
                "cpu": 1,
                "ram": 1024,
                "disk": 15360,
                "bandwidth": 100,
            },
            {
                "id": 3001,
                "location": "ru-1",
                "price": 99,
                "cpu": 1,
                "ram": 512,
                "disk": 15360,
                "bandwidth": 100,
            },
        ]

        result = MODULE.select_budget_presets(
            os_info=os_info,
            presets=presets,
            max_server_price_rub=Decimal("149"),
        )

        self.assertEqual([item["id"] for item in result], [2573])

    def test_build_placements_expands_all_provider_zones(self) -> None:
        presets = [
            {
                "id": 2573,
                "location": "ru-1",
                "price": 149,
                "cpu": 1,
                "ram": 1024,
                "disk": 15360,
                "bandwidth": 100,
            }
        ]
        locations = [
            {
                "location": "ru-1",
                "availability_zones": [
                    "spb-1",
                    "spb-2",
                    "spb-3",
                    "spb-4",
                ],
            }
        ]

        placements = MODULE.build_placements(
            presets=presets,
            locations=locations,
        )

        self.assertEqual(
            [item.label for item in placements],
            [
                "2573@spb-1",
                "2573@spb-2",
                "2573@spb-3",
                "2573@spb-4",
            ],
        )

    def test_no_free_node_falls_back_to_next_zone(self) -> None:
        capacity_error = MODULE.TimewebApiError(
            status_code=409,
            error_code=MODULE.CAPACITY_ERROR_CODE,
            message="No free node",
            response_id="test-response",
        )
        client = FakeClient([capacity_error, {"id": 42}])
        os_info = {"id": 61}
        placements = [
            MODULE.Placement(
                preset_id=2573,
                location="ru-1",
                availability_zone="spb-1",
                price_rub=Decimal("149"),
                cpu=1,
                ram_mb=1024,
                disk_mb=15360,
                bandwidth_mbps=100,
            ),
            MODULE.Placement(
                preset_id=2573,
                location="ru-1",
                availability_zone="spb-2",
                price_rub=Decimal("149"),
                cpu=1,
                ram_mb=1024,
                disk_mb=15360,
                bandwidth_mbps=100,
            ),
        ]

        created, failures = MODULE.create_with_capacity_fallback(
            client=client,
            os_info=os_info,
            placements=placements,
            server_name="omni-cio-white-site",
            server_comment="Managed by GitHub Actions: timeweb-white-site",
        )

        self.assertEqual(created["id"], 42)
        self.assertEqual(failures, ["2573@spb-1"])
        self.assertEqual(
            [payload["availability_zone"] for payload in client.create_payloads],
            ["spb-1", "spb-2"],
        )
        self.assertTrue(
            all(
                payload["network"]["floating_ip"] == "create_ip"
                for payload in client.create_payloads
            )
        )

    def test_ambiguous_create_never_blindly_tries_next_zone(self) -> None:
        client = FakeClient(
            [MODULE.AmbiguousProviderError("network result unknown")]
        )
        os_info = {"id": 61}
        placements = [
            MODULE.Placement(
                preset_id=2573,
                location="ru-1",
                availability_zone="spb-1",
                price_rub=Decimal("149"),
                cpu=1,
                ram_mb=1024,
                disk_mb=15360,
                bandwidth_mbps=100,
            ),
            MODULE.Placement(
                preset_id=2573,
                location="ru-1",
                availability_zone="spb-2",
                price_rub=Decimal("149"),
                cpu=1,
                ram_mb=1024,
                disk_mb=15360,
                bandwidth_mbps=100,
            ),
        ]
        original_sleep = MODULE.time.sleep
        MODULE.time.sleep = lambda _: None
        try:
            with self.assertRaises(MODULE.DeploymentError):
                MODULE.create_with_capacity_fallback(
                    client=client,
                    os_info=os_info,
                    placements=placements,
                    server_name="omni-cio-white-site",
                    server_comment=(
                        "Managed by GitHub Actions: timeweb-white-site"
                    ),
                )
        finally:
            MODULE.time.sleep = original_sleep

        self.assertEqual(len(client.create_payloads), 1)

    def test_private_ipv4_is_not_reported_as_public(self) -> None:
        server = {
            "networks": [
                {
                    "type": "private",
                    "ips": [{"ip": "10.0.0.5"}],
                },
                {
                    "type": "public",
                    "ips": [{"ip": "203.0.113.10"}],
                },
            ]
        }

        self.assertEqual(
            MODULE.public_ipv4_addresses(server),
            ["203.0.113.10"],
        )


if __name__ == "__main__":
    unittest.main()
