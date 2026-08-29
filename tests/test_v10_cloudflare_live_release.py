from __future__ import annotations

import unittest
from unittest import mock

import scripts.check_v10_cloudflare_live_release as verifier


class CloudflareLiveReleaseTests(unittest.TestCase):
    def test_origin_requires_https_default_tls_origin(self) -> None:
        self.assertEqual(verifier._origin("https://example.workers.dev/"), "https://example.workers.dev")
        for value in (
            "http://example.workers.dev",
            "https://user@example.workers.dev",
            "https://example.workers.dev:8443",
            "https://example.workers.dev/path",
            "https://example.workers.dev?x=1",
        ):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    RuntimeError, "CLOUDFLARE_RELEASE_ORIGIN_INVALID"
                ):
                    verifier._origin(value)

    def test_verify_accepts_exact_release_and_health(self) -> None:
        sha = "a" * 40
        responses = {
            "/api/v10/release": {
                "status": "ok",
                "platform": "cloudflare",
                "source_sha": sha,
                "backend": "container",
                "static_assets": True,
                "public_multi_user_enabled": False,
                "real_trading_enabled": False,
            },
            "/healthz": {
                "status": "ok",
                "release_sha": sha,
                "database": "READY",
            },
        }
        with mock.patch.object(
            verifier,
            "_json",
            side_effect=lambda origin, path: responses[path],
        ):
            verifier.verify("https://example.workers.dev", sha)

    def test_verify_rejects_source_drift(self) -> None:
        sha = "a" * 40
        with mock.patch.object(
            verifier,
            "_json",
            return_value={
                "status": "ok",
                "platform": "cloudflare",
                "source_sha": "b" * 40,
                "backend": "container",
                "static_assets": True,
                "public_multi_user_enabled": False,
                "real_trading_enabled": False,
            },
        ):
            with self.assertRaisesRegex(
                RuntimeError, "CLOUDFLARE_RELEASE_SOURCE_SHA_INVALID"
            ):
                verifier.verify("https://example.workers.dev", sha)

    def test_verify_rejects_public_multi_user_widening(self) -> None:
        sha = "a" * 40
        with mock.patch.object(
            verifier,
            "_json",
            return_value={
                "status": "ok",
                "platform": "cloudflare",
                "source_sha": sha,
                "backend": "container",
                "static_assets": True,
                "public_multi_user_enabled": True,
                "real_trading_enabled": False,
            },
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_RELEASE_PUBLIC_MULTI_USER_ENABLED_INVALID",
            ):
                verifier.verify("https://example.workers.dev", sha)


if __name__ == "__main__":
    unittest.main()
