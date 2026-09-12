from __future__ import annotations

import json
from typing import Any
import unittest
from unittest.mock import patch

import scripts.bootstrap_v10_cloudflare_builds as builds
import scripts.probe_v10_cloudflare_neon_function_provenance_via_staging as provenance


_EXPECTED_SHA = "a" * 40
_EXPECTED_DIGEST = "b" * 64
_STAGING_ORIGIN = "https://omni-cio-v10-web-staging.example.workers.dev"
_SYNC_TOKEN = "c" * 64


class _Response:
    def __init__(
        self,
        status: int,
        payload: object,
        *,
        content_type: str = "application/json",
    ) -> None:
        self.status = status
        self.body = (
            payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
        )
        self.content_type = content_type

    def getheader(self, name: str, default: str = "") -> str:
        if name.lower() == "content-type":
            return self.content_type
        return default

    def read(self, limit: int) -> bytes:
        return self.body[:limit]


class _Connection:
    def __init__(self, response: _Response) -> None:
        self.response = response
        self.closed = False
        self.requests: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def request(self, *args: Any, **kwargs: Any) -> None:
        self.requests.append((args, kwargs))

    def getresponse(self) -> _Response:
        return self.response

    def close(self) -> None:
        self.closed = True


def _ready_payload(digest: object, *, state: str = "DIGEST") -> dict[str, object]:
    return {
        "status": "READY",
        "source_sha": _EXPECTED_SHA,
        "source_state": state,
        "source_sha256": digest,
    }


class CloudflareNeonFunctionProvenanceViaStagingTests(unittest.TestCase):
    def _probe(
        self,
        response: _Response,
        digest: str = _EXPECTED_DIGEST,
    ) -> tuple[bool, _Connection]:
        connection = _Connection(response)
        with patch.object(
            provenance.http.client,
            "HTTPSConnection",
            return_value=connection,
        ):
            result = provenance.probe_exact_source_via_staging(
                staging_origin=_STAGING_ORIGIN,
                expected_sha=_EXPECTED_SHA,
                token=_SYNC_TOKEN,
                expected_digest=digest,
            )
        return result, connection

    def test_exact_digest_and_stale_states_are_distinguished_without_provider_target(
        self,
    ) -> None:
        exact, connection = self._probe(
            _Response(200, _ready_payload(_EXPECTED_DIGEST))
        )
        self.assertTrue(exact)
        self.assertTrue(connection.closed)
        args, kwargs = connection.requests[0]
        self.assertEqual(args[0:2], ("POST", provenance._PROVENANCE_CUSTODY_PATH))
        headers = kwargs["headers"]
        self.assertEqual(headers["x-omni-expected-sha"], _EXPECTED_SHA)
        self.assertEqual(headers["x-omni-cf-d-origin-sync-token"], _SYNC_TOKEN)
        self.assertNotIn("authorization", headers)
        self.assertNotIn("compute.", provenance._PROVENANCE_CUSTODY_PATH)

        mismatch, _ = self._probe(_Response(200, _ready_payload("d" * 64)))
        self.assertFalse(mismatch)

        legacy, _ = self._probe(
            _Response(200, _ready_payload(None, state="LEGACY_STALE"))
        )
        self.assertFalse(legacy)

    def test_malformed_success_payload_fails_closed(self) -> None:
        cases = [
            _Response(200, {"status": "READY"}),
            _Response(200, {**_ready_payload(_EXPECTED_DIGEST), "extra": True}),
            _Response(200, _ready_payload("not-a-digest")),
            _Response(200, _ready_payload(None)),
            _Response(
                200,
                _ready_payload(_EXPECTED_DIGEST),
                content_type="text/html",
            ),
        ]
        for response in cases:
            with self.subTest(body=response.body):
                with self.assertRaisesRegex(
                    builds.BootstrapStopped,
                    "CLOUDFLARE_CF_D_NEON_FUNCTION_PROVENANCE_INVALID|DIGEST_INVALID",
                ):
                    self._probe(response)

    def test_worker_failure_codes_are_sanitized_and_nontransient_errors_do_not_retry(
        self,
    ) -> None:
        cases = [
            (403, {"detail": "hidden"}, provenance._PROVENANCE_UNAUTHORIZED),
            (404, {"detail": "hidden"}, provenance._PROVENANCE_NOT_FOUND),
            (
                502,
                {"detail": provenance._PROVENANCE_REDIRECT_REJECTED},
                provenance._PROVENANCE_REDIRECT_REJECTED,
            ),
            (418, {"detail": "hidden"}, provenance._PROVENANCE_HTTP_STATUS_INVALID),
        ]
        for status, payload, code in cases:
            with self.subTest(status=status):
                connection = _Connection(_Response(status, payload))
                with patch.object(
                    provenance.http.client,
                    "HTTPSConnection",
                    return_value=connection,
                ) as factory:
                    with self.assertRaises(builds.BootstrapStopped) as raised:
                        provenance.probe_exact_source_via_staging(
                            staging_origin=_STAGING_ORIGIN,
                            expected_sha=_EXPECTED_SHA,
                            token=_SYNC_TOKEN,
                            expected_digest=_EXPECTED_DIGEST,
                        )
                self.assertEqual(raised.exception.code, code)
                self.assertEqual(factory.call_count, 1)

    def test_transient_worker_failure_retries_with_bound(self) -> None:
        first = _Connection(
            _Response(
                502,
                {"detail": provenance._PROVENANCE_DERIVATION_FAILED},
            )
        )
        second = _Connection(_Response(200, _ready_payload(_EXPECTED_DIGEST)))
        with (
            patch.object(
                provenance.http.client,
                "HTTPSConnection",
                side_effect=[first, second],
            ) as factory,
            patch.object(provenance.time, "sleep") as sleep,
        ):
            self.assertTrue(
                provenance.probe_exact_source_via_staging(
                    staging_origin=_STAGING_ORIGIN,
                    expected_sha=_EXPECTED_SHA,
                    token=_SYNC_TOKEN,
                    expected_digest=_EXPECTED_DIGEST,
                )
            )
        self.assertEqual(factory.call_count, 2)
        sleep.assert_called_once_with(provenance._RETRY_DELAY_SECONDS)


if __name__ == "__main__":
    unittest.main()
