from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import re
import secrets
from threading import RLock
from typing import TYPE_CHECKING, Protocol
from urllib.parse import urlsplit

from omni_cio.web.identity_v1 import IdentityProviderV1, VerifiedExternalIdentityV1

if TYPE_CHECKING:
    from omni_cio.persistence.migration import ConnectionLike


_OPAQUE_32_512_PATTERN = re.compile(r"^[A-Za-z0-9_-]{32,512}$")
_STATE_PATTERN = _OPAQUE_32_512_PATTERN
_BROWSER_PROOF_PATTERN = _OPAQUE_32_512_PATTERN
_PKCE_VERIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43,128}$")
_NONCE_PATTERN = _OPAQUE_32_512_PATTERN
_MAX_PENDING_AUTH_TRANSACTIONS = 4096
_AUTH_TRANSACTION_CAPACITY_LOCK_KEY = 220205


class ProviderAuthorizationError(RuntimeError):
    """Fail-closed external-provider authorization transaction error."""


@dataclass(frozen=True, slots=True)
class AuthorizationTransactionPolicyV1:
    lifetime: timedelta = timedelta(minutes=5)
    max_pending: int = 1024

    def __post_init__(self) -> None:
        if self.lifetime <= timedelta(0) or self.lifetime > timedelta(minutes=15):
            raise ValueError("AUTH_TRANSACTION_LIFETIME_INVALID")
        if self.max_pending < 1 or self.max_pending > _MAX_PENDING_AUTH_TRANSACTIONS:
            raise ValueError("AUTH_TRANSACTION_CAPACITY_INVALID")


@dataclass(frozen=True, slots=True)
class AuthorizationStartV1:
    provider: IdentityProviderV1
    state: str
    code_challenge: str
    nonce: str
    redirect_uri: str
    expires_at: datetime
    browser_proof: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class ProviderAuthorizationStartV1:
    authorization_url: str
    browser_proof: str = field(repr=False)
    expires_at: datetime
    authorization_query: str | None = None


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
    browser_proof_sha256: str


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("AUTH_TRANSACTION_CLOCK_NOT_UTC_AWARE")
    return value.astimezone(timezone.utc)


def _https_redirect_uri(value: str) -> str:
    if not isinstance(value, str) or value != value.strip():
        raise ValueError("AUTH_REDIRECT_URI_INVALID")
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


