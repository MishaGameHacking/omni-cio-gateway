from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
import secrets
from typing import Protocol

from omni_cio.persistence.migration import ConnectionLike
from omni_cio.web.identity_v1 import VerifiedExternalIdentityV1


_USER_ID_PATTERN = re.compile(r"^user:v1:[a-z0-9][a-z0-9_-]{2,63}$")
_TENANT_ID_PATTERN = re.compile(r"^tenant:v1:[a-z0-9][a-z0-9_-]{2,63}$")


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


class PostgresProductIdentityRepositoryV1:
    """Durable external-identity -> internal account/tenant binding.

    Raw provider subjects are used only long enough to derive the binding digest.
    They are never written to PostgreSQL. The repository never accepts a tenant
    selector from a browser; callers supply only an already-authenticated scope.
    """

    def __init__(
        self,
        connection: ConnectionLike,
        *,
        scope_factory: Callable[[], ProductAccountScopeV1] = _new_scope,
    ) -> None:
        self._connection = connection
        self._scope_factory = scope_factory

    def resolve_verified_identity(
        self,
        identity: VerifiedExternalIdentityV1,
    ) -> ProductAccountScopeV1 | None:
        row = self._connection.execute(
            "SELECT user_id, tenant_id "
            "FROM omni_cio_v10.external_identity_bindings "
            "WHERE provider = %s AND subject_binding_sha256 = %s",
            (identity.provider.value, identity.binding_fingerprint_sha256()),
        ).fetchone()
        if row is None:
            return None
        return ProductAccountScopeV1(user_id=str(row[0]), tenant_id=str(row[1]))

    def create_account(
        self,
        identity: VerifiedExternalIdentityV1,
        *,
        now: datetime,
    ) -> ProductAccountScopeV1:
        timestamp = _utc(now)
        with self._connection.transaction():
            existing = self.resolve_verified_identity(identity)
            if existing is not None:
                return existing

            scope = self._scope_factory()
            if scope.user_id == "user:v1:owner" or scope.tenant_id == "tenant:v1:owner":
                raise ProductIdentityError("OWNER_IDENTITY_RESERVED")

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
            self._insert_binding(scope, identity, timestamp)
            return scope

    def link_identity(
        self,
        scope: ProductAccountScopeV1,
        identity: VerifiedExternalIdentityV1,
        *,
        now: datetime,
    ) -> None:
        timestamp = _utc(now)
        with self._connection.transaction():
            existing = self.resolve_verified_identity(identity)
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
                "SELECT subject_binding_sha256 "
                "FROM omni_cio_v10.external_identity_bindings "
                "WHERE user_id = %s AND provider = %s",
                (scope.user_id, identity.provider.value),
            ).fetchone()
            if provider_row is not None:
                raise ProductIdentityError("PROVIDER_ALREADY_LINKED")

            self._insert_binding(scope, identity, timestamp)

    def _insert_binding(
        self,
        scope: ProductAccountScopeV1,
        identity: VerifiedExternalIdentityV1,
        timestamp: datetime,
    ) -> None:
        self._connection.execute(
            "INSERT INTO omni_cio_v10.external_identity_bindings "
            "(provider, subject_binding_sha256, user_id, tenant_id, linked_at, "
            "last_verified_at) VALUES (%s, %s, %s, %s, %s, %s)",
            (
                identity.provider.value,
                identity.binding_fingerprint_sha256(),
                scope.user_id,
                scope.tenant_id,
                timestamp,
                timestamp,
            ),
        )


class ProductIdentityServiceV1:
    """Authentication-to-account boundary with registration disabled by default."""

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
            return existing
        if not self._registration_enabled:
            raise ProductIdentityError("PUBLIC_REGISTRATION_DISABLED")
        return self._repository.create_account(identity, now=now)

    def link_authenticated_identity(
        self,
        scope: ProductAccountScopeV1,
        identity: VerifiedExternalIdentityV1,
        *,
        now: datetime,
    ) -> None:
        self._repository.link_identity(scope, identity, now=now)
