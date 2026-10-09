#!/usr/bin/env python3
"""Regression tests for the private PostgreSQL reconciler."""

from __future__ import annotations

import ast
import importlib.util
import io
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import traceback
import unittest
from contextlib import ExitStack
from dataclasses import asdict, replace
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
UPGRADE = importlib.import_module("inplace_upgrade")
REVIEWED_MIGRATIONS = (
    "migrations/0027_assistant_stream_memory.sql",
    "migrations/0028_notification_device_binding.sql",
)


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

    def test_workflow_passes_only_reviewed_upgrade_migrations_in_order(self) -> None:
        root = MODULE_PATH.parents[2]
        workflow = (root / ".github/workflows/auth-postgres.yml").read_text(encoding="utf-8")
        migrations = list(REVIEWED_MIGRATIONS)
        self.assertEqual(len(migrations), 2)
        self.assertEqual([path.split("/")[-1][:4] for path in migrations], ["0027", "0028"])
        MODULE.migration_bodies(self.reviewed_upgrade_plan(), [
            (root / path).read_text(encoding="utf-8") for path in migrations
        ])
        lines = [line.strip() for line in workflow.splitlines()]
        first = lines.index(f"--migration {migrations[0]} ^")
        expected = [f"--migration {path} ^" for path in migrations[:-1]]
        expected.append(f"--migration {migrations[-1]}")
        self.assertEqual(lines[first:first + len(migrations)], expected)
        self.assertTrue(lines[first - 1].endswith(" ^"))
        self.assertEqual(workflow.count("--migration "), 2)
        for path in migrations:
            with self.subTest(migration=path):
                self.assertEqual(workflow.count(f"--migration {path}"), 1)

    def test_push_validation_queue_cannot_be_replaced_by_scheduled_or_manual_runs(self) -> None:
        workflow = (MODULE_PATH.parents[2] / ".github/workflows/auth-postgres.yml").read_text(
            encoding="utf-8",
        )
        header, jobs = workflow.split("\njobs:\n", 1)
        concurrency = header.split("\nconcurrency:\n", 1)[1]
        group = re.search(r"^  group: (.*?)\$\{\{\s*(.*?)\s*\}\}(.*?)$", concurrency, re.M)
        self.assertIsNotNone(group)
        self.assertIn("  cancel-in-progress: false\n", concurrency)
        terms = [term.strip() for term in group[2].split("||")]
        self.assertEqual(len(terms), 2)

        def queue(pr_number: int | None, run_id: int) -> str:
            # Evaluate only this workflow's nonzero-id/null fallback expression.
            # The previous 'production' literal is intentionally evaluable, so
            # the regression fails on its collision, without requiring Node here.
            context = {"github.event.pull_request.number": pr_number, "github.run_id": run_id}
            values = [context[term] if term in context else ast.literal_eval(term)
                      for term in terms]
            return group[1] + str(next(value for value in values if value)) + group[3]

        scenarios = (
            ("first PR", 765, 1001), ("same PR again", 765, 1002),
            ("other PR", 766, 1003),
            ("main push", None, 2001), ("scheduled maintenance", None, 2002),
            ("manual reconcile", None, 2003), ("later main push", None, 2004),
            ("later schedule", None, 2005), ("manual restore request", None, 2006),
        )
        groups = [queue(pr, run_id) for _, pr, run_id in scenarios]
        self.assertEqual(groups[0], groups[1], "The same PR retains one validation queue")
        self.assertEqual(len(set(groups)), len(scenarios) - 1,
                         "Each non-PR run needs a separate pending slot; false does not queue them")

        tests, mutations = jobs.split("\n  reconcile:\n", 1)
        self.assertNotIn("omnicio-production-ssh", tests)
        reconcile, restore = mutations.split("\n  isolated-restore:\n", 1)
        for name, block in (("reconcile", reconcile), ("restore", restore)):
            with self.subTest(job=name):
                lock = re.search(r"^    concurrency:\n((?:      [^\n]*\n)+)", block, re.M)
                self.assertIsNotNone(lock)
                self.assertEqual(lock[1], "      group: omnicio-production-ssh\n"
                                 "      cancel-in-progress: false\n      queue: max\n")
                self.assertIn("    needs: tests\n", block)
                self.assertIn("github.ref == 'refs/heads/main'", block)
        self.assertLess(reconcile.index("name: Verify current main release checks"),
                        reconcile.index("name: Validate Timeweb secret"))
        self.assertIn('OMNICIO_RESTORE_DRILL_ALLOWED: "false"', restore)

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

    def reviewed_upgrade_sql(self) -> list[str]:
        root = MODULE_PATH.parents[2]
        return [(root / path).read_text(encoding="utf-8") for path in REVIEWED_MIGRATIONS]

    def reviewed_upgrade_plan(self) -> dict:
        """Validate the frozen 1.3 contract without authorizing the current release."""
        fixture = MODULE_PATH.parents[2] / "tests/fixtures/accepted_upgrade_1_3.json"
        document = json.loads(fixture.read_text(encoding="utf-8"))
        plan = UPGRADE.validate_plan(document["plan"])
        UPGRADE.schema_query(document["source_schema"], plan["source_schema_sha256"])
        return plan

    def test_current_application_cannot_use_historical_upgrade_before_provider_access(self) -> None:
        with self.assertRaisesRegex(MODULE.UpgradeBlocked, "^application_version_mismatch$"):
            MODULE.load_plan()
        client = Mock()
        with self.assertRaisesRegex(MODULE.UpgradeBlocked, "^application_version_mismatch$"):
            MODULE.reconcile(
                client, desired=self.desired, server_name="server", server_comment="managed",
                vpc_name="private", migration_sqls=self.reviewed_upgrade_sql(),
                release_sha="a" * 40,
            )
        self.assertEqual(client.mock_calls, [])

    def test_inplace_rejects_changed_or_reordered_sql_before_provider_access(self) -> None:
        reviewed = self.reviewed_upgrade_sql()
        for statements in (reviewed[:1], reviewed[::-1], [reviewed[0] + "SELECT 1;", reviewed[1]]):
            client = Mock()
            with (
                self.subTest(count=len(statements)),
                patch.object(MODULE, "load_plan", return_value=self.reviewed_upgrade_plan()),
                self.assertRaises(MODULE.UpgradeBlocked),
            ):
                MODULE.reconcile(
                    client, desired=self.desired, server_name="server", server_comment="managed",
                    vpc_name="private", migration_sqls=statements, release_sha="a" * 40,
                )
            self.assertEqual(client.mock_calls, [])

    def test_inplace_uses_existing_python_and_requires_exact_remote_confirmation(self) -> None:
        valid = {"status": "applied", "cluster_id": MODULE.load_policy().cluster_id,
                 "release_sha": "a" * 40, "new_database_copies": 0}
        ssh = Mock()
        ssh.run.return_value = json.dumps(valid)
        arguments = dict(migration_sqls=self.reviewed_upgrade_sql(), release_sha="a" * 40,
                         endpoint=MODULE.DatabaseEndpoint("10.0.0.5", 5432), desired=self.desired)
        with patch.object(UPGRADE, "load_plan", return_value=self.reviewed_upgrade_plan()):
            MODULE.run_inplace_upgrade(ssh, **arguments)
        self.assertEqual(ssh.run.call_args.args, ("/opt/omnicio/current/.venv/bin/python -I -",))
        self.assertEqual(ssh.run.call_args.kwargs["stage"], MODULE.STAGE_SCHEMA_MIGRATION)
        compile(ssh.run.call_args.kwargs["input_text"], "reviewed-remote-program", "exec")
        for response in ("private-canary", json.dumps(None), json.dumps(valid | {"status": []}),
                         json.dumps(valid | {"cluster_id": 42}),
                         json.dumps(valid | {"release_sha": "b" * 40}),
                         json.dumps(valid | {"new_database_copies": False})):
            ssh.run.return_value = response
            with (
                self.subTest(response=response),
                patch.object(UPGRADE, "load_plan", return_value=self.reviewed_upgrade_plan()),
                self.assertRaisesRegex(
                    MODULE.InfraError, "^In-place upgrade result was not confirmed$",
                ),
            ):
                MODULE.run_inplace_upgrade(ssh, **arguments)

    def controller_arguments(self, *, backup_only: bool = False) -> SimpleNamespace:
        return SimpleNamespace(
            **asdict(self.desired),
            server_name="server", server_comment="managed", vpc_name="private",
            migration=["migrations/0001_phone_auth.sql"], backup_only=backup_only,
        )

    def test_full_release_checks_context_and_checkout_before_provider_access(self) -> None:
        sha = "a" * 40
        for backup_only in (False, True):
            with (
                self.subTest(backup_only=backup_only),
                patch.object(MODULE, "parse_args", return_value=self.controller_arguments(
                    backup_only=backup_only,
                )),
                patch.object(MODULE, "load_migrations", return_value=["SELECT 1;"]),
                patch.object(MODULE, "release_context",
                             return_value=(sha, "test-token")) as context,
                patch.object(MODULE, "require_checkout") as checkout,
                patch.object(MODULE, "TimewebClient") as provider,
                patch.object(MODULE, "reconcile", return_value=0) as reconcile,
            ):
                calls = []
                context.side_effect = lambda events=calls: (
                    events.append("context") or (sha, "test-token"))
                checkout.side_effect = lambda _, events=calls: events.append("checkout")
                provider.side_effect = lambda _, events=calls: events.append("provider")
                self.assertEqual(MODULE.main(), 0)
                self.assertEqual(calls, ["provider"] if backup_only else [
                    "context", "checkout", "provider",
                ])
                self.assertEqual(reconcile.call_args.kwargs["release_sha"],
                                 None if backup_only else sha)
                if backup_only:
                    context.assert_not_called()
                    checkout.assert_not_called()
                else:
                    checkout.assert_called_once_with(sha)

    def test_invalid_release_context_or_checkout_stops_before_timeweb(self) -> None:
        for boundary in ("release_context", "require_checkout"):
            with (
                self.subTest(boundary=boundary),
                patch.object(MODULE, "parse_args", return_value=self.controller_arguments()),
                patch.object(MODULE, "load_migrations", return_value=["SELECT 1;"]),
                patch.object(MODULE, "release_context", return_value=("a" * 40, "test-token")),
                patch.object(MODULE, "require_checkout"),
                patch.object(MODULE, boundary,
                             side_effect=MODULE.ReleaseBlocked("source rejected")),
                patch.object(MODULE, "TimewebClient") as provider,
                patch.object(MODULE, "reconcile") as reconcile,
                patch("sys.stderr"),
            ):
                self.assertEqual(MODULE.main(), 1)
                provider.assert_not_called()
                reconcile.assert_not_called()

    def test_scheduled_reconcile_cannot_receive_creation_authority(self) -> None:
        with patch.object(MODULE, "TimewebClient") as provider:
            client = provider.return_value
            with self.assertRaises(MODULE.InfraError):
                MODULE.reconcile(
                    client, desired=self.desired, server_name="server", server_comment="managed",
                    vpc_name="private", migration_sqls=["SELECT 1;"], backup_only=True,
                    release_sha="a" * 40,
                )
            self.assertEqual(client.mock_calls, [])

    def test_schema_command_preserves_sql_and_requests_only_safe_psql_diagnostics(self) -> None:
        ssh = Mock()
        sql = "SELECT 'synthetic-private-value';\n"
        MODULE.run_schema_migration(
            ssh, migration_sql=sql, migration_step=14,
            endpoint=MODULE.DatabaseEndpoint("10.0.0.5", 5432), desired=self.desired,
        )
        self.assertEqual(ssh.run.call_count, 2)
        install, execute = ssh.run.call_args_list
        self.assertEqual(install.kwargs, {"stage": "psql_client", "migration_step": 14})
        self.assertEqual(execute.kwargs, {
            "input_text": sql, "stage": MODULE.STAGE_SCHEMA_MIGRATION, "migration_step": 14,
        })
        command = execute.args[0]
        self.assertIn("-X -f - -v ON_ERROR_STOP=1", command)
        self.assertIn("-v VERBOSITY=sqlstate -v SHOW_CONTEXT=never", command)
        self.assertIn("statement_timeout=30000 -c lock_timeout=5000", command)
        self.assertNotIn(sql, command)
        self.assertNotIn("--echo", command)

    def test_failed_migration_stops_sequence_and_never_reports_readiness(self) -> None:
        cluster_id = MODULE.load_policy().cluster_id
        values = {
            "load_policy": replace(MODULE.load_policy(), mode="managed_backups"),
            "find_managed_server": {"id": 1}, "find_vpc": {"id": "private"},
            "find_vpc_service": {}, "private_server_cidr": "10.0.0.4/24",
            "select_postgres_type": "postgres18", "select_database_preset": {"id": 1},
            "find_database_cluster": {"id": cluster_id}, "public_ipv4": "192.0.2.1",
            "inspect_provider_recovery": {},
            "wait_for_database_endpoint": ({"id": cluster_id}, Mock()),
            "validate_existing_cluster": None, "service_matches": True,
            "ensure_recovery_point": None, "inspect_restore_capacity": None,
            "ensure_server_private_network": None, "load_or_create_server_secrets": {},
            "write_runtime_env": None, "set_output": None, "add_summary": None,
        }
        with ExitStack() as stack:
            stubs = {name: stack.enter_context(patch.object(MODULE, name, return_value=value))
                     for name, value in values.items()}
            ssh = stack.enter_context(patch.object(MODULE, "EphemeralSsh"))
            migration = stack.enter_context(patch.object(
                MODULE, "run_schema_migration", side_effect=[None, MODULE.InfraError("blocked")],
            ))
            client = Mock()
            client.get_vpc_services.return_value = [{}]
            with self.assertRaises(MODULE.InfraError):
                MODULE.reconcile(
                    client, desired=self.desired, server_name="server", server_comment="managed",
                    vpc_name="private", migration_sqls=["SELECT 1;", "SELECT 2;", "SELECT 3;"],
                )
        self.assertEqual([call.kwargs["migration_step"] for call in migration.call_args_list],
                         [1, 2])
        self.assertEqual([call.kwargs["migration_sql"] for call in migration.call_args_list],
                         ["SELECT 1;", "SELECT 2;"])
        stubs["set_output"].assert_not_called()
        ssh.return_value.__exit__.assert_called_once()

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


class RemoteDiagnosticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = MODULE.EphemeralSsh(
            client=Mock(), server_id=1, server_ip="192.0.2.1",
        )
        self.session._key_path = pathlib.Path("synthetic-key")
        self.session._known_hosts = pathlib.Path("synthetic-known-hosts")

    def test_sql_failure_reports_only_stage_step_code_and_numeric_line(self) -> None:
        sql = "SELECT 'sql-canary';"
        diagnostic = (
            b"psql:<stdin>:146: ERROR:  42501\r\n"
            b"DETAIL: password-canary\nCONTEXT: SELECT user-data-canary\n"
            b"psql: error: postgresql://connection-canary\n"
        )
        completed = subprocess.CompletedProcess([], 3, b"stdout-canary", diagnostic)
        with (
            patch.object(MODULE.subprocess, "run", return_value=completed) as process,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
            self.assertRaises(MODULE.InfraError) as error,
        ):
            self.session.run(
                "command-canary", input_text=sql,
                stage=MODULE.STAGE_SCHEMA_MIGRATION, migration_step=14,
            )
        self.assertEqual(str(error.exception),
                         "Remote command failed (stage=schema_migration, migration_step=14, "
                         "exit_code=3, sqlstate=42501, psql_line=146)")
        self.assertNotIn("canary", str(error.exception) + stdout.getvalue() + stderr.getvalue())
        process.assert_called_once()
        self.assertEqual(process.call_args.kwargs["input"], sql.encode("utf-8"))

    def test_unknown_oversized_or_ambiguous_stderr_never_becomes_free_text(self) -> None:
        unknown = "sqlstate=unknown, psql_line=unknown"
        for data in (
            b"psql: error: connection-password-canary", b"\xffprivate-canary",
            b"DETAIL: psql:<stdin>:2: ERROR:  42501",
            b"psql:<stdin>:0: ERROR:  42501", b"psql:<stdin>:1234567890: ERROR:  42501",
            b"psql:<stdin>:2: ERROR:  42501 SQL-canary",
            b"psql:<stdin>:2: ERROR:  42p01",
            b"ERROR:  42501\nERROR:  22012\n",
            b"x" * (MODULE.MAX_DIAGNOSTIC_BYTES + 1),
        ):
            with self.subTest(size=len(data)):
                self.assertEqual(MODULE.psql_failure_fields(data), unknown)
        self.assertEqual(MODULE.psql_failure_fields(b"FATAL:  28P01\n"),
                         "sqlstate=28P01, psql_line=unknown")

    def test_non_sql_failures_ignore_stderr_and_reject_untrusted_context(self) -> None:
        completed = subprocess.CompletedProcess([], 255, b"stdout-canary", b"ERROR:  42501")
        with (
            patch.object(MODULE.subprocess, "run", return_value=completed) as process,
            self.assertRaises(MODULE.InfraError) as error,
        ):
            self.session.run("command-canary")
        self.assertEqual(str(error.exception),
                         "Remote command failed (stage=remote_command, exit_code=255)")
        process.assert_called_once()
        for context in ({"stage": "private-canary"}, {"migration_step": True},
                        {"migration_step": -1}, {"migration_step": "private-canary"},
                        {"migration_step": 10000}):
            with (
                self.subTest(context=context),
                patch.object(MODULE.subprocess, "run") as process,
                self.assertRaises(MODULE.InfraError) as error,
            ):
                self.session.run("unused", **context)
            process.assert_not_called()
            self.assertNotIn("canary", str(error.exception))

    def test_timeout_omits_command_output_and_original_exception_without_retry(self) -> None:
        timeout = subprocess.TimeoutExpired(
            "command-canary", 90, output=b"stdout-canary", stderr=b"password-canary",
        )
        with (
            patch.object(MODULE.subprocess, "run", side_effect=timeout) as process,
            self.assertRaises(MODULE.InfraError) as error,
        ):
            self.session.run("command-canary", stage="runtime_env")
        self.assertEqual(str(error.exception), "Remote command timed out (stage=runtime_env)")
        self.assertNotIn("canary", "".join(traceback.format_exception(error.exception)))
        self.assertTrue(error.exception.__suppress_context__)
        process.assert_called_once()

    def test_long_deploy_budget_does_not_change_default_remote_command_budget(self) -> None:
        completed = subprocess.CompletedProcess([], 0, b"", b"")
        with patch.object(MODULE.subprocess, "run", return_value=completed) as process:
            self.session.run("read current state")
            self.assertEqual(process.call_args.kwargs["timeout"], 90)
            self.session.run("bounded deployment", timeout=900)
            self.assertEqual(process.call_args.kwargs["timeout"], 900)
            self.assertEqual(process.call_count, 2)

    def test_successful_generic_command_keeps_exact_stdout_consumer(self) -> None:
        output = "Сохранённые значения\nsynthetic-secret=unchanged\n"
        with patch.object(MODULE.subprocess, "run", return_value=subprocess.CompletedProcess(
            [], 0, output.encode("utf-8"), b"ignored stderr",
        )) as process:
            self.assertEqual(self.session.run("read existing secret"), output)
        process.assert_called_once()


if __name__ == "__main__":
    unittest.main()
