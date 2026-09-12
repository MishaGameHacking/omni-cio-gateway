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
_S3_SECRET = "nsk_live_" + "a" * 64
_TOKEN_ID = "nak_live_0123456789abcdef0123456789abcdef"
_MANUAL_NAME = "omni-cio-cf-d-release-manual"


def _empty_list_response() -> bytes:
    return b'{"credentials":[]}'


def _managed_meta(*, scopes: list[str] | None = None) -> dict[str, object]:
    return {
        "token_id": _TOKEN_ID,
        "name": "omni-cio-cf-d-release-123-1",
        "scopes": scopes if scopes is not None else ["functions:invoke"],
        "branch_id": _BRANCH_ID,
        "principal_type": "user",
        "created_at": "2026-09-12T00:00:00Z",
    }


def _create_response(
    *,
    branch_id: str = _BRANCH_ID,
    name: str = _MANUAL_NAME,
    scopes: list[str] | None = None,
    s3_secret_access_key: str = _S3_SECRET,
) -> bytes:
    return json.dumps(
        {
            "token_id": _TOKEN_ID,
            "token_id_short": "0123456789ab",
            "name": name,
            "api_token": _INVOKE_TOKEN,
            "s3_secret_access_key": s3_secret_access_key,
            "scopes": scopes if scopes is not None else ["functions:invoke"],
            "branch_id": branch_id,
            "created_at": "2026-09-12T00:00:00Z",
        },
        separators=(",", ":"),
    ).encode("utf-8")


