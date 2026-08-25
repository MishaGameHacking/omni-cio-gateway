from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import re
import secrets
from typing import Protocol

from omni_cio.persistence.migration import ConnectionLike
from omni_cio.web.identity_v1 import VerifiedExternalIdentityV1
from omni_cio.web.session_v1 import SessionScopeV1


_USER_ID_PATTERN = re.compile(r"^user:v1:[a-z0-9][a-z0-9_-]{2,63}$")
_TENANT_ID_PATTERN = re.compile(r"^tenant:v1:[a-z0-9][a-z0-9_-]{2,63}$")
_BINDING_KEY_MIN_BYTES = 32
_OWNER_USER_ID = "user:v1:owner"
_OWNER_TENANT_ID = "tenant:v1:owner"


class ProductIdentityError(RuntimeError):
    """Fail-closed product-account identity error."""


@dataclass(frozen=True, slots=True)
class ProductAccountScopeV1:
    user_id: str
    tenant_id: str

    def __post_init__(self) -> None:
        if _USER_ID_PATTERN.fullmatch(self.user_id) is None:
            raise ValueError("PRODUCT_USER_ID_INVALID")
        if _TENANT_ID_PATTERN.fullmatch(self.tenant_id) is None:
            raise ValueError("PRODUCT_TENANT_ID_INVALID")


def _require_product_scope(scope: ProductAccountScopeV1) -> ProductAccountScopeV1:
    if scope.user_id == _OWNER_USER_ID or scope.tenant_id == _OWNER_TENANT_ID:
        raise ProductIdentityError("OWNER_IDENTITY_RESERVED")
    return scope


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("PRODUCT_IDENTITY_CLOCK_NOT_UTC_AWARE")
    return value.astimezone(timezone.utc)


def _new_scope() -> ProductAccountScopeV1:
    suffix = secrets.token_hex(16)
    return ProductAccountScopeV1(
        user_id=f"user:v1:{suffix}",
        tenant_id=f"tenant:v1:{suffix}",
    )


