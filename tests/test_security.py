from __future__ import annotations

import base64
import os

import pytest
from cryptography.fernet import Fernet

from omnicio.security import (
    SecurityValueError,
    decrypt_phone,
    encrypt_phone,
    encrypt_secret,
    format_public_id,
    normalize_russian_mobile,
    otp_digest,
    parse_public_id,
    verify_otp_digest,
)


def test_phone_accepts_only_requested_russian_mobile_shape() -> None:
    assert normalize_russian_mobile("+79161234567") == "+79161234567"

    for value in (
        "79161234567",
        "+78161234567",
        "+7916123456",
        "+791612345678",
        "+7 916 123-45-67",
        "+7999abc4567",
    ):
        with pytest.raises(SecurityValueError):
            normalize_russian_mobile(value)


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


def test_phone_encryption_round_trip() -> None:
    key = Fernet.generate_key().decode("ascii")
    encrypted = encrypt_phone("+79161234567", key)

    assert encrypted != b"+79161234567"
    assert decrypt_phone(encrypted, key) == "+79161234567"


def test_otp_digest_is_challenge_bound() -> None:
    key = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
    digest = otp_digest("challenge-a", "123456", key)

    assert verify_otp_digest("challenge-a", "123456", digest, key)
    assert not verify_otp_digest("challenge-a", "654321", digest, key)
    assert not verify_otp_digest("challenge-b", "123456", digest, key)


def test_secret_encryption_does_not_store_plaintext() -> None:
    key = Fernet.generate_key().decode("ascii")
    plaintext = "t.example-owner-credential"
    encrypted = encrypt_secret(plaintext, key)

    assert encrypted != plaintext.encode()
    assert plaintext.encode() not in encrypted