class NeonFunctionInvocationCredentialTests(unittest.TestCase):
    @staticmethod
    def _raise_inside_invocation_context() -> None:
        with invoke.function_invocation_credential(
            _PROJECT_TOKEN,
            _PROJECT_ID,
            _BRANCH_ID,
        ):
            raise RuntimeError("boom")

    @staticmethod
    def _issue_credential(
        *,
        run_id: str = "",
        run_attempt: str = "",
    ) -> invoke.FunctionInvocationCredential:
        with mock.patch.dict(
            invoke.os.environ,
            {
                "GITHUB_RUN_ID": run_id,
                "GITHUB_RUN_ATTEMPT": run_attempt,
            },
            clear=False,
        ):
            return invoke.issue_function_invocation_credential(
                _PROJECT_TOKEN,
                _PROJECT_ID,
                _BRANCH_ID,
            )

    @staticmethod
    def _cleanup_managed_credentials() -> int:
        return invoke.cleanup_managed_function_invocation_credentials(
            _PROJECT_TOKEN,
            _PROJECT_ID,
            _BRANCH_ID,
        )

    @staticmethod
    def _revoke_with_reconciliation() -> None:
        invoke._revoke_with_reconciliation(
            _PROJECT_TOKEN,
            _PROJECT_ID,
            _BRANCH_ID,
            _TOKEN_ID,
        )

    def test_issue_requests_only_function_invoke_scope_and_masks_all_secrets(
        self,
    ) -> None:
        observed: dict[str, object] = {}

        def request(
            method: str,
            path: str,
            token: str,
            *,
            body: bytes | None = None,
        ) -> tuple[int, bytes]:
            if method == "GET":
                return 200, _empty_list_response()
            observed.update(method=method, path=path, token=token, body=body)
            return 201, _create_response(name="omni-cio-cf-d-release-123-1")

        with (
            mock.patch.object(invoke, "_request", side_effect=request),
            mock.patch.object(builds, "_mask") as mask,
        ):
            credential = self._issue_credential(run_id="123", run_attempt="1")

        self.assertEqual(credential.token_id, _TOKEN_ID)
        self.assertEqual(credential.api_token, _INVOKE_TOKEN)
        self.assertEqual(observed["method"], "POST")
        self.assertIn("/credentials", str(observed["path"]))
        self.assertEqual(observed["token"], _PROJECT_TOKEN)
        payload = json.loads(bytes(observed["body"]).decode("utf-8"))
        self.assertEqual(payload["name"], "omni-cio-cf-d-release-123-1")
        self.assertEqual(payload["scopes"], ["functions:invoke"])
        self.assertEqual(payload["principal_type"], "user")
        self.assertEqual(
            mask.call_args_list,
            [mock.call(_INVOKE_TOKEN), mock.call(_S3_SECRET)],
        )

    def test_issue_rejects_broader_mismatched_or_unlabeled_credential(self) -> None:
        payloads = (
            _create_response(scopes=["functions:invoke", "storage:read"]),
            _create_response(branch_id="br-other1234"),
            _create_response(name="provider-mutated-name"),
        )
        for payload in payloads:
            with (
                mock.patch.object(
                    invoke,
                    "_request",
                    side_effect=[
                        (200, _empty_list_response()),
                        (201, payload),
                        (204, b""),
                        (200, _empty_list_response()),
                    ],
                ),
                self.assertRaisesRegex(
                    builds.BootstrapStopped,
                    "CLOUDFLARE_CF_D_NEON_FUNCTION_INVOKE_CREDENTIAL_RESPONSE_INVALID",
                ),
            ):
                self._issue_credential()

    def test_invalid_created_response_masks_secrets_and_revokes_known_token(
        self,
    ) -> None:
        calls: list[str] = []

        def request(
            method: str,
            path: str,
            token: str,
            *,
            body: bytes | None = None,
        ) -> tuple[int, bytes]:
            del path, token, body
            calls.append(method)
            if calls == ["GET"]:
                return 200, _empty_list_response()
            if calls == ["GET", "POST"]:
                return 201, _create_response(name="provider-mutated-name")
            if method == "DELETE":
                return 204, b""
            if method == "GET":
                return 200, _empty_list_response()
            raise AssertionError(method)

        with (
            mock.patch.object(invoke, "_request", side_effect=request),
            mock.patch.object(builds, "_mask") as mask,
            self.assertRaisesRegex(
                builds.BootstrapStopped,
                "CLOUDFLARE_CF_D_NEON_FUNCTION_INVOKE_CREDENTIAL_RESPONSE_INVALID",
            ),
        ):
            self._issue_credential()

        self.assertEqual(calls, ["GET", "POST", "DELETE", "GET"])
        self.assertEqual(
            mask.call_args_list,
            [mock.call(_INVOKE_TOKEN), mock.call(_S3_SECRET)],
        )

    def test_issue_403_is_explicit_project_authority_failure(self) -> None:
        with (
            mock.patch.object(
                invoke,
                "_request",
                side_effect=[
                    (200, _empty_list_response()),
                    (403, b'{"provider":"redacted"}'),
                ],
            ),
            self.assertRaisesRegex(
                builds.BootstrapStopped,
                "CLOUDFLARE_CF_D_NEON_FUNCTION_INVOKE_CREDENTIAL_PROJECT_API_KEY_INSUFFICIENT",
            ),
        ):
            self._issue_credential()

    def test_issue_revokes_stale_managed_credential_before_create(self) -> None:
        list_response = json.dumps(
            {"credentials": [_managed_meta()]},
            separators=(",", ":"),
        ).encode("utf-8")
        observed: list[tuple[str, str]] = []

        def request(
            method: str,
            path: str,
            token: str,
            *,
            body: bytes | None = None,
        ) -> tuple[int, bytes]:
            del token, body
            observed.append((method, path))
            if method == "GET":
                return 200, list_response
            if method == "DELETE":
                return 204, b""
            return 201, _create_response()

        with mock.patch.object(invoke, "_request", side_effect=request):
            credential = self._issue_credential()

        self.assertEqual(credential.token_id, _TOKEN_ID)
        self.assertEqual(
            [method for method, _ in observed],
            ["GET", "DELETE", "POST"],
        )

    def test_stale_scope_drift_fails_closed_without_delete(self) -> None:
        list_response = json.dumps(
            {
                "credentials": [
                    _managed_meta(scopes=["functions:invoke", "storage:read"])
                ]
            },
            separators=(",", ":"),
        ).encode("utf-8")
        with (
            mock.patch.object(
                invoke,
                "_request",
                return_value=(200, list_response),
            ) as request,
            self.assertRaisesRegex(
                builds.BootstrapStopped,
                "CLOUDFLARE_CF_D_NEON_FUNCTION_INVOKE_CREDENTIAL_STALE_SCOPE_DRIFT",
            ),
        ):
            self._cleanup_managed_credentials()
        request.assert_called_once()

    def test_ambiguous_create_reconciles_and_stays_failed(self) -> None:
        ambiguous = builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_INVOKE_CREDENTIAL_UNAVAILABLE"
        )
        stale_response = json.dumps(
            {"credentials": [_managed_meta()]},
            separators=(",", ":"),
        ).encode("utf-8")
        calls: list[str] = []

        def request(
            method: str,
            path: str,
            token: str,
            *,
            body: bytes | None = None,
        ) -> tuple[int, bytes]:
            del path, token, body
            calls.append(method)
            if calls == ["GET"]:
                return 200, _empty_list_response()
            if calls == ["GET", "POST"]:
                raise ambiguous
            if method == "GET":
                return 200, stale_response
            if method == "DELETE":
                return 204, b""
            raise AssertionError(method)

        with (
            mock.patch.object(invoke, "_request", side_effect=request),
            self.assertRaises(builds.BootstrapStopped) as raised,
        ):
            self._issue_credential()

        self.assertIs(raised.exception, ambiguous)
        self.assertEqual(calls, ["GET", "POST", "GET", "DELETE"])

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

    def test_context_revoke_failure_reconciles_and_stays_failed(self) -> None:
        credential = invoke.FunctionInvocationCredential(
            token_id=_TOKEN_ID,
            api_token=_INVOKE_TOKEN,
        )
        revoke_failure = builds.BootstrapStopped(
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
                side_effect=revoke_failure,
            ),
            mock.patch.object(
                invoke,
                "cleanup_managed_function_invocation_credentials",
                return_value=0,
            ) as reconcile,
        ):
            with self.assertRaises(builds.BootstrapStopped) as raised:
                self._raise_inside_invocation_context()

        self.assertIs(raised.exception, revoke_failure)
        self.assertIsInstance(raised.exception.__context__, RuntimeError)
        reconcile.assert_called_once_with(
            _PROJECT_TOKEN,
            _PROJECT_ID,
            _BRANCH_ID,
        )

    def test_ambiguous_revoke_reconciles_and_stays_failed(self) -> None:
        ambiguous = builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_INVOKE_CREDENTIAL_UNAVAILABLE"
        )
        stale_response = json.dumps(
            {"credentials": [_managed_meta()]},
            separators=(",", ":"),
        ).encode("utf-8")
        calls: list[str] = []

        def request(
            method: str,
            path: str,
            token: str,
            *,
            body: bytes | None = None,
        ) -> tuple[int, bytes]:
            del path, token, body
            calls.append(method)
            if calls == ["DELETE"]:
                raise ambiguous
            if method == "GET":
                return 200, stale_response
            if method == "DELETE":
                return 204, b""
            raise AssertionError(method)

        with (
            mock.patch.object(invoke, "_request", side_effect=request),
            self.assertRaises(builds.BootstrapStopped) as raised,
        ):
            self._revoke_with_reconciliation()

        self.assertIs(raised.exception, ambiguous)
        self.assertEqual(calls, ["DELETE", "GET", "DELETE"])

    def test_revoke_reconciliation_failure_remains_blocking(self) -> None:
        primary = builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_INVOKE_CREDENTIAL_UNAVAILABLE"
        )
        secondary = builds.BootstrapStopped(
            "CLOUDFLARE_CF_D_NEON_FUNCTION_INVOKE_CREDENTIAL_LIST_REJECTED"
        )
        with (
            mock.patch.object(
                invoke,
                "revoke_function_invocation_credential",
                side_effect=primary,
            ),
            mock.patch.object(
                invoke,
                "cleanup_managed_function_invocation_credentials",
                side_effect=secondary,
            ),
            self.assertRaises(builds.BootstrapStopped) as raised,
        ):
            self._revoke_with_reconciliation()

        self.assertIs(raised.exception, secondary)
        self.assertIs(raised.exception.__context__, primary)

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
