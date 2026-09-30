#!/usr/bin/env python3
"""Regression tests for the private PostgreSQL reconciler."""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest
from decimal import Decimal

MODULE_PATH = pathlib.Path(__file__).with_name("timeweb_auth_postgres.py")
SPEC = importlib.util.spec_from_file_location("timeweb_auth_postgres", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load timeweb_auth_postgres.py")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class PostgresTests(unittest.TestCase):
    def setUp(self) -> None:
        self.desired = MODULE.DesiredDatabase(
            cluster_name="omnicio-auth-postgres",
            instance_name="omnicio",
            admin_login="omnicio_app",
            postgres_version="18",
            location="ru-3",
            availability_zone="msk-1",
            max_price_rub=Decimal("1110"),
            min_cpu=1,
            min_ram_mb=2048,
            min_disk_mb=20480,
        )

    def test_selects_supported_postgres_18_type(self) -> None:
        types = [
            {
                "name": "PostgreSQL",
                "version": "18",
                "type": "postgres18",
                "is_deprecated": False,
            },
            {
                "name": "PostgreSQL",
                "version": "17",
                "type": "postgres17",
                "is_deprecated": False,
            },
        ]
        self.assertEqual(
            MODULE.select_postgres_type(types, version="18"),
            "postgres18",
        )

    def test_preset_selection_enforces_resources_and_budget(self) -> None:
        presets = [
            {
                "id": 1,
                "type": "postgres",
                "location": "ru-3",
                "price": 700,
                "cpu": 1,
                "ram": 1024,
                "disk": 8192,
            },
            {
                "id": 2,
                "type": "postgres",
                "location": "ru-3",
                "price": 1110,
                "cpu": 1,
                "ram": 2048,
                "disk": 20480,
            },
            {
                "id": 3,
                "type": "postgres",
                "location": "ru-3",
                "price": 1200,
                "cpu": 2,
                "ram": 4096,
                "disk": 40960,
            },
        ]
        selected = MODULE.select_database_preset(presets, self.desired)
        self.assertEqual(selected["id"], 2)

    def test_create_payload_is_private_only_and_no_autoscale(self) -> None:
        payload = MODULE.create_payload(
            desired=self.desired,
            db_type="postgres18",
            preset={"id": 2},
            vpc_id="network-123",
            password="secret-value",
        )
        self.assertEqual(payload["network"], {"id": "network-123"})
        self.assertFalse(payload["is_public_ipv6"])
        self.assertNotIn("floating_ip", payload["network"])
        self.assertEqual(payload["disk_autoscaling"], {"is_enabled": False})

    def test_private_database_endpoint_uses_private_ipv4(self) -> None:
        cluster = {
            "port": 5432,
            "networks": [
                {
                    "type": "local",
                    "ips": [{"type": "ipv4", "ip": "10.77.0.10"}],
                }
            ],
        }
        endpoint = MODULE.private_database_endpoint(cluster)
        self.assertIsNotNone(endpoint)
        assert endpoint is not None
        self.assertEqual(endpoint.host, "10.77.0.10")
        self.assertEqual(endpoint.port, 5432)

    def test_secret_bundle_requires_all_runtime_keys(self) -> None:
        raw = (
            "OMNICIO_DB_ADMIN_PASSWORD=pw\n"
            "PHONE_CRYPTO_KEY=crypto\n"
            "PHONE_LOOKUP_KEY=lookup\n"
            "OTP_SIGNING_KEY=otp\n"
            "CLIENT_IP_KEY=ip\n"
        )
        parsed = MODULE.parse_secret_bundle(raw)
        self.assertEqual(parsed["OMNICIO_DB_ADMIN_PASSWORD"], "pw")

        with self.assertRaises(MODULE.InfraError):
            MODULE.parse_secret_bundle("OMNICIO_DB_ADMIN_PASSWORD=pw\n")

    def test_existing_cluster_rejects_public_network(self) -> None:
        cluster = {
            "type": "postgres18",
            "location": "ru-3",
            "availability_zone": "msk-1",
            "is_enabled_public_network": True,
            "is_enabled_public_ipv6": False,
        }
        with self.assertRaises(MODULE.InfraError):
            MODULE.validate_existing_cluster(
                cluster,
                desired=self.desired,
                db_type="postgres18",
            )


if __name__ == "__main__":
    unittest.main()
