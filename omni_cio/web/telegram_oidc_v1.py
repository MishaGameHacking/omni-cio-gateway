from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import re
from threading import RLock
from typing import Any, Protocol
from urllib.parse import urlencode, urlsplit

import httpx

from omni_cio.web.identity_v1 import IdentityProviderV1, VerifiedExternalIdentityV1
from omni_cio.web.provider_auth_v1 import (
    AuthorizationTransactionStoreLike,
    ConsumedAuthorizationTransactionV1,
    ProviderAuthorizationStartV1,
    ProviderAuthorizationError,
)

TELEGRAM_OIDC_ISSUER = "https://oauth.telegram.org"
TELEGRAM_OIDC_AUTHORIZATION_ENDPOINT = f"{TELEGRAM_OIDC_ISSUER}/auth"
TELEGRAM_OIDC_TOKEN_ENDPOINT = f"{TELEGRAM_OIDC_ISSUER}/token"
TELEGRAM_OIDC_JWKS_ENDPOINT = f"{TELEGRAM_OIDC_ISSUER}/.well-known/jwks.json"

_MAX_TOKEN_RESPONSE_BYTES = 32_768
_MAX_JWKS_RESPONSE_BYTES = 131_072
_MAX_ID_TOKEN_CHARS = 16_384
_MAX_JWKS_KEYS = 32
_MIN_RSA_BITS = 2048
_MAX_RSA_BITS = 4096
_B64URL_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
_KID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_CODE_PATTERN = re.compile(r"^[\x21-\x7e]{1,2048}$")
_SHA256_DIGEST_INFO_PREFIX = bytes(
    (48, 49, 48, 13, 6, 9, 96, 134, 72, 1, 101, 3, 4, 2, 1, 5, 0, 4, 32)
)


class TelegramOidcError(ProviderAuthorizationError):
    """Fail-closed Telegram OIDC transport or verification error."""


@dataclass(frozen=True, slots=True)
class TelegramOidcConfigV1:
    client_id: str
    client_secret: str = field(repr=False)
    redirect_uri: str
    timeout_seconds: float = 5.0
    clock_skew: timedelta = timedelta(seconds=60)
    jwks_cache_lifetime: timedelta = timedelta(minutes=1)

    def __post_init__(self) -> None:
        if not self.client_id.isascii() or not self.client_id.isdigit():
            raise ValueError("TELEGRAM_OIDC_CLIENT_ID_INVALID")
        if not 1 <= len(self.client_id) <= 64:
            raise ValueError("TELEGRAM_OIDC_CLIENT_ID_INVALID")
        if not _visible_ascii(self.client_secret, minimum=16, maximum=512):
            raise ValueError("TELEGRAM_OIDC_CLIENT_CREDENTIAL_INVALID")
        _validate_redirect_uri(self.redirect_uri)
        if not 0.5 <= self.timeout_seconds <= 15.0:
            raise ValueError("TELEGRAM_OIDC_TIMEOUT_INVALID")
        if self.clock_skew < timedelta(0) or self.clock_skew > timedelta(minutes=2):
            raise ValueError("TELEGRAM_OIDC_CLOCK_SKEW_INVALID")
        if not timedelta(seconds=10) <= self.jwks_cache_lifetime <= timedelta(hours=1):
            raise ValueError("TELEGRAM_OIDC_JWKS_CACHE_INVALID")


@dataclass(frozen=True, slots=True)
class _RsaPublicKeyV1:
    modulus: int
    exponent: int
    size_bytes: int


class TelegramIdTokenVerifierLike(Protocol):
    def verify(
        self,
        id_token: str,
        *,
        expected_nonce: str,
        now: datetime,
        client: httpx.Client,
    ) -> VerifiedExternalIdentityV1: ...


def _visible_ascii(value: str, *, minimum: int, maximum: int) -> bool:
    return (
        isinstance(value, str)
        and minimum <= len(value) <= maximum
        and value.isascii()
        and all(0x21 <= ord(char) <= 0x7E for char in value)
    )


def _validate_redirect_uri(value: str) -> None:
    if not isinstance(value, str) or value != value.strip():
        raise ValueError("TELEGRAM_OIDC_REDIRECT_URI_INVALID")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("TELEGRAM_OIDC_REDIRECT_URI_INVALID") from exc
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
        or not parsed.path.startswith("/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("TELEGRAM_OIDC_REDIRECT_URI_INVALID")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("TELEGRAM_OIDC_CLOCK_NOT_UTC_AWARE")
    return value.astimezone(timezone.utc)


def _b64url_decode(value: object, *, reason: str, maximum: int) -> bytes:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > maximum
        or _B64URL_PATTERN.fullmatch(value) is None
    ):
        raise TelegramOidcError(reason)
    padded = value + ("=" * (-len(value) % 4))
    try:
        return base64.b64decode(padded, altchars=b"-_", validate=True)
    except (binascii.Error, ValueError):
        raise TelegramOidcError(reason) from None


