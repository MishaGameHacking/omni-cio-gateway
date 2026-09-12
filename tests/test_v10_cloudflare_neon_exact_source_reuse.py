from __future__ import annotations

from pathlib import Path
from typing import cast
import unittest
from unittest import mock

import scripts.bootstrap_v10_cloudflare_builds as builds
import scripts.reuse_v10_cloudflare_neon_bootstrap_function_source as reuse


_ROOT = Path(__file__).resolve().parents[1]
_CANDIDATE_RUNNER = _ROOT / "scripts/run_v10_cloudflare_gated_candidate.py"
_EXPECTED_SHA = "a" * 40


class CloudflareNeonExactSourceReuseTests(unittest.TestCase):
    @staticmethod
    def _api() -> builds.CloudflareApi:
        return cast(builds.CloudflareApi, object())

    def test_runtime_secret_ready_skips_legacy_function_authority(self) -> None:
        api = self._api()
        with (
            mock.patch(
                "scripts.manage_v10_cloudflare_production._runtime_secret_present",
                return_value=True,
            ) as runtime_secret,
            mock.patch.object(builds, "_expected_sha", return_value=_EXPECTED_SHA),
        ):
            changed = reuse.deploy_exact_main_bootstrap_function_if_required(
                api,
                _EXPECTED_SHA,
            )

        self.assertFalse(changed)
        runtime_secret.assert_called_once_with(api)

    def test_missing_runtime_secret_defers_to_project_scoped_bootstrap(self) -> None:
        with (
            mock.patch(
                "scripts.manage_v10_cloudflare_production._runtime_secret_present",
                return_value=False,
            ),
            mock.patch.object(builds, "_expected_sha", return_value=_EXPECTED_SHA),
            mock.patch("builtins.print") as output,
        ):
            changed = reuse.deploy_exact_main_bootstrap_function_if_required(
                self._api(),
                _EXPECTED_SHA,
            )

        self.assertFalse(changed)
        output.assert_called_once_with(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY="
            "DEFERRED_PROJECT_SCOPED_RUNTIME_BOOTSTRAP"
        )

    def test_missing_production_worker_anchor_also_defers(self) -> None:
        missing_anchor = builds.BootstrapStopped(
            "CLOUDFLARE_PRODUCTION_WORKER_NOT_FOUND",
            status=404,
        )
        with (
            mock.patch(
                "scripts.manage_v10_cloudflare_production._runtime_secret_present",
                side_effect=missing_anchor,
            ),
            mock.patch.object(builds, "_expected_sha", return_value=_EXPECTED_SHA),
            mock.patch("builtins.print") as output,
        ):
            changed = reuse.deploy_exact_main_bootstrap_function_if_required(
                self._api(),
                _EXPECTED_SHA,
            )

        self.assertFalse(changed)
        output.assert_called_once_with(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_DEPLOY="
            "DEFERRED_PROJECT_SCOPED_RUNTIME_BOOTSTRAP"
        )

    def test_non_404_runtime_secret_failure_remains_fail_closed(self) -> None:
        failure = builds.BootstrapStopped(
            "CLOUDFLARE_PRODUCTION_SECRETS_INVALID",
            status=403,
        )
        with (
            mock.patch(
                "scripts.manage_v10_cloudflare_production._runtime_secret_present",
                side_effect=failure,
            ),
            mock.patch.object(builds, "_expected_sha", return_value=_EXPECTED_SHA),
        ):
            with self.assertRaisesRegex(
                builds.BootstrapStopped,
                "CLOUDFLARE_PRODUCTION_SECRETS_INVALID",
            ):
                reuse.deploy_exact_main_bootstrap_function_if_required(
                    self._api(),
                    _EXPECTED_SHA,
                )

    def test_adapter_has_no_active_function_or_invoke_secret_dependency(self) -> None:
        source = Path(reuse.__file__).read_text(encoding="utf-8")
        self.assertNotIn("NEON_FUNCTION_INVOKE_API_TOKEN", source)
        self.assertNotIn("function_invocation_credential", source)
        self.assertNotIn("deploy_exact_main_bootstrap_function(", source)
        self.assertNotIn("_probe_source_provenance", source)

    def test_candidate_runner_keeps_single_bounded_compatibility_adapter(self) -> None:
        source = _CANDIDATE_RUNNER.read_text(encoding="utf-8")
        self.assertIn(
            "from scripts.reuse_v10_cloudflare_neon_bootstrap_function_source import (",
            source,
        )
        self.assertEqual(
            source.count("deploy_exact_main_bootstrap_function_if_required(api, sha)"),
            1,
        )


if __name__ == "__main__":
    unittest.main()
