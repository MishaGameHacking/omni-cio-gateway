from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, cast
import unittest
from unittest.mock import patch

import scripts.bootstrap_v10_cloudflare_builds as builds
from scripts.bootstrap_v10_cloudflare_production_database_direct import (
    BootstrapFunctionTarget,
)
import scripts.run_v10_cloudflare_gated_candidate as gated


_EXPECTED_SHA = "a" * 40
_ACCOUNT_ID = "b" * 32
_TRIGGER_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_BUILD_UUID = "11111111-2222-3333-4444-555555555555"
_STAGING_URL = "https://omni-cio-v10-web-staging.example.workers.dev"
_BOOTSTRAP_ORIGIN = (
    "https://br-example1234-cfdprodbootstrap.compute."
    "c-6.eu-central-1.aws.neon.tech/"
)
_SYNC_TOKEN = "c" * 64
_TARGET = BootstrapFunctionTarget(branch_id="br-example1234", cell="c-6")
_DIGEST = "d" * 64


class CloudflareGatedCandidateProvenanceTransportTests(unittest.TestCase):
    def test_adapter_routes_digest_probe_through_staging_and_restores_direct_probe(
        self,
    ) -> None:
        observed: list[dict[str, str]] = []

        def original(_target: BootstrapFunctionTarget, _digest: str) -> bool:
            raise AssertionError("direct probe must be replaced inside adapter")

        def staging_probe(**kwargs: str) -> bool:
            observed.append(dict(kwargs))
            return True

        with (
            patch.object(gated.function_deployer, "_probe_source_provenance", original),
            patch.object(
                gated,
                "probe_exact_source_via_staging",
                side_effect=staging_probe,
            ),
        ):
            with gated._candidate_provenance_transport(
                staging_origin=_STAGING_URL,
                expected_sha=_EXPECTED_SHA,
                sync_token=_SYNC_TOKEN,
            ):
                self.assertTrue(
                    gated.function_deployer._probe_source_provenance(
                        _TARGET,
                        _DIGEST,
                    )
                )
            self.assertIs(gated.function_deployer._probe_source_provenance, original)

        self.assertEqual(
            observed,
            [
                {
                    "staging_origin": _STAGING_URL,
                    "expected_sha": _EXPECTED_SHA,
                    "token": _SYNC_TOKEN,
                    "expected_digest": _DIGEST,
                }
            ],
        )

    def test_exact_main_function_convergence_runs_while_ephemeral_token_is_armed(
        self,
    ) -> None:
        events: list[str] = []
        api = cast(builds.CloudflareApi, object())

        @contextmanager
        def token_context(_api: builds.CloudflareApi) -> Iterator[str]:
            events.append("arm-token")
            try:
                yield _SYNC_TOKEN
            finally:
                events.append("disarm-token")

        @contextmanager
        def provenance_context(**kwargs: str) -> Iterator[None]:
            self.assertEqual(
                kwargs,
                {
                    "staging_origin": _STAGING_URL,
                    "expected_sha": _EXPECTED_SHA,
                    "sync_token": _SYNC_TOKEN,
                },
            )
            events.append("bind-provenance")
            try:
                yield
            finally:
                events.append("restore-provenance")

        def required_env(name: str) -> str:
            return {
                "CLOUDFLARE_API_TOKEN": "synthetic-token",
                "CLOUDFLARE_ACCOUNT_ID": _ACCOUNT_ID,
            }[name]

        def deploy(_api: builds.CloudflareApi, sha: str) -> bool:
            self.assertEqual(sha, _EXPECTED_SHA)
            events.append("function-convergence")
            return True

        with (
            patch.object(gated, "_assert_exact_head", return_value=_EXPECTED_SHA),
            patch.object(builds, "_required_env", side_effect=required_env),
            patch.object(builds, "CloudflareApi", return_value=api),
            patch.object(
                gated,
                "_prepare_candidate",
                return_value=("a" * 32, _TRIGGER_UUID),
            ),
            patch.object(gated, "bootstrap_origin_sync_token", side_effect=token_context),
            patch.object(gated, "_start_exact_manual_build", return_value=_BUILD_UUID),
            patch.object(builds, "_wait_build"),
            patch.object(builds, "_staging_url", return_value=_STAGING_URL),
            patch.object(gated, "_staging_active_version_id"),
            patch.object(gated, "assert_staging_exact_release"),
            patch.object(
                gated,
                "fetch_bootstrap_origin_custody",
                return_value=_BOOTSTRAP_ORIGIN,
            ),
            patch.object(gated, "write_bootstrap_origin_handoff") as handoff,
            patch.object(
                gated,
                "_candidate_provenance_transport",
                side_effect=provenance_context,
            ),
            patch.object(
                gated,
                "deploy_exact_main_bootstrap_function_if_required",
                side_effect=deploy,
            ),
            patch.object(gated, "persist_bootstrap_origin_custody") as persist,
            patch.object(gated, "quarantine_staging_autobuild"),
            patch.object(builds, "_write_output"),
        ):
            self.assertEqual(
                gated.run(_EXPECTED_SHA, source_branch="main"),
                _STAGING_URL,
            )

        self.assertEqual(
            events,
            [
                "arm-token",
                "bind-provenance",
                "function-convergence",
                "restore-provenance",
                "disarm-token",
            ],
        )
        handoff.assert_called_once_with(_BOOTSTRAP_ORIGIN)
        persist.assert_called_once_with(api, _BOOTSTRAP_ORIGIN)


if __name__ == "__main__":
    unittest.main()
