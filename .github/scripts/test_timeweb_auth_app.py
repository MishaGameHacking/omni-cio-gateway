#!/usr/bin/env python3
"""Regression tests for the auth application deployer."""

from __future__ import annotations

import ast
import base64
import copy
import hashlib
import importlib.util
import io
import json
import os
import pathlib
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from email.message import Message
from types import SimpleNamespace
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
        self.inputs: list[str | None] = []

    def run(self, command: str, *, input_text: str | None = None, timeout: int = 300) -> str:
        self.commands.append(command)
        self.inputs.append(input_text)
        if not self.succeeds:
            raise MODULE.InfraError("not ready")
        if "count(*) FILTER" in command:
            return "1|1\n"
        return ""


class ProductPreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = pathlib.Path(directory.name)
        self.legal = {
            "LEGAL_OPERATOR_NAME": "Test Operator", "LEGAL_OPERATOR_EMAIL": "operator@example.com",
            "LEGAL_PRIVACY_VERSION": "fixture-privacy", "LEGAL_CONSENT_VERSION": "fixture-consent",
            "LEGAL_TERMS_VERSION": "fixture-terms",
        }
        self.candidate_count = 0
        self.probe_environment = {
            "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/main",
            "GITHUB_SHA": "b" * 40, "GITHUB_RUN_ATTEMPT": "1", "GITHUB_RUN_ID": "123456",
            "OMNICIO_SMTP_PROBE_RECIPIENT": "Owner+release@GMAIL.COM",
        }
        self.auth_product = (
            'AUTH_SMTP_HOST="smtp.auth.example.com"\nAUTH_SMTP_SENDER="auth@example.com"\n'
            'AUTH_SMTP_USERNAME="auth-user"\nAUTH_SMTP_PASSWORD="auth-secret-fixture"\n'
            'AUTH_SMTP_PORT="587"\nAUTH_SMTP_MODE="starttls"\n'
        )
        environment = patch.dict(os.environ, self.legal, clear=True)
        environment.start()
        self.addCleanup(environment.stop)

    def _candidate(
        self, overrides: dict[str, str], *, smtp_probe: bool = False,
        release_sha: str = "", capture_configuration_errors: bool = False,
    ) -> SimpleNamespace:
        with patch.dict(os.environ, {**self.legal, **overrides}, clear=True):
            source = MODULE.render_product_preflight(
                smtp_probe=smtp_probe, release_sha=release_sha,
                capture_configuration_errors=capture_configuration_errors,
            )
        # Each generated fixture has its own module and bytecode path, including
        # same-length variations created within one filesystem timestamp tick.
        self.candidate_count += 1
        name = f"candidate_configuration_{self.candidate_count}"
        path = self.directory / (name + ".py")
        path.write_text(
            "from inplace_upgrade import UpgradeBlocked, _private_file, parse_environment\n"
            + source, encoding="utf-8",
        )
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            self.fail("Unable to load candidate configuration")
        candidate = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = candidate
        self.addCleanup(sys.modules.pop, spec.name, None)
        spec.loader.exec_module(candidate)
        return candidate

    def _run(
        self, candidate: SimpleNamespace, product: str, *, smtp_probe: bool = False,
        diagnostics: dict[str, object] | None = None,
    ) -> dict[str, object]:
        broker_key = base64.urlsafe_b64encode(b"b" * 32).decode("ascii")
        runtime = (
            'TELEGRAM_CLIENT_ID="123456"\nTELEGRAM_CLIENT_SECRET="synthetic-secret"\n'
            'VKID_APP_ID="789012"\n'
            'DATABASE_URL="postgresql://fixture@127.0.0.1/test"\n'
            'CLIENT_IP_KEY="fixture-ip-key"\n'
            f'BROKER_TOKEN_CRYPTO_KEY="{broker_key}"\n'
        )
        original = dict(os.environ)
        with patch.object(candidate, "_private_file", side_effect=[runtime, product]) as read:
            try:
                if smtp_probe:
                    return candidate.send_upgrade_control_email()
                if diagnostics is not None:
                    return candidate.require_upgrade_product_configuration(diagnostics=diagnostics)
                return candidate.require_upgrade_product_configuration()
            finally:
                self.assertEqual(dict(os.environ), original)
                self.assertEqual(
                    [call.args[0].name for call in read.call_args_list],
                    ["runtime.env", "product.env"],
                )

    def test_existing_email_configuration_is_read_without_requiring_new_credentials(self) -> None:
        candidate = self._candidate({})
        result = self._run(candidate, (
            'AUTH_SMTP_HOST="smtp.example.com"\nAUTH_SMTP_SENDER="test@example.com"\n'
            'AUTH_SMTP_PASSWORD="fixture-only"\nMARKET_DATA_TOKEN="source-fixture"\n'
            'MARKET_DATA_DISTRIBUTION_APPROVED="true"\n'
        ))
        self.assertEqual(result, {
            "status": "configuration_ready", "smtp_delivery_verified": False,
            "market_token_configured": True, "market_distribution_approved": False,
        })
        self.assertNotIn("fixture", json.dumps(result))

    def test_missing_social_provider_has_valid_diagnostics_without_sending(self) -> None:
        from inplace_upgrade import _valid_configuration_observation

        for key in ("TELEGRAM_CLIENT_ID", "TELEGRAM_CLIENT_SECRET", "VKID_APP_ID"):
            with self.subTest(key=key):
                candidate = self._candidate({})
                diagnostics: dict[str, object] = {}
                with (
                    patch("omnicio.notifications.NotificationTransport.send_email") as send,
                    self.assertRaisesRegex(
                        candidate.UpgradeBlocked, "^social_auth_configuration_required$",
                    ),
                ):
                    self._run(candidate, self.auth_product + f'{key}=""\n',
                              diagnostics=diagnostics)
                self.assertTrue(_valid_configuration_observation(diagnostics))
                self.assertEqual(diagnostics["stage"], "social_readiness")
                send.assert_not_called()

    def test_diagnostics_distinguish_missing_effective_smtp_fields_without_sending(self) -> None:
        for host_present, sender_present in ((False, False), (True, False), (False, True),
                                             (True, True)):
            product = (
                ('AUTH_SMTP_HOST="smtp.private-canary.example"\n' if host_present else "")
                + ('AUTH_SMTP_SENDER="private-canary@example.com"\n' if sender_present else "")
                + 'MARKET_DATA_TOKEN="private-market-canary"\n'
                + 'MARKET_DATA_DISTRIBUTION_APPROVED="true"\n'
            )
            candidate = self._candidate({})
            diagnostics: dict[str, object] = {}
            with (
                self.subTest(host=host_present, sender=sender_present),
                patch("omnicio.notifications.NotificationTransport.send_email") as send,
            ):
                if host_present and sender_present:
                    result = self._run(candidate, product, diagnostics=diagnostics)
                    self.assertEqual(set(result), {
                        "status", "smtp_delivery_verified", "market_token_configured",
                        "market_distribution_approved",
                    })
                else:
                    with self.assertRaisesRegex(
                        candidate.UpgradeBlocked, "^auth_email_configuration_required$",
                    ):
                        self._run(candidate, product, diagnostics=diagnostics)
            send.assert_not_called()
            self.assertEqual(diagnostics, {
                "stage": "validated" if host_present and sender_present else "email_readiness",
                "auth_smtp_host_present": host_present, "auth_smtp_sender_present": sender_present,
                "existing_receipt_key_present": False, "existing_archive_key_present": False,
                "market_data_token_present": True, "market_data_distribution_approved": False,
            })
            self.assertNotIn("canary", json.dumps(diagnostics))

    def test_diagnostics_use_future_settings_and_existing_key_custody(self) -> None:
        candidate = self._candidate({
            "AUTH_SMTP_HOST": "smtp.private-canary.example",
            "AUTH_SMTP_SENDER": "private-canary@example.com",
            "MARKET_DATA_TOKEN": "private-market-canary",
            "MARKET_DATA_DISTRIBUTION_APPROVED": "true",
            "OMNICIO_RESTORE_RECEIPT_KEY": "private-new-receipt-canary" * 2,
            "OMNICIO_RESTORE_ARCHIVE_KEY": base64.urlsafe_b64encode(b"k" * 32).decode(),
        })
        diagnostics: dict[str, object] = {}
        self._run(candidate, "", diagnostics=diagnostics)
        self.assertEqual(diagnostics, {
            "stage": "validated", "auth_smtp_host_present": True, "auth_smtp_sender_present": True,
            "existing_receipt_key_present": False, "existing_archive_key_present": False,
            "market_data_token_present": True, "market_data_distribution_approved": True,
        })
        preserved = self._candidate({})
        product = (self.auth_product
                   + 'OMNICIO_RESTORE_RECEIPT_KEY="private-existing-receipt-canary"\n'
                   + 'OMNICIO_RESTORE_ARCHIVE_KEY="private-existing-archive-canary"\n')
        self._run(preserved, product, diagnostics=diagnostics)
        self.assertTrue(diagnostics["existing_receipt_key_present"])
        self.assertTrue(diagnostics["existing_archive_key_present"])
        self.assertFalse(diagnostics["market_data_token_present"])
        self.assertFalse(diagnostics["market_data_distribution_approved"])
        self.assertNotIn("canary", json.dumps(diagnostics))

    def test_diagnostics_record_configuration_failure_stage_without_values(self) -> None:
        for overrides, product, stage in (
            ({"SESSION_TTL_SECONDS": "0"}, self.auth_product, "settings_validation"),
            ({"AUTH_SMTP_SENDER": "invalid-private-canary"}, self.auth_product,
             "auth_email_validation"),
            ({"NOTIFICATION_VAPID_PRIVATE_KEY": "private-canary"}, self.auth_product,
             "push_validation"),
            ({"OMNICIO_RESTORE_RECEIPT_KEY": "new-private-canary"},
             self.auth_product + 'OMNICIO_RESTORE_RECEIPT_KEY="old-private-canary"\n',
             "environment_merge"),
        ):
            candidate = self._candidate(overrides)
            diagnostics: dict[str, object] = {}
            with self.subTest(stage=stage), self.assertRaises(ValueError if stage in (
                "auth_email_validation", "push_validation",
            ) else candidate.UpgradeBlocked):
                self._run(candidate, product, diagnostics=diagnostics)
            self.assertEqual(diagnostics["stage"], stage)
            self.assertNotIn("canary", json.dumps(diagnostics))
        candidate = self._candidate({})
        for path, values, stage in (
            ("runtime", [FileNotFoundError("private-canary")], "runtime_environment"),
            ("product", ["", PermissionError("private-canary")], "product_environment"),
        ):
            diagnostics = {}
            with (
                self.subTest(path=path),
                patch.object(candidate, "_private_file", side_effect=values),
                self.assertRaises((OSError, candidate.UpgradeBlocked)),
            ):
                candidate.require_upgrade_product_configuration(diagnostics=diagnostics)
            self.assertEqual(diagnostics["stage"], stage)
            self.assertTrue(all(value is None for name, value in diagnostics.items()
                                if name != "stage"))

    def test_first_email_release_uses_ci_overrides_without_writing_environment(self) -> None:
        candidate = self._candidate({
            "AUTH_SMTP_HOST": "smtp.example.com", "AUTH_SMTP_SENDER": "test@example.com",
            "AUTH_SMTP_MODE": "starttls", "AUTH_SMTP_PORT": "587",
            "AUTH_SMTP_PASSWORD": (
                "fixture-$-`-\\-\"-__OMNICIO_PRESERVED_KEYS__-__OMNICIO_PRODUCT_ENVIRONMENT__"
            ),
            "MARKET_DATA_TOKEN": "fixture-source", "MARKET_DATA_DISTRIBUTION_APPROVED": "true",
        })
        reader = candidate.load_settings

        def check_password():
            self.assertEqual(
                os.environ["AUTH_SMTP_PASSWORD"],
                "fixture-$-`-\\-\"-__OMNICIO_PRESERVED_KEYS__-__OMNICIO_PRODUCT_ENVIRONMENT__",
            )
            return reader()

        with patch.object(candidate, "load_settings", side_effect=check_password):
            result = self._run(candidate, 'LEGAL_TERMS_VERSION="fixture-version"\n')
        self.assertTrue(result["market_token_configured"])
        self.assertTrue(result["market_distribution_approved"])
        self.assertFalse(result["smtp_delivery_verified"])

    def test_missing_or_invalid_effective_smtp_fails_before_activation(self) -> None:
        for product in (
            "", 'AUTH_SMTP_HOST="smtp.example.com"\n',
            'AUTH_SMTP_HOST="smtp.example.com"\nAUTH_SMTP_SENDER="test@example.com"\n'
            'AUTH_SMTP_MODE="plain"\n',
            'AUTH_SMTP_HOST="smtp.example.com"\nAUTH_SMTP_SENDER="test@example.com"\n'
            'AUTH_SMTP_PORT="65536"\n',
        ):
            with self.subTest(product=product):
                candidate = self._candidate({})
                with self.assertRaises((candidate.UpgradeBlocked, candidate.ConfigurationError)):
                    self._run(candidate, product)

    def test_future_base_and_integration_configuration_is_validated_before_cutover(self) -> None:
        product = (
            'AUTH_SMTP_HOST="smtp.example.com"\nAUTH_SMTP_SENDER="test@example.com"\n'
            'SESSION_TTL_SECONDS="60"\nASSISTANT_ENABLED="false"\n'
        )
        for overrides in (
            {"SESSION_TTL_SECONDS": "0"}, {"OPERATOR_USER_ID": "invalid-uuid"},
            {"ASSISTANT_ENABLED": "invalid-boolean"},
            {"ASSISTANT_ENABLED": "false", "ASSISTANT_DAILY_REQUEST_LIMIT": "201"},
        ):
            with self.subTest(overrides=overrides):
                candidate = self._candidate(overrides)
                with self.assertRaises(candidate.ConfigurationError):
                    self._run(candidate, product)

    def test_invalid_published_settings_are_rejected_before_remote_preflight(self) -> None:
        for overrides in ({"AUTH_SMTP_HOST": "bad host"}, {"LEGAL_OPERATOR_EMAIL": "not-email"}):
            with self.subTest(overrides=overrides), self.assertRaises(MODULE.InfraError):
                self._candidate(overrides)

    def test_candidate_validates_email_sender_and_encryption(self) -> None:
        for product in (
            'AUTH_SMTP_HOST="smtp.example.com"\nAUTH_SMTP_SENDER="not-email"\n',
            'AUTH_SMTP_HOST="smtp.example.com"\nAUTH_SMTP_SENDER="test@example.com"\n'
            'NOTIFICATION_CRYPTO_KEY="invalid-fernet-key"\n',
        ):
            with self.subTest(product=product):
                candidate = self._candidate({})
                with self.assertRaises(ValueError):
                    self._run(candidate, product)

    def test_candidate_validates_actual_push_key_before_cutover(self) -> None:
        candidate = self._candidate({"NOTIFICATION_VAPID_SUBJECT": "https://omnicio.ru"})
        email = 'AUTH_SMTP_HOST="smtp.example.com"\nAUTH_SMTP_SENDER="test@example.com"\n'
        for key in ("invalid-key", base64.urlsafe_b64encode(b"\0" * 32).decode("ascii")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self._run(candidate, email + f'NOTIFICATION_VAPID_PRIVATE_KEY="{key}"\n')
        valid_key = base64.urlsafe_b64encode(b"\1" * 32).decode("ascii")
        result = self._run(candidate, email + f'NOTIFICATION_VAPID_PRIVATE_KEY="{valid_key}"\n')
        self.assertEqual(result["status"], "configuration_ready")

    def test_removed_base_values_do_not_survive_from_old_product_environment(self) -> None:
        candidate = self._candidate({})
        product = (
            'AUTH_SMTP_HOST="smtp.example.com"\nAUTH_SMTP_SENDER="test@example.com"\n'
            'SESSION_TTL_SECONDS="0"\nOPERATOR_USER_ID="invalid-old-authority"\n'
            'UNRELATED_OLD_SETTING="old-value"\n'
        )
        captured = {}
        reader = candidate.load_settings

        def capture_settings():
            captured.update(os.environ)
            return reader()

        with patch.object(candidate, "load_settings", side_effect=capture_settings):
            self.assertEqual(self._run(candidate, product)["status"], "configuration_ready")
        self.assertEqual(captured["SESSION_TTL_SECONDS"], "34560000")
        self.assertEqual(captured["OPERATOR_USER_ID"], "")
        self.assertNotIn("UNRELATED_OLD_SETTING", captured)
        self.assertEqual(captured["AUTH_SMTP_HOST"], "smtp.example.com")

    def test_recovery_key_custody_survives_and_rotation_is_rejected(self) -> None:
        from cryptography.fernet import Fernet

        archive_key = Fernet.generate_key().decode("ascii")
        archive = Fernet(archive_key).encrypt(b"PGDMPsynthetic-recovery-fixture")
        receipt_key = "synthetic-receipt-key"
        product = (
            'AUTH_SMTP_HOST="smtp.example.com"\nAUTH_SMTP_SENDER="test@example.com"\n'
            f'OMNICIO_RESTORE_ARCHIVE_KEY="{archive_key}"\n'
            f'OMNICIO_RESTORE_RECEIPT_KEY="{receipt_key}"\n'
        )
        for overrides in ({}, {"OMNICIO_RESTORE_ARCHIVE_KEY": archive_key,
                               "OMNICIO_RESTORE_RECEIPT_KEY": receipt_key}):
            candidate = self._candidate(overrides)
            reader = candidate.load_settings

            def check_custody(reader=reader):
                self.assertEqual(
                    Fernet(os.environ["OMNICIO_RESTORE_ARCHIVE_KEY"]).decrypt(archive),
                    b"PGDMPsynthetic-recovery-fixture",
                )
                self.assertEqual(os.environ["OMNICIO_RESTORE_RECEIPT_KEY"], receipt_key)
                return reader()

            with patch.object(candidate, "load_settings", side_effect=check_custody):
                self.assertEqual(self._run(candidate, product)["status"], "configuration_ready")
        for key in ("OMNICIO_RESTORE_ARCHIVE_KEY", "OMNICIO_RESTORE_RECEIPT_KEY"):
            with self.subTest(key=key):
                candidate = self._candidate({key: "replacement-key"})
                with patch.object(candidate, "load_settings") as reader:
                    with self.assertRaisesRegex(candidate.UpgradeBlocked, "recovery_key_rotation"):
                        self._run(candidate, product)
                    reader.assert_not_called()

    def test_generated_environment_escapes_roundtrip_and_reject_substitution(self) -> None:
        candidate = self._candidate({})
        for value in ("", "plain", "space value", 'literal-$-`-\\-"-only', "single'quote"):
            with self.subTest(value=value):
                self.assertEqual(
                    candidate.parse_environment("KEY=" + MODULE._environment_value(value) + "\n"),
                    {"KEY": value},
                )
        for value in ('"$(printf unsafe)"', '"$HOME"', '"`id`"'):
            with self.subTest(value=value), self.assertRaises(candidate.UpgradeBlocked):
                candidate.parse_environment("KEY=" + value + "\n")

    def test_normal_preflight_never_sends_even_when_probe_inputs_exist(self) -> None:
        for include_probe in (False, True):
            with self.subTest(include_probe=include_probe):
                candidate = self._candidate(
                    self.probe_environment, smtp_probe=include_probe, release_sha="b" * 40,
                )
                self.assertEqual(hasattr(candidate, "send_upgrade_control_email"), include_probe)
                with patch("omnicio.notifications.NotificationTransport.send_email") as send:
                    result = self._run(candidate, self.auth_product)
                send.assert_not_called()
                self.assertEqual(result, {
                    "status": "configuration_ready", "smtp_delivery_verified": False,
                    "market_token_configured": False, "market_distribution_approved": False,
                })

    def test_probe_refuses_missing_or_repeated_manual_authority_before_send(self) -> None:
        scenarios = (
            ("GITHUB_EVENT_NAME", "push"), ("GITHUB_EVENT_NAME", "pull_request"),
            ("GITHUB_REF", "refs/heads/feature"), ("GITHUB_SHA", "a" * 40),
            ("GITHUB_RUN_ATTEMPT", None), ("GITHUB_RUN_ATTEMPT", ""),
            ("GITHUB_RUN_ATTEMPT", "0"), ("GITHUB_RUN_ATTEMPT", "2"),
            ("GITHUB_RUN_ATTEMPT", "01"), ("GITHUB_RUN_ID", None),
            ("GITHUB_RUN_ID", "0"), ("GITHUB_RUN_ID", "1\nBcc: other@gmail.com"),
            ("GITHUB_RUN_ID", "1\u0662"), ("GITHUB_RUN_ID", "1" * 21),
            ("OMNICIO_SMTP_PROBE_RECIPIENT", None),
        )
        for name, value in scenarios:
            environment = dict(self.probe_environment)
            if value is None:
                environment.pop(name)
            else:
                environment[name] = value
            with self.subTest(name=name, value=value):
                with (
                    patch("omnicio.notifications.NotificationTransport.send_email") as send,
                    self.assertRaises(MODULE.InfraError),
                ):
                    self._candidate(
                        environment, smtp_probe=True, release_sha="b" * 40,
                        capture_configuration_errors=True,
                    )
                send.assert_not_called()

    def test_probe_rejects_malformed_recipient_and_header_injection(self) -> None:
        for recipient in (
            "Owner <owner@gmail.com>", "owner@gmail.com\r\nBcc: other@gmail.com",
            "owner@gmail.com,other@gmail.com", "owner@GMAIL.COM.evil", "owner@example.com",
            "a..b@gmail.com", "owner\t@gmail.com", "владелец@gmail.com",
        ):
            with self.subTest(recipient=recipient):
                candidate = self._candidate(
                    {**self.probe_environment, "OMNICIO_SMTP_PROBE_RECIPIENT": recipient},
                    smtp_probe=True, release_sha="b" * 40,
                )
                with (
                    patch("omnicio.notifications.NotificationTransport.send_email") as send,
                    self.assertRaises(candidate.SecurityValueError),
                ):
                    self._run(candidate, self.auth_product, smtp_probe=True)
                send.assert_not_called()

    def test_probe_sends_one_auth_message_with_existing_transport_api(self) -> None:
        from omnicio import notifications

        candidate = self._candidate(
            {**self.probe_environment, "AUTH_SMTP_PASSWORD": "future-auth-password"},
            smtp_probe=True, release_sha="b" * 40,
        )
        # The accepted 1.3 module has these two API names, but none of the new
        # candidate configuration validators. Exercise that import boundary.
        legacy_api = SimpleNamespace(
            NotificationConfig=notifications.NotificationConfig,
            NotificationTransport=notifications.NotificationTransport,
        )
        product = self.auth_product + (
            'NOTIFICATION_SMTP_HOST="unrelated.example.com"\n'
            'NOTIFICATION_SMTP_USERNAME="unrelated-user"\n'
            'NOTIFICATION_SMTP_PASSWORD="unrelated-secret"\n'
            'NOTIFICATION_SMTP_SENDER="unrelated@example.com"\n'
        )
        with (
            patch.object(notifications.smtplib, "SMTP") as smtp,
            patch.object(notifications.smtplib, "SMTP_SSL") as smtp_tls,
            patch.dict(sys.modules, {"omnicio.notifications": legacy_api}),
        ):
            result = self._run(candidate, product, smtp_probe=True)
        smtp.assert_called_once_with("smtp.auth.example.com", 587, timeout=10)
        smtp_tls.assert_not_called()
        client = smtp.return_value
        client.login.assert_called_once_with("auth-user", "future-auth-password")
        client.starttls.assert_called_once()
        client.send_message.assert_called_once()
        message = client.send_message.call_args.args[0]
        expected_id = "<smtp-probe-1.4-bbbbbbbbbbbb-123456@omnicio.ru>"
        self.assertEqual(message["Message-ID"], expected_id)
        self.assertEqual(message["To"], "Owner+release@gmail.com")
        self.assertEqual(message["From"], "auth@example.com")
        self.assertEqual(result, {
            "message_id": expected_id, "status": "accepted", "code": "email_provider_accepted",
        })
        self.assertNotIn("secret", message.as_string())
        self.assertNotIn("password", message.as_string())
        self.assertNotIn("Owner", json.dumps(result))

    def test_probe_reports_rejection_or_ambiguity_without_a_second_send(self) -> None:
        from omnicio import notifications

        recipient = "Owner+release@gmail.com"
        cases = (
            (notifications.smtplib.SMTPResponseException(451, b"synthetic-secret-reply"),
             "queued", "email_temporary_rejection"),
            (notifications.smtplib.SMTPResponseException(550, b"synthetic-secret-reply"),
             "failed", "email_provider_rejected"),
            (notifications.smtplib.SMTPRecipientsRefused({recipient: (550, b"private-reply")}),
             "failed", "email_recipient_rejected"),
            (OSError("synthetic-secret-connection"), "uncertain", "email_result_unknown"),
        )
        for error, status, code in cases:
            with self.subTest(status=status, code=code):
                candidate = self._candidate(
                    self.probe_environment, smtp_probe=True, release_sha="b" * 40,
                )
                with patch.object(notifications.smtplib, "SMTP") as smtp:
                    smtp.return_value.send_message.side_effect = error
                    result = self._run(candidate, self.auth_product, smtp_probe=True)
                smtp.assert_called_once()
                smtp.return_value.send_message.assert_called_once()
                self.assertEqual(result, {
                    "message_id": "<smtp-probe-1.4-bbbbbbbbbbbb-123456@omnicio.ru>",
                    "status": status, "code": code,
                })
                self.assertNotIn("secret", json.dumps(result))
                self.assertNotIn("private", json.dumps(result))

    def test_probe_placeholder_text_is_literal_recipient_data(self) -> None:
        from omnicio.notifications import DeliveryResult

        recipient = "__OMNICIO_SMTP_PROBE_TAG__@gmail.com"
        candidate = self._candidate(
            {**self.probe_environment, "OMNICIO_SMTP_PROBE_RECIPIENT": recipient},
            smtp_probe=True, release_sha="b" * 40,
        )
        with patch("omnicio.notifications.NotificationTransport.send_email") as send:
            send.return_value = DeliveryResult("accepted", "email_provider_accepted")
            self._run(candidate, self.auth_product, smtp_probe=True)
        send.assert_called_once()
        self.assertEqual(send.call_args.args[0], {"email": recipient})

    def test_configuration_failure_can_be_reported_independently_without_sending(self) -> None:
        for include_probe in (False, True):
            with self.subTest(include_probe=include_probe):
                candidate = self._candidate(
                    {**self.probe_environment, "AUTH_SMTP_HOST": "invalid host"},
                    smtp_probe=include_probe, release_sha="b" * 40,
                    capture_configuration_errors=True,
                )
                diagnostics = {"auth_smtp_host_present": None, "auth_smtp_sender_present": None}
                with self.assertRaisesRegex(
                    candidate.UpgradeBlocked, "product_configuration_invalid",
                ):
                    candidate.require_upgrade_product_configuration(diagnostics=diagnostics)
                self.assertEqual(diagnostics["stage"], "candidate_validation")
                self.assertTrue(all(value is None for name, value in diagnostics.items()
                                    if name != "stage"))
                if include_probe:
                    with (
                        patch("omnicio.notifications.NotificationTransport.send_email") as send,
                        self.assertRaisesRegex(
                            candidate.UpgradeBlocked, "product_configuration_invalid",
                        ),
                    ):
                        candidate.send_upgrade_control_email()
                    send.assert_not_called()

    def test_configuration_capture_does_not_hide_source_read_failures(self) -> None:
        error = OSError("unreadable source")
        with (
            patch.object(MODULE.pathlib.Path, "read_text", side_effect=error),
            self.assertRaisesRegex(OSError, "unreadable source"),
        ):
            MODULE.render_product_preflight(capture_configuration_errors=True)

    def test_preflight_transport_accepts_only_bounded_safe_confirmation(self) -> None:
        from unittest.mock import Mock

        valid = {
            "status": "configuration_ready", "smtp_delivery_verified": False,
            "market_token_configured": False, "market_distribution_approved": False,
        }
        for result in (valid, {**valid, "smtp_delivery_verified": True},
                       {**valid, "market_token_configured": 1},
                       {**valid, "unexpected": "fixture"}, "x" * 2049):
            with self.subTest(result=result):
                ssh = Mock()
                ssh.run.return_value = result if isinstance(result, str) else json.dumps(result)
                if result == valid:
                    MODULE.preflight_product_environment(ssh)
                else:
                    with self.assertRaises(MODULE.InfraError):
                        MODULE.preflight_product_environment(ssh)
                command = ssh.run.call_args.args[0]
                self.assertNotIn("fixture", command)
                self.assertIn(f"flock -n {MODULE.DEPLOY_LOCK}", command)
                compile(ssh.run.call_args.kwargs["input_text"], "preflight", "exec")


    def test_preflight_failure_leaves_the_existing_release_and_environment_untouched(self) -> None:
        from contextlib import ExitStack
        from unittest.mock import MagicMock

        client = MagicMock()
        client.get_vpc_services.return_value = [{"name": "database"}]
        monitored = (
            "validate_product_environment", "validate_legal_documents",
            "find_managed_server", "find_vpc", "public_ipv4", "build_release_archive",
            "EphemeralSsh", "runtime_is_ready", "preflight_product_environment",
            "upload_release", "write_product_environment", "deploy_remote", "rollback_remote",
            "commit_product_environment", "add_summary", "set_output",
        )
        with ExitStack() as stack:
            mocks = {
                name: stack.enter_context(patch.object(MODULE, name)) for name in monitored
            }
            mocks["find_managed_server"].return_value = {"id": 1}
            mocks["find_vpc"].return_value = {"id": "fixture-vpc"}
            mocks["public_ipv4"].return_value = "192.0.2.1"
            mocks["build_release_archive"].return_value = "fixture-archive"
            mocks["runtime_is_ready"].return_value = True
            mocks["preflight_product_environment"].side_effect = MODULE.InfraError("not ready")
            with self.assertRaises(MODULE.InfraError):
                MODULE.reconcile(
                    client, server_name="fixture-server", server_comment="fixture-only",
                    release_sha="a" * 40, repository_root=SCRIPT_DIR.parent.parent,
                    cluster_name="database", vpc_name="fixture-vpc", location="fixture",
                    availability_zone="fixture",
                )
            mocks["preflight_product_environment"].assert_called_once()
            for name in (
                "upload_release", "write_product_environment", "deploy_remote", "rollback_remote",
                "commit_product_environment", "set_output",
            ):
                mocks[name].assert_not_called()


class RollbackCompatibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = pathlib.Path(directory.name).resolve()
        self.releases = self.root / "releases"
        self.releases.mkdir()
        source = self.root / "rollback_check.py"
        source.write_text(MODULE._ROLLBACK_COMPATIBILITY_PROGRAM, encoding="utf-8")
        spec = importlib.util.spec_from_file_location("rollback_check", source)
        if spec is None or spec.loader is None:
            self.fail("Unable to load the embedded compatibility check")
        self.checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.checker)
        self.metadata_policy = self.checker.trusted_metadata

        # The production target is POSIX/root, while this suite also runs on
        # Windows. Simulate only its ownership/mode; keep real file types,
        # contents, bounded reads and path resolution. Test the trust policy
        # separately with unsafe ownership, modes and symlinks below.
        trust = patch.object(self.checker, "trusted_metadata", self._fixture_metadata)
        trust.start()
        self.addCleanup(trust.stop)

    def _fixture_metadata(self, info: os.stat_result, *, directory: bool) -> bool:
        mode = stat.S_IFMT(info.st_mode) | (0o755 if directory else 0o644)
        return bool(self.metadata_policy(
            SimpleNamespace(st_uid=0, st_mode=mode), directory=directory,
        ))

    def _release(
        self, letter: str, contract: str | None, *, version: str = "1.4.0",
    ) -> pathlib.Path:
        release = self.releases / (letter * 40)
        release.mkdir(exist_ok=True)
        body = '[project]\nname="omnicio-gateway"\n' + f'version="{version}"\n'
        if contract is not None:
            body += '[tool.omnicio.runtime]\nrollback_contract=' + json.dumps(contract) + '\n'
        (release / "pyproject.toml").write_text(body, encoding="utf-8")
        return release

    def test_contract_is_explicit_and_independent_of_version_order(self) -> None:
        expected = self.checker.EXPECTED_CONTRACT
        scenarios = (
            (expected, expected, True),
            (expected, None, False),
            (None, expected, False),
            (expected, "unknown-contract", False),
            ("unknown-contract", "unknown-contract", False),
        )
        for candidate_contract, previous_contract, allowed in scenarios:
            with self.subTest(candidate=candidate_contract, previous=previous_contract):
                candidate = self._release("a", candidate_contract, version="1.4.0")
                previous = self._release("b", previous_contract, version="1.4.1")
                self.assertEqual(
                    self.checker.compatible(candidate, previous, self.releases), allowed,
                )

    def test_missing_malformed_foreign_and_oversized_metadata_are_denied(self) -> None:
        candidate = self._release("a", self.checker.EXPECTED_CONTRACT)
        previous = self._release("b", self.checker.EXPECTED_CONTRACT)
        metadata = previous / "pyproject.toml"
        for body in ("", "[broken", "project=7", '[project]\nname="other-service"',
                     "#" * (self.checker.MAX_METADATA_BYTES + 1)):
            with self.subTest(body_length=len(body)):
                metadata.write_text(body, encoding="utf-8")
                self.assertFalse(self.checker.compatible(candidate, previous, self.releases))
        metadata.unlink()
        self.assertFalse(self.checker.compatible(candidate, previous, self.releases))
        self.assertFalse(self.checker.compatible(candidate, "", self.releases))
        self.assertFalse(self.checker.compatible(candidate, self.root, self.releases))

    def test_untrusted_metadata_modes_and_owners_are_denied(self) -> None:
        cases = (
            (0, stat.S_IFREG | 0o644, False, True),
            (0, stat.S_IFDIR | 0o755, True, True),
            (1000, stat.S_IFREG | 0o644, False, False),
            (0, stat.S_IFREG | 0o664, False, False),
            (0, stat.S_IFREG | 0o646, False, False),
            (0, stat.S_IFDIR | 0o775, True, False),
            (0, stat.S_IFLNK | 0o777, False, False),
            (0, stat.S_IFIFO | 0o600, False, False),
        )
        for owner, mode, directory, allowed in cases:
            with self.subTest(owner=owner, mode=mode, directory=directory):
                self.assertEqual(self.metadata_policy(
                    SimpleNamespace(st_uid=owner, st_mode=mode), directory=directory,
                ), allowed)

        candidate = self._release("a", self.checker.EXPECTED_CONTRACT)
        previous = self._release("b", self.checker.EXPECTED_CONTRACT)
        with patch.object(self.checker, "trusted_metadata", return_value=False):
            self.assertFalse(self.checker.compatible(candidate, previous, self.releases))

    def _run_rollback(
        self, flow: str, *, compatible: bool, failure: str = "",
        missing_state: bool = False, current_candidate: bool = False,
    ) -> tuple[subprocess.CompletedProcess[str], str, pathlib.Path, pathlib.Path, pathlib.Path]:
        candidate = self._release("a", self.checker.EXPECTED_CONTRACT)
        previous = self._release(
            "b", self.checker.EXPECTED_CONTRACT if compatible else None,
            version="1.4.0" if compatible else "1.3.0",
        )
        (self.root / "run").mkdir(exist_ok=True)
        (self.root / "etc").mkdir(exist_ok=True)
        (self.root / "nginx").mkdir(exist_ok=True)
        previous_web = self.root / "previous-web"
        previous_web.mkdir(exist_ok=True)
        sha = candidate.name
        state = self.root / "run" / f"omnicio-auth-deploy-{sha}.state"
        state.write_text(
            f"PREVIOUS_APP={shlex.quote(previous.as_posix())}\n"
            f"PREVIOUS_WEB={shlex.quote(previous_web.as_posix())}\n"
            "OBSERVER_TIMER_WAS_ENABLED=1\nOBSERVER_TIMER_WAS_ACTIVE=1\n",
            encoding="utf-8", newline="\n",
        )
        if missing_state:
            state.unlink()
        product = self.root / "etc" / "product.env"
        product.write_text("candidate-environment\n", encoding="utf-8")
        product.with_name(f"product.env.pre-{sha}").write_text(
            "previous-environment\n", encoding="utf-8",
        )
        product.with_name(f"product.env.pre-{sha}.state").write_text(
            "present\n", encoding="utf-8", newline="\n",
        )
        nginx = self.root / "nginx" / "omnicio.ru"
        nginx.write_text("candidate-nginx\n", encoding="utf-8")
        nginx.with_name("omnicio.ru.pre-auth").write_text("previous-nginx\n", encoding="utf-8")
        log = self.root / "calls.log"
        log.write_text("", encoding="utf-8")
        allowed = self.checker.compatible(candidate, previous, self.releases)
        preamble = f"""set -euo pipefail
LOG={shlex.quote(log.as_posix())}
CHECK_EXIT={0 if allowed else 45}
STOP_FAIL={1 if failure == 'stop' else 0}
RESTART_FAIL={1 if failure == 'restart' else 0}
NGINX_FAIL={1 if flow == 'nginx' else 0}
NGINX_ALWAYS_FAIL={1 if failure == 'nginx' else 0}
CURRENT_TARGET={shlex.quote((candidate if current_candidate else previous).as_posix())}
python3() {{
    printf '%s\\n' 'contract-check' >> "$LOG"
    cat >/dev/null
    test "$1" = '-I' || return 45
    test "$2" = '-' || return 45
    test "$3" = "$RELEASE" || return 45
    test "$4" = "${{PREVIOUS_APP:-}}" || return 45
    if [ -z "$4" ]; then return 45; fi
    return "$CHECK_EXIT"
}}
readlink() {{ printf '%s\\n' "$CURRENT_TARGET"; }}
systemctl() {{
    printf 'systemctl %s\\n' "$*" >> "$LOG"
    if [ "$1" = 'stop' ] && [ "$STOP_FAIL" = 1 ]; then return 1; fi
    if [ "$1" = 'restart' ] && [ "$RESTART_FAIL" = 1 ]; then return 1; fi
}}
ln() {{ printf 'ln %s\\n' "$*" >> "$LOG"; }}
nginx() {{
    if [ "$NGINX_ALWAYS_FAIL" = 1 ]; then return 1; fi
    if [ "$NGINX_FAIL" = 1 ]; then NGINX_FAIL=0; return 1; fi
}}
"""
        if flow == "controller":
            script = MODULE.REMOTE_ROLLBACK_SCRIPT
        else:
            deploy = MODULE.REMOTE_DEPLOY_SCRIPT
            if flow == "readiness":
                start = deploy.index('\nif [ "$READY" != "1" ]; then')
                end = deploy.index('\nif [ -f "$NGINX_SITE" ]; then', start)
            else:
                start = deploy.index('\nif ! nginx -t; then')
                end = deploy.index('\nsystemctl reload nginx', start)
            script = (
                f'SHA="{sha}"\nRELEASE="/opt/omnicio/releases/$SHA"\n'
                'APP_CURRENT="/opt/omnicio/current"\n'
                'WEB_CURRENT="/var/www/omnicio.ru/current"\n'
                'NGINX_SITE="/etc/nginx/sites-available/omnicio.ru"\n'
                '. "/run/omnicio-auth-deploy-$SHA.state"\nREADY=0\n'
                + MODULE._ROLLBACK_COMPATIBILITY_GUARD + deploy[start:end]
            )
        for original, replacement in (
            ("/opt/omnicio/releases", self.releases),
            ("/opt/omnicio/current", self.root / "current"),
            ("/var/www/omnicio.ru/current", self.root / "web-current"),
            ("/etc/nginx/sites-available", self.root / "nginx"),
            ("/etc/omnicio", self.root / "etc"),
            ("/run/omnicio-auth-deploy", self.root / "run" / "omnicio-auth-deploy"),
        ):
            script = script.replace(original, replacement.as_posix())
        if os.name == "nt":
            bash = str(pathlib.Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
                       / "Git" / "bin" / "bash.exe")
        else:
            bash = "/bin/bash"
        # Bash input and sourced state must keep LF on Windows too. Text-mode
        # stdin would translate newlines before Git Bash receives this script.
        raw = subprocess.run(
            [bash, "-s", "--", sha], input=(preamble + script).encode("utf-8"),
            capture_output=True, timeout=10,
        )
        result = subprocess.CompletedProcess(
            raw.args, raw.returncode, raw.stdout.decode("utf-8"), raw.stderr.decode("utf-8"),
        )
        return result, log.read_text(encoding="utf-8"), product, nginx, candidate

    def test_incompatible_rollback_never_restores_or_restarts_any_previous_runtime(self) -> None:
        for flow in ("readiness", "nginx", "controller"):
            with self.subTest(flow=flow):
                result, calls, product, nginx, candidate = self._run_rollback(
                    flow, compatible=False,
                )
                self.assertEqual(result.returncode, 45, result.stderr)
                self.assertIn("contract-check\n", calls)
                self.assertIn(
                    "systemctl stop omnicio-auth.service omnicio-observer.timer "
                    "omnicio-observer.service", calls,
                )
                self.assertIn(
                    "systemctl disable omnicio-auth.service omnicio-observer.timer "
                    "omnicio-observer.service", calls,
                )
                self.assertNotIn("restart", calls)
                self.assertNotIn("ln ", calls)
                self.assertEqual(product.read_text(encoding="utf-8"), "candidate-environment\n")
                self.assertEqual(nginx.read_text(encoding="utf-8"), "candidate-nginx\n")
                self.assertTrue((candidate / "pyproject.toml").is_file())

    def test_same_explicit_contract_allows_normal_rollback(self) -> None:
        for flow, expected_exit in (("readiness", 41), ("nginx", 42), ("controller", 0)):
            with self.subTest(flow=flow):
                result, calls, product, nginx, _ = self._run_rollback(flow, compatible=True)
                self.assertEqual(result.returncode, expected_exit, result.stderr)
                self.assertLess(calls.index("contract-check"), calls.index("ln "))
                if flow != "nginx":
                    self.assertIn("systemctl restart omnicio-auth.service", calls)
                if flow == "controller":
                    self.assertEqual(product.read_text(encoding="utf-8"), "previous-environment\n")
                    self.assertIn("systemctl restart omnicio-observer.timer", calls)
                if flow != "readiness":
                    self.assertEqual(nginx.read_text(encoding="utf-8"), "previous-nginx\n")

    def test_failed_service_stop_is_reported_without_restore_or_success_claim(self) -> None:
        result, calls, product, _, _ = self._run_rollback(
            "controller", compatible=False, failure="stop",
        )
        self.assertEqual(result.returncode, 46, result.stderr)
        self.assertNotIn("restart", calls)
        self.assertNotIn("ln ", calls)
        self.assertEqual(product.read_text(encoding="utf-8"), "candidate-environment\n")
        self.assertIn("shutdown was not confirmed", result.stderr)

    def test_environment_failure_before_deploy_preserves_compatible_running_service(self) -> None:
        result, calls, product, nginx, _ = self._run_rollback(
            "controller", compatible=True, missing_state=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, "contract-check\n")
        self.assertEqual(product.read_text(encoding="utf-8"), "previous-environment\n")
        self.assertEqual(nginx.read_text(encoding="utf-8"), "candidate-nginx\n")

    def test_compatible_service_or_nginx_failure_does_not_claim_successful_restore(self) -> None:
        for failure in ("restart", "nginx"):
            with self.subTest(failure=failure):
                result, calls, product, _, _ = self._run_rollback(
                    "controller", compatible=True, failure=failure,
                )
                self.assertEqual(result.returncode, 47, result.stderr)
                self.assertIn("systemctl restart omnicio-auth.service", calls)
                self.assertIn("systemctl restart omnicio-observer.timer", calls)
                self.assertEqual(product.read_text(encoding="utf-8"), "previous-environment\n")

    def test_missing_state_does_not_certify_legacy_or_already_active_candidate(self) -> None:
        for compatible, current_candidate in ((False, False), (True, True)):
            with self.subTest(compatible=compatible, current_candidate=current_candidate):
                result, calls, product, _, _ = self._run_rollback(
                    "controller", compatible=compatible, missing_state=True,
                    current_candidate=current_candidate,
                )
                self.assertEqual(result.returncode, 45, result.stderr)
                self.assertNotIn("restart", calls)
                self.assertNotIn("ln ", calls)
                self.assertEqual(product.read_text(encoding="utf-8"), "candidate-environment\n")


