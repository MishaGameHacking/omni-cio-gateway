from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from omni_cio.web.identity_v1 import IdentityProviderV1, VerifiedExternalIdentityV1
from omni_cio.web.provider_auth_v1 import (
    AuthorizationTransactionRegistryV1,
    ProviderAuthorizationError,
)
import omni_cio.web.telegram_oidc_v1 as telegram_oidc
from omni_cio.web.telegram_oidc_v1 import (
    TELEGRAM_OIDC_AUTHORIZATION_ENDPOINT,
    TELEGRAM_OIDC_JWKS_ENDPOINT,
    TELEGRAM_OIDC_TOKEN_ENDPOINT,
    TelegramIdTokenVerifierV1,
    TelegramOidcConfigV1,
    TelegramOidcError,
    TelegramOidcRuntimeV1,
    _RsaPublicKeyV1,
    _verify_rs256_signature,
)

NOW = datetime(2026, 8, 24, 1, 0, tzinfo=timezone.utc)
CLIENT_ID = "123456789"
CLIENT_AUTH_FIXTURE = "fixture-" + "client-auth-material"
CALLBACK = "https://omni.example/api/v10/web/auth/telegram/callback"


class _FakeVerifier:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def verify(
        self,
        id_token: str,
        *,
        expected_nonce: str,
        now: datetime,
        client: httpx.Client,
    ) -> VerifiedExternalIdentityV1:
        self.calls.append((id_token, expected_nonce))
        return VerifiedExternalIdentityV1(
            provider=IdentityProviderV1.TELEGRAM,
            subject="42",
        )


def _config() -> TelegramOidcConfigV1:
    return TelegramOidcConfigV1(
        client_id=CLIENT_ID,
        client_secret=CLIENT_AUTH_FIXTURE,
        redirect_uri=CALLBACK,
    )


def _json_response(payload: dict[str, object]) -> httpx.Response:
    return httpx.Response(200, json=payload)


