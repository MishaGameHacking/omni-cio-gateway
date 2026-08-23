from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import re
import secrets
from threading import RLock
from typing import Protocol
from urllib.parse import urlsplit

from omni_cio.web.identity_v1 import IdentityProviderV1, VerifiedExternalIdentityV1


_STATE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{32,512}$")


class ProviderAuthorizationError(RuntimeError):
    """Fail-closed external-provider authorization transaction error."""


@dataclass(frozen=True, slots=True)
class AuthorizationTransactionPolicyV1:
    lifetime: timedelta = timedelta(minutes=5)
    max_pending: int = 1024

    def __post_init__(self) -> None:
        if self.lifetime <= timedelta(0) or self.lifetime > timedelta(minutes=15):
            raise ValueError("AUTH_TRANSACTION_LIFETIME_INVALID")
        if self.max_pending < 1 or self.max_pending > 100_000:
            raise ValueError("AUTH_TRANSACTION_CAPACITY_INVALID")


@dataclass(frozen=True, slots=True)
class AuthorizationStartV1:
    provider: IdentityProviderV1
    state: str
    code_challenge: str
    nonce: str
    redirect_uri: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ConsumedAuthorizationTransactionV1:
    provider: IdentityProviderV1
    code_verifier: str
    nonce: str
    redirect_uri: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class _PendingAuthorizationTransactionV1:
    provider: IdentityProviderV1
    code_verifier: str
    nonce: str
    redirect_uri: str
    expires_at: datetime


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("AUTH_TRANSACTION_CLOCK_NOT_UTC_AWARE")
    return value.astimezone(timezone.utc)


def _https_redirect_uri(value: str) -> str:
    normalized = value.strip()
    try:
        parsed = urlsplit(normalized)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("AUTH_REDIRECT_URI_INVALID") from exc
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
        raise ValueError("AUTH_REDIRECT_URI_INVALID")
    return normalized


def _state_digest(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


class AuthorizationTransactionRegistryV1:
    """Bounded in-process OAuth/OIDC state + PKCE transaction registry.

    Raw state is returned once to the provider redirect but only its SHA-256
    digest is retained. The PKCE verifier and nonce stay server-side and are
    destroyed when the transaction is consumed or expires. Runtime restart
    invalidates in-flight login attempts, which fails closed and requires retry.
    """

    def __init__(self, policy: AuthorizationTransactionPolicyV1 | None = None) -> None:
        self._policy = policy or AuthorizationTransactionPolicyV1()
        self._pending: dict[str, _PendingAuthorizationTransactionV1] = {}
        self._lock = RLock()

    def begin(
        self,
        *,
        provider: IdentityProviderV1,
        redirect_uri: str,
        now: datetime,
    ) -> AuthorizationStartV1:
        timestamp = _utc(now)
        callback = _https_redirect_uri(redirect_uri)
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(48)
        nonce = secrets.token_urlsafe(32)
        digest = _state_digest(state)
        expires_at = timestamp + self._policy.lifetime
        pending = _PendingAuthorizationTransactionV1(
            provider=provider,
            code_verifier=verifier,
            nonce=nonce,
            redirect_uri=callback,
            expires_at=expires_at,
        )
        with self._lock:
            self._purge_expired(timestamp)
            if len(self._pending) >= self._policy.max_pending:
                raise ProviderAuthorizationError("AUTH_TRANSACTION_CAPACITY_EXCEEDED")
            self._pending[digest] = pending
        return AuthorizationStartV1(
            provider=provider,
            state=state,
            code_challenge=_pkce_challenge(verifier),
            nonce=nonce,
            redirect_uri=callback,
            expires_at=expires_at,
        )

    def consume(
        self,
        *,
        provider: IdentityProviderV1,
        state: str,
        now: datetime,
    ) -> ConsumedAuthorizationTransactionV1:
        timestamp = _utc(now)
        if _STATE_PATTERN.fullmatch(state) is None:
            raise ProviderAuthorizationError("AUTH_TRANSACTION_STATE_INVALID")
        digest = _state_digest(state)
        with self._lock:
            self._purge_expired(timestamp)
            pending = self._pending.get(digest)
            if pending is None:
                raise ProviderAuthorizationError("AUTH_TRANSACTION_NOT_FOUND")
            if pending.provider != provider:
                raise ProviderAuthorizationError("AUTH_TRANSACTION_PROVIDER_MISMATCH")
            self._pending.pop(digest, None)
        return ConsumedAuthorizationTransactionV1(
            provider=pending.provider,
            code_verifier=pending.code_verifier,
            nonce=pending.nonce,
            redirect_uri=pending.redirect_uri,
            expires_at=pending.expires_at,
        )

    def pending_count(self, *, now: datetime) -> int:
        timestamp = _utc(now)
        with self._lock:
            self._purge_expired(timestamp)
            return len(self._pending)

    def _purge_expired(self, now: datetime) -> None:
        for digest, pending in tuple(self._pending.items()):
            if now >= pending.expires_at:
                self._pending.pop(digest, None)


class ProviderAuthenticationRuntimeLike(Protocol):
    @property
    def provider(self) -> IdentityProviderV1: ...

    def start(self, *, now: datetime) -> str: ...

    def complete(
        self,
        *,
        state: str,
        code: str,
        now: datetime,
    ) -> VerifiedExternalIdentityV1: ...
