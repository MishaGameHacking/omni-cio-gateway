from __future__ import annotations

import unittest
from unittest import mock

import scripts.bootstrap_v10_cloudflare_builds as builds
import scripts.bootstrap_v10_cloudflare_production_database_direct as direct
import scripts.deploy_v10_cloudflare_neon_bootstrap_function as deployer


_EXPECTED_SHA = "a" * 40
_PROJECT_ID = "billowing-smoke-00000000"
_ORG_ID = "org-example1234"
_BRANCH_ID = "br-example1234"
_PROJECT_TOKEN = "synthetic-project-authority"
_INVOKE_TOKEN = "synthetic-invoke-authority"
_TARGET = direct.BootstrapFunctionTarget(branch_id=_BRANCH_ID, cell="c-6")


class CloudflareNeonInvocationFallbackTests(unittest.TestCase):
    @staticmethod
    def _run_direct_bootstrap() -> object:
        return direct.run(_EXPECTED_SHA)

    def test_direct_run_retries_exact_provider_403_with_scoped_credential(self) -> None:
        provider_403 = direct.legacy.BootstrapStopped(
            direct._DIRECT_PROVIDER_AUTH_REQUIRED
        )
        manager = mock.MagicMock()
        manager.__enter__.return_value = _INVOKE_TOKEN
        manager.__exit__.return_value = False
        with (
            mock.patch.object(
                direct,
                "read_bootstrap_origin_handoff",
                return_value=_TARGET,
            ),
            mock.patch.object(
                direct,
                "_run_direct_bootstrap",
                side_effect=[provider_403, mock.sentinel.output_path],
            ) as run_direct,
            mock.patch.object(
                direct,
                "project_invocation_authority_from_env",
                return_value=(_PROJECT_TOKEN, _PROJECT_ID),
            ) as authority,
            mock.patch.object(
                direct,
                "function_invocation_credential",
                return_value=manager,
            ) as credential,
        ):
            result = direct.run(_EXPECTED_SHA)

        self.assertIs(result, mock.sentinel.output_path)
        self.assertEqual(
            run_direct.call_args_list,
            [
                mock.call(_TARGET, _EXPECTED_SHA, None),
                mock.call(_TARGET, _EXPECTED_SHA, _INVOKE_TOKEN),
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

    def test_direct_run_does_not_mint_credential_for_handler_failure(self) -> None:
        handler_failure = direct.legacy.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_OIDC_AUDIENCE_INVALID"
        )
        with (
            mock.patch.object(
                direct,
                "read_bootstrap_origin_handoff",
                return_value=_TARGET,
            ),
            mock.patch.object(
                direct,
                "_run_direct_bootstrap",
                side_effect=handler_failure,
            ),
            mock.patch.object(
                direct,
                "project_invocation_authority_from_env",
            ) as authority,
            mock.patch.object(
                direct,
                "function_invocation_credential",
            ) as credential,
        ):
            with self.assertRaisesRegex(
                direct.legacy.BootstrapStopped,
                "CLOUDFLARE_CF_D_NEON_FUNCTION_OIDC_AUDIENCE_INVALID",
            ):
                self._run_direct_bootstrap()

        authority.assert_not_called()
        credential.assert_not_called()

    def test_direct_headers_separate_outer_invoke_from_inner_github_oidc(self) -> None:
        headers = direct._direct_headers(
            oidc_token="synthetic-inner-github-oidc",
            invocation_token=_INVOKE_TOKEN,
        )
        self.assertEqual(
            headers,
            {
                "Accept": "application/json",
                "User-Agent": direct._DIRECT_USER_AGENT,
                "Authorization": f"Bearer {_INVOKE_TOKEN}",
                direct._DIRECT_OIDC_HEADER: "synthetic-inner-github-oidc",
                "Content-Type": "application/json",
            },
        )

    def test_deployer_retries_unauthenticated_403_with_scoped_credential(self) -> None:
        archive = b"PK synthetic"
        digest = "b" * 64
        provider_403 = builds.BootstrapStopped(
            deployer._SOURCE_PROVENANCE_AUTH_REQUIRED,
            status=403,
        )
        manager = mock.MagicMock()
        manager.__enter__.return_value = _INVOKE_TOKEN
        manager.__exit__.return_value = False

        def required_id(name: str) -> str:
            if name == "NEON_PROJECT_ID":
                return _PROJECT_ID
            if name == "NEON_ORG_ID":
                return _ORG_ID
            raise AssertionError(name)

        with (
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
                return_value=(archive, digest),
            ),
            mock.patch.object(
                deployer,
                "_probe_source_provenance",
                side_effect=[provider_403, True],
            ) as provenance,
            mock.patch.object(
                deployer,
                "_deploy_api_key",
                return_value=_PROJECT_TOKEN,
            ),
            mock.patch.object(
                deployer,
                "_required_id",
                side_effect=required_id,
            ),
            mock.patch.object(deployer, "_validate_project") as validate_project,
            mock.patch.object(
                deployer,
                "_exact_branch",
                return_value=_BRANCH_ID,
            ),
            mock.patch.object(deployer, "_function", return_value={}),
            mock.patch.object(deployer, "_preexisting", return_value="6"),
            mock.patch.object(
                deployer,
                "function_invocation_credential",
                return_value=manager,
            ) as credential,
            mock.patch.object(deployer, "_converge_exact_source") as converge,
        ):
            changed = deployer.deploy_exact_main_bootstrap_function(_EXPECTED_SHA)

        self.assertFalse(changed)
        self.assertEqual(
            provenance.call_args_list,
            [
                mock.call(_TARGET, digest),
                mock.call(_TARGET, digest, _INVOKE_TOKEN),
            ],
        )
        validate_project.assert_called_once_with(
            _PROJECT_TOKEN,
            _PROJECT_ID,
            _ORG_ID,
        )
        credential.assert_called_once_with(
            _PROJECT_TOKEN,
            _PROJECT_ID,
            _BRANCH_ID,
        )
        converge.assert_not_called()


if __name__ == "__main__":
    unittest.main()
