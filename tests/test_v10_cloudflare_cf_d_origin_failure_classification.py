from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import scripts.bootstrap_v10_cloudflare_builds as builds
import scripts.sync_v10_cloudflare_cf_d_bootstrap_origin as custody


_EXPECTED_SHA = "a" * 40
_STAGING_ORIGIN = "https://omni-cio-v10-web-staging.example.workers.dev"
_SYNC_VALUE = "b" * 64
_BOOTSTRAP_ORIGIN = (
    "https://br-example1234-cfdprodbootstrap.compute."
    "c-6.eu-central-1.aws.neon.tech/"
)


class _Response:
    def __init__(
        self,
        status: int,
        *,
        payload: object | None = None,
        raw: bytes | None = None,
        content_type: str = "application/json",
    ) -> None:
        self.status = status
        if raw is not None:
            self.body = raw
        elif payload is not None:
            self.body = json.dumps(payload).encode("utf-8")
        else:
            self.body = b""
        self.content_type = content_type

    def getheader(self, name: str, default: str = "") -> str:
        if name.lower() == "content-type":
            return self.content_type or default
        return default

    def read(self, limit: int) -> bytes:
        return self.body[:limit]


class CloudflareCfDOriginFailureClassificationTests(unittest.TestCase):
    def test_502_preserves_only_allowlisted_worker_derivation_codes(self) -> None:
        for code in custody._ORIGIN_SYNC_DERIVATION_CODES:
            with self.subTest(code=code):
                response = _Response(502, payload={"detail": code})
                self.assertEqual(
                    custody._origin_sync_failure_code(response, 502),
                    code,
                )

        response = _Response(
            502,
            payload={"detail": "UNTRUSTED_INTERNAL_DETAIL"},
        )
        self.assertEqual(
            custody._origin_sync_failure_code(response, 502),
            custody._ORIGIN_SYNC_DERIVATION_FAILED,
        )

    def test_502_malformed_or_non_json_body_fails_closed(self) -> None:
        malformed = _Response(502, raw=b"{", content_type="application/json")
        with self.assertRaisesRegex(
            builds.BootstrapStopped,
            custody._ORIGIN_SYNC_RESPONSE_INVALID,
        ) as raised:
            custody._origin_sync_failure_code(malformed, 502)
        self.assertEqual(raised.exception.status, 502)

        non_json = _Response(502, raw=b"ignored", content_type="text/plain")
        self.assertEqual(
            custody._origin_sync_failure_code(non_json, 502),
            custody._ORIGIN_SYNC_DERIVATION_FAILED,
        )

    def test_retry_policy_contains_only_explicit_transient_classes(self) -> None:
        self.assertEqual(
            custody._ORIGIN_SYNC_RETRYABLE,
            frozenset(
                {
                    custody._NEON_BRANCH_LOOKUP_FAILED,
                    custody._NEON_BRANCH_LOOKUP_NOT_READY,
                    custody._ORIGIN_SYNC_STAGING_NOT_READY,
                    custody._ORIGIN_SYNC_UNAVAILABLE,
                }
            ),
        )
        for permanent in (
            custody._ORIGIN_SYNC_DERIVATION_FAILED,
            custody._RUNTIME_DATABASE_INVALID,
            custody._NEON_DESTINATION_REJECTED,
            custody._NEON_BRANCH_LOOKUP_UNAUTHORIZED,
            custody._NEON_BRANCH_LOOKUP_NOT_FOUND,
            custody._NEON_BRANCH_LOOKUP_HTTP_STATUS_INVALID,
            custody._NEON_BRANCH_RESPONSE_TOO_LARGE,
            custody._NEON_BRANCH_RESPONSE_INVALID,
            custody._BOOTSTRAP_ORIGIN_INVALID,
            custody._BOOTSTRAP_ORIGIN_MISMATCH,
        ):
            with self.subTest(permanent=permanent):
                self.assertNotIn(permanent, custody._ORIGIN_SYNC_RETRYABLE)

    def test_transient_derivation_failure_retries_once_then_succeeds(self) -> None:
        with (
            patch.object(
                custody,
                "_fetch_bootstrap_origin_once",
                side_effect=[
                    builds.BootstrapStopped(custody._NEON_BRANCH_LOOKUP_NOT_READY),
                    _BOOTSTRAP_ORIGIN,
                ],
            ) as fetch_once,
            patch.object(custody.time, "sleep") as sleep,
        ):
            actual = custody._fetch_bootstrap_origin(
                _STAGING_ORIGIN,
                _EXPECTED_SHA,
                _SYNC_VALUE,
            )
        self.assertEqual(actual, _BOOTSTRAP_ORIGIN)
        self.assertEqual(fetch_once.call_count, 2)
        sleep.assert_called_once_with(custody._RETRY_DELAY_SECONDS)

    def test_permanent_derivation_failure_is_not_retried(self) -> None:
        with (
            patch.object(
                custody,
                "_fetch_bootstrap_origin_once",
                side_effect=builds.BootstrapStopped(
                    custody._NEON_BRANCH_LOOKUP_UNAUTHORIZED
                ),
            ) as fetch_once,
            patch.object(custody.time, "sleep") as sleep,
        ):
            with self.assertRaisesRegex(
                builds.BootstrapStopped,
                custody._NEON_BRANCH_LOOKUP_UNAUTHORIZED,
            ):
                custody._fetch_bootstrap_origin(
                    _STAGING_ORIGIN,
                    _EXPECTED_SHA,
                    _SYNC_VALUE,
                )
        self.assertEqual(fetch_once.call_count, 1)
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
