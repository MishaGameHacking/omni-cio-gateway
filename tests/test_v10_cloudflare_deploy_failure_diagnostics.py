from __future__ import annotations

from typing import Any, cast
import unittest
from unittest.mock import patch

import scripts.bootstrap_v10_cloudflare_builds as builds


class _TerminalBuildApi:
    account_id = "a" * 32

    @staticmethod
    def request(method: str, path: str, **kwargs: Any) -> dict[str, object]:
        del kwargs
        if method != "GET" or "/builds/builds/" not in path:
            raise AssertionError((method, path))
        return {"status": "stopped", "build_outcome": "fail"}


class CloudflareDeployFailureDiagnosticTests(unittest.TestCase):
    def test_container_registry_unauthorized_requires_container_image_context(
        self,
    ) -> None:
        diagnostic = builds._classify_build_failure(
            (
                "Building image omni-cio-v10-web-staging:abcdef",
                "✘ [ERROR] Unauthorized",
            )
        )
        self.assertEqual(diagnostic, "CLOUDFLARE_CONTAINER_REGISTRY_UNAUTHORIZED")

        unrelated = builds._classify_build_failure(
            (
                "> omni-cio-gateway@10.0.0 cloudflare:deploy:staging",
                "✘ [ERROR] Unauthorized",
            )
        )
        self.assertEqual(unrelated, "CLOUDFLARE_BUILD_DEPLOY_PHASE_FAILED")

    def test_container_access_denial_is_classified_without_raw_log_disclosure(
        self,
    ) -> None:
        cases = (
            "Authentication error",
            "ApiError: Forbidden",
        )
        for failure in cases:
            with self.subTest(failure=failure):
                diagnostic = builds._classify_build_failure(
                    (
                        "Building image omni-cio-v10-web-staging:abcdef",
                        failure,
                    )
                )
                self.assertEqual(diagnostic, "CLOUDFLARE_CONTAINERS_ACCESS_DENIED")

    def test_first_deploy_secret_inheritance_failure_has_exact_classifier(self) -> None:
        phrases = (
            "Cannot inherit bindings: no previous version exists",
            "A request to the Cloudflare API failed [code: 10057]",
        )
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                diagnostic = builds._classify_build_failure(
                    (
                        "> omni-cio-gateway@10.0.0 cloudflare:deploy:staging",
                        phrase,
                    )
                )
                self.assertEqual(
                    diagnostic,
                    "CLOUDFLARE_FIRST_DEPLOY_SECRET_INHERITANCE_FAILED",
                )

    def test_unrecognized_deploy_failure_remains_generic_and_fail_closed(self) -> None:
        diagnostic = builds._classify_build_failure(
            (
                "> omni-cio-gateway@10.0.0 cloudflare:deploy:staging",
                "unexpected provider deployment failure",
            )
        )
        self.assertEqual(diagnostic, "CLOUDFLARE_BUILD_DEPLOY_PHASE_FAILED")

    def test_actionable_container_diagnostic_propagates_from_terminal_build(
        self,
    ) -> None:
        api = cast(builds.CloudflareApi, _TerminalBuildApi())
        with patch.object(
            builds,
            "_safe_build_failure_diagnostic",
            return_value="CLOUDFLARE_CONTAINER_REGISTRY_UNAUTHORIZED",
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_CONTAINER_REGISTRY_UNAUTHORIZED",
            ):
                builds._wait_build(
                    api,
                    "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                    "c" * 40,
                )

    def test_generic_deploy_diagnostic_does_not_gain_false_actionable_authority(
        self,
    ) -> None:
        api = cast(builds.CloudflareApi, _TerminalBuildApi())
        with patch.object(
            builds,
            "_safe_build_failure_diagnostic",
            return_value="CLOUDFLARE_BUILD_DEPLOY_PHASE_FAILED",
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_STAGING_BUILD_FAILED",
            ):
                builds._wait_build(
                    api,
                    "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                    "c" * 40,
                )


if __name__ == "__main__":
    unittest.main()
