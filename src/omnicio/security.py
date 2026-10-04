"""Security primitives for owner authentication, sessions, and secrets."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets

from cryptography.fernet import Fernet, InvalidToken

PUBLIC_ID_MIN = 1
PUBLIC_ID_MAX = 999_999_999


class SecurityValueError(ValueError):
    """Raised when a security-sensitive value is malformed."""


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


def encrypt_secret(value: str, crypto_key: str) -> bytes:
    try:
        return Fernet(crypto_key.encode("ascii")).encrypt(value.encode())
    except ValueError as exc:
        raise SecurityValueError("invalid secret encryption key") from exc


def decrypt_secret(value: bytes, crypto_key: str) -> str:
    try:
        return Fernet(crypto_key.encode("ascii")).decrypt(value).decode()
    except (InvalidToken, ValueError, UnicodeError) as exc:
        raise SecurityValueError("invalid encrypted secret or encryption key") from exc


def generate_session_token() -> str:
    return secrets.token_urlsafe(48)


def session_digest(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def client_ip_digest(ip_address: str, ip_key: str) -> bytes:
    key = _key_bytes(ip_key, name="client ip key")
    return hmac.new(key, ip_address.encode(), hashlib.sha256).digest()


def generate_oauth_state() -> str:
    return secrets.token_urlsafe(32)


def generate_pkce_verifier() -> str:
    verifier = secrets.token_urlsafe(64)
    if not 43 <= len(verifier) <= 128:
        raise SecurityValueError("generated PKCE verifier has invalid length")
    return verifier


def pkce_challenge(verifier: str) -> str:
    if not 43 <= len(verifier) <= 128:
        raise SecurityValueError("PKCE verifier has invalid length")
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def seal_vkid_flow(
    *,
    state: str,
    code_verifier: str,
    legal_versions: dict[str, str],
    crypto_key: str,
) -> str:
    payload = json.dumps(
        {
            "state": state,
            "code_verifier": code_verifier,
            "legal_versions": legal_versions,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    try:
        return Fernet(crypto_key.encode("ascii")).encrypt(payload).decode("ascii")
    except (ValueError, UnicodeError) as exc:
        raise SecurityValueError("invalid VK ID flow encryption key") from exc


def open_vkid_flow(
    token: str,
    *,
    crypto_key: str,
    ttl_seconds: int,
) -> tuple[str, str, dict[str, str]]:
    try:
        raw = Fernet(crypto_key.encode("ascii")).decrypt(
            token.encode("ascii"),
            ttl=ttl_seconds,
        )
        payload = json.loads(raw)
    except (InvalidToken, ValueError) as exc:
        raise SecurityValueError("invalid or expired VK ID flow") from exc

    if not isinstance(payload, dict):
        raise SecurityValueError("invalid VK ID flow payload")
    state = payload.get("state")
    verifier = payload.get("code_verifier")
    versions = payload.get("legal_versions")
    if not isinstance(state, str) or not state:
        raise SecurityValueError("VK ID flow state is missing")
    if not isinstance(verifier, str) or not 43 <= len(verifier) <= 128:
        raise SecurityValueError("VK ID flow verifier is invalid")
    if not isinstance(versions, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in versions.items()
    ):
        raise SecurityValueError("VK ID flow legal versions are invalid")
    return state, verifier, versions
