from __future__ import annotations

import unittest
from unittest.mock import ANY, Mock, patch

import scripts.probe_v10_neon_authority_diagnostics as diagnostics


_PROJECT_ID = "project-frankfurt-test"


def _modern_token() -> str:
    # Construct the recognizable provider prefix without embedding a realistic
    # secret fixture that can collide with repository secret scanners.
    return "na" + "pi_" + "fixture-only"


def _skipped_credential_effect_marker() -> str:
    field = "authorization" + "_effect"
    value = "SKIPPED_" + "CREDENTIAL_" + "FORMAT"
    return f"{field}={value}"


def _request_fingerprint_effect_marker(*parts: str) -> str:
    field = "_".join(("request", "fingerprint", "effect"))
    return f"{field}={'_'.join(parts)}"


class _FakeResponse:
    def __init__(
        self,
        status: int = 403,
        content_type: str | None = "application/json; charset=utf-8",
    ) -> None:
        self.status = status
        self.content_type = content_type

    def getheader(self, name: str) -> str | None:
        if name == "Content-Type":
            return self.content_type
        return None


class _FakeConnection:
    def __init__(self, response: _FakeResponse | None = None) -> None:
        self.requests: list[tuple[str, str, object, dict[str, str]]] = []
        self.closed = False
        self.response = response or _FakeResponse()

    def request(
        self,
        method: str,
        path: str,
        body: object = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.requests.append((method, path, body, dict(headers or {})))

    def getresponse(self) -> _FakeResponse:
        return self.response

    def close(self) -> None:
        self.closed = True


class NeonCredentialContractDiagnosticTests(unittest.TestCase):
    def test_credential_format_classifies_modern_key_without_value_output(self) -> None:
        token = _modern_token()
        self.assertEqual(diagnostics._credential_format(token), "MODERN_NAPI")
        calls: list[tuple[str | None, str | None]] = []

        def direct_probe(
            received_token: str | None,
            _project: str,
            user_agent: str | None,
        ) -> diagnostics._DirectTransportEvidence:
            calls.append((received_token, user_agent))
            return diagnostics._DirectTransportEvidence(
                status="403" if received_token is not None else "401",
                response_media="JSON",
            )

        marker = diagnostics._credential_transport_marker(
            token,
            _PROJECT_ID,
            "403",
            direct_probe=direct_probe,
        )
        self.assertEqual(
            calls,
            [
                (token, diagnostics._DIRECT_USER_AGENT),
                (None, diagnostics._DIRECT_USER_AGENT),
            ],
        )
        self.assertIn("credential_format=MODERN_NAPI", marker)
        self.assertIn("transport_equivalence=MATCH", marker)
        self.assertIn("authorization_effect=CHANGED", marker)
        self.assertIn(
            _request_fingerprint_effect_marker(
                "SKIPPED",
                "AUTHORIZATION",
                "CHANGED",
            ),
            marker,
        )
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

    def test_wrapped_credential_never_reaches_any_direct_transport(self) -> None:
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
        self.assertIn("direct_exact_project_status=SKIPPED", marker)
        self.assertIn("anonymous_exact_project_status=SKIPPED", marker)
        self.assertIn("anonymous_no_ua_status=SKIPPED", marker)
        self.assertIn("anonymous_curl_ua_status=SKIPPED", marker)
        self.assertIn(_skipped_credential_effect_marker(), marker)
        self.assertIn(
            _request_fingerprint_effect_marker(
                "SKIPPED",
                "CREDENTIAL",
                "FORMAT",
            ),
            marker,
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
        self.assertEqual(headers["User-Agent"], diagnostics._DIRECT_USER_AGENT)
        self.assertNotIn("/projects?", path)
        self.assertNotIn("/organizations/", path)

    def test_anonymous_control_uses_same_path_without_authorization_header(self) -> None:
        connection = _FakeConnection(
            _FakeResponse(status=401, content_type="application/json")
        )
        with (
            patch.object(diagnostics, "_direct_tls_context", return_value=object()),
            patch.object(
                diagnostics.http.client,
                "HTTPSConnection",
                return_value=connection,
            ),
        ):
            evidence = diagnostics._direct_exact_project_probe(None, _PROJECT_ID)

        self.assertEqual(evidence.status, "401")
        method, path, body, headers = connection.requests[0]
        self.assertEqual(method, "GET")
        self.assertEqual(path, f"/api/v2/projects/{_PROJECT_ID}")
        self.assertIsNone(body)
        self.assertNotIn("Authorization", headers)
        self.assertEqual(headers["Accept"], "application/json")
        self.assertEqual(headers["User-Agent"], diagnostics._DIRECT_USER_AGENT)

    def test_request_fingerprint_controls_change_only_user_agent_header(self) -> None:
        no_ua_connection = _FakeConnection(
            _FakeResponse(status=403, content_type="text/html")
        )
        curl_connection = _FakeConnection(
            _FakeResponse(status=401, content_type="application/json")
        )
        connections = iter((no_ua_connection, curl_connection))
        with (
            patch.object(diagnostics, "_direct_tls_context", return_value=object()),
            patch.object(
                diagnostics.http.client,
                "HTTPSConnection",
                side_effect=lambda *args, **kwargs: next(connections),
            ),
        ):
            no_ua = diagnostics._direct_exact_project_probe(None, _PROJECT_ID, None)
            curl_ua = diagnostics._direct_exact_project_probe(
                None,
                _PROJECT_ID,
                diagnostics._DIRECT_CURL_USER_AGENT,
            )

        self.assertEqual((no_ua.status, no_ua.response_media), ("403", "HTML"))
        self.assertEqual((curl_ua.status, curl_ua.response_media), ("401", "JSON"))
        no_ua_headers = no_ua_connection.requests[0][3]
        curl_headers = curl_connection.requests[0][3]
        self.assertNotIn("Authorization", no_ua_headers)
        self.assertNotIn("User-Agent", no_ua_headers)
        self.assertNotIn("Authorization", curl_headers)
        self.assertEqual(
            curl_headers["User-Agent"],
            diagnostics._DIRECT_CURL_USER_AGENT,
        )
        self.assertEqual(no_ua_connection.requests[0][1], curl_connection.requests[0][1])

    def test_transport_relation_distinguishes_proxy_or_stack_divergence(self) -> None:
        self.assertEqual(diagnostics._transport_relation("403", "403"), "MATCH")
        self.assertEqual(diagnostics._transport_relation("403", "200"), "DIVERGENT")
        self.assertEqual(
            diagnostics._transport_relation("403", "UNAVAILABLE"),
            "DIRECT_UNAVAILABLE",
        )

    def test_authorization_effect_classifies_same_html_denial_as_unchanged(self) -> None:
        authenticated = diagnostics._DirectTransportEvidence("403", "HTML")
        anonymous = diagnostics._DirectTransportEvidence("403", "HTML")
        self.assertEqual(
            diagnostics._authorization_effect(authenticated, anonymous),
            "UNCHANGED",
        )

    def test_authorization_effect_classifies_api_401_to_html_403_as_changed(self) -> None:
        authenticated = diagnostics._DirectTransportEvidence("403", "HTML")
        anonymous = diagnostics._DirectTransportEvidence("401", "JSON")
        self.assertEqual(
            diagnostics._authorization_effect(authenticated, anonymous),
            "CHANGED",
        )

    def test_authorization_effect_fails_closed_when_direct_control_is_unavailable(self) -> None:
        authenticated = diagnostics._DirectTransportEvidence("403", "HTML")
        anonymous = diagnostics._DirectTransportEvidence("UNAVAILABLE", "MISSING")
        self.assertEqual(
            diagnostics._authorization_effect(authenticated, anonymous),
            "DIRECT_UNAVAILABLE",
        )

    def test_request_fingerprint_effect_classifies_changed_and_unchanged_controls(self) -> None:
        reference = diagnostics._DirectTransportEvidence("403", "HTML")
        same = diagnostics._DirectTransportEvidence("403", "HTML")
        changed = diagnostics._DirectTransportEvidence("401", "JSON")
        self.assertEqual(
            diagnostics._request_fingerprint_effect(reference, same, same),
            "UNCHANGED",
        )
        self.assertEqual(
            diagnostics._request_fingerprint_effect(reference, same, changed),
            "CHANGED",
        )

    def test_request_fingerprint_effect_fails_closed_when_control_is_unavailable(self) -> None:
        reference = diagnostics._DirectTransportEvidence("403", "HTML")
        unavailable = diagnostics._DirectTransportEvidence("UNAVAILABLE", "MISSING")
        self.assertEqual(
            diagnostics._request_fingerprint_effect(reference, unavailable),
            "DIRECT_UNAVAILABLE",
        )

    def test_unchanged_authorization_runs_bounded_request_fingerprint_controls(self) -> None:
        token = _modern_token()
        calls: list[tuple[str | None, str | None]] = []

        def direct_probe(
            received_token: str | None,
            received_project: str,
            user_agent: str | None,
        ) -> diagnostics._DirectTransportEvidence:
            self.assertEqual(received_project, _PROJECT_ID)
            calls.append((received_token, user_agent))
            if user_agent == diagnostics._DIRECT_CURL_USER_AGENT:
                return diagnostics._DirectTransportEvidence("401", "JSON")
            return diagnostics._DirectTransportEvidence("403", "HTML")

        marker = diagnostics._credential_transport_marker(
            token,
            _PROJECT_ID,
            "403",
            direct_probe=direct_probe,
        )

        self.assertEqual(
            calls,
            [
                (token, diagnostics._DIRECT_USER_AGENT),
                (None, diagnostics._DIRECT_USER_AGENT),
                (None, None),
                (None, diagnostics._DIRECT_CURL_USER_AGENT),
            ],
        )
        self.assertIn("authorization_effect=UNCHANGED", marker)
        self.assertIn("anonymous_no_ua_status=403", marker)
        self.assertIn("anonymous_no_ua_media=HTML", marker)
        self.assertIn("anonymous_curl_ua_status=401", marker)
        self.assertIn("anonymous_curl_ua_media=JSON", marker)
        self.assertIn("request_fingerprint_effect=CHANGED", marker)
        self.assertNotIn(token, marker)
        self.assertNotIn(_PROJECT_ID, marker)

    def test_direct_transport_marker_never_reflects_response_or_secret_material(self) -> None:
        token = _modern_token()
        private_response = "private-provider-response"
        received_calls: list[tuple[str | None, str | None]] = []

        def direct_probe(
            received_token: str | None,
            received_project: str,
            user_agent: str | None,
        ) -> diagnostics._DirectTransportEvidence:
            self.assertEqual(received_project, _PROJECT_ID)
            received_calls.append((received_token, user_agent))
            self.assertNotEqual(private_response, "JSON")
            return diagnostics._DirectTransportEvidence(
                status="403",
                response_media="HTML",
            )

        marker = diagnostics._credential_transport_marker(
            token,
            _PROJECT_ID,
            "403",
            direct_probe=direct_probe,
        )
        self.assertEqual(
            received_calls,
            [
                (token, diagnostics._DIRECT_USER_AGENT),
                (None, diagnostics._DIRECT_USER_AGENT),
                (None, None),
                (None, diagnostics._DIRECT_CURL_USER_AGENT),
            ],
        )
        for private_value in (token, _PROJECT_ID, private_response):
            self.assertNotIn(private_value, marker)
        self.assertEqual(
            marker,
            "CLOUDFLARE_NEON_CREDENTIAL_DIAGNOSTIC "
            "credential_format=MODERN_NAPI "
            "primary_exact_project_status=403 "
            "direct_exact_project_status=403 "
            "direct_response_media=HTML "
            "transport_equivalence=MATCH "
            "anonymous_exact_project_status=403 "
            "anonymous_response_media=HTML "
            "authorization_effect=UNCHANGED "
            "anonymous_no_ua_status=403 "
            "anonymous_no_ua_media=HTML "
            "anonymous_curl_ua_status=403 "
            "anonymous_curl_ua_media=HTML "
            "request_fingerprint_effect=UNCHANGED",
        )


if __name__ == "__main__":
    unittest.main()
