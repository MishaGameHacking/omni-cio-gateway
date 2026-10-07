"""Security primitives for owner authentication, sessions, and secrets."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
from dataclasses import dataclass
from urllib.parse import parse_qsl

from cryptography.fernet import Fernet, InvalidToken

PUBLIC_ID_MIN = 1
PUBLIC_ID_MAX = 999_999_999
DEFAULT_AUTH_RETURN = "/#account/home"


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
    except (InvalidToken, ValueError) as exc:
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


@dataclass(frozen=True, slots=True)
class OAuthFlow:
    state: str
    code_verifier: str
    legal_versions: dict[str, str]
    link_user_id: str | None = None
    link_session_digest: str | None = None
    return_to: str = DEFAULT_AUTH_RETURN


def validate_auth_return_to(value: str) -> str:
    """Accept only a bounded application route; never redirect to a supplied origin."""
    if (not isinstance(value, str) or len(value) > 2048
            or not value.startswith("/#account/")
            or any(ord(char) < 32 or ord(char) == 127 or char == "\\" for char in value)):
        raise SecurityValueError("oauth_return_to_invalid")
    path, _, query = value[len("/#account/"):].partition("?")
    parts = path.split("/")
    if (not 1 <= len(parts) <= 2
            or parts[0] not in {
                "home", "portfolio", "market", "strategies", "assistant", "goals",
                "analytics", "events", "profile", "settings", "asset", "search",
            }
            or any(re.fullmatch(r"[a-z][a-z0-9-]{0,39}", part) is None for part in parts)):
        raise SecurityValueError("oauth_return_to_invalid")
    try:
        fields = parse_qsl(query, keep_blank_values=True, strict_parsing=True, max_num_fields=24)
    except ValueError as exc:
        raise SecurityValueError("oauth_return_to_invalid") from exc
    if (len({key for key, _ in fields}) != len(fields)
            or any(re.fullmatch(r"[a-z_]{1,30}", key) is None
                   or len(item) > 512 or "#" in item
                   or any(ord(char) < 32 or ord(char) == 127 for char in item)
                   for key, item in fields)):
        raise SecurityValueError("oauth_return_to_invalid")
    return value


def seal_oauth_flow(
    *,
    state: str,
    code_verifier: str,
    legal_versions: dict[str, str],
    crypto_key: str,
    provider: str = "vkid",
    link_user_id: str | None = None,
    link_session_digest: str | None = None,
    return_to: str = DEFAULT_AUTH_RETURN,
) -> str:
    if provider not in {"vkid", "tid"}:
        raise SecurityValueError("invalid OAuth provider")
    payload = json.dumps(
        {
            "state": state,
            "code_verifier": code_verifier,
            "legal_versions": legal_versions,
            "provider": provider,
            "link_user_id": link_user_id,
            "link_session_digest": link_session_digest,
            "return_to": validate_auth_return_to(return_to),
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    try:
        return Fernet(crypto_key.encode("ascii")).encrypt(payload).decode("ascii")
    except ValueError as exc:
        raise SecurityValueError("invalid OAuth flow encryption key") from exc


def open_oauth_flow(
    token: str,
    *,
    crypto_key: str,
    ttl_seconds: int,
    provider: str = "vkid",
) -> OAuthFlow:
    try:
        raw = Fernet(crypto_key.encode("ascii")).decrypt(
            token.encode("ascii"),
            ttl=ttl_seconds,
        )
        payload = json.loads(raw)
    except (InvalidToken, ValueError) as exc:
        raise SecurityValueError("invalid or expired OAuth flow") from exc

    if not isinstance(payload, dict):
        raise SecurityValueError("invalid OAuth flow payload")
    if provider not in {"vkid", "tid"} or payload.get("provider") != provider:
        raise SecurityValueError("OAuth provider mismatch")
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
    link_user = payload.get("link_user_id")
    link_session = payload.get("link_session_digest")
    if (link_user is None) != (link_session is None):
        raise SecurityValueError("OAuth link context is incomplete")
    if link_user is not None and (
        not isinstance(link_user, str) or len(link_user) != 36
        or not isinstance(link_session, str) or len(link_session) != 64
        or any(c not in "0123456789abcdef" for c in link_session)
    ):
        raise SecurityValueError("OAuth link context is invalid")
    return OAuthFlow(
        state, verifier, versions, link_user, link_session,
        validate_auth_return_to(payload.get("return_to", DEFAULT_AUTH_RETURN)),
    )
