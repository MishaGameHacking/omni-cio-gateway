#!/usr/bin/env python3
"""Regression tests for the private PostgreSQL reconciler."""

from __future__ import annotations

import ast
import hashlib
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
from contextlib import ExitStack, closing, nullcontext
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
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
    "migrations/0029_email_auth.sql",
    "migrations/0030_portfolio_read_only.sql",
)
HISTORICAL_MIGRATIONS = (
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
        self.assertEqual([path.split("/")[-1][:4] for path in migrations], ["0029", "0030"])
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

    def test_cutover_preflight_matches_application_environment(self) -> None:
        root = MODULE_PATH.parents[2] / ".github/workflows"

        def environment(filename: str, job: str) -> dict[str, str]:
            text = (root / filename).read_text(encoding="utf-8").split(f"\n  {job}:\n", 1)[1]
            block = text.split("\n    env:\n", 1)[1].split("\n    steps:\n", 1)[0]
            return dict(re.findall(r"^      ([A-Z][A-Z0-9_]*): ([^\n]*)$", block, re.M))

        app = environment("auth-app-deploy.yml", "deploy")
        postgres = environment("auth-postgres.yml", "reconcile")
        self.assertEqual({name: postgres.get(name) for name in app}, app)

    def test_workflow_defaults_to_inspection_and_keeps_recipient_out_of_commands(self) -> None:
        workflow = (MODULE_PATH.parents[2] / ".github/workflows/auth-postgres.yml").read_text(
            encoding="utf-8",
        )
        operation_input = workflow.split("      operation:\n", 1)[1].split(
            "      smtp_probe_recipient:\n", 1,
        )[0]
        self.assertIn("        default: preflight\n", operation_input)
        self.assertEqual(re.findall(r"^          - ([a-z_]+)$", operation_input, re.M),
                         ["preflight", "email_probe", "apply"])
        self.assertIn(
            "OMNICIO_POSTGRES_OPERATION: ${{ github.event_name == 'workflow_dispatch' "
            "&& inputs.operation || 'preflight' }}", workflow,
        )
        self.assertIn(
            "OMNICIO_SMTP_PROBE_RECIPIENT: ${{ github.event_name == 'workflow_dispatch' "
            "&& inputs.smtp_probe_recipient || '' }}", workflow,
        )
        commands = workflow.split("\n  reconcile:\n", 1)[1].split("\n    steps:\n", 1)[1]
        self.assertNotIn("SMTP_PROBE_RECIPIENT", commands)
        self.assertNotIn("inputs.smtp_probe_recipient", commands)
        self.assertNotIn("--operation apply", commands)

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
        """Bind current migration content to the accepted 1.3 source readiness."""
        fixture = MODULE_PATH.parents[2] / "tests/fixtures/accepted_upgrade_1_3.json"
        document = json.loads(fixture.read_text(encoding="utf-8"))
        plan = UPGRADE.load_plan()
        UPGRADE.schema_query(document["target_schema"], plan["source_schema_sha256"])
        return plan

    def test_current_application_cannot_use_historical_upgrade_before_provider_access(self) -> None:
        root = MODULE_PATH.parents[2]
        historical = json.loads((root / "tests/fixtures/accepted_upgrade_1_3.json").read_text(
            encoding="utf-8",
        ))
        historical_sqls = [
            (root / path).read_text(encoding="utf-8") for path in HISTORICAL_MIGRATIONS
        ]
        UPGRADE.migration_bodies(historical["plan"], historical_sqls)
        document = {"project": {"version": "1.4.0"},
                    "tool": {"omnicio": {"timeweb": {"upgrade": historical["plan"]}}}}
        client = Mock()
        with (
            patch.object(UPGRADE.tomllib, "load", return_value=document),
            self.assertRaisesRegex(MODULE.UpgradeBlocked, "^application_version_mismatch$"),
        ):
            MODULE.load_plan()
        with (
            patch.object(UPGRADE, "load_plan", return_value=historical["plan"]),
            self.assertRaisesRegex(MODULE.UpgradeBlocked, "^application_version_mismatch$"),
        ):
            UPGRADE.render_remote_upgrade(
                historical_sqls, release_sha="a" * 40, database={},
            )
        with (
            patch.object(UPGRADE.tomllib, "load", return_value=document),
            patch.object(MODULE, "load_policy", return_value=SimpleNamespace(
                mode=UPGRADE.MODE,
            )),
            self.assertRaisesRegex(MODULE.UpgradeBlocked, "^application_version_mismatch$"),
        ):
            MODULE.reconcile(
                client, desired=self.desired, server_name="server", server_comment="managed",
                vpc_name="private", migration_sqls=["BEGIN;\nSELECT 1;\nCOMMIT;\n"],
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
                         endpoint=MODULE.DatabaseEndpoint("10.0.0.5", 5432), desired=self.desired,
                         operation="apply")
        environment = {
            "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/main",
            "GITHUB_SHA": "a" * 40,
            "LEGAL_OPERATOR_NAME": "Synthetic Operator",
            "LEGAL_OPERATOR_EMAIL": "operator@example.test",
            "LEGAL_PRIVACY_VERSION": "test-v1",
            "LEGAL_CONSENT_VERSION": "test-v1",
            "LEGAL_TERMS_VERSION": "test-v1",
        }
        with (
            patch.dict(MODULE.os.environ, environment, clear=True),
            patch.object(UPGRADE, "load_plan", return_value=self.reviewed_upgrade_plan()),
        ):
            MODULE.run_inplace_upgrade(ssh, **arguments)
            self.assertEqual(
                ssh.run.call_args.args, ("/opt/omnicio/current/.venv/bin/python -I -",),
            )
            self.assertEqual(ssh.run.call_args.kwargs["stage"], MODULE.STAGE_SCHEMA_MIGRATION)
            compile(ssh.run.call_args.kwargs["input_text"], "reviewed-remote-program", "exec")
            for response in ("private-canary", json.dumps(None), json.dumps(valid | {"status": []}),
                             json.dumps(valid | {"cluster_id": 42}),
                             json.dumps(valid | {"release_sha": "b" * 40}),
                             json.dumps(valid | {"new_database_copies": False})):
                ssh.run.return_value = response
                with (
                    self.subTest(response=response),
                    self.assertRaisesRegex(
                        MODULE.InfraError, "^In-place upgrade result was not confirmed$",
                    ),
                ):
                    MODULE.run_inplace_upgrade(ssh, **arguments)

    def current_cutover_arguments(self) -> dict:
        from timeweb_auth_app import DEPLOY_LOCK

        plan = self.reviewed_upgrade_plan()
        database = {"cluster_id": 4215095, "host": "10.0.0.5", "port": 5432,
                    "database": "omnicio", "user": "omnicio_app"}
        return {
            "plan": plan, "url": "synthetic-database",
            "payload": {"plan": plan, "database": database, "release_sha": "a" * 40,
                        "statements": self.reviewed_upgrade_sql(), "target_query": "target",
                        "application_version": plan["target_version"],
                        "deployment_lock": DEPLOY_LOCK},
            "identity": UPGRADE.operation_identity(plan, database), "receipt": None,
            "source_query": "source", "installed_release": plan["source_release"],
            "recovery_validator": Mock(), "product_preflight": Mock(return_value={
                "status": "configuration_ready",
            }),
        }

    def writer_state(self) -> dict:
        return {
            unit: {"active": unit != "omnicio-observer.service",
                   "enabled": "static" if unit == "omnicio-observer.service" else "enabled"}
            for unit in UPGRADE.WRITER_UNITS
        }

    def inspection_report(self, *, operation: str = "preflight", ready: bool = True) -> dict:
        return {
            "status": "preflight_ready" if ready else "preflight_blocked",
            "operation": operation, "cluster_id": 4215095,
            "release_sha": "a" * 40, "new_database_copies": 0, "schema": "source_ready",
            "recovery": ({"status": "ready", "code": "recovery_verified"} if ready else
                         {"status": "blocked", "code": "upgrade_recovery_unavailable"}),
            "configuration": {
                "status": "configuration_ready", "smtp_delivery_verified": False,
                "market_token_configured": False, "market_distribution_approved": False,
            },
            "email_probe": ({"status": "accepted", "code": "email_provider_accepted",
                             "message_id": "<smtp-probe-1.4-aaaaaaaaaaaa-123@omnicio.ru>"}
                            if operation == "email_probe" else
                            {"status": "not_requested", "code": "not_requested", "message_id": ""}),
        }

    def test_remote_inspection_reads_both_checks_without_mutating_source_or_target(self) -> None:
        import psycopg

        cases = (
            (False, False, False, "preflight"), (False, True, False, "preflight"),
            (False, False, True, "preflight"), (False, True, True, "preflight"),
            (True, True, False, "preflight"), (True, False, False, "preflight"),
            (False, True, False, "email_probe"), (False, False, True, "email_probe"),
        )
        for target_ready, recovery_failed, configuration_failed, operation in cases:
            arguments = self.current_cutover_arguments()
            payload = arguments["payload"] | {"operation": operation}
            # A missing current-operation field must also take the read-only route.
            if not any((target_ready, recovery_failed, configuration_failed)):
                payload.pop("operation")
            receipt = None
            if target_ready:
                receipt = {
                    "identity": arguments["identity"], "phase": "pending",
                    "release_sha": payload["release_sha"],
                    "installed_release": arguments["installed_release"],
                    "writers": self.writer_state(),
                }
            configuration = Mock(return_value=self.inspection_report()["configuration"])
            if configuration_failed:
                configuration.side_effect = ValueError("private-configuration-canary")
            probe = Mock(return_value=self.inspection_report(
                operation="email_probe",
            )["email_probe"])
            readonly = {
                "_database_url": "synthetic-connection",
                "_read_receipt": receipt,
                "_existing_installation": ("source", arguments["installed_release"]),
                "_verify_connected_database": None, "_verify_upgrade_role": None,
                "_source_is_ready": True, "_assert_writers_stopped": None,
                "_require_recovery": None, "_inspection_lock": nullcontext(),
            }
            mutators = ("_operation_lock", "_receipt_directory", "_write_receipt", "_change_units",
                        "_capture_writer_state", "_drain_writers", "_restore_writers",
                        "apply_upgrade", "_apply_current_upgrade")
            case = (target_ready, recovery_failed, configuration_failed, operation)
            with self.subTest(case=case):
                with ExitStack() as stack:
                    stack.enter_context(patch.object(UPGRADE.sys, "platform", "linux"))
                    stubs = {name: stack.enter_context(patch.object(
                        UPGRADE, name, return_value=value,
                    )) for name, value in readonly.items()}
                    mutations = {name: stack.enter_context(patch.object(UPGRADE, name))
                                 for name in mutators}
                    if recovery_failed:
                        stubs["_require_recovery"].side_effect = UPGRADE.UpgradeBlocked(
                            "upgrade_recovery_unavailable",
                        )
                    connect = stack.enter_context(patch.object(psycopg, "connect"))
                    connection = connect.return_value.__enter__.return_value
                    connection.execute.return_value.fetchone.side_effect = [
                        (True,), (target_ready,),
                    ]
                    output = stack.enter_context(patch("sys.stdout", new_callable=io.StringIO))
                    UPGRADE.remote_main(
                        payload, recovery_validator=arguments["recovery_validator"],
                        product_preflight=configuration, smtp_probe=probe,
                    )
                    report = json.loads(output.getvalue())
                self.assertIn("-c default_transaction_read_only=on",
                              connect.call_args.kwargs["options"])
                self.assertEqual([call.args[0] for call in connection.execute.call_args_list],
                                 ["SELECT pg_try_advisory_lock(4215095001300)", "target"])
                self.assertEqual(report["schema"],
                                 "target_ready" if target_ready else "source_ready")
                self.assertEqual(report["recovery"]["status"],
                                 "blocked" if recovery_failed else "ready")
                self.assertEqual(report["configuration"]["status"],
                                 "blocked" if configuration_failed else "configuration_ready")
                self.assertEqual(report["status"], "preflight_blocked" if recovery_failed
                                 or configuration_failed else "preflight_ready")
                self.assertNotIn("private-configuration-canary", json.dumps(report))
                self.assertEqual(probe.call_count, int(operation == "email_probe"
                                                      and not configuration_failed))
                stubs["_require_recovery"].assert_called_once()
                stubs["_inspection_lock"].assert_called_once_with(payload["deployment_lock"])
                configuration.assert_called_once_with()
                for name, mutation in mutations.items():
                    self.assertEqual(mutation.call_count, 0, name)

    def test_inspection_lock_requires_existing_trusted_inode_without_creating_files(self) -> None:
        for failure in (None, "missing", "symlink", "writable", "contended", "replaced"):
            path = Mock()
            path.parent.lstat.return_value = SimpleNamespace(
                st_mode=UPGRADE.stat.S_IFDIR | 0o755, st_uid=0,
            )
            details = SimpleNamespace(
                st_mode=UPGRADE.stat.S_IFREG | (0o666 if failure == "writable" else 0o644),
                st_uid=0, st_dev=1, st_ino=2,
            )
            path.lstat.return_value = (SimpleNamespace(st_dev=1, st_ino=3)
                                      if failure == "replaced" else details)
            handle = Mock()
            handle.fileno.return_value = 42
            filesystem = SimpleNamespace(
                O_RDONLY=0, O_NOFOLLOW=131072, O_CREAT=64, open=Mock(return_value=42),
                fdopen=Mock(return_value=closing(handle)), fstat=Mock(return_value=details),
            )
            if failure in ("missing", "symlink"):
                filesystem.open.side_effect = FileNotFoundError("private-path-canary")
            fcntl = SimpleNamespace(LOCK_EX=2, LOCK_NB=4, flock=Mock())
            if failure == "contended":
                fcntl.flock.side_effect = BlockingIOError("busy")
            with (
                self.subTest(failure=failure),
                patch.object(UPGRADE.sys, "platform", "linux"),
                patch.object(UPGRADE, "os", filesystem),
                patch.object(UPGRADE.pathlib, "Path", return_value=path),
                patch.dict(sys.modules, {"fcntl": fcntl}),
            ):
                entered = False
                if failure is None:
                    with UPGRADE._inspection_lock("existing-deployment-lock"):
                        entered = True
                        handle.close.assert_not_called()
                else:
                    with (
                        self.assertRaises(UPGRADE.UpgradeBlocked),
                        UPGRADE._inspection_lock("existing-deployment-lock"),
                    ):
                        entered = True
            self.assertEqual(entered, failure is None)
            filesystem.open.assert_called_once_with(
                path, filesystem.O_RDONLY | filesystem.O_NOFOLLOW,
            )
            if failure not in ("missing", "symlink"):
                handle.close.assert_called_once_with()
            if failure not in ("missing", "symlink", "writable"):
                fcntl.flock.assert_called_once_with(42, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_inspection_source_mismatch_prevents_probe_and_all_mutation(self) -> None:
        arguments = self.current_cutover_arguments()
        arguments["payload"]["operation"] = "email_probe"
        arguments.pop("url")
        arguments.pop("identity")
        arguments["smtp_probe"] = Mock()
        connection = Mock()
        connection.execute.return_value.fetchone.return_value = (False,)
        with (
            patch.object(UPGRADE, "_verify_upgrade_role"),
            patch.object(UPGRADE, "_source_is_ready", return_value=False),
            patch.object(UPGRADE, "_require_recovery") as recovery,
            patch.object(UPGRADE, "_operation_lock") as mutation,
            self.assertRaisesRegex(UPGRADE.UpgradeBlocked,
                                   "^source_schema_is_not_reviewed_baseline$"),
        ):
            UPGRADE._inspect_current_upgrade(connection, **arguments)
        recovery.assert_not_called()
        mutation.assert_not_called()
        arguments["product_preflight"].assert_not_called()
        arguments["smtp_probe"].assert_not_called()

    def test_inspection_report_requires_exact_types_and_never_promotes_readiness(self) -> None:
        valid = self.inspection_report(ready=False)
        kwargs = dict(cluster_id=4215095, release_sha="a" * 40,
                      operation="preflight", message_id="")
        self.assertEqual(MODULE._read_upgrade_result(json.dumps(valid), **kwargs), valid)
        variants = (
            valid | {"status": "database_ready"}, valid | {"status": "preflight_ready"},
            valid | {"new_database_copies": False}, valid | {"secret": "private-canary"},
            valid | {"recovery": []}, valid | {"configuration": None},
            valid | {"configuration": valid["configuration"] | {"smtp_delivery_verified": True}},
            valid | {"recovery": {"status": "blocked", "code": "private canary"}},
            valid | {"schema": []},
            valid | {"email_probe": {"status": [], "code": [], "message_id": ""}},
        )
        for value in variants:
            raw = json.dumps(value)
            with self.subTest(value=value), self.assertRaisesRegex(
                MODULE.InfraError, "^In-place upgrade result was not confirmed$",
            ):
                MODULE._read_upgrade_result(raw, **kwargs)

    def test_generated_inspection_program_is_bounded_and_probe_is_only_explicit(self) -> None:
        environment = {
            "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/main",
            "GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1",
            "OMNICIO_SMTP_PROBE_RECIPIENT": "synthetic-recipient@gmail.com",
            "LEGAL_OPERATOR_NAME": "Synthetic Operator", "LEGAL_OPERATOR_EMAIL": "a@example.test",
            "LEGAL_PRIVACY_VERSION": "test", "LEGAL_CONSENT_VERSION": "test",
            "LEGAL_TERMS_VERSION": "test",
        }
        for operation in ("preflight", "email_probe"):
            for invalid_local_configuration in (False, True):
                values = environment | ({"AUTH_SMTP_HOST": "bad host"}
                                        if invalid_local_configuration else {})
                ssh = Mock()
                report = self.inspection_report(operation=operation, ready=False)
                ssh.run.return_value = json.dumps(report)
                with (
                    self.subTest(operation=operation, invalid=invalid_local_configuration),
                    patch.dict(MODULE.os.environ, values, clear=True),
                ):
                    actual = MODULE.run_inplace_upgrade(
                        ssh, migration_sqls=self.reviewed_upgrade_sql(), release_sha="a" * 40,
                        endpoint=MODULE.DatabaseEndpoint("10.0.0.5", 5432), desired=self.desired,
                        operation=operation,
                    )
                self.assertEqual(actual, report)
                self.assertEqual(ssh.run.call_count, 1)
                self.assertEqual(ssh.run.call_args.args, (
                    "timeout --kill-after=5s 180s /opt/omnicio/current/.venv/bin/python -I -B -",
                ))
                self.assertEqual(ssh.run.call_args.kwargs["timeout"], 200)
                program = ssh.run.call_args.kwargs["input_text"]
                compile(program, "reviewed-inspection-program", "exec")
                self.assertEqual("smtp_probe=send_upgrade_control_email" in program,
                                 operation == "email_probe")
                if invalid_local_configuration:
                    self.assertIn('raise UpgradeBlocked("product_configuration_invalid")', program)

    def test_cutover_preflight_failure_does_not_write_receipts_or_stop_source(self) -> None:
        for failure in ("source", "recovery", "configuration", "missing_verifier"):
            arguments = self.current_cutover_arguments()
            connection = Mock()
            connection.execute.return_value.fetchone.return_value = (False,)
            if failure == "missing_verifier":
                arguments["recovery_validator"] = None
            if failure == "configuration":
                arguments["product_preflight"].side_effect = UPGRADE.UpgradeBlocked("smtp_missing")
            with (
                self.subTest(failure=failure),
                patch.object(UPGRADE, "_verify_upgrade_role"),
                patch.object(UPGRADE, "_source_is_ready", return_value=failure != "source"),
                patch.object(UPGRADE, "_require_recovery", side_effect=(
                    UPGRADE.UpgradeBlocked("proof_missing") if failure == "recovery" else None,
                )) as proof,
                patch.object(UPGRADE, "_operation_lock") as lock,
                patch.object(UPGRADE, "_write_receipt") as write,
                patch.object(UPGRADE, "_drain_writers") as stop,
                self.assertRaises(UPGRADE.UpgradeBlocked),
            ):
                UPGRADE._apply_current_upgrade(connection, **arguments)
            lock.assert_not_called()
            write.assert_not_called()
            stop.assert_not_called()
            if failure in ("source", "missing_verifier"):
                proof.assert_not_called()

    def test_cutover_records_original_writers_and_stops_them_before_migration(self) -> None:
        arguments = self.current_cutover_arguments()
        connection = Mock()
        connection.execute.return_value.fetchone.side_effect = [(False,), (True,)]
        events = []
        arguments["product_preflight"].side_effect = lambda: events.append("configuration")
        writers = self.writer_state()
        with (
            patch.object(UPGRADE, "_verify_upgrade_role"),
            patch.object(UPGRADE, "_source_is_ready", return_value=True),
            patch.object(UPGRADE, "_require_recovery",
                         side_effect=lambda *_: events.append("proof")),
            patch.object(UPGRADE, "_operation_lock", nullcontext),
            patch.object(UPGRADE, "_capture_writer_state", return_value=writers),
            patch.object(UPGRADE, "_write_receipt", side_effect=lambda _: events.append("receipt"))
                as write,
            patch.object(UPGRADE, "_drain_writers", side_effect=lambda _: events.append("stop")),
            patch.object(UPGRADE, "apply_upgrade", side_effect=lambda *_args, **_kwargs:
                         events.append("migration") or "applied"),
        ):
            self.assertEqual(UPGRADE._apply_current_upgrade(connection, **arguments), "applied")
        self.assertEqual(events, ["proof", "configuration", "receipt", "stop", "migration"])
        recorded = write.call_args.args[0]
        self.assertEqual(recorded["writers"], writers)
        self.assertEqual(recorded["phase"], "pending")
        self.assertEqual(recorded["identity"], arguments["identity"])

    def test_cutover_failure_resumes_only_a_proven_source_schema(self) -> None:
        for source_verified in (True, False):
            arguments = self.current_cutover_arguments()
            connection = Mock()
            connection.execute.return_value.fetchone.return_value = (False,)
            with (
                self.subTest(source_verified=source_verified),
                patch.object(UPGRADE, "_verify_upgrade_role"),
                patch.object(UPGRADE, "_source_is_ready", return_value=True),
                patch.object(UPGRADE, "_require_recovery"),
                patch.object(UPGRADE, "_operation_lock", nullcontext),
                patch.object(UPGRADE, "_capture_writer_state", return_value=self.writer_state()),
                patch.object(UPGRADE, "_write_receipt"),
                patch.object(UPGRADE, "_drain_writers"),
                patch.object(UPGRADE, "apply_upgrade", side_effect=UPGRADE.UpgradeBlocked(
                    "migration_failed",
                )),
                patch.object(UPGRADE, "_resume_source_after_failure", return_value=source_verified)
                    as resume,
                self.assertRaisesRegex(UPGRADE.UpgradeBlocked, (
                    "^migration_failed$" if source_verified
                    else "^upgrade_failed_writers_remain_stopped$"
                )),
            ):
                UPGRADE._apply_current_upgrade(connection, **arguments)
            connection.close.assert_called_once_with()
            self.assertEqual(resume.call_args.args[-1], self.writer_state())

    def test_committed_cutover_reconciles_without_repeating_stop_or_initial_preflight(self) -> None:
        arguments = self.current_cutover_arguments()
        arguments["receipt"] = {
            "identity": arguments["identity"], "phase": "pending", "release_sha": "a" * 40,
            "installed_release": arguments["plan"]["source_release"],
            "writers": self.writer_state(),
        }
        connection = Mock()
        connection.execute.return_value.fetchone.return_value = (True,)
        with (
            patch.object(UPGRADE, "_verify_upgrade_role"),
            patch.object(UPGRADE, "_assert_writers_stopped") as stopped,
            patch.object(UPGRADE, "_require_recovery") as proof,
            patch.object(UPGRADE, "_operation_lock", nullcontext),
            patch.object(UPGRADE, "_drain_writers") as stop,
            patch.object(UPGRADE, "apply_upgrade", return_value="already_applied") as apply,
        ):
            self.assertEqual(UPGRADE._apply_current_upgrade(connection, **arguments),
                             "already_applied")
        stopped.assert_called_once_with()
        proof.assert_not_called()
        arguments["product_preflight"].assert_not_called()
        stop.assert_not_called()
        self.assertEqual(apply.call_args.kwargs["receipt"]["writers"], self.writer_state())

    def test_quiescence_disables_previous_boot_targets_before_stopping_writers(self) -> None:
        calls = []
        with (
            patch.object(UPGRADE, "_change_units", side_effect=lambda command, units:
                         calls.append((command, units))),
            patch.object(UPGRADE, "_assert_writers_stopped") as verify,
        ):
            UPGRADE._drain_writers(self.writer_state())
        self.assertEqual(calls, [
            ("disable", ["omnicio-auth.service", "omnicio-observer.timer"]),
            ("stop", ["omnicio-observer.timer", "omnicio-observer.service",
                      "omnicio-auth.service"]),
        ])
        verify.assert_called_once_with()

    def test_upgrade_requires_unprivileged_role_and_does_not_grant_identity_access(self) -> None:
        connection = Mock()
        for flags in ((False, False, False, False, False), (True, False, False, False, False),
                      (False, True, False, False, False), (False, False, True, False, False),
                      (False, False, False, True, False), (False, False, False, False, True), None):
            connection.execute.return_value.fetchone.return_value = flags
            if flags == (False, False, False, False, False):
                UPGRADE._verify_upgrade_role(connection)
            else:
                with self.subTest(flags=flags), self.assertRaisesRegex(
                    UPGRADE.UpgradeBlocked, "^upgrade_database_role_is_privileged$",
                ):
                    UPGRADE._verify_upgrade_role(connection)
        connection.reset_mock()
        connection.execute.return_value.fetchone.return_value = (False,)
        plan = self.reviewed_upgrade_plan()
        validator = Mock()
        with (
            patch.object(UPGRADE, "_operational_bytes") as read,
            self.assertRaisesRegex(UPGRADE.UpgradeBlocked,
                                   "^recovery_system_identity_access_unavailable$"),
        ):
            UPGRADE._require_recovery(connection, plan, {}, validator)
        read.assert_not_called()
        self.assertTrue(connection.execute.call_args.args[0].startswith("SELECT "))

    def test_recovery_consumer_decrypts_existing_ciphertext_and_decodes_quoted_keys(self) -> None:
        from cryptography.fernet import Fernet
        from timeweb_auth_app import _environment_value

        from omnicio.recovery import require_upgrade_recovery, sign_recovery_evidence

        plan = self.reviewed_upgrade_plan()
        signing_key = 'synthetic-only-$key`with\\quote"' * 2
        archive_key = Fernet.generate_key().decode()
        raw = b"PGDMP synthetic test data only"
        encrypted = Fernet(archive_key).encrypt(raw)
        now = datetime.now(UTC)
        identity = {
            "source_kind": "runtime_pg_dump", "cluster_id": 4215095,
            "release_sha": plan["source_release"],
            "source_at": (now - timedelta(minutes=2)).isoformat(),
            "source_system_id": "12345", "archive_sha256": hashlib.sha256(raw).hexdigest(),
        }
        manifest = sign_recovery_evidence({
            **identity, "kind": "logical_export_v1", "encrypted_sha256":
                hashlib.sha256(encrypted).hexdigest(), "content_digest": "a" * 64,
            "schema_digest": "b" * 64,
        }, signing_key)
        state = {"schema_version": 1, "cluster_id": 4215095, "restore_verification":
                 sign_recovery_evidence({
                     **identity, "kind": "logical_restore_v1", "target_system_id": "12346",
                     "verified_at": (now - timedelta(minutes=1)).isoformat(), "duration_seconds": 1,
                     "checks": dict.fromkeys(
                         ("content", "schema", "foreign_keys", "tenant_isolation"), True,
                     ),
                 }, signing_key)}
        for corrupt in (False, True):
            files = {
                "status.json": json.dumps(state).encode(),
                "manifest.json": json.dumps(manifest).encode(),
                "database.dump.encrypted": encrypted[:-1] + b"!" if corrupt else encrypted,
                "product.env": (
                    "OMNICIO_RESTORE_RECEIPT_KEY=" + _environment_value(signing_key) + "\n"
                    "OMNICIO_RESTORE_ARCHIVE_KEY=" + _environment_value(archive_key) + "\n"
                ).encode(),
            }
            connection = Mock()
            connection.execute.return_value.fetchone.side_effect = [(True,), ("12345",)]
            validator = Mock(wraps=require_upgrade_recovery)
            with (
                self.subTest(corrupt=corrupt),
                patch.object(UPGRADE, "_operational_bytes", side_effect=lambda path, *_args,
                             source_files=files, **_kwargs: source_files[path.name]) as read,
                patch.object(UPGRADE, "_write_receipt") as write,
                patch.object(UPGRADE, "_change_units") as units,
            ):
                if corrupt:
                    with self.assertRaisesRegex(UPGRADE.UpgradeBlocked,
                                               "^upgrade_recovery_unavailable$"):
                        UPGRADE._require_recovery(connection, plan, {"cluster_id": 4215095},
                                                  validator)
                    validator.assert_not_called()
                else:
                    UPGRADE._require_recovery(connection, plan, {"cluster_id": 4215095}, validator)
                    self.assertEqual(validator.call_args.kwargs["decrypted_archive_sha256"],
                                     hashlib.sha256(raw).hexdigest())
                    self.assertEqual(read.call_args_list[0].kwargs, {"private": False})
            write.assert_not_called()
            units.assert_not_called()

    def test_writer_resume_needs_reconnected_source_evidence(self) -> None:
        import psycopg

        plan = self.reviewed_upgrade_plan()
        for source_status in (True, False, None):
            with (
                self.subTest(source_status=source_status),
                patch("psycopg.connect") as connect,
                patch.object(UPGRADE, "CURRENT_RELEASE", SimpleNamespace(resolve=lambda **_:
                             UPGRADE.RELEASE_ROOT / plan["source_release"])),
                patch.object(UPGRADE, "_verify_connected_database"),
                patch.object(UPGRADE, "_verify_upgrade_role"),
                patch.object(UPGRADE, "_source_is_ready", return_value=source_status,
                             side_effect=psycopg.OperationalError("synthetic connection lost")
                             if source_status is None else None),
                patch.object(UPGRADE, "_restore_writers") as resume,
            ):
                connection = connect.return_value.__enter__.return_value
                connection.execute.return_value.fetchone.return_value = (True,)
                self.assertEqual(UPGRADE._resume_source_after_failure(
                    "synthetic-only", {}, plan, "source", self.writer_state(),
                ), source_status is True)
            self.assertEqual(resume.call_count, int(source_status is True))

    def controller_arguments(self, *, backup_only: bool = False) -> SimpleNamespace:
        return SimpleNamespace(
            **asdict(self.desired),
            server_name="server", server_comment="managed", vpc_name="private",
            migration=["migrations/0001_phone_auth.sql"], backup_only=backup_only,
            operation="preflight",
        )

    def test_mutating_cli_operations_require_manual_main_before_provider_access(self) -> None:
        environment = {"GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/main",
                       "GITHUB_SHA": "a" * 40, "GITHUB_RUN_ATTEMPT": "1"}
        cases = (
            ("apply", {"GITHUB_EVENT_NAME": "push"}),
            ("apply", {"GITHUB_EVENT_NAME": "schedule"}),
            ("apply", {"GITHUB_REF": "refs/heads/candidate"}),
            ("apply", {"GITHUB_SHA": "b" * 40}),
            ("email_probe", {"GITHUB_EVENT_NAME": "push"}),
            ("email_probe", {"GITHUB_RUN_ATTEMPT": "2"}),
        )
        for operation, changes in cases:
            arguments = self.controller_arguments()
            arguments.operation = operation
            with (
                self.subTest(operation=operation, changes=changes),
                patch.dict(MODULE.os.environ, environment | changes, clear=True),
                patch.object(MODULE, "parse_args", return_value=arguments),
                patch.object(MODULE, "load_migrations", return_value=self.reviewed_upgrade_sql()),
                patch.object(MODULE, "release_context", return_value=("a" * 40, "synthetic-token")),
                patch.object(MODULE, "require_checkout"),
                patch.object(MODULE, "TimewebClient") as provider,
                patch.object(MODULE, "reconcile") as reconcile,
                patch("sys.stderr"),
            ):
                self.assertEqual(MODULE.main(), 1)
            provider.assert_not_called()
            reconcile.assert_not_called()
        with patch.dict(MODULE.os.environ, environment | {"GITHUB_RUN_ATTEMPT": "2"}, clear=True):
            # Reconciliation after a lost apply response remains explicitly retryable.
            MODULE.validate_operation("apply", release_sha="a" * 40)

    def test_default_reconcile_inspects_existing_cluster_without_bootstrap_or_copy(self) -> None:
        values = {
            "find_managed_server": {"id": 1}, "find_vpc": {"id": "private"},
            "find_vpc_service": {}, "private_server_cidr": "10.0.0.4/24",
            "select_postgres_type": "postgres18", "select_database_preset": {"id": 1},
            "find_database_cluster": {"id": 4215095}, "public_ipv4": "192.0.2.1",
            "inspect_provider_recovery": {},
            "wait_for_database_endpoint": (
                {"id": 4215095}, MODULE.DatabaseEndpoint("10.0.0.5", 5432),
            ),
            "validate_existing_cluster": None, "service_matches": True,
            "validate_budget": None, "get_schedule": {"is_enabled": False},
        }
        mutation_names = (
            "ensure_recovery_point", "inspect_restore_capacity", "ensure_server_private_network",
            "load_or_create_server_secrets", "write_runtime_env", "run_schema_migration",
            "apply_database_release",
        )
        for ready in (True, False):
            report = self.inspection_report(ready=ready)
            with self.subTest(ready=ready), ExitStack() as stack:
                for name, value in values.items():
                    stack.enter_context(patch.object(MODULE, name, return_value=value))
                mutations = {name: stack.enter_context(patch.object(MODULE, name))
                             for name in mutation_names}
                stack.enter_context(patch.dict(MODULE.os.environ, {}, clear=True))
                ssh = stack.enter_context(patch.object(MODULE, "EphemeralSsh"))
                remote = stack.enter_context(patch.object(MODULE, "run_inplace_upgrade",
                                                         return_value=report))
                output = stack.enter_context(patch.object(MODULE, "set_output"))
                summary = stack.enter_context(patch.object(MODULE, "add_summary"))
                stack.enter_context(patch("sys.stderr"))
                client = Mock()
                client.get_vpc_services.return_value = [{}]
                result = MODULE.reconcile(
                    client, desired=self.desired, server_name="server", server_comment="managed",
                    vpc_name="private", migration_sqls=self.reviewed_upgrade_sql(),
                    release_sha="a" * 40,
                )
            self.assertEqual(result, 0 if ready else 1)
            self.assertEqual(remote.call_args.kwargs["operation"], "preflight")
            self.assertEqual(remote.call_count, 1)
            output.assert_any_call("status", report["status"])
            self.assertNotIn("database_ready", [call.args[1] for call in output.call_args_list])
            self.assertEqual(json.loads(summary.call_args.args[0]), report)
            ssh.return_value.__exit__.assert_called_once()
            for name, mutation in mutations.items():
                self.assertEqual(mutation.call_count, 0, name)
            self.assertTrue(all(call[0].startswith("get_") for call in client.mock_calls))

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
        environment = {"GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/main",
                       "GITHUB_SHA": "a" * 40}
        with ExitStack() as stack:
            stack.enter_context(patch.dict(MODULE.os.environ, environment, clear=True))
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
                    operation="apply", release_sha="a" * 40,
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
