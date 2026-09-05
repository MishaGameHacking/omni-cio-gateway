from __future__ import annotations

import os
import ssl
import unittest
from unittest import mock

import apps.api.cf_d_database_bootstrap as bootstrap


class CfDBootstrapTlsPolicyTests(unittest.TestCase):
    def test_tls_context_uses_explicit_tls12_floor_and_server_verification(
        self,
    ) -> None:
        context = bootstrap._secure_tls_context()

        self.assertEqual(context.minimum_version, ssl.TLSVersion.TLSv1_2)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)

    def test_local_ca_fallback_preserves_explicit_tls_floor(self) -> None:
        with (
            mock.patch.dict(
                os.environ,
                {"OMNI_V10_CLOUDFLARE_RUNTIME": ""},
                clear=False,
            ),
            mock.patch.object(
                bootstrap,
                "_CLOUDFLARE_CONTAINER_CA_FILE",
                "/definitely/missing/cloudflare-container-ca.crt",
            ),
        ):
            context = bootstrap._container_tls_context()

        self.assertEqual(context.minimum_version, ssl.TLSVersion.TLSv1_2)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)


if __name__ == "__main__":
    unittest.main()
