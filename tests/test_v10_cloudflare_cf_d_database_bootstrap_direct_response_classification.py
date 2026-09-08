from __future__ import annotations

from http.client import IncompleteRead
import io
import json
import unittest
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request

from omni_cio.contracts.v1.cloudflare_cf_d_bootstrap_failures import (
    GENERIC_STAGING_BOOTSTRAP_FAILURE,
    NEON_FUNCTION_FAILURE_PREFIX,
    STAGING_BOOTSTRAP_REDIRECT_REJECTED,
    STAGING_BOOTSTRAP_UNAVAILABLE,
)
import scripts.bootstrap_v10_cloudflare_production_database_via_staging as runner


class _DirectResponse:
    def __init__(self, status: int, content: bytes) -> None:
        self.status = status
        self._stream = io.BytesIO(content)

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)

    def __enter__(self) -> _DirectResponse:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
        self._stream.close()
        return None


class _IncompleteReadBody:
    def read(self, size: int = -1) -> bytes:
        del size
        raise IncompleteRead(b"partial", 100)

    def close(self) -> None:
        return None


def _json_bytes(payload: object) -> bytes:
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


class CloudflareCfDDatabaseBootstrapDirectResponseClassificationTests(
    unittest.TestCase
):
    def _stopped_code(self, response: _DirectResponse) -> str:
        opener = mock.Mock()
        opener.open.return_value = response
        with mock.patch.object(runner, "_OPENER", opener):
            with self.assertRaises(runner.BootstrapStopped) as stopped:
                runner._request_staging_bootstrap_json(
                    Request("https://example.invalid/bootstrap")
                )
        return stopped.exception.code

    def test_direct_redirect_response_is_classified_without_body_parsing(self) -> None:
        response = _DirectResponse(302, b"untrusted redirect body")
        self.assertEqual(
            self._stopped_code(response),
            STAGING_BOOTSTRAP_REDIRECT_REJECTED,
        )

    def test_direct_allowlisted_failure_preserves_sanitized_detail(self) -> None:
        code = f"{NEON_FUNCTION_FAILURE_PREFIX}OIDC_AUDIENCE_INVALID"
        response = _DirectResponse(502, _json_bytes({"detail": code}))
        self.assertEqual(self._stopped_code(response), code)

    def test_direct_oversized_failure_collapses_fail_closed(self) -> None:
        response = _DirectResponse(
            502,
            b"x" * (runner._MAX_STAGING_FAILURE_RESPONSE_BYTES + 1),
        )
        self.assertEqual(
            self._stopped_code(response),
            GENERIC_STAGING_BOOTSTRAP_FAILURE,
        )

    def test_direct_incomplete_read_is_sanitized_as_transport_unavailable(self) -> None:
        response = _DirectResponse(502, b"")
        response.read = mock.Mock(side_effect=IncompleteRead(b"partial", 100))
        self.assertEqual(
            self._stopped_code(response),
            STAGING_BOOTSTRAP_UNAVAILABLE,
        )

    def test_http_error_incomplete_read_is_sanitized_before_exception_escapes(self) -> None:
        error = HTTPError(
            "https://example.invalid/bootstrap",
            502,
            "synthetic",
            None,
            _IncompleteReadBody(),
        )
        opener = mock.Mock()
        opener.open.side_effect = error
        with mock.patch.object(runner, "_OPENER", opener):
            with self.assertRaises(runner.BootstrapStopped) as stopped:
                runner._request_staging_bootstrap_json(
                    Request("https://example.invalid/bootstrap")
                )
        self.assertEqual(stopped.exception.code, STAGING_BOOTSTRAP_UNAVAILABLE)
        self.assertNotIn("partial", str(stopped.exception))


if __name__ == "__main__":
    unittest.main()