def _unique_json_object(payload: bytes, *, reason: str) -> dict[str, Any]:
    def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON member")
            result[key] = value
        return result

    try:
        decoded = payload.decode("utf-8")
        value = json.loads(decoded, object_pairs_hook=unique_pairs)
    except (UnicodeDecodeError, ValueError):
        raise TelegramOidcError(reason) from None
    if not isinstance(value, dict):
        raise TelegramOidcError(reason)
    return value


def _content_type(response: httpx.Response) -> str:
    return response.headers.get("content-type", "").partition(";")[0].strip().lower()


def _read_bounded_json_response(
    response: httpx.Response,
    *,
    max_response_bytes: int,
) -> dict[str, Any]:
    if response.status_code != 200 or _content_type(response) != "application/json":
        raise TelegramOidcError("TELEGRAM_OIDC_PROVIDER_RESPONSE_INVALID")
    declared = response.headers.get("content-length")
    if declared is not None:
        try:
            if int(declared) > max_response_bytes:
                raise TelegramOidcError("TELEGRAM_OIDC_PROVIDER_RESPONSE_TOO_LARGE")
        except ValueError:
            pass
    payload = bytearray()
    for chunk in response.iter_bytes():
        if len(payload) + len(chunk) > max_response_bytes:
            raise TelegramOidcError("TELEGRAM_OIDC_PROVIDER_RESPONSE_TOO_LARGE")
        payload.extend(chunk)
    return _unique_json_object(
        bytes(payload),
        reason="TELEGRAM_OIDC_PROVIDER_JSON_INVALID",
    )


def _bounded_token_response(
    client: httpx.Client,
    *,
    timeout_seconds: float,
    data: dict[str, str],
    auth: httpx.Auth,
) -> dict[str, Any]:
    """POST only to Telegram's fixed token endpoint."""

    try:
        with client.stream(
            "POST",
            TELEGRAM_OIDC_TOKEN_ENDPOINT,
            data=data,
            auth=auth,
            timeout=timeout_seconds,
            follow_redirects=False,
            headers={"Accept": "application/json"},
        ) as response:
            return _read_bounded_json_response(
                response,
                max_response_bytes=_MAX_TOKEN_RESPONSE_BYTES,
            )
    except TelegramOidcError:
        raise
    except httpx.HTTPError:
        raise TelegramOidcError("TELEGRAM_OIDC_NETWORK_ERROR") from None


def _bounded_jwks_response(
    client: httpx.Client,
    *,
    timeout_seconds: float,
) -> dict[str, Any]:
    """GET only from Telegram's fixed JWKS endpoint."""

    try:
        with client.stream(
            "GET",
            TELEGRAM_OIDC_JWKS_ENDPOINT,
            timeout=timeout_seconds,
            follow_redirects=False,
            headers={"Accept": "application/json"},
        ) as response:
            return _read_bounded_json_response(
                response,
                max_response_bytes=_MAX_JWKS_RESPONSE_BYTES,
            )
    except TelegramOidcError:
        raise
    except httpx.HTTPError:
        raise TelegramOidcError("TELEGRAM_OIDC_NETWORK_ERROR") from None


