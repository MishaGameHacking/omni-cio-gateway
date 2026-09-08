from __future__ import annotations

import io
import json
from pathlib import Path
import re
import unittest
from unittest import mock
from urllib.error import HTTPError, URLError
from urllib.request import Request

import apps.api.cf_d_database_bootstrap as proxy
from omni_cio.contracts.v1.cloudflare_cf_d_bootstrap_failures import (
    GENERIC_STAGING_BOOTSTRAP_FAILURE,
    NEON_BOOTSTRAP_REJECTED,
    NEON_FUNCTION_FAILURE_CODES,
    NEON_FUNCTION_FAILURE_PREFIX,
    NEON_FUNCTION_FAILURE_STATUS_BY_CODE,
    STAGING_BOOTSTRAP_REDIRECT_REJECTED,
    STAGING_BOOTSTRAP_UNAVAILABLE,
    WORKER_FAILURE_CODES,
    classify_neon_bootstrap_provider_failure,
)
import scripts.bootstrap_v10_cloudflare_production_database_via_staging as runner


_ROOT = Path(__file__).resolve().parents[1]
_FUNCTION_SOURCE = _ROOT / "infrastructure/cloudflare/cf_d_neon_bootstrap/index.mjs"
_RELEASE_CONTRACT = (
    _ROOT / "docs/architecture/V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json"
)
_EXPECTED_SHA = "a" * 40


class _ProviderResponse:
    def __init__(self, status_code: int, content: bytes) -> None:
        self.status_code = status_code
        self._content = content
        self.bytes_yielded = 0

    def iter_bytes(self, chunk_size: int | None = None):  # type: ignore[no-untyped-def]
        size = chunk_size or max(1, len(self._content))
        for offset in range(0, len(self._content), size):
            chunk = self._content[offset : offset + size]
            self.bytes_yielded += len(chunk)
            yield chunk


class _ProviderStream:
    def __init__(self, response: _ProviderResponse) -> None:
        self._response = response

    def __enter__(self) -> _ProviderResponse:
        return self._response

    def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
        return None


class _ProviderClient:
    def __init__(self, response: _ProviderResponse) -> None:
        self._response = response

    def __enter__(self) -> _ProviderClient:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
        return None

    def stream(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, str],
    ) -> _ProviderStream:
        self.method = method
        self.url = url
        self.headers = headers
        self.json = json
        return _ProviderStream(self._response)


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


def _source_function_failure_codes() -> frozenset[str]:
    source = _FUNCTION_SOURCE.read_text(encoding="utf-8")
    throw_codes = set(
        re.findall(r"throw new Error\('([A-Z0-9_]{3,80})'\)", source)
    )
    fail_codes = set(re.findall(r"fail\('([A-Z0-9_]{3,80})'", source))
    parse_codes = set(
        re.findall(
            r"parseJsonSegment\([^,]+,\s*'([A-Z0-9_]{3,80})'\)",
            source,
        )
    )
    return frozenset(throw_codes | fail_codes | parse_codes | {"BOOTSTRAP_FAILED"})


def _expected_function_status(code: str) -> int:
    explicit = {
        "METHOD_NOT_ALLOWED": 405,
        "OIDC_REQUIRED": 401,
        "REQUEST_TOO_LARGE": 400,
        "REQUEST_INVALID": 400,
        "EXPECTED_SHA_INVALID": 400,
    }
    if code in explicit:
        return explicit[code]
    if code.startswith("OIDC_"):
        return 403
    return 502


