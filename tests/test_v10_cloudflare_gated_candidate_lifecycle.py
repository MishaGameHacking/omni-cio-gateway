from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, cast
import unittest
from unittest.mock import patch

import scripts.bootstrap_v10_cloudflare_builds as builds
import scripts.run_v10_cloudflare_gated_candidate as gated


_EXPECTED_SHA = "a" * 40
_WORKER_TAG = "a" * 32
_ACCOUNT_ID = "b" * 32
_TRIGGER_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_BUILD_UUID = "11111111-2222-3333-4444-555555555555"
_VERSION_UUID = "66666666-7777-8888-9999-aaaaaaaaaaaa"
_STAGING_URL = "https://omni-cio-v10-web-staging.example.workers.dev"
_BOOTSTRAP_ORIGIN = (
    "https://br-example1234-cfdprodbootstrap.compute."
    "c-6.eu-central-1.aws.neon.tech/"
)
_SYNC_TOKEN = "c" * 64


class _DeploymentsApi:
    account_id = _ACCOUNT_ID

    def __init__(self, versions: list[dict[str, object]]) -> None:
        self.versions = versions
        self.calls: list[tuple[str, str]] = []

    def request(
        self,
        method: str,
        path: str,
        *,
        body: object | None = None,
        expected: frozenset[int] = frozenset({200}),
        timeout: float = 30.0,
    ) -> Any:
        del body, expected, timeout
        self.calls.append((method, path))
        if method != "GET" or not path.endswith("/deployments"):
            raise AssertionError(f"unexpected request: {method} {path}")
        return {"deployments": [{"versions": self.versions}]}


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
        release_error: builds.BootstrapStopped | None = None,
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

        def deployment(_api: builds.CloudflareApi) -> str:
            events.append("deployment-proof")
            return _VERSION_UUID

        def release(staging_origin: str, expected_sha: str) -> None:
            self.assertEqual(staging_origin, _STAGING_URL)
            self.assertEqual(expected_sha, _EXPECTED_SHA)
            events.append("release-proof")
            if release_error is not None:
                raise release_error

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
            patch.object(
                gated, "bootstrap_origin_sync_token", side_effect=token_context
            ),
            patch.object(gated, "_start_exact_manual_build", side_effect=start),
            patch.object(builds, "_wait_build", side_effect=wait),
            patch.object(builds, "_staging_url", side_effect=staging_url),
            patch.object(gated, "_staging_active_version_id", side_effect=deployment),
            patch.object(gated, "assert_staging_exact_release", side_effect=release),
            patch.object(
                gated, "fetch_bootstrap_origin_custody", side_effect=fetch_origin
            ),
            patch.object(
                gated, "persist_bootstrap_origin_custody", side_effect=persist
            ),
            patch.object(
                gated,
                "quarantine_staging_autobuild",
                side_effect=cleanup,
            ),
            patch.object(builds, "_write_output"),
        ):
            return gated.run(_EXPECTED_SHA)

    def test_token_is_armed_before_exact_build_and_custody_proof_precedes_mutation(
        self,
    ) -> None:
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
                "deployment-proof",
                "release-proof",
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

    def test_release_attestation_failure_stops_before_custody_and_disarms_token(
        self,
    ) -> None:
        events: list[str] = []
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_CF_D_PRE_CUSTODY_RELEASE_SHA_MISMATCH",
        ):
            self._run_candidate(
                events,
                release_error=builds.BootstrapStopped(
                    "CLOUDFLARE_CF_D_PRE_CUSTODY_RELEASE_SHA_MISMATCH"
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
                "deployment-proof",
                "release-proof",
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
                "deployment-proof",
                "release-proof",
                "custody-proof",
                "disarm-token",
                "cleanup-trigger",
            ],
        )

    def test_staging_deployment_requires_one_exact_100_percent_version(self) -> None:
        api = _DeploymentsApi([{"version_id": _VERSION_UUID, "percentage": 100}])
        actual = gated._staging_active_version_id(cast(builds.CloudflareApi, api))
        self.assertEqual(actual, _VERSION_UUID)
        self.assertEqual(len(api.calls), 1)
        self.assertIn("omni-cio-v10-web-staging/deployments", api.calls[0][1])

        invalid = (
            [],
            [
                {"version_id": _VERSION_UUID, "percentage": 50},
                {
                    "version_id": "bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
                    "percentage": 50,
                },
            ],
            [{"version_id": _VERSION_UUID, "percentage": 99}],
            [{"version_id": _VERSION_UUID, "percentage": True}],
        )
        for versions in invalid:
            with self.subTest(versions=versions):
                bad_api = _DeploymentsApi(list(versions))
                with self.assertRaises(builds.BootstrapStopped):
                    gated._staging_active_version_id(
                        cast(builds.CloudflareApi, bad_api)
                    )


if __name__ == "__main__":
    unittest.main()
