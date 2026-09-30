#!/usr/bin/env python3
"""Regression tests for the auth private-network reconciler."""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest

MODULE_PATH = pathlib.Path(__file__).with_name("timeweb_auth_network.py")
SPEC = importlib.util.spec_from_file_location("timeweb_auth_network", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load timeweb_auth_network.py")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class NetworkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.desired = MODULE.DesiredNetwork(
            name="omni-cio-private",
            subnet_v4="10.77.0.0/24",
            location="ru-3",
            availability_zone="msk-1",
        )

    def test_managed_server_requires_exact_ownership_marker(self) -> None:
        servers = [
            {
                "id": 9235089,
                "name": "omni-cio-white-site",
                "comment": "Managed by GitHub Actions: timeweb-white-site",
            }
        ]
        server = MODULE.find_managed_server(
            servers,
            name="omni-cio-white-site",
            comment="Managed by GitHub Actions: timeweb-white-site",
        )
        self.assertEqual(server["id"], 9235089)

    def test_server_preset_must_allow_private_network(self) -> None:
        server = {"preset_id": 42}
        allowed = [{"id": 42, "is_allowed_local_network": True}]
        blocked = [{"id": 42, "is_allowed_local_network": False}]

        self.assertTrue(MODULE.server_supports_private_network(server, allowed))
        self.assertFalse(MODULE.server_supports_private_network(server, blocked))

    def test_server_preset_lookup_must_be_unambiguous(self) -> None:
        with self.assertRaises(MODULE.InfraError):
            MODULE.server_supports_private_network({"preset_id": 42}, [])

    def test_vpc_rejects_same_name_with_wrong_subnet(self) -> None:
        vpcs = [
            {
                "id": "vpc-1",
                "name": "omni-cio-private",
                "subnet_v4": "10.88.0.0/24",
                "location": "ru-3",
                "availability_zone": "msk-1",
            }
        ]
        with self.assertRaises(MODULE.InfraError):
            MODULE.find_vpc(vpcs, self.desired)

    def test_server_attachment_requires_matching_id_and_name(self) -> None:
        services = [
            {
                "id": 9235089,
                "name": "omni-cio-white-site",
                "type": "server",
                "local_ip": "10.77.0.2",
            }
        ]
        self.assertTrue(
            MODULE.server_is_attached(
                services,
                server_id=9235089,
                server_name="omni-cio-white-site",
            )
        )
        self.assertFalse(
            MODULE.server_is_attached(
                services,
                server_id=999,
                server_name="omni-cio-white-site",
            )
        )


if __name__ == "__main__":
    unittest.main()
