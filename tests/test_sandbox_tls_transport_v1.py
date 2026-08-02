from __future__ import annotations

from pathlib import Path
import ssl

import httpx
import pytest

from omni_cio.sandbox import client_v1
from omni_cio.sandbox.client_v1 import SandboxApiFailure, SandboxRestClientV1


_FAKE_PEM = b"""-----BEGIN CERTIFICATE-----
ZmFrZS1jZXJ0aWZpY2F0ZS1maXh0dXJl
-----END CERTIFICATE-----
"""


def test_sdk_certificate_discovery_accepts_embedded_pem(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    package_file = tmp_path / "t_tech" / "invest" / "certs" / "root_ca.pem"
    package_file.parent.mkdir(parents=True)
    package_file.write_bytes(_FAKE_PEM)

    class FakeDistribution:
        files = (Path("t_tech/invest/certs/root_ca.pem"),)

        def locate_file(self, entry: Path) -> Path:
            return tmp_path / entry

    client_v1._sdk_certificate_blobs.cache_clear()
    monkeypatch.setattr(
        client_v1.metadata,
        "distribution",
        lambda package_name: FakeDistribution(),
    )

    assert client_v1._sdk_certificate_blobs() == (_FAKE_PEM,)
    client_v1._sdk_certificate_blobs.cache_clear()


def test_ssl_tbank_verify_adds_sdk_ca_to_httpx_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded: list[str] = []

    class FakeContext:
        def load_verify_locations(self, *, cadata: str) -> None:
            loaded.append(cadata)

    context = FakeContext()
    monkeypatch.setenv("SSL_TBANK_VERIFY", "True")
    monkeypatch.setattr(client_v1.ssl, "create_default_context", lambda: context)
    monkeypatch.setattr(client_v1, "_sdk_certificate_blobs", lambda: (_FAKE_PEM,))

    result = client_v1._sandbox_ssl_context()

    assert result is context
    assert len(loaded) == 1
    assert "BEGIN CERTIFICATE" in loaded[0]


def test_missing_sdk_ca_fails_closed_when_ssl_tbank_verify_is_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SSL_TBANK_VERIFY", "True")
    monkeypatch.setattr(client_v1, "_sdk_certificate_blobs", lambda: ())

    with pytest.raises(SandboxApiFailure) as failure:
        client_v1._sandbox_ssl_context()

    assert failure.value.code == "SANDBOX_TLS_CA_UNAVAILABLE"
    assert failure.value.http_status == 503


def test_non_submission_connect_error_is_not_labeled_ambiguous() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connect failed", request=request)

    client = SandboxRestClientV1(
        "sandbox-test-token",
        transport=httpx.MockTransport(handler),
        ssl_context=ssl.create_default_context(),
    )

    with pytest.raises(SandboxApiFailure) as failure:
        client.post("GetSandboxAccounts", {"status": "ACCOUNT_STATUS_OPEN"})

    assert failure.value.code == "SANDBOX_TRANSPORT_ERROR"
    assert failure.value.ambiguous_submission is False


def test_submission_connect_error_remains_fail_closed_and_ambiguous() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("response state unknown", request=request)

    client = SandboxRestClientV1(
        "sandbox-test-token",
        transport=httpx.MockTransport(handler),
        ssl_context=ssl.create_default_context(),
    )

    with pytest.raises(SandboxApiFailure) as failure:
        client.post("PostSandboxOrder", {})

    assert failure.value.code == "SANDBOX_TRANSPORT_AMBIGUOUS"
    assert failure.value.ambiguous_submission is True
