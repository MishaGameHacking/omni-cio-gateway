from __future__ import annotations

import base64
import os

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from starlette.requests import Request

from omnicio.main import CANONICAL_ORIGIN, client_ip, require_same_origin
from omnicio.security import (
    SecurityValueError,
    client_ip_digest,
    decrypt_secret,
    encrypt_secret,
    format_public_id,
    generate_oauth_state,
    generate_pkce_verifier,
    open_vkid_flow,
    parse_public_id,
    pkce_challenge,
    seal_vkid_flow,
)


def test_public_id_is_exactly_nine_digits() -> None:
    assert format_public_id(1) == "000000001"
    assert format_public_id(999_999_999) == "999999999"

    with pytest.raises(SecurityValueError):
        format_public_id(0)
    with pytest.raises(SecurityValueError):
        format_public_id(1_000_000_000)


def test_public_id_parser_rejects_malformed_or_zero_values() -> None:
    assert parse_public_id("000000001") == 1
    assert parse_public_id("999999999") == 999_999_999

    for value in ("1", "000000000", "1000000000", "00000000x"):
        with pytest.raises(SecurityValueError):
            parse_public_id(value)


def test_secret_encryption_does_not_store_plaintext() -> None:
    key = Fernet.generate_key().decode("ascii")
    plaintext = "t.example-owner-credential"
    encrypted = encrypt_secret(plaintext, key)

    assert encrypted != plaintext.encode()
    assert plaintext.encode() not in encrypted


def test_secret_encryption_round_trip() -> None:
    key = Fernet.generate_key().decode("ascii")
    plaintext = "t.example-owner-credential"
    encrypted = encrypt_secret(plaintext, key)

    assert decrypt_secret(encrypted, key) == plaintext

    wrong_key = Fernet.generate_key().decode("ascii")
    with pytest.raises(SecurityValueError):
        decrypt_secret(encrypted, wrong_key)


def test_pkce_challenge_is_stable_and_urlsafe() -> None:
    verifier = generate_pkce_verifier()
    challenge = pkce_challenge(verifier)

    assert 43 <= len(verifier) <= 128
    assert "=" not in challenge
    assert challenge == pkce_challenge(verifier)


def test_vkid_flow_round_trip_and_tamper_rejection() -> None:
    key = Fernet.generate_key().decode("ascii")
    state = generate_oauth_state()
    verifier = generate_pkce_verifier()
    versions = {
        "privacy_policy": "2026-10-02-v3",
        "personal_data_consent": "2026-10-02-v3",
        "terms": "2026-10-02-v3",
    }
    token = seal_vkid_flow(
        state=state,
        code_verifier=verifier,
        legal_versions=versions,
        crypto_key=key,
    )

    assert open_vkid_flow(
        token,
        crypto_key=key,
        ttl_seconds=600,
    ) == (state, verifier, versions)

    with pytest.raises(SecurityValueError):
        open_vkid_flow(
            token[:-1] + ("A" if token[-1] != "A" else "B"),
            crypto_key=key,
            ttl_seconds=600,
        )


def test_client_ip_digest_is_keyed() -> None:
    first = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
    second = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")

    assert client_ip_digest("203.0.113.10", first) != client_ip_digest(
        "203.0.113.10",
        second,
    )


def _request(client_host: str, headers: dict[str, str]) -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "https",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": [
                (name.lower().encode("ascii"), value.encode("ascii"))
                for name, value in headers.items()
            ],
            "client": (client_host, 12345),
            "server": ("omnicio.ru", 443),
        }
    )


def test_client_ip_ignores_untrusted_forwarded_headers() -> None:
    request = _request(
        "198.51.100.20",
        {
            "x-real-ip": "203.0.113.10",
            "x-forwarded-for": "203.0.113.11",
        },
    )

    assert client_ip(request) == "198.51.100.20"


def test_client_ip_trusts_nginx_overwritten_real_ip_only_from_loopback() -> None:
    request = _request(
        "127.0.0.1",
        {
            "x-real-ip": "203.0.113.10",
            "x-forwarded-for": "192.0.2.55, 203.0.113.10",
        },
    )

    assert client_ip(request) == "203.0.113.10"


def test_client_ip_rejects_invalid_proxy_value() -> None:
    request = _request(
        "127.0.0.1",
        {
            "x-real-ip": "not-an-ip",
            "x-forwarded-for": "203.0.113.10",
        },
    )

    assert client_ip(request) == "unknown"


def test_state_changing_requests_require_canonical_origin() -> None:
    accepted = _request("127.0.0.1", {"origin": CANONICAL_ORIGIN})
    require_same_origin(accepted)

    for headers in ({}, {"origin": "https://evil.example"}):
        rejected = _request("127.0.0.1", headers)
        with pytest.raises(HTTPException) as error:
            require_same_origin(rejected)
        assert error.value.status_code == 403
