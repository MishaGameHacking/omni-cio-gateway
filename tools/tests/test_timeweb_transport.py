"""Transport diagnostics must remain secret-free and never disable TLS."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import timeweb_actions_probe as probe

TOKEN = "test-only-credential-not-a-real-token"


class TransportTests(unittest.TestCase):
    def test_transport_categories_do_not_leak_exception_messages(self):
        cases = (
            (probe.ssl.SSLCertVerificationError(TOKEN), "tls_certificate_verification_failed"),
            (probe.ssl.SSLError(TOKEN), "tls_handshake_failed"),
            (probe.socket.gaierror(TOKEN), "dns_lookup_failed"),
            (TimeoutError(TOKEN), "connection_timeout"),
            (ConnectionRefusedError(TOKEN), "connection_refused"),
            (ConnectionResetError(TOKEN), "connection_reset"),
            (PermissionError(TOKEN), "connection_denied"),
        )
        for reason, expected in cases:
            for error in (reason, urllib.error.URLError(reason)):
                with self.subTest(category=expected, wrapped=isinstance(error, urllib.error.URLError)):
                    self.assertEqual(probe.transport_error_code(error), "timeweb_" + expected)

    def test_unknown_transport_reason_is_not_echoed(self):
        reason = urllib.error.URLError(TOKEN)
        self.assertEqual(probe.transport_error_code(reason), "timeweb_transport_error")

    def test_certificate_failure_remains_failure_without_insecure_retry(self):
        error = urllib.error.URLError(probe.ssl.SSLCertVerificationError(TOKEN))
        with patch.object(probe.urllib.request, "build_opener") as build:
            build.return_value.open.side_effect = error
            with self.assertRaisesRegex(probe.ProbeError, "timeweb_tls_certificate_verification_failed"):
                probe.read_resource(TOKEN, "projects")
            self.assertEqual(build.return_value.open.call_count, 1)


    def test_windows_uses_native_verified_context(self):
        context = probe.ssl.create_default_context()
        with patch.object(probe.sys, "platform", "win32"), patch.object(probe, "native_tls_context", return_value=context) as native:
            actual = probe.verified_ssl_context()
        native.assert_called_once_with()
        self.assertIs(actual, context)
        self.assertTrue(actual.check_hostname)
        self.assertEqual(actual.verify_mode, probe.ssl.CERT_REQUIRED)
        self.assertEqual(actual.minimum_version, probe.ssl.TLSVersion.TLSv1_2)

    def test_unverified_context_cannot_be_used(self):
        context = probe.ssl.SSLContext(probe.ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        with patch.object(probe.sys, "platform", "win32"), patch.object(probe, "native_tls_context", return_value=context):
            with self.assertRaisesRegex(probe.ProbeError, "tls_verification_required"):
                probe.verified_ssl_context()

    def test_missing_native_dependency_has_no_insecure_fallback(self):
        with patch.dict(sys.modules, {"truststore": None}):
            with self.assertRaisesRegex(probe.ProbeError, "native_tls_dependency_missing"):
                probe.native_tls_context()

    def test_non_windows_uses_verified_standard_context(self):
        with patch.object(probe.sys, "platform", "linux"), patch.object(probe, "native_tls_context") as native:
            actual = probe.verified_ssl_context()
        native.assert_not_called()
        self.assertTrue(actual.check_hostname)
        self.assertEqual(actual.verify_mode, probe.ssl.CERT_REQUIRED)


if __name__ == "__main__":
    unittest.main()
