from __future__ import annotations

import base64
import os

import pytest
from cryptography.fernet import Fernet

from omnicio.security import (
    SecurityValueError,
    client_ip_digest,
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
        "privacy_policy": "2026-10-01",
        "personal_data_consent": "2026-10-01",
        "terms": "2026-10-01",
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
