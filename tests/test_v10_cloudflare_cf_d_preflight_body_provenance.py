from __future__ import annotations

import json
import secrets
from unittest import mock

import scripts.bootstrap_v10_cloudflare_production_database_direct as direct
import scripts.bootstrap_v10_cloudflare_production_database_via_staging as legacy


EXPECTED_SHA = "a" * 40
ORIGIN = (
    "https://br-example1234-cfdprodbootstrap.compute."
    "c-6.eu-central-1.aws.neon.tech/"
)


class _Response:
    def __init__(
        self,
        status: int,
        payload: bytes,
        *,
        content_type: str = "text/plain",
        reject_read: bool = False,
    ) -> None:
        self.status = status
        self._payload = payload
        self._content_type = content_type
        self._reject_read = reject_read

    def getheader(self, name: str, default: str = "") -> str:
        if name.lower() == "content-type":
            return self._content_type
        return default

    def read(self, size: int = -1) -> bytes:
        if self._reject_read:
            raise AssertionError("redirect response body must not be consumed")
        if size < 0:
            return self._payload
        return self._payload[:size]


class _Connection:
    def __init__(self, response: _Response) -> None:
        self._response = response
        self.requests: list[tuple[str, str, bytes | None, dict[str, str]]] = []
        self.closed = False

    def request(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None,
        headers: dict[str, str],
    ) -> None:
        self.requests.append((method, path, body, headers))

    def getresponse(self) -> _Response:
        return self._response

    def close(self) -> None:
        self.closed = True


def _source_controlled_preflight_body() -> bytes:
    return json.dumps(
        {"status": "BLOCKED", "code": "METHOD_NOT_ALLOWED"},
        separators=(",", ":"),
    ).encode("utf-8")


def _expect_preflight_failure(response: _Response) -> str:
    connection = _Connection(response)
    target = direct._target_from_origin(ORIGIN)
    with mock.patch.object(direct, "_direct_connection", return_value=connection):
        try:
            direct._preflight_direct_function(target)
        except legacy.BootstrapStopped as exc:
            assert connection.closed is True
            return exc.code
    raise AssertionError("invalid preflight response was accepted")


def test_preflight_uses_exact_status_and_body_not_response_media_type() -> None:
    connection = _Connection(
        _Response(
            405,
            _source_controlled_preflight_body(),
            content_type="text/plain; charset=utf-8",
        )
    )
    target = direct._target_from_origin(ORIGIN)

    with mock.patch.object(direct, "_direct_connection", return_value=connection):
        direct._preflight_direct_function(target)

    assert connection.requests == [
        (
            "GET",
            "/",
            None,
            {
                "Accept": "application/json",
                "User-Agent": direct._DIRECT_USER_AGENT,
            },
        )
    ]
    assert connection.closed is True


def test_preflight_preserves_provider_status_before_oidc_mint() -> None:
    target = direct._target_from_origin(ORIGIN)
    connection = _Connection(
        _Response(
            403,
            b"<untrusted-provider-body>",
            content_type="text/html",
        )
    )
    fallback_unavailable = legacy.BootstrapStopped(
        "NEON_FUNCTION_DEPLOY_API_KEY_REQUIRED"
    )

    with (
        mock.patch.object(direct, "read_bootstrap_origin_handoff", return_value=target),
        mock.patch.object(direct, "_direct_connection", return_value=connection),
        mock.patch.object(
            direct,
            "project_invocation_authority_from_env",
            side_effect=fallback_unavailable,
        ) as invocation_authority,
        mock.patch.object(legacy, "_github_oidc_token") as oidc_token,
    ):
        try:
            direct.run(EXPECTED_SHA)
        except legacy.BootstrapStopped as exc:
            assert exc is fallback_unavailable
        else:
            raise AssertionError("provider edge rejection was accepted")
        invocation_authority.assert_called_once_with()
        oidc_token.assert_not_called()


def test_preflight_rejects_non_source_controlled_405_body() -> None:
    code = _expect_preflight_failure(
        _Response(
            405,
            b'{"status":"BLOCKED","code":"UNKNOWN_PROVIDER_CODE"}',
            content_type="application/json",
        )
    )
    assert code == "CLOUDFLARE_CF_D_DIRECT_HTTP_405_UNCLASSIFIED"


def test_preflight_keeps_bounded_response_limit() -> None:
    code = _expect_preflight_failure(
        _Response(
            405,
            b"x" * (direct._MAX_DIRECT_FAILURE_BYTES + 1),
        )
    )
    assert code == direct._DIRECT_RESPONSE_TOO_LARGE


