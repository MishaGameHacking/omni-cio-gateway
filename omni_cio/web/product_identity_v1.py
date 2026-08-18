from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import secrets
from typing import Final

from omni_cio.persistence.migration import ConnectionLike
from omni_cio.web.identity_v1 import VerifiedExternalIdentityV1


_IDENTITY_BINDING_DOMAIN: Final[bytes] = b"omni-cio:v10:external-identity:v1"
_MIN_BINDING_KEY_BYTES: Final[int] = 32


class ProductIdentityError(RuntimeError):
    """Fail-closed product identity/account resolution error."""


@dataclass(frozen=True, slots=True)
class ProductAccountScopeV1:
    user_id: str
    tenant_id: str


@dataclass(frozen=True, slots=True)
class IdentityBindingKeyV1:
    version: int
    key: bytes

    def __post_init__(self) -> None:
        if self.version <= 0:
            raise ValueError("identity binding key version must be positive")
        if len(self.key) < _MIN_BINDING_KEY_BYTES:
            raise ValueError("identity binding key must contain at least 32 bytes")

    def digest(self, identity: VerifiedExternalIdentityV1) -> str:
        payload = b"\x00".join(
            (
                _IDENTITY_BINDING_DOMAIN,
                identity.provider.value.encode("utf-8"),
                identity.subject.encode("utf-8"),
            )
        )
        return hmac.new(self.key, payload, hashlib.sha256).hexdigest()


@dataclass(frozen=True, slots=True)
class IdentityBindingKeyringV1:
    active: IdentityBindingKeyV1
    previous: tuple[IdentityBindingKeyV1, ...] = ()

    def __post_init__(self) -> None:
        versions = [self.active.version, *(item.version for item in self.previous)]
        if len(versions) != len(set(versions)):
            raise ValueError("identity binding key versions must be unique")

    @property
    def keys(self) -> tuple[IdentityBindingKeyV1, ...]:
        return (self.active, *self.previous)


