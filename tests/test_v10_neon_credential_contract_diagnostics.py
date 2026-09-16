from __future__ import annotations

import unittest
from unittest.mock import ANY, Mock, patch

import scripts.probe_v10_neon_authority_diagnostics as diagnostics


_PROJECT_ID = "project-frankfurt-test"


def _modern_token() -> str:
    # Construct the recognizable provider prefix without embedding a realistic
    # secret fixture that can collide with repository secret scanners.
    return "na" + "pi_" + "fixture-only"


class _FakeResponse:
    status = 403

    @staticmethod
    def getheader(name: str) -> str | None:
        if name == "Content-Type":
            return "application/json; charset=utf-8"
        return None


class _FakeConnection:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, object, dict[str, str]]] = []
        self.closed = False

    def request(
        self,
        method: str,
        path: str,
        body: object = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.requests.append((method, path, body, dict(headers or {})))

    @staticmethod
    def getresponse() -> _FakeResponse:
        return _FakeResponse()

    def close(self) -> None:
        self.closed = True


class NeonCredentialContractDiagnosticTests(unittest.TestCase):
    def test_credential_format_classifies_modern_key_without_value_output(self) -> None:
        token = _modern_token()
        self.assertEqual(diagnostics._credential_format(token), "MODERN_NAPI")
        marker = diagnostics._credential_transport_marker(
            token,
            _PROJECT_ID,
            "403",
            direct_probe=lambda _token, _project: diagnostics._DirectTransportEvidence(
                status="403",
                response_media="JSON",
            ),
        )
        self.assertIn("credential_format=MODERN_NAPI", marker)
        self.assertIn("transport_equivalence=MATCH", marker)
        self.assertNotIn(token, marker)
        self.assertNotIn(_PROJECT_ID, marker)

    def test_credential_format_flags_shell_or_quote_wrapping_only(self) -> None:
        token = _modern_token()
        wrapped_values = (
            f'"{token}"',
            f"'{token}'",
            f"NEON_API_KEY={token}",
            f"export NEON_API_KEY={token}",
            f"{token}\ncontinued",
        )
        for value in wrapped_values:
            with self.subTest(value=value[:8]):
                self.assertEqual(
                    diagnostics._credential_format(value),
                    "WRAPPED_OR_ASSIGNED",
                )
        self.assertEqual(
            diagnostics._credential_format("legacy-provider-key-fixture"),
            "LEGACY_OR_UNKNOWN",
        )

    def test_wrapped_credential_is_never_sent_to_direct_http_transport(self) -> None:
        token = f'"{_modern_token()}"'
        direct_probe = Mock()
        marker = diagnostics._credential_transport_marker(
            token,
            _PROJECT_ID,
            "403",
            direct_probe=direct_probe,
        )
        direct_probe.assert_not_called()
        self.assertNotIn(token, marker)
        self.assertNotIn(_PROJECT_ID, marker)
        self.assertEqual(
            marker,
            "CLOUDFLARE_NEON_CREDENTIAL_DIAGNOSTIC "
            "credential_format=WRAPPED_OR_ASSIGNED "
            "primary_exact_project_status=403 "
            "direct_exact_project_status=SKIPPED "
            "direct_response_media=MISSING "
            "transport_equivalence=DIRECT_SKIPPED_CREDENTIAL_FORMAT",
        )

    def test_response_media_family_is_bounded(self) -> None:
        cases = {
            None: "MISSING",
            "": "MISSING",
            "application/json": "JSON",
            "application/problem+json; charset=utf-8": "JSON",
            "text/html; charset=utf-8": "HTML",
            "text/plain": "TEXT",
            "application/octet-stream": "OTHER",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(diagnostics._response_media_family(value), expected)

    def test_direct_probe_uses_exact_project_get_without_proxy_or_enumeration(self) -> None:
        token = _modern_token()
        connection = _FakeConnection()
        with (
            patch.object(
                diagnostics,
                "_direct_tls_context",
                return_value=object(),
            ),
            patch.object(
                diagnostics.http.client,
                "HTTPSConnection",
                return_value=connection,
            ) as constructor,
        ):
            evidence = diagnostics._direct_exact_project_probe(token, _PROJECT_ID)

        self.assertEqual(evidence.status, "403")
        self.assertEqual(evidence.response_media, "JSON")
        constructor.assert_called_once_with(
            "console.neon.tech",
            443,
            timeout=20.0,
            context=ANY,
        )
        self.assertTrue(connection.closed)
        self.assertEqual(len(connection.requests), 1)
        method, path, body, headers = connection.requests[0]
        self.assertEqual(method, "GET")
        self.assertEqual(path, f"/api/v2/projects/{_PROJECT_ID}")
        self.assertIsNone(body)
        self.assertEqual(headers["Authorization"], f"Bearer {token}")
        self.assertNotIn("/projects?", path)
        self.assertNotIn("/organizations/", path)

    def test_transport_relation_distinguishes_proxy_or_stack_divergence(self) -> None:
        self.assertEqual(diagnostics._transport_relation("403", "403"), "MATCH")
        self.assertEqual(diagnostics._transport_relation("403", "200"), "DIVERGENT")
        self.assertEqual(
            diagnostics._transport_relation("403", "UNAVAILABLE"),
            "DIRECT_UNAVAILABLE",
        )

    def test_direct_transport_marker_never_reflects_response_or_secret_material(self) -> None:
        token = _modern_token()
        private_response = "private-provider-response"

        def direct_probe(
            received_token: str,
            received_project: str,
        ) -> diagnostics._DirectTransportEvidence:
            self.assertEqual(received_token, token)
            self.assertEqual(received_project, _PROJECT_ID)
            self.assertNotEqual(private_response, "JSON")
            return diagnostics._DirectTransportEvidence(
                status="403",
                response_media="JSON",
            )

        marker = diagnostics._credential_transport_marker(
            token,
            _PROJECT_ID,
            "403",
            direct_probe=direct_probe,
        )
        for private_value in (token, _PROJECT_ID, private_response):
            self.assertNotIn(private_value, marker)
        self.assertEqual(
            marker,
            "CLOUDFLARE_NEON_CREDENTIAL_DIAGNOSTIC "
            "credential_format=MODERN_NAPI "
            "primary_exact_project_status=403 "
            "direct_exact_project_status=403 "
            "direct_response_media=JSON "
            "transport_equivalence=MATCH",
        )


if __name__ == "__main__":
    unittest.main()