def _rsa_public_key(jwk: dict[str, Any]) -> tuple[str, _RsaPublicKeyV1]:
    kid = jwk.get("kid")
    if not isinstance(kid, str) or _KID_PATTERN.fullmatch(kid) is None:
        raise TelegramOidcError("TELEGRAM_OIDC_JWKS_INVALID")
    if jwk.get("kty") != "RSA":
        raise TelegramOidcError("TELEGRAM_OIDC_JWKS_INVALID")
    if jwk.get("use") not in {None, "sig"} or jwk.get("alg") not in {None, "RS256"}:
        raise TelegramOidcError("TELEGRAM_OIDC_JWKS_INVALID")
    key_ops = jwk.get("key_ops")
    if key_ops is not None and (
        not isinstance(key_ops, list)
        or "verify" not in key_ops
        or any(not isinstance(item, str) for item in key_ops)
    ):
        raise TelegramOidcError("TELEGRAM_OIDC_JWKS_INVALID")
    modulus_raw = _b64url_decode(
        jwk.get("n"),
        reason="TELEGRAM_OIDC_JWKS_INVALID",
        maximum=1024,
    )
    exponent_raw = _b64url_decode(
        jwk.get("e"),
        reason="TELEGRAM_OIDC_JWKS_INVALID",
        maximum=16,
    )
    if (
        not modulus_raw
        or modulus_raw[0] == 0
        or not exponent_raw
        or exponent_raw[0] == 0
    ):
        raise TelegramOidcError("TELEGRAM_OIDC_JWKS_INVALID")
    modulus = int.from_bytes(modulus_raw, "big")
    exponent = int.from_bytes(exponent_raw, "big")
    bits = modulus.bit_length()
    if bits < _MIN_RSA_BITS or bits > _MAX_RSA_BITS:
        raise TelegramOidcError("TELEGRAM_OIDC_JWKS_INVALID")
    if exponent < 3 or exponent > 0xFFFFFFFF or exponent % 2 == 0:
        raise TelegramOidcError("TELEGRAM_OIDC_JWKS_INVALID")
    return kid, _RsaPublicKeyV1(
        modulus=modulus,
        exponent=exponent,
        size_bytes=(bits + 7) // 8,
    )


def _parse_jwks(payload: dict[str, Any]) -> dict[str, _RsaPublicKeyV1]:
    items = payload.get("keys")
    if not isinstance(items, list) or not 1 <= len(items) <= _MAX_JWKS_KEYS:
        raise TelegramOidcError("TELEGRAM_OIDC_JWKS_INVALID")
    keys: dict[str, _RsaPublicKeyV1] = {}
    for item in items:
        if not isinstance(item, dict):
            raise TelegramOidcError("TELEGRAM_OIDC_JWKS_INVALID")
        algorithm = item.get("alg")
        key_type = item.get("kty")
        if algorithm not in {None, "RS256"}:
            continue
        if key_type != "RSA":
            if algorithm == "RS256":
                raise TelegramOidcError("TELEGRAM_OIDC_JWKS_INVALID")
            continue
        kid, key = _rsa_public_key(item)
        if kid in keys:
            raise TelegramOidcError("TELEGRAM_OIDC_JWKS_INVALID")
        keys[kid] = key
    if not keys:
        raise TelegramOidcError("TELEGRAM_OIDC_JWKS_INVALID")
    return keys


def _verify_rs256_signature(
    *,
    signing_input: bytes,
    signature: bytes,
    key: _RsaPublicKeyV1,
) -> bool:
    if len(signature) != key.size_bytes:
        return False
    signature_value = int.from_bytes(signature, "big")
    if signature_value >= key.modulus:
        return False
    encoded = pow(signature_value, key.exponent, key.modulus).to_bytes(
        key.size_bytes,
        "big",
    )
    digest_info = _SHA256_DIGEST_INFO_PREFIX + hashlib.sha256(signing_input).digest()
    padding_length = key.size_bytes - len(digest_info) - 3
    if padding_length < 8:
        return False
    expected = b"\x00\x01" + (b"\xff" * padding_length) + b"\x00" + digest_info
    return hmac.compare_digest(encoded, expected)


def _jwt_parts(id_token: str) -> tuple[dict[str, Any], dict[str, Any], bytes, bytes]:
    if not isinstance(id_token, str) or not 1 <= len(id_token) <= _MAX_ID_TOKEN_CHARS:
        raise TelegramOidcError("TELEGRAM_OIDC_ID_TOKEN_INVALID")
    parts = id_token.split(".")
    if len(parts) != 3:
        raise TelegramOidcError("TELEGRAM_OIDC_ID_TOKEN_INVALID")
    header_segment, payload_segment, signature_segment = parts
    header = _unique_json_object(
        _b64url_decode(
            header_segment,
            reason="TELEGRAM_OIDC_ID_TOKEN_INVALID",
            maximum=4096,
        ),
        reason="TELEGRAM_OIDC_ID_TOKEN_INVALID",
    )
    payload = _unique_json_object(
        _b64url_decode(
            payload_segment,
            reason="TELEGRAM_OIDC_ID_TOKEN_INVALID",
            maximum=12_288,
        ),
        reason="TELEGRAM_OIDC_ID_TOKEN_INVALID",
    )
    signature = _b64url_decode(
        signature_segment,
        reason="TELEGRAM_OIDC_ID_TOKEN_INVALID",
        maximum=1024,
    )
    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    return header, payload, signing_input, signature


