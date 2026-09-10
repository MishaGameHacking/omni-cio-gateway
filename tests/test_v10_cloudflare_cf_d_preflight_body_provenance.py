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

    with (
        mock.patch.object(direct, "read_bootstrap_origin_handoff", return_value=target),
        mock.patch.object(direct, "_direct_connection", return_value=connection),
        mock.patch.object(legacy, "_github_oidc_token") as oidc_token,
    ):
        try:
            direct.run(EXPECTED_SHA)
        except legacy.BootstrapStopped as exc:
            assert exc.code == "CLOUDFLARE_CF_D_DIRECT_HTTP_403_UNCLASSIFIED"
        else:
            raise AssertionError("provider edge rejection was accepted")
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
        "Authorization": f"Bearer {oidc_token}",
        "Content-Type": "application/json",
    }