def _record_sha256(payload: dict[str, object]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def protected_identity_binding_hmac_sha256(
    identity: VerifiedExternalIdentityV1,
    *,
    binding_key: bytes,
) -> str:
    """Derive an exact-lookup binding without persisting an enumerable raw subject hash."""

    if len(binding_key) < _BINDING_KEY_MIN_BYTES:
        raise ValueError("PRODUCT_IDENTITY_BINDING_KEY_TOO_SHORT")
    payload = f"{identity.provider.value}:{identity.subject}".encode("utf-8")
    return hmac.new(binding_key, payload, hashlib.sha256).hexdigest()


def _binding_lock_key(binding_digest: str) -> int:
    raw = bytes.fromhex(binding_digest[:16])
    return int.from_bytes(raw, byteorder="big", signed=True)


class ProductIdentityRepositoryLike(Protocol):
    def resolve_verified_identity(
        self,
        identity: VerifiedExternalIdentityV1,
    ) -> ProductAccountScopeV1 | None: ...

    def create_account(
        self,
        identity: VerifiedExternalIdentityV1,
        *,
        now: datetime,
    ) -> ProductAccountScopeV1: ...

    def link_identity(
        self,
        scope: ProductAccountScopeV1,
        identity: VerifiedExternalIdentityV1,
        *,
        now: datetime,
    ) -> None: ...


class SessionIssuerLike(Protocol):
    def create(
        self,
        *,
        user_id: str,
        tenant_id: str,
        now: datetime,
    ) -> tuple[str, SessionScopeV1]: ...

    def revoke(self, token: str | None, *, now: datetime) -> bool: ...


class PostgresProductIdentityRepositoryV1:
    """Durable verified external-identity -> internal account/tenant binding.

    The provider subject exists in process memory only long enough to derive a
    keyed HMAC binding. PostgreSQL receives no raw Telegram/VK subject and no
    unkeyed subject fingerprint. Browser-controlled user/tenant selectors are
    never accepted by this repository.
    """

    def __init__(
        self,
        connection: ConnectionLike,
        *,
        binding_key: bytes,
        scope_factory: Callable[[], ProductAccountScopeV1] = _new_scope,
    ) -> None:
        if len(binding_key) < _BINDING_KEY_MIN_BYTES:
            raise ValueError("PRODUCT_IDENTITY_BINDING_KEY_TOO_SHORT")
        self._connection = connection
        self._binding_key = bytes(binding_key)
        self._scope_factory = scope_factory

    def _binding_digest(self, identity: VerifiedExternalIdentityV1) -> str:
        return protected_identity_binding_hmac_sha256(
            identity,
            binding_key=self._binding_key,
        )

    def _resolve_digest(
        self,
        *,
        provider: str,
        binding_digest: str,
    ) -> ProductAccountScopeV1 | None:
        row = self._connection.execute(
            "SELECT user_id, tenant_id "
            "FROM omni_cio_v10.external_identity_bindings "
            "WHERE provider = %s AND subject_binding_hmac_sha256 = %s",
            (provider, binding_digest),
        ).fetchone()
        if row is None:
            return None
        return _require_product_scope(
            ProductAccountScopeV1(user_id=str(row[0]), tenant_id=str(row[1]))
        )

    def resolve_verified_identity(
        self,
        identity: VerifiedExternalIdentityV1,
    ) -> ProductAccountScopeV1 | None:
        return self._resolve_digest(
            provider=identity.provider.value,
            binding_digest=self._binding_digest(identity),
        )

    def create_account(
        self,
        identity: VerifiedExternalIdentityV1,
        *,
        now: datetime,
    ) -> ProductAccountScopeV1:
        timestamp = _utc(now)
        binding_digest = self._binding_digest(identity)
        with self._connection.transaction():
            self._connection.execute(
                "SELECT pg_advisory_xact_lock(%s)",
                (_binding_lock_key(binding_digest),),
            )
            existing = self._resolve_digest(
                provider=identity.provider.value,
                binding_digest=binding_digest,
            )
            if existing is not None:
                return existing

            scope = _require_product_scope(self._scope_factory())

            tenant_payload: dict[str, object] = {
                "schema_version": "1.0",
                "identity_version": 1,
                "tenant_id": scope.tenant_id,
                "mode": "product_user",
                "created_at": timestamp.isoformat(),
            }
            user_payload: dict[str, object] = {
                "schema_version": "1.0",
                "identity_version": 1,
                "user_id": scope.user_id,
                "tenant_id": scope.tenant_id,
                "role": "user",
                "created_at": timestamp.isoformat(),
            }
            self._connection.execute(
                "INSERT INTO omni_cio_v10.tenants "
                "(tenant_id, schema_version, identity_version, mode, created_at, "
                "record_sha256) VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    scope.tenant_id,
                    "1.0",
                    1,
                    "product_user",
                    timestamp,
                    _record_sha256(tenant_payload),
                ),
            )
            self._connection.execute(
                "INSERT INTO omni_cio_v10.users "
                "(user_id, tenant_id, schema_version, identity_version, role, "
                "created_at, record_sha256) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    scope.user_id,
                    scope.tenant_id,
                    "1.0",
                    1,
                    "user",
                    timestamp,
                    _record_sha256(user_payload),
                ),
            )
            self._insert_binding(
                scope,
                identity,
                binding_digest=binding_digest,
                timestamp=timestamp,
            )
            return scope

    def link_identity(
        self,
        scope: ProductAccountScopeV1,
        identity: VerifiedExternalIdentityV1,
        *,
        now: datetime,
    ) -> None:
        scope = _require_product_scope(scope)
        timestamp = _utc(now)
        binding_digest = self._binding_digest(identity)
        with self._connection.transaction():
            self._connection.execute(
                "SELECT pg_advisory_xact_lock(%s)",
                (_binding_lock_key(binding_digest),),
            )
            existing = self._resolve_digest(
                provider=identity.provider.value,
                binding_digest=binding_digest,
            )
            if existing is not None:
                if existing != scope:
                    raise ProductIdentityError("IDENTITY_ALREADY_BOUND")
                return

            account = self._connection.execute(
                "SELECT 1 FROM omni_cio_v10.users "
                "WHERE user_id = %s AND tenant_id = %s",
                (scope.user_id, scope.tenant_id),
            ).fetchone()
            if account is None:
                raise ProductIdentityError("AUTHENTICATED_ACCOUNT_NOT_FOUND")

            provider_row = self._connection.execute(
                "SELECT subject_binding_hmac_sha256 "
                "FROM omni_cio_v10.external_identity_bindings "
                "WHERE user_id = %s AND provider = %s",
                (scope.user_id, identity.provider.value),
            ).fetchone()
            if provider_row is not None:
                raise ProductIdentityError("PROVIDER_ALREADY_LINKED")

            self._insert_binding(
                scope,
                identity,
                binding_digest=binding_digest,
                timestamp=timestamp,
            )

    def _insert_binding(
        self,
        scope: ProductAccountScopeV1,
        identity: VerifiedExternalIdentityV1,
        *,
        binding_digest: str,
        timestamp: datetime,
    ) -> None:
        scope = _require_product_scope(scope)
        self._connection.execute(
            "INSERT INTO omni_cio_v10.external_identity_bindings "
            "(provider, subject_binding_hmac_sha256, user_id, tenant_id, linked_at, "
            "last_verified_at) VALUES (%s, %s, %s, %s, %s, %s)",
            (
                identity.provider.value,
                binding_digest,
                scope.user_id,
                scope.tenant_id,
                timestamp,
                timestamp,
            ),
        )


