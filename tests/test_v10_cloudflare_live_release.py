from __future__ import annotations

import unittest

import scripts.check_v10_cloudflare_live_release as verifier


class CloudflareLiveReleaseTests(unittest.TestCase):
    def test_origin_requires_allowed_https_origin(self) -> None:
        self.assertEqual(
            verifier._origin("https://example.workers.dev/"),
            "https://example.workers.dev",
        )
        self.assertEqual(
            verifier._origin(
                "https://www.example.com",
                allowed_custom_host="www.example.com",
            ),
            "https://www.example.com",
        )
        for value in (
            "http://example.workers.dev",
            "https://user@example.workers.dev",
            "https://example.workers.dev:8443",
            "https://example.workers.dev/path",
            "https://example.workers.dev?x=1",
            "https://127.0.0.1",
            "https://localhost",
            "https://metadata.google.internal",
            "https://service.local",
            "https://service.home.arpa",
        ):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    RuntimeError, "CLOUDFLARE_RELEASE_ORIGIN_"
                ):
                    verifier._origin(value)

    def test_workers_dev_origin_ignores_irrelevant_malformed_custom_host(self) -> None:
        self.assertEqual(
            verifier._origin(
                "https://example.workers.dev",
                allowed_custom_host="not a valid host",
            ),
            "https://example.workers.dev",
        )

    def test_custom_origin_still_requires_valid_exact_custom_host(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError, "CLOUDFLARE_RELEASE_ORIGIN_INVALID"
        ):
            verifier._origin(
                "https://www.example.com",
                allowed_custom_host="not a valid host",
            )

    def test_origin_rejects_unapproved_public_custom_host(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError, "CLOUDFLARE_RELEASE_ORIGIN_NOT_ALLOWED"
        ):
            verifier._origin("https://unapproved.example.com")

    def test_configured_origin_is_required(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError, "CLOUDFLARE_RELEASE_ORIGIN_REQUIRED"
        ):
            verifier._configured_origin({})

    def test_verify_release_accepts_exact_payload(self) -> None:
        sha = "a" * 40
        verifier.verify_release(
            {
                "status": "ok",
                "platform": "cloudflare",
                "source_sha": sha,
                "backend": "container",
                "static_assets": True,
                "public_multi_user_enabled": False,
                "real_trading_enabled": False,
            },
            sha,
        )

    def test_verify_container_source_accepts_exact_baked_sha(self) -> None:
        sha = "a" * 40
        verifier.verify_container_source(
            {"status": "ok", "image_source_sha": sha},
            sha,
        )

    def test_verify_container_source_rejects_image_drift(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_RELEASE_CONTAINER_IMAGE_SHA_MISMATCH",
        ):
            verifier.verify_container_source(
                {"status": "ok", "image_source_sha": "b" * 40},
                "a" * 40,
            )

    def test_verify_health_accepts_exact_payload(self) -> None:
        sha = "a" * 40
        verifier.verify_health(
            {
                "status": "ok",
                "release_sha": sha,
                "database": "READY",
            },
            sha,
        )

    def test_verify_release_rejects_source_drift(self) -> None:
        sha = "a" * 40
        with self.assertRaisesRegex(
            RuntimeError, "CLOUDFLARE_RELEASE_SOURCE_SHA_INVALID"
        ):
            verifier.verify_release(
                {
                    "status": "ok",
                    "platform": "cloudflare",
                    "source_sha": "b" * 40,
                    "backend": "container",
                    "static_assets": True,
                    "public_multi_user_enabled": False,
                    "real_trading_enabled": False,
                },
                sha,
            )

    def test_verify_release_rejects_public_multi_user_widening(self) -> None:
        sha = "a" * 40
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_RELEASE_PUBLIC_MULTI_USER_ENABLED_INVALID",
        ):
            verifier.verify_release(
                {
                    "status": "ok",
                    "platform": "cloudflare",
                    "source_sha": sha,
                    "backend": "container",
                    "static_assets": True,
                    "public_multi_user_enabled": True,
                    "real_trading_enabled": False,
                },
                sha,
            )


if __name__ == "__main__":
    unittest.main()