def _b64json(payload: dict[str, object]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _rfc_rsa_modulus() -> str:
    return "".join(
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


def _jwks(kid: str = "telegram-key-1") -> dict[str, object]:
    # Telegram currently publishes multiple signing families in one JWKS. The
    # RS256-pinned adapter must ignore unrelated keys instead of rejecting the
    # whole provider key set.
    return {
        "keys": [
            {
                "kty": "RSA",
                "kid": kid,
                "use": "sig",
                "alg": "RS256",
                "n": _rfc_rsa_modulus(),
                "e": "AQAB",
            },
            {
                "kty": "EC",
                "kid": "oidc-es256-1",
                "use": "sig",
                "alg": "ES256",
                "crv": "P-256",
                "x": "fixture-x",
                "y": "fixture-y",
            },
            {
                "kty": "OKP",
                "kid": "oidc-eddsa-1",
                "use": "sig",
                "alg": "EdDSA",
                "crv": "Ed25519",
                "x": "fixture-x",
            },
            {
                "kty": "EC",
                "kid": "oidc-es256k-1",
                "use": "sig",
                "alg": "ES256K",
                "crv": "secp256k1",
                "x": "fixture-x",
                "y": "fixture-y",
            },
        ]
    }


def _token(
    *,
    kid: str = "telegram-key-1",
    alg: str = "RS256",
    nonce: str = "expected-nonce",
    issuer: str = telegram_oidc.TELEGRAM_OIDC_ISSUER,
    audience: str = CLIENT_ID,
    subject: object = "424242",
    issued_at: int | None = None,
    expires_at: int | None = None,
    extra_header: dict[str, object] | None = None,
) -> str:
    now_seconds = int(NOW.timestamp())
    header: dict[str, object] = {"alg": alg, "kid": kid, "typ": "JWT"}
    if extra_header:
        header.update(extra_header)
    payload = {
        "iss": issuer,
        "aud": audience,
        "sub": subject,
        "iat": issued_at if issued_at is not None else now_seconds - 5,
        "exp": expires_at if expires_at is not None else now_seconds + 300,
        "nonce": nonce,
    }
    return f"{_b64json(header)}.{_b64json(payload)}.AA"


def test_start_builds_minimal_telegram_pkce_authorization_url() -> None:
    runtime = TelegramOidcRuntimeV1(
        config=_config(),
        transactions=AuthorizationTransactionRegistryV1(),
    )

    url = runtime.start(now=NOW)
    parsed = urlsplit(url)
    expected = urlsplit(TELEGRAM_OIDC_AUTHORIZATION_ENDPOINT)
    query = parse_qs(parsed.query, keep_blank_values=True)

    assert (parsed.scheme, parsed.netloc, parsed.path) == (
        expected.scheme,
        expected.netloc,
        expected.path,
    )
    assert query["client_id"] == [CLIENT_ID]
    assert query["redirect_uri"] == [CALLBACK]
    assert query["response_type"] == ["code"]
    assert query["scope"] == ["openid"]
    assert query["code_challenge_method"] == ["S256"]
    assert len(query["state"][0]) >= 43
    assert len(query["code_challenge"][0]) == 43
    assert len(query["nonce"][0]) >= 43
    assert "code_verifier" not in query
    assert CLIENT_AUTH_FIXTURE not in url


def test_complete_exchanges_code_server_side_and_consumes_state_once() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert str(request.url) == TELEGRAM_OIDC_TOKEN_ENDPOINT
        assert request.method == "POST"
        assert request.headers["authorization"].startswith("Basic ")
        body = request.content.decode()
        assert "grant_type=authorization_code" in body
        assert "code=telegram-code" in body
        assert "redirect_uri=" in body
        assert "client_id=123456789" in body
        assert "code_verifier=" in body
        return _json_response(
            {
                "id_token": "fixture." + "id." + "token",  # pragma: allowlist secret
            }
        )

    verifier = _FakeVerifier()
    client = httpx.Client(transport=httpx.MockTransport(handler))
    runtime = TelegramOidcRuntimeV1(
        config=_config(),
        transactions=AuthorizationTransactionRegistryV1(),
        client=client,
        verifier=verifier,
    )
    start = runtime.start(now=NOW)
    state = parse_qs(urlsplit(start).query)["state"][0]
    nonce = parse_qs(urlsplit(start).query)["nonce"][0]

    identity = runtime.complete(state=state, code="telegram-code", now=NOW)

    assert identity == VerifiedExternalIdentityV1(
        provider=IdentityProviderV1.TELEGRAM,
        subject="42",
    )
    assert verifier.calls == [("fixture.id.token", nonce)]
    assert len(requests) == 1
    with pytest.raises(ProviderAuthorizationError, match="AUTH_TRANSACTION_NOT_FOUND"):
        runtime.complete(state=state, code="telegram-code", now=NOW)
    assert len(requests) == 1


def test_provider_failure_does_not_preserve_consumed_transaction() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(302, headers={"location": "https://example.invalid/"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    runtime = TelegramOidcRuntimeV1(
        config=_config(),
        transactions=AuthorizationTransactionRegistryV1(),
        client=client,
    )
    state = parse_qs(urlsplit(runtime.start(now=NOW)).query)["state"][0]

    with pytest.raises(
        TelegramOidcError,
        match="TELEGRAM_OIDC_PROVIDER_RESPONSE_INVALID",
    ):
        runtime.complete(state=state, code="telegram-code", now=NOW)
    with pytest.raises(ProviderAuthorizationError, match="AUTH_TRANSACTION_NOT_FOUND"):
        runtime.complete(state=state, code="telegram-code", now=NOW)
    assert calls == 1


def test_network_error_is_generic_and_transaction_stays_consumed() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("fixture provider unavailable", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    runtime = TelegramOidcRuntimeV1(
        config=_config(),
        transactions=AuthorizationTransactionRegistryV1(),
        client=client,
    )
    state = parse_qs(urlsplit(runtime.start(now=NOW)).query)["state"][0]

    with pytest.raises(TelegramOidcError, match="TELEGRAM_OIDC_NETWORK_ERROR"):
        runtime.complete(state=state, code="telegram-code", now=NOW)
    with pytest.raises(ProviderAuthorizationError, match="AUTH_TRANSACTION_NOT_FOUND"):
        runtime.complete(state=state, code="telegram-code", now=NOW)
    assert calls == 1


def test_provider_response_size_is_bounded_before_json_parse() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "content-type": "application/json",
                "content-length": "999999",
            },
            content=b"{}",
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    runtime = TelegramOidcRuntimeV1(
        config=_config(),
        transactions=AuthorizationTransactionRegistryV1(),
        client=client,
    )
    state = parse_qs(urlsplit(runtime.start(now=NOW)).query)["state"][0]

    with pytest.raises(
        TelegramOidcError,
        match="TELEGRAM_OIDC_PROVIDER_RESPONSE_TOO_LARGE",
    ):
        runtime.complete(state=state, code="telegram-code", now=NOW)


def test_rs256_verifier_matches_rfc7515_vector_and_rejects_tampering() -> None:
    modulus = _rfc_rsa_modulus()
    modulus_bytes = base64.urlsafe_b64decode(modulus + ("=" * (-len(modulus) % 4)))
    key = _RsaPublicKeyV1(
        modulus=int.from_bytes(modulus_bytes, "big"),
        exponent=65537,
        size_bytes=len(modulus_bytes),
    )
    header = "".join(["eyJhbGciOiJS", "UzI1NiJ9"])
    payload = "".join(
        [
            "eyJpc3MiOiJq",
            "b2UiLA0KICJl",
            "eHAiOjEzMDA4",
            "MTkzODAsDQog",
            "Imh0dHA6Ly9l",
            "eGFtcGxlLmNv",
            "bS9pc19yb290",
            "Ijp0cnVlfQ",
        ]
    )
    signature_text = "".join(
        [
            "cC4hiUPoj9Ee",
            "tdgtv3hF80EG",
            "rhuB__dzERat",
            "0XF9g2VtQgr9",
            "PJbu3XOiZj5R",
            "Zmh7AAuHIm4B",
            "h-0Qc_lF5YKt",
            "_O8W2Fp5jujG",
            "bds9uJdbF9CU",
            "Ar7t1dnZcAcQ",
            "jbKBYNX4BAyn",
            "RFdiuB--f_nZ",
            "LgrnbyTyWzO7",
            "5vRK5h6xBArL",
            "IARNPvkSjtQB",
            "MHlb1L07Qe7K",
            "0GarZRmB_eSN",
            "9383LcOLn6_d",
            "O--xi12jzDwu",
            "sC-eOkHWEsqt",
            "FZESc6BfI7no",
            "OPqvhJ1phCnv",
            "Wh6IeYI2w9QO",
            "YEUipUTI8np6",
            "LbgGY9Fs98rq",
            "Vt5AXLIhWkWy",
            "wlVmtVrBp0ig",
            "cN_IoypGlUPQ",
            "Ge77Rw",
        ]
    )
    signature = base64.urlsafe_b64decode(
        signature_text + ("=" * (-len(signature_text) % 4))
    )
    signing_input = f"{header}.{payload}".encode()

    assert _verify_rs256_signature(
        signing_input=signing_input,
        signature=signature,
        key=key,
    )
    assert not _verify_rs256_signature(
        signing_input=signing_input + b"x",
        signature=signature,
        key=key,
    )


def test_id_token_verifier_pins_fixed_jwks_and_validates_claims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        return _json_response(_jwks())

    monkeypatch.setattr(telegram_oidc, "_verify_rs256_signature", lambda **_: True)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    verifier = TelegramIdTokenVerifierV1(_config())

    identity = verifier.verify(
        _token(),
        expected_nonce="expected-nonce",
        now=NOW,
        client=client,
    )

    assert identity.provider is IdentityProviderV1.TELEGRAM
    assert identity.subject == "424242"
    assert urls == [TELEGRAM_OIDC_JWKS_ENDPOINT]


@pytest.mark.parametrize(
    ("token", "reason"),
    [
        (_token(alg="HS256"), "TELEGRAM_OIDC_ALGORITHM_INVALID"),
        (
            _token(extra_header={"jku": "https://example.invalid/jwks"}),
            "TELEGRAM_OIDC_HEADER_INVALID",
        ),
        (
            _token(extra_header={"crit": []}),
            "TELEGRAM_OIDC_HEADER_INVALID",
        ),
    ],
)
def test_id_token_header_confusion_is_rejected_before_signature(
    token: str,
    reason: str,
) -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _: _json_response(_jwks()))
    )
    verifier = TelegramIdTokenVerifierV1(_config())
    with pytest.raises(TelegramOidcError, match=reason):
        verifier.verify(
            token,
            expected_nonce="expected-nonce",
            now=NOW,
            client=client,
        )


@pytest.mark.parametrize(
    "token",
    [
        _token(issuer="https://example.invalid"),
        _token(audience="different-client"),
        _token(nonce="wrong-nonce"),
        _token(subject=""),
        _token(issued_at=int(NOW.timestamp()) + 300),
        _token(expires_at=int(NOW.timestamp()) - 300),
    ],
)
def test_id_token_claim_mismatches_fail_closed(
    token: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(telegram_oidc, "_verify_rs256_signature", lambda **_: True)
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _: _json_response(_jwks()))
    )
    verifier = TelegramIdTokenVerifierV1(_config())
    with pytest.raises(TelegramOidcError, match="TELEGRAM_OIDC_CLAIMS_INVALID"):
        verifier.verify(
            token,
            expected_nonce="expected-nonce",
            now=NOW,
            client=client,
        )


def test_unknown_kid_does_not_trigger_repeat_fetch_while_cache_is_fresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return _json_response(_jwks("known-key"))

    monkeypatch.setattr(telegram_oidc, "_verify_rs256_signature", lambda **_: True)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    verifier = TelegramIdTokenVerifierV1(_config())

    with pytest.raises(TelegramOidcError, match="TELEGRAM_OIDC_SIGNING_KEY_UNKNOWN"):
        verifier.verify(
            _token(kid="unknown-key"),
            expected_nonce="expected-nonce",
            now=NOW,
            client=client,
        )
    with pytest.raises(TelegramOidcError, match="TELEGRAM_OIDC_SIGNING_KEY_UNKNOWN"):
        verifier.verify(
            _token(kid="another-unknown-key"),
            expected_nonce="expected-nonce",
            now=NOW + timedelta(seconds=5),
            client=client,
        )
    assert calls == 1


def test_concurrent_jwks_cache_miss_is_single_fixed_origin_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return _json_response(_jwks())

    monkeypatch.setattr(telegram_oidc, "_verify_rs256_signature", lambda **_: True)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    verifier = TelegramIdTokenVerifierV1(_config())

    def verify(_: int) -> str:
        return verifier.verify(
            _token(),
            expected_nonce="expected-nonce",
            now=NOW,
            client=client,
        ).subject

    with ThreadPoolExecutor(max_workers=8) as executor:
        subjects = list(executor.map(verify, range(16)))

    assert subjects == ["424242"] * 16
    assert calls == [TELEGRAM_OIDC_JWKS_ENDPOINT]


def test_config_and_callback_code_are_fail_closed() -> None:
    with pytest.raises(ValueError, match="TELEGRAM_OIDC_CLIENT_ID_INVALID"):
        TelegramOidcConfigV1(
            client_id="not-numeric",
            client_secret=CLIENT_AUTH_FIXTURE,
            redirect_uri=CALLBACK,
        )
    with pytest.raises(ValueError, match="TELEGRAM_OIDC_REDIRECT_URI_INVALID"):
        TelegramOidcConfigV1(
            client_id=CLIENT_ID,
            client_secret=CLIENT_AUTH_FIXTURE,
            redirect_uri="http://omni.example/callback",
        )

    runtime = TelegramOidcRuntimeV1(
        config=_config(),
        transactions=AuthorizationTransactionRegistryV1(),
    )
    state = parse_qs(urlsplit(runtime.start(now=NOW)).query)["state"][0]
    with pytest.raises(TelegramOidcError, match="TELEGRAM_OIDC_CODE_INVALID"):
        runtime.complete(state=state, code="bad\ncode", now=NOW)


def test_config_repr_omits_provider_auth_material() -> None:
    config = _config()
    assert CLIENT_AUTH_FIXTURE not in repr(config)


def test_signature_failure_blocks_external_identity() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _: _json_response(_jwks()))
    )
    verifier = TelegramIdTokenVerifierV1(_config())
    with pytest.raises(TelegramOidcError, match="TELEGRAM_OIDC_SIGNATURE_INVALID"):
        verifier.verify(
            _token(),
            expected_nonce="expected-nonce",
            now=NOW,
            client=client,
        )


def test_jwks_algorithm_confusion_key_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            {
                "keys": [
                    {
                        "kty": "oct",
                        "kid": "telegram-key-1",
                        "alg": "HS256",
                        "k": "fixture-key-material",
                    }
                ]
            }
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    verifier = TelegramIdTokenVerifierV1(_config())
    with pytest.raises(TelegramOidcError, match="TELEGRAM_OIDC_JWKS_INVALID"):
        verifier.verify(
            _token(),
            expected_nonce="expected-nonce",
            now=NOW,
            client=client,
        )


def test_duplicate_provider_json_members_fail_closed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            content=b'{"id_token":"first","id_token":"second"}',
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    runtime = TelegramOidcRuntimeV1(
        config=_config(),
        transactions=AuthorizationTransactionRegistryV1(),
        client=client,
    )
    state = parse_qs(urlsplit(runtime.start(now=NOW)).query)["state"][0]
    with pytest.raises(
        TelegramOidcError,
        match="TELEGRAM_OIDC_PROVIDER_JSON_INVALID",
    ):
        runtime.complete(state=state, code="telegram-code", now=NOW)