class AuthAppDeployTests(unittest.TestCase):
    def test_app_entrypoint_rejects_unapproved_context_before_provider_access(self) -> None:
        args = SimpleNamespace(release_sha="a" * 40)
        baseline = {
            "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/main",
            "GITHUB_SHA": "a" * 40, "TIMEWEB_CLOUD_TOKEN": "synthetic-private-token",
        }
        for overrides in (
            {"GITHUB_EVENT_NAME": ""}, {"GITHUB_EVENT_NAME": "push"},
            {"GITHUB_EVENT_NAME": "workflow_run"}, {"GITHUB_EVENT_NAME": "pull_request"},
            {"GITHUB_REF": "refs/heads/feature"}, {"GITHUB_SHA": "b" * 40},
        ):
            with (
                self.subTest(overrides=overrides),
                patch.dict(os.environ, {**baseline, **overrides}, clear=True),
                patch.object(MODULE, "parse_args", return_value=args),
                patch.object(MODULE, "TimewebClient") as client,
                patch.object(MODULE, "reconcile") as reconcile,
                patch.object(sys, "stderr", new_callable=io.StringIO) as error,
            ):
                self.assertEqual(MODULE.main(), 1)
                client.assert_not_called()
                reconcile.assert_not_called()
                self.assertEqual(
                    error.getvalue(), "::error::postgres_operation_requires_manual_main\n",
                )

    def test_app_entrypoint_allows_explicit_main_apply_and_reconciliation_attempts(self) -> None:
        args = SimpleNamespace(
            scope="application",
            release_sha="a" * 40, server_name="fixture-server", server_comment="fixture-managed",
            repository_root=str(SCRIPT_DIR.parent.parent), cluster_name="fixture-database",
            vpc_name="fixture-vpc", location="fixture-location", availability_zone="fixture-zone",
        )
        baseline = {
            "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/main",
            "GITHUB_SHA": "a" * 40, "TIMEWEB_CLOUD_TOKEN": "synthetic-private-token",
        }
        for attempt in (None, "1", "2"):
            environment = dict(baseline)
            if attempt is not None:
                environment["GITHUB_RUN_ATTEMPT"] = attempt
            with (
                self.subTest(attempt=attempt),
                patch.dict(os.environ, environment, clear=True),
                patch.object(MODULE, "parse_args", return_value=args),
                patch.object(MODULE, "TimewebClient") as client,
                patch.object(MODULE, "reconcile", return_value=0) as reconcile,
            ):
                self.assertEqual(MODULE.main(), 0)
                client.assert_called_once_with("synthetic-private-token")
                reconcile.assert_called_once_with(
                    client.return_value,
                    server_name=args.server_name, server_comment=args.server_comment,
                    release_sha=args.release_sha,
                    repository_root=SCRIPT_DIR.parent.parent.resolve(),
                    cluster_name=args.cluster_name, vpc_name=args.vpc_name,
                    location=args.location, availability_zone=args.availability_zone,
                )

    def test_public_scope_never_enters_application_or_database_reconcile(self) -> None:
        args = SimpleNamespace(scope="public_site", release_sha="a" * 40,
                               server_name="fixture-server", server_comment="fixture-managed",
                               repository_root=str(SCRIPT_DIR.parent.parent))
        environment = {"GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/main",
                       "GITHUB_SHA": "a" * 40, "TIMEWEB_CLOUD_TOKEN": "synthetic-private-token"}
        with (patch.dict(os.environ, environment, clear=True),
              patch.object(MODULE, "parse_args", return_value=args),
              patch.object(MODULE, "TimewebClient") as client,
              patch.object(MODULE, "reconcile") as reconcile,
              patch("timeweb_public_site.publish_public_site") as publish,
              patch.object(MODULE, "set_output") as output,
              patch.object(MODULE, "add_summary")):
            self.assertEqual(MODULE.main(), 0)
            reconcile.assert_not_called()
            publish.assert_called_once_with(client.return_value,
                root=SCRIPT_DIR.parent.parent.resolve(), sha=args.release_sha,
                server_name=args.server_name, server_comment=args.server_comment)
            output.assert_called_once_with("status", "public_site_ready")

    def test_release_sha_requires_full_lowercase_commit(self) -> None:
        self.assertIsNotNone(MODULE.RELEASE_RE.fullmatch("a" * 40))
        self.assertIsNone(MODULE.RELEASE_RE.fullmatch("A" * 40))
        self.assertIsNone(MODULE.RELEASE_RE.fullmatch("a" * 39))

    def test_upload_never_removes_the_active_release(self) -> None:
        from unittest.mock import Mock

        sha = "a" * 40
        ssh = Mock()
        ssh.run.return_value = f"/opt/omnicio/releases/{sha}\n"
        with self.assertRaisesRegex(MODULE.InfraError, "already active"):
            MODULE.upload_release(ssh, archive_b64="test-only", release_sha=sha)
        ssh.run.assert_called_once_with(
            "readlink -f /opt/omnicio/current 2>/dev/null || true",
        )

        ssh.reset_mock()
        with self.assertRaisesRegex(MODULE.InfraError, "40-character SHA"):
            MODULE.upload_release(ssh, archive_b64="test-only", release_sha="../current")
        ssh.run.assert_not_called()

    def test_release_upload_rechecks_active_target_before_destructive_steps(self) -> None:
        ssh = FakeSsh(True)
        MODULE.upload_release(ssh, archive_b64="test-only", release_sha="b" * 40)
        locked_command = ssh.commands[-1]
        self.assertTrue(locked_command.startswith(f"flock -w 855 {MODULE.DEPLOY_LOCK} "))
        command = shlex.split(locked_command)[-1]
        self.assertTrue(command.startswith("set -euo pipefail; "))
        self.assertLess(command.index("readlink -f"), command.index("rm -rf"))
        self.assertIn("--no-same-owner --no-same-permissions", command)
        self.assertIn(f"chmod 0644 /opt/omnicio/releases/{'b' * 40}/pyproject.toml", command)
        self.assertIn(f"rm -f /run/omnicio-auth-deploy-{'b' * 40}.state ", command)
        self.assertLess(command.index("chmod 0644"), command.index("rm -f /run/"))

    def test_only_successful_upload_clears_a_previous_attempts_rollback_state(self) -> None:
        sha = "b" * 40
        ssh = FakeSsh(True)
        MODULE.upload_release(ssh, archive_b64="test-only", release_sha=sha)
        command = shlex.split(ssh.commands[-1])[-1]
        body = b'[project]\nname="omnicio-gateway"\nversion="1.4.0"\n'
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            entry = tarfile.TarInfo("pyproject.toml")
            entry.size = len(body)
            archive.addfile(entry, io.BytesIO(body))
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        if os.name == "nt":
            bash = str(pathlib.Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
                       / "Git" / "bin" / "bash.exe")
        else:
            bash = "/bin/bash"
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory).resolve()
            run = root / "run"
            run.mkdir()
            state = run / f"omnicio-auth-deploy-{sha}.state"
            marker = run / f"omnicio-auth-deploy-{sha}.rollback-blocked"
            state.write_text("previous-attempt-state\n", encoding="utf-8")
            marker.write_text("previous-attempt-marker\n", encoding="utf-8")
            command = command.replace("/opt/omnicio", (root / "app").as_posix())
            command = command.replace("/run/omnicio-auth-deploy", (run / "omnicio-auth-deploy")
                                      .as_posix())
            failed = subprocess.run(
                [bash, "-c", command], input="not-an-archive", text=True,
                capture_output=True, timeout=10,
            )
            self.assertNotEqual(failed.returncode, 0)
            self.assertEqual(state.read_text(encoding="utf-8"), "previous-attempt-state\n")
            self.assertEqual(marker.read_text(encoding="utf-8"), "previous-attempt-marker\n")
            completed = subprocess.run(
                [bash, "-c", command], input=encoded, text=True,
                capture_output=True, timeout=10,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertFalse(state.exists())
            self.assertFalse(marker.exists())
            self.assertEqual(
                (root / "app" / "releases" / sha / "pyproject.toml").read_bytes(), body,
            )

    def test_rollback_reports_blocked_contract_and_unconfirmed_shutdown_separately(self) -> None:
        from unittest.mock import Mock

        for code, expected in ((45, "Auth and observer were stopped"),
                               (46, "shutdown could not be confirmed"),
                               (47, "application rollback was not confirmed")):
            with self.subTest(code=code):
                ssh = Mock()
                ssh.run.side_effect = MODULE.InfraError(
                    f"Remote command failed (remote_command, exit_code={code})",
                )
                with patch.object(MODULE, "add_summary") as summary:
                    MODULE.rollback_remote(ssh, release_sha="a" * 40)
                message = summary.call_args.args[0]
                self.assertIn(expected, message)
                if code == 46:
                    self.assertNotIn("were stopped", message)

    def test_deploy_and_rollback_share_a_lock_and_finish_before_ssh_deadline(self) -> None:
        from unittest.mock import Mock

        ssh = Mock()
        sha = "a" * 40
        MODULE.deploy_remote(ssh, release_sha=sha)
        MODULE.rollback_remote(ssh, release_sha=sha)
        deploy, rollback = ssh.run.call_args_list
        self.assertIn(f"flock -n {MODULE.DEPLOY_LOCK} ", deploy.args[0])
        self.assertIn(f"flock -w 855 {MODULE.DEPLOY_LOCK} ", rollback.args[0])
        budgets = []
        for call in (deploy, rollback):
            command = shlex.split(call.args[0])
            position = command.index("timeout")
            grace, duration = command[position + 1:position + 3]
            self.assertRegex(grace, r"^--kill-after=[0-9]+s$")
            self.assertRegex(duration, r"^[0-9]+s$")
            grace_seconds = int(grace.removeprefix("--kill-after=")[:-1])
            operation_seconds = int(duration[:-1])
            lock_seconds = 0 if command[1] == "-n" else int(command[2])
            self.assertGreater(call.kwargs["timeout"],
                               lock_seconds + operation_seconds + grace_seconds)
            self.assertNotIn("--foreground", command)
            budgets.append(operation_seconds)
        self.assertEqual(budgets, [840, 180])
        self.assertEqual(rollback.kwargs["timeout"], 1080)
        script = MODULE.REMOTE_DEPLOY_SCRIPT
        auth = script.split('cat > "$SERVICE.new"', 1)[1].split("\nEOF\n", 1)[0]
        observer = script.split('cat > "$OBSERVER_SERVICE.new"', 1)[1].split("\nEOF\n", 1)[0]
        auth_stop = int(re.search(r"^TimeoutStopSec=([0-9]+)$", auth, flags=re.M)[1])
        auth_start = int(re.search(r"^TimeoutStartSec=([0-9]+)$", auth, flags=re.M)[1])
        observer_stop = int(re.search(r"^TimeoutStopSec=([0-9]+)$", observer, flags=re.M)[1])
        # Incompatible rollback stops both units; compatible rollback restarts auth.
        self.assertGreater(budgets[1], max(auth_stop + observer_stop, auth_stop + auth_start))
        # Restoring the timer does not wait for the observer's long-running work.
        self.assertNotRegex(MODULE.REMOTE_ROLLBACK_SCRIPT.replace("\\\n", " "),
                            r"systemctl\s+(?:start|restart)\s+[^\n]*omnicio-observer\.service\b")
        self.assertEqual(
            deploy.kwargs["input_text"],
            MODULE.REMOTE_DEPLOY_SCRIPT.replace(
                "__OMNICIO_PUBLIC_BUILD__", sha[:12],
            ).replace("__OMNICIO_PUBLIC_RELEASE__", sha),
        )
        self.assertNotIn("__OMNICIO_PUBLIC_BUILD__", deploy.kwargs["input_text"])
        self.assertIn(f'add_header X-Omnicio-Build "{sha[:12]}";', deploy.kwargs["input_text"])
        roots = re.findall(r"^\s*root ([^;]+);$", deploy.kwargs["input_text"], flags=re.M)
        self.assertTrue(roots)
        self.assertEqual(set(roots), {f"/var/www/omnicio.ru/releases/{sha}"})
        self.assertNotIn("__OMNICIO_PUBLIC_RELEASE__", deploy.kwargs["input_text"])
        self.assertEqual(rollback.kwargs["input_text"], MODULE.REMOTE_ROLLBACK_SCRIPT)

    def test_deploy_and_rollback_reject_non_commit_arguments_before_ssh(self) -> None:
        from unittest.mock import Mock

        ssh = Mock()
        for action in (MODULE.deploy_remote, MODULE.rollback_remote):
            for sha in ("../current", "a" * 39, "A" * 40, "a" * 40 + "; true"):
                with self.subTest(action=action.__name__, sha=sha), self.assertRaisesRegex(
                    MODULE.InfraError, "40-character SHA",
                ):
                    action(ssh, release_sha=sha)
        ssh.run.assert_not_called()

    def test_existing_legacy_brand_links_can_be_republished(self) -> None:
        if os.name == "nt":
            bash = str(pathlib.Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
                       / "Git" / "bin" / "bash.exe")
        else:
            bash = "/bin/bash"
        script = MODULE.REMOTE_DEPLOY_SCRIPT
        start = script.index("for name in apple-touch-icon-180.png")
        loop = script[start:script.index("\ndone", start) + len("\ndone")]
        with tempfile.TemporaryDirectory() as directory:
            brand = pathlib.Path(directory) / "assets" / "brand"
            brand.mkdir(parents=True)
            (brand / "omnicio-logo.png").write_bytes(b"test-only-brand")
            for _ in range(2):
                subprocess.run(
                    [bash, "-c", 'set -e; WEB_RELEASE=.; ' + loop],
                    cwd=directory, check=True, capture_output=True, timeout=10,
                )
            for name in (
                "apple-touch-icon-180.png", "pwa-icon-192.png", "pwa-icon-512.png",
                "pwa-maskable-512.png",
            ):
                self.assertEqual((brand / name).read_bytes(), b"test-only-brand")

    def test_runtime_gate_requires_remote_environment(self) -> None:
        ready = FakeSsh(True)
        missing = FakeSsh(False)

        self.assertTrue(MODULE.runtime_is_ready(ready))
        self.assertFalse(MODULE.runtime_is_ready(missing))
        self.assertIn("BROKER_TOKEN_CRYPTO_KEY", ready.commands[0])
        self.assertIn("CLIENT_IP_KEY", ready.commands[0])
        self.assertIn("command -v psql", ready.commands[0])
        self.assertIn("email_identities", ready.inputs[0])
        self.assertIn("column_name = 'role'", ready.inputs[0])

    def test_runtime_gate_matches_application_database_readiness(self) -> None:
        source = SCRIPT_DIR.parent.parent / "src/omnicio"
        tree = ast.parse((source / "schema.py").read_text(encoding="utf-8"))
        query = next(ast.literal_eval(node.value) for node in tree.body
                     if isinstance(node, ast.Assign)
                     and any(isinstance(target, ast.Name) and target.id == "READINESS_QUERY"
                             for target in node.targets))
        database_source = (source / "db.py").read_text(encoding="utf-8")
        self.assertIn("from .schema import READINESS_QUERY", database_source)
        self.assertIn("cur.execute(READINESS_QUERY)", database_source)
        predicate = query.strip().removeprefix("SELECT").removesuffix("AS ready")
        expected = f"SELECT CASE WHEN {predicate} THEN 'ready' ELSE 'missing' END"
        ssh = FakeSsh(True)
        self.assertTrue(MODULE.runtime_is_ready(ssh))
        actual = ssh.inputs[0]
        self.assertIsInstance(actual, str)
        self.assertEqual(" ".join(actual.split()), " ".join(expected.split()))
        self.assertIn("column_name = 'next_assessment_at'", actual)
        self.assertIn("c.relforcerowsecurity", actual)
        self.assertIn("$argon2id$%", actual)
        self.assertIn("$check$", actual)
        self.assertIn("-v ON_ERROR_STOP=1 -Atqf -", ssh.commands[0])
        self.assertNotIn("$argon2id$", ssh.commands[0])
        self.assertLess(len(ssh.commands[0]), 4096)

    def test_missing_runtime_schema_does_not_activate_or_rollback_release(self) -> None:
        from contextlib import ExitStack
        from unittest.mock import MagicMock

        client = MagicMock()
        client.get_vpc_services.return_value = [{"name": "database"}]
        monitored = (
            "validate_product_environment", "validate_legal_documents",
            "find_managed_server", "find_vpc", "public_ipv4", "build_release_archive",
            "EphemeralSsh", "preflight_product_environment", "upload_release",
            "write_product_environment", "deploy_remote", "rollback_remote",
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
                "preflight_product_environment", "upload_release", "write_product_environment",
                "deploy_remote", "rollback_remote", "commit_product_environment",
            ):
                mocks[name].assert_not_called()


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
        os.environ.update({
            "LEGAL_OPERATOR_NAME": "Test Operator", "LEGAL_OPERATOR_EMAIL": "operator@example.com",
            "LEGAL_PRIVACY_VERSION": "2026-10-11-v1.5.0",
            "LEGAL_CONSENT_VERSION": "2026-10-11-v1.5.0",
            "LEGAL_TERMS_VERSION": "2026-10-11-v1.5.0",
            "AUTH_SMTP_HOST": "smtp.example.org", "AUTH_SMTP_SENDER": "auth@example.org",
            "AUTH_SMTP_MODE": "tls", "AUTH_SMTP_PORT": "465",
        })

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


    def test_public_registration_requires_operator_identity(self) -> None:
        old = dict(os.environ)
        try:
            self._base_registration_environment()
            os.environ["LEGAL_OPERATOR_EMAIL"] = "not-an-email"
            with self.assertRaises(MODULE.InfraError):
                MODULE.validate_product_environment()
        finally:
            os.environ.clear()
            os.environ.update(old)

    def test_product_environment_builds_public_email_registration_without_user_cap(self) -> None:
        old = dict(os.environ)
        try:
            self._base_registration_environment()
            MODULE.validate_product_environment()
            product_env = MODULE.build_product_environment()
        finally:
            os.environ.clear()
            os.environ.update(old)

        self.assertIn('AUTH_SMTP_HOST="smtp.example.org"', product_env)
        self.assertIn('AUTH_SMTP_MODE="tls"', product_env)
        self.assertIn('MARKET_DATA_DISTRIBUTION_APPROVED="false"', product_env)
        for removed in ("VKID", "TID_", "REGISTRATION_", "PORTFOLIO_LIVE", "LEGACY_PROFILE"):
            self.assertNotIn(removed, product_env)
        self.assertIn('LEGAL_OPERATOR_EMAIL="operator@example.com"', product_env)
        self.assertIn(
            'OMNICIO_RECOVERY_STATUS_PATH="/var/lib/omnicio-recovery/status.json"', product_env,
        )
        self.assertNotIn("OWNER_VK_ID", product_env)


    def test_mail_and_market_configuration_is_validated_without_provider_id_gates(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self._base_registration_environment()
            MODULE.validate_product_environment()
            for name, value in (
                ("AUTH_SMTP_PORT", "0"), ("AUTH_SMTP_PORT", "65536"),
                ("AUTH_SMTP_PORT", "abc"), ("AUTH_SMTP_MODE", "plain"),
                ("AUTH_SMTP_HOST", "https://smtp.example.org"),
                ("MARKET_DATA_DISTRIBUTION_APPROVED", "yes"),
            ):
                with (
                    self.subTest(name=name, value=value),
                    patch.dict(os.environ, {name: value}),
                    self.assertRaises(MODULE.InfraError),
                ):
                    MODULE.validate_product_environment()
            with patch.dict(os.environ, {"AUTH_SMTP_HOST": "", "AUTH_SMTP_SENDER": ""}):
                # The deployment may preserve already configured server mail credentials.
                # The public configuration check still blocks an unconfigured deployment.
                MODULE.validate_product_environment()

    def test_market_publication_authority_cannot_inherit_an_old_true_flag(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertIn('MARKET_DATA_DISTRIBUTION_APPROVED="false"',
                          MODULE.build_product_environment())
        with patch.dict(os.environ, {"MARKET_DATA_DISTRIBUTION_APPROVED": "true"}, clear=True):
            self.assertIn('MARKET_DATA_DISTRIBUTION_APPROVED="true"',
                          MODULE.build_product_environment())
        self.assertNotIn("MARKET_DATA_DISTRIBUTION_APPROVED", MODULE.OPTIONAL_INTEGRATION_KEYS)

    def test_deployment_preserves_users_and_only_configures_current_identity_providers(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        workflow = (SCRIPT_DIR.parent / "workflows" / "auth-app-deploy.yml").read_text(
            encoding="utf-8",
        )
        self.assertNotIn("retire_legacy_profile", source)
        self.assertNotIn("DELETE FROM users", source)
        for key in ("TID_CLIENT_ID", "LEGACY_PROFILE_RESET_ENABLED",
                    "REGISTRATION_MAX_USERS", "CONTROLLED_LIVE_TEST_MODE",
                    "PORTFOLIO_LIVE_EXECUTION_ENABLED"):
            self.assertNotIn(key, source)
            self.assertNotIn(key, workflow)
        for key in ("AUTH_SMTP_HOST", "AUTH_SMTP_PASSWORD", "MARKET_DATA_TOKEN",
                    "MARKET_DATA_DISTRIBUTION_APPROVED"):
            self.assertIn(key, workflow)

    def test_legal_templates_require_operator_placeholders(self) -> None:
        versions = {
            f"LEGAL_{name}_VERSION": "2026-10-11-v1.5.0"
            for name in ("PRIVACY", "CONSENT", "TERMS")
        }
        with patch.dict(os.environ, versions):
            MODULE.validate_legal_documents(SCRIPT_DIR.parent.parent)

    def test_legal_templates_reject_stale_or_missing_deployment_version(self) -> None:
        for value in ("2026-10-06-v1.0.0", ""):
            with (
                self.subTest(value=value),
                patch.dict(os.environ, {"LEGAL_PRIVACY_VERSION": value}),
                self.assertRaisesRegex(MODULE.InfraError, "Legal document version"),
            ):
                MODULE.validate_legal_documents(SCRIPT_DIR.parent.parent)


    def test_auth_deploy_workflow_separates_pr_and_production_concurrency(self) -> None:
        workflow = (
            SCRIPT_DIR.parent / "workflows" / "auth-app-deploy.yml"
        ).read_text(encoding="utf-8")
        concurrency = workflow.split("\nconcurrency:\n", 1)[1].split("\njobs:\n", 1)[0]
        group = re.search(r"^  group: (.*?)\$\{\{\s*(.*?)\s*\}\}(.*?)$", concurrency, re.M)
        cancel = re.search(r"^  cancel-in-progress: \$\{\{\s*(.*?)\s*\}\}$", concurrency, re.M)
        self.assertIsNotNone(group)
        self.assertIsNotNone(cancel)
        self.assertNotIn("queue:", concurrency, "PR cancellation cannot use a bounded queue")

        scenarios = (
            ("first PR run", "pull_request", 765, 1001),
            ("newer same PR", "pull_request", 765, 1002),
            ("different PR", "pull_request", 766, 1003),
            ("main push", "push", None, 2001),
            ("manual release", "workflow_dispatch", None, 2002),
            ("later main push", "push", None, 2003),
            ("later manual release", "workflow_dispatch", None, 2004),
        )
        contexts = [
            {"event_name": event, "run_id": run_id, "sha": "a" * 40,
             "event": {"pull_request": {"number": pr}}}
            for _, event, pr, run_id in scenarios
        ]
        # Evaluate the actual workflow expressions using their shared string,
        # truthiness and boolean semantics in Node, already required by this job.
        node = shutil.which("node")
        self.assertIsNotNone(node, "Node is required by the application workflow")
        source = (
            "const contexts = " + json.dumps(contexts) + ";\n"
            "const results = contexts.map(github => [\n"
            f"  {json.dumps(group[1])} + String({group[2]}) + {json.dumps(group[3])},\n"
            f"  Boolean({cancel[1]})\n"
            "]);\nprocess.stdout.write(JSON.stringify(results));\n"
        )
        result = subprocess.run([node, "-"], input=source, text=True,
                                capture_output=True, check=True, timeout=10)
        actual = json.loads(result.stdout)
        self.assertEqual(actual[0], actual[1], "New commits of one PR share their queue")
        self.assertEqual(len({item[0] for item in actual}), len(scenarios) - 1,
                         "Different PRs and every non-PR run need independent queues")
        for (name, event, _, _), (_, cancels) in zip(scenarios, actual, strict=True):
            with self.subTest(event=name):
                self.assertEqual(cancels, event == "pull_request")

        tests, deploy = workflow.split("\n  tests:\n", 1)[1].split("\n  deploy:\n", 1)
        self.assertNotIn("omnicio-production-ssh", tests, "Validation cannot occupy the SSH lock")
        self.assertEqual(
            deploy.split("    concurrency:\n", 1)[1].split("    if:", 1)[0],
            "      group: omnicio-production-ssh\n"
            "      cancel-in-progress: false\n"
            "      queue: max\n",
        )
        self.assertIn("    needs: tests\n", deploy)
        self.assertLess(deploy.index("name: Verify current main release checks"),
                        deploy.index("name: Validate Timeweb secret"))

    def test_product_environment_is_backed_up_for_rollback(self) -> None:
        old = dict(os.environ)
        try:
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
        with patch.dict(os.environ, {}, clear=True):
            self.assertIn('OPERATOR_USER_ID=""\n', MODULE.build_product_environment())
            ssh = FakeSsh(True)
            MODULE.write_product_environment(ssh, release_sha="b" * 40)
        tokens = shlex.split(ssh.commands[0])
        program = tokens[tokens.index("-c") + 1]
        with tempfile.TemporaryDirectory() as directory:
            old = pathlib.Path(directory) / "previous.env"
            new = pathlib.Path(directory) / "candidate.env"
            old.write_text(
                'OPERATOR_USER_ID="00000000-0000-0000-0000-0000000001f5"\n'
                'AUTH_SMTP_HOST="existing-app"\n'
                'AUTH_SMTP_PASSWORD="test-only-value"\n'
                'AUTH_SMTP_MODE="tls"\n'
                'ASSISTANT_ENABLED="true"\n'
                'VKID_APP_ID="123456"\n'
                'UNRELATED_KEY="must-not-migrate"\n',
                encoding="utf-8",
            )
            new.write_text(
                'OPERATOR_USER_ID=""\n'
                'AUTH_SMTP_HOST="replacement-app"\n'
                'ASSISTANT_ENABLED="false"\n'
                'MARKET_DATA_DISTRIBUTION_APPROVED="false"\n',
                encoding="utf-8",
            )
            subprocess.run(
                [sys.executable, "-c", program, str(new), str(old)],
                check=True, timeout=5,
            )
            result = new.read_text(encoding="utf-8").splitlines()
        self.assertEqual(result, [
            'OPERATOR_USER_ID=""',
            'AUTH_SMTP_HOST="replacement-app"',
            'ASSISTANT_ENABLED="false"',
            'MARKET_DATA_DISTRIBUTION_APPROVED="false"',
            'AUTH_SMTP_PASSWORD="test-only-value"',
            'AUTH_SMTP_MODE="tls"', 'VKID_APP_ID="123456"',
        ])

    def test_optional_passwords_preserve_exact_bytes_and_config_values_are_trimmed(self) -> None:
        secret = "  test-only-secret-with-outer-spaces  "
        with patch.dict(os.environ, {
            "AUTH_SMTP_PASSWORD": secret,
            "MARKET_DATA_TOKEN": secret,
            "NOTIFICATION_SMTP_PASSWORD": secret,
            "BILLING_PASSWORD": secret,
            "OMNICIO_RESTORE_RECEIPT_KEY": secret,
            "NOTIFICATION_SMTP_HOST": " smtp.example.test ",
        }, clear=True):
            result = MODULE.build_product_environment()
        for key in (
            "NOTIFICATION_SMTP_PASSWORD", "BILLING_PASSWORD", "OMNICIO_RESTORE_RECEIPT_KEY",
            "AUTH_SMTP_PASSWORD", "MARKET_DATA_TOKEN",
        ):
            self.assertIn(f'{key}="{secret}"\n', result)
        self.assertIn('NOTIFICATION_SMTP_HOST="smtp.example.test"\n', result)

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
        self.assertIn("zone=omnicio_api:10m rate=120r/m", script)
        self.assertIn("limit_conn_zone $binary_remote_addr zone=omnicio_conn:10m", script)
        self.assertIn("location ^~ /api/auth/email/", script)
        self.assertIn("client_max_body_size 4k", script)
        self.assertNotIn("location = /api/auth/vkid", script)
        self.assertNotIn("location = /api/auth/tid", script)
        self.assertIn("limit_req zone=omnicio_api burst=60 nodelay", script)
        self.assertGreaterEqual(script.count("client_max_body_size 16k;"), 2)
        self.assertGreaterEqual(script.count("client_body_timeout 10s;"), 2)
        self.assertGreaterEqual(script.count("client_header_timeout 10s;"), 2)
        self.assertGreaterEqual(script.count("limit_conn omnicio_conn 32;"), 2)
        self.assertIn("limit_conn_status 429", script)
        self.assertIn("limit_req_status 429", script)

    def test_nginx_effective_security_headers_survive_location_overrides_and_errors(self) -> None:
        script = MODULE.REMOTE_DEPLOY_SCRIPT
        nginx = script.split('cat > "$NGINX_SITE.new" <<\'EOF\'\n', 1)[1].split(
            "\nEOF", 1,
        )[0]
        https = nginx.split("    listen 443 ssl;", 1)[1]
        expected = {
            "Strict-Transport-Security": ("max-age=31536000", True),
            "X-Content-Type-Options": ("nosniff", True),
            "Referrer-Policy": ("$omnicio_referrer_policy", True),
            "Permissions-Policy": ("camera=(), microphone=(), geolocation=()", True),
            "Content-Security-Policy": (
                "default-src 'self'; connect-src 'self'; img-src 'self' data:; "
                "style-src 'self'; script-src 'self'; base-uri 'none'; "
                "frame-ancestors 'none'; form-action 'self'", True,
            ),
        }

        def headers(scope: str) -> dict[str, tuple[str, bool]]:
            result = {}
            for line in re.findall(r"^\s*add_header .+;$", scope, flags=re.M):
                tokens = shlex.split(line.strip().removesuffix(";"))
                self.assertIn(len(tokens), (3, 4))
                self.assertNotIn(tokens[1], result)
                result[tokens[1]] = (tokens[2], tokens[3:] == ["always"])
            return result

        server_headers = headers(https.split("    location ", 1)[0])
        self.assertEqual(server_headers, expected)
        locations = dict(re.findall(
            r"^    location ([^\n]+) \{\n(.*?)^    \}", https, flags=re.M | re.S,
        ))
        self.assertEqual(len(locations), len(re.findall(r"^    location ", https, re.M)))
        self.assertTrue({
            "/", "/api/", "/health/", "/assets/", "= /assets/app.css",
            "= /assets/tokens.css",
            "= /assets/app.js",
            "= /sw.js", "= /offline.html", "= /manifest.webmanifest", "= /version.js",
        }.issubset(locations))
        for location, scope in locations.items():
            with self.subTest(location=location):
                # Nginx inherits only when this location defines no add_header at all.
                # Requiring always also covers rate-limit and other 4xx/5xx responses.
                effective = headers(scope) or server_headers
                self.assertEqual(
                    {name: effective.get(name) for name in expected}, expected,
                )
                if location == "/assets/":
                    self.assertEqual(effective["Cache-Control"], ("public, max-age=86400", False))
                elif "Cache-Control" in effective:
                    self.assertEqual(effective["Cache-Control"], ("no-cache", False))
                if "Cache-Control" in effective:
                    self.assertEqual(
                        effective["X-Omnicio-Build"], ("__OMNICIO_PUBLIC_BUILD__", False),
                    )
        self.assertEqual(headers(locations["= /sw.js"])["Service-Worker-Allowed"], ("/", False))
        self.assertNotIn("__OMNICIO_SERVER_SECURITY_HEADERS__", script)
        self.assertNotIn("__OMNICIO_LOCATION_SECURITY_HEADERS__", script)
        self.assertNotIn("__OMNICIO_DEFAULT_REFERRER_POLICY__", script)
        self.assertNotIn("add_header_inherit", nginx)
        self.assertNotIn("nginx-security-headers.conf", script)

    def test_nginx_preserves_stricter_upstream_policy_and_emits_one_referrer_header(self) -> None:
        nginx = MODULE.REMOTE_DEPLOY_SCRIPT.split(
            'cat > "$NGINX_SITE.new" <<\'EOF\'\n', 1,
        )[1].split("\nEOF", 1)[0]
        http = nginx.split("server {", 1)[0]
        mapping = re.search(
            r"map \$upstream_http_referrer_policy \$omnicio_referrer_policy \{\n(.*?)\n\}",
            http, flags=re.S,
        )
        self.assertIsNotNone(mapping)
        entries = dict(shlex.split(line.strip().removesuffix(";"))
                       for line in mapping[1].splitlines())
        self.assertEqual(entries, {
            "default": "strict-origin-when-cross-origin", "no-referrer": "no-referrer",
        })
        https = nginx.split("    listen 443 ssl;", 1)[1]
        server = https.split("    location ", 1)[0]
        server_hidden = re.findall(r"proxy_hide_header ([^;]+);", server)
        self.assertEqual(server_hidden, ["Referrer-Policy"])
        self.assertNotRegex(https, r"(?i)proxy_pass_header\s+Referrer-Policy\s*;")
        locations = dict(re.findall(
            r"^    location ([^\n]+) \{\n(.*?)^    \}", https, flags=re.M | re.S,
        ))
        for location, scope in locations.items():
            local_hidden = re.findall(r"proxy_hide_header ([^;]+);", scope)
            hidden = local_hidden or server_hidden
            additions = re.findall(r'^\s*add_header Referrer-Policy "([^\"]+)" always;',
                                   scope, flags=re.M)
            if not re.search(r"^\s*add_header ", scope, flags=re.M):
                additions = re.findall(
                    r'^\s*add_header Referrer-Policy "([^\"]+)" always;', server, flags=re.M,
                )
            for upstream, expected in (
                ([], "strict-origin-when-cross-origin"),
                (["no-referrer"], "no-referrer"),
                (["unsafe-url"], "strict-origin-when-cross-origin"),
                (["no-referrer", "unsafe-url"], "strict-origin-when-cross-origin"),
            ):
                with self.subTest(location=location, upstream=upstream):
                    # Apply proxy response filtering before add_header; duplicates are unsafe.
                    output = [] if "Referrer-Policy" in hidden else list(upstream)
                    mapped = entries.get(", ".join(upstream).lower(), entries["default"])
                    output.extend(mapped if value == "$omnicio_referrer_policy" else value
                                  for value in additions)
                    self.assertEqual(output, [expected])

    def test_remote_service_is_loopback_only_and_resource_bounded(self) -> None:
        from uvicorn.main import main as uvicorn_command

        script = MODULE.REMOTE_DEPLOY_SCRIPT
        service = script.split('cat > "$SERVICE.new"', 1)[1].split("\nEOF\n", 1)[0]
        starts = re.findall(r"^ExecStart=(.+)$", service.replace("\\\n", " "), flags=re.M)
        self.assertEqual(len(starts), 1)
        command = shlex.split(starts[0])
        self.assertEqual(command[0], "/opt/omnicio/current/.venv/bin/uvicorn")
        # Parse the rendered command through the pinned CLI without starting a server.
        with uvicorn_command.make_context("uvicorn", command[1:]) as context:
            expected = {
                "app": "omnicio.main:app", "host": "127.0.0.1", "port": 8001,
                "workers": 1, "limit_concurrency": 64, "backlog": 128,
                "timeout_keep_alive": 5, "timeout_graceful_shutdown": 30,
                "proxy_headers": True, "forwarded_allow_ips": "127.0.0.1",
            }
            for name, value in expected.items():
                with self.subTest(option=name):
                    self.assertEqual(context.params[name], value)
                    if name != "app":
                        option = "--" + name.replace("_", "-")
                        self.assertEqual(sum(arg.split("=", 1)[0] == option for arg in command), 1)
        # HTTP drain does not bound lifespan cleanup. The simple unit's own deadline
        # terminates its entire process group if cleanup or database I/O remains stuck.
        for name, value in {
            "Type": "simple", "User": "omnicio", "Group": "omnicio",
            "TimeoutStopSec": "90", "KillMode": "control-group", "SendSIGKILL": "yes",
            "NoNewPrivileges": "true",
        }.items():
            with self.subTest(setting=name):
                self.assertEqual(re.findall(rf"^{name}=(.*)$", service, flags=re.M), [value])
        self.assertNotRegex(service, r"(?m)^ExecStop(?:Post)?=")
        self.assertEqual(re.findall(r"^EnvironmentFile=(.*)$", service, flags=re.M), [
            "/etc/omnicio/runtime.env", "/etc/omnicio/product.env",
        ])
        self.assertIn("proxy_pass http://127.0.0.1:8001", script)

    def test_production_app_deploy_requires_explicit_main_dispatch(self) -> None:
        root = SCRIPT_DIR.parent.parent
        app_workflow = (
            root / ".github" / "workflows" / "auth-app-deploy.yml"
        ).read_text(encoding="utf-8")
        postgres_workflow = (
            root / ".github" / "workflows" / "auth-postgres.yml"
        ).read_text(encoding="utf-8")

        self.assertNotIn("workflow_run", app_workflow)
        trigger = app_workflow.split("\npermissions:\n", 1)[0]
        for event in ("  pull_request:\n", "  push:\n", "  workflow_dispatch:\n"):
            self.assertIn(event, trigger)
        deploy_if = app_workflow.split("  deploy:", 1)[1].split(
            "    needs: tests",
            1,
        )[0]
        self.assertNotIn("github.event_name == 'push'", deploy_if)
        self.assertIn("github.event_name == 'workflow_dispatch'", deploy_if)
        self.assertIn("github.ref == 'refs/heads/main'", deploy_if)
        self.assertNotIn("Detect schema-first release", app_workflow)

        for workflow in (app_workflow, postgres_workflow):
            push_trigger = workflow.split("\n  push:\n", 1)[1].split(
                "\n  workflow_dispatch:", 1,
            )[0]
            self.assertEqual(push_trigger.strip(), "branches:\n      - main")
        postgres_pr_trigger = postgres_workflow.split("\n  pull_request:\n", 1)[1].split(
            "\n  push:\n", 1,
        )[0]
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
            self.assertIn(release_path, postgres_pr_trigger)

    def test_workflow_events_preserve_validation_and_only_manual_main_deploys(self) -> None:
        workflow = (SCRIPT_DIR.parent / "workflows/auth-app-deploy.yml").read_text(
            encoding="utf-8",
        )
        tests, deploy = workflow.split("\n  tests:\n", 1)[1].split("\n  deploy:\n", 1)
        expressions = []
        for job in (tests, deploy):
            match = re.search(r"^    if: >-\n((?:      .+\n)+)", job, flags=re.M)
            self.assertIsNotNone(match)
            expressions.append(match[1].strip())
        self.assertNotIn("Require successful PostgreSQL release prerequisite", tests)
        diagnostic_conditions = {
            "Upload public site browser evidence": (
                "always() && steps.checkout.outcome == 'success'"
            ),
            "Report source-specific Sonar": (
                "github.event_name == 'pull_request' && always() "
                "&& steps.checkout.outcome == 'success' && steps.python.outcome == 'success'"
            ),
        }
        for name, condition in diagnostic_conditions.items():
            step = tests.split("      - name: " + name, 1)[1].split("      - name:", 1)[0]
            self.assertIn("        if: " + condition + "\n", step)

        baseline = {
            "event_name": "workflow_dispatch", "repository": "test/omnicio", "sha": "a" * 40,
            "ref": "refs/heads/main",
            "event": {
                "pull_request": {
                    "author_association": "OWNER",
                    "head": {"repo": {"full_name": "test/omnicio"}},
                },
            },
        }
        scenarios = (
            ("manual main release", {}, [True, True]),
            ("upstream completion", {"event_name": "workflow_run"}, [False, False]),
            ("scheduled workflow", {"event_name": "schedule"}, [False, False]),
            ("push validation", {"event_name": "push"}, [True, False]),
            ("owner PR validation", {"event_name": "pull_request"}, [True, False]),
            ("fork PR", {"event_name": "pull_request",
                         "event.pull_request.head.repo.full_name": "fork/omnicio"},
             [False, False]),
            ("nonowner PR", {"event_name": "pull_request",
                             "event.pull_request.author_association": "CONTRIBUTOR"},
             [False, False]),
            ("manual branch validation", {"event_name": "workflow_dispatch",
                                          "ref": "refs/heads/feature"}, [True, False]),
        )
        contexts = []
        for _, changes, _ in scenarios:
            context = copy.deepcopy(baseline)
            for path, value in changes.items():
                parent = context
                *keys, last = path.split(".")
                for key in keys:
                    parent = parent[key]
                parent[last] = value
            contexts.append(context)
        # These conditions use only string equality and boolean operators shared
        # by GitHub expressions and JavaScript. Execute the workflow expressions
        # themselves using Node, already required by this job's browser checks.
        node = shutil.which("node")
        self.assertIsNotNone(node, "Node is required by the application workflow")
        source = (
            "const contexts = " + json.dumps(contexts) + ";\n"
            "const results = contexts.map(github => {\n"
            f"  const tests = Boolean({expressions[0]});\n"
            f"  const deploy = tests && Boolean({expressions[1]});\n"
            "  return [tests, deploy];\n});\n"
            "process.stdout.write(JSON.stringify(results));\n"
        )
        result = subprocess.run([node, "-"], input=source, text=True,
                                capture_output=True, check=True, timeout=10)
        for (name, _, expected), actual in zip(scenarios, json.loads(result.stdout), strict=True):
            with self.subTest(event=name):
                self.assertEqual(actual, expected)

    def test_deploy_completion_requires_confirmed_app_ready(self) -> None:
        workflow = (SCRIPT_DIR.parent / "workflows/auth-app-deploy.yml").read_text(
            encoding="utf-8",
        )
        step = workflow.split("      - name: Confirm application readiness\n", 1)[1]
        step = step.split("      - name:", 1)[0]
        self.assertIsNone(re.search(r"^        if:", step, flags=re.M))
        self.assertIn("AUTH_DEPLOY_STATUS: ${{ steps.app.outputs.status }}", step)
        self.assertIn("          if errorlevel 1 exit /b 1\n", step)
        match = re.search(r'^          "%OMNICIO_PYTHON%" -c "(.+)"$', step, flags=re.M)
        self.assertIsNotNone(match)
        self.assertIn("EXPECTED_DEPLOY_STATUS: ${{ inputs.scope == 'public_site' && "
                      "'public_site_ready' || 'app_ready' }}", step)
        for expected in ("app_ready", "public_site_ready"):
            for status in (None, "", "pending_database", "unknown", "APP_READY",
                           "app_ready\n", "app_ready", "public_site_ready"):
                environment = {**os.environ, "EXPECTED_DEPLOY_STATUS": expected}
                environment.pop("AUTH_DEPLOY_STATUS", None)
                if status is not None:
                    environment["AUTH_DEPLOY_STATUS"] = status
                result = subprocess.run([sys.executable, "-c", match[1]], env=environment,
                                        text=True, capture_output=True, timeout=10)
                with self.subTest(expected=expected, status=status):
                    self.assertEqual(result.returncode, 0 if status == expected else 1)
                    if status != expected:
                        self.assertIn("::error::Application deployment did not reach app_ready",
                                      result.stderr)

    def test_remote_daily_observer_is_read_only_bounded_and_rollback_safe(self) -> None:
        script = MODULE.REMOTE_DEPLOY_SCRIPT
        rollback = MODULE.REMOTE_ROLLBACK_SCRIPT

        self.assertIn("omnicio-observer.service", script)
        self.assertIn("omnicio-observer.timer", script)
        self.assertIn("OnCalendar=*-*-* 06:15:00 Europe/Moscow", script)
        self.assertIn("OnBootSec=2min", script)
        self.assertIn("OnUnitInactiveSec=5min", script)
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

    def test_observer_recovery_timer_cannot_exhaust_its_normal_start_budget(self) -> None:
        script = MODULE.REMOTE_DEPLOY_SCRIPT
        observer = script.split('cat > "$OBSERVER_SERVICE.new"', 1)[1].split("EOF", 2)[1]
        timer = script.split('cat > "$OBSERVER_TIMER.new"', 1)[1].split("EOF", 2)[1]
        interval = int(re.search(r"StartLimitIntervalSec=(\d+)", observer)[1])
        burst = int(re.search(r"StartLimitBurst=(\d+)", observer)[1])
        recovery_seconds = int(re.search(r"OnUnitInactiveSec=(\d+)min", timer)[1]) * 60
        restart_seconds = int(re.search(r"RestartSec=(\d+)", observer)[1])
        # systemd counts successful and timer starts as well as failure restarts.
        # Retain a burst guard, while every bounded recovery attempt lies beyond
        # its counting window even when all preceding runs finish immediately.
        self.assertGreaterEqual(burst, 1)
        self.assertGreater(interval, 0)
        self.assertLess(interval, min(recovery_seconds, restart_seconds))

    def test_research_timeout_is_narrow_and_other_api_requests_remain_bounded(self) -> None:
        script = MODULE.REMOTE_DEPLOY_SCRIPT
        research = script.split("location = /api/profile/strategy/research {", 1)[1]
        research = research.split("}", 1)[0]
        generic = script.split("location /api/ {", 1)[1].split("}", 1)[0]
        self.assertIn("proxy_read_timeout 300s;", research)
        self.assertIn("limit_req zone=omnicio_auth_start burst=5 nodelay;", research)
        self.assertIn("proxy_read_timeout 30s;", generic)
        self.assertEqual(script.count("proxy_read_timeout 300s;"), 1)
        source = (SCRIPT_DIR.parent.parent / "src/omnicio/main.py").read_text(encoding="utf-8")
        self.assertIn(("post", "/api/profile/strategy/research"), declared_http_routes(source))

    def test_evidence_upload_limit_only_applies_to_its_authenticated_endpoint(self) -> None:
        script = MODULE.REMOTE_DEPLOY_SCRIPT
        evidence = script.split("location = /api/research/evidence {", 1)[1].split("}", 1)[0]
        generic = script.split("location /api/ {", 1)[1].split("}", 1)[0]
        self.assertIn("client_max_body_size 17m;", evidence)
        self.assertIn("limit_req zone=omnicio_auth_start burst=5 nodelay;", evidence)
        self.assertIn("proxy_read_timeout 30s;", evidence)
        self.assertIn("proxy_set_header X-Forwarded-Proto $scheme;", evidence)
        self.assertNotIn("client_max_body_size 17m;", generic)
        self.assertEqual(script.count("client_max_body_size 17m;"), 1)
        source = (SCRIPT_DIR.parent.parent / "src/omnicio/main.py").read_text(encoding="utf-8")
        self.assertIn(("put", "/api/research/evidence"), declared_http_routes(source))


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

    def test_legal_pages_publish_versioned_public_registration_terms(self) -> None:
        root = SCRIPT_DIR.parent.parent
        privacy = (root / "web" / "legal" / "privacy.html").read_text(encoding="utf-8")
        consent = (root / "web" / "legal" / "consent.html").read_text(encoding="utf-8")
        terms = (root / "web" / "legal" / "terms.html").read_text(encoding="utf-8")

        for document, version in (
            (privacy, "2026-10-11-v1.5.0"),
            (consent, "2026-10-11-v1.5.0"),
            (terms, "2026-10-11-v1.5.0"),
        ):
            self.assertIn('content="noindex,nofollow"', document)
            self.assertIn(version, document)
            self.assertIn("__OMNICIO_OPERATOR_", document)

        self.assertIn("OMNICIO", privacy)
        self.assertIn("T-Invest", privacy)
        self.assertIn("Argon2id", privacy)
        self.assertIn("READ_ONLY", privacy)
        self.assertNotIn("Текущий временный live-test лимит — два пользовательских аккаунта", terms)
        self.assertIn("gmail.com, mail.ru или xmail.ru", terms)
        self.assertIn("Удаление аккаунта", terms)

    def test_reference_workspace_keeps_required_runtime_contracts(self) -> None:
        root = SCRIPT_DIR.parent.parent
        page = (root / "web" / "index.html").read_text(encoding="utf-8")
        source = (root / "src" / "omnicio" / "main.py").read_text(encoding="utf-8")
        routes = declared_http_routes(source)
        required = {
            ("post", "/api/auth/email/register"), ("post", "/api/auth/email/verify"),
            ("post", "/api/auth/email/login"), ("post", "/api/auth/email/enroll"),
            ("post", "/api/auth/email/password-reset/request"),
            ("post", "/api/auth/email/password-reset/confirm"),
            ("get", "/api/public/market-status"), ("get", "/api/public/market"),
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
        self.assertIn('id="download"', page)
        self.assertNotIn('<form', page)
        self.assertNotIn('type="password"', page)
        for path in MODULE.LEGAL_PAGES:
            self.assertIn(path, page)

    def test_reference_assets_are_shipped_without_legacy_brand(self) -> None:
        root = SCRIPT_DIR.parent.parent
        self.assertEqual(
            hashlib.sha256((root / MODULE.BRAND_SOURCE).read_bytes()).hexdigest(),
            "d9c44905a77858882d99e948a647705afa853fd11cfd01efd37528645b8ca12f",
        )
        encoded = MODULE.build_release_archive(root)
        with tarfile.open(fileobj=io.BytesIO(base64.b64decode(encoded)), mode="r:gz") as archive:
            shipped = set(archive.getnames())
        for asset in MODULE.BRAND_RUNTIME_FILES:
            self.assertIn(asset, shipped)
        self.assertFalse(any("omni-sentinel" in name for name in shipped))
        manifest = json.loads((root / "web" / "manifest.webmanifest").read_text(
            encoding="utf-8",
        ))
        self.assertEqual(manifest["name"], "OMNICIO — о приложении")
        for icon in manifest["icons"]:
            name = icon["src"].rsplit("/", 1)[-1]
            self.assertEqual(name, "omnicio-logo.png")
            self.assertTrue((root / MODULE.BRAND_SOURCE).is_file())

    def test_release_archive_rejects_an_oversized_runtime_asset(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            asset = root / "large.png"
            asset.write_bytes(os.urandom(MODULE.MAX_RELEASE_ARCHIVE_BYTES + 1))
            with (
                patch.object(MODULE, "iter_release_files", return_value=iter([asset])),
                self.assertRaisesRegex(MODULE.InfraError, "archive unexpectedly exceeds"),
            ):
                MODULE.build_release_archive(root)

    def test_personal_dashboard_exposes_release_version(self) -> None:
        root = SCRIPT_DIR.parent.parent
        page = (root / "web" / "index.html").read_text(encoding="utf-8")
        deploy_script = MODULE.REMOTE_DEPLOY_SCRIPT

        self.assertEqual(page.count("data-app-version"), 1)
        self.assertIn("__OMNICIO_VERSION__", page)
        self.assertIn("__OMNICIO_BUILD__", page)
        self.assertIn("/assets/app.css?build=__OMNICIO_BUILD__", page)
        self.assertIn("/assets/app.js?build=__OMNICIO_BUILD__", page)
        self.assertIn('/assets/tokens.css?build=__OMNICIO_BUILD__', page)
        self.assertIn(
            '"$RELEASE/.venv/bin/python" -m omnicio.web_assets '
            '"$RELEASE/web" "$WEB_RELEASE" "$SHA"', deploy_script,
        )
        self.assertNotIn('python3 - "$RELEASE/pyproject.toml"', deploy_script)
        self.assertEqual(MODULE.VERSION_PUBLIC_PATH, "/version.js")

    def test_runtime_assets_cannot_mix_across_frontend_releases(self) -> None:
        script = MODULE.REMOTE_DEPLOY_SCRIPT

        self.assertIn("location = /assets/app.css", script)
        self.assertIn("location = /assets/tokens.css", script)
        self.assertIn("location = /assets/app.js", script)
        self.assertIn("location = /sw.js", script)
        self.assertIn("location = /offline.html", script)
        self.assertIn("location = /version.js", script)
        self.assertIn("location = /manifest.webmanifest", script)
        self.assertGreaterEqual(script.count('add_header Cache-Control "no-cache";'), 5)
        self.assertNotIn('add_header Cache-Control "public, max-age=300";', script)

    def test_public_version_script_accepts_only_the_bounded_release_assignment(self) -> None:
        sha = "b" * 40
        metadata = json.dumps({"version": MODULE.release_version(), "build": sha[:12]})
        assignment = "window.OMNICIO_RELEASE = " + metadata
        for body in (assignment, assignment + ";", " \n" + assignment + ";\n"):
            MODULE.verify_public_version_script(body.encode(), sha)
        invalid = (
            "document.location = " + metadata,
            assignment + "; alert('unexpected');",
            assignment + "; " + assignment,
            "window.OMNICIO_RELEASE = []",
            "window.OMNICIO_RELEASE = {broken}",
            assignment.replace(MODULE.release_version(), "0.0.0-obsolete"),
            assignment.replace(sha[:12], "old-build"),
            assignment + " " * MODULE.MAX_RELEASE_METADATA_BYTES,
        )
        for value in invalid:
            body = value.encode()
            with self.subTest(body=body[:100]), self.assertRaises(MODULE.InfraError):
                MODULE.verify_public_version_script(body, sha)

    def test_rendered_offline_styles_match_the_service_worker_build(self) -> None:
        root = SCRIPT_DIR.parent.parent
        build = "b" * 40
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory)
            subprocess.run([
                sys.executable, "-m", "omnicio.web_assets", str(root / "web"),
                str(output), build,
            ], check=True, capture_output=True, timeout=10)
            offline = (output / "offline.html").read_text(encoding="utf-8")
            worker = (output / "sw.js").read_text(encoding="utf-8")
            self.assertIn(f"/assets/app.css?build={build[:12]}", offline)
            self.assertIn(f"/assets/tokens.css?build={build[:12]}", offline)
            self.assertIn(f'const build = "{build[:12]}"', worker)
            self.assertNotIn("__OMNICIO_BUILD__", offline)
            self.assertNotIn("__OMNICIO_BUILD__", worker)
            for name in ("app.js", "tokens.css", "app.css"):
                script = (output / "assets" / name).read_text(encoding="utf-8")
                self.assertIn(build[:12], script)
                self.assertNotIn("__OMNICIO_BUILD__", script)

    def test_legal_renderer_stamps_styles_without_changing_document_revision(self) -> None:
        root = SCRIPT_DIR.parent.parent
        program = MODULE.REMOTE_DEPLOY_SCRIPT.split(
            'python3 - "$RELEASE/web/legal"', 1,
        )[1].split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
        sha = "c" * 40
        with tempfile.TemporaryDirectory() as directory:
            subprocess.run([
                sys.executable, "-c", program, str(root / "web" / "legal"), directory, sha,
            ], env={**os.environ, "LEGAL_OPERATOR_NAME": "Test <Operator>",
                    "LEGAL_OPERATOR_EMAIL": "operator@example.com"},
                check=True, capture_output=True, timeout=10)
            for name in ("privacy.html", "consent.html", "terms.html"):
                original = (root / "web" / "legal" / name).read_text(encoding="utf-8")
                rendered = (pathlib.Path(directory) / name).read_text(encoding="utf-8")
                self.assertIn("Test &lt;Operator&gt;", rendered)
                self.assertIn(f"/assets/tokens.css?build={sha[:12]}", rendered)
                self.assertNotIn("__OMNICIO_", rendered)
                self.assertEqual(
                    re.findall(r'<p class="legal-meta">([^<]+)</p>', rendered),
                    re.findall(r'<p class="legal-meta">([^<]+)</p>', original),
                )

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
        for name, value in MODULE.PUBLIC_SECURITY_HEADERS.items():
            self.headers[name] = value


class PublicReleaseVerificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sha = "a" * 40
        self.legal_version = "2026-10-11-v1.5.0"
        environment = patch.dict(os.environ, {
            f"LEGAL_{name}_VERSION": self.legal_version
            for name in ("PRIVACY", "CONSENT", "TERMS")
        })
        environment.start()
        self.addCleanup(environment.stop)
        root = " ".join((
            MODULE.SITE_MARKER, MODULE.BRAND_PUBLIC_MARK, MODULE.WEB_MANIFEST_PATH,
            self.sha[:12],
            f'<span data-release-version>{MODULE.release_version()}</span>',
        )).encode()
        config = json.dumps({
            "release": {"version": MODULE.release_version(), "build": self.sha[:12]},
            "mode": "public", "registration_enabled": True,
            "auth_provider": "email", "auth_providers": ["email", "telegram", "vkid"],
            "social_providers": {"telegram": True, "vkid": True},
            "login_enabled": True, "email_enabled": True,
            "registration_available": True, "password_reset_available": True,
            "email_domains": ["gmail.com", "mail.ru", "xmail.ru"],
            "password_min_length": 15, "password_max_length": 128, "email_code_digits": 8,
            "legal_versions": {
                "privacy_policy": self.legal_version,
                "personal_data_consent": self.legal_version,
                "terms": self.legal_version,
            },
        }).encode()
        self.responses = {
            "/": (root, "text/html", 200),
            MODULE.BRAND_PUBLIC_MARK: (
                (SCRIPT_DIR.parent.parent / MODULE.BRAND_SOURCE).read_bytes(), "image/png", 200,
            ),
            MODULE.WEB_MANIFEST_PATH: (b'{"icons": []}', "application/json", 200),
            MODULE.VERSION_PUBLIC_PATH: (
                ('window.OMNICIO_RELEASE = ' + json.dumps({
                    "version": MODULE.release_version(), "build": self.sha[:12],
                }) + ";").encode(),
                "text/javascript", 200,
            ),
            "/api/auth/config": (config, "application/json", 200),
        }
        for path, body, content_type in (
            ("/assets/tokens.css", b"--browser-theme-dark " + self.sha[:12].encode(), "text/css"),
            ("/assets/app.js", b"Public product site " + self.sha[:12].encode(), "text/javascript"),
            ("/assets/app.css", b".site-header " + self.sha[:12].encode(), "text/css"),
            ("/sw.js", b"OMNICIO build " + self.sha[:12].encode(), "text/javascript"),
            (
                "/offline.html",
                b'<html lang="ru">' + self.sha[:12].encode() + b'</html>', "text/html",
            ),
        ):
            self.responses[f"{path}?build={self.sha[:12]}"] = (body, content_type, 200)
        for path, marker in MODULE.LEGAL_PAGES.items():
            self.responses[path] = (
                (f"{marker} Test Operator operator@example.com"
                 f'<p class="legal-meta">OMNICIO · omnicio.ru · версия {self.legal_version}</p>'
                 ).encode(),
                "text/html",
                200,
            )

    def verify(
        self, *, missing_header_path: str | None = None,
        build_header_path: str | None = None, build_headers: tuple[str, ...] = (),
    ) -> set[str]:
        requested: set[str] = set()

        def open_response(request, *, timeout, context):
            prefix = f"https://{MODULE.DOMAIN}"
            self.assertTrue(request.full_url.startswith(prefix + "/"))
            self.assertEqual(timeout, 15)
            self.assertTrue(context.check_hostname)
            self.assertEqual(context.verify_mode, MODULE.ssl.CERT_REQUIRED)
            path = request.full_url.removeprefix(prefix)
            requested.add(path)
            response = PublicResponse(*self.responses[path])
            for value in build_headers if path == build_header_path else (self.sha[:12],):
                response.headers["X-Omnicio-Build"] = value
            if path == missing_header_path:
                del response.headers["Content-Security-Policy"]
            return response

        with patch.object(MODULE.urllib.request, "urlopen", side_effect=open_response):
            MODULE.verify_public(self.sha)
        return requested

    def test_matching_release_checks_every_public_surface(self) -> None:
        self.assertEqual(self.verify(), set(self.responses))

    def test_security_headers_are_required_on_every_public_surface(self) -> None:
        for path in self.responses:
            with self.subTest(path=path), self.assertRaisesRegex(
                MODULE.InfraError, "security header invalid: Content-Security-Policy",
            ):
                self.verify(missing_header_path=path)

    def test_static_public_assets_reject_missing_stale_or_duplicate_build_headers(self) -> None:
        for path in self.responses:
            if path.startswith("/api/"):
                continue
            for values in ((), ("old-build",), (self.sha[:12], self.sha[:12])):
                with self.subTest(path=path, values=values), self.assertRaisesRegex(
                    MODULE.InfraError, "build header does not match release",
                ):
                    self.verify(build_header_path=path, build_headers=values)

    def test_missing_weakened_or_duplicate_security_headers_reject_public_response(self) -> None:
        context = MODULE.ssl.create_default_context()
        for name, expected in MODULE.PUBLIC_SECURITY_HEADERS.items():
            for values in ([], ["unsafe-test-value"], [expected, expected]):
                response = PublicResponse(b"test", "text/plain")
                del response.headers[name]
                for value in values:
                    response.headers[name] = value
                with (
                    self.subTest(header=name, values=values),
                    patch.object(MODULE.urllib.request, "urlopen", return_value=response),
                    self.assertRaisesRegex(MODULE.InfraError, f"security header invalid: {name}"),
                ):
                    MODULE.fetch_public("/", context)


    def test_public_login_contract_rejects_missing_or_inconsistent_readiness(self) -> None:
        base = json.loads(self.responses["/api/auth/config"][0])
        invalid = (
            {"auth_providers": ["vkid"]}, {"auth_provider": "tid"},
            {"mode": "closed"}, {"registration_enabled": False}, {"registration_max_users": 2},
            {"email_enabled": None}, {"email_enabled": False},
            {"registration_available": False}, {"password_reset_available": False},
            {"login_enabled": False}, {"email_code_digits": 6},
            {"email_domains": ["gmail.com"]}, {"password_min_length": 8},
        )
        for changed in invalid:
            encoded = json.dumps(dict(base, **changed)).encode()
            with self.subTest(changed=changed), self.assertRaises(MODULE.InfraError):
                MODULE.verify_public_config(encoded)

    def test_invalid_public_release_is_rejected(self) -> None:
        cases = [
            ("/", b"wrong site", "text/html", 200),
            ("/", self.responses["/"][0] + b"__OMNICIO_BUILD__", "text/html", 200),
            ("/", self.responses["/"][0] + b"__OMNICIO_THEME_COLOR__", "text/html", 200),
            ("/", self.responses["/"][0], "text/html", 503),
            (MODULE.BRAND_PUBLIC_MARK, b"", "image/png", 200),
            (MODULE.BRAND_PUBLIC_MARK, b"png", "text/html", 200),
            (MODULE.WEB_MANIFEST_PATH, b"[]", "application/json", 200),
            (MODULE.WEB_MANIFEST_PATH, b"invalid", "application/json", 200),
            (MODULE.VERSION_PUBLIC_PATH, b"window.OMNICIO_RELEASE = {}", "text/javascript", 200),
            (
                f"/assets/app.js?build={self.sha[:12]}",
                b"Public product site old", "text/javascript", 200,
            ),
            (
                f"/assets/tokens.css?build={self.sha[:12]}",
                b"--browser-theme-dark old", "text/css", 200,
            ),
            (f"/assets/app.js?build={self.sha[:12]}", b"wrong asset", "text/javascript", 200),
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

    def test_matching_build_with_wrong_public_version_is_rejected(self) -> None:
        for path in ("/", MODULE.VERSION_PUBLIC_PATH, "/api/auth/config"):
            previous = self.responses[path]
            changed = previous[0].replace(MODULE.release_version().encode(), b"0.0.0-obsolete")
            self.assertNotEqual(changed, previous[0])
            with self.subTest(path=path):
                self.responses[path] = (changed, *previous[1:])
                try:
                    with self.assertRaisesRegex(MODULE.InfraError, "version"):
                        self.verify()
                finally:
                    self.responses[path] = previous

    def test_stale_or_ambiguous_public_legal_document_is_rejected(self) -> None:
        for path in MODULE.LEGAL_PAGES:
            original = self.responses[path]
            body = original[0]
            for changed in (
                body.replace(self.legal_version.encode(), b"2026-10-06-v1.0.0"),
                body.replace(self.legal_version.encode(), b""),
                body + body,
            ):
                with self.subTest(path=path, content=changed[:80]):
                    self.responses[path] = (changed, "text/html", 200)
                    try:
                        with self.assertRaisesRegex(MODULE.InfraError, "Legal document version"):
                            self.verify()
                    finally:
                        self.responses[path] = original

    def test_public_api_legal_versions_must_match_the_deployed_documents(self) -> None:
        config = json.loads(self.responses["/api/auth/config"][0])
        current = config["legal_versions"]
        invalid = [None, {}, dict(current, terms="2026-10-06-v1.0.0")]
        for legal_versions in invalid:
            encoded = json.dumps(dict(config, legal_versions=legal_versions)).encode()
            with (
                self.subTest(legal_versions=legal_versions),
                self.assertRaisesRegex(MODULE.InfraError, "Public legal versions"),
            ):
                MODULE.verify_public_config(encoded)

    def test_excessive_public_response_is_rejected(self) -> None:
        self.responses["/"] = (b"x" * (4 * 1024 * 1024 + 1), "text/html", 200)
        with self.assertRaises(MODULE.InfraError):
            self.verify()


if __name__ == "__main__":
    unittest.main()

