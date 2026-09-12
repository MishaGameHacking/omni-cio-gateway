from __future__ import annotations

from pathlib import Path
from typing import cast
import unittest
from unittest import mock

import scripts.bootstrap_v10_cloudflare_builds as builds
import scripts.bootstrap_v10_cloudflare_production_database_direct as direct
import scripts.deploy_v10_cloudflare_neon_bootstrap_function as deployer
import scripts.reuse_v10_cloudflare_neon_bootstrap_function_source as reuse


_ROOT = Path(__file__).resolve().parents[1]
_CANDIDATE_RUNNER = _ROOT / "scripts/run_v10_cloudflare_gated_candidate.py"
_EXPECTED_SHA = "a" * 40
_PROJECT_ID = "billowing-smoke-00000000"
_BRANCH_ID = "br-example1234"
_PROJECT_TOKEN = "synthetic-project-authority"
_INVOKE_TOKEN = "synthetic-invoke-authority"
_TARGET = direct.BootstrapFunctionTarget(branch_id=_BRANCH_ID, cell="c-6")


class CloudflareNeonExactSourceReuseTests(unittest.TestCase):
    @staticmethod
    def _api() -> builds.CloudflareApi:
        return cast(builds.CloudflareApi, object())

    def test_authenticated_exact_source_reuse_precedes_metadata_reads(self) -> None:
        digest = "b" * 64
        provider_403 = builds.BootstrapStopped(
            deployer._SOURCE_PROVENANCE_AUTH_REQUIRED,
            status=403,
        )
        manager = mock.MagicMock()
        manager.__enter__.return_value = _INVOKE_TOKEN
        manager.__exit__.return_value = False

        with (
            mock.patch(
                "scripts.manage_v10_cloudflare_production._runtime_secret_present",
                return_value=False,
            ),
            mock.patch.object(
                deployer,
                "_assert_exact_head",
                return_value=_EXPECTED_SHA,
            ),
            mock.patch.object(
                deployer,
                "read_bootstrap_origin_handoff",
                return_value=_TARGET,
            ),
            mock.patch.object(
                deployer,
                "_deployment_bundle",
                return_value=(b"PK synthetic", digest),
            ),
            mock.patch.object(
                deployer,
                "_probe_source_provenance",
                side_effect=[provider_403, True],
            ) as provenance,
            mock.patch.object(
                reuse,
                "project_invocation_authority_from_env",
                return_value=(_PROJECT_TOKEN, _PROJECT_ID),
            ) as authority,
            mock.patch.object(
                reuse,
                "function_invocation_credential",
                return_value=manager,
            ) as credential,
            mock.patch.object(deployer, "_deploy_api_key") as deploy_key,
            mock.patch.object(deployer, "_validate_project") as validate_project,
            mock.patch.object(deployer, "_exact_branch") as exact_branch,
            mock.patch.object(deployer, "_function") as function_read,
            mock.patch.object(
                deployer,
                "deploy_exact_main_bootstrap_function",
            ) as converge,
        ):
            changed = reuse.deploy_exact_main_bootstrap_function_if_required(
                self._api(),
                _EXPECTED_SHA,
            )

        self.assertFalse(changed)
        self.assertEqual(
            provenance.call_args_list,
            [
                mock.call(_TARGET, digest),
                mock.call(_TARGET, digest, _INVOKE_TOKEN),
            ],
        )
        authority.assert_called_once_with()
        credential.assert_called_once_with(
            _PROJECT_TOKEN,
            _PROJECT_ID,
            _BRANCH_ID,
        )
        manager.__enter__.assert_called_once_with()
        manager.__exit__.assert_called_once()
        deploy_key.assert_not_called()
        validate_project.assert_not_called()
        exact_branch.assert_not_called()
        function_read.assert_not_called()
        converge.assert_not_called()

    def test_unauthenticated_exact_source_reuse_stays_credential_free(self) -> None:
        digest = "c" * 64
        with (
            mock.patch(
                "scripts.manage_v10_cloudflare_production._runtime_secret_present",
                return_value=False,
            ),
            mock.patch.object(deployer, "_assert_exact_head"),
            mock.patch.object(
                deployer,
                "read_bootstrap_origin_handoff",
                return_value=_TARGET,
            ),
            mock.patch.object(
                deployer,
                "_deployment_bundle",
                return_value=(b"PK synthetic", digest),
            ),
            mock.patch.object(
                deployer,
                "_probe_source_provenance",
                return_value=True,
            ),
            mock.patch.object(reuse, "project_invocation_authority_from_env") as authority,
            mock.patch.object(reuse, "function_invocation_credential") as credential,
            mock.patch.object(
                deployer,
                "deploy_exact_main_bootstrap_function",
            ) as converge,
        ):
            changed = reuse.deploy_exact_main_bootstrap_function_if_required(
                self._api(),
                _EXPECTED_SHA,
            )

        self.assertFalse(changed)
        authority.assert_not_called()
        credential.assert_not_called()
        converge.assert_not_called()

    def test_authenticated_stale_source_delegates_to_hardened_convergence(self) -> None:
        digest = "d" * 64
        provider_403 = builds.BootstrapStopped(
            deployer._SOURCE_PROVENANCE_AUTH_REQUIRED,
            status=403,
        )
        manager = mock.MagicMock()
        manager.__enter__.return_value = _INVOKE_TOKEN
        manager.__exit__.return_value = False

        with (
            mock.patch(
                "scripts.manage_v10_cloudflare_production._runtime_secret_present",
                return_value=False,
            ),
            mock.patch.object(deployer, "_assert_exact_head"),
            mock.patch.object(
                deployer,
                "read_bootstrap_origin_handoff",
                return_value=_TARGET,
            ),
            mock.patch.object(
                deployer,
                "_deployment_bundle",
                return_value=(b"PK synthetic", digest),
            ),
            mock.patch.object(
                deployer,
                "_probe_source_provenance",
                side_effect=[provider_403, False],
            ),
            mock.patch.object(
                reuse,
                "project_invocation_authority_from_env",
                return_value=(_PROJECT_TOKEN, _PROJECT_ID),
            ),
            mock.patch.object(
                reuse,
                "function_invocation_credential",
                return_value=manager,
            ),
            mock.patch.object(
                deployer,
                "deploy_exact_main_bootstrap_function",
                return_value=True,
            ) as converge,
        ):
            changed = reuse.deploy_exact_main_bootstrap_function_if_required(
                self._api(),
                _EXPECTED_SHA,
            )

        self.assertTrue(changed)
        manager.__exit__.assert_called_once()
        converge.assert_called_once_with(_EXPECTED_SHA)

    def test_unexpected_provenance_failure_never_mints_or_delegates(self) -> None:
        failure = builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_PROVENANCE_INVALID",
            status=403,
        )
        api = self._api()
        with (
            mock.patch(
                "scripts.manage_v10_cloudflare_production._runtime_secret_present",
                return_value=False,
            ),
            mock.patch.object(deployer, "_assert_exact_head"),
            mock.patch.object(
                deployer,
                "read_bootstrap_origin_handoff",
                return_value=_TARGET,
            ),
            mock.patch.object(
                deployer,
                "_deployment_bundle",
                return_value=(b"PK synthetic", "e" * 64),
            ),
            mock.patch.object(
                deployer,
                "_probe_source_provenance",
                side_effect=failure,
            ),
            mock.patch.object(reuse, "project_invocation_authority_from_env") as authority,
            mock.patch.object(reuse, "function_invocation_credential") as credential,
            mock.patch.object(
                deployer,
                "deploy_exact_main_bootstrap_function",
            ) as converge,
        ):
            with self.assertRaisesRegex(
                builds.BootstrapStopped,
                "CLOUDFLARE_CF_D_NEON_FUNCTION_PROVENANCE_INVALID",
            ):
                reuse.deploy_exact_main_bootstrap_function_if_required(
                    api,
                    _EXPECTED_SHA,
                )

        authority.assert_not_called()
        credential.assert_not_called()
        converge.assert_not_called()

    def test_runtime_secret_ready_skips_all_function_authority(self) -> None:
        with (
            mock.patch(
                "scripts.manage_v10_cloudflare_production._runtime_secret_present",
                return_value=True,
            ),
            mock.patch.object(deployer, "_assert_exact_head") as exact_head,
            mock.patch.object(reuse, "project_invocation_authority_from_env") as authority,
            mock.patch.object(
                deployer,
                "deploy_exact_main_bootstrap_function",
            ) as converge,
        ):
            changed = reuse.deploy_exact_main_bootstrap_function_if_required(
                self._api(),
                _EXPECTED_SHA,
            )

        self.assertFalse(changed)
        exact_head.assert_not_called()
        authority.assert_not_called()
        converge.assert_not_called()

    def test_candidate_runner_uses_exact_source_reuse_adapter(self) -> None:
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