def _browser_proof_digest(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def _validated_browser_proof(value: str) -> str:
    if not isinstance(value, str) or _BROWSER_PROOF_PATTERN.fullmatch(value) is None:
        raise ProviderAuthorizationError("AUTH_TRANSACTION_BROWSER_PROOF_INVALID")
    return value


def new_authorization_browser_proof_v1() -> str:
    """Mint one browser-bound provider proof from the process CSPRNG only."""

    return _validated_browser_proof(secrets.token_urlsafe(32))


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


class AuthorizationTransactionRegistryV1:
    """Bounded browser-bound in-process OAuth/OIDC transaction test fixture.

    Raw state is returned once to the provider redirect but only its SHA-256
    digest is retained. A separate initiating-browser proof is returned only to
    the caller and retained solely as a digest. The PKCE verifier and nonce stay
    server-side and are destroyed when the transaction is consumed or expires.

    Deployed multi-instance runtimes use PostgresAuthorizationTransactionStoreV1.
    This implementation remains injectable for deterministic unit tests and
    local composition, while enforcing the same browser-binding contract.
    """

    def __init__(self, policy: AuthorizationTransactionPolicyV1 | None = None) -> None:
        self._policy = policy or AuthorizationTransactionPolicyV1()
        self._pending: dict[str, _PendingAuthorizationTransactionV1] = {}
        self._next_expiry_at: datetime | None = None
        self._lock = RLock()

    def begin(
        self,
        *,
        provider: IdentityProviderV1,
        redirect_uri: str,
        now: datetime,
        browser_proof: str | None = None,
    ) -> AuthorizationStartV1:
        timestamp = _utc(now)
        callback = _https_redirect_uri(redirect_uri)
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(48)
        nonce = secrets.token_urlsafe(32)
        proof = (
            new_authorization_browser_proof_v1()
            if browser_proof is None
            else _validated_browser_proof(browser_proof)
        )
        digest = _state_digest(state)
        expires_at = timestamp + self._policy.lifetime
        pending = _PendingAuthorizationTransactionV1(
            provider=provider,
            code_verifier=verifier,
            nonce=nonce,
            redirect_uri=callback,
            expires_at=expires_at,
            browser_proof_sha256=_browser_proof_digest(proof),
        )
        with self._lock:
            self._purge_expired(timestamp)
            if len(self._pending) >= self._policy.max_pending:
                raise ProviderAuthorizationError("AUTH_TRANSACTION_CAPACITY_EXCEEDED")
            self._pending[digest] = pending
            if self._next_expiry_at is None or expires_at < self._next_expiry_at:
                self._next_expiry_at = expires_at
        return AuthorizationStartV1(
            provider=provider,
            state=state,
            code_challenge=_pkce_challenge(verifier),
            nonce=nonce,
            redirect_uri=callback,
            expires_at=expires_at,
            browser_proof=proof,
        )

    def consume(
        self,
        *,
        provider: IdentityProviderV1,
        state: str,
        browser_proof: str,
        now: datetime,
    ) -> ConsumedAuthorizationTransactionV1:
        timestamp = _utc(now)
        if not isinstance(state, str) or _STATE_PATTERN.fullmatch(state) is None:
            raise ProviderAuthorizationError("AUTH_TRANSACTION_STATE_INVALID")
        proof = _validated_browser_proof(browser_proof)
        digest = _state_digest(state)
        browser_proof_sha256 = _browser_proof_digest(proof)
        with self._lock:
            self._purge_expired(timestamp)
            pending = self._pending.get(digest)
            if pending is None:
                raise ProviderAuthorizationError("AUTH_TRANSACTION_NOT_FOUND")
            if pending.provider != provider:
                raise ProviderAuthorizationError("AUTH_TRANSACTION_PROVIDER_MISMATCH")
            if not hmac.compare_digest(
                pending.browser_proof_sha256,
                browser_proof_sha256,
            ):
                # Keep the valid transaction available to the initiating browser
                # and avoid revealing whether an attacker guessed a live state.
                raise ProviderAuthorizationError("AUTH_TRANSACTION_NOT_FOUND")
            self._pending.pop(digest, None)
            if not self._pending:
                self._next_expiry_at = None
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
        next_expiry = self._next_expiry_at
        if next_expiry is None or now < next_expiry:
            return
        next_expiry = None
        for digest, pending in tuple(self._pending.items()):
            if now >= pending.expires_at:
                self._pending.pop(digest, None)
            elif next_expiry is None or pending.expires_at < next_expiry:
                next_expiry = pending.expires_at
        self._next_expiry_at = next_expiry


class AuthorizationTransactionStoreLike(Protocol):
    def begin(
        self,
        *,
        provider: IdentityProviderV1,
        redirect_uri: str,
        now: datetime,
        browser_proof: str | None = None,
    ) -> AuthorizationStartV1: ...

    def consume(
        self,
        *,
        provider: IdentityProviderV1,
        state: str,
        browser_proof: str,
        now: datetime,
    ) -> ConsumedAuthorizationTransactionV1: ...


class PostgresAuthorizationTransactionStoreV1:
    """Durable, bounded, browser-bound OAuth/OIDC transaction authority.

    Only digests of provider state and the initiating-browser proof are stored.
    PostgreSQL performs the one-time claim with DELETE ... RETURNING, so exactly
    one callback can obtain the verifier/nonce even across multiple processes.
    """

    def __init__(
        self,
        connection: ConnectionLike,
        policy: AuthorizationTransactionPolicyV1 | None = None,
    ) -> None:
        self._connection = connection
        self._policy = policy or AuthorizationTransactionPolicyV1()

    def begin(
        self,
        *,
        provider: IdentityProviderV1,
        redirect_uri: str,
        now: datetime,
        browser_proof: str | None = None,
    ) -> AuthorizationStartV1:
        timestamp = _utc(now)
        callback = _https_redirect_uri(redirect_uri)
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(48)
        nonce = secrets.token_urlsafe(32)
        proof = (
            new_authorization_browser_proof_v1()
            if browser_proof is None
            else _validated_browser_proof(browser_proof)
        )
        expires_at = timestamp + self._policy.lifetime

        with self._connection.transaction():
            # Serialize cleanup/capacity/insert across every hosted process.
            self._connection.execute(
                "SELECT pg_advisory_xact_lock(%s)",
                (_AUTH_TRANSACTION_CAPACITY_LOCK_KEY,),
            )
            self._connection.execute(
                "DELETE FROM omni_cio_v10.provider_auth_transactions "
                "WHERE expires_at <= %s",
                (timestamp,),
            )
            row = self._connection.execute(
                "SELECT count(*) FROM omni_cio_v10.provider_auth_transactions"
            ).fetchone()
            if (
                row is None
                or len(row) != 1
                or not isinstance(row[0], int)
                or isinstance(row[0], bool)
            ):
                raise ProviderAuthorizationError("AUTH_TRANSACTION_STORE_INVALID")
            if int(row[0]) >= self._policy.max_pending:
                raise ProviderAuthorizationError("AUTH_TRANSACTION_CAPACITY_EXCEEDED")
            self._connection.execute(
                "INSERT INTO omni_cio_v10.provider_auth_transactions "
                "(state_sha256, browser_proof_sha256, provider, code_verifier, "
                "nonce, redirect_uri, created_at, expires_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    _state_digest(state),
                    _browser_proof_digest(proof),
                    provider.value,
                    verifier,
                    nonce,
                    callback,
                    timestamp,
                    expires_at,
                ),
            )

        return AuthorizationStartV1(
            provider=provider,
            state=state,
            code_challenge=_pkce_challenge(verifier),
            nonce=nonce,
            redirect_uri=callback,
            expires_at=expires_at,
            browser_proof=proof,
        )

    def consume(
        self,
        *,
        provider: IdentityProviderV1,
        state: str,
        browser_proof: str,
        now: datetime,
    ) -> ConsumedAuthorizationTransactionV1:
        timestamp = _utc(now)
        if not isinstance(state, str) or _STATE_PATTERN.fullmatch(state) is None:
            raise ProviderAuthorizationError("AUTH_TRANSACTION_STATE_INVALID")
        proof = _validated_browser_proof(browser_proof)

        state_sha256 = _state_digest(state)
        with self._connection.transaction():
            row = self._connection.execute(
                "DELETE FROM omni_cio_v10.provider_auth_transactions "
                "WHERE state_sha256 = %s AND browser_proof_sha256 = %s "
                "AND provider = %s AND expires_at > %s "
                "RETURNING provider, code_verifier, nonce, redirect_uri, expires_at",
                (
                    state_sha256,
                    _browser_proof_digest(proof),
                    provider.value,
                    timestamp,
                ),
            ).fetchone()
            if row is None:
                # Remove only an expired row. A wrong browser proof or provider
                # cannot destroy the initiating browser's valid transaction.
                self._connection.execute(
                    "DELETE FROM omni_cio_v10.provider_auth_transactions "
                    "WHERE state_sha256 = %s AND expires_at <= %s",
                    (state_sha256, timestamp),
                )
                raise ProviderAuthorizationError("AUTH_TRANSACTION_NOT_FOUND")

        try:
            if len(row) != 5:
                raise ValueError
            stored_provider = IdentityProviderV1(row[0])
            code_verifier = row[1]
            nonce = row[2]
            redirect_uri = row[3]
            expires_at = _utc(row[4])
            if (
                not isinstance(code_verifier, str)
                or _PKCE_VERIFIER_PATTERN.fullmatch(code_verifier) is None
                or not isinstance(nonce, str)
                or _NONCE_PATTERN.fullmatch(nonce) is None
                or not isinstance(redirect_uri, str)
                or _https_redirect_uri(redirect_uri) != redirect_uri
                or expires_at <= timestamp
            ):
                raise ValueError
        except (TypeError, ValueError, IndexError):
            raise ProviderAuthorizationError("AUTH_TRANSACTION_STORE_INVALID") from None
        if stored_provider != provider:
            raise ProviderAuthorizationError("AUTH_TRANSACTION_STORE_INVALID")
        return ConsumedAuthorizationTransactionV1(
            provider=stored_provider,
            code_verifier=code_verifier,
            nonce=nonce,
            redirect_uri=redirect_uri,
            expires_at=expires_at,
        )

    def pending_count(self, *, now: datetime) -> int:
        timestamp = _utc(now)
        with self._connection.transaction():
            self._connection.execute(
                "SELECT pg_advisory_xact_lock(%s)",
                (_AUTH_TRANSACTION_CAPACITY_LOCK_KEY,),
            )
            self._connection.execute(
                "DELETE FROM omni_cio_v10.provider_auth_transactions "
                "WHERE expires_at <= %s",
                (timestamp,),
            )
            row = self._connection.execute(
                "SELECT count(*) FROM omni_cio_v10.provider_auth_transactions"
            ).fetchone()
        if (
            row is None
            or len(row) != 1
            or not isinstance(row[0], int)
            or isinstance(row[0], bool)
        ):
            raise ProviderAuthorizationError("AUTH_TRANSACTION_STORE_INVALID")
        return int(row[0])


class ProviderAuthenticationRuntimeLike(Protocol):
    @property
    def provider(self) -> IdentityProviderV1: ...

    def start(
        self,
        *,
        now: datetime,
        browser_proof: str | None = None,
    ) -> ProviderAuthorizationStartV1: ...

    def complete(
        self,
        *,
        state: str,
        code: str,
        browser_proof: str,
        now: datetime,
        device_id: str | None = None,
    ) -> VerifiedExternalIdentityV1: ...
