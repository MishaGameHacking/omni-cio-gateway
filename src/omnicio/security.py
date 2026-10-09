"""Security primitives for owner authentication, sessions, and secrets."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import unicodedata
import urllib.error
import urllib.request
from typing import Any

from cryptography.exceptions import InvalidKey
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

PUBLIC_ID_MIN = 1
PUBLIC_ID_MAX = 999_999_999


class SecurityValueError(ValueError):
    """Raised when a security-sensitive value is malformed."""


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Keep provider credentials and one-shot requests at their original endpoint."""

    def redirect_request(
        self, req: urllib.request.Request, fp: Any, code: int, msg: str,
        headers: Any, newurl: str,
    ) -> None:
        # The URL may contain OAuth secrets; omit it from the raised error too.
        raise urllib.error.HTTPError("", code, "provider_redirect_rejected", headers, fp)


def parse_public_id(value: str) -> int:
    if len(value) != 9 or not value.isascii() or not value.isdecimal():
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


def encrypt_secret(value: str, crypto_key: str) -> bytes:
    try:
        return Fernet(crypto_key.encode("ascii")).encrypt(value.encode())
    except ValueError as exc:
        raise SecurityValueError("invalid secret encryption key") from exc


def decrypt_secret(value: bytes, crypto_key: str) -> str:
    try:
        return Fernet(crypto_key.encode("ascii")).decrypt(value).decode()
    except (InvalidToken, ValueError) as exc:
        raise SecurityValueError("invalid encrypted secret or encryption key") from exc


def generate_session_token() -> str:
    return secrets.token_urlsafe(48)


def session_digest(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def client_ip_digest(ip_address: str, ip_key: str) -> bytes:
    key = _key_bytes(ip_key, name="client ip key")
    return hmac.new(key, ip_address.encode(), hashlib.sha256).digest()


# Password length is measured in NFC Unicode code points. Limits keep expensive
# password hashing bounded; composition and periodic-change rules are not imposed.
PASSWORD_MIN_LENGTH = 15
PASSWORD_MAX_LENGTH = 128
PASSWORD_MEMORY_KIB = 19_456
PASSWORD_ITERATIONS = 2
PASSWORD_PARALLELISM = 1
EMAIL_CODE_DIGITS = 8
EMAIL_CODE_TTL_SECONDS = 600
EMAIL_RESEND_SECONDS = 60
EMAIL_CODE_MAX_ATTEMPTS = 5
EMAIL_DOMAINS = ("gmail.com", "mail.ru", "xmail.ru")
# Common long passwords that pass the minimum length. Short compromised values
# already fail length validation. Comparison uses the whole candidate only.
_PASSWORD_BLOCKLIST = frozenset({
    "123456789012345", "1234567890123456", "12345678901234567",
    "123456789012345678", "1234567890123456789", "12345678901234567890",
    "123456789123456789", "1234567812345678", "1234567890abcdef",
    "passwordpassword", "passwordpassword1", "passwordpassword123",
    "password123456789", "password12345678", "password1234567",
    "password1234567890", "qwertyuiopasdfgh", "qwertyuiopasdfghjkl",
    "qwertyuiop123456", "qwerty1234567890", "qwertyqwertyqwerty",
    "asdfghjklqwertyuiop", "asdfghjkl123456789", "iloveyouiloveyou",
    "iloveyou123456789", "adminadminadmin", "administrator123",
    "letmeinletmeinletmein", "changemechangeme", "welcome123456789",
    "correcthorsebatterystaple", "парольпарольпароль", "йцукенгшщзфывапр",
    "omnicioomnicioomnicio",
})


def password_bytes(password: str) -> bytes:
    """Normalize the complete password without stripping spaces or truncating it."""
    normalized = unicodedata.normalize("NFC", password)
    if not 1 <= len(normalized) <= PASSWORD_MAX_LENGTH:
        raise SecurityValueError("password_length_invalid")
    return normalized.encode("utf-8")


def validate_new_password(password: str, email: str) -> None:
    normalized = unicodedata.normalize("NFC", password)
    password_bytes(password)
    if len(normalized) < PASSWORD_MIN_LENGTH:
        raise SecurityValueError("password_too_short")
    candidate = normalized.casefold()
    local = email.partition("@")[0].casefold()
    if (candidate in _PASSWORD_BLOCKLIST or candidate in {email.casefold(), local}
            or len(set(candidate)) == 1
            or any(candidate == item * count for item in ("omnicio", local) if item
                   for count in range(2, 10))):
        raise SecurityValueError("password_compromised_or_common")


def hash_password(password: str) -> str:
    """Generate a fresh Argon2id PHC verifier using the existing crypto dependency."""
    return Argon2id(
        salt=secrets.token_bytes(16), length=32, iterations=PASSWORD_ITERATIONS,
        lanes=PASSWORD_PARALLELISM, memory_cost=PASSWORD_MEMORY_KIB,
    ).derive_phc_encoded(password_bytes(password))


def verify_password(password: str, encoded: str) -> bool:
    try:
        Argon2id.verify_phc_encoded(password_bytes(password), encoded)
    except (InvalidKey, SecurityValueError):
        return False
    return True


def generate_email_code() -> str:
    return f"{secrets.randbelow(10 ** EMAIL_CODE_DIGITS):0{EMAIL_CODE_DIGITS}d}"


def email_code_digest(challenge_id: str, code: str, key: str) -> bytes:
    """A database copy alone cannot enumerate a short email code's keyed verifier."""
    return hmac.new(
        _key_bytes(key, name="auth code key"),
        f"email-code:v1:{challenge_id}:{code}".encode(), hashlib.sha256,
    ).digest()


def auth_rate_digest(scope: str, value: str, key: str) -> bytes:
    return hmac.new(
        _key_bytes(key, name="auth rate key"),
        f"auth-rate:v1:{scope}:{value}".encode(), hashlib.sha256,
    ).digest()
