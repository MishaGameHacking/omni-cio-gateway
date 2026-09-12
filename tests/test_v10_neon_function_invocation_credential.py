from __future__ import annotations

import json
import unittest
from unittest import mock

import scripts.bootstrap_v10_cloudflare_builds as builds
import scripts.neon_function_invocation_credential as invoke


_PROJECT_ID = "billowing-smoke-00000000"
_BRANCH_ID = "br-example1234"
_PROJECT_TOKEN = "synthetic-project-authority"
_INVOKE_TOKEN = "synthetic-invoke-authority"
_TOKEN_ID = "nak_live_0123456789abcdef0123456789abcdef"


class NeonFunctionInvocationCredentialTests(unittest.TestCase):
    @staticmethod
    def _raise_inside_invocation_context() -> None:
        with invoke.function_invocation_credential(
            _PROJECT_TOKEN,
            _PROJECT_ID,
            _BRANCH_ID,
        ):
            raise RuntimeError("boom")

    def test_issue_requests_only_function_invoke_scope_and_masks_token(self) -> None:
        response = json.dumps(
            {
                "token_id": _TOKEN_ID,
                "name": "omni-cio-cf-d-release",
                "api_token": _INVOKE_TOKEN,
                "scopes": ["functions:invoke"],
                "branch_id": _BRANCH_ID,
                "principal_type": "user",
            },
            separators=(",", ":"),
        ).encode("utf-8")
        observed: dict[str, object] = {}

        def request(
            method: str,
            path: str,
            token: str,
            *,
            body: bytes | None = None,
        ) -> tuple[int, bytes]:
            observed.update(method=method, path=path, token=token, body=body)
            return 201, response

        with (
            mock.patch.object(invoke, "_request", side_effect=request),
            mock.patch.object(builds, "_mask") as mask,
            mock.patch.dict(invoke.os.environ, {}, clear=True),
        ):
            credential = invoke.issue_function_invocation_credential(
                _PROJECT_TOKEN,
                _PROJECT_ID,
                _BRANCH_ID,
            )

        self.assertEqual(credential.token_id, _TOKEN_ID)
        self.assertEqual(credential.api_token, _INVOKE_TOKEN)
        self.assertEqual(observed["method"], "POST")
        self.assertIn("/credentials", str(observed["path"]))
        self.assertEqual(observed["token"], _PROJECT_TOKEN)
        payload = json.loads(bytes(observed["body"]).decode("utf-8"))
        self.assertEqual(payload["scopes"], ["functions:invoke"])
        self.assertEqual(payload["principal_type"], "user")
        mask.assert_called_once_with(_INVOKE_TOKEN)

    def test_issue_rejects_broader_or_mismatched_credential(self) -> None:
        for payload in (
            {
                "token_id": _TOKEN_ID,
                "api_token": _INVOKE_TOKEN,
                "scopes": ["functions:invoke", "storage:read"],
                "branch_id": _BRANCH_ID,
            },
            {
                "token_id": _TOKEN_ID,
                "api_token": _INVOKE_TOKEN,
                "scopes": ["functions:invoke"],
                "branch_id": "br-other1234",
            },
        ):
            with (
                mock.patch.object(
                    invoke,
                    "_request",
                    return_value=(201, json.dumps(payload).encode("utf-8")),
                ),
                self.assertRaisesRegex(
                    builds.BootstrapStopped,
                    "CLOUDFLARE_CF_D_NEON_FUNCTION_INVOKE_CREDENTIAL_RESPONSE_INVALID",
                ),
            ):
                invoke.issue_function_invocation_credential(
                    _PROJECT_TOKEN,
                    _PROJECT_ID,
                    _BRANCH_ID,
                )

    def test_issue_403_is_explicit_project_authority_failure(self) -> None:
        with (
            mock.patch.object(
                invoke,
                "_request",
                return_value=(403, b'{"provider":"redacted"}'),
            ),
            self.assertRaisesRegex(
                builds.BootstrapStopped,
                "CLOUDFLARE_CF_D_NEON_FUNCTION_INVOKE_CREDENTIAL_PROJECT_API_KEY_INSUFFICIENT",
            ),
        ):
            invoke.issue_function_invocation_credential(
                _PROJECT_TOKEN,
                _PROJECT_ID,
                _BRANCH_ID,
            )

    def test_context_revokes_credential_after_success(self) -> None:
        credential = invoke.FunctionInvocationCredential(
            token_id=_TOKEN_ID,
            api_token=_INVOKE_TOKEN,
        )
        with (
            mock.patch.object(
                invoke,
                "issue_function_invocation_credential",
                return_value=credential,
            ),
            mock.patch.object(
                invoke,
                "revoke_function_invocation_credential",
            ) as revoke,
        ):
            with invoke.function_invocation_credential(
                _PROJECT_TOKEN,
                _PROJECT_ID,
                _BRANCH_ID,
            ) as token:
                self.assertEqual(token, _INVOKE_TOKEN)
        revoke.assert_called_once_with(
            _PROJECT_TOKEN,
            _PROJECT_ID,
            _BRANCH_ID,
            _TOKEN_ID,
        )

    def test_context_revokes_credential_after_failure(self) -> None:
        credential = invoke.FunctionInvocationCredential(
            token_id=_TOKEN_ID,
            api_token=_INVOKE_TOKEN,
        )
        with (
            mock.patch.object(
                invoke,
                "issue_function_invocation_credential",
                return_value=credential,
            ),
            mock.patch.object(
                invoke,
                "revoke_function_invocation_credential",
            ) as revoke,
        ):
            with self.assertRaisesRegex(RuntimeError, "boom"):
                self._raise_inside_invocation_context()
        revoke.assert_called_once_with(
            _PROJECT_TOKEN,
            _PROJECT_ID,
            _BRANCH_ID,
            _TOKEN_ID,
        )

    def test_context_revoke_failure_is_fail_closed(self) -> None:
        credential = invoke.FunctionInvocationCredential(
            token_id=_TOKEN_ID,
            api_token=_INVOKE_TOKEN,
        )
        cleanup = builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_INVOKE_CREDENTIAL_REVOKE_REJECTED"
        )
        with (
            mock.patch.object(
                invoke,
                "issue_function_invocation_credential",
                return_value=credential,
            ),
            mock.patch.object(
                invoke,
                "revoke_function_invocation_credential",
                side_effect=cleanup,
            ),
        ):
            with self.assertRaises(builds.BootstrapStopped) as raised:
                self._raise_inside_invocation_context()
        self.assertIs(raised.exception, cleanup)
        self.assertIsInstance(raised.exception.__context__, RuntimeError)

    def test_revoke_is_idempotent_for_missing_provider_credential(self) -> None:
        for status in (204, 404):
            with mock.patch.object(invoke, "_request", return_value=(status, b"")):
                invoke.revoke_function_invocation_credential(
                    _PROJECT_TOKEN,
                    _PROJECT_ID,
                    _BRANCH_ID,
                    _TOKEN_ID,
                )

    def test_project_authority_is_loaded_from_exact_secret_bindings(self) -> None:
        def required(name: str) -> str:
            values = {
                invoke._PROJECT_AUTHORITY_ENV: _PROJECT_TOKEN,
                invoke._PROJECT_ID_ENV: _PROJECT_ID,
            }
            return values[name]

        with (
            mock.patch.object(builds, "_required_env", side_effect=required),
            mock.patch.object(builds, "_mask") as mask,
        ):
            self.assertEqual(
                invoke.project_invocation_authority_from_env(),
                (_PROJECT_TOKEN, _PROJECT_ID),
            )
        mask.assert_called_once_with(_PROJECT_TOKEN)


if __name__ == "__main__":
    unittest.main()