class PostgresProductIdentityRepositoryV1:
    """Map verified external identities to internal Omni-CIO account scope.

    Raw Telegram/VK subjects are never written to PostgreSQL. Persistent lookup
    uses a runtime-keyed HMAC digest with an explicit key version so a leaked
    database cannot cheaply enumerate low-entropy provider subject identifiers.
    """

    def __init__(
        self,
        connection: ConnectionLike,
        *,
        keyring: IdentityBindingKeyringV1,
        registration_enabled: bool = False,
    ) -> None:
        self._connection = connection
        self._keyring = keyring
        self._registration_enabled = registration_enabled

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("identity timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    def resolve_verified(
        self,
        identity: VerifiedExternalIdentityV1,
        *,
        now: datetime,
    ) -> ProductAccountScopeV1 | None:
        verified_at = self._utc(now)
        for binding_key in self._keyring.keys:
            digest = binding_key.digest(identity)
            row = self._connection.execute(
                "SELECT user_id, tenant_id "
                "FROM omni_cio_v10.external_identity_bindings "
                "WHERE provider = %s AND subject_binding_sha256 = %s "
                "AND binding_key_version = %s",
                (identity.provider.value, digest, binding_key.version),
            ).fetchone()
            if row is None:
                continue
            scope = ProductAccountScopeV1(user_id=str(row[0]), tenant_id=str(row[1]))
            with self._connection.transaction():
                self._connection.execute(
                    "UPDATE omni_cio_v10.external_identity_bindings "
                    "SET last_verified_at = GREATEST(last_verified_at, %s) "
                    "WHERE provider = %s AND subject_binding_sha256 = %s",
                    (verified_at, identity.provider.value, digest),
                )
            return scope
        return None

    def resolve_or_register(
        self,
        identity: VerifiedExternalIdentityV1,
        *,
        now: datetime,
    ) -> ProductAccountScopeV1:
        existing = self.resolve_verified(identity, now=now)
        if existing is not None:
            return existing
        if not self._registration_enabled:
            raise ProductIdentityError("PRODUCT_REGISTRATION_DISABLED")
        return self._register_verified(identity, now=now)

    def link_verified(
        self,
        scope: ProductAccountScopeV1,
        identity: VerifiedExternalIdentityV1,
        *,
        now: datetime,
    ) -> None:
        linked_at = self._utc(now)
        digest = self._keyring.active.digest(identity)
        with self._connection.transaction():
            account = self._connection.execute(
                "SELECT 1 FROM omni_cio_v10.users "
                "WHERE user_id = %s AND tenant_id = %s",
                (scope.user_id, scope.tenant_id),
            ).fetchone()
            if account is None:
                raise ProductIdentityError("PRODUCT_ACCOUNT_SCOPE_UNKNOWN")

            existing_identity = self._connection.execute(
                "SELECT user_id, tenant_id FROM omni_cio_v10.external_identity_bindings "
                "WHERE provider = %s AND subject_binding_sha256 = %s",
                (identity.provider.value, digest),
            ).fetchone()
            if existing_identity is not None:
                if (str(existing_identity[0]), str(existing_identity[1])) != (
                    scope.user_id,
                    scope.tenant_id,
                ):
                    raise ProductIdentityError("EXTERNAL_IDENTITY_ALREADY_BOUND")
                self._connection.execute(
                    "UPDATE omni_cio_v10.external_identity_bindings "
                    "SET last_verified_at = GREATEST(last_verified_at, %s) "
                    "WHERE provider = %s AND subject_binding_sha256 = %s",
                    (linked_at, identity.provider.value, digest),
                )
                return

            provider_for_user = self._connection.execute(
                "SELECT subject_binding_sha256 FROM omni_cio_v10.external_identity_bindings "
                "WHERE user_id = %s AND provider = %s",
                (scope.user_id, identity.provider.value),
            ).fetchone()
            if provider_for_user is not None:
                raise ProductIdentityError("ACCOUNT_PROVIDER_ALREADY_BOUND")

            self._connection.execute(
                "INSERT INTO omni_cio_v10.external_identity_bindings "
                "(provider, subject_binding_sha256, binding_key_version, user_id, "
                "tenant_id, linked_at, last_verified_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    identity.provider.value,
                    digest,
                    self._keyring.active.version,
                    scope.user_id,
                    scope.tenant_id,
                    linked_at,
                    linked_at,
                ),
            )

    def _register_verified(
        self,
        identity: VerifiedExternalIdentityV1,
        *,
        now: datetime,
    ) -> ProductAccountScopeV1:
        created_at = self._utc(now)
        user_id = f"user:v1:{secrets.token_hex(16)}"
        tenant_id = f"tenant:v1:{secrets.token_hex(16)}"
        scope = ProductAccountScopeV1(user_id=user_id, tenant_id=tenant_id)
        digest = self._keyring.active.digest(identity)
        timestamp = created_at.isoformat()
        tenant_hash = hashlib.sha256(
            f"tenant|{tenant_id}|1.0|1|product_user|{timestamp}".encode("utf-8")
        ).hexdigest()
        user_hash = hashlib.sha256(
            f"user|{user_id}|{tenant_id}|1.0|1|user|{timestamp}".encode("utf-8")
        ).hexdigest()

        with self._connection.transaction():
            existing = self._connection.execute(
                "SELECT user_id, tenant_id FROM omni_cio_v10.external_identity_bindings "
                "WHERE provider = %s AND subject_binding_sha256 = %s",
                (identity.provider.value, digest),
            ).fetchone()
            if existing is not None:
                return ProductAccountScopeV1(
                    user_id=str(existing[0]), tenant_id=str(existing[1])
                )

            self._connection.execute(
                "INSERT INTO omni_cio_v10.tenants "
                "(tenant_id, schema_version, identity_version, mode, created_at, record_sha256) "
                "VALUES (%s, '1.0', 1, 'product_user', %s, %s)",
                (tenant_id, created_at, tenant_hash),
            )
            self._connection.execute(
                "INSERT INTO omni_cio_v10.users "
                "(user_id, tenant_id, schema_version, identity_version, role, created_at, record_sha256) "
                "VALUES (%s, %s, '1.0', 1, 'user', %s, %s)",
                (user_id, tenant_id, created_at, user_hash),
            )
            self._connection.execute(
                "INSERT INTO omni_cio_v10.external_identity_bindings "
                "(provider, subject_binding_sha256, binding_key_version, user_id, "
                "tenant_id, linked_at, last_verified_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    identity.provider.value,
                    digest,
                    self._keyring.active.version,
                    user_id,
                    tenant_id,
                    created_at,
                    created_at,
                ),
            )
        return scope
