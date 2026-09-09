from __future__ import annotations

import unittest
from unittest import mock
from urllib.request import Request

import scripts.bootstrap_v10_cloudflare_production_database_via_staging as runner


_EXPECTED_SHA = "a" * 40
_TEST_OIDC = "synthetic_header.synthetic_claims.synthetic_signature"
_TEST_DSN = (
    "postgresql://omni_cio_cloudflare_prod:synthetic-credential-marker@"
    "ep-example-pooler.eu-central-1.aws.neon.tech/neondb?"
    "sslmode=require&channel_binding=require"
)


class CloudflareCfDBootstrapIngressChannelTests(unittest.TestCase):
    def test_runner_keeps_github_oidc_out_of_public_authorization_header(self) -> None:
        observed: list[Request] = []

        def fake_request(request: Request) -> dict[str, object]:
            observed.append(request)
            return {
                "status": "READY",
                "runtime_role": "omni_cio_cloudflare_prod",
                "runtime_dsn": _TEST_DSN,
                "source_sha": _EXPECTED_SHA,
            }

        with mock.patch.object(
            runner,
            "_request_staging_bootstrap_json",
            side_effect=fake_request,
        ):
            self.assertEqual(
                runner._bootstrap_runtime_dsn(
                    "https://omni-cio-v10-web-staging.example.workers.dev",
                    _EXPECTED_SHA,
                    _TEST_OIDC,
                ),
                _TEST_DSN,
            )

        self.assertEqual(len(observed), 1)
        request = observed[0]
        self.assertIsNone(request.get_header("Authorization"))
        self.assertEqual(request.get_header("X-omni-github-oidc"), _TEST_OIDC)
        self.assertEqual(request.get_header("X-omni-expected-sha"), _EXPECTED_SHA)
        self.assertNotIn(_TEST_OIDC, request.full_url)


if __name__ == "__main__":
    unittest.main()
