#!/usr/bin/env python3
"""Regression tests for the Timeweb white-site reconciler."""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest
from decimal import Decimal
from typing import Any
from unittest.mock import patch

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
            max_server_price_rub=Decimal("199"),
            target_location="ru-3",
        )

        self.assertEqual([item["id"] for item in result], [3000])

    def test_compatible_presets_can_exceed_current_budget(self) -> None:
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
                "id": 3000,
                "location": "ru-3",
                "price": 900,
                "cpu": 2,
                "ram": 2048,
                "disk": 40960,
                "bandwidth": 1000,
            }
        ]

        compatible = MODULE.select_compatible_presets(
            os_info=os_info,
            presets=presets,
            target_location="ru-3",
        )
        within_budget = MODULE.select_budget_presets(
            os_info=os_info,
            presets=presets,
            max_server_price_rub=Decimal("199"),
            target_location="ru-3",
        )

        self.assertEqual([item["id"] for item in compatible], [3000])
        self.assertEqual(within_budget, [])

    def test_build_placements_restricts_to_moscow_zone(self) -> None:
        presets = [
            {
                "id": 3000,
                "location": "ru-3",
                "price": 199,
                "cpu": 1,
                "ram": 1024,
                "disk": 15360,
                "bandwidth": 100,
            }
        ]
        locations = [
            {
                "location": "ru-3",
                "availability_zones": ["msk-1"],
            },
            {
                "location": "ru-1",
                "availability_zones": ["spb-1", "spb-2"],
            },
        ]

        placements = MODULE.build_placements(
            presets=presets,
            locations=locations,
            target_location="ru-3",
            target_availability_zone="msk-1",
        )

        self.assertEqual(
            [item.label for item in placements],
            ["3000@msk-1"],
        )
        self.assertTrue(
            all(item.location == "ru-3" for item in placements)
        )

    def test_build_placements_rejects_missing_moscow_zone(self) -> None:
        presets = [
            {
                "id": 3000,
                "location": "ru-3",
                "price": 199,
                "cpu": 1,
                "ram": 1024,
                "disk": 15360,
                "bandwidth": 100,
            }
        ]
        locations = [
            {
                "location": "ru-3",
                "availability_zones": ["msk-2"],
            }
        ]

        with self.assertRaises(MODULE.DeploymentError):
            MODULE.build_placements(
                presets=presets,
                locations=locations,
                target_location="ru-3",
                target_availability_zone="msk-1",
            )

    def test_no_free_node_falls_back_to_next_zone(self) -> None:
        capacity_error = MODULE.TimewebApiError(
            status_code=409,
            error_code=MODULE.PLACEMENT_CAPACITY_ERROR_CODE,
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

    def test_location_run_out_skips_remaining_zones_in_location(self) -> None:
        location_error = MODULE.TimewebApiError(
            status_code=400,
            error_code=MODULE.LOCATION_CAPACITY_ERROR_CODE,
            message="Servers in location: ru-1 is run out",
            response_id="region-capacity",
        )
        client = FakeClient([location_error])
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
            MODULE.Placement(
                preset_id=3000,
                location="ru-3",
                availability_zone="msk-1",
                price_rub=Decimal("149"),
                cpu=1,
                ram_mb=1024,
                disk_mb=15360,
                bandwidth_mbps=100,
            ),
        ]

        client.create_results.append({"id": 84})
        created, failures = MODULE.create_with_capacity_fallback(
            client=client,
            os_info=os_info,
            placements=placements,
            server_name="omni-cio-white-site",
            server_comment="Managed by GitHub Actions: timeweb-white-site",
        )

        self.assertEqual(created["id"], 84)
        self.assertEqual(
            failures,
            ["2573@spb-1", "2573@spb-2"],
        )
        self.assertEqual(
            [payload["availability_zone"] for payload in client.create_payloads],
            ["spb-1", "msk-1"],
        )

    def test_unrelated_bad_request_is_not_treated_as_capacity(self) -> None:
        bad_request = MODULE.TimewebApiError(
            status_code=400,
            error_code="validation_error",
            message="Invalid payload",
            response_id="bad-request",
        )
        client = FakeClient([bad_request])
        placement = MODULE.Placement(
            preset_id=2573,
            location="ru-1",
            availability_zone="spb-1",
            price_rub=Decimal("149"),
            cpu=1,
            ram_mb=1024,
            disk_mb=15360,
            bandwidth_mbps=100,
        )

        with self.assertRaises(MODULE.TimewebApiError):
            MODULE.create_with_capacity_fallback(
                client=client,
                os_info={"id": 61},
                placements=[placement],
                server_name="omni-cio-white-site",
                server_comment="Managed by GitHub Actions: timeweb-white-site",
            )

        self.assertEqual(len(client.create_payloads), 1)

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

    def test_unknown_conflicts_never_trigger_a_second_create(self) -> None:
        for status in (409, 423):
            error = MODULE.TimewebApiError(
                status_code=status, error_code="unknown_conflict",
                message="conflict", response_id="test",
            )
            client = FakeClient([error])
            with self.subTest(status=status), patch.object(MODULE.time, "sleep"):
                with self.assertRaises(MODULE.TimewebApiError) as raised:
                    MODULE.create_server_candidate(
                        client, {}, server_name="managed", server_comment="owned",
                    )
                self.assertIs(raised.exception, error)
                self.assertEqual(client.create_payloads, [{}])

    def test_wait_for_web_port_uses_canonical_ipv4_only(self) -> None:
        calls: list[tuple[tuple[str, int], int]] = []

        class FakeConnection:
            def __enter__(self) -> FakeConnection:
                return self

            def __exit__(self, *_args: object) -> None:
                return None

        original_create_connection = MODULE.socket.create_connection

        def fake_create_connection(
            address: tuple[str, int],
            timeout: int,
        ) -> FakeConnection:
            calls.append((address, timeout))
            return FakeConnection()

        MODULE.socket.create_connection = fake_create_connection
        try:
            MODULE.wait_for_web_port(
                "194.087.151.244".replace(".087.", ".87."),
                attempts=1,
                sleep_seconds=0,
            )
        finally:
            MODULE.socket.create_connection = original_create_connection

        self.assertEqual(
            calls,
            [(("194.87.151.244", 80), 5)],
        )

    def test_wait_for_web_port_rejects_ipv6(self) -> None:
        with self.assertRaises(MODULE.DeploymentError):
            MODULE.wait_for_web_port(
                "2001:db8::1",
                attempts=1,
                sleep_seconds=0,
            )

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