def _validate_header(header: dict[str, Any]) -> str:
    if header.get("alg") != "RS256":
        raise TelegramOidcError("TELEGRAM_OIDC_ALGORITHM_INVALID")
    if "crit" in header or any(
        name in header for name in ("jku", "jwk", "x5u", "x5c", "b64")
    ):
        raise TelegramOidcError("TELEGRAM_OIDC_HEADER_INVALID")
    token_type = header.get("typ")
    if token_type is not None and token_type != "JWT":
        raise TelegramOidcError("TELEGRAM_OIDC_HEADER_INVALID")
    kid = header.get("kid")
    if not isinstance(kid, str) or _KID_PATTERN.fullmatch(kid) is None:
        raise TelegramOidcError("TELEGRAM_OIDC_HEADER_INVALID")
    return kid


def _integer_claim(payload: dict[str, Any], name: str) -> int:
    value = payload.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TelegramOidcError("TELEGRAM_OIDC_CLAIMS_INVALID")
    return value


def _validate_claims(
    payload: dict[str, Any],
    *,
    client_id: str,
    expected_nonce: str,
    now: datetime,
    clock_skew: timedelta,
) -> str:
    if payload.get("iss") != TELEGRAM_OIDC_ISSUER:
        raise TelegramOidcError("TELEGRAM_OIDC_CLAIMS_INVALID")
    if payload.get("aud") != client_id:
        raise TelegramOidcError("TELEGRAM_OIDC_CLAIMS_INVALID")
    if payload.get("nonce") != expected_nonce:
        raise TelegramOidcError("TELEGRAM_OIDC_CLAIMS_INVALID")
    subject = payload.get("sub")
    if not isinstance(subject, str) or not 1 <= len(subject) <= 256:
        raise TelegramOidcError("TELEGRAM_OIDC_CLAIMS_INVALID")
    if not subject.isascii() or any(
        ord(char) < 0x21 or ord(char) > 0x7E for char in subject
    ):
        raise TelegramOidcError("TELEGRAM_OIDC_CLAIMS_INVALID")

    now_seconds = int(_utc(now).timestamp())
    skew_seconds = int(clock_skew.total_seconds())
    issued_at = _integer_claim(payload, "iat")
    expires_at = _integer_claim(payload, "exp")
    if issued_at <= 0 or expires_at <= 0:
        raise TelegramOidcError("TELEGRAM_OIDC_CLAIMS_INVALID")
    if issued_at > now_seconds + skew_seconds or expires_at <= issued_at:
        raise TelegramOidcError("TELEGRAM_OIDC_CLAIMS_INVALID")
    if now_seconds > expires_at + skew_seconds:
        raise TelegramOidcError("TELEGRAM_OIDC_CLAIMS_INVALID")
    not_before = payload.get("nbf")
    if not_before is not None:
        if isinstance(not_before, bool) or not isinstance(not_before, int):
            raise TelegramOidcError("TELEGRAM_OIDC_CLAIMS_INVALID")
        if now_seconds + skew_seconds < not_before:
            raise TelegramOidcError("TELEGRAM_OIDC_CLAIMS_INVALID")
    return subject


class TelegramIdTokenVerifierV1:
    """Verify Telegram RS256 ID tokens against the fixed official JWKS origin."""

    def __init__(self, config: TelegramOidcConfigV1) -> None:
        self._config = config
        self._keys: dict[str, _RsaPublicKeyV1] = {}
        self._keys_expires_at: datetime | None = None
        self._lock = RLock()

    def verify(
        self,
        id_token: str,
        *,
        expected_nonce: str,
        now: datetime,
        client: httpx.Client,
    ) -> VerifiedExternalIdentityV1:
        timestamp = _utc(now)
        header, payload, signing_input, signature = _jwt_parts(id_token)
        kid = _validate_header(header)
        key = self._key_for(kid, now=timestamp, client=client)
        if not _verify_rs256_signature(
            signing_input=signing_input,
            signature=signature,
            key=key,
        ):
            raise TelegramOidcError("TELEGRAM_OIDC_SIGNATURE_INVALID")
        subject = _validate_claims(
            payload,
            client_id=self._config.client_id,
            expected_nonce=expected_nonce,
            now=timestamp,
            clock_skew=self._config.clock_skew,
        )
        return VerifiedExternalIdentityV1(
            provider=IdentityProviderV1.TELEGRAM,
            subject=subject,
        )

    def _key_for(
        self,
        kid: str,
        *,
        now: datetime,
        client: httpx.Client,
    ) -> _RsaPublicKeyV1:
        with self._lock:
            if self._keys_expires_at is not None and now < self._keys_expires_at:
                key = self._keys.get(kid)
                if key is None:
                    raise TelegramOidcError("TELEGRAM_OIDC_SIGNING_KEY_UNKNOWN")
                return key

            # Serialize the bounded fixed-origin refresh so a cache miss cannot
            # amplify into one provider request per concurrent login.
            payload = _bounded_jwks_response(
                client,
                timeout_seconds=self._config.timeout_seconds,
            )
            self._keys = _parse_jwks(payload)
            self._keys_expires_at = now + self._config.jwks_cache_lifetime
            key = self._keys.get(kid)
            if key is None:
                raise TelegramOidcError("TELEGRAM_OIDC_SIGNING_KEY_UNKNOWN")
            return key


