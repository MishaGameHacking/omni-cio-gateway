from __future__ import annotations

import io
import json
import secrets
import unittest
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request

from omni_cio.contracts.v1.cloudflare_cf_d_bootstrap_failures import (
    GENERIC_STAGING_BOOTSTRAP_FAILURE,
    STAGING_BOOTSTRAP_FAILURE_CODES,
    STAGING_OUTER_FAILURE_PREFIX,
    STAGING_OUTER_FAILURE_STATUS_BY_DETAIL,
    STAGING_UNCLASSIFIED_HTTP_PREFIX,
    STAGING_UNCLASSIFIED_HTTP_STATUSES,
    classify_staging_bootstrap_failure,
    staging_unclassified_http_failure_code,
)
import scripts.bootstrap_v10_cloudflare_production_database_via_staging as runner


def _json_bytes(payload: object) -> bytes:
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def _http_error(status: int, content: bytes) -> HTTPError:
    return HTTPError(
        "https://omni-cio-v10-web-staging.example.workers.dev/bootstrap",
        status,
        "synthetic",
        None,
        io.BytesIO(content),
    )


def _request() -> Request:
    return Request(
        "https://example.invalid/bootstrap",
        data=b"{}",
        headers={"Authorization": "Bearer " + secrets.token_urlsafe(32)},
        method="POST",
    )


class CloudflareCfDStagingBootstrapBoundaryDiagnosticsTests(unittest.TestCase):
    def test_outer_source_controlled_failures_are_preserved_without_raw_context(self) -> None:
        for detail, status in STAGING_OUTER_FAILURE_STATUS_BY_DETAIL.items():
            with self.subTest(detail=detail, status=status):
                content = _json_bytes({"detail": detail})
                expected = f"{STAGING_OUTER_FAILURE_PREFIX}{detail}"
                self.assertEqual(
                    classify_staging_bootstrap_failure(status, content),
                    expected,
                )
                self.assertIn(expected, STAGING_BOOTSTRAP_FAILURE_CODES)
                self.assertEqual(
                    classify_staging_bootstrap_failure(status + 1, content),
                    GENERIC_STAGING_BOOTSTRAP_FAILURE,
                )

    def test_unclassified_http_fallback_is_status_only_and_finite(self) -> None:
        for status in sorted(STAGING_UNCLASSIFIED_HTTP_STATUSES):
            with self.subTest(status=status):
                expected = f"{STAGING_UNCLASSIFIED_HTTP_PREFIX}{status}_UNCLASSIFIED"
                self.assertEqual(staging_unclassified_http_failure_code(status), expected)
                self.assertIn(expected, STAGING_BOOTSTRAP_FAILURE_CODES)
        self.assertEqual(
            staging_unclassified_http_failure_code(418),
            GENERIC_STAGING_BOOTSTRAP_FAILURE,
        )
        self.assertEqual(
            staging_unclassified_http_failure_code("not-a-status"),
            GENERIC_STAGING_BOOTSTRAP_FAILURE,
        )

    def test_runner_preserves_known_outer_detail_at_real_request_boundary(self) -> None:
        detail = "CLOUDFLARE_EDGE_ROUTE_REJECTED"
        status = STAGING_OUTER_FAILURE_STATUS_BY_DETAIL[detail]
        opener = mock.Mock()
        opener.open.side_effect = _http_error(status, _json_bytes({"detail": detail}))
        request = _request()
        with mock.patch.object(runner, "_OPENER", opener):
            with self.assertRaises(runner.BootstrapStopped) as stopped:
                runner._request_staging_bootstrap_json(request)
        self.assertEqual(
            stopped.exception.code,
            f"{STAGING_OUTER_FAILURE_PREFIX}{detail}",
        )

    def test_runner_unknown_body_reports_status_only_without_reflection(self) -> None:
        raw_details = (
            (400, b"Invalid host header with synthetic-request-id"),
            (500, b"Internal server error synthetic-private-detail"),
            (502, _json_bytes({"detail": "UNTRUSTED_STAGING_DETAIL"})),
            (530, b"provider-specific opaque response synthetic-account-id"),
        )
        for status, content in raw_details:
            with self.subTest(status=status):
                opener = mock.Mock()
                opener.open.side_effect = _http_error(status, content)
                request = _request()
                with mock.patch.object(runner, "_OPENER", opener):
                    with self.assertRaises(runner.BootstrapStopped) as stopped:
                        runner._request_staging_bootstrap_json(request)
                self.assertEqual(
                    stopped.exception.code,
                    f"{STAGING_UNCLASSIFIED_HTTP_PREFIX}{status}_UNCLASSIFIED",
                )
                self.assertNotIn(
                    content.decode("utf-8", errors="ignore"),
                    str(stopped.exception),
                )

    def test_unsupported_unknown_status_remains_generic(self) -> None:
        opener = mock.Mock()
        opener.open.side_effect = _http_error(418, b"synthetic detail")
        request = _request()
        with mock.patch.object(runner, "_OPENER", opener):
            with self.assertRaises(runner.BootstrapStopped) as stopped:
                runner._request_staging_bootstrap_json(request)
        self.assertEqual(stopped.exception.code, GENERIC_STAGING_BOOTSTRAP_FAILURE)


if __name__ == "__main__":
    unittest.main()
