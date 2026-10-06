#!/usr/bin/env python3
"""Regression tests for the auth application deployer."""

from __future__ import annotations

import ast
import base64
import importlib.util
import io
import json
import os
import pathlib
import re
import shlex
import subprocess
import sys
import tarfile
import tempfile
import unittest
from email.message import Message
from unittest.mock import patch

SCRIPT_DIR = pathlib.Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

MODULE_PATH = SCRIPT_DIR / "timeweb_auth_app.py"
SPEC = importlib.util.spec_from_file_location("timeweb_auth_app", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load timeweb_auth_app.py")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def declared_http_routes(source: str) -> set[tuple[str, str]]:
    """Check route declarations independently of whitespace or response metadata."""
    routes = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and isinstance(decorator.func.value, ast.Name)
                and decorator.func.value.id == "app"
                and decorator.func.attr in {
                    "get", "post", "put", "delete", "patch", "head", "options",
                }
                and decorator.args
                and isinstance(decorator.args[0], ast.Constant)
            ):
                routes.add((decorator.func.attr, str(decorator.args[0].value)))
    return routes


class FakeSsh:
    def __init__(self, succeeds: bool) -> None:
        self.succeeds = succeeds
        self.commands: list[str] = []

    def run(self, command: str, *, input_text: str | None = None) -> str:
        self.commands.append(command)
        if not self.succeeds:
            raise MODULE.InfraError("not ready")
        if "count(*) FILTER" in command:
            return "1|1\n"
        return ""


class MissingLegacyMarkerSsh:
    def __init__(self) -> None:
        self.commands: list[str] = []
        self.inputs: list[str | None] = []

    def run(self, command: str, *, input_text: str | None = None) -> str:
        self.commands.append(command)
        self.inputs.append(input_text)
        if command.startswith("test -f "):
            raise MODULE.InfraError("marker missing")
        return ""


