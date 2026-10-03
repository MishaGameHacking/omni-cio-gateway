#!/usr/bin/env python3
"""Regression tests for the auth application deployer."""

from __future__ import annotations

import base64
import importlib.util
import io
import json
import os
import pathlib
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

        with self.assertRaises(MODULE.InfraError):
            MODULE.registration_occupancy(OccupancySsh())

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
        ).read_text()

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
        self.assertIn('PRODUCT_ENV_STATE="$PRODUCT_ENV.pre-$SHA.state"', MODULE.REMOTE_ROLLBACK_SCRIPT)

    def test_product_environment_backup_rejects_invalid_release_sha(self) -> None:
        with self.assertRaises(MODULE.InfraError):
            MODULE.product_environment_backup_paths("short")

    def test_public_vk_id_endpoints_are_rate_limited(self) -> None:
        script = MODULE.REMOTE_DEPLOY_SCRIPT
        self.assertIn("zone=omnicio_auth_start:10m rate=10r/m", script)
        self.assertIn("zone=omnicio_auth_callback:10m rate=30r/m", script)
        self.assertIn("location = /api/auth/vkid/start", script)
        self.assertIn("location = /api/auth/vkid/callback", script)
        self.assertIn("limit_req_status 429", script)

    def test_remote_service_is_loopback_only_and_registration_is_gated(self) -> None:
        script = MODULE.REMOTE_DEPLOY_SCRIPT
        self.assertIn("--host 127.0.0.1 --port 8001", script)
        self.assertIn("EnvironmentFile=/etc/omnicio/runtime.env", script)
        self.assertIn("NoNewPrivileges=true", script)
        self.assertIn("proxy_pass http://127.0.0.1:8001", script)

    def test_production_app_deploy_waits_for_postgres_reconcile(self) -> None:
        root = SCRIPT_DIR.parent.parent
        app_workflow = (
            root / ".github" / "workflows" / "auth-app-deploy.yml"
        ).read_text()
        postgres_workflow = (
            root / ".github" / "workflows" / "auth-postgres.yml"
        ).read_text()

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
        privacy = (root / "web" / "legal" / "privacy.html").read_text()
        consent = (root / "web" / "legal" / "consent.html").read_text()
        terms = (root / "web" / "legal" / "terms.html").read_text()

        for document in (privacy, consent, terms):
            self.assertIn('content="noindex,nofollow"', document)
            self.assertIn("2026-10-02-v6", document)
            self.assertIn("__OMNICIO_OPERATOR_", document)

        self.assertIn("OmniCIO Personal", privacy)
        self.assertIn("T-Invest API", privacy)
        self.assertIn("Текущий временный live-test лимит — два пользовательских аккаунта", terms)
        self.assertIn("ролью <code>user</code>", terms)
        self.assertIn("Самостоятельное удаление аккаунта", terms)
        self.assertIn("восстановление удалённого аккаунта невозможно", privacy)

    def test_personal_dashboard_keeps_auth_and_broker_contracts(self) -> None:
        root = SCRIPT_DIR.parent.parent
        page = (root / "web" / "index.html").read_text()
        script = (root / "web" / "app.js").read_text()

        for element_id in (
            "auth-card",
            "profile-panel",
            "vkid-form",
            "tbank-form",
            "tbank-account-form",
            "tbank-connected",
            "profile-id",
            "app-menu-toggle",
            "app-back",
            "app-drawer",
            "drawer-backdrop",
            "drawer-profile-id",
            "profile-page-id",
            "support-profile-id",
            "fullscreen-toggle",
            "copy-support-diagnostics",
            "logout",
            "delete-account-start",
            "delete-account-form",
            "delete-account-confirmation",
            "delete-account-submit",
        ):
            self.assertIn(f'id="{element_id}"', page)

        for endpoint in (
            "/api/me",
            "/api/auth/config",
            "/api/auth/vkid/start",
            "/api/auth/logout",
            "/api/account/delete",
            "/api/broker/tbank",
            "/api/broker/tbank/accounts",
            "/api/broker/tbank/portfolio",
            "/api/broker/tbank/analysis",
            "/api/portfolio/intelligence",
            "/api/portfolio/balancing",
            "/api/profile/balancing",
            "/api/broker/tbank/instruments/search",
            "/api/market/usd-rub",
            "/api/market/usd-rub/stream",
        ):
            self.assertIn(endpoint, script)

    def test_versioned_balancing_policy_has_explicit_limits_and_no_trade_authority(self) -> None:
        root = SCRIPT_DIR.parent.parent
        page = (root / "web" / "index.html").read_text()
        script = (root / "web" / "app.js").read_text()
        backend = (root / "src" / "omnicio" / "main.py").read_text()

        for element_id in (
            "balancing-policy-form",
            "balancing-policy-version",
            "balance-max-instrument",
            "balance-max-sector",
            "balance-max-issuer",
            "balance-max-group",
            "balance-max-share",
            "balance-max-bond",
            "balance-max-etf",
            "balance-max-below-grade",
            "balance-max-unknown",
            "balance-max-term",
            "balance-turnover-budget",
            "balance-daily-participation",
            "balance-tax-rate",
            "balance-uncertainty-haircut",
            "balance-credit-haircut",
            "balance-no-trade-band",
            "balance-min-replace-benefit",
            "balancing-policy-save",
        ):
            self.assertIn(f'id="{element_id}"', page)

        self.assertIn('"/api/profile/balancing"', script)
        self.assertIn('@app.get("/api/profile/balancing")', backend)
        self.assertIn('@app.put("/api/profile/balancing")', backend)
        self.assertIn("require_same_origin(request)", backend)
        self.assertNotIn("OrdersService", backend)
        self.assertIn("не подставляет скрытые проценты", page)
        self.assertIn("не получает", page)
        self.assertIn("торговых полномочий", page)
        self.assertIn("ytw_from_tinvest_fixed_cashflows", script)
        self.assertIn("liquidity_from_tinvest_exchange_candles", script)
        self.assertNotIn("moex_runtime_transport_security_gate", script)

    def test_personal_dashboard_uses_real_portfolio_data_without_fake_values(self) -> None:
        root = SCRIPT_DIR.parent.parent
        page = (root / "web" / "index.html").read_text()
        script = (root / "web" / "app.js").read_text()

        self.assertIn("Данные читаются напрямую из T-Invest", page)
        self.assertIn('id="portfolio-content"', page)
        self.assertIn('id="positions-list"', page)
        self.assertNotIn('id="operations-list"', page)
        self.assertNotIn("Последние исполненные операции", page)
        self.assertIn('data-view-panel="system"', page)
        self.assertIn("Системные модули", page)
        self.assertIn("/api/broker/tbank/portfolio", script)
        self.assertNotIn("/api/broker/tbank/operations", script)
        self.assertNotIn("innerHTML", script)
        self.assertNotIn("₽ 1 000 000", page)
        self.assertNotIn("+12.4%", page)

    def test_versioned_investment_profile_is_user_scoped_and_not_trade_authority(self) -> None:
        root = SCRIPT_DIR.parent.parent
        page = (root / "web" / "index.html").read_text()
        script = (root / "web" / "app.js").read_text()
        backend = (root / "src" / "omnicio" / "main.py").read_text()

        for element_id in (
            "investment-profile-form",
            "investment-profile-version",
            "balancing-status",
            "balancing-scenarios",
            "balancing-screening",
            "profile-reserve-rub",
            "profile-withdrawal-rub",
            "profile-horizon-months",
            "profile-max-drawdown",
            "profile-liquidity-days",
            "profile-allow-below-grade",
            "investment-profile-save",
        ):
            self.assertIn(f'id="{element_id}"', page)

        self.assertIn('"/api/profile/investment"', script)
        self.assertIn('@app.get("/api/profile/investment")', backend)
        self.assertIn('@app.put("/api/profile/investment")', backend)
        self.assertIn("require_same_origin(request)", backend)
        self.assertIn("authenticated_user(request, session_token)", backend)
        self.assertIn("не дают OmniCIO полномочий совершать сделки", page)
        self.assertNotIn("/api/broker/tbank/operations", script)

    def test_user_transaction_history_is_not_exposed(self) -> None:
        root = SCRIPT_DIR.parent.parent
        page = (root / "web" / "index.html").read_text()
        script = (root / "web" / "app.js").read_text()
        backend = (root / "src" / "omnicio" / "main.py").read_text()

        self.assertNotIn("Последние исполненные операции", page)
        self.assertNotIn("/api/broker/tbank/operations", script)
        self.assertNotIn('@app.get("/api/broker/tbank/operations")', backend)

    def test_personal_dashboard_system_modules_are_real_and_read_only(self) -> None:
        root = SCRIPT_DIR.parent.parent
        page = (root / "web" / "index.html").read_text()
        script = (root / "web" / "app.js").read_text()

        for element_id in (
            "owl-state",
            "owl-last-refresh",
            "hunter-form",
            "hunter-query",
            "hunter-results",
            "guard-state",
            "guard-blocked-positions",
            "guard-blocked-cash",
            "guard-largest-class",
        ):
            self.assertIn(f'id="{element_id}"', page)

        self.assertIn("Автоматически обновляет портфель раз в 5 минут", page)
        self.assertIn("не является рекомендацией", page)
        self.assertIn("без автоматических решений", page)
        self.assertIn("/api/broker/tbank/instruments/search", script)
        self.assertIn("5 * 60 * 1000", script)
        self.assertIn('document.visibilityState === "visible"', script)
        self.assertNotIn("innerHTML", script)

    def test_personal_dashboard_shows_live_usd_rub_without_fake_rate(self) -> None:
        root = SCRIPT_DIR.parent.parent
        page = (root / "web" / "index.html").read_text()
        script = (root / "web" / "app.js").read_text()

        for element_id in (
            "usd-rub-card",
            "usd-rub-state",
            "usd-rub-price",
            "usd-rub-change",
            "usd-rub-source",
            "usd-rub-time",
            "usd-rub-cbr",
            "usd-rub-cbr-date",
            "usd-rub-cbr-next-row",
            "usd-rub-cbr-next",
            "usd-rub-cbr-next-date",
            "home-fx-state",
            "owl-fx-status",
        ):
            self.assertIn(f'id="{element_id}"', page)

        self.assertIn("Оперативная котировка T-Invest", page)
        self.assertIn("ЦБ РФ — действует сегодня", page)
        self.assertIn("Следующий курс ЦБ РФ", page)
        self.assertIn('new EventSource("/api/market/usd-rub/stream")', script)
        self.assertIn('/api/market/usd-rub"', script)
        self.assertIn("5 * 1000", script)
        self.assertNotIn("92,47", page)
        self.assertNotIn("91,86", page)
        self.assertNotIn("innerHTML", script)

    def test_personal_dashboard_uses_grouped_drawer_navigation(self) -> None:
        root = SCRIPT_DIR.parent.parent
        page = (root / "web" / "index.html").read_text()
        script = (root / "web" / "app.js").read_text()
        stylesheet = (root / "web" / "app.css").read_text()

        for view in (
            "home",
            "portfolio",
            "decisions",
            "system",
            "connections",
            "profile",
            "settings",
            "support",
        ):
            self.assertIn(f'data-view="{view}"', page)
            self.assertIn(f'data-view-panel="{view}"', page)

        self.assertIn("Рабочее пространство", page)
        self.assertIn("Профиль", page)
        self.assertIn("Поддержка", page)
        self.assertIn("T-Invest и API-токен", page)
        self.assertIn("drawer-open", stylesheet)
        self.assertIn("navigateToView", script)
        self.assertIn("goBack", script)
        self.assertNotIn("data-mobile-view", page)

    def test_personal_dashboard_uses_approved_brand_assets(self) -> None:
        root = SCRIPT_DIR.parent.parent
        page = (root / "web" / "index.html").read_text()
        stylesheet = (root / "web" / "app.css").read_text()
        manifest = (root / "web" / "manifest.webmanifest").read_text()
        deploy_script = MODULE.REMOTE_DEPLOY_SCRIPT

        self.assertIn(
            "/assets/brand/omni-sentinel-core-color-1024.png",
            page,
        )
        self.assertIn("/assets/brand/favicon.ico", page)
        self.assertIn("/manifest.webmanifest", page)
        self.assertNotIn('class="brand-mark"', page)
        self.assertNotIn(".brand-mark {", stylesheet)

        for filename in (
            "omni-sentinel-core-color-1024.png",
            "apple-touch-icon-180.png",
            "favicon.ico",
            "pwa-icon-192.png",
            "pwa-icon-512.png",
            "pwa-maskable-512.png",
        ):
            self.assertIn(filename, deploy_script)

        self.assertIn('"purpose": "maskable"', manifest)

    def test_personal_dashboard_is_mobile_safe_and_respects_reduced_motion(self) -> None:
        root = SCRIPT_DIR.parent.parent
        page = (root / "web" / "index.html").read_text()
        stylesheet = (root / "web" / "app.css").read_text()
        script = (root / "web" / "app.js").read_text()

        self.assertIn("viewport-fit=cover", page)
        self.assertIn("interactive-widget=resizes-content", page)
        self.assertIn("100dvh", stylesheet)
        self.assertIn("safe-area-inset-bottom", stylesheet)
        self.assertIn("@media (prefers-reduced-motion: reduce)", stylesheet)
        self.assertIn("beforeinstallprompt", script)
        self.assertIn("requestFullscreen", script)
        self.assertIn("history.pushState", script)
        self.assertIn('window.addEventListener("popstate"', script)
        self.assertIn('id="app-drawer"', page)
        self.assertNotIn('class="mobile-nav"', page)
        manifest = (root / "web" / "manifest.webmanifest").read_text()
        self.assertIn('"display": "fullscreen"', manifest)
        self.assertIn('"display_override": ["fullscreen", "standalone"]', manifest)

    def test_system_status_panel_is_kept_in_settings(self) -> None:
        root = SCRIPT_DIR.parent.parent
        page = (root / "web" / "index.html").read_text()

        settings_start = page.index('data-view-panel="settings"')
        support_start = page.index('data-view-panel="support"')
        status_start = page.index('id="working-now-title"')

        self.assertEqual(page.count('id="working-now-title"'), 1)
        self.assertLess(settings_start, status_start)
        self.assertLess(status_start, support_start)
        self.assertIn("Состояние системы", page[settings_start:support_start])

    def test_decisions_workspace_is_read_only_and_uses_canonical_navigation(self) -> None:
        root = SCRIPT_DIR.parent.parent
        page = (root / "web" / "index.html").read_text()
        script = (root / "web" / "app.js").read_text()

        self.assertEqual(page.count('data-view="decisions"'), 1)
        self.assertEqual(page.count('data-view-panel="decisions"'), 1)
        self.assertIn('id="analysis-refresh"', page)
        self.assertIn('id="analysis-observations"', page)
        self.assertIn('id="analysis-sources"', page)
        self.assertIn("Только наблюдение", page)
        self.assertNotIn('class="mobile-nav"', page)
        self.assertIn('"/api/broker/tbank/analysis"', script)
        self.assertIn('decisions: "Решения"', script)
        self.assertIn("textContent = observation.detail", script)
        self.assertNotIn("/api/broker/tbank/operations", script)

    def test_personal_dashboard_exposes_release_version(self) -> None:
        root = SCRIPT_DIR.parent.parent
        page = (root / "web" / "index.html").read_text()
        project = (root / "pyproject.toml").read_text()
        deploy_script = MODULE.REMOTE_DEPLOY_SCRIPT

        self.assertGreaterEqual(page.count("data-app-version"), 3)
        self.assertIn("data-app-build", page)
        self.assertIn("__OMNICIO_VERSION__", page)
        self.assertIn("__OMNICIO_BUILD__", page)
        self.assertIn("/version.js?build=__OMNICIO_BUILD__", page)
        self.assertIn("/assets/app.css?build=__OMNICIO_BUILD__", page)
        self.assertIn("/assets/app.js?build=__OMNICIO_BUILD__", page)
        self.assertIn('version = "0.11.5"', project)
        self.assertIn("window.OMNICIO_RELEASE", deploy_script)
        self.assertIn('replace("__OMNICIO_VERSION__", version)', deploy_script)
        self.assertIn('replace("__OMNICIO_BUILD__", build)', deploy_script)
        self.assertIn("tomllib", deploy_script)
        self.assertEqual(MODULE.VERSION_PUBLIC_PATH, "/version.js")

    def test_runtime_assets_cannot_mix_across_frontend_releases(self) -> None:
        script = MODULE.REMOTE_DEPLOY_SCRIPT

        self.assertIn("location = /assets/app.css", script)
        self.assertIn("location = /assets/app.js", script)
        self.assertIn("location = /version.js", script)
        self.assertIn("location = /manifest.webmanifest", script)
        self.assertGreaterEqual(script.count('add_header Cache-Control "no-cache";'), 5)
        self.assertNotIn('add_header Cache-Control "public, max-age=300";', script)

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
