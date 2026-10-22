"""Pure Telegram ID-token validation, with no application, database or network IO.

The caller supplies a trusted JWKS document, audience and transaction nonce.
Unverified token headers never select a URL or an algorithm other than RS256.
"""
from __future__ import annotations

import json
import secrets

import jwt

TELEGRAM_ISSUER = "https://oauth.telegram.org"
MAX_ID_TOKEN_LENGTH = 16_384


class TelegramTokenError(ValueError):
    """Fixed diagnostic for a token that cannot authenticate a Telegram user."""


class TelegramKeyUnavailable(RuntimeError):
    """The trusted signing-key set is absent, ambiguous or structurally invalid."""


def nonce_matches(received: object, expected: object) -> bool:
    if not isinstance(received, str) or not isinstance(expected, str):
        return False
    if not received or not expected or not received.isascii() or not expected.isascii():
        return False
    return secrets.compare_digest(received, expected)


def signing_key(token: str, jwks: dict):
    if not isinstance(token, str) or not 64 <= len(token) <= MAX_ID_TOKEN_LENGTH or not token.isascii():
        raise TelegramTokenError("invalid_token_size_or_encoding")
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as error:
        raise TelegramTokenError("invalid_header") from error
    kid = header.get("kid")
    if (header.get("alg") != "RS256" or not isinstance(kid, str)
            or not 1 <= len(kid) <= 256 or not kid.isascii()
            or "crit" in header or "jku" in header or "x5u" in header):
        raise TelegramTokenError("unsupported_signing_header")
    try:
        keys = jwks.get("keys") if isinstance(jwks, dict) else None
        if not isinstance(keys, list) or not 1 <= len(keys) <= 64:
            raise TelegramKeyUnavailable("jwks_keys_missing")
        matches = [key for key in keys if isinstance(key, dict)
                   and key.get("kid") == kid and key.get("alg") == "RS256"
                   and key.get("kty") == "RSA" and key.get("use", "sig") == "sig"
                   and ("key_ops" not in key or
                        isinstance(key["key_ops"], list) and "verify" in key["key_ops"])]
        if len(matches) != 1:
            raise TelegramKeyUnavailable("jwks_kid_unavailable")
        key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(matches[0]))
        if key.key_size < 2048 or hasattr(key, "private_numbers"):
            raise TelegramKeyUnavailable("jwks_public_rsa_key_required")
        return key
    except TelegramKeyUnavailable:
        raise
    except (ValueError, TypeError, jwt.PyJWTError) as error:
        raise TelegramKeyUnavailable("jwks_invalid") from error


def verify_id_token(token: str, expected_nonce: str, *, client_id: str,
                    jwks: dict, issuer: str = TELEGRAM_ISSUER, leeway: int = 60) -> dict:
    key = signing_key(token, jwks)
    try:
        claims = jwt.decode(token, key, algorithms=["RS256"], audience=client_id,
                            issuer=issuer, leeway=leeway,
                            options={"require": ["exp", "iat", "iss", "aud", "sub", "nonce"]})
    except jwt.PyJWTError as error:
        raise TelegramTokenError("invalid_claims_or_signature") from error
    # This installation has one trusted client. Do not accept a token also
    # intended for another audience, or an authorized-party claim for it.
    if claims["aud"] not in (client_id, [client_id]) or claims.get("azp", client_id) != client_id:
        raise TelegramTokenError("untrusted_audience_or_authorized_party")
    if (type(claims["iat"]) is not int or type(claims["exp"]) is not int
            or claims["exp"] <= claims["iat"]):
        raise TelegramTokenError("invalid_token_times")
    if not nonce_matches(claims.get("nonce"), expected_nonce):
        raise TelegramTokenError("nonce_mismatch")
    subject = claims.get("sub")
    if (not isinstance(subject, str) or not 1 <= len(subject) <= 255
            or any(ord(character) < 33 or ord(character) > 126 for character in subject)):
        raise TelegramTokenError("invalid_subject")
    return claims
