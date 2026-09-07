from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import json
from typing import Any, cast
import unittest
from unittest.mock import patch

import scripts.bootstrap_v10_cloudflare_builds as builds
import scripts.sync_v10_cloudflare_cf_d_bootstrap_origin as custody


_EXPECTED_SHA = "a" * 40
_ACCOUNT_ID = "b" * 32
_STAGING_ORIGIN = "https://omni-cio-v10-web-staging.example.workers.dev"
_BOOTSTRAP_ORIGIN = (
    "https://br-example1234-cfdprodbootstrap.compute."
    "c-6.eu-central-1.aws.neon.tech/"
)
_SYNC_TOKEN = "c" * 64
_ROOT = Path(__file__).resolve().parents[1]
_INDEX_SOURCE = _ROOT / "cloudflare/src/index.js"
_GATED_RUNNER_SOURCE = _ROOT / "scripts/run_v10_cloudflare_gated_candidate.py"
_CONTRACT = (
    _ROOT / "docs/architecture/V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json"
)


class _Api:
    account_id = _ACCOUNT_ID

    def __init__(self, *, cleanup_failure: bool = False) -> None:
        self.calls: list[tuple[str, str, object | None]] = []
        self.cleanup_failure = cleanup_failure
        self.delete_calls = 0
        self.secret_types: dict[str, str] = {}

    def request(
        self,
        method: str,
        path: str,
        *,
        body: object | None = None,
        expected: frozenset[int] = frozenset({200}),
        timeout: float = 30.0,
    ) -> Any:
        del expected, timeout
        self.calls.append((method, path, body))
        if method == "DELETE":
            self.delete_calls += 1
            if self.cleanup_failure and self.delete_calls == 2:
                raise builds.BootstrapStopped("CLOUDFLARE_API_NETWORK_ERROR")
            self.secret_types.pop(path.rsplit("/", 1)[-1], None)
            return None
        if method == "GET":
            return [
                {"name": name, "type": secret_type}
                for name, secret_type in self.secret_types.items()
            ]
        if method == "PUT":
            if not isinstance(body, dict):
                raise AssertionError("secret body must be a mapping")
            name = body.get("name")
            secret_type = body.get("type")
            if not isinstance(name, str) or secret_type != "secret_text":
                raise AssertionError("invalid secret body")
            self.secret_types[name] = secret_type
            return None
        raise AssertionError(f"unexpected request: {method} {path}")


class _HttpResponse:
    def __init__(
        self,
        status: int,
        *,
        body: bytes = b"",
        content_type: str = "",
    ) -> None:
        self.status = status
        self.body = body
        self.content_type = content_type

    def getheader(self, name: str, default: str = "") -> str:
        if name.lower() == "content-type":
            return self.content_type or default
        return default

    def read(self, limit: int) -> bytes:
        return self.body[:limit]


class _HttpConnection:
    def __init__(self, response: _HttpResponse | int) -> None:
        self.response = (
            _HttpResponse(response) if isinstance(response, int) else response
        )
        self.closed = False
        self.requests: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def request(self, *args, **kwargs) -> None:
        self.requests.append((args, kwargs))

    def getresponse(self) -> _HttpResponse:
        return self.response

    def close(self) -> None:
        self.closed = True


def _release_payload(source_sha: str = _EXPECTED_SHA) -> bytes:
    return json.dumps(
        {
            "status": "ok",
            "platform": "cloudflare",
            "source_sha": source_sha,
            "backend": "container",
            "static_assets": True,
            "public_multi_user_enabled": False,
            "real_trading_enabled": False,
        }
    ).encode("utf-8")


