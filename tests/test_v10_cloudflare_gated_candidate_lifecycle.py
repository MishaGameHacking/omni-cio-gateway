from __future__ import annotations

from typing import cast
import unittest
from unittest.mock import patch

import scripts.bootstrap_v10_cloudflare_builds as builds
import scripts.run_v10_cloudflare_gated_candidate as gated


_EXPECTED_SHA = "a" * 40
_WORKER_TAG = "a" * 32
_ACCOUNT_ID = "b" * 32
_BUILD_UUID = "11111111-2222-3333-4444-555555555555"
_STAGING_URL = "https://omni-cio-v10-web-staging.example.workers.dev"


class CloudflareGatedCandidateLifecycleTests(unittest.TestCase):
    @staticmethod
    def _required_environment(name: str) -> str:
        values = {
            "CLOUDFLARE_API_TOKEN": "synthetic-token",
            "CLOUDFLARE_ACCOUNT_ID": _ACCOUNT_ID,
        }
        return values[name]

    def test_waits_for_terminal_build_before_cleanup(self) -> None:
        events: list[str] = []
        api = cast(builds.CloudflareApi, object())

        def prepare(_api: builds.CloudflareApi, _sha: str) -> tuple[str, str]:
            events.append("prepare")
            return _WORKER_TAG, _BUILD_UUID

        def wait(
            _api: builds.CloudflareApi,
            _build_uuid: str,
            _sha: str,
        ) -> None:
            events.append("wait")

        def staging_url(_api: builds.CloudflareApi) -> str:
            events.append("url")
            return _STAGING_URL

        def cleanup(*args, **kwargs) -> tuple[int, int]:
            del args, kwargs
            events.append("cleanup")
            return 0, 1

        with (
            patch.object(gated, "_assert_exact_head", return_value=_EXPECTED_SHA),
            patch.object(
                builds,
                "_required_env",
                side_effect=self._required_environment,
            ),
            patch.object(builds, "CloudflareApi", return_value=api),
            patch.object(gated, "_prepare_candidate", side_effect=prepare),
            patch.object(builds, "_wait_build", side_effect=wait),
            patch.object(builds, "_staging_url", side_effect=staging_url),
            patch.object(
                gated,
                "quarantine_staging_autobuild",
                side_effect=cleanup,
            ),
            patch.object(builds, "_write_output"),
        ):
            actual = gated.run(_EXPECTED_SHA)

        self.assertEqual(actual, _STAGING_URL)
        self.assertEqual(events, ["prepare", "wait", "url", "cleanup"])

    def test_terminal_build_failure_still_cleans_up(self) -> None:
        events: list[str] = []
        api = cast(builds.CloudflareApi, object())

        def prepare(_api: builds.CloudflareApi, _sha: str) -> tuple[str, str]:
            events.append("prepare")
            return _WORKER_TAG, _BUILD_UUID

        def wait(
            _api: builds.CloudflareApi,
            _build_uuid: str,
            _sha: str,
        ) -> None:
            events.append("wait")
            raise builds.BootstrapStopped("CLOUDFLARE_STAGING_BUILD_FAILED")

        def cleanup(*args, **kwargs) -> tuple[int, int]:
            del args, kwargs
            events.append("cleanup")
            return 0, 1

        with (
            patch.object(gated, "_assert_exact_head", return_value=_EXPECTED_SHA),
            patch.object(
                builds,
                "_required_env",
                side_effect=self._required_environment,
            ),
            patch.object(builds, "CloudflareApi", return_value=api),
            patch.object(gated, "_prepare_candidate", side_effect=prepare),
            patch.object(builds, "_wait_build", side_effect=wait),
            patch.object(
                gated,
                "quarantine_staging_autobuild",
                side_effect=cleanup,
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_STAGING_BUILD_FAILED",
            ):
                gated.run(_EXPECTED_SHA)

        self.assertEqual(events, ["prepare", "wait", "cleanup"])


if __name__ == "__main__":
    unittest.main()
