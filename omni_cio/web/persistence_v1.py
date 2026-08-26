from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
import secrets
from typing import Any

from omni_cio.adapters.tinvest_read_v1 import BrokerAccountBindingV1
from omni_cio.contracts.v1.domain import BrokerAccountV1, BrokerProvider
from omni_cio.persistence.migration import ConnectionLike
from omni_cio.persistence.repository import model_record_sha256
from omni_cio.web.broker_vault_v1 import new_read_connection_secret_ref
from omni_cio.web.session_v1 import (
    SessionPolicyV1,
    SessionScopeV1,
    _token_hash,
    new_session_token_v1,
)


_TENANT_ID_RE = re.compile(r"^tenant:v1:[a-z0-9][a-z0-9_-]{2,63}$")


@dataclass(frozen=True, slots=True)
class BrokerConnectionRecordV1:
    connection_id: str
    tenant_id: str
    provider: str
    credential_role: str
    state: str
    secret_ref: str
    created_at: datetime
    last_verified_at: datetime | None
    accounts: tuple[BrokerAccountBindingV1, ...]


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Web persistence timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def _set_tenant_scope(connection: ConnectionLike, tenant_id: str) -> None:
    """Bind PostgreSQL RLS to the authenticated server-side tenant for this tx."""

    if _TENANT_ID_RE.fullmatch(tenant_id) is None:
        raise ValueError("WEB_TENANT_SCOPE_INVALID")
    connection.execute(
        "SELECT set_config('omni_cio.tenant_id', %s, true)",
        (tenant_id,),
    )


def new_broker_connection_id() -> str:
    return f"broker-connection:v1:{secrets.token_hex(32)}"


class PostgresWebSessionRegistryV1:
    def __init__(
        self,
        connection: ConnectionLike,
        policy: SessionPolicyV1 | None = None,
    ) -> None:
        self._connection = connection
        self._policy = policy or SessionPolicyV1()

    def create(
        self,
        *,
        user_id: str,
        tenant_id: str,
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
        user_id: str,
        tenant_id: str,
        now: datetime,
    ) -> SessionScopeV1:
        """Bind a pre-minted opaque credential to durable server-side scope."""

        issued = _utc(now)
        digest = _token_hash(token)
        idle_expires = issued + self._policy.idle_lifetime
        absolute_expires = issued + self._policy.absolute_lifetime
        with self._connection.transaction():
            self._connection.execute(
                "INSERT INTO omni_cio_v10.web_sessions "
                "(token_sha256, user_id, tenant_id, created_at, last_seen_at, "
                "idle_expires_at, absolute_expires_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    digest,
                    user_id,
                    tenant_id,
                    issued,
                    issued,
                    idle_expires,
                    absolute_expires,
                ),
            )
        return SessionScopeV1(
            user_id=user_id,
            tenant_id=tenant_id,
            expires_at=idle_expires,
        )

    def resolve(self, token: str | None, *, now: datetime) -> SessionScopeV1 | None:
        if not token:
            return None
        current = _utc(now)
        try:
            digest = _token_hash(token)
        except ValueError:
            return None
        with self._connection.transaction():
            row = self._connection.execute(
                "SELECT user_id, tenant_id, idle_expires_at, absolute_expires_at, revoked_at "
                "FROM omni_cio_v10.web_sessions WHERE token_sha256 = %s FOR UPDATE",
                (digest,),
            ).fetchone()
            if row is None or row[4] is not None:
                return None
            idle_expires = _utc(row[2])
            absolute_expires = _utc(row[3])
            if current >= idle_expires or current >= absolute_expires:
                self._connection.execute(
                    "DELETE FROM omni_cio_v10.web_sessions WHERE token_sha256 = %s",
                    (digest,),
                )
                return None
            refreshed_idle = min(
                current + self._policy.idle_lifetime,
                absolute_expires,
            )
            self._connection.execute(
                "UPDATE omni_cio_v10.web_sessions SET last_seen_at = %s, idle_expires_at = %s "
                "WHERE token_sha256 = %s",
                (current, refreshed_idle, digest),
            )
            return SessionScopeV1(
                user_id=str(row[0]),
                tenant_id=str(row[1]),
                expires_at=refreshed_idle,
            )

    def revoke(self, token: str | None, *, now: datetime) -> bool:
        if not token:
            return False
        current = _utc(now)
        try:
            digest = _token_hash(token)
        except ValueError:
            return False
        with self._connection.transaction():
            cursor = self._connection.execute(
                "UPDATE omni_cio_v10.web_sessions SET revoked_at = %s "
                "WHERE token_sha256 = %s AND revoked_at IS NULL",
                (current, digest),
            )
            return cursor.rowcount == 1

    def revoke_all_for_user(self, user_id: str, *, now: datetime) -> int:
        current = _utc(now)
        with self._connection.transaction():
            cursor = self._connection.execute(
                "UPDATE omni_cio_v10.web_sessions SET revoked_at = %s "
                "WHERE user_id = %s AND revoked_at IS NULL",
                (current, user_id),
            )
            return cursor.rowcount


class PostgresBrokerConnectionRepositoryV1:
    def __init__(self, connection: ConnectionLike) -> None:
        self._connection = connection

    def create_read_connection(
        self,
        *,
        tenant_id: str,
        connection_id: str,
        secret_ref: str,
        bindings: tuple[BrokerAccountBindingV1, ...],
        now: datetime,
    ) -> None:
        if not bindings:
            raise ValueError("broker connection requires at least one verified account")
        timestamp = _utc(now)
        with self._connection.transaction():
            _set_tenant_scope(self._connection, tenant_id)
            for binding in bindings:
                account = BrokerAccountV1(
                    broker_account_id=binding.broker_account_id,
                    tenant_id=tenant_id,
                    provider=BrokerProvider.T_INVEST,
                    account_fingerprint_sha256=binding.account_fingerprint_sha256,
                    masked_label=binding.masked_label,
                    created_at=timestamp,
                )
                digest = model_record_sha256(account)
                cursor = self._connection.execute(
                    "INSERT INTO omni_cio_v10.broker_accounts "
                    "(broker_account_id, tenant_id, schema_version, identity_version, provider, "
                    "account_fingerprint_sha256, masked_label, created_at, record_sha256) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (broker_account_id) DO NOTHING RETURNING record_sha256",
                    (
                        account.broker_account_id,
                        account.tenant_id,
                        account.schema_version,
                        account.identity_version,
                        account.provider.value,
                        account.account_fingerprint_sha256,
                        account.masked_label,
                        account.created_at,
                        digest,
                    ),
                )
                if cursor.fetchone() is None:
                    existing = self._connection.execute(
                        "SELECT schema_version, identity_version, provider, "
                        "account_fingerprint_sha256, masked_label, created_at, record_sha256 "
                        "FROM omni_cio_v10.broker_accounts "
                        "WHERE broker_account_id = %s AND tenant_id = %s",
                        (account.broker_account_id, tenant_id),
                    ).fetchone()
                    if (
                        existing is None
                        or str(existing[0]) != account.schema_version
                        or int(existing[1]) != account.identity_version
                    ):
                        raise ValueError("BROKER_ACCOUNT_IMMUTABLE_CONFLICT")
                    existing_account = BrokerAccountV1(
                        broker_account_id=account.broker_account_id,
                        tenant_id=tenant_id,
                        provider=BrokerProvider(str(existing[2])),
                        account_fingerprint_sha256=str(existing[3]),
                        masked_label=str(existing[4]),
                        created_at=_utc(existing[5]),
                    )
                    if (
                        existing_account.provider != account.provider
                        or existing_account.account_fingerprint_sha256
                        != account.account_fingerprint_sha256
                        or existing_account.masked_label != account.masked_label
                        or model_record_sha256(existing_account) != str(existing[6])
                    ):
                        raise ValueError("BROKER_ACCOUNT_IMMUTABLE_CONFLICT")

            self._connection.execute(
                "INSERT INTO omni_cio_v10.broker_connections "
                "(connection_id, tenant_id, provider, credential_role, state, secret_ref, "
                "created_at, last_verified_at) VALUES (%s, %s, 't_invest', 'read', 'ACTIVE', %s, %s, %s)",
                (connection_id, tenant_id, secret_ref, timestamp, timestamp),
            )
            for binding in bindings:
                self._connection.execute(
                    "INSERT INTO omni_cio_v10.broker_connection_accounts "
                    "(connection_id, tenant_id, broker_account_id, linked_at) "
                    "VALUES (%s, %s, %s, %s)",
                    (
                        connection_id,
                        tenant_id,
                        binding.broker_account_id,
                        timestamp,
                    ),
                )

    def list_read_connections(
        self, *, tenant_id: str
    ) -> tuple[BrokerConnectionRecordV1, ...]:
        with self._connection.transaction():
            _set_tenant_scope(self._connection, tenant_id)
            rows = self._connection.execute(
                "SELECT c.connection_id, c.tenant_id, c.provider, c.credential_role, c.state, "
                "c.secret_ref, c.created_at, c.last_verified_at, a.broker_account_id, "
                "a.account_fingerprint_sha256, a.masked_label "
                "FROM omni_cio_v10.broker_connections c "
                "LEFT JOIN omni_cio_v10.broker_connection_accounts ca "
                "ON ca.connection_id = c.connection_id AND ca.tenant_id = c.tenant_id "
                "LEFT JOIN omni_cio_v10.broker_accounts a "
                "ON a.broker_account_id = ca.broker_account_id AND a.tenant_id = ca.tenant_id "
                "WHERE c.tenant_id = %s AND c.state <> 'REVOKED' "
                "ORDER BY c.created_at, c.connection_id, a.broker_account_id",
                (tenant_id,),
            ).fetchall()
        grouped: dict[str, tuple[list[Any], list[BrokerAccountBindingV1]]] = {}
        for row in rows:
            connection_id = str(row[0])
            entry = grouped.setdefault(connection_id, (list(row[:8]), []))
            if row[8] is not None:
                entry[1].append(
                    BrokerAccountBindingV1(
                        broker_account_id=str(row[8]),
                        account_fingerprint_sha256=str(row[9]),
                        masked_label=str(row[10]),
                        access_level="ACCOUNT_ACCESS_LEVEL_READ_ONLY",
                    )
                )
        return tuple(
            BrokerConnectionRecordV1(
                connection_id=values[0][0],
                tenant_id=values[0][1],
                provider=values[0][2],
                credential_role=values[0][3],
                state=values[0][4],
                secret_ref=values[0][5],
                created_at=_utc(values[0][6]),
                last_verified_at=(
                    _utc(values[0][7]) if values[0][7] is not None else None
                ),
                accounts=tuple(values[1]),
            )
            for _, values in sorted(grouped.items())
        )

    def revoke_read_connection(
        self,
        *,
        tenant_id: str,
        connection_id: str,
        now: datetime,
    ) -> str | None:
        current = _utc(now)
        with self._connection.transaction():
            _set_tenant_scope(self._connection, tenant_id)
            row = self._connection.execute(
                "SELECT secret_ref, state FROM omni_cio_v10.broker_connections "
                "WHERE tenant_id = %s AND connection_id = %s FOR UPDATE",
                (tenant_id, connection_id),
            ).fetchone()
            if row is None:
                return None
            if str(row[1]) == "REVOKED":
                return str(row[0])
            self._connection.execute(
                "UPDATE omni_cio_v10.broker_connections SET state = 'REVOKED', revoked_at = %s "
                "WHERE tenant_id = %s AND connection_id = %s",
                (current, tenant_id, connection_id),
            )
            return str(row[0])

    def replace_secret_ref(
        self,
        *,
        tenant_id: str,
        connection_id: str,
        new_secret_ref: str,
        now: datetime,
    ) -> str:
        current = _utc(now)
        with self._connection.transaction():
            _set_tenant_scope(self._connection, tenant_id)
            row = self._connection.execute(
                "SELECT secret_ref, state FROM omni_cio_v10.broker_connections "
                "WHERE tenant_id = %s AND connection_id = %s FOR UPDATE",
                (tenant_id, connection_id),
            ).fetchone()
            if row is None or str(row[1]) != "ACTIVE":
                raise ValueError("BROKER_CONNECTION_NOT_ACTIVE")
            previous = str(row[0])
            self._connection.execute(
                "UPDATE omni_cio_v10.broker_connections "
                "SET secret_ref = %s, last_verified_at = %s "
                "WHERE tenant_id = %s AND connection_id = %s",
                (new_secret_ref, current, tenant_id, connection_id),
            )
            return previous


def new_connection_identity_pair() -> tuple[str, str]:
    return new_broker_connection_id(), new_read_connection_secret_ref()
