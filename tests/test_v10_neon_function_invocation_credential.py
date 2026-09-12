from __future__ import annotations

from pathlib import Path
import unittest
from unittest import mock

import scripts.bootstrap_v10_cloudflare_builds as builds
import scripts.neon_function_invocation_credential as invoke


_INVOKE_TOKEN = "synthetic-invoke-authority"
_PROJECT_TOKEN = "synthetic-project-authority"
_PROJECT_ID = "billowing-smoke-00000000"
_BRANCH_ID = "br-example1234"


class NeonFunctionInvocationCredentialTests(unittest.TestCase):
    def test_preprovisioned_invoke_secret_is_loaded_and_masked(self) -> None:
        with (
            mock.patch.dict(
                invoke.os.environ,
                {invoke._INVOKE_API_TOKEN_ENV: _INVOKE_TOKEN},
                clear=True,
            ),
            mock.patch.object(builds, "_mask") as mask,
        ):
            self.assertEqual(
                invoke.function_invocation_token_from_env(),
                _INVOKE_TOKEN,
            )
        mask.assert_called_once_with(_INVOKE_TOKEN)

    def test_missing_invoke_secret_fails_closed(self) -> None:
        with (
            mock.patch.dict(invoke.os.environ, {}, clear=True),
            self.assertRaisesRegex(
                builds.BootstrapStopped,
                "CLOUDFLARE_CF_D_NEON_FUNCTION_INVOKE_CREDENTIAL_TOKEN_REQUIRED",
            ),
        ):
            invoke.function_invocation_token_from_env()

    def test_invalid_invoke_secret_fails_closed_without_masking(self) -> None:
        invalid_values = (
            "short",
            " synthetic-invoke-authority",
            "synthetic invoke authority",
            "synthetic-invoke-authority\n",
            "токен-не-ascii-123456",
        )
        for value in invalid_values:
            with self.subTest(value=repr(value)):
                with (
                    mock.patch.dict(
                        invoke.os.environ,
                        {invoke._INVOKE_API_TOKEN_ENV: value},
                        clear=True,
                    ),
                    mock.patch.object(builds, "_mask") as mask,
                    self.assertRaisesRegex(
                        builds.BootstrapStopped,
                        "CLOUDFLARE_CF_D_NEON_FUNCTION_INVOKE_CREDENTIAL_TOKEN_INVALID",
                    ),
                ):
                    invoke.function_invocation_token_from_env()
                mask.assert_not_called()

    def test_invoke_secret_must_not_equal_management_secret(self) -> None:
        with (
            mock.patch.dict(
                invoke.os.environ,
                {
                    invoke._INVOKE_API_TOKEN_ENV: _INVOKE_TOKEN,
                    invoke._MANAGEMENT_API_TOKEN_ENV: _INVOKE_TOKEN,
                },
                clear=True,
            ),
            mock.patch.object(builds, "_mask") as mask,
            self.assertRaisesRegex(
                builds.BootstrapStopped,
                "CLOUDFLARE_CF_D_NEON_FUNCTION_INVOKE_CREDENTIAL_TOKEN_ROLE_COLLISION",
            ),
        ):
            invoke.function_invocation_token_from_env()
        mask.assert_not_called()

    def test_legacy_project_authority_adapter_loads_no_management_secret(self) -> None:
        with mock.patch.object(builds, "_required_env") as required:
            self.assertEqual(
                invoke.project_invocation_authority_from_env(),
                ("", ""),
            )
        required.assert_not_called()

    def test_context_yields_only_preprovisioned_invoke_secret(self) -> None:
        with (
            mock.patch.dict(
                invoke.os.environ,
                {invoke._INVOKE_API_TOKEN_ENV: _INVOKE_TOKEN},
                clear=True,
            ),
            mock.patch.object(builds, "_mask") as mask,
        ):
            with invoke.function_invocation_credential(
                _PROJECT_TOKEN,
                _PROJECT_ID,
                _BRANCH_ID,
            ) as token:
                self.assertEqual(token, _INVOKE_TOKEN)
        mask.assert_called_once_with(_INVOKE_TOKEN)

    def test_release_helper_contains_no_branch_credential_crud(self) -> None:
        source = Path(invoke.__file__).read_text(encoding="utf-8")
        self.assertNotIn("/credentials", source)
        self.assertNotIn("http.client", source)
        self.assertNotIn("issue_function_invocation_credential", source)
        self.assertNotIn("revoke_function_invocation_credential", source)
        self.assertNotIn("cleanup_managed_function_invocation_credentials", source)
        self.assertIn("NEON_FUNCTION_INVOKE_API_TOKEN", source)


if __name__ == "__main__":
    unittest.main()
