"""Telegram OIDC and VK ID code exchange for the memory-only Android client."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from threading import BoundedSemaphore, Lock
from typing import Any
from uuid import UUID, uuid4

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from . import APPLICATION_USER_AGENT
from .config import Settings
from .db import Database, UserRecord
from .security import (
    NoRedirectHandler,
    auth_rate_digest,
    client_ip_digest,
    decrypt_secret,
    encrypt_secret,
    generate_session_token,
    session_digest,
)
from .social_store import FLOW_TTL_SECONDS, SocialAuthStore

CALLBACK_ROOT = "https://omnicio.ru/api/auth/social"
TELEGRAM_ISSUER = "https://oauth.telegram.org"
VK_ORIGIN = "https://id.vk.ru"
PROVIDERS = frozenset({"telegram", "vkid"})
_MAX_PROVIDER_BYTES = 65536


class SocialAuthError(ValueError):
    """Safe public code, without provider payloads, URLs or credentials."""


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,16384}", value):
        raise SocialAuthError("social_proof_invalid")
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _subject(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise SocialAuthError("social_proof_invalid")
    result = str(value)
    if not re.fullmatch(r"\d{1,128}", result, flags=re.ASCII) or int(result) <= 0:
        raise SocialAuthError("social_proof_invalid")
    return result


class SocialProvider:
    """Fixed HTTPS endpoints; no provider token is persisted or returned to Android."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._jwks: list[dict[str, Any]] = []
        self._keys_at = 0.0
        self._keys_lock = Lock()

    @staticmethod
    def _json(
        url: str, fields: dict[str, str] | None = None, *, authorization: str = "",
    ) -> dict[str, Any]:
        headers = {"Accept": "application/json", "User-Agent": APPLICATION_USER_AGENT}
        if authorization:
            headers["Authorization"] = authorization
        if fields is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        request = urllib.request.Request(
            url, data=urllib.parse.urlencode(fields).encode() if fields is not None else None,
            headers=headers,
        )
        try:
            opener = urllib.request.build_opener(NoRedirectHandler())
            with opener.open(request, timeout=10) as reply:
                if reply.status != 200:
                    raise SocialAuthError("social_provider_unavailable")
                raw = reply.read(_MAX_PROVIDER_BYTES + 1)
            if len(raw) > _MAX_PROVIDER_BYTES:
                raise SocialAuthError("social_proof_invalid")
            payload = json.loads(raw)
            if not isinstance(payload, dict) or "error" in payload:
                raise SocialAuthError("social_proof_invalid")
            return payload
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise SocialAuthError("social_provider_unavailable") from exc

    def url(self, provider: str, state: str, verifier: str, nonce: str) -> str:
        fields = {
            "client_id": self.settings.telegram_client_id if provider == "telegram"
            else self.settings.vkid_app_id,
            "redirect_uri": f"{CALLBACK_ROOT}/{provider}/callback",
            "response_type": "code", "state": state,
            "code_challenge": _b64(hashlib.sha256(verifier.encode("ascii")).digest()),
            "code_challenge_method": "S256",
        }
        if provider == "telegram":
            fields.update(scope="openid", nonce=nonce)
            endpoint = TELEGRAM_ISSUER + "/auth"
        else:
            # Profile email/phone are not requested and never used for account merging.
            fields.update(scope="", prompt="login")
            endpoint = VK_ORIGIN + "/authorize"
        return endpoint + "?" + urllib.parse.urlencode(fields)

    def exchange(
        self, provider: str, code: str, device_id: str, state: str, proof: dict[str, str],
    ) -> str:
        fields = {
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": f"{CALLBACK_ROOT}/{provider}/callback",
            "code_verifier": proof["verifier"],
        }
        if provider == "telegram":
            fields["client_id"] = self.settings.telegram_client_id
            credentials = (self.settings.telegram_client_id + ":" +
                           self.settings.telegram_client_secret).encode()
            token = self._json(TELEGRAM_ISSUER + "/token", fields,
                               authorization="Basic " + base64.b64encode(credentials).decode())
            return self._telegram_subject(token.get("id_token"), proof["nonce"])
        if not device_id:
            raise SocialAuthError("social_proof_invalid")
        fields.update(client_id=self.settings.vkid_app_id, device_id=device_id, state=state)
        token = self._json(VK_ORIGIN + "/oauth2/auth", fields)
        if (not isinstance(token.get("state"), str)
                or not hmac.compare_digest(token["state"], state)):
            raise SocialAuthError("social_proof_invalid")
        access = token.get("access_token")
        if not isinstance(access, str) or not 1 <= len(access) <= 16384:
            raise SocialAuthError("social_proof_invalid")
        user = self._json(VK_ORIGIN + "/oauth2/user_info", {
            "client_id": self.settings.vkid_app_id, "access_token": access,
        }).get("user")
        if not isinstance(user, dict):
            raise SocialAuthError("social_proof_invalid")
        subject = _subject(user.get("user_id"))
        if subject != _subject(token.get("user_id")):
            raise SocialAuthError("social_proof_invalid")
        return subject

    def _telegram_subject(self, token: Any, nonce: str) -> str:
        try:
            if not isinstance(token, str) or len(token) > 24000 or token.count(".") != 2:
                raise SocialAuthError("social_proof_invalid")
            encoded_header, encoded_payload, signature = token.split(".")
            header = json.loads(_decode(encoded_header))
            claims = json.loads(_decode(encoded_payload))
            if (not isinstance(header, dict) or not isinstance(claims, dict)
                    or header.get("alg") != "RS256" or "crit" in header
                    or not isinstance(header.get("kid"), str)):
                raise SocialAuthError("social_proof_invalid")
            key = self._telegram_key(header["kid"])
            key.verify(_decode(signature), (encoded_header + "." + encoded_payload).encode(),
                       padding.PKCS1v15(), hashes.SHA256())
            now = time.time()
            if (claims.get("iss") != TELEGRAM_ISSUER
                    or claims.get("aud") != self.settings.telegram_client_id
                    or type(claims.get("exp")) is not int or claims["exp"] <= now
                    or type(claims.get("iat")) is not int or claims["iat"] > now + 30
                    or claims["iat"] < now - FLOW_TTL_SECONDS - 30
                    or claims["iat"] >= claims["exp"]
                    or ("nbf" in claims and (type(claims["nbf"]) is not int
                                            or claims["nbf"] > now))
                    or not isinstance(claims.get("nonce"), str)
                    or not hmac.compare_digest(claims["nonce"], nonce)):
                raise SocialAuthError("social_proof_invalid")
            return _subject(claims.get("sub"))
        except (ValueError, TypeError, KeyError, InvalidSignature) as exc:
            raise SocialAuthError("social_proof_invalid") from exc

    def _telegram_key(self, kid: str) -> rsa.RSAPublicKey:
        with self._keys_lock:
            known = any(key.get("kid") == kid for key in self._jwks)
            age = time.monotonic() - self._keys_at
            if not self._jwks or age > 300 or (not known and age > 60):
                keys = self._json(TELEGRAM_ISSUER + "/.well-known/jwks.json").get("keys")
                if not isinstance(keys, list) or not 1 <= len(keys) <= 20:
                    raise SocialAuthError("social_proof_invalid")
                self._jwks = [key for key in keys if isinstance(key, dict)]
                self._keys_at = time.monotonic()
            matches = [key for key in self._jwks if key.get("kid") == kid
                       and key.get("kty") == "RSA" and key.get("alg", "RS256") == "RS256"
                       and key.get("use", "sig") == "sig"]
            if len(matches) != 1:
                raise SocialAuthError("social_proof_invalid")
            item = matches[0]
            modulus = int.from_bytes(_decode(item["n"]), "big")
            if not 2048 <= modulus.bit_length() <= 8192:
                raise SocialAuthError("social_proof_invalid")
            exponent = int.from_bytes(_decode(item["e"]), "big")
            return rsa.RSAPublicNumbers(exponent, modulus).public_key()


