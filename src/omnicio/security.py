"""Security primitives for phone identity, OTPs, and sessions."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets

from cryptography.fernet import Fernet, InvalidToken

PHONE_RE = re.compile(r"^\+79\d{9}$")
PUBLIC_ID_MIN = 1
PUBLIC_ID_MAX = 999_999_999


class SecurityValueError(ValueError):
    """Raised when a security-sensitive value is malformed."""


def normalize_russian_mobile(raw: str) -> str:
    """Return the canonical +79XXXXXXXXX form or reject the input.

    Only Russian mobile-number syntax requested by the product owner is accepted:
    +7 followed by 9 and nine more digits.
    """

    candidate = raw.strip()
    if not PHONE_RE.fullmatch(candidate):
        raise SecurityValueError("phone must match +79XXXXXXXXX")
    return candidate


def parse_public_id(value: str) -> int:
    if len(value) != 9 or not value.isdigit():
        raise SecurityValueError("public id must contain exactly 9 digits")
    parsed = int(value)
    if not PUBLIC_ID_MIN <= parsed <= PUBLIC_ID_MAX:
        raise SecurityValueError("public id is outside the supported range")
    return parsed


def format_public_id(value: int) -> str:
    if not PUBLIC_ID_MIN <= value <= PUBLIC_ID_MAX:
        raise SecurityValueError("public id is outside the 9-digit range")
    return f"{value:09d}"


def _key_bytes(value: str, *, name: str) -> bytes:
    data = value.encode()
    if len(data) < 32:
        raise SecurityValueError(f"{name} must contain at least 32 bytes")
    return data


def phone_lookup(phone: str, lookup_key: str) -> bytes:
    key = _key_bytes(lookup_key, name="lookup key")
    return hmac.new(key, phone.encode(), hashlib.sha256).digest()


def encrypt_phone(phone: str, crypto_key: str) -> bytes:
    try:
        return Fernet(crypto_key.encode("ascii")).encrypt(phone.encode())
    except (ValueError, UnicodeError) as exc:
        raise SecurityValueError("invalid phone encryption key") from exc


def decrypt_phone(ciphertext: bytes, crypto_key: str) -> str:
    try:
        return Fernet(crypto_key.encode("ascii")).decrypt(ciphertext).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeError) as exc:
        raise SecurityValueError("unable to decrypt phone") from exc


def encrypt_secret(value: str, crypto_key: str) -> bytes:
    try:
        return Fernet(crypto_key.encode("ascii")).encrypt(value.encode())
    except (ValueError, UnicodeError) as exc:
        raise SecurityValueError("invalid secret encryption key") from exc


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def otp_digest(challenge_id: str, code: str, otp_key: str) -> bytes:
    key = _key_bytes(otp_key, name="otp key")
    payload = f"{challenge_id}:{code}".encode()
    return hmac.new(key, payload, hashlib.sha256).digest()


def verify_otp_digest(
    challenge_id: str,
    code: str,
    expected_digest: bytes,
    otp_key: str,
) -> bool:
    actual = otp_digest(challenge_id, code, otp_key)
    return hmac.compare_digest(actual, expected_digest)


def generate_session_token() -> str:
    return secrets.token_urlsafe(48)


def session_digest(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def client_ip_digest(ip_address: str, ip_key: str) -> bytes:
    key = _key_bytes(ip_key, name="client ip key")
    return hmac.new(key, ip_address.encode(), hashlib.sha256).digest()
