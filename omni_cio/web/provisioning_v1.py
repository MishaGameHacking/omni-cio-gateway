from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hmac
import secrets
from threading import RLock, Timer
from typing import Any, Protocol

from omni_cio.adapters.tinvest_connection_v1 import discover_read_account_bindings
from omni_cio.adapters.tinvest_read_v1 import BrokerAccountBindingV1
from omni_cio.web.broker_vault_v1 import ReadBrokerConnectionVaultV1
from omni_cio.web.persistence_v1 import (
    BrokerConnectionRecordV1,
    PostgresBrokerConnectionRepositoryV1,
    new_connection_identity_pair,
)


class BrokerProvisioningError(RuntimeError):
    """Fail-closed Web broker provisioning error without credential disclosure."""


class _ExpiryHandle(Protocol):
    def cancel(self) -> None: ...


ExpiryScheduler = Callable[[float, Callable[[], None]], _ExpiryHandle]


@dataclass(frozen=True, slots=True)
class BrokerProvisioningAccountV1:
    selection_id: str
    masked_label: str
    access_level: str = "READ_ONLY"


@dataclass(frozen=True, slots=True)
class BrokerProvisioningPreviewV1:
    challenge_id: str
    expires_at: datetime
    accounts: tuple[BrokerProvisioningAccountV1, ...]


