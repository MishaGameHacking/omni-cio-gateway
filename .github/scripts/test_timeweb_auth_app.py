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
            "/api/broker/tbank/instruments/search",
            "/api/market/usd-rub",
            "/api/market/usd-rub/stream",
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
        manifest = (root / "web" / "manifest.webmanifest").read_text()
        self.assertIn('"display": "standalone"', manifest)

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
        self.assertIn('version = "0.5.2"', project)
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
            "registration_enabled": False, "auth_provider": "vkid",
            "owner_login_enabled": False,
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
            self.responses[path] = (marker.encode(), "text/html", 200)

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
