"""Pure Telegram ID-token validation, with no application, database or network IO.

The caller supplies a trusted JWKS document, audience and transaction nonce.
Only signature-verified headers are inspected; trusted keys and RS256 are fixed
independently of the token, and no header can select a network destination.
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


def _signing_candidates(jwks: dict) -> list[dict]:
    keys = jwks.get("keys") if isinstance(jwks, dict) else None
    if not isinstance(keys, list) or not 1 <= len(keys) <= 64:
        raise TelegramKeyUnavailable("jwks_keys_missing")
    candidates = [key for key in keys if isinstance(key, dict)
                  and key.get("alg") == "RS256" and key.get("kty") == "RSA"
                  and key.get("use", "sig") == "sig"
                  and ("key_ops" not in key or
                       isinstance(key["key_ops"], list) and "verify" in key["key_ops"])]
    if not candidates:
        raise TelegramKeyUnavailable("jwks_kid_unavailable")
    return candidates


def _rsa_public_key(candidate: dict):
    try:
        key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(candidate))
    except (ValueError, TypeError, jwt.PyJWTError) as error:
        raise TelegramKeyUnavailable("jwks_invalid") from error
    if key.key_size < 2048 or hasattr(key, "private_numbers"):
        raise TelegramKeyUnavailable("jwks_public_rsa_key_required")
    return key


def _verified_signing_kid(header: dict, candidates: list[dict]) -> str:
    kid = header.get("kid")
    if (header.get("alg") != "RS256" or not isinstance(kid, str)
            or not 1 <= len(kid) <= 256 or not kid.isascii()
            or "crit" in header or "jku" in header or "x5u" in header):
        raise TelegramTokenError("unsupported_signing_header")
    # Count all eligible entries, including malformed key material: dropping a
    # malformed duplicate must never turn an ambiguous kid into a trusted one.
    if sum(candidate.get("kid") == kid for candidate in candidates) != 1:
        raise TelegramKeyUnavailable("jwks_kid_unavailable")
    return kid


def _decode_verified(token: str, candidates: list[dict], *, client_id: str,
                     issuer: str, leeway: int) -> dict:
    key_available = False
    for candidate in candidates:
        try:
            key = _rsa_public_key(candidate)
        except TelegramKeyUnavailable:
            continue
        key_available = True
        try:
            decoded = jwt.decode_complete(
                token, key, algorithms=["RS256"], audience=client_id,
                issuer=issuer, leeway=leeway,
                options={"require": ["exp", "iat", "iss", "aud", "sub", "nonce"]})
        except jwt.InvalidSignatureError:
            continue
        except jwt.PyJWTError as error:
            raise TelegramTokenError("invalid_claims_or_signature") from error
        kid = _verified_signing_kid(decoded["header"], candidates)
        if candidate.get("kid") == kid:
            return decoded["payload"]
    if not key_available:
        raise TelegramKeyUnavailable("jwks_public_rsa_key_required")
    raise TelegramTokenError("invalid_claims_or_signature")


def verify_id_token(token: str, expected_nonce: str, *, client_id: str,
                    jwks: dict, issuer: str = TELEGRAM_ISSUER, leeway: int = 60) -> dict:
    if not isinstance(token, str) or not 64 <= len(token) <= MAX_ID_TOKEN_LENGTH or not token.isascii():
        raise TelegramTokenError("invalid_token_size_or_encoding")
    claims = _decode_verified(token, _signing_candidates(jwks), client_id=client_id,
                              issuer=issuer, leeway=leeway)
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