class CloudflareCfDBootstrapOriginCustodyTests(unittest.TestCase):
    @staticmethod
    def _run_lifecycle(
        api: _Api,
        *,
        fetch_error: builds.BootstrapStopped | None = None,
    ) -> str:
        fetch_options: dict[str, object]
        if fetch_error is None:
            fetch_options = {"return_value": _BOOTSTRAP_ORIGIN}
        else:
            fetch_options = {"side_effect": fetch_error}
        output = StringIO()
        with (
            patch.object(custody.secrets, "token_hex", return_value=_SYNC_TOKEN),
            patch.object(custody.builds, "_mask"),
            patch.object(custody, "_fetch_bootstrap_origin", **fetch_options),
            redirect_stdout(output),
        ):
            with custody.bootstrap_origin_sync_token(
                cast(builds.CloudflareApi, api)
            ) as token:
                bootstrap_origin = custody.fetch_bootstrap_origin_custody(
                    staging_origin=_STAGING_ORIGIN,
                    expected_sha=_EXPECTED_SHA,
                    token=token,
                )
            custody.persist_bootstrap_origin_custody(
                cast(builds.CloudflareApi, api),
                bootstrap_origin,
            )
        return output.getvalue()

    def test_release_contract_requires_version_bound_ephemeral_origin_custody(
        self,
    ) -> None:
        contract = json.loads(_CONTRACT.read_text(encoding="utf-8"))
        candidate = contract["candidate"]
        self.assertEqual(
            candidate["staging_bootstrap_origin_binding"],
            custody._BOOTSTRAP_ORIGIN_BINDING,
        )
        self.assertEqual(
            candidate["staging_bootstrap_origin_custody_path"],
            custody._CUSTODY_PATH,
        )
        self.assertEqual(
            candidate["staging_bootstrap_origin_sync_token_binding"],
            custody._SYNC_TOKEN_BINDING,
        )
        self.assertIs(
            candidate["staging_bootstrap_origin_sync_token_persistence_allowed"],
            False,
        )
        self.assertIs(
            candidate["staging_bootstrap_origin_neon_management_api_required"],
            False,
        )
        for field in (
            "staging_bootstrap_origin_sync_token_armed_before_exact_build",
            "staging_bootstrap_origin_custody_after_exact_build_success",
            "staging_bootstrap_origin_no_secret_mutation_between_build_and_custody",
            "staging_bootstrap_origin_persist_after_sync_token_cleanup",
            "staging_pre_custody_single_active_version_required",
            "staging_pre_custody_exact_sha_release_probe_required",
            "staging_post_custody_exact_sha_live_revalidation_required",
            "staging_origin_sync_http_status_classification_required",
        ):
            with self.subTest(field=field):
                self.assertIs(candidate[field], True)
        self.assertIs(
            contract["fail_closed"][
                "stale_staging_bootstrap_origin_sync_token_is_success"
            ],
            False,
        )

    def test_gated_runner_arms_token_and_attests_release_before_custody(self) -> None:
        source = _GATED_RUNNER_SOURCE.read_text(encoding="utf-8")
        markers = (
            "with bootstrap_origin_sync_token(api) as sync_token:",
            "build_uuid = _start_exact_manual_build(",
            "builds._wait_build(api, build_uuid, sha)",
            "_staging_active_version_id(api)",
            "assert_staging_exact_release(url, sha)",
            "bootstrap_origin = fetch_bootstrap_origin_custody(",
            "persist_bootstrap_origin_custody(api, bootstrap_origin)",
            "quarantine_staging_autobuild(api, expected_sha=sha, verify_head=False)",
        )
        positions = tuple(source.index(marker) for marker in markers)
        self.assertEqual(positions, tuple(sorted(positions)))
        between_build_and_custody = source[positions[2] : positions[5]]
        self.assertNotIn("put_staging_secret(", between_build_and_custody)
        self.assertNotIn("delete_staging_secret(", between_build_and_custody)
        self.assertNotIn("sync_bootstrap_origin_custody", source)

    def test_custody_route_stays_in_worker_before_container_proxy(self) -> None:
        source = _INDEX_SOURCE.read_text(encoding="utf-8")
        custody_route = source.index(
            "url.pathname === CF_D_BOOTSTRAP_ORIGIN_CUSTODY_PATH"
        )
        generic_api_route = source.index(
            'url.pathname === "/healthz" || url.pathname.startsWith("/api/")'
        )
        self.assertLess(custody_route, generic_api_route)
        self.assertNotIn(custody._SYNC_TOKEN_BINDING, source)

    def test_staging_origin_is_exact_worker_scope(self) -> None:
        self.assertEqual(
            custody._staging_origin(_STAGING_ORIGIN),
            _STAGING_ORIGIN,
        )
        for value in (
            "http://omni-cio-v10-web-staging.example.workers.dev",
            "https://other.example.workers.dev",
            "https://omni-cio-v10-web-staging.example.workers.dev/path",
            "https://omni-cio-v10-web-staging.example.workers.dev?query=1",
        ):
            with self.subTest(value=value):
                with self.assertRaises(builds.BootstrapStopped):
                    custody._staging_origin(value)

    def test_bootstrap_origin_validation_is_bounded(self) -> None:
        self.assertEqual(
            custody._bootstrap_origin(_BOOTSTRAP_ORIGIN),
            _BOOTSTRAP_ORIGIN,
        )
        for value in (
            "https://example.com/",
            (
                "http://br-example1234-cfdprodbootstrap.compute."
                "c-6.eu-central-1.aws.neon.tech/"
            ),
            (
                "https://br-example1234-cfdprodbootstrap.compute."
                "c-9.us-east-1.aws.neon.tech/"
            ),
            _BOOTSTRAP_ORIGIN + "path",
        ):
            with self.subTest(value=value):
                with self.assertRaises(builds.BootstrapStopped):
                    custody._bootstrap_origin(value)

    def test_sync_token_validation_requires_fresh_256_bit_hex(self) -> None:
        self.assertEqual(custody._sync_token(_SYNC_TOKEN), _SYNC_TOKEN)
        for value in ("", "c" * 63, "g" * 64, "c" * 65):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    builds.BootstrapStopped,
                    "CLOUDFLARE_CF_D_ORIGIN_SYNC_TOKEN_INVALID",
                ):
                    custody._sync_token(value)

    def test_lifecycle_arms_before_proof_and_removes_token_before_persisting_origin(
        self,
    ) -> None:
        api = _Api()
        log = self._run_lifecycle(api)
        operations = [(method, body) for method, _path, body in api.calls]
        self.assertEqual(
            operations,
            [
                ("DELETE", None),
                (
                    "PUT",
                    {
                        "name": custody._SYNC_TOKEN_BINDING,
                        "text": _SYNC_TOKEN,
                        "type": "secret_text",
                    },
                ),
                ("GET", None),
                ("DELETE", None),
                ("GET", None),
                ("GET", None),
                (
                    "PUT",
                    {
                        "name": custody._BOOTSTRAP_ORIGIN_BINDING,
                        "text": _BOOTSTRAP_ORIGIN,
                        "type": "secret_text",
                    },
                ),
                ("GET", None),
                ("GET", None),
            ],
        )
        self.assertIn("CLOUDFLARE_CF_D_ORIGIN_SYNC_TOKEN=ARMED_BEFORE_EXACT_BUILD", log)
        self.assertIn("CLOUDFLARE_CF_D_BOOTSTRAP_ORIGIN_CUSTODY=READY", log)
        self.assertNotIn(_SYNC_TOKEN, log)
        self.assertNotIn(_BOOTSTRAP_ORIGIN, log)

    def test_fetch_failure_still_removes_ephemeral_token(self) -> None:
        api = _Api()
        with self.assertRaisesRegex(
            builds.BootstrapStopped,
            "CLOUDFLARE_CF_D_ORIGIN_SYNC_UNAVAILABLE",
        ):
            self._run_lifecycle(
                api,
                fetch_error=builds.BootstrapStopped(
                    "CLOUDFLARE_CF_D_ORIGIN_SYNC_UNAVAILABLE"
                ),
            )
        self.assertEqual(
            [call[0] for call in api.calls],
            ["DELETE", "PUT", "GET", "DELETE", "GET"],
        )
        self.assertNotIn(custody._SYNC_TOKEN_BINDING, api.secret_types)
        self.assertNotIn(custody._BOOTSTRAP_ORIGIN_BINDING, api.secret_types)

    def test_cleanup_failure_blocks_persistent_origin_write(self) -> None:
        api = _Api(cleanup_failure=True)
        with self.assertRaisesRegex(
            builds.BootstrapStopped,
            "CLOUDFLARE_CF_D_ORIGIN_SYNC_TOKEN_CLEANUP_FAILED",
        ):
            self._run_lifecycle(api)
        self.assertEqual(
            [call[0] for call in api.calls],
            ["DELETE", "PUT", "GET", "DELETE"],
        )
        self.assertNotIn(custody._BOOTSTRAP_ORIGIN_BINDING, api.secret_types)

    def test_pre_custody_release_requires_exact_sha_and_protected_flags(self) -> None:
        response = _HttpResponse(
            200,
            body=_release_payload(),
            content_type="application/json; charset=utf-8",
        )
        connection = _HttpConnection(response)
        with patch.object(
            custody.http.client,
            "HTTPSConnection",
            return_value=connection,
        ):
            custody._fetch_exact_release_once(_STAGING_ORIGIN, _EXPECTED_SHA)
        self.assertTrue(connection.closed)
        self.assertEqual(connection.requests[0][0][0:2], ("GET", custody._RELEASE_PATH))

        mismatch = _HttpConnection(
            _HttpResponse(
                200,
                body=_release_payload("b" * 40),
                content_type="application/json",
            )
        )
        with patch.object(
            custody.http.client,
            "HTTPSConnection",
            return_value=mismatch,
        ):
            with self.assertRaisesRegex(
                builds.BootstrapStopped,
                "CLOUDFLARE_CF_D_PRE_CUSTODY_RELEASE_SHA_MISMATCH",
            ):
                custody._fetch_exact_release_once(_STAGING_ORIGIN, _EXPECTED_SHA)

    def test_pre_custody_release_retries_only_bounded_readiness_states(self) -> None:
        with (
            patch.object(
                custody,
                "_fetch_exact_release_once",
                side_effect=[
                    builds.BootstrapStopped(
                        "CLOUDFLARE_CF_D_PRE_CUSTODY_RELEASE_SHA_MISMATCH"
                    ),
                    None,
                ],
            ) as fetch_once,
            patch.object(custody.time, "sleep") as sleep,
        ):
            custody.assert_staging_exact_release(_STAGING_ORIGIN, _EXPECTED_SHA)
        self.assertEqual(fetch_once.call_count, 2)
        sleep.assert_called_once_with(custody._RETRY_DELAY_SECONDS)

    def test_origin_sync_preserves_sanitized_http_failure_class(self) -> None:
        cases = {
            403: "CLOUDFLARE_CF_D_ORIGIN_SYNC_UNAUTHORIZED",
            404: "CLOUDFLARE_CF_D_ORIGIN_SYNC_NOT_FOUND",
            502: "CLOUDFLARE_CF_D_ORIGIN_SYNC_DERIVATION_FAILED",
            503: "CLOUDFLARE_CF_D_ORIGIN_SYNC_STAGING_NOT_READY",
            418: "CLOUDFLARE_CF_D_ORIGIN_SYNC_HTTP_STATUS_INVALID",
        }
        for status, code in cases.items():
            with self.subTest(status=status):
                connection = _HttpConnection(status)
                with patch.object(
                    custody.http.client,
                    "HTTPSConnection",
                    return_value=connection,
                ):
                    with self.assertRaises(builds.BootstrapStopped) as raised:
                        custody._fetch_bootstrap_origin_once(
                            _STAGING_ORIGIN,
                            _EXPECTED_SHA,
                            _SYNC_TOKEN,
                        )
                self.assertEqual(raised.exception.code, code)
                self.assertEqual(raised.exception.status, status)
                self.assertTrue(connection.closed)

    def test_origin_fetch_retries_only_explicit_transient_states(self) -> None:
        for code in custody._ORIGIN_SYNC_RETRYABLE:
            with self.subTest(code=code):
                with (
                    patch.object(
                        custody,
                        "_fetch_bootstrap_origin_once",
                        side_effect=[
                            builds.BootstrapStopped(code),
                            _BOOTSTRAP_ORIGIN,
                        ],
                    ) as fetch_once,
                    patch.object(custody.time, "sleep") as sleep,
                ):
                    actual = custody._fetch_bootstrap_origin(
                        _STAGING_ORIGIN,
                        _EXPECTED_SHA,
                        _SYNC_TOKEN,
                    )
                self.assertEqual(actual, _BOOTSTRAP_ORIGIN)
                self.assertEqual(fetch_once.call_count, 2)
                sleep.assert_called_once_with(custody._RETRY_DELAY_SECONDS)

        for code in (
            "CLOUDFLARE_CF_D_ORIGIN_SYNC_UNAUTHORIZED",
            "CLOUDFLARE_CF_D_ORIGIN_SYNC_NOT_FOUND",
            "CLOUDFLARE_CF_D_ORIGIN_SYNC_HTTP_STATUS_INVALID",
        ):
            with self.subTest(non_retryable=code):
                with (
                    patch.object(
                        custody,
                        "_fetch_bootstrap_origin_once",
                        side_effect=builds.BootstrapStopped(code),
                    ) as fetch_once,
                    patch.object(custody.time, "sleep") as sleep,
                ):
                    with self.assertRaises(builds.BootstrapStopped):
                        custody._fetch_bootstrap_origin(
                            _STAGING_ORIGIN,
                            _EXPECTED_SHA,
                            _SYNC_TOKEN,
                        )
                self.assertEqual(fetch_once.call_count, 1)
                sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
