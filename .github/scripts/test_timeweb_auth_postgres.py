#!/usr/bin/env python3
"""Regression tests for the private PostgreSQL reconciler."""

from __future__ import annotations

import importlib.util
import pathlib
import secrets
import sys
import tempfile
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

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

    def test_ambiguous_database_creation_is_not_retried(self) -> None:
        for recovered in (None, {"id": 42}):
            with self.subTest(recovered=recovered):
                client = Mock()
                error = MODULE.AmbiguousProviderError("timeout")
                client.create_database_cluster.side_effect = error
                with patch.object(
                    MODULE, "reconcile_after_ambiguous_create", return_value=recovered,
                ):
                    if recovered is None:
                        with self.assertRaises(MODULE.InfraError):
                            MODULE.create_database_cluster(client, {}, cluster_name="managed")
                    else:
                        result = MODULE.create_database_cluster(client, {}, cluster_name="managed")
                        self.assertEqual(result, 42)
                client.create_database_cluster.assert_called_once_with({})

    def test_address_inventory_keeps_private_endpoint_separate(self) -> None:
        cluster = {"networks": [
            {"type": "private", "ips": [{"ip": "10.0.0.5"}, {"ip": "10.0.0.5"}]},
            {"type": "public", "ips": [{"ip": "invalid"}, {}, {"ip": "8.8.8.8"}]},
        ]}
        self.assertEqual(MODULE.private_database_endpoint(cluster).host, "10.0.0.5")
        self.assertEqual(MODULE.public_ipv4(cluster), "8.8.8.8")
        cluster["networks"][0]["ips"].append({"ip": "10.0.0.6"})
        with self.assertRaises(MODULE.InfraError):
            MODULE.private_database_endpoint(cluster)

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
            password=secrets.token_urlsafe(18),
        )
        self.assertEqual(payload["network"], {"id": "network-123"})
        self.assertFalse(payload["is_public_ipv6"])
        self.assertNotIn("floating_ip", payload["network"])
        self.assertEqual(payload["disk_autoscaling"], {"is_enabled": False})

    def test_private_server_cidr_uses_vpc_prefix(self) -> None:
        vpc = {"subnet_v4": "10.77.0.0/24"}
        service = {"local_ip": "10.77.0.4"}

        self.assertEqual(
            MODULE.private_server_cidr(vpc, service),
            "10.77.0.4/24",
        )

    def test_private_server_cidr_rejects_outside_subnet(self) -> None:
        with self.assertRaises(MODULE.InfraError):
            MODULE.private_server_cidr(
                {"subnet_v4": "10.77.0.0/24"},
                {"local_ip": "10.88.0.4"},
            )

    def test_private_network_script_never_targets_public_interface(self) -> None:
        script = MODULE.REMOTE_PRIVATE_NETWORK_CONFIG
        self.assertIn('if [ "$PRIVATE_IF" = "$PUBLIC_IF" ]', script)
        self.assertIn("/etc/netplan/99-omnicio-private.yaml", script)
        self.assertIn('ip addr add "$CIDR" dev "$PRIVATE_IF"', script)
        self.assertIn('ip link set dev "$PRIVATE_IF" up', script)
        self.assertIn("netplan generate", script)
        self.assertNotIn('case "$state" in', script)

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

    def test_timeweb_database_password_policy(self) -> None:
        self.assertTrue(MODULE.is_valid_timeweb_db_password("Abcdef1234567890_-"))
        self.assertFalse(MODULE.is_valid_timeweb_db_password("short"))
        self.assertFalse(MODULE.is_valid_timeweb_db_password("A" * 31))
        self.assertFalse(MODULE.is_valid_timeweb_db_password("valid-length but space"))

    def test_secret_bootstrap_uses_provider_compatible_password_length(self) -> None:
        self.assertIn("secrets.token_urlsafe(18)", MODULE.REMOTE_SECRET_BOOTSTRAP)
        self.assertNotIn("secrets.token_urlsafe(36)", MODULE.REMOTE_SECRET_BOOTSTRAP)

    def test_secret_bundle_requires_all_runtime_keys(self) -> None:
        raw = (
            "OMNICIO_DB_ADMIN_PASSWORD=pw\n"
            "CLIENT_IP_KEY=ip\n"
            "BROKER_TOKEN_CRYPTO_KEY=broker\n"
            "VKID_FLOW_CRYPTO_KEY=vkid\n"
        )
        parsed = MODULE.parse_secret_bundle(raw)
        self.assertEqual(parsed["OMNICIO_DB_ADMIN_PASSWORD"], "pw")

        with self.assertRaises(MODULE.InfraError):
            MODULE.parse_secret_bundle("OMNICIO_DB_ADMIN_PASSWORD=pw\n")

    def test_secret_bootstrap_adds_required_encryption_keys(self) -> None:
        self.assertIn("BROKER_TOKEN_CRYPTO_KEY", MODULE.REMOTE_SECRET_BOOTSTRAP)
        self.assertIn("VKID_FLOW_CRYPTO_KEY", MODULE.REMOTE_SECRET_BOOTSTRAP)
        self.assertIn(
            "base64.urlsafe_b64encode(os.urandom(32)).decode()",
            MODULE.REMOTE_SECRET_BOOTSTRAP,
        )

    def test_workflow_applies_portfolio_observer_migration_after_existing_schema(self) -> None:
        root = MODULE_PATH.parents[2]
        workflow = (root / ".github" / "workflows" / "auth-postgres.yml").read_text()

        migrations = [
            "migrations/0001_phone_auth.sql",
            "migrations/0002_tbank_connection.sql",
            "migrations/0003_vkid_owner_identity.sql",
            "migrations/0004_user_role.sql",
            "migrations/0005_drop_phone_auth.sql",
            "migrations/0006_portfolio_observer.sql",
            "migrations/0007_portfolio_evidence.sql",
            "migrations/0008_portfolio_optimizer_metadata.sql",
        ]
        positions = [workflow.index(path) for path in migrations]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(workflow.count("--migration migrations/0006_portfolio_observer.sql"), 1)
        self.assertEqual(workflow.count("--migration migrations/0007_portfolio_evidence.sql"), 1)
        self.assertEqual(
            workflow.count("--migration migrations/0008_portfolio_optimizer_metadata.sql"),
            1,
        )

    def test_parser_accepts_multiple_migrations(self) -> None:
        old = sys.argv
        try:
            sys.argv = [
                "timeweb_auth_postgres.py",
                "--server-name", "server",
                "--server-comment", "comment",
                "--vpc-name", "vpc",
                "--cluster-name", "cluster",
                "--instance-name", "db",
                "--admin-login", "user",
                "--postgres-version", "18",
                "--location", "ru-3",
                "--availability-zone", "msk-1",
                "--max-price-rub", "1110",
                "--min-cpu", "1",
                "--min-ram-mb", "2048",
                "--min-disk-mb", "20480",
                "--migration", "migrations/0001.sql",
                "--migration", "migrations/0002.sql",
            ]
            args = MODULE.parse_args()
        finally:
            sys.argv = old

        self.assertEqual(
            args.migration,
            ["migrations/0001.sql", "migrations/0002.sql"],
        )

    def test_migrations_are_loaded_from_checkout_in_requested_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            migrations = root / "migrations"
            migrations.mkdir()
            (migrations / "0001.sql").write_text("SELECT 1;", encoding="utf-8")
            (migrations / "0002.sql").write_text("SELECT 2;", encoding="utf-8")
            with patch.object(MODULE, "__file__", root / ".github/scripts/deployer.py"):
                result = MODULE.load_migrations(["migrations/0001.sql", "migrations/0002.sql"])
        self.assertEqual(result, ["SELECT 1;", "SELECT 2;"])

    def test_migration_paths_fail_before_provider_access(self) -> None:
        paths = (
            "../outside.sql", "/tmp/outside.sql", "migrations/../outside.sql",
            "migrations/nested/file.sql", "migrations/config.env", "migrations/missing.sql",
            "migrations/invalid\x00.sql",
        )
        for path in paths:
            with (
                self.subTest(path=path),
                patch.object(MODULE, "parse_args", return_value=SimpleNamespace(migration=[path])),
                patch.object(MODULE, "TimewebClient") as provider,
                patch("sys.stderr"),
            ):
                self.assertEqual(MODULE.main(), 1)
                provider.assert_not_called()

    def test_migration_symlink_cannot_read_an_outside_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            migrations = root / "migrations"
            migrations.mkdir()
            outside = root / "outside.sql"
            outside.write_text("SELECT 'outside';", encoding="utf-8")
            (migrations / "0001.sql").symlink_to(outside)
            with (
                patch.object(MODULE, "__file__", root / ".github/scripts/deployer.py"),
                self.assertRaises(MODULE.InfraError),
            ):
                MODULE.load_migrations(["migrations/0001.sql"])

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