def test_preflight_rejects_redirect_without_consuming_body() -> None:
    code = _expect_preflight_failure(
        _Response(
            302,
            b"ignored",
            reject_read=True,
        )
    )
    assert code == direct._DIRECT_REDIRECT


def test_direct_oidc_ingress_preflight_proves_custom_header_before_oidc_mint() -> None:
    response = _Response(
        403,
        json.dumps(
            {"status": "BLOCKED", "code": "OIDC_TOKEN_INVALID"},
            separators=(",", ":"),
        ).encode("utf-8"),
    )
    connection = _Connection(response)
    target = direct._target_from_origin(ORIGIN)

    with mock.patch.object(direct, "_direct_connection", return_value=connection):
        direct._preflight_direct_oidc_ingress(target, EXPECTED_SHA)

    assert connection.requests == [
        (
            "POST",
            "/",
            json.dumps({"expected_sha": EXPECTED_SHA}, separators=(",", ":")).encode(
                "utf-8"
            ),
            {
                "Accept": "application/json",
                "User-Agent": direct._DIRECT_USER_AGENT,
                direct._DIRECT_OIDC_HEADER: direct._DIRECT_INGRESS_PROBE_TOKEN,
                "Content-Type": "application/json",
            },
        )
    ]
    assert "Authorization" not in connection.requests[0][3]
    assert connection.closed is True


def test_direct_oidc_ingress_preflight_failure_cannot_mint_real_oidc() -> None:
    target = direct._target_from_origin(ORIGIN)
    fallback_unavailable = legacy.BootstrapStopped(
        "NEON_FUNCTION_DEPLOY_API_KEY_REQUIRED"
    )
    with (
        mock.patch.object(direct, "read_bootstrap_origin_handoff", return_value=target),
        mock.patch.object(direct, "_preflight_direct_function"),
        mock.patch.object(
            direct,
            "_preflight_direct_oidc_ingress",
            side_effect=legacy.BootstrapStopped(
                "CLOUDFLARE_CF_D_DIRECT_HTTP_403_UNCLASSIFIED"
            ),
        ),
        mock.patch.object(
            direct,
            "project_invocation_authority_from_env",
            side_effect=fallback_unavailable,
        ) as invocation_authority,
        mock.patch.object(legacy, "_github_oidc_token") as oidc_token,
    ):
        try:
            direct.run(EXPECTED_SHA)
        except legacy.BootstrapStopped as exc:
            assert exc is fallback_unavailable
        else:
            raise AssertionError("failed ingress provenance was accepted")
        invocation_authority.assert_called_once_with()
        oidc_token.assert_not_called()


def test_success_payload_validation_is_body_authoritative() -> None:
    payload = {
        "status": "READY",
        "runtime_role": "omni_cio_cloudflare_prod",
        "runtime_dsn": "runtime-value-stays-inside-validator-test",
        "source_sha": EXPECTED_SHA,
    }
    connection = _Connection(
        _Response(
            200,
            json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            content_type="application/octet-stream",
        )
    )
    target = direct._target_from_origin(ORIGIN)
    oidc_token = ".".join(secrets.token_urlsafe(18) for _ in range(3))

    with mock.patch.object(direct, "_direct_connection", return_value=connection):
        result = direct._request_direct_bootstrap_json(target, EXPECTED_SHA, oidc_token)

    assert result == payload
    assert connection.closed is True
    assert connection.requests[0][0:3] == (
        "POST",
        "/",
        json.dumps({"expected_sha": EXPECTED_SHA}, separators=(",", ":")).encode(
            "utf-8"
        ),
    )
    assert connection.requests[0][3] == {
        "Accept": "application/json",
        "User-Agent": direct._DIRECT_USER_AGENT,
        direct._DIRECT_OIDC_HEADER: oidc_token,
        "Content-Type": "application/json",
    }
    assert "Authorization" not in connection.requests[0][3]


def test_success_response_still_requires_strict_json_object_body() -> None:
    target = direct._target_from_origin(ORIGIN)
    oidc_token = ".".join(secrets.token_urlsafe(18) for _ in range(3))

    for body in (b"<untrusted-html>", b"[]"):
        connection = _Connection(_Response(200, body))
        with mock.patch.object(direct, "_direct_connection", return_value=connection):
            try:
                direct._request_direct_bootstrap_json(target, EXPECTED_SHA, oidc_token)
            except legacy.BootstrapStopped as exc:
                assert exc.code == direct._DIRECT_RESPONSE_INVALID
            else:
                raise AssertionError("invalid HTTP 200 body was accepted")
        assert connection.closed is True
