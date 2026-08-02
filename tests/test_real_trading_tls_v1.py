from __future__ import annotations

import ssl

import httpx
import pytest

from omni_cio import tbank_tls
from omni_cio.real_trading import client_v1
from omni_cio.real_trading.client_v1 import RealTradingApiFailure, RealTradingRestClientV1


def test_real_client_maps_missing_verified_ca_to_fail_closed_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        client_v1,
        "build_tbank_ssl_context",
        lambda: (_ for _ in ()).throw(tbank_tls.TBankTlsCaUnavailable("missing CA")),
    )

    with pytest.raises(RealTradingApiFailure) as failure:
        client_v1._real_ssl_context()

    assert failure.value.code == "REAL_TRADING_TLS_CA_UNAVAILABLE"
    assert failure.value.http_status == 503


def test_real_client_passes_verified_ssl_context_to_httpx() -> None:
    seen_verify: list[object] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"accounts": []})

    class RecordingClient(httpx.Client):
        def __init__(self, **kwargs: object) -> None:
            seen_verify.append(kwargs["verify"])
            super().__init__(**kwargs)

    context = ssl.create_default_context()
    client = RealTradingRestClientV1(
        "real-test-token",  # pragma: allowlist secret
        transport=httpx.MockTransport(handler),
        client_factory=RecordingClient,
        ssl_context=context,
    )

    assert client.post("GetAccounts", {}) == {"accounts": []}
    assert seen_verify == [context]


def test_real_post_order_transport_error_is_ambiguous_and_not_retried_here() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("response state unknown", request=request)

    client = RealTradingRestClientV1(
        "real-test-token",  # pragma: allowlist secret
        transport=httpx.MockTransport(handler),
        ssl_context=ssl.create_default_context(),
    )

    with pytest.raises(RealTradingApiFailure) as failure:
        client.post("PostOrder", {})

    assert failure.value.code == "REAL_TRADING_TRANSPORT_AMBIGUOUS"
    assert failure.value.ambiguous_submission is True
