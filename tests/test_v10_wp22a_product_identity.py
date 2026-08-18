from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from omni_cio.web.identity_v1 import IdentityProviderV1, VerifiedExternalIdentityV1
from omni_cio.web.product_identity_v1 import (
    IdentityBindingKeyV1,
    IdentityBindingKeyringV1,
    PostgresProductIdentityRepositoryV1,
    ProductAccountScopeV1,
    ProductIdentityError,
)


NOW = datetime(2026, 8, 18, 20, 0, tzinfo=timezone.utc)


class _Cursor:
    def __init__(self, row: tuple[Any, ...] | None = None) -> None:
        self._row = row
        self.rowcount = 0 if row is None else 1

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._row

    def fetchall(self) -> list[tuple[Any, ...]]:
        return [] if self._row is None else [self._row]


class _Transaction:
    def __enter__(self) -> _Transaction:
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        del exc_type, exc, traceback


class _FakeConnection:
    def __init__(self) -> None:
        self.users: set[tuple[str, str]] = set()
        self.tenants: set[str] = set()
        self.bindings: dict[tuple[str, str], tuple[int, str, str]] = {}
        self.params_seen: list[tuple[Any, ...]] = []
        self.advisory_locks: list[int] = []

    def transaction(self) -> _Transaction:
        return _Transaction()

    def execute(
        self,
        query: Any,
        params: Any = None,
        *,
        prepare: bool | None = None,
    ) -> _Cursor:
        del prepare
        sql = " ".join(str(query).split())
        values = tuple(params or ())
        self.params_seen.append(values)

        if sql.startswith("SELECT pg_advisory_xact_lock"):
            self.advisory_locks.append(int(values[0]))
            return _Cursor((1,))

        if sql.startswith(
            "SELECT user_id, tenant_id FROM omni_cio_v10.external_identity_bindings"
        ):
            provider, digest = str(values[0]), str(values[1])
            row = self.bindings.get((provider, digest))
            if row is None:
                return _Cursor()
            version, user_id, tenant_id = row
            if "binding_key_version = %s" in sql and version != int(values[2]):
                return _Cursor()
            return _Cursor((user_id, tenant_id))

        if sql.startswith("UPDATE omni_cio_v10.external_identity_bindings"):
            return _Cursor((1,))

        if sql.startswith("SELECT 1 FROM omni_cio_v10.users"):
            return _Cursor((1,)) if (str(values[0]), str(values[1])) in self.users else _Cursor()

        if sql.startswith(
            "SELECT subject_binding_sha256 FROM omni_cio_v10.external_identity_bindings"
        ):
            user_id, provider = str(values[0]), str(values[1])
            for (stored_provider, digest), (_, stored_user, _) in self.bindings.items():
                if stored_provider == provider and stored_user == user_id:
                    return _Cursor((digest,))
            return _Cursor()

        if sql.startswith("INSERT INTO omni_cio_v10.tenants"):
            self.tenants.add(str(values[0]))
            return _Cursor((1,))

        if sql.startswith("INSERT INTO omni_cio_v10.users"):
            self.users.add((str(values[0]), str(values[1])))
            return _Cursor((1,))

        if sql.startswith("INSERT INTO omni_cio_v10.external_identity_bindings"):
            provider = str(values[0])
            digest = str(values[1])
            version = int(values[2])
            user_id = str(values[3])
            tenant_id = str(values[4])
            self.bindings[(provider, digest)] = (version, user_id, tenant_id)
            return _Cursor((1,))

        raise AssertionError(f"unexpected SQL in fake: {sql}")


def _key(version: int = 1, byte: bytes = b"k") -> IdentityBindingKeyV1:
    return IdentityBindingKeyV1(version=version, key=byte * 32)


def _repo(
    connection: _FakeConnection,
    *,
    registration_enabled: bool = False,
    keyring: IdentityBindingKeyringV1 | None = None,
) -> PostgresProductIdentityRepositoryV1:
    return PostgresProductIdentityRepositoryV1(
        connection,  # type: ignore[arg-type]
        keyring=keyring or IdentityBindingKeyringV1(active=_key()),
        registration_enabled=registration_enabled,
    )


def test_keyed_binding_is_stable_provider_scoped_and_not_raw_subject() -> None:
    telegram = VerifiedExternalIdentityV1(
        provider=IdentityProviderV1.TELEGRAM,
        subject="123456789",
    )
    vk = VerifiedExternalIdentityV1(
        provider=IdentityProviderV1.VK_ID,
        subject="123456789",
    )
    first = _key().digest(telegram)
    second = _key().digest(telegram)

    assert first == second
    assert len(first) == 64
    assert first != _key().digest(vk)
    assert "123456789" not in first
    assert _key(byte=b"z").digest(telegram) != first


def test_binding_key_requires_version_and_high_entropy_length() -> None:
    with pytest.raises(ValueError, match="version"):
        IdentityBindingKeyV1(version=0, key=b"k" * 32)
    with pytest.raises(ValueError, match="32 bytes"):
        IdentityBindingKeyV1(version=1, key=b"short")
    with pytest.raises(ValueError, match="unique"):
        IdentityBindingKeyringV1(active=_key(1), previous=(_key(1, b"z"),))


