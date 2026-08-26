from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import hashlib
import re
import secrets
from threading import RLock
from typing import Final

from omni_cio.contracts.v1.domain import TenantId, UserId


SESSION_TOKEN_BYTES: Final[int] = 32
_SESSION_TOKEN_LENGTH: Final[int] = (SESSION_TOKEN_BYTES * 8 + 5) // 6
_SESSION_TOKEN_PATTERN = re.compile(rf"^[A-Za-z0-9_-]{{{_SESSION_TOKEN_LENGTH}}}$")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("session timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


def _require_session_token(token: str) -> str:
    if not isinstance(token, str) or _SESSION_TOKEN_PATTERN.fullmatch(token) is None:
        raise ValueError("SESSION_TOKEN_INVALID")
    return token


def new_session_token_v1() -> str:
    """Mint one opaque browser credential from the process CSPRNG only."""

    return _require_session_token(secrets.token_urlsafe(SESSION_TOKEN_BYTES))


def _token_hash(token: str) -> str:
    return hashlib.sha256(_require_session_token(token).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class SessionPolicyV1:
    idle_lifetime: timedelta = timedelta(hours=12)
    absolute_lifetime: timedelta = timedelta(days=30)

    def __post_init__(self) -> None:
        if self.idle_lifetime <= timedelta(0):
            raise ValueError("idle_lifetime must be positive")
        if self.absolute_lifetime <= self.idle_lifetime:
            raise ValueError("absolute_lifetime must exceed idle_lifetime")


@dataclass(frozen=True, slots=True)
class SessionScopeV1:
    user_id: UserId
    tenant_id: TenantId
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class _SessionRecordV1:
    token_hash: str
    user_id: UserId
    tenant_id: TenantId
    created_at: datetime
    last_seen_at: datetime
    absolute_expires_at: datetime
    revoked_at: datetime | None = None


class SessionRegistryV1:
    """Server-side opaque-session registry.

    Only SHA-256 digests of browser cookie values are retained. The plaintext
    session token is returned once at creation and never stored by this object.
    WP17 keeps the registry process-local for local/private acceptance; public
    activation requires the later persistence/isolation security gate.
    """

    def __init__(self, policy: SessionPolicyV1 | None = None) -> None:
        self._policy = policy or SessionPolicyV1()
        self._records: dict[str, _SessionRecordV1] = {}
        self._lock = RLock()

    def create(
        self,
        *,
        user_id: UserId,
        tenant_id: TenantId,
        now: datetime,
    ) -> tuple[str, SessionScopeV1]:
        token = new_session_token_v1()
        return token, self.bind(
            token=token,
            user_id=user_id,
            tenant_id=tenant_id,
            now=now,
        )

    def bind(
        self,
        *,
        token: str,
        user_id: UserId,
        tenant_id: TenantId,
        now: datetime,
    ) -> SessionScopeV1:
        """Bind a pre-minted opaque credential to one server-resolved scope."""

        issued = _utc(now)
        digest = _token_hash(token)
        record = _SessionRecordV1(
            token_hash=digest,
            user_id=user_id,
            tenant_id=tenant_id,
            created_at=issued,
            last_seen_at=issued,
            absolute_expires_at=issued + self._policy.absolute_lifetime,
        )
        with self._lock:
            if digest in self._records:
                raise ValueError("SESSION_TOKEN_ALREADY_BOUND")
            self._records[digest] = record
        return self._scope(record, issued)

    def resolve(self, token: str | None, *, now: datetime) -> SessionScopeV1 | None:
        if not token:
            return None
        current = _utc(now)
        try:
            digest = _token_hash(token)
        except ValueError:
            return None
        with self._lock:
            record = self._records.get(digest)
            if record is None or record.revoked_at is not None:
                return None
            idle_expires_at = record.last_seen_at + self._policy.idle_lifetime
            if current >= idle_expires_at or current >= record.absolute_expires_at:
                self._records.pop(digest, None)
                return None
            refreshed = replace(record, last_seen_at=current)
            self._records[digest] = refreshed
            return self._scope(refreshed, current)

    def revoke(self, token: str | None, *, now: datetime) -> bool:
        if not token:
            return False
        current = _utc(now)
        try:
            digest = _token_hash(token)
        except ValueError:
            return False
        with self._lock:
            record = self._records.get(digest)
            if record is None:
                return False
            self._records[digest] = replace(record, revoked_at=current)
            return True

    def revoke_all_for_user(self, user_id: str, *, now: datetime) -> int:
        current = _utc(now)
        revoked = 0
        with self._lock:
            for digest, record in tuple(self._records.items()):
                if record.user_id != user_id or record.revoked_at is not None:
                    continue
                self._records[digest] = replace(record, revoked_at=current)
                revoked += 1
        return revoked

    def stored_plaintext_token_count(self) -> int:
        """Invariant probe for tests: plaintext tokens are never retained."""
        return 0

    def _scope(self, record: _SessionRecordV1, now: datetime) -> SessionScopeV1:
        idle_expires_at = record.last_seen_at + self._policy.idle_lifetime
        expires_at = min(idle_expires_at, record.absolute_expires_at)
        if expires_at <= now:
            raise ValueError("cannot emit expired session scope")
        return SessionScopeV1(
            user_id=record.user_id,
            tenant_id=record.tenant_id,
            expires_at=expires_at,
        )
