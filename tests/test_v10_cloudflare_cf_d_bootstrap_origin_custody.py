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
_CONTRACT = (
    _ROOT / "docs/architecture/V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json"
)


class _Api:
    account_id = _ACCOUNT_ID

    def __init__(self, *, cleanup_failure: bool = False) -> None:
        self.calls: list[tuple[str, str, object | None]] = []
        self.cleanup_failure = cleanup_failure
        self.delete_calls = 0

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
            return None
        if method == "GET":
            return [
                {
                    "name": custody._BOOTSTRAP_ORIGIN_BINDING,
                    "type": "secret_text",
                }
            ]
        if method == "PUT":
            return None
        raise AssertionError(f"unexpected request: {method} {path}")


class CloudflareCfDBootstrapOriginCustodyTests(unittest.TestCase):
    def test_release_contract_requires_ephemeral_origin_custody(self) -> None:
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
        self.assertIs(
            contract["fail_closed"][
                "stale_staging_bootstrap_origin_sync_token_is_success"
            ],
            False,
        )

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

    def test_sync_removes_ephemeral_token_before_persisting_origin(self) -> None:
        api = _Api()
        output = StringIO()
        with (
            patch.object(custody.secrets, "token_hex", return_value=_SYNC_TOKEN),
            patch.object(custody.builds, "_mask"),
            patch.object(
                custody,
                "_fetch_bootstrap_origin",
                return_value=_BOOTSTRAP_ORIGIN,
            ),
            redirect_stdout(output),
        ):
            custody.sync_bootstrap_origin_custody(
                cast(builds.CloudflareApi, api),
                staging_origin=_STAGING_ORIGIN,
                expected_sha=_EXPECTED_SHA,
            )

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
                ("DELETE", None),
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
        log = output.getvalue()
        self.assertIn("CLOUDFLARE_CF_D_BOOTSTRAP_ORIGIN_CUSTODY=READY", log)
        self.assertNotIn(_SYNC_TOKEN, log)
        self.assertNotIn(_BOOTSTRAP_ORIGIN, log)

    def test_fetch_failure_still_removes_ephemeral_token(self) -> None:
        api = _Api()
        with (
            patch.object(custody.secrets, "token_hex", return_value=_SYNC_TOKEN),
            patch.object(custody.builds, "_mask"),
            patch.object(
                custody,
                "_fetch_bootstrap_origin",
                side_effect=builds.BootstrapStopped(
                    "CLOUDFLARE_CF_D_ORIGIN_SYNC_UNAVAILABLE"
                ),
            ),
        ):
            with self.assertRaisesRegex(
                builds.BootstrapStopped,
                "CLOUDFLARE_CF_D_ORIGIN_SYNC_UNAVAILABLE",
            ):
                custody.sync_bootstrap_origin_custody(
                    cast(builds.CloudflareApi, api),
                    staging_origin=_STAGING_ORIGIN,
                    expected_sha=_EXPECTED_SHA,
                )

        self.assertEqual([call[0] for call in api.calls], ["DELETE", "PUT", "DELETE"])

    def test_cleanup_failure_blocks_persistent_origin_write(self) -> None:
        api = _Api(cleanup_failure=True)
        with (
            patch.object(custody.secrets, "token_hex", return_value=_SYNC_TOKEN),
            patch.object(custody.builds, "_mask"),
            patch.object(
                custody,
                "_fetch_bootstrap_origin",
                return_value=_BOOTSTRAP_ORIGIN,
            ),
        ):
            with self.assertRaisesRegex(
                builds.BootstrapStopped,
                "CLOUDFLARE_CF_D_ORIGIN_SYNC_TOKEN_CLEANUP_FAILED",
            ):
                custody.sync_bootstrap_origin_custody(
                    cast(builds.CloudflareApi, api),
                    staging_origin=_STAGING_ORIGIN,
                    expected_sha=_EXPECTED_SHA,
                )

        self.assertEqual([call[0] for call in api.calls], ["DELETE", "PUT", "DELETE"])

    def test_origin_fetch_retries_only_bounded_transient_states(self) -> None:
        with (
            patch.object(
                custody,
                "_fetch_bootstrap_origin_once",
                side_effect=[
                    builds.BootstrapStopped(
                        "CLOUDFLARE_CF_D_ORIGIN_SYNC_REJECTED"
                    ),
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
        sleep.assert_called_once_with(2)


if __name__ == "__main__":
    unittest.main()
