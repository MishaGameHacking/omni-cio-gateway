from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from omni_cio.contracts.v1.domain import OWNER_TENANT_ID, OWNER_USER_ID
from omni_cio.web.persistence_v1 import BrokerConnectionRecordV1
from omni_cio.web.provisioning_v1 import (
    BrokerProvisioningError,
    BrokerProvisioningRegistryV1,
    BrokerProvisioningServiceV1,
)


NOW = datetime(2026, 8, 11, 7, 0, tzinfo=timezone.utc)


class FakeUsers:
    def __init__(self, accounts: list[dict[str, Any]]) -> None:
        self._accounts = accounts

    def get_accounts(self) -> dict[str, Any]:
        return {"accounts": list(self._accounts)}


class FakeClient:
    def __init__(self, accounts: list[dict[str, Any]]) -> None:
        self.users = FakeUsers(accounts)

    def __enter__(self) -> FakeClient:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        del exc_type, exc, tb


def account(
    account_id: str,
    *,
    access_level: str = "ACCOUNT_ACCESS_LEVEL_READ_ONLY",
) -> dict[str, Any]:
    return {
        "id": account_id,
        "type": "ACCOUNT_TYPE_TINKOFF",
        "status": "ACCOUNT_STATUS_OPEN",
        "access_level": access_level,
    }


class FakeVault:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def store(self, *, secret_ref: str, token: str) -> None:
        self.values[secret_ref] = token

    def revoke(self, *, secret_ref: str) -> bool:
        return self.values.pop(secret_ref, None) is not None


class FakeRepository:
    def __init__(self) -> None:
        self.records: dict[str, BrokerConnectionRecordV1] = {}

    def create_read_connection(self, *, tenant_id: str, connection_id: str, secret_ref: str, bindings: tuple[Any, ...], now: datetime) -> None:
        self.records[connection_id] = BrokerConnectionRecordV1(
            connection_id=connection_id,
            tenant_id=tenant_id,
            provider="t_invest",
            credential_role="read",
            state="ACTIVE",
            secret_ref=secret_ref,
            created_at=now,
            last_verified_at=now,
            accounts=bindings,
        )

    def list_read_connections(self, *, tenant_id: str) -> tuple[BrokerConnectionRecordV1, ...]:
        return tuple(record for record in self.records.values() if record.tenant_id == tenant_id)

    def replace_secret_ref(self, *, tenant_id: str, connection_id: str, new_secret_ref: str, now: datetime) -> str:
        record = self.records[connection_id]
        assert record.tenant_id == tenant_id
        previous = record.secret_ref
        self.records[connection_id] = BrokerConnectionRecordV1(
            connection_id=record.connection_id,
            tenant_id=record.tenant_id,
            provider=record.provider,
            credential_role=record.credential_role,
            state=record.state,
            secret_ref=new_secret_ref,
            created_at=record.created_at,
            last_verified_at=now,
            accounts=record.accounts,
        )
        return previous

    def revoke_read_connection(self, *, tenant_id: str, connection_id: str, now: datetime) -> str | None:
        del now
        record = self.records.get(connection_id)
        if record is None or record.tenant_id != tenant_id:
            return None
        self.records[connection_id] = BrokerConnectionRecordV1(
            connection_id=record.connection_id,
            tenant_id=record.tenant_id,
            provider=record.provider,
            credential_role=record.credential_role,
            state="REVOKED",
            secret_ref=record.secret_ref,
            created_at=record.created_at,
            last_verified_at=record.last_verified_at,
            accounts=record.accounts,
        )
        return record.secret_ref


def builder(accounts: list[dict[str, Any]]):
    return lambda token: (lambda: FakeClient(accounts))


def service(accounts: list[dict[str, Any]]) -> tuple[BrokerProvisioningServiceV1, BrokerProvisioningRegistryV1, FakeRepository, FakeVault]:
    registry = BrokerProvisioningRegistryV1()
    repository = FakeRepository()
    vault = FakeVault()
    instance = BrokerProvisioningServiceV1(
        registry=registry,
        repository=repository,  # type: ignore[arg-type]
        vault=vault,  # type: ignore[arg-type]
        client_factory_builder=builder(accounts),
    )
    return instance, registry, repository, vault


