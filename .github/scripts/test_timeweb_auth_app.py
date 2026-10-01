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
        self.assertIn("VKID_FLOW_CRYPTO_KEY", ready.commands[0])
        self.assertIn("command -v psql", ready.commands[0])
        self.assertIn("vkid_identities", ready.commands[0])

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
            for relative in MODULE.BRAND_RUNTIME_FILES:
                brand_file = root / relative
                brand_file.parent.mkdir(parents=True, exist_ok=True)
                brand_file.write_bytes(b"brand")

            encoded = MODULE.build_release_archive(root)
            raw = base64.b64decode(encoded)
            with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
                names = set(archive.getnames())

        self.assertIn("pyproject.toml", names)
        self.assertIn("src/omnicio/__init__.py", names)
        self.assertIn("web/index.html", names)
        for relative in MODULE.BRAND_RUNTIME_FILES:
            self.assertIn(relative, names)
        self.assertNotIn("tests/secret-test.txt", names)

    def test_product_environment_requires_legal_versions(self) -> None:
        old = dict(os.environ)
        try:
            os.environ["LEGAL_PRIVACY_VERSION"] = "2026-10-01-v2"
            os.environ["LEGAL_CONSENT_VERSION"] = "2026-10-01-v2"
            os.environ["LEGAL_TERMS_VERSION"] = "2026-10-01-v2"
            os.environ.pop("VKID_APP_ID", None)
            os.environ.pop("OWNER_VK_ID", None)
            MODULE.validate_product_environment()

            os.environ.pop("LEGAL_TERMS_VERSION")
            with self.assertRaises(MODULE.InfraError):
                MODULE.validate_product_environment()
        finally:
            os.environ.clear()
            os.environ.update(old)

    def test_product_environment_fails_on_partial_vkid_config(self) -> None:
        old = dict(os.environ)
        try:
            os.environ["LEGAL_PRIVACY_VERSION"] = "2026-10-01-v2"
            os.environ["LEGAL_CONSENT_VERSION"] = "2026-10-01-v2"
            os.environ["LEGAL_TERMS_VERSION"] = "2026-10-01-v2"
            os.environ["VKID_APP_ID"] = "123456"
            os.environ.pop("OWNER_VK_ID", None)
            with self.assertRaises(MODULE.InfraError):
                MODULE.validate_product_environment()
        finally:
            os.environ.clear()
            os.environ.update(old)

    def test_product_environment_rejects_non_numeric_vkid_config(self) -> None:
        old = dict(os.environ)
        try:
            os.environ["LEGAL_PRIVACY_VERSION"] = "2026-10-01-v2"
            os.environ["LEGAL_CONSENT_VERSION"] = "2026-10-01-v2"
            os.environ["LEGAL_TERMS_VERSION"] = "2026-10-01-v2"
            os.environ["VKID_APP_ID"] = "app"
            os.environ["OWNER_VK_ID"] = "987654321"
            with self.assertRaises(MODULE.InfraError):
                MODULE.validate_product_environment()
        finally:
            os.environ.clear()
            os.environ.update(old)

    def test_product_environment_keeps_vkid_fail_closed_without_owner_config(self) -> None:
        old = dict(os.environ)
        try:
            os.environ.pop("VKID_APP_ID", None)
            os.environ.pop("OWNER_VK_ID", None)
            os.environ["LEGAL_PRIVACY_VERSION"] = "2026-10-01-v2"
            os.environ["LEGAL_CONSENT_VERSION"] = "2026-10-01-v2"
            os.environ["LEGAL_TERMS_VERSION"] = "2026-10-01-v2"

            product_env = MODULE.build_product_environment()
        finally:
            os.environ.clear()
            os.environ.update(old)

        self.assertIn('VKID_APP_ID=""', product_env)
        self.assertIn('OWNER_VK_ID=""', product_env)
        self.assertIn('VKID_LOGIN_ENABLED="false"', product_env)
        self.assertIn('REGISTRATION_ENABLED="false"', product_env)

    def test_product_environment_enables_vkid_only_with_owner_config(self) -> None:
        old = dict(os.environ)
        try:
            os.environ["VKID_APP_ID"] = "123456"
            os.environ["OWNER_VK_ID"] = "987654321"
            product_env = MODULE.build_product_environment()
        finally:
            os.environ.clear()
            os.environ.update(old)

        self.assertIn('VKID_APP_ID="123456"', product_env)
        self.assertIn('OWNER_VK_ID="987654321"', product_env)
        self.assertIn('VKID_LOGIN_ENABLED="true"', product_env)
        self.assertIn('REGISTRATION_ENABLED="false"', product_env)

    def test_remote_service_is_loopback_only_and_registration_is_gated(self) -> None:
        script = MODULE.REMOTE_DEPLOY_SCRIPT
        self.assertIn("--host 127.0.0.1 --port 8001", script)
        self.assertIn("EnvironmentFile=/etc/omnicio/runtime.env", script)
        self.assertIn("NoNewPrivileges=true", script)
        self.assertIn("proxy_pass http://127.0.0.1:8001", script)

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

    def test_legal_pages_are_private_owner_documents(self) -> None:
        root = SCRIPT_DIR.parent.parent
        privacy = (root / "web" / "legal" / "privacy.html").read_text()
        consent = (root / "web" / "legal" / "consent.html").read_text()
        terms = (root / "web" / "legal" / "terms.html").read_text()

        for document in (privacy, consent, terms):
            self.assertIn('content="noindex,nofollow"', document)
            self.assertIn("2026-10-01-v2", document)

        self.assertIn("OmniCIO Personal", privacy)
        self.assertIn("T-Invest API", privacy)
        self.assertIn("статьи 437", terms)
        self.assertNotIn("omnicioinfo@gmail.com", privacy)

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
            "logout",
        ):
            self.assertIn(f'id="{element_id}"', page)

        for endpoint in (
            "/api/me",
            "/api/auth/config",
            "/api/auth/vkid/start",
            "/api/auth/logout",
            "/api/broker/tbank",
            "/api/broker/tbank/accounts",
            "/api/broker/tbank/portfolio",
            "/api/broker/tbank/operations",
        ):
            self.assertIn(endpoint, script)

    def test_personal_dashboard_uses_real_portfolio_data_without_fake_values(self) -> None:
        root = SCRIPT_DIR.parent.parent
        page = (root / "web" / "index.html").read_text()
        script = (root / "web" / "app.js").read_text()

        self.assertIn("Данные читаются напрямую из T-Invest", page)
        self.assertIn('id="portfolio-content"', page)
        self.assertIn('id="positions-list"', page)
        self.assertIn('id="operations-list"', page)
        self.assertIn("Системные модули", page)
        self.assertIn("/api/broker/tbank/portfolio", script)
        self.assertIn("/api/broker/tbank/operations?limit=30", script)
        self.assertNotIn("innerHTML", script)
        self.assertNotIn("₽ 1 000 000", page)
        self.assertNotIn("+12.4%", page)

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
        self.assertIn('"display": "standalone"', (root / "web" / "manifest.webmanifest").read_text())

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
        self.assertIn('version = "0.3.0"', project)
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