def test_unknown_identity_fails_closed_while_registration_is_disabled() -> None:
    connection = _FakeConnection()
    identity = VerifiedExternalIdentityV1(
        provider=IdentityProviderV1.TELEGRAM,
        subject="tg-subject-disabled",
    )

    with pytest.raises(ProductIdentityError, match="PRODUCT_REGISTRATION_DISABLED"):
        _repo(connection).resolve_or_register(identity, now=NOW)

    assert connection.tenants == set()
    assert connection.users == set()
    assert connection.bindings == {}


def test_registration_creates_internal_scope_serializes_and_never_persists_raw_subject() -> None:
    connection = _FakeConnection()
    identity = VerifiedExternalIdentityV1(
        provider=IdentityProviderV1.VK_ID,
        subject="vk-stable-subject-001",
    )
    repository = _repo(connection, registration_enabled=True)

    first = repository.resolve_or_register(identity, now=NOW)
    second = repository.resolve_or_register(identity, now=NOW)

    assert first == second
    assert first.user_id.startswith("user:v1:")
    assert first.tenant_id.startswith("tenant:v1:")
    assert first.user_id != "user:v1:owner"
    assert first.tenant_id != "tenant:v1:owner"
    assert (first.user_id, first.tenant_id) in connection.users
    assert first.tenant_id in connection.tenants
    assert len(connection.advisory_locks) == 1
    assert "vk-stable-subject-001" not in repr(connection.params_seen)


def test_previous_binding_key_is_resolved_and_cannot_be_rebound() -> None:
    connection = _FakeConnection()
    previous = _key(1, b"p")
    active = _key(2, b"a")
    keyring = IdentityBindingKeyringV1(active=active, previous=(previous,))
    identity = VerifiedExternalIdentityV1(
        provider=IdentityProviderV1.TELEGRAM,
        subject="rotated-key-subject",
    )
    first_scope = ProductAccountScopeV1(
        user_id="user:v1:first_user",
        tenant_id="tenant:v1:first_tenant",
    )
    second_scope = ProductAccountScopeV1(
        user_id="user:v1:second_user",
        tenant_id="tenant:v1:second_tenant",
    )
    connection.users.update(
        {
            (first_scope.user_id, first_scope.tenant_id),
            (second_scope.user_id, second_scope.tenant_id),
        }
    )
    connection.bindings[(identity.provider.value, previous.digest(identity))] = (
        previous.version,
        first_scope.user_id,
        first_scope.tenant_id,
    )
    repository = _repo(connection, keyring=keyring)

    assert repository.resolve_verified(identity, now=NOW) == first_scope
    with pytest.raises(ProductIdentityError, match="EXTERNAL_IDENTITY_ALREADY_BOUND"):
        repository.link_verified(second_scope, identity, now=NOW)


def test_external_identity_cannot_be_rebound_to_another_account() -> None:
    connection = _FakeConnection()
    first_scope = ProductAccountScopeV1(
        user_id="user:v1:first_user",
        tenant_id="tenant:v1:first_tenant",
    )
    second_scope = ProductAccountScopeV1(
        user_id="user:v1:second_user",
        tenant_id="tenant:v1:second_tenant",
    )
    connection.users.update(
        {
            (first_scope.user_id, first_scope.tenant_id),
            (second_scope.user_id, second_scope.tenant_id),
        }
    )
    identity = VerifiedExternalIdentityV1(
        provider=IdentityProviderV1.TELEGRAM,
        subject="shared-provider-subject",
    )
    repository = _repo(connection)

    repository.link_verified(first_scope, identity, now=NOW)
    with pytest.raises(ProductIdentityError, match="EXTERNAL_IDENTITY_ALREADY_BOUND"):
        repository.link_verified(second_scope, identity, now=NOW)


def test_same_account_cannot_auto_replace_provider_binding() -> None:
    connection = _FakeConnection()
    scope = ProductAccountScopeV1(
        user_id="user:v1:bound_user",
        tenant_id="tenant:v1:bound_tenant",
    )
    connection.users.add((scope.user_id, scope.tenant_id))
    repository = _repo(connection)
    repository.link_verified(
        scope,
        VerifiedExternalIdentityV1(
            provider=IdentityProviderV1.VK_ID,
            subject="first-vk-subject",
        ),
        now=NOW,
    )

    with pytest.raises(ProductIdentityError, match="ACCOUNT_PROVIDER_ALREADY_BOUND"):
        repository.link_verified(
            scope,
            VerifiedExternalIdentityV1(
                provider=IdentityProviderV1.VK_ID,
                subject="second-vk-subject",
            ),
            now=NOW,
        )


def test_identity_subject_must_be_canonical_not_profile_derived_whitespace() -> None:
    with pytest.raises(ValueError, match="canonical"):
        VerifiedExternalIdentityV1(
            provider=IdentityProviderV1.TELEGRAM,
            subject=" 12345 ",
        )
