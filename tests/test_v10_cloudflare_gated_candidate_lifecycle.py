from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, cast
import unittest
from unittest.mock import patch

import scripts.bootstrap_v10_cloudflare_builds as builds
import scripts.run_v10_cloudflare_gated_candidate as gated


_EXPECTED_SHA = "a" * 40
_WORKER_TAG = "a" * 32
_ACCOUNT_ID = "b" * 32
_TRIGGER_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_BUILD_UUID = "11111111-2222-3333-4444-555555555555"
_STAGING_URL = "https://omni-cio-v10-web-staging.example.workers.dev"
_BOOTSTRAP_ORIGIN = (
    "https://br-example1234-cfdprodbootstrap.compute."
    "c-6.eu-central-1.aws.neon.tech/"
)
_SYNC_TOKEN = "c" * 64


class CloudflareGatedCandidateLifecycleTests(unittest.TestCase):
    @staticmethod
    def _required_environment(name: str) -> str:
        values = {
            "CLOUDFLARE_API_TOKEN": "synthetic-token",
            "CLOUDFLARE_ACCOUNT_ID": _ACCOUNT_ID,
        }
        return values[name]

    def _run_candidate(
        self,
        events: list[str],
        *,
        wait_error: builds.BootstrapStopped | None = None,
        custody_error: builds.BootstrapStopped | None = None,
    ) -> str:
        api = cast(builds.CloudflareApi, object())

        def prepare(_api: builds.CloudflareApi, _sha: str) -> tuple[str, str]:
            events.append("prepare")
            return _WORKER_TAG, _TRIGGER_UUID

        @contextmanager
        def token_context(_api: builds.CloudflareApi) -> Iterator[str]:
            events.append("arm-token")
            try:
                yield _SYNC_TOKEN
            finally:
                events.append("disarm-token")

        def start(
            _api: builds.CloudflareApi,
            *,
            trigger_uuid: str,
            expected_sha: str,
        ) -> str:
            self.assertEqual(trigger_uuid, _TRIGGER_UUID)
            self.assertEqual(expected_sha, _EXPECTED_SHA)
            events.append("start")
            return _BUILD_UUID

        def wait(
            _api: builds.CloudflareApi,
            _build_uuid: str,
            _sha: str,
        ) -> None:
            events.append("wait")
            if wait_error is not None:
                raise wait_error

        def staging_url(_api: builds.CloudflareApi) -> str:
            events.append("url")
            return _STAGING_URL

        def fetch_origin(*, staging_origin: str, expected_sha: str, token: str) -> str:
            self.assertEqual(staging_origin, _STAGING_URL)
            self.assertEqual(expected_sha, _EXPECTED_SHA)
            self.assertEqual(token, _SYNC_TOKEN)
            events.append("custody-proof")
            if custody_error is not None:
                raise custody_error
            return _BOOTSTRAP_ORIGIN

        def persist(_api: builds.CloudflareApi, origin: str) -> None:
            self.assertEqual(origin, _BOOTSTRAP_ORIGIN)
            events.append("persist-origin")

        def cleanup(*args, **kwargs) -> tuple[int, int]:
            del args, kwargs
            events.append("cleanup-trigger")
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
            patch.object(gated, "bootstrap_origin_sync_token", side_effect=token_context),
            patch.object(gated, "_start_exact_manual_build", side_effect=start),
            patch.object(builds, "_wait_build", side_effect=wait),
            patch.object(builds, "_staging_url", side_effect=staging_url),
            patch.object(gated, "fetch_bootstrap_origin_custody", side_effect=fetch_origin),
            patch.object(gated, "persist_bootstrap_origin_custody", side_effect=persist),
            patch.object(
                gated,
                "quarantine_staging_autobuild",
                side_effect=cleanup,
            ),
            patch.object(builds, "_write_output"),
        ):
            return gated.run(_EXPECTED_SHA)

    def test_token_is_armed_before_exact_build_and_custody_proof_precedes_mutation(self) -> None:
        events: list[str] = []
        actual = self._run_candidate(events)
        self.assertEqual(actual, _STAGING_URL)
        self.assertEqual(
            events,
            [
                "prepare",
                "arm-token",
                "start",
                "wait",
                "url",
                "custody-proof",
                "disarm-token",
                "persist-origin",
                "cleanup-trigger",
            ],
        )

    def test_terminal_build_failure_disarms_token_before_trigger_cleanup(self) -> None:
        events: list[str] = []
        with self.assertRaisesRegex(RuntimeError, "CLOUDFLARE_STAGING_BUILD_FAILED"):
            self._run_candidate(
                events,
                wait_error=builds.BootstrapStopped("CLOUDFLARE_STAGING_BUILD_FAILED"),
            )
        self.assertEqual(
            events,
            [
                "prepare",
                "arm-token",
                "start",
                "wait",
                "disarm-token",
                "cleanup-trigger",
            ],
        )

    def test_custody_failure_disarms_token_and_does_not_persist_origin(self) -> None:
        events: list[str] = []
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_CF_D_ORIGIN_SYNC_UNAVAILABLE",
        ):
            self._run_candidate(
                events,
                custody_error=builds.BootstrapStopped(
                    "CLOUDFLARE_CF_D_ORIGIN_SYNC_UNAVAILABLE"
                ),
            )
        self.assertEqual(
            events,
            [
                "prepare",
                "arm-token",
                "start",
                "wait",
                "url",
                "custody-proof",
                "disarm-token",
                "cleanup-trigger",
            ],
        )


if __name__ == "__main__":
    unittest.main()