class CloudflareCfDDatabaseBootstrapFailureClassificationTests(unittest.TestCase):
    def test_function_taxonomy_matches_source_controlled_failure_surface(self) -> None:
        source_codes = _source_function_failure_codes()
        self.assertEqual(source_codes, NEON_FUNCTION_FAILURE_CODES)
        self.assertEqual(
            dict(NEON_FUNCTION_FAILURE_STATUS_BY_CODE),
            {code: _expected_function_status(code) for code in source_codes},
        )

    def test_release_contract_matches_endpoint_specific_failure_taxonomy(self) -> None:
        contract = json.loads(_RELEASE_CONTRACT.read_text(encoding="utf-8"))
        cutover = contract["cutover"]
        function_codes = cutover[
            "production_database_bootstrap_function_failure_codes"
        ]
        worker_codes = cutover["production_database_bootstrap_worker_failure_codes"]

        self.assertIs(
            cutover["production_database_bootstrap_failure_classification_required"],
            True,
        )
        self.assertIs(
            cutover[
                "production_database_bootstrap_endpoint_specific_classifier_required"
            ],
            True,
        )
        self.assertIs(
            cutover[
                "production_database_bootstrap_oidc_token_helper_contract_must_remain_generic"
            ],
            True,
        )
        self.assertEqual(
            cutover["production_database_bootstrap_function_failure_prefix"],
            NEON_FUNCTION_FAILURE_PREFIX,
        )
        self.assertEqual(len(function_codes), len(set(function_codes)))
        self.assertEqual(frozenset(function_codes), NEON_FUNCTION_FAILURE_CODES)
        self.assertEqual(len(worker_codes), len(set(worker_codes)))
        self.assertEqual(frozenset(worker_codes), WORKER_FAILURE_CODES)
        self.assertEqual(
            cutover["production_database_bootstrap_failure_response_max_bytes"],
            runner._MAX_STAGING_FAILURE_RESPONSE_BYTES,
        )
        self.assertIs(
            cutover["production_database_bootstrap_raw_error_reflection_allowed"],
            False,
        )
        self.assertIs(
            cutover["production_database_bootstrap_unknown_failure_retryable"],
            False,
        )

    def test_provider_classifier_preserves_only_exact_source_controlled_failures(self) -> None:
        for code, status in NEON_FUNCTION_FAILURE_STATUS_BY_CODE.items():
            with self.subTest(code=code, status=status):
                content = _json_bytes({"status": "BLOCKED", "code": code})
                self.assertEqual(
                    classify_neon_bootstrap_provider_failure(status, content),
                    f"{NEON_FUNCTION_FAILURE_PREFIX}{code}",
                )
                self.assertEqual(
                    classify_neon_bootstrap_provider_failure(599, content),
                    NEON_BOOTSTRAP_REJECTED,
                )

        for payload in (
            {"status": "BLOCKED", "code": "UNTRUSTED_PROVIDER_CODE"},
            {"status": "READY", "code": "OIDC_AUDIENCE_INVALID"},
            {"detail": f"{NEON_FUNCTION_FAILURE_PREFIX}OIDC_AUDIENCE_INVALID"},
        ):
            with self.subTest(payload=payload):
                self.assertEqual(
                    classify_neon_bootstrap_provider_failure(502, _json_bytes(payload)),
                    NEON_BOOTSTRAP_REJECTED,
                )

        for content in (b"{", b"\xff", b"[]"):
            with self.subTest(content=content):
                self.assertEqual(
                    classify_neon_bootstrap_provider_failure(502, content),
                    NEON_BOOTSTRAP_REJECTED,
                )

    def test_proxy_preserves_function_oidc_class_without_raw_body(self) -> None:
        code = "OIDC_AUDIENCE_INVALID"
        response = _ProviderResponse(
            403,
            _json_bytes({"status": "BLOCKED", "code": code}),
        )
        client = _ProviderClient(response)
        with mock.patch.object(proxy.httpx, "Client", return_value=client):
            with self.assertRaises(proxy._BootstrapRouteStopped) as error:
                proxy._fetch_bootstrap_response(
                    "Bearer synthetic.jwt.token",
                    _EXPECTED_SHA,
                    proxy._secure_tls_context(),
                )
        self.assertEqual(
            error.exception.code,
            f"{NEON_FUNCTION_FAILURE_PREFIX}{code}",
        )
        self.assertEqual(error.exception.status_code, 502)
        self.assertNotIn("synthetic.jwt.token", str(error.exception))
        self.assertEqual(client.method, "POST")
        self.assertEqual(client.json, {"expected_sha": _EXPECTED_SHA})

    def test_proxy_bounds_error_body_before_classification(self) -> None:
        response = _ProviderResponse(
            502,
            b"x" * (proxy._MAX_PROVIDER_RESPONSE_BYTES + 1),
        )
        with mock.patch.object(
            proxy.httpx,
            "Client",
            return_value=_ProviderClient(response),
        ):
            with self.assertRaises(proxy._BootstrapRouteStopped) as error:
                proxy._fetch_bootstrap_response(
                    "Bearer synthetic.jwt.token",
                    _EXPECTED_SHA,
                    proxy._secure_tls_context(),
                )
        self.assertEqual(
            error.exception.code,
            "CLOUDFLARE_CF_D_NEON_BOOTSTRAP_RESPONSE_TOO_LARGE",
        )
        self.assertLessEqual(
            response.bytes_yielded,
            proxy._MAX_PROVIDER_RESPONSE_BYTES + proxy._PROVIDER_STREAM_CHUNK_BYTES,
        )

    def test_staging_runner_preserves_allowlisted_route_detail_only(self) -> None:
        code = f"{NEON_FUNCTION_FAILURE_PREFIX}OIDC_AUDIENCE_INVALID"
        error = _http_error(502, _json_bytes({"detail": code}))
        opener = mock.Mock()
        opener.open.side_effect = error
        with mock.patch.object(runner, "_OPENER", opener):
            with self.assertRaises(runner.BootstrapStopped) as stopped:
                runner._request_staging_bootstrap_json(
                    Request("https://example.invalid/bootstrap")
                )
        self.assertEqual(stopped.exception.code, code)

        for content in (
            _json_bytes({"detail": "UNTRUSTED_STAGING_DETAIL"}),
            _json_bytes({"detail": code, "extra": "ignored"}),
            b"{",
            b"\xff",
        ):
            with self.subTest(content=content):
                failure = _http_error(502, content)
                try:
                    self.assertEqual(
                        runner._staging_http_error_code(failure),
                        GENERIC_STAGING_BOOTSTRAP_FAILURE,
                    )
                finally:
                    failure.close()

    def test_staging_runner_rejects_oversized_redirect_and_transport_failures(self) -> None:
        oversized = _http_error(
            502,
            b"x" * (runner._MAX_STAGING_FAILURE_RESPONSE_BYTES + 1),
        )
        try:
            self.assertEqual(
                runner._staging_http_error_code(oversized),
                GENERIC_STAGING_BOOTSTRAP_FAILURE,
            )
        finally:
            oversized.close()

        redirect = _http_error(302, b"untrusted redirect body")
        try:
            self.assertEqual(
                runner._staging_http_error_code(redirect),
                STAGING_BOOTSTRAP_REDIRECT_REJECTED,
            )
        finally:
            redirect.close()

        opener = mock.Mock()
        opener.open.side_effect = URLError("synthetic transport detail")
        with mock.patch.object(runner, "_OPENER", opener):
            with self.assertRaises(runner.BootstrapStopped) as stopped:
                runner._request_staging_bootstrap_json(
                    Request("https://example.invalid/bootstrap")
                )
        self.assertEqual(stopped.exception.code, STAGING_BOOTSTRAP_UNAVAILABLE)
        self.assertNotIn("synthetic transport detail", str(stopped.exception))

    def test_generic_oidc_request_helper_remains_unclassified(self) -> None:
        provider_like = _http_error(
            403,
            _json_bytes(
                {"status": "BLOCKED", "code": "OIDC_AUDIENCE_INVALID"}
            ),
        )
        opener = mock.Mock()
        opener.open.side_effect = provider_like
        try:
            with mock.patch.object(runner, "_OPENER", opener):
                with self.assertRaises(runner.BootstrapStopped) as stopped:
                    runner._request_json(
                        Request("https://example.invalid/oidc"),
                        limit=runner._MAX_OIDC_RESPONSE_BYTES,
                        failure_code="GITHUB_OIDC_TOKEN_REQUEST_FAILED",
                    )
            self.assertEqual(
                stopped.exception.code,
                "GITHUB_OIDC_TOKEN_REQUEST_FAILED",
            )
        finally:
            provider_like.close()


if __name__ == "__main__":
    unittest.main()