class TelegramOidcRuntimeV1:
    """Dormant Telegram Authorization Code + PKCE adapter for WP22A Phase 5."""

    def __init__(
        self,
        *,
        config: TelegramOidcConfigV1,
        transactions: AuthorizationTransactionStoreLike,
        client: httpx.Client | None = None,
        verifier: TelegramIdTokenVerifierLike | None = None,
    ) -> None:
        self._config = config
        self._transactions = transactions
        self._client = client
        self._verifier = verifier or TelegramIdTokenVerifierV1(config)

    @property
    def provider(self) -> IdentityProviderV1:
        return IdentityProviderV1.TELEGRAM

    def start(self, *, now: datetime) -> ProviderAuthorizationStartV1:
        transaction = self._transactions.begin(
            provider=self.provider,
            redirect_uri=self._config.redirect_uri,
            now=now,
        )
        query = urlencode(
            {
                "client_id": self._config.client_id,
                "redirect_uri": transaction.redirect_uri,
                "response_type": "code",
                "scope": "openid",
                "state": transaction.state,
                "code_challenge": transaction.code_challenge,
                "code_challenge_method": "S256",
                "nonce": transaction.nonce,
            }
        )
        return ProviderAuthorizationStartV1(
            authorization_url=f"{TELEGRAM_OIDC_AUTHORIZATION_ENDPOINT}?{query}",
            browser_proof=transaction.browser_proof,
            expires_at=transaction.expires_at,
        )

    def complete(
        self,
        *,
        state: str,
        code: str,
        browser_proof: str,
        now: datetime,
        device_id: str | None = None,
    ) -> VerifiedExternalIdentityV1:
        if device_id is not None:
            raise TelegramOidcError("TELEGRAM_OIDC_CALLBACK_INVALID")
        if not isinstance(code, str) or _CODE_PATTERN.fullmatch(code) is None:
            raise TelegramOidcError("TELEGRAM_OIDC_CODE_INVALID")
        transaction = self._transactions.consume(
            provider=self.provider,
            state=state,
            browser_proof=browser_proof,
            now=now,
        )
        if self._client is not None:
            return self._complete_with_client(
                transaction=transaction,
                code=code,
                now=now,
                client=self._client,
            )
        try:
            with httpx.Client(
                timeout=self._config.timeout_seconds,
                verify=True,
                follow_redirects=False,
            ) as client:
                return self._complete_with_client(
                    transaction=transaction,
                    code=code,
                    now=now,
                    client=client,
                )
        except TelegramOidcError:
            raise
        except httpx.HTTPError:
            raise TelegramOidcError("TELEGRAM_OIDC_NETWORK_ERROR") from None

    def _complete_with_client(
        self,
        *,
        transaction: ConsumedAuthorizationTransactionV1,
        code: str,
        now: datetime,
        client: httpx.Client,
    ) -> VerifiedExternalIdentityV1:
        payload = _bounded_token_response(
            client,
            timeout_seconds=self._config.timeout_seconds,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": transaction.redirect_uri,
                "client_id": self._config.client_id,
                "code_verifier": transaction.code_verifier,
            },
            auth=httpx.BasicAuth(
                username=self._config.client_id,
                password=self._config.client_secret,
            ),
        )
        id_token = payload.get("id_token")
        payload.clear()
        if not isinstance(id_token, str):
            raise TelegramOidcError("TELEGRAM_OIDC_ID_TOKEN_MISSING")
        return self._verifier.verify(
            id_token,
            expected_nonce=transaction.nonce,
            now=now,
            client=client,
        )