def test_preview_returns_only_masked_bindings_and_commit_scopes_secret() -> None:
    instance, registry, repository, vault = service(
        [account("owner-account-a-0001"), account("owner-account-b-0002")]
    )
    preview = instance.preview(
        user_id=OWNER_USER_ID,
        tenant_id=OWNER_TENANT_ID,
        token="synthetic-read-token",
        now=NOW,
    )
    serialized = repr(preview)
    assert "synthetic-read-token" not in serialized
    assert "owner-account-a-0001" not in serialized
    assert "owner-account-b-0002" not in serialized
    assert len(preview.accounts) == 2

    selected = (preview.accounts[1].account_fingerprint_sha256,)
    connection = instance.commit_new(
        user_id=OWNER_USER_ID,
        tenant_id=OWNER_TENANT_ID,
        challenge_id=preview.challenge_id,
        selected_fingerprints=selected,
        now=NOW + timedelta(seconds=2),
    )
    assert connection.tenant_id == OWNER_TENANT_ID
    assert len(connection.accounts) == 1
    assert connection.secret_ref in vault.values
    assert registry.active_count(now=NOW + timedelta(seconds=3)) == 0
    assert tuple(repository.records) == (connection.connection_id,)


def test_challenge_cannot_cross_tenant_or_user_scope() -> None:
    instance, _, _, _ = service([account("owner-account-a-0001")])
    preview = instance.preview(
        user_id=OWNER_USER_ID,
        tenant_id=OWNER_TENANT_ID,
        token="synthetic-read-token",
        now=NOW,
    )
    with pytest.raises(BrokerProvisioningError, match="SCOPE_MISMATCH"):
        instance.commit_new(
            user_id="user:v1:other",
            tenant_id="tenant:v1:other",
            challenge_id=preview.challenge_id,
            selected_fingerprints=(preview.accounts[0].account_fingerprint_sha256,),
            now=NOW + timedelta(seconds=1),
        )


def test_full_access_credential_is_rejected_before_challenge_or_vault_write() -> None:
    instance, registry, _, vault = service(
        [account("owner-account-a-0001", access_level="ACCOUNT_ACCESS_LEVEL_FULL_ACCESS")]
    )
    with pytest.raises(Exception, match="BROKER_READ_CREDENTIAL_NOT_READ_ONLY"):
        instance.preview(
            user_id=OWNER_USER_ID,
            tenant_id=OWNER_TENANT_ID,
            token="synthetic-full-token",
            now=NOW,
        )
    assert registry.active_count(now=NOW) == 0
    assert vault.values == {}


def test_replace_requires_same_verified_account_set() -> None:
    instance, _, repository, vault = service([account("owner-account-a-0001")])
    first = instance.preview(
        user_id=OWNER_USER_ID,
        tenant_id=OWNER_TENANT_ID,
        token="synthetic-read-token-one",
        now=NOW,
    )
    connection = instance.commit_new(
        user_id=OWNER_USER_ID,
        tenant_id=OWNER_TENANT_ID,
        challenge_id=first.challenge_id,
        selected_fingerprints=(first.accounts[0].account_fingerprint_sha256,),
        now=NOW + timedelta(seconds=1),
    )
    old_secret = connection.secret_ref

    second = instance.preview(
        user_id=OWNER_USER_ID,
        tenant_id=OWNER_TENANT_ID,
        token="synthetic-read-token-two",
        now=NOW + timedelta(seconds=2),
    )
    instance.replace_read_credential(
        user_id=OWNER_USER_ID,
        tenant_id=OWNER_TENANT_ID,
        connection_id=connection.connection_id,
        challenge_id=second.challenge_id,
        selected_fingerprints=(second.accounts[0].account_fingerprint_sha256,),
        now=NOW + timedelta(seconds=3),
    )
    current = repository.records[connection.connection_id]
    assert current.secret_ref != old_secret
    assert old_secret not in vault.values
    assert current.secret_ref in vault.values