class ProductIdentityServiceV1:
    """Verified-provider to internal-account boundary; registration is off by default."""

    def __init__(
        self,
        repository: ProductIdentityRepositoryLike,
        *,
        registration_enabled: bool = False,
    ) -> None:
        self._repository = repository
        self._registration_enabled = registration_enabled

    @property
    def registration_enabled(self) -> bool:
        return self._registration_enabled

    def authenticate(
        self,
        identity: VerifiedExternalIdentityV1,
        *,
        now: datetime,
    ) -> ProductAccountScopeV1:
        existing = self._repository.resolve_verified_identity(identity)
        if existing is not None:
            return _require_product_scope(existing)
        if not self._registration_enabled:
            raise ProductIdentityError("PUBLIC_REGISTRATION_DISABLED")
        return _require_product_scope(
            self._repository.create_account(identity, now=now)
        )

    def link_authenticated_identity(
        self,
        scope: ProductAccountScopeV1,
        identity: VerifiedExternalIdentityV1,
        *,
        now: datetime,
    ) -> None:
        self._repository.link_identity(
            _require_product_scope(scope),
            identity,
            now=now,
        )


class ProductAuthenticationServiceV1:
    """Bind provider identity to product scope and issue fresh server-side sessions."""

    def __init__(
        self,
        *,
        identities: ProductIdentityServiceV1,
        sessions: SessionIssuerLike,
    ) -> None:
        self._identities = identities
        self._sessions = sessions

    def resolve_verified_identity(
        self,
        identity: VerifiedExternalIdentityV1,
        *,
        now: datetime,
    ) -> ProductAccountScopeV1:
        """Resolve provider identity without accepting browser session material."""

        timestamp = _utc(now)
        return _require_product_scope(
            self._identities.authenticate(identity, now=timestamp)
        )

    def revoke_session(self, token: str | None, *, now: datetime) -> bool:
        """Consume an untrusted current-session candidate without producing a token."""

        return self._sessions.revoke(token, now=_utc(now))

    def issue_session(
        self,
        account_scope: ProductAccountScopeV1,
        *,
        now: datetime,
    ) -> tuple[str, SessionScopeV1]:
        """Mint a fresh session from server-resolved product scope only."""

        timestamp = _utc(now)
        account_scope = _require_product_scope(account_scope)
        token, session_scope = self._sessions.create(
            user_id=account_scope.user_id,
            tenant_id=account_scope.tenant_id,
            now=timestamp,
        )
        if (
            session_scope.user_id != account_scope.user_id
            or session_scope.tenant_id != account_scope.tenant_id
        ):
            self._sessions.revoke(token, now=timestamp)
            raise ProductIdentityError("SESSION_SCOPE_MISMATCH")
        return token, session_scope

    def authenticate_verified_identity(
        self,
        identity: VerifiedExternalIdentityV1,
        *,
        current_session_token: str | None,
        now: datetime,
    ) -> tuple[str, SessionScopeV1]:
        """Compatibility wrapper preserving fixation-safe resolve/revoke/issue order."""

        timestamp = _utc(now)
        account_scope = self.resolve_verified_identity(identity, now=timestamp)
        self.revoke_session(current_session_token, now=timestamp)
        return self.issue_session(account_scope, now=timestamp)

    def link_verified_identity(
        self,
        authenticated_scope: SessionScopeV1,
        identity: VerifiedExternalIdentityV1,
        *,
        now: datetime,
    ) -> None:
        self._identities.link_authenticated_identity(
            ProductAccountScopeV1(
                user_id=authenticated_scope.user_id,
                tenant_id=authenticated_scope.tenant_id,
            ),
            identity,
            now=_utc(now),
        )
