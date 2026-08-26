from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import secrets
from threading import Event

import httpx
import pytest

from omni_cio.web.telegram_jwks_v1 import TelegramJwksSingleFlightVerifierV1
from omni_cio.web.telegram_oidc_v1 import TelegramOidcConfigV1, TelegramOidcError


NOW = datetime(2026, 8, 25, 19, 0, tzinfo=timezone.utc)
CALLBACK = "https://omni.example/api/v10/web/auth/telegram/callback"
CLIENT_SECRET = secrets.token_urlsafe(32)
RFC_RSA_MODULUS = "".join(
    [
        "ofgWCuLjybRl",
        "zo0tZWJjNiuS",
        "fb4p4fAkd_wW",
        "JcyQoTbji9k0",
        "l8W26mPddxHm",
        "fHQp-Vaw-4qP",
        "CJrcS2mJPMEz",
        "P1Pt0Bm4d4Ql",
        "L-yRT-SFd2lZ",
        "S-pCgNMsD1W_",
        "YpRPEwOWvG6b",
        "32690r2jZ47s",
        "oMZo9wGzjb_7",
        "OMg0LOL-bSf6",
        "3kpaSHSXndS5",
        "z5rexMdbBYUs",
        "LA9e-KXBdQOS",
        "-UTo7WTBEMa2",
        "R2CapHg665xs",
        "mtdVMTBQY4uD",
        "Zlxvb3qCo5Zw",
        "Kh9kG4LT6_I5",
        "IhlJH7aGhyxX",
        "FvUK-DWNmoud",
        "F8NAco9_h9ia",
        "GNj8q2ethFkM",
        "Ls91kzk2PAcD",
        "TW9gb54h4FRW",
        "yuXpoQ",
    ]
)


def _config() -> TelegramOidcConfigV1:
    return TelegramOidcConfigV1(
        client_id="123456789",
        client_secret=CLIENT_SECRET,
        redirect_uri=CALLBACK,
        timeout_seconds=1.0,
        jwks_cache_lifetime=timedelta(minutes=1),
    )


def _jwks(kid: str) -> dict[str, object]:
    return {
        "keys": [
            {
                "kty": "RSA",
                "kid": kid,
                "use": "sig",
                "alg": "RS256",
                "n": RFC_RSA_MODULUS,
                "e": "AQAB",
            }
        ]
    }


def test_jwks_network_io_runs_outside_shared_refresh_lock() -> None:
    entered = Event()
    release = Event()

    def handler(request: httpx.Request) -> httpx.Response:
        entered.set()
        if not release.wait(timeout=2.0):
            raise AssertionError("test did not release provider response")
        return httpx.Response(200, json=_jwks("telegram-key"))

    verifier = TelegramJwksSingleFlightVerifierV1(_config())
    client = httpx.Client(transport=httpx.MockTransport(handler))

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            verifier._key_for,
            "telegram-key",
            now=NOW,
            client=client,
        )
        assert entered.wait(timeout=1.0)
        acquired = verifier._refresh_lock.acquire(blocking=False)
        try:
            assert acquired is True
        finally:
            if acquired:
                verifier._refresh_lock.release()
            release.set()
        assert future.result().size_bytes >= 256


def test_concurrent_cache_miss_is_single_flight() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=_jwks("telegram-key"))

    verifier = TelegramJwksSingleFlightVerifierV1(_config())
    client = httpx.Client(transport=httpx.MockTransport(handler))

    def load(_: int) -> int:
        return verifier._key_for(
            "telegram-key",
            now=NOW,
            client=client,
        ).size_bytes

    with ThreadPoolExecutor(max_workers=8) as executor:
        sizes = list(executor.map(load, range(16)))

    assert all(size >= 256 for size in sizes)
    assert calls == 1


def test_unknown_kid_rotation_probe_is_cooldown_bounded() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        kid = "known-key" if calls == 1 else "rotated-key"
        return httpx.Response(200, json=_jwks(kid))

    verifier = TelegramJwksSingleFlightVerifierV1(_config())
    client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(TelegramOidcError, match="TELEGRAM_OIDC_SIGNING_KEY_UNKNOWN"):
        verifier._key_for("rotated-key", now=NOW, client=client)
    with pytest.raises(TelegramOidcError, match="TELEGRAM_OIDC_SIGNING_KEY_UNKNOWN"):
        verifier._key_for(
            "rotated-key",
            now=NOW + timedelta(seconds=5),
            client=client,
        )
    assert calls == 1

    key = verifier._key_for(
        "rotated-key",
        now=NOW + timedelta(seconds=11),
        client=client,
    )
    assert key.size_bytes >= 256
    assert calls == 2


def test_failed_refresh_has_bounded_retry_cooldown() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("provider unavailable", request=request)

    verifier = TelegramJwksSingleFlightVerifierV1(_config())
    client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(TelegramOidcError, match="TELEGRAM_OIDC_NETWORK_ERROR"):
        verifier._key_for("telegram-key", now=NOW, client=client)
    with pytest.raises(TelegramOidcError, match="TELEGRAM_OIDC_JWKS_REFRESH_BACKOFF"):
        verifier._key_for(
            "telegram-key",
            now=NOW + timedelta(seconds=1),
            client=client,
        )
    assert calls == 1

    with pytest.raises(TelegramOidcError, match="TELEGRAM_OIDC_NETWORK_ERROR"):
        verifier._key_for(
            "telegram-key",
            now=NOW + timedelta(seconds=6),
            client=client,
        )
    assert calls == 2