class SocialAuthService:
    def __init__(self, settings: Settings, database: Database) -> None:
        self.settings, self.database = settings, database
        self.store = SocialAuthStore(database)
        self.provider = SocialProvider(settings)
        self._slots = BoundedSemaphore(4)

    def _budget(self, scope: str, client_ip: str) -> None:
        if not self.database.consume_auth_budget([
            (auth_rate_digest(scope + ":ip", client_ip, self.settings.ip_key), 30, 300),
            (auth_rate_digest(scope + ":global", "all", self.settings.ip_key), 2000, 60),
        ]):
            raise SocialAuthError("social_rate_limited")

    def start(
        self, provider: str, *, purpose: str, android_package: str, client_ip: str,
        user: UserRecord | None, current_session: str | None,
    ) -> dict[str, Any]:
        if provider not in PROVIDERS or not self.settings.social_providers.get(provider):
            raise SocialAuthError("social_provider_not_configured")
        self._budget("social-start", client_ip)
        flow_id, flow_token = uuid4(), generate_session_token()
        state, verifier, nonce = (generate_session_token() for _ in range(3))
        self.store.create(
            flow_id=flow_id, provider=provider, purpose=purpose,
            flow_digest=session_digest(flow_token), state_digest=session_digest(state),
            secrets_ciphertext=encrypt_secret(json.dumps({"verifier": verifier, "nonce": nonce}),
                                              self.settings.broker_token_crypto_key),
            android_package=android_package, user_id=user.id if user else None,
            session_digest=session_digest(current_session) if current_session else None,
        )
        return {"flow_id": str(flow_id), "flow_token": flow_token,
                "authorization_url": self.provider.url(provider, state, verifier, nonce),
                "expires_in_seconds": FLOW_TTL_SECONDS}

    def callback(
        self, provider: str, *, state: str, code: str, device_id: str, denied: bool,
    ) -> tuple[str, bool]:
        if provider not in PROVIDERS or not self.settings.social_providers.get(provider):
            raise SocialAuthError("social_provider_not_configured")
        if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", state):
            raise SocialAuthError("social_proof_invalid")
        if not self._slots.acquire(blocking=False):
            raise SocialAuthError("social_rate_limited")
        try:
            return self._callback(provider, state, code, device_id, denied)
        finally:
            self._slots.release()

    def _callback(
        self, provider: str, state: str, code: str, device_id: str, denied: bool,
    ) -> tuple[str, bool]:
        row = self.store.claim(provider, session_digest(state))
        if row is None:
            raise SocialAuthError("social_flow_expired")
        subject = None
        try:
            if not denied and 1 <= len(code) <= 4096 and len(device_id) <= 4096:
                proof = json.loads(decrypt_secret(bytes(row["secrets_ciphertext"]),
                                                 self.settings.broker_token_crypto_key))
                subject = self.provider.exchange(provider, code, device_id, state, proof)
        except SocialAuthError:
            # Provider text and credentials must never reach the page, API or log.
            subject = None
        self.store.verified(row["id"], subject)
        return row["android_package"], subject is not None

    def complete(
        self, flow_id: UUID, flow_token: str, *, client_ip: str,
        legal_versions: dict[str, str], current_session: str | None,
    ) -> tuple[UserRecord, bool, str] | str:
        if not 32 <= len(flow_token) <= 256:
            raise SocialAuthError("social_flow_expired")
        self._budget("social-complete", client_ip)
        token = generate_session_token()
        result = self.store.finish(
            flow_id=flow_id, flow_digest=session_digest(flow_token),
            token_digest=session_digest(token),
            client_ip_hash=client_ip_digest(client_ip, self.settings.ip_key),
            session_ttl_seconds=self.settings.session_ttl_seconds, legal_versions=legal_versions,
            current_session_digest=session_digest(current_session) if current_session else None,
        )
        if isinstance(result, str):
            if result not in {"pending", "registration_required"}:
                raise SocialAuthError(result)
            return result
        user, created = result
        return user, created, token