class AuthAppDeployTests(unittest.TestCase):
    def test_release_sha_requires_full_lowercase_commit(self) -> None:
        self.assertIsNotNone(MODULE.RELEASE_RE.fullmatch("a" * 40))
        self.assertIsNone(MODULE.RELEASE_RE.fullmatch("A" * 40))
        self.assertIsNone(MODULE.RELEASE_RE.fullmatch("a" * 39))

    def test_runtime_gate_requires_remote_environment(self) -> None:
        ready = FakeSsh(True)
        missing = FakeSsh(False)

        self.assertTrue(MODULE.runtime_is_ready(ready))
        self.assertFalse(MODULE.runtime_is_ready(missing))
        self.assertIn("BROKER_TOKEN_CRYPTO_KEY", ready.commands[0])
        self.assertIn("VKID_FLOW_CRYPTO_KEY", ready.commands[0])
        self.assertIn("command -v psql", ready.commands[0])
        self.assertIn("vkid_identities", ready.commands[0])
        self.assertIn("column_name = 'role'", ready.commands[0])

    def test_runtime_gate_matches_application_database_readiness(self) -> None:
        database_path = SCRIPT_DIR.parent.parent / "src" / "omnicio" / "db.py"
        tree = ast.parse(database_path.read_text(encoding="utf-8"))
        healthcheck = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "healthcheck"
        )
        queries = [
            node.value for node in ast.walk(healthcheck)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
            and node.value.lstrip().startswith("SELECT")
        ]
        self.assertEqual(len(queries), 1)
        predicate = queries[0].strip().removeprefix("SELECT").removesuffix("AS ready")
        expected = f"SELECT CASE WHEN {predicate} THEN 'ready' ELSE 'missing' END"
        ssh = FakeSsh(True)
        self.assertTrue(MODULE.runtime_is_ready(ssh))
        match = re.search(r'-Atqc "(.*?)" 2>/dev/null', ssh.commands[0], flags=re.S)
        self.assertIsNotNone(match)
        actual = match.group(1) if match else ""
        self.assertEqual(" ".join(actual.split()), " ".join(expected.split()))
        self.assertIn("column_name = 'next_assessment_at'", actual)
        self.assertIn("c.relforcerowsecurity", actual)

    def test_missing_runtime_schema_does_not_activate_or_rollback_release(self) -> None:
        from contextlib import ExitStack
        from unittest.mock import MagicMock

        client = MagicMock()
        client.get_vpc_services.return_value = [{"name": "database"}]
        monitored = (
            "validate_product_environment", "validate_legal_documents",
            "find_managed_server", "find_vpc", "public_ipv4", "build_release_archive",
            "EphemeralSsh", "upload_release", "write_product_environment",
            "deploy_remote", "rollback_remote", "retire_legacy_profile",
            "commit_product_environment", "add_summary", "set_output",
        )
        with ExitStack() as stack:
            mocks = {
                name: stack.enter_context(patch.object(MODULE, name))
                for name in monitored
            }
            mocks["find_managed_server"].return_value = {"id": 1}
            mocks["find_vpc"].return_value = {"id": "test-vpc"}
            mocks["public_ipv4"].return_value = "192.0.2.1"
            mocks["build_release_archive"].return_value = "test-archive"
            mocks["EphemeralSsh"].return_value.__enter__.return_value = FakeSsh(False)
            result = MODULE.reconcile(
                client, server_name="test-server", server_comment="test-only",
                release_sha="a" * 40, repository_root=SCRIPT_DIR.parent.parent,
                cluster_name="database", vpc_name="test-vpc", location="test",
                availability_zone="test",
            )
            self.assertEqual(result, 0)
            mocks["set_output"].assert_called_once_with("status", "pending_database")
            for name in (
                "upload_release", "write_product_environment", "deploy_remote",
                "rollback_remote", "retire_legacy_profile", "commit_product_environment",
            ):
                mocks[name].assert_not_called()

    def test_registration_occupancy_parses_privacy_safe_counts(self) -> None:
        class OccupancySsh:
            def run(self, command: str, *, input_text: str | None = None) -> str:
                self.command = command
                return "1|1\n"

        ssh = OccupancySsh()
        self.assertEqual(MODULE.registration_occupancy(ssh), (1, 1))
        self.assertIn("count(*) FILTER", ssh.command)
        self.assertNotIn("public_id", ssh.command)
        self.assertNotIn("vk_user_id", ssh.command)

    def test_registration_occupancy_rejects_invalid_result(self) -> None:
        class OccupancySsh:
            def run(self, command: str, *, input_text: str | None = None) -> str:
                return "two|one\n"

        ssh = OccupancySsh()
        with self.assertRaises(MODULE.InfraError):
            MODULE.registration_occupancy(ssh)

    def test_release_archive_contains_only_runtime_project_files(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = pathlib.Path(tempdir)
            (root / "src" / "omnicio").mkdir(parents=True)
            (root / "web").mkdir()
            (root / "tests").mkdir()
            (root / "pyproject.toml").write_text("[project]\nname='x'\n")
            (root / "requirements-runtime.txt").write_text("# Locked deployment dependencies\n")
            (root / "src" / "omnicio" / "__init__.py").write_text("")
            (root / "web" / "index.html").write_text("<html></html>")
            (root / "tests" / "secret-test.txt").write_text("not shipped")
            for relative in MODULE.BRAND_RUNTIME_FILES:
                brand_file = root / relative
                brand_file.parent.mkdir(parents=True, exist_ok=True)
                brand_file.write_bytes(b"brand")

            encoded = MODULE.build_release_archive(root)
            raw = base64.b64decode(encoded)
            with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
                names = set(archive.getnames())

        self.assertIn("pyproject.toml", names)
        self.assertIn("requirements-runtime.txt", names)
        self.assertIn("src/omnicio/__init__.py", names)
        self.assertIn("web/index.html", names)
        for relative in MODULE.BRAND_RUNTIME_FILES:
            self.assertIn(relative, names)
        self.assertNotIn("tests/secret-test.txt", names)

    def _base_registration_environment(self) -> None:
        os.environ["VKID_APP_ID"] = "123456"
        os.environ["REGISTRATION_ENABLED"] = "true"
        os.environ["REGISTRATION_MAX_USERS"] = "2"
        os.environ["MULTIUSER_LEGAL_APPROVED"] = "true"
        os.environ["RKN_NOTIFICATION_CONFIRMED"] = "true"
        os.environ["CONTROLLED_LIVE_TEST_MODE"] = "false"
        os.environ["LEGAL_OPERATOR_NAME"] = "Test Operator"
        os.environ["LEGAL_OPERATOR_EMAIL"] = "operator@example.com"
        os.environ["LEGAL_PRIVACY_VERSION"] = "2026-10-02-v6"
        os.environ["LEGAL_CONSENT_VERSION"] = "2026-10-02-v6"
        os.environ["LEGAL_TERMS_VERSION"] = "2026-10-02-v6"

    def test_product_environment_requires_legal_versions(self) -> None:
        old = dict(os.environ)
        try:
            self._base_registration_environment()
            MODULE.validate_product_environment()
            os.environ.pop("LEGAL_TERMS_VERSION")
            with self.assertRaises(MODULE.InfraError):
                MODULE.validate_product_environment()
        finally:
            os.environ.clear()
            os.environ.update(old)

    def test_product_environment_requires_numeric_vkid_app_id(self) -> None:
        old = dict(os.environ)
        try:
            self._base_registration_environment()
            os.environ["VKID_APP_ID"] = "app"
            with self.assertRaises(MODULE.InfraError):
                MODULE.validate_product_environment()
        finally:
            os.environ.clear()
            os.environ.update(old)

    def test_limited_registration_requires_reviewed_legal_gate(self) -> None:
        old = dict(os.environ)
        try:
            self._base_registration_environment()
            os.environ["MULTIUSER_LEGAL_APPROVED"] = "false"
            with self.assertRaises(MODULE.InfraError):
                MODULE.validate_product_environment()
        finally:
            os.environ.clear()
            os.environ.update(old)

    def test_limited_registration_requires_regulatory_or_live_test_gate(self) -> None:
        old = dict(os.environ)
        try:
            self._base_registration_environment()
            os.environ["RKN_NOTIFICATION_CONFIRMED"] = "false"
            os.environ["CONTROLLED_LIVE_TEST_MODE"] = "false"
            with self.assertRaises(MODULE.InfraError):
                MODULE.validate_product_environment()
        finally:
            os.environ.clear()
            os.environ.update(old)

    def test_controlled_live_test_allows_two_registration_slots(self) -> None:
        old = dict(os.environ)
        try:
            self._base_registration_environment()
            os.environ["RKN_NOTIFICATION_CONFIRMED"] = "false"
            os.environ["CONTROLLED_LIVE_TEST_MODE"] = "true"
            os.environ["REGISTRATION_MAX_USERS"] = "2"
            MODULE.validate_product_environment()
        finally:
            os.environ.clear()
            os.environ.update(old)

    def test_controlled_live_test_rejects_more_than_two_slots(self) -> None:
        old = dict(os.environ)
        try:
            self._base_registration_environment()
            os.environ["RKN_NOTIFICATION_CONFIRMED"] = "false"
            os.environ["CONTROLLED_LIVE_TEST_MODE"] = "true"
            os.environ["REGISTRATION_MAX_USERS"] = "3"
            with self.assertRaises(MODULE.InfraError):
                MODULE.validate_product_environment()
        finally:
            os.environ.clear()
            os.environ.update(old)

    def test_controlled_live_test_must_be_disabled_after_regulatory_confirmation(self) -> None:
        old = dict(os.environ)
        try:
            self._base_registration_environment()
            os.environ["RKN_NOTIFICATION_CONFIRMED"] = "true"
            os.environ["CONTROLLED_LIVE_TEST_MODE"] = "true"
            with self.assertRaises(MODULE.InfraError):
                MODULE.validate_product_environment()
        finally:
            os.environ.clear()
            os.environ.update(old)

    def test_limited_registration_requires_operator_identity(self) -> None:
        old = dict(os.environ)
        try:
            self._base_registration_environment()
            os.environ["LEGAL_OPERATOR_EMAIL"] = "not-an-email"
            with self.assertRaises(MODULE.InfraError):
                MODULE.validate_product_environment()
        finally:
            os.environ.clear()
            os.environ.update(old)

    def test_product_environment_builds_two_slot_registration(self) -> None:
        old = dict(os.environ)
        try:
            self._base_registration_environment()
            MODULE.validate_product_environment()
            product_env = MODULE.build_product_environment()
        finally:
            os.environ.clear()
            os.environ.update(old)

        self.assertIn('VKID_APP_ID="123456"', product_env)
        self.assertIn('VKID_LOGIN_ENABLED="true"', product_env)
        self.assertIn('REGISTRATION_ENABLED="true"', product_env)
        self.assertIn('REGISTRATION_MAX_USERS="2"', product_env)
        self.assertIn('LEGAL_OPERATOR_EMAIL="operator@example.com"', product_env)
        self.assertIn(
            'OMNICIO_RECOVERY_STATUS_PATH="/var/lib/omnicio-recovery/status.json"', product_env,
        )
        self.assertNotIn("OWNER_VK_ID", product_env)

    def test_registration_environment_rejects_invalid_boolean(self) -> None:
        old = dict(os.environ)
        try:
            os.environ["REGISTRATION_ENABLED"] = "yes"
            with self.assertRaises(MODULE.InfraError):
                MODULE.registration_enabled()
        finally:
            os.environ.clear()
            os.environ.update(old)

    def test_registration_capacity_must_be_positive(self) -> None:
        old = dict(os.environ)
        try:
            os.environ["REGISTRATION_MAX_USERS"] = "0"
            with self.assertRaises(MODULE.InfraError):
                MODULE.registration_max_users()
        finally:
            os.environ.clear()
            os.environ.update(old)

    def test_legal_templates_require_operator_placeholders(self) -> None:
        MODULE.validate_legal_documents(SCRIPT_DIR.parent.parent)

    def test_legacy_reset_is_disabled_without_regulatory_or_live_test_gate(self) -> None:
        old = dict(os.environ)
        try:
            os.environ["LEGACY_PROFILE_RESET_ENABLED"] = "true"
            os.environ["REGISTRATION_ENABLED"] = "false"
            os.environ["RKN_NOTIFICATION_CONFIRMED"] = "false"
            os.environ["CONTROLLED_LIVE_TEST_MODE"] = "false"
            ssh = FakeSsh(True)
            MODULE.retire_legacy_profile(ssh)
            self.assertEqual(ssh.commands, [])

            os.environ["REGISTRATION_ENABLED"] = "true"
            MODULE.retire_legacy_profile(ssh)
            self.assertEqual(ssh.commands, [])
        finally:
            os.environ.clear()
            os.environ.update(old)

    def test_legacy_reset_is_allowed_for_explicit_controlled_live_test(self) -> None:
        old = dict(os.environ)
        try:
            os.environ["LEGACY_PROFILE_RESET_ENABLED"] = "true"
            os.environ["REGISTRATION_ENABLED"] = "true"
            os.environ["RKN_NOTIFICATION_CONFIRMED"] = "false"
            os.environ["CONTROLLED_LIVE_TEST_MODE"] = "true"
            ssh = FakeSsh(True)
            MODULE.retire_legacy_profile(ssh)
        finally:
            os.environ.clear()
            os.environ.update(old)

        self.assertGreaterEqual(len(ssh.commands), 1)

    def test_legacy_reset_only_targets_public_id_one(self) -> None:
        old = dict(os.environ)
        try:
            os.environ["REGISTRATION_ENABLED"] = "true"
            os.environ["RKN_NOTIFICATION_CONFIRMED"] = "true"
            os.environ["LEGACY_PROFILE_RESET_ENABLED"] = "true"
            ssh = MissingLegacyMarkerSsh()
            MODULE.retire_legacy_profile(ssh)
        finally:
            os.environ.clear()
            os.environ.update(old)

        migration = next(value for value in ssh.inputs if value and "BEGIN;" in value)
        self.assertIn("WHERE public_id = 1", migration)
        self.assertIn("refuses to delete a non-legacy user", migration)
        self.assertIn("DO $", migration)
        self.assertNotIn("\nDELETE FROM users;\n", migration)
        self.assertTrue(any(MODULE.LEGACY_RESET_MARKER in command for command in ssh.commands))

    def test_legacy_reset_marker_makes_cleanup_idempotent(self) -> None:
        old = dict(os.environ)
        try:
            os.environ["REGISTRATION_ENABLED"] = "true"
            os.environ["RKN_NOTIFICATION_CONFIRMED"] = "true"
            os.environ["LEGACY_PROFILE_RESET_ENABLED"] = "true"
            ssh = FakeSsh(True)
            MODULE.retire_legacy_profile(ssh)
        finally:
            os.environ.clear()
            os.environ.update(old)

        self.assertEqual(ssh.commands, [f"test -f {MODULE.LEGACY_RESET_MARKER}"])


    def test_auth_deploy_workflow_separates_pr_and_production_concurrency(self) -> None:
        workflow = (
            SCRIPT_DIR.parent / "workflows" / "auth-app-deploy.yml"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "github.event.pull_request.number || 'production'",
            workflow,
        )
        self.assertIn(
            "cancel-in-progress: ${{ github.event_name == 'pull_request' }}",
            workflow,
        )

    def test_product_environment_is_backed_up_for_rollback(self) -> None:
        old = dict(os.environ)
        try:
            os.environ["VKID_APP_ID"] = "123456"
            os.environ["REGISTRATION_ENABLED"] = "false"
            ssh = FakeSsh(True)
            sha = "a" * 40
            MODULE.write_product_environment(ssh, release_sha=sha)
        finally:
            os.environ.clear()
            os.environ.update(old)

        backup, state = MODULE.product_environment_backup_paths(sha)
        self.assertIn(backup, ssh.commands[0])
        self.assertIn(state, ssh.commands[0])
        self.assertIn(f"{MODULE.PRODUCT_ENV}.tmp-{sha}", ssh.commands[0])
        self.assertIn('PRODUCT_ENV_BACKUP="$PRODUCT_ENV.pre-$SHA"', MODULE.REMOTE_ROLLBACK_SCRIPT)
        self.assertIn(
            'PRODUCT_ENV_STATE="$PRODUCT_ENV.pre-$SHA.state"', MODULE.REMOTE_ROLLBACK_SCRIPT,
        )

    def test_product_environment_backup_rejects_invalid_release_sha(self) -> None:
        with self.assertRaises(MODULE.InfraError):
            MODULE.product_environment_backup_paths("short")

    def test_optional_integration_configuration_survives_unrelated_deployment(self) -> None:
        with patch.dict(os.environ, {"VKID_APP_ID": "123456"}, clear=True):
            ssh = FakeSsh(True)
            MODULE.write_product_environment(ssh, release_sha="b" * 40)
        tokens = shlex.split(ssh.commands[0])
        program = tokens[tokens.index("-c") + 1]
        with tempfile.TemporaryDirectory() as directory:
            old = pathlib.Path(directory) / "previous.env"
            new = pathlib.Path(directory) / "candidate.env"
            old.write_text(
                'TID_CLIENT_ID="existing-app"\n'
                'TID_CLIENT_SECRET="test-only-value"\n'
                'TID_LOGIN_ENABLED="true"\n'
                'ASSISTANT_ENABLED="true"\n'
                'REGISTRATION_ENABLED="true"\n'
                'UNRELATED_KEY="must-not-migrate"\n',
                encoding="utf-8",
            )
            new.write_text(
                'TID_CLIENT_ID="replacement-app"\n'
                'ASSISTANT_ENABLED="false"\n'
                'REGISTRATION_ENABLED="false"\n',
                encoding="utf-8",
            )
            subprocess.run(
                [sys.executable, "-c", program, str(new), str(old)],
                check=True, timeout=5,
            )
            result = new.read_text(encoding="utf-8").splitlines()
        self.assertEqual(result, [
            'TID_CLIENT_ID="replacement-app"',
            'ASSISTANT_ENABLED="false"',
            'REGISTRATION_ENABLED="false"',
            'TID_CLIENT_SECRET="test-only-value"',
            'TID_LOGIN_ENABLED="true"',
        ])

    def test_runtime_values_escape_systemd_double_quote_metacharacters(self) -> None:
        # EnvironmentFile uses the POSIX double-quote escape set, including $/`.
        value = 'test-only-$VALUE-`literal`-"quoted"-\\path'
        self.assertEqual(
            MODULE._environment_value(value),
            '"test-only-\\$VALUE-\\`literal\\`-\\"quoted\\"-\\\\path"',
        )
        for value in ("line\nbreak", "line\rbreak"):
            with self.subTest(value=repr(value)), self.assertRaises(MODULE.InfraError):
                MODULE._environment_value(value)

    def test_public_http_surface_has_bounded_resource_consumption(self) -> None:
        script = MODULE.REMOTE_DEPLOY_SCRIPT
        self.assertIn("zone=omnicio_auth_start:10m rate=10r/m", script)
        self.assertIn("zone=omnicio_auth_callback:10m rate=30r/m", script)
        self.assertIn("zone=omnicio_api:10m rate=120r/m", script)
        self.assertIn("limit_conn_zone $binary_remote_addr zone=omnicio_conn:10m", script)
        self.assertIn("location = /api/auth/vkid/start", script)
        self.assertIn("location = /api/auth/vkid/callback", script)
        self.assertIn("limit_req zone=omnicio_api burst=60 nodelay", script)
        self.assertGreaterEqual(script.count("client_max_body_size 16k;"), 2)
        self.assertGreaterEqual(script.count("client_body_timeout 10s;"), 2)
        self.assertGreaterEqual(script.count("client_header_timeout 10s;"), 2)
        self.assertGreaterEqual(script.count("limit_conn omnicio_conn 32;"), 2)
        self.assertIn("limit_conn_status 429", script)
        self.assertIn("limit_req_status 429", script)

    def test_remote_service_is_loopback_only_bounded_and_registration_is_gated(self) -> None:
        script = MODULE.REMOTE_DEPLOY_SCRIPT
        self.assertIn("--host 127.0.0.1 --port 8001", script)
        self.assertIn("--limit-concurrency 64", script)
        self.assertIn("--backlog 128", script)
        self.assertIn("--timeout-keep-alive 5", script)
        self.assertIn("EnvironmentFile=/etc/omnicio/runtime.env", script)
        self.assertIn("NoNewPrivileges=true", script)
        self.assertIn("proxy_pass http://127.0.0.1:8001", script)

    def test_production_app_deploy_waits_for_postgres_reconcile(self) -> None:
        root = SCRIPT_DIR.parent.parent
        app_workflow = (
            root / ".github" / "workflows" / "auth-app-deploy.yml"
        ).read_text(encoding="utf-8")
        postgres_workflow = (
            root / ".github" / "workflows" / "auth-postgres.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("workflow_run", app_workflow)
        self.assertIn("Auth PostgreSQL", app_workflow)
        deploy_if = app_workflow.split("  deploy:", 1)[1].split(
            "    needs: tests",
            1,
        )[0]
        self.assertNotIn("github.event_name == 'push'", deploy_if)
        self.assertIn(
            "github.event.workflow_run.conclusion == 'success'",
            deploy_if,
        )
        self.assertIn(
            "github.event.workflow_run.head_sha == github.sha",
            deploy_if,
        )
        self.assertNotIn("Detect schema-first release", app_workflow)

        for release_path in (
            '"uv.lock"',
            '"requirements-runtime.txt"',
            '".github/workflows/auth-app-deploy.yml"',
            '".github/scripts/timeweb_auth_app.py"',
            '".github/scripts/test_timeweb_auth_app.py"',
            '"src/omnicio/**"',
            '"web/**"',
            '"assets/brand/**"',
            '"pyproject.toml"',
        ):
            self.assertGreaterEqual(
                postgres_workflow.count(release_path),
                2,
                release_path,
            )

    def test_remote_daily_observer_is_read_only_bounded_and_rollback_safe(self) -> None:
        script = MODULE.REMOTE_DEPLOY_SCRIPT
        rollback = MODULE.REMOTE_ROLLBACK_SCRIPT

        self.assertIn("omnicio-observer.service", script)
        self.assertIn("omnicio-observer.timer", script)
        self.assertIn("ExecStart=/opt/omnicio/current/.venv/bin/python -m omnicio.observer", script)
        self.assertIn("OnCalendar=*-*-* 06:15:00 Europe/Moscow", script)
        self.assertIn("Persistent=true", script)
        self.assertIn("Restart=on-failure", script)
        self.assertIn("StartLimitBurst=3", script)
        self.assertIn("RuntimeMaxSec=1500", script)
        self.assertIn("NoNewPrivileges=true", script)
        self.assertIn("OBSERVER_TIMER_WAS_ENABLED", script)
        self.assertIn("OBSERVER_TIMER_WAS_ACTIVE", script)
        self.assertIn("OBSERVER_TIMER_WAS_ENABLED", rollback)
        self.assertIn("OBSERVER_TIMER_WAS_ACTIVE", rollback)
        self.assertNotIn("omnicio.observer --execute", script)

    def test_remote_service_installs_tbank_russian_trusted_ca_safely(self) -> None:
        script = MODULE.REMOTE_DEPLOY_SCRIPT
        self.assertIn("russian_trusted_root_ca.cer", script)
        self.assertIn("russian_trusted_sub_ca.cer", script)
        self.assertIn("openssl verify -CAfile", script)
        self.assertIn("update-ca-certificates", script)
        self.assertIn(
            "Environment=SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt",
            script,
        )
        self.assertNotIn("curl -k", script)
        self.assertNotIn("--insecure", script)

    def test_legal_pages_describe_limited_user_registration(self) -> None:
        root = SCRIPT_DIR.parent.parent
        privacy = (root / "web" / "legal" / "privacy.html").read_text(encoding="utf-8")
        consent = (root / "web" / "legal" / "consent.html").read_text(encoding="utf-8")
        terms = (root / "web" / "legal" / "terms.html").read_text(encoding="utf-8")

        for document, version in (
            (privacy, "2026-10-06-v1.0.0"),
            (consent, "2026-10-06-v1.0.0"),
            (terms, "2026-10-06-v1.0.0"),
        ):
            self.assertIn('content="noindex,nofollow"', document)
            self.assertIn(version, document)
            self.assertIn("__OMNICIO_OPERATOR_", document)

        self.assertIn("OMNICIO", privacy)
        self.assertIn("T-Invest API", privacy)
        self.assertIn("Текущий временный live-test лимит — два пользовательских аккаунта", terms)
        self.assertIn("ролью <code>user</code>", terms)
        self.assertIn("Самостоятельное удаление аккаунта", terms)
        self.assertIn("восстановление удалённого аккаунта невозможно", privacy)

    def test_reference_workspace_keeps_required_runtime_contracts(self) -> None:
        root = SCRIPT_DIR.parent.parent
        page = (root / "web" / "index.html").read_text(encoding="utf-8")
        source = (root / "src" / "omnicio" / "main.py").read_text(encoding="utf-8")
        routes = declared_http_routes(source)
        required = {
            ("post", "/api/auth/tid/start"), ("get", "/api/auth/tid/callback"),
            ("post", "/api/auth/vkid/start"), ("get", "/api/auth/vkid/callback"),
            ("get", "/api/workspace"), ("get", "/api/preferences"),
            ("put", "/api/preferences"), ("get", "/api/goals"),
            ("post", "/api/goals"), ("put", "/api/goals/{goal_id}"),
            ("delete", "/api/goals/{goal_id}"), ("get", "/api/events"),
            ("post", "/api/events/read"), ("post", "/api/profile/strategy/research"),
            ("get", "/api/assistant/status"), ("post", "/api/assistant/messages"),
            ("get", "/api/public/news"),
        }
        self.assertLessEqual(required, routes, required - routes)
        self.assertNotIn(("post", "/api/profile/strategy/feasibility"), routes)
        self.assertIn(MODULE.SITE_MARKER, page)
        self.assertIn('id="app-sidebar"', page)
        self.assertIn('id="auth-dialog"', page)
        self.assertIn('id="global-search-form"', page)
        self.assertNotIn('type="password"', page)
        for path in MODULE.LEGAL_PAGES:
            self.assertIn(path, page)

    def test_reference_assets_are_shipped_without_legacy_brand(self) -> None:
        root = SCRIPT_DIR.parent.parent
        shipped = {str(path.relative_to(root)).replace("\\", "/")
                   for path in MODULE.iter_release_files(root)}
        for asset in MODULE.BRAND_RUNTIME_FILES:
            self.assertIn(asset, shipped)
        self.assertIn("assets/brand/web/earth-hero.png", shipped)
        self.assertFalse(any("omni-sentinel" in name for name in shipped))
        manifest = json.loads((root / "web" / "manifest.webmanifest").read_text())
        self.assertEqual(manifest["name"], "OMNICIO")
        for icon in manifest["icons"]:
            name = icon["src"].rsplit("/", 1)[-1]
            self.assertTrue((root / "assets" / "brand" / "web" / name).is_file())

    def test_personal_dashboard_exposes_release_version(self) -> None:
        root = SCRIPT_DIR.parent.parent
        page = (root / "web" / "index.html").read_text(encoding="utf-8")
        project = (root / "pyproject.toml").read_text(encoding="utf-8")
        deploy_script = MODULE.REMOTE_DEPLOY_SCRIPT

        self.assertGreaterEqual(page.count("data-app-version"), 3)
        self.assertIn("data-app-build", page)
        self.assertIn("__OMNICIO_VERSION__", page)
        self.assertIn("__OMNICIO_BUILD__", page)
        self.assertIn("/version.js?build=__OMNICIO_BUILD__", page)
        self.assertIn("/assets/app.css?build=__OMNICIO_BUILD__", page)
        self.assertIn("/assets/app.js?build=__OMNICIO_BUILD__", page)
        self.assertIn('version = "1.0.0"', project)
        self.assertIn("window.OMNICIO_RELEASE", deploy_script)
        self.assertIn('replace("__OMNICIO_VERSION__", version)', deploy_script)
        self.assertIn('replace("__OMNICIO_BUILD__", build)', deploy_script)
        self.assertIn("tomllib", deploy_script)
        self.assertEqual(MODULE.VERSION_PUBLIC_PATH, "/version.js")

    def test_runtime_assets_cannot_mix_across_frontend_releases(self) -> None:
        script = MODULE.REMOTE_DEPLOY_SCRIPT

        self.assertIn("location = /assets/app.css", script)
        self.assertIn("location = /assets/app.js", script)
        self.assertIn("location = /assets/workspace.js", script)
        self.assertIn("location = /sw.js", script)
        self.assertIn("location = /offline.html", script)
        self.assertIn("location = /version.js", script)
        self.assertIn("location = /manifest.webmanifest", script)
        self.assertGreaterEqual(script.count('add_header Cache-Control "no-cache";'), 5)
        self.assertNotIn('add_header Cache-Control "public, max-age=300";', script)

    def test_rendered_offline_styles_match_the_service_worker_build(self) -> None:
        root = SCRIPT_DIR.parent.parent
        program = MODULE.REMOTE_DEPLOY_SCRIPT.split(
            'python3 - "$RELEASE/pyproject.toml"', 1,
        )[1].split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
        build = "b" * 40
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory)
            subprocess.run([
                sys.executable, "-c", program, str(root / "pyproject.toml"), build,
                str(root / "web" / "index.html"), str(output / "index.html"),
                str(output / "version.js"),
                str(root / "web" / "sw.js"), str(output / "sw.js"),
                str(root / "web" / "offline.html"), str(output / "offline.html"),
            ], check=True, capture_output=True, timeout=10)
            offline = (output / "offline.html").read_text(encoding="utf-8")
            worker = (output / "sw.js").read_text(encoding="utf-8")
            self.assertIn(f"/assets/app.css?build={build[:12]}", offline)
            self.assertIn(f'const build = "{build[:12]}"', worker)
            self.assertNotIn("__OMNICIO_BUILD__", offline)
            self.assertNotIn("__OMNICIO_BUILD__", worker)

    def test_remote_release_publishes_all_legal_pages(self) -> None:
        script = MODULE.REMOTE_DEPLOY_SCRIPT
        self.assertIn('"$RELEASE/web/legal"', script)
        self.assertIn('"$WEB_RELEASE/legal"', script)
        for filename in ("privacy.html", "consent.html", "terms.html"):
            self.assertIn(filename, script)
        for marker in MODULE.LEGAL_OPERATOR_MARKERS:
            self.assertIn(marker, script)

        self.assertEqual(
            set(MODULE.LEGAL_PAGES),
            {
                "/legal/privacy.html",
                "/legal/consent.html",
                "/legal/terms.html",
            },
        )


class PublicResponse(io.BytesIO):
    def __init__(self, body: bytes, content_type: str, status: int = 200) -> None:
        super().__init__(body)
        self.status = status
        self.headers = Message()
        self.headers["Content-Type"] = content_type


class PublicReleaseVerificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sha = "a" * 40
        root = " ".join((
            MODULE.SITE_MARKER, MODULE.BRAND_PUBLIC_MARK, MODULE.WEB_MANIFEST_PATH,
            self.sha[:12],
        )).encode()
        config = json.dumps({
            "mode": "closed",
            "registration_enabled": False,
            "registration_max_users": 1,
            "auth_provider": "vkid",
            "login_enabled": False,
        }).encode()
        self.responses = {
            "/": (root, "text/html", 200),
            MODULE.BRAND_PUBLIC_MARK: (b"png", "image/png", 200),
            MODULE.WEB_MANIFEST_PATH: (b'{"icons": []}', "application/json", 200),
            MODULE.VERSION_PUBLIC_PATH: (
                f'window.OMNICIO_RELEASE = {{"build": "{self.sha[:12]}"}}'.encode(),
                "text/javascript", 200,
            ),
            "/api/auth/config": (config, "application/json", 200),
        }
        for path, body, content_type in (
            ("/assets/app.js", b"window.OmniUI", "text/javascript"),
            ("/assets/workspace.js", b"window.OmniUI", "application/javascript"),
            ("/assets/app.css", b"--sidebar:240px", "text/css"),
            ("/sw.js", b"omnicio-public-test " + self.sha[:12].encode(), "text/javascript"),
            (
                "/offline.html",
                b'<html lang="ru">' + self.sha[:12].encode() + b'</html>', "text/html",
            ),
        ):
            self.responses[f"{path}?build={self.sha[:12]}"] = (body, content_type, 200)
        for path, marker in MODULE.LEGAL_PAGES.items():
            self.responses[path] = (
                f"{marker} Test Operator operator@example.com".encode(),
                "text/html",
                200,
            )

    def verify(self) -> set[str]:
        requested: set[str] = set()

        def open_response(request, *, timeout, context):
            prefix = f"https://{MODULE.DOMAIN}"
            self.assertTrue(request.full_url.startswith(prefix + "/"))
            self.assertEqual(timeout, 15)
            self.assertTrue(context.check_hostname)
            self.assertEqual(context.verify_mode, MODULE.ssl.CERT_REQUIRED)
            path = request.full_url.removeprefix(prefix)
            requested.add(path)
            return PublicResponse(*self.responses[path])

        with (
            patch.object(MODULE.urllib.request, "urlopen", side_effect=open_response),
            patch.object(MODULE, "vkid_configuration_ready", return_value=False),
        ):
            MODULE.verify_public(self.sha)
        return requested

    def test_matching_release_checks_every_public_surface(self) -> None:
        self.assertEqual(self.verify(), set(self.responses))

    def test_invalid_public_release_is_rejected(self) -> None:
        cases = [
            ("/", b"wrong site", "text/html", 200),
            ("/", self.responses["/"][0] + b"__OMNICIO_BUILD__", "text/html", 200),
            ("/", self.responses["/"][0], "text/html", 503),
            (MODULE.BRAND_PUBLIC_MARK, b"", "image/png", 200),
            (MODULE.BRAND_PUBLIC_MARK, b"png", "text/html", 200),
            (MODULE.WEB_MANIFEST_PATH, b"[]", "application/json", 200),
            (MODULE.WEB_MANIFEST_PATH, b"invalid", "application/json", 200),
            (MODULE.VERSION_PUBLIC_PATH, b"window.OMNICIO_RELEASE = {}", "text/javascript", 200),
            (f"/assets/workspace.js?build={self.sha[:12]}", b"wrong asset", "text/javascript", 200),
            (f"/sw.js?build={self.sha[:12]}", b"<html>fallback</html>", "text/html", 200),
            (
                f"/sw.js?build={self.sha[:12]}",
                b"omnicio-public-__OMNICIO_BUILD__", "text/javascript", 200,
            ),
            (
                f"/offline.html?build={self.sha[:12]}",
                b"<html>__OMNICIO_BUILD__</html>", "text/html", 200,
            ),
            (f"/offline.html?build={self.sha[:12]}", b"<html>old release</html>", "text/html", 200),
            ("/api/auth/config", b"[]", "application/json", 200),
            ("/api/auth/config", b'{"registration_enabled": true}', "application/json", 200),
            ("/api/auth/config", b'{"registration_enabled": false}', "application/json", 200),
            (
                "/api/auth/config",
                b'{"mode":"limited_registration","registration_enabled":false,"registration_max_users":1,"auth_provider":"vkid","login_enabled":false}',
                "application/json",
                200,
            ),
        ]
        cases.extend((path, b"missing legal text", "text/html", 200) for path in MODULE.LEGAL_PAGES)
        for path, body, content_type, status in cases:
            previous = self.responses[path]
            with self.subTest(path=path, body=body[:80]):
                self.responses[path] = (body, content_type, status)
                try:
                    with self.assertRaises(MODULE.InfraError):
                        self.verify()
                finally:
                    self.responses[path] = previous

    def test_excessive_public_response_is_rejected(self) -> None:
        self.responses["/"] = (b"x" * (4 * 1024 * 1024 + 1), "text/html", 200)
        with self.assertRaises(MODULE.InfraError):
            self.verify()


if __name__ == "__main__":
    unittest.main()
