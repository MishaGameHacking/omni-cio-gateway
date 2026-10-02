#!/usr/bin/env python3
"""Regression tests for the omnicio.ru TLS bootstrap."""

from __future__ import annotations

import importlib.util
import os
import pathlib
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

MODULE_PATH = pathlib.Path(__file__).with_name("timeweb_domain_tls.py")
SPEC = importlib.util.spec_from_file_location("timeweb_domain_tls", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load timeweb_domain_tls.py.")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class TlsVerificationTests(unittest.TestCase):
    """Exercise certificate trust and hostname checks against a real TLS peer."""

    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = pathlib.Path(directory.name)
        self.certificate = self.directory / "certificate.pem"
        key = self.directory / "key.pem"
        subprocess.run(
            [
                "/usr/bin/openssl", "req", "-x509", "-newkey", "rsa:2048",
                "-noenc", "-keyout", str(key), "-out", str(self.certificate),
                "-days", "1", "-subj", "/CN=localhost",
                "-addext", "subjectAltName=DNS:localhost",
            ],
            check=True,
            capture_output=True,
            timeout=15,
        )

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                body = MODULE.SITE_MARKER.encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.addCleanup(self.server.server_close)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(self.certificate, key)
        self.server.socket = context.wrap_socket(self.server.socket, server_side=True)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(self.server.shutdown)

    def verify(self, host: str, *, trusted: bool) -> bool:
        authority = f"{host}:{self.server.server_port}"
        ca_file = self.certificate if trusted else self.directory / "absent-ca.pem"
        with (
            patch.object(MODULE, "DOMAIN_NAME", authority),
            patch.dict(os.environ, {
                "SSL_CERT_FILE": str(ca_file),
                "SSL_CERT_DIR": str(self.directory),
                "NO_PROXY": "localhost,127.0.0.1",
            }),
        ):
            return bool(MODULE.verify_https())

    def test_trusted_certificate_with_matching_hostname_is_accepted(self) -> None:
        self.assertTrue(self.verify("localhost", trusted=True))

    def test_untrusted_certificate_is_rejected(self) -> None:
        self.assertFalse(self.verify("localhost", trusted=False))

    def test_trusted_certificate_with_wrong_hostname_is_rejected(self) -> None:
        self.assertFalse(self.verify("127.0.0.1", trusted=True))


class TimewebDomainTlsTests(unittest.TestCase):
    def test_dns_ready_when_a_matches_and_aaaa_absent(self) -> None:
        result = MODULE.assess_dns(
            expected_ipv4="194.87.151.244",
            dns_ipv4={"194.87.151.244"},
            dns_ipv6=set(),
        )

        self.assertTrue(result.ready)

    def test_dns_rejects_wrong_a(self) -> None:
        result = MODULE.assess_dns(
            expected_ipv4="194.87.151.244",
            dns_ipv4={"203.0.113.10"},
            dns_ipv6=set(),
        )

        self.assertFalse(result.ready)
        self.assertIn("A record", result.reason)

    def test_dns_rejects_any_aaaa_during_initial_cutover(self) -> None:
        result = MODULE.assess_dns(
            expected_ipv4="194.87.151.244",
            dns_ipv4={"194.87.151.244"},
            dns_ipv6={"2a03:6f00:a::3:18f5"},
        )

        self.assertFalse(result.ready)
        self.assertIn("AAAA", result.reason)

    def test_public_addresses_ignore_private_networks(self) -> None:
        server = {
            "networks": [
                {
                    "type": "private",
                    "ips": [
                        {"ip": "10.0.0.5"},
                        {"ip": "fd00::5"},
                    ],
                },
                {
                    "type": "public",
                    "ips": [
                        {"ip": "194.87.151.244"},
                        {"ip": "2a03:6f00:a::3:18f5"},
                    ],
                },
            ]
        }

        ipv4, ipv6 = MODULE.public_addresses(server)

        self.assertEqual(ipv4, {"194.87.151.244"})
        self.assertEqual(ipv6, {"2a03:6f00:a::3:18f5"})

    def test_remote_script_installs_certbot_and_redirects(self) -> None:
        script = MODULE.REMOTE_SCRIPT

        self.assertIn("python3-certbot-nginx", script)
        self.assertIn("certbot --nginx", script)
        self.assertIn("--redirect", script)
        self.assertIn("systemctl enable --now certbot.timer", script)

    def test_remote_script_uses_fixed_approved_domain(self) -> None:
        script = MODULE.REMOTE_SCRIPT

        self.assertIn('DOMAIN="omnicio.ru"', script)
        self.assertNotIn('DOMAIN="$1"', script)

    def test_ssh_requires_strict_host_key_checking(self) -> None:
        args = MODULE.ssh_base_args(
            pathlib.Path("/tmp/id_ed25519"),
            pathlib.Path("/tmp/known_hosts"),
        )

        self.assertIn("StrictHostKeyChecking=yes", args)
        self.assertNotIn("StrictHostKeyChecking=accept-new", args)


if __name__ == "__main__":
    unittest.main()
