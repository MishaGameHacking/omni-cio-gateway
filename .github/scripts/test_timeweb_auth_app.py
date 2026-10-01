#!/usr/bin/env python3
"""Regression tests for the auth application deployer."""

from __future__ import annotations

import base64
import importlib.util
import io
import os
import pathlib
import sys
import tarfile
import tempfile
import unittest

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
        self.assertIn("REGISTRATION_ENABLED=false", ready.commands[0])
        self.assertIn("BROKER_TOKEN_CRYPTO_KEY", ready.commands[0])

    def test_release_archive_contains_only_runtime_project_files(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = pathlib.Path(tempdir)
            (root / "src" / "omnicio").mkdir(parents=True)
            (root / "web").mkdir()
            (root / "tests").mkdir()
            (root / "pyproject.toml").write_text("[project]\nname='x'\n")
            (root / "src" / "omnicio" / "__init__.py").write_text("")
            (root / "web" / "index.html").write_text("<html></html>")
            (root / "tests" / "secret-test.txt").write_text("not shipped")

            encoded = MODULE.build_release_archive(root)
            raw = base64.b64decode(encoded)
            with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
                names = set(archive.getnames())

        self.assertIn("pyproject.toml", names)
        self.assertIn("src/omnicio/__init__.py", names)
        self.assertIn("web/index.html", names)
        self.assertNotIn("tests/secret-test.txt", names)

    def test_product_environment_validation_requires_all_runtime_secrets(self) -> None:
        old = dict(os.environ)
        try:
            values = {
                "SMS_PROVIDER_LOGIN": "user@example.test",
                "SMS_PROVIDER_TOKEN": "secret-token",
                "SMS_SENDER": "SMS Aero",
                "SMS_TEST_NUMBER": "+79161234567",
                "OWNER_PHONE": "+79161234567",
                "LEGAL_OPERATOR_NAME": "Test Operator",
                "LEGAL_OPERATOR_ADDRESS": "Test Address",
                "LEGAL_PRIVACY_CONTACT": "privacy@example.test",
            }
            os.environ.update(values)
            MODULE.validate_product_environment()
            os.environ.pop("LEGAL_OPERATOR_ADDRESS")
            with self.assertRaises(MODULE.InfraError):
                MODULE.validate_product_environment()
        finally:
            os.environ.clear()
            os.environ.update(old)

    def test_product_environment_keeps_registration_closed_without_sender(self) -> None:
        old = dict(os.environ)
        try:
            os.environ["SMS_PROVIDER_LOGIN"] = "user@example.test"
            os.environ["SMS_PROVIDER_TOKEN"] = "secret-token"
            os.environ.pop("SMS_SENDER", None)
            os.environ["LEGAL_OPERATOR_NAME"] = "Test Operator"
            os.environ["LEGAL_OPERATOR_ADDRESS"] = "Test Address"
            os.environ["LEGAL_PRIVACY_CONTACT"] = "privacy@example.test"
            os.environ["LEGAL_PRIVACY_VERSION"] = "2026-09-30"
            os.environ["LEGAL_CONSENT_VERSION"] = "2026-09-30"
            os.environ["LEGAL_TERMS_VERSION"] = "2026-09-30"

            product_env = MODULE.build_product_environment()
        finally:
            os.environ.clear()
            os.environ.update(old)

        self.assertIn('SMS_PROVIDER="disabled"', product_env)
        self.assertIn('SMS_PROVIDER_LOGIN="user@example.test"', product_env)
        self.assertIn('SMS_PROVIDER_TOKEN="secret-token"', product_env)
        self.assertIn('REGISTRATION_ENABLED="false"', product_env)
        self.assertIn('OWNER_LOGIN_ENABLED="false"', product_env)

    def test_product_environment_enables_provider_only_with_sender(self) -> None:
        old = dict(os.environ)
        try:
            os.environ["SMS_PROVIDER_LOGIN"] = "user@example.test"
            os.environ["SMS_PROVIDER_TOKEN"] = "secret-token"
            os.environ["SMS_SENDER"] = "SMS Aero"
            os.environ["OWNER_PHONE"] = "+79161234567"
            product_env = MODULE.build_product_environment()
        finally:
            os.environ.clear()
            os.environ.update(old)

        self.assertIn('SMS_PROVIDER="smsaero"', product_env)
        self.assertIn('SMS_PROVIDER_LOGIN="user@example.test"', product_env)
        self.assertIn('SMS_SENDER="SMS Aero"', product_env)
        self.assertIn('OWNER_PHONE="+79161234567"', product_env)
        self.assertIn('OWNER_LOGIN_ENABLED="true"', product_env)
        self.assertIn('REGISTRATION_ENABLED="false"', product_env)

    def test_remote_service_is_loopback_only_and_registration_is_gated(self) -> None:
        script = MODULE.REMOTE_DEPLOY_SCRIPT
        self.assertIn("--host 127.0.0.1 --port 8001", script)
        self.assertIn("EnvironmentFile=/etc/omnicio/runtime.env", script)
        self.assertIn("NoNewPrivileges=true", script)
        self.assertIn("proxy_pass http://127.0.0.1:8001", script)

    def test_remote_release_publishes_all_legal_pages(self) -> None:
        script = MODULE.REMOTE_DEPLOY_SCRIPT
        for filename in ("privacy.html", "consent.html", "terms.html"):
            self.assertIn(f'web/legal/{filename}', script)
            self.assertIn(f'legal/{filename}', script)

        self.assertEqual(
            set(MODULE.LEGAL_PAGES),
            {
                "/legal/privacy.html",
                "/legal/consent.html",
                "/legal/terms.html",
            },
        )


if __name__ == "__main__":
    unittest.main()