@dataclass(slots=True)
class _ChallengeV1:
    challenge_id: str
    user_id: str
    tenant_id: str
    token_bytes: bytearray
    selections: dict[str, BrokerAccountBindingV1]
    expires_at: datetime
    expiry_handle: _ExpiryHandle | None = None


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("provisioning timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def _zero(buffer: bytearray) -> None:
    for index in range(len(buffer)):
        buffer[index] = 0


def _schedule_expiry(delay_seconds: float, callback: Callable[[], None]) -> Timer:
    timer = Timer(delay_seconds, callback)
    timer.daemon = True
    timer.start()
    return timer


class BrokerProvisioningRegistryV1:
    """Short-lived memory-only bridge between token preview and account selection.

    A daemon expiry timer removes and zeroes every challenge at its wall-clock TTL,
    even when the browser abandons the provisioning flow and no later registry call
    occurs. Deterministic timestamp checks remain authoritative during consume.
    """

    def __init__(
        self,
        *,
        lifetime: timedelta = timedelta(minutes=5),
        expiry_scheduler: ExpiryScheduler = _schedule_expiry,
    ) -> None:
        if lifetime <= timedelta(0) or lifetime > timedelta(minutes=15):
            raise ValueError("provisioning lifetime must be in (0, 15 minutes]")
        self._lifetime = lifetime
        self._expiry_scheduler = expiry_scheduler
        self._challenges: dict[str, _ChallengeV1] = {}
        self._lock = RLock()

    def create(
        self,
        *,
        user_id: str,
        tenant_id: str,
        token: str,
        bindings: tuple[BrokerAccountBindingV1, ...],
        now: datetime,
    ) -> BrokerProvisioningPreviewV1:
        current = _utc(now)
        normalized = token.strip()
        if not normalized or len(normalized) > 16384:
            raise BrokerProvisioningError("BROKER_READ_TOKEN_INVALID")
        if not bindings:
            raise BrokerProvisioningError("BROKER_READ_NO_ACCOUNTS")
        challenge_id = secrets.token_urlsafe(24)
        selections: dict[str, BrokerAccountBindingV1] = {}
        preview_accounts: list[BrokerProvisioningAccountV1] = []
        for binding in bindings:
            selection_id = secrets.token_urlsafe(18)
            while selection_id in selections:
                selection_id = secrets.token_urlsafe(18)
            selections[selection_id] = binding
            preview_accounts.append(
                BrokerProvisioningAccountV1(
                    selection_id=selection_id,
                    masked_label=binding.masked_label,
                )
            )
        record = _ChallengeV1(
            challenge_id=challenge_id,
            user_id=user_id,
            tenant_id=tenant_id,
            token_bytes=bytearray(normalized.encode("utf-8")),
            selections=selections,
            expires_at=current + self._lifetime,
        )
        with self._lock:
            self._purge_locked(current)
            self._challenges[challenge_id] = record
        try:
            handle = self._expiry_scheduler(
                self._lifetime.total_seconds(),
                lambda: self._expire_challenge(challenge_id),
            )
        except Exception:
            with self._lock:
                current_record = self._challenges.pop(challenge_id, None)
            if current_record is not None:
                self._destroy(current_record, cancel_expiry=False)
            raise BrokerProvisioningError("BROKER_PROVISIONING_EXPIRY_UNAVAILABLE") from None
        with self._lock:
            current_record = self._challenges.get(challenge_id)
            if current_record is record:
                record.expiry_handle = handle
            else:
                handle.cancel()
        return BrokerProvisioningPreviewV1(
            challenge_id=challenge_id,
            expires_at=record.expires_at,
            accounts=tuple(preview_accounts),
        )

    @contextmanager
    def consume(
        self,
        *,
        challenge_id: str,
        user_id: str,
        tenant_id: str,
        selected_accounts: tuple[str, ...],
        now: datetime,
    ) -> Iterator[tuple[str, tuple[BrokerAccountBindingV1, ...]]]:
        current = _utc(now)
        with self._lock:
            self._purge_locked(current)
            record = self._challenges.pop(challenge_id, None)
        if record is None:
            raise BrokerProvisioningError("BROKER_PROVISIONING_CHALLENGE_INVALID")
        try:
            if record.user_id != user_id or record.tenant_id != tenant_id:
                raise BrokerProvisioningError("BROKER_PROVISIONING_SCOPE_MISMATCH")
            if current >= record.expires_at:
                raise BrokerProvisioningError("BROKER_PROVISIONING_CHALLENGE_EXPIRED")
            selected = set(selected_accounts)
            if not selected or len(selected) != len(selected_accounts):
                raise BrokerProvisioningError("BROKER_ACCOUNT_SELECTION_INVALID")
            if not selected.issubset(record.selections):
                raise BrokerProvisioningError("BROKER_ACCOUNT_SELECTION_INVALID")
            bindings = tuple(
                record.selections[selection_id] for selection_id in sorted(selected)
            )
            try:
                token = record.token_bytes.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise BrokerProvisioningError("BROKER_READ_TOKEN_INVALID") from exc
            yield token, bindings
        finally:
            self._destroy(record)

    def cancel(
        self,
        *,
        challenge_id: str,
        user_id: str,
        tenant_id: str,
    ) -> bool:
        with self._lock:
            record = self._challenges.get(challenge_id)
            if record is None:
                return False
            if record.user_id != user_id or record.tenant_id != tenant_id:
                raise BrokerProvisioningError("BROKER_PROVISIONING_SCOPE_MISMATCH")
            self._challenges.pop(challenge_id, None)
        self._destroy(record)
        return True

    def active_count(self, *, now: datetime) -> int:
        current = _utc(now)
        with self._lock:
            self._purge_locked(current)
            return len(self._challenges)

    def _expire_challenge(self, challenge_id: str) -> None:
        with self._lock:
            record = self._challenges.pop(challenge_id, None)
        if record is not None:
            self._destroy(record, cancel_expiry=False)

    @staticmethod
    def _destroy(record: _ChallengeV1, *, cancel_expiry: bool = True) -> None:
        handle = record.expiry_handle
        record.expiry_handle = None
        if cancel_expiry and handle is not None:
            handle.cancel()
        _zero(record.token_bytes)
        record.selections.clear()

    def _purge_locked(self, now: datetime) -> None:
        expired = [
            challenge_id
            for challenge_id, record in self._challenges.items()
            if now >= record.expires_at
        ]
        for challenge_id in expired:
            record = self._challenges.pop(challenge_id)
            self._destroy(record)


class BrokerProvisioningServiceV1:
    def __init__(
        self,
        *,
        registry: BrokerProvisioningRegistryV1,
        repository: PostgresBrokerConnectionRepositoryV1,
        vault: ReadBrokerConnectionVaultV1,
        client_factory_builder: Callable[[str], Callable[[], Any]],
    ) -> None:
        self._registry = registry
        self._repository = repository
        self._vault = vault
        self._client_factory_builder = client_factory_builder

    def preview(
        self,
        *,
        user_id: str,
        tenant_id: str,
        token: str,
        now: datetime,
    ) -> BrokerProvisioningPreviewV1:
        bindings = discover_read_account_bindings(self._client_factory_builder(token))
        return self._registry.create(
            user_id=user_id,
            tenant_id=tenant_id,
            token=token,
            bindings=bindings,
            now=now,
        )

    def commit_new(
        self,
        *,
        user_id: str,
        tenant_id: str,
        challenge_id: str,
        selected_accounts: tuple[str, ...],
        now: datetime,
    ) -> BrokerConnectionRecordV1:
        current = _utc(now)
        with self._registry.consume(
            challenge_id=challenge_id,
            user_id=user_id,
            tenant_id=tenant_id,
            selected_accounts=selected_accounts,
            now=current,
        ) as (token, preview_bindings):
            live_bindings = discover_read_account_bindings(
                self._client_factory_builder(token)
            )
            selected = self._rebind_selection(preview_bindings, live_bindings)
            connection_id, secret_ref = new_connection_identity_pair()
            self._vault.store(secret_ref=secret_ref, token=token)
            try:
                self._repository.create_read_connection(
                    tenant_id=tenant_id,
                    connection_id=connection_id,
                    secret_ref=secret_ref,
                    bindings=selected,
                    now=current,
                )
            except Exception:
                self._vault.revoke(secret_ref=secret_ref)
                raise

        records = self._repository.list_read_connections(tenant_id=tenant_id)
        for record in records:
            if hmac.compare_digest(record.connection_id, connection_id):
                return record
        raise BrokerProvisioningError("BROKER_CONNECTION_PERSISTENCE_MISMATCH")

    def replace_read_credential(
        self,
        *,
        user_id: str,
        tenant_id: str,
        connection_id: str,
        challenge_id: str,
        selected_accounts: tuple[str, ...],
        now: datetime,
    ) -> None:
        current = _utc(now)
        existing = next(
            (
                item
                for item in self._repository.list_read_connections(tenant_id=tenant_id)
                if hmac.compare_digest(item.connection_id, connection_id)
            ),
            None,
        )
        if existing is None or existing.state != "ACTIVE":
            raise BrokerProvisioningError("BROKER_CONNECTION_NOT_ACTIVE")
        expected = {item.account_fingerprint_sha256 for item in existing.accounts}

        with self._registry.consume(
            challenge_id=challenge_id,
            user_id=user_id,
            tenant_id=tenant_id,
            selected_accounts=selected_accounts,
            now=current,
        ) as (token, preview_bindings):
            live_bindings = discover_read_account_bindings(
                self._client_factory_builder(token)
            )
            selected = self._rebind_selection(preview_bindings, live_bindings)
            actual = {item.account_fingerprint_sha256 for item in selected}
            if actual != expected:
                raise BrokerProvisioningError("BROKER_REPLACEMENT_ACCOUNT_MISMATCH")
            _, new_secret_ref = new_connection_identity_pair()
            self._vault.store(secret_ref=new_secret_ref, token=token)
            try:
                old_secret_ref = self._repository.replace_secret_ref(
                    tenant_id=tenant_id,
                    connection_id=connection_id,
                    new_secret_ref=new_secret_ref,
                    now=current,
                )
            except Exception:
                self._vault.revoke(secret_ref=new_secret_ref)
                raise
            self._vault.revoke(secret_ref=old_secret_ref)

    def revoke_read_connection(
        self,
        *,
        tenant_id: str,
        connection_id: str,
        now: datetime,
    ) -> bool:
        secret_ref = self._repository.revoke_read_connection(
            tenant_id=tenant_id,
            connection_id=connection_id,
            now=_utc(now),
        )
        if secret_ref is None:
            return False
        self._vault.revoke(secret_ref=secret_ref)
        return True

    @staticmethod
    def _rebind_selection(
        preview: tuple[BrokerAccountBindingV1, ...],
        live: tuple[BrokerAccountBindingV1, ...],
    ) -> tuple[BrokerAccountBindingV1, ...]:
        live_map = {item.account_fingerprint_sha256: item for item in live}
        rebound: list[BrokerAccountBindingV1] = []
        for candidate in preview:
            live_candidate = live_map.get(candidate.account_fingerprint_sha256)
            if live_candidate is None:
                raise BrokerProvisioningError(
                    "BROKER_ACCOUNT_CHANGED_DURING_PROVISIONING"
                )
            if (
                live_candidate.broker_account_id != candidate.broker_account_id
                or live_candidate.masked_label != candidate.masked_label
            ):
                raise BrokerProvisioningError(
                    "BROKER_ACCOUNT_CHANGED_DURING_PROVISIONING"
                )
            rebound.append(live_candidate)
        return tuple(rebound)