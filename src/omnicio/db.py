"""PostgreSQL persistence boundary for authentication."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


@dataclass(frozen=True, slots=True)
class UserRecord:
    id: UUID
    public_id: int
    status: str
    role: str


@dataclass(frozen=True, slots=True)
class TBankConnectionRecord:
    user_id: UUID
    environment: str
    account_id: str
    account_name: str
    encrypted_credential: bytes
    verified_at: datetime
    updated_at: datetime


class RegistrationClosedError(RuntimeError):
    """Raised when an unknown VK identity cannot create an account."""


class RegistrationCapacityError(RuntimeError):
    """Raised when the configured user-account capacity is exhausted."""


class Database:
    """Thin persistence adapter for authentication state."""

    def __init__(self, database_url: str) -> None:
        self.pool = ConnectionPool(
            conninfo=database_url,
            min_size=1,
            max_size=8,
            kwargs={"row_factory": dict_row},
            open=False,
        )

    def open(self) -> None:
        self.pool.open(wait=True)

    def close(self) -> None:
        self.pool.close()

    def healthcheck(self) -> bool:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    to_regclass('public.users') IS NOT NULL
                    AND to_regclass('public.sessions') IS NOT NULL
                    AND to_regclass('public.legal_acceptances') IS NOT NULL
                    AND to_regclass('public.vkid_identities') IS NOT NULL
                    AND to_regclass('public.tbank_connection') IS NOT NULL
                    AND to_regclass('public.instrument_catalog') IS NOT NULL
                    AND to_regclass('public.issuer_groups') IS NOT NULL
                    AND to_regclass('public.issuers') IS NOT NULL
                    AND to_regclass('public.instrument_issuer_map') IS NOT NULL
                    AND to_regclass('public.investment_profile_versions') IS NOT NULL
                    AND to_regclass('public.job_runs') IS NOT NULL
                    AND to_regclass('public.portfolio_snapshots') IS NOT NULL
                    AND to_regclass('public.portfolio_snapshot_positions') IS NOT NULL
                    AND to_regclass('public.operation_observations') IS NOT NULL
                    AND to_regclass('public.broker_sync_state') IS NOT NULL
                    AND EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'users'
                          AND column_name = 'role'
                    )
                    AND (
                        SELECT count(*) = 6
                        FROM pg_class AS c
                        JOIN pg_namespace AS n ON n.oid = c.relnamespace
                        WHERE n.nspname = 'public'
                          AND c.relname = ANY (
                              ARRAY[
                                  'investment_profile_versions',
                                  'job_runs',
                                  'portfolio_snapshots',
                                  'portfolio_snapshot_positions',
                                  'operation_observations',
                                  'broker_sync_state'
                              ]
                          )
                          AND c.relrowsecurity
                          AND c.relforcerowsecurity
                    )
                    AS ready
                """
            )
            fetched = cur.fetchone()
            if fetched is None:
                return False
            row = cast(dict[str, Any], fetched)
            return bool(row["ready"])

    def complete_vkid_login(
        self,
        *,
        vk_user_id: str,
        client_ip_hash: bytes,
        session_token_digest: bytes,
        session_ttl_seconds: int,
        legal_versions: dict[str, str],
        registration_enabled: bool,
        registration_max_users: int,
    ) -> tuple[UserRecord, bool]:
        """Resolve one VK ID identity and create its isolated application session."""

        with (
            self.pool.connection() as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            cur.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (vk_user_id,),
            )
            cur.execute(
                """
                SELECT u.id, u.public_id, u.status, u.role
                FROM users AS u
                JOIN vkid_identities AS v ON v.user_id = u.id
                WHERE v.vk_user_id = %s
                """,
                (vk_user_id,),
            )
            fetched_user = cur.fetchone()
            created = False
            linked = False

            if fetched_user is None:
                if not registration_enabled:
                    raise RegistrationClosedError("registration is closed")

                cur.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    ("omnicio-registration-capacity",),
                )
                cur.execute(
                    """
                    SELECT count(*) AS total
                    FROM users
                    WHERE status <> 'deleted'
                    """
                )
                count_row = cur.fetchone()
                if count_row is None:
                    raise RuntimeError("registration capacity query returned no row")
                total = int(cast(dict[str, Any], count_row)["total"])
                if total >= registration_max_users:
                    raise RegistrationCapacityError("registration capacity reached")

                cur.execute(
                    "INSERT INTO users DEFAULT VALUES RETURNING id, public_id, status, role"
                )
                inserted = cur.fetchone()
                if inserted is None:
                    raise RuntimeError("user insert returned no row")
                user = _user(cast(dict[str, Any], inserted))
                created = True

                cur.execute(
                    """
                    INSERT INTO vkid_identities (user_id, vk_user_id, verified_at)
                    VALUES (%s, %s, now())
                    """,
                    (user.id, vk_user_id),
                )
                linked = True
            else:
                user = _user(cast(dict[str, Any], fetched_user))

            if user.status != "active":
                raise PermissionError("account is not active")

            for document_type, version in legal_versions.items():
                cur.execute(
                    """
                    INSERT INTO legal_acceptances (
                        user_id,
                        document_type,
                        document_version,
                        client_ip_hash
                    )
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (
                        user_id,
                        document_type,
                        document_version
                    ) DO NOTHING
                    """,
                    (user.id, document_type, version, client_ip_hash),
                )

            cur.execute(
                """
                INSERT INTO sessions (
                    user_id,
                    token_digest,
                    client_ip_hash,
                    expires_at
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    now() + make_interval(secs => %s)
                )
                """,
                (
                    user.id,
                    session_token_digest,
                    client_ip_hash,
                    session_ttl_seconds,
                ),
            )
            cur.execute(
                """
                INSERT INTO audit_events (user_id, event_type, metadata)
                VALUES (%s, %s, %s::jsonb)
                """,
                (
                    user.id,
                    "account_created" if created else "login_succeeded",
                    json.dumps({"method": "vkid", "identity_linked": linked}),
                ),
            )
            return user, created

    def refresh_session_digest(
        self,
        token_digest: bytes,
        *,
        session_ttl_seconds: int,
    ) -> UserRecord | None:
        """Validate an active VK ID session and extend its rolling expiry."""

        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE sessions AS s
                SET
                    last_seen_at = now(),
                    expires_at = now() + make_interval(secs => %s)
                FROM users AS u, vkid_identities AS v
                WHERE s.user_id = u.id
                  AND v.user_id = u.id
                  AND s.token_digest = %s
                  AND s.revoked_at IS NULL
                  AND s.expires_at > now()
                  AND u.status = 'active'
                RETURNING u.id, u.public_id, u.status, u.role
                """,
                (session_ttl_seconds, token_digest),
            )
            fetched = cur.fetchone()
            if fetched is None:
                return None
            return _user(cast(dict[str, Any], fetched))

    def revoke_session(self, token_digest: bytes) -> None:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE sessions
                SET revoked_at = COALESCE(revoked_at, now())
                WHERE token_digest = %s
                """,
                (token_digest,),
            )

    def delete_user_account(self, user_id: UUID) -> bool:
        """Permanently delete one authenticated user's account and linked data."""

        with self.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute(
                """
                SELECT vk_user_id
                FROM vkid_identities
                WHERE user_id = %s
                """,
                (user_id,),
            )
            identity = cur.fetchone()
            if identity is None:
                return False

            vk_user_id = str(cast(dict[str, Any], identity)["vk_user_id"])
            cur.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (vk_user_id,),
            )
            cur.execute(
                """
                SELECT u.id, u.public_id, u.status, u.role
                FROM users AS u
                JOIN vkid_identities AS v ON v.user_id = u.id
                WHERE u.id = %s
                  AND v.vk_user_id = %s
                FOR UPDATE
                """,
                (user_id, vk_user_id),
            )
            fetched = cur.fetchone()
            if fetched is None:
                return False

            user = _user(cast(dict[str, Any], fetched))
            if user.status != "active":
                raise PermissionError("account is not active")

            cur.execute(
                """
                INSERT INTO audit_events (user_id, event_type, metadata)
                VALUES (%s, 'self_account_deleted', '{"source":"settings"}'::jsonb)
                """,
                (user.id,),
            )
            cur.execute(
                """
                DELETE FROM users
                WHERE id = %s
                RETURNING id
                """,
                (user.id,),
            )
            return cur.fetchone() is not None

    def has_legal_versions(
        self,
        user_id: UUID,
        legal_versions: dict[str, str],
    ) -> bool:
        if not legal_versions or any(not version for version in legal_versions.values()):
            return False
        with self.pool.connection() as conn, conn.cursor() as cur:
            for document_type, version in legal_versions.items():
                cur.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM legal_acceptances
                        WHERE user_id = %s
                          AND document_type = %s
                          AND document_version = %s
                    ) AS accepted
                    """,
                    (user_id, document_type, version),
                )
                fetched = cur.fetchone()
                if fetched is None or not bool(cast(dict[str, Any], fetched)["accepted"]):
                    return False
        return True

    def tbank_connection(self, user_id: UUID) -> TBankConnectionRecord | None:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    user_id,
                    environment,
                    account_id,
                    account_name,
                    token_ciphertext,
                    verified_at,
                    updated_at
                FROM tbank_connection
                WHERE user_id = %s
                """,
                (user_id,),
            )
            fetched = cur.fetchone()
            if fetched is None:
                return None
            return _tbank_connection(cast(dict[str, Any], fetched))

    def upsert_tbank_connection(
        self,
        *,
        user_id: UUID,
        environment: str,
        account_id: str,
        account_name: str,
        encrypted_credential: bytes,
        terms_version: str,
    ) -> TBankConnectionRecord:
        with self.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tbank_connection (
                    user_id,
                    environment,
                    account_id,
                    account_name,
                    token_ciphertext
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    environment = EXCLUDED.environment,
                    account_id = EXCLUDED.account_id,
                    account_name = EXCLUDED.account_name,
                    token_ciphertext = EXCLUDED.token_ciphertext,
                    verified_at = now(),
                    updated_at = now()
                RETURNING
                    user_id,
                    environment,
                    account_id,
                    account_name,
                    token_ciphertext,
                    verified_at,
                    updated_at
                """,
                (
                    user_id,
                    environment,
                    account_id,
                    account_name,
                    encrypted_credential,
                ),
            )
            fetched = cur.fetchone()
            if fetched is None:
                raise RuntimeError("T-Bank connection upsert returned no row")
            record = _tbank_connection(cast(dict[str, Any], fetched))
            cur.execute(
                """
                INSERT INTO audit_events (user_id, event_type, metadata)
                VALUES (%s, 'tbank_connected', %s::jsonb)
                """,
                (
                    user_id,
                    json.dumps(
                        {
                            "environment": environment,
                            "terms_version": terms_version,
                        }
                    ),
                ),
            )
            return record

    def delete_tbank_connection(self, user_id: UUID) -> bool:
        with self.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute(
                """
                SELECT environment
                FROM tbank_connection
                WHERE user_id = %s
                FOR UPDATE
                """,
                (user_id,),
            )
            fetched = cur.fetchone()
            if fetched is None:
                return False
            row = cast(dict[str, Any], fetched)

            # Derived broker facts are retained only while the integration is
            # connected. The user-owned investment profile remains independent.
            cur.execute(
                "SELECT set_config('omnicio.user_id', %s, true)",
                (str(user_id),),
            )
            cur.execute("DELETE FROM broker_sync_state WHERE user_id = %s", (user_id,))
            cur.execute("DELETE FROM operation_observations WHERE user_id = %s", (user_id,))
            cur.execute("DELETE FROM portfolio_snapshots WHERE user_id = %s", (user_id,))
            cur.execute("DELETE FROM job_runs WHERE user_id = %s", (user_id,))

            cur.execute(
                """
                DELETE FROM tbank_connection
                WHERE user_id = %s
                """,
                (user_id,),
            )
            cur.execute(
                """
                INSERT INTO audit_events (user_id, event_type, metadata)
                VALUES (%s, 'tbank_disconnected', %s::jsonb)
                """,
                (
                    user_id,
                    json.dumps({"environment": str(row["environment"])}),
                ),
            )
            return True

    def support_user_by_public_id(self, public_id: int) -> UserRecord | None:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, public_id, status, role
                FROM users
                WHERE public_id = %s
                """,
                (public_id,),
            )
            fetched = cur.fetchone()
            if fetched is None:
                return None
            return _user(cast(dict[str, Any], fetched))

    def support_revoke_all_sessions(
        self,
        *,
        public_id: int,
        reason: str,
    ) -> UserRecord | None:
        with self.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            user = self._support_locked_user(cur, public_id)
            if user is None:
                return None

            cur.execute(
                """
                UPDATE sessions
                SET revoked_at = COALESCE(revoked_at, now())
                WHERE user_id = %s AND revoked_at IS NULL
                """,
                (user.id,),
            )
            cur.execute(
                """
                INSERT INTO audit_events (user_id, event_type, metadata)
                VALUES (%s, 'support_sessions_revoked', %s::jsonb)
                """,
                (user.id, json.dumps({"reason": reason})),
            )
            return user

    def support_change_status(
        self,
        *,
        public_id: int,
        target_status: str,
        allowed_from: frozenset[str],
        event_type: str,
        reason: str,
        revoke_sessions: bool,
    ) -> tuple[UserRecord, bool] | None:
        with self.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            user = self._support_locked_user(cur, public_id)
            if user is None:
                return None
            if user.status == target_status:
                return user, False
            if user.status not in allowed_from:
                raise PermissionError(
                    f"cannot change account from {user.status} to {target_status}"
                )

            cur.execute(
                """
                UPDATE users
                SET status = %s, updated_at = now()
                WHERE id = %s
                RETURNING id, public_id, status, role
                """,
                (target_status, user.id),
            )
            updated = cur.fetchone()
            if updated is None:
                raise RuntimeError("support status update returned no row")
            updated_user = _user(cast(dict[str, Any], updated))

            if revoke_sessions:
                cur.execute(
                    """
                    UPDATE sessions
                    SET revoked_at = COALESCE(revoked_at, now())
                    WHERE user_id = %s AND revoked_at IS NULL
                    """,
                    (user.id,),
                )

            cur.execute(
                """
                INSERT INTO audit_events (user_id, event_type, metadata)
                VALUES (%s, %s, %s::jsonb)
                """,
                (user.id, event_type, json.dumps({"reason": reason})),
            )
            return updated_user, True

    @staticmethod
    def _support_locked_user(cur: Any, public_id: int) -> UserRecord | None:
        cur.execute(
            """
            SELECT id, public_id, status, role
            FROM users
            WHERE public_id = %s
            FOR UPDATE
            """,
            (public_id,),
        )
        fetched = cur.fetchone()
        if fetched is None:
            return None
        return _user(cast(dict[str, Any], fetched))


def _user(row: dict[str, Any]) -> UserRecord:
    return UserRecord(
        id=row["id"],
        public_id=int(row["public_id"]),
        status=str(row["status"]),
        role=str(row["role"]),
    )


def _tbank_connection(row: dict[str, Any]) -> TBankConnectionRecord:
    return TBankConnectionRecord(
        user_id=row["user_id"],
        environment=str(row["environment"]),
        account_id=str(row["account_id"]),
        account_name=str(row["account_name"]),
        encrypted_credential=bytes(row["token_ciphertext"]),
        verified_at=row["verified_at"],
        updated_at=row["updated_at"],
    )
