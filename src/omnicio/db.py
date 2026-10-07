"""PostgreSQL persistence boundary for authentication."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from threading import BoundedSemaphore
from typing import Any, cast
from uuid import UUID

from psycopg import Error as DatabaseError
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_ADVISORY_LOCK_SQL = "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))"
_SET_USER_CONTEXT_SQL = "SELECT set_config('omnicio.user_id', %s, true)"

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


class ActiveLiveExecutionError(RuntimeError):
    """Raised when cleanup would race with an unfinished production execution."""


class BrokerConnectionConflict(ValueError):
    """A connected account must be explicitly disconnected before replacement."""


def live_execution_lock_key(user_id: UUID) -> str:
    """Return the shared transaction-lock key for live execution and cleanup."""

    return f"portfolio-live-execution:{user_id}"


class Database:
    """Thin persistence adapter for authentication state."""

    def __init__(self, database_url: str) -> None:
        # Reserve at least six of the eight shared connections for ordinary and
        # nested reads. Cross-process per-owner exclusion remains in PostgreSQL.
        self._strategy_read_slots = BoundedSemaphore(2)
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

    @contextmanager
    def strategy_assessment_slot(self, user_id: UUID) -> Iterator[bool]:
        """Bound shared-pool lock holders before acquiring a database connection."""
        if not self._strategy_read_slots.acquire(blocking=False):
            yield False
            return
        try:
            with self._strategy_assessment_owner_slot(user_id) as admitted:
                yield admitted
        finally:
            self._strategy_read_slots.release()

    @contextmanager
    def _strategy_assessment_owner_slot(self, user_id: UUID) -> Iterator[bool]:
        """Serialize account reads across processes, with a durable start cooldown.

        A dedicated session lock spans the network work; no transaction or
        financial-execution lock does. Closing a failed connection discards its
        session locks instead of returning a locked connection to the pool.
        """
        name = f"strategy-account-assessment:{user_id}"
        with self.pool.connection() as conn:
            locked = False
            try:
                with conn.transaction(), conn.cursor() as cur:
                    cur.execute(_SET_USER_CONTEXT_SQL, (str(user_id),))
                    cur.execute(
                        "SELECT pg_try_advisory_lock(hashtextextended(%s, 0)) AS locked",
                        (name,),
                    )
                    row = cur.fetchone()
                    locked = row is not None and bool(cast(dict[str, Any], row)["locked"])
                    admitted = False
                    if locked:
                        cur.execute(
                            "UPDATE strategy_drafts SET next_assessment_at = "
                            "clock_timestamp() + interval '10 seconds' "
                            "WHERE user_id = %s AND next_assessment_at <= clock_timestamp() "
                            "RETURNING user_id", (user_id,),
                        )
                        admitted = cur.fetchone() is not None
                yield admitted
            finally:
                if locked:
                    try:
                        with conn.transaction(), conn.cursor() as cur:
                            cur.execute(
                                "SELECT pg_advisory_unlock(hashtextextended(%s, 0)) AS unlocked",
                                (name,),
                            )
                            row = cur.fetchone()
                            if row is None or not cast(dict[str, Any], row)["unlocked"]:
                                raise RuntimeError("strategy_assessment_lock_not_released")
                    except (DatabaseError, RuntimeError):
                        # Cleanup, not error suppression: closing is necessary to
                        # release a session lock if the database operation failed.
                        conn.close()
                        raise

    def healthcheck(self) -> bool:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    to_regclass('public.users') IS NOT NULL
                    AND to_regclass('public.sessions') IS NOT NULL
                    AND to_regclass('public.legal_acceptances') IS NOT NULL
                    AND to_regclass('public.vkid_identities') IS NOT NULL
                    AND to_regclass('public.tid_identities') IS NOT NULL
                    AND to_regclass('public.oauth_flow_claims') IS NOT NULL
                    AND to_regclass('public.workspace_preferences') IS NOT NULL
                    AND to_regclass('public.investment_goals') IS NOT NULL
                    AND to_regclass('public.workspace_events') IS NOT NULL
                    AND to_regclass('public.tbank_connection') IS NOT NULL
                    AND to_regclass('public.instrument_catalog') IS NOT NULL
                    AND to_regclass('public.account_instrument_access') IS NOT NULL
                    AND to_regclass('public.issuer_groups') IS NOT NULL
                    AND to_regclass('public.issuers') IS NOT NULL
                    AND to_regclass('public.instrument_issuer_map') IS NOT NULL
                    AND to_regclass('public.investment_profile_versions') IS NOT NULL
                    AND to_regclass('public.job_runs') IS NOT NULL
                    AND EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conrelid = to_regclass('public.job_runs')
                          AND conname = 'job_runs_user_id_job_type_scheduled_for_key'
                          AND contype = 'u'
                    )
                    AND to_regclass('public.job_runs_refresh_active_idx') IS NOT NULL
                    AND to_regclass('public.job_runs_refresh_requested_idx') IS NOT NULL
                    AND EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = 'public' AND table_name = 'job_runs'
                          AND column_name = 'requested_at' AND is_nullable = 'NO'
                    )
                    AND EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = 'public' AND table_name = 'job_runs'
                          AND column_name = 'scheduled_for' AND is_nullable = 'YES'
                    )
                    AND EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conrelid = to_regclass('public.job_runs')
                          AND conname = 'job_runs_schedule_kind_consistent'
                          AND contype = 'c' AND convalidated
                    )
                    AND to_regclass('public.portfolio_snapshots') IS NOT NULL
                    AND to_regclass('public.portfolio_snapshot_positions') IS NOT NULL
                    AND to_regclass('public.operation_observations') IS NOT NULL
                    AND to_regclass('public.broker_sync_state') IS NOT NULL
                    AND to_regclass('public.source_documents') IS NOT NULL
                    AND to_regclass('public.source_retrievals') IS NOT NULL
                    AND to_regclass('public.source_facts') IS NOT NULL
                    AND to_regclass('public.payout_events') IS NOT NULL
                    AND to_regclass('public.portfolio_risk_assessments') IS NOT NULL
                    AND to_regclass('public.balancing_policy_versions') IS NOT NULL
                    AND to_regclass('public.strategy_drafts') IS NOT NULL
                    AND EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = 'public' AND table_name = 'strategy_drafts'
                          AND column_name = 'next_assessment_at'
                    )
                    AND to_regclass('public.portfolio_proposals') IS NOT NULL
                    AND to_regclass('public.portfolio_proposal_actions') IS NOT NULL
                    AND to_regclass('public.portfolio_execution_runs') IS NOT NULL
                    AND to_regclass('public.portfolio_execution_legs') IS NOT NULL
                    AND to_regclass('public.portfolio_execution_events') IS NOT NULL
                    AND to_regclass('public.portfolio_live_execution_mandates') IS NOT NULL
                    AND EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'users'
                          AND column_name = 'role'
                    )
                    AND (
                        SELECT count(*) = 8
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'instrument_catalog'
                          AND column_name = ANY (
                              ARRAY[
                                  'nominal_value',
                                  'nominal_currency',
                                  'maturity_date',
                                  'floating_coupon',
                                  'perpetual',
                                  'amortization',
                                  'subordinated',
                                  'liquidity'
                              ]
                          )
                    )
                    AND (
                        SELECT count(*) = 3
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'portfolio_proposals'
                          AND column_name = ANY (
                              ARRAY[
                                  'account_id',
                                  'created_session_digest',
                                  'proposal_hash'
                              ]
                          )
                    )
                    AND (
                        SELECT count(*) = 3
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'portfolio_proposal_actions'
                          AND column_name = ANY (
                              ARRAY[
                                  'session_digest',
                                  'user_reason',
                                  'deferred_until'
                              ]
                          )
                    )
                    AND (
                        SELECT count(*) = 19
                        FROM pg_class AS c
                        JOIN pg_namespace AS n ON n.oid = c.relnamespace
                        WHERE n.nspname = 'public'
                          AND c.relname = ANY (
                              ARRAY[
                                  'account_instrument_access',
                                  'investment_profile_versions',
                                  'job_runs',
                                  'portfolio_snapshots',
                                  'portfolio_snapshot_positions',
                                  'operation_observations',
                                  'broker_sync_state',
                                  'portfolio_risk_assessments',
                                  'balancing_policy_versions',
                                  'portfolio_proposals',
                                  'portfolio_proposal_actions',
                                  'portfolio_execution_runs',
                                  'portfolio_execution_legs',
                                  'portfolio_execution_events',
                                  'portfolio_live_execution_mandates',
                                  'strategy_drafts',
                                  'workspace_preferences',
                                  'investment_goals',
                                  'workspace_events'
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
        self, *, vk_user_id: str, **context: Any,
    ) -> tuple[UserRecord, bool]:
        return self._complete_identity_login(provider="vkid", subject=vk_user_id, **context)

    def complete_tid_login(
        self, *, tid_subject: str, **context: Any,
    ) -> tuple[UserRecord, bool]:
        return self._complete_identity_login(provider="tid", subject=tid_subject, **context)

    def claim_oauth_flow(self, state_digest: bytes, provider: str, ttl_seconds: int) -> bool:
        """Consume a verified browser-bound state exactly once across processes."""
        if provider not in {"vkid", "tid"} or len(state_digest) != 32:
            raise ValueError("oauth_flow_invalid")
        with self.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM oauth_flow_claims WHERE expires_at < now()")
            cur.execute(
                "INSERT INTO oauth_flow_claims (state_digest, provider, expires_at) "
                "VALUES (%s, %s, now() + make_interval(secs => %s)) "
                "ON CONFLICT (state_digest) DO NOTHING RETURNING state_digest",
                (state_digest, provider, ttl_seconds),
            )
            return cur.fetchone() is not None

    def _complete_identity_login(
        self, *, provider: str, subject: str,
        client_ip_hash: bytes, session_token_digest: bytes, session_ttl_seconds: int,
        legal_versions: dict[str, str], registration_enabled: bool,
        registration_max_users: int, link_user_id: UUID | None = None,
        link_session_digest: bytes | None = None,
    ) -> tuple[UserRecord, bool]:
        """Resolve a verified identity; linking never guesses a tenant from email."""
        lookup = {
            "vkid": "SELECT u.id, u.public_id, u.status, u.role FROM users AS u "
                    "JOIN vkid_identities AS v ON v.user_id = u.id "
                    "WHERE v.vk_user_id = %s FOR UPDATE OF u",
            "tid": "SELECT u.id, u.public_id, u.status, u.role FROM users AS u "
                   "JOIN tid_identities AS v ON v.user_id = u.id "
                   "WHERE v.tid_subject = %s FOR UPDATE OF u",
        }
        insert_identity = {
            "vkid": "INSERT INTO vkid_identities (user_id, vk_user_id, verified_at) "
                    "VALUES (%s, %s, now())",
            "tid": "INSERT INTO tid_identities (user_id, tid_subject, verified_at) "
                   "VALUES (%s, %s, now())",
        }
        if provider not in lookup:
            raise ValueError("oauth_provider_invalid")
        if (link_user_id is None) != (link_session_digest is None):
            raise PermissionError("oauth_link_session_required")
        with self.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            if link_user_id is not None:
                cur.execute(_ADVISORY_LOCK_SQL, (live_execution_lock_key(link_user_id),))
            cur.execute(_ADVISORY_LOCK_SQL, (f"identity:{provider}:{subject}",))
            if link_user_id is not None:
                cur.execute(
                    "SELECT 1 FROM sessions WHERE user_id = %s AND token_digest = %s "
                    "AND revoked_at IS NULL AND expires_at > now() FOR UPDATE",
                    (link_user_id, link_session_digest),
                )
                if cur.fetchone() is None:
                    raise PermissionError("oauth_link_session_expired")
            cur.execute(lookup[provider], (subject,))
            fetched = cur.fetchone()
            user, created = self._identity_login_user(
                cur, fetched, provider=provider, link_user_id=link_user_id,
                registration_enabled=registration_enabled,
                registration_max_users=registration_max_users,
            )
            linked = fetched is None
            if linked:
                cur.execute(insert_identity[provider], (user.id, subject))
            if user.status != "active":
                raise PermissionError("account is not active")
            for document_type, version in legal_versions.items():
                cur.execute(
                    "INSERT INTO legal_acceptances "
                    "(user_id, document_type, document_version, client_ip_hash) "
                    "VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (user_id, document_type, document_version) DO NOTHING",
                    (user.id, document_type, version, client_ip_hash),
                )
            cur.execute(
                "INSERT INTO sessions (user_id, token_digest, client_ip_hash, expires_at) "
                "VALUES (%s, %s, %s, now() + make_interval(secs => %s))",
                (user.id, session_token_digest, client_ip_hash, session_ttl_seconds),
            )
            cur.execute(
                "INSERT INTO audit_events (user_id, event_type, metadata) "
                "VALUES (%s, %s, %s::jsonb)",
                (user.id, "account_created" if created else "login_succeeded",
                 json.dumps({"method": provider, "identity_linked": linked})),
            )
            return user, created

    @staticmethod
    def _identity_login_user(
        cur: Any, fetched: Any, *, provider: str, link_user_id: UUID | None,
        registration_enabled: bool, registration_max_users: int,
    ) -> tuple[UserRecord, bool]:
        if fetched is not None:
            user = _user(cast(dict[str, Any], fetched))
            if link_user_id is not None and user.id != link_user_id:
                raise PermissionError("identity_already_linked")
            return user, False
        if link_user_id is not None:
            return Database._active_identity_link_target(cur, provider, link_user_id), False
        return Database._register_identity_user(
            cur, registration_enabled=registration_enabled,
            registration_max_users=registration_max_users,
        ), True

    @staticmethod
    def _active_identity_link_target(cur: Any, provider: str, user_id: UUID) -> UserRecord:
        cur.execute(
            "SELECT id, public_id, status, role FROM users "
            "WHERE id = %s AND status = 'active' FOR UPDATE", (user_id,),
        )
        active = cur.fetchone()
        if active is None:
            raise PermissionError("link_account_inactive")
        user = _user(cast(dict[str, Any], active))
        # Each provider is linked once. Do not silently replace it.
        existing_query = (
            "SELECT 1 FROM vkid_identities WHERE user_id = %s" if provider == "vkid"
            else "SELECT 1 FROM tid_identities WHERE user_id = %s"
        )
        cur.execute(existing_query, (user.id,))
        if cur.fetchone() is not None:
            raise PermissionError("provider_already_linked")
        return user

    @staticmethod
    def _register_identity_user(
        cur: Any, *, registration_enabled: bool, registration_max_users: int,
    ) -> UserRecord:
        if not registration_enabled:
            raise RegistrationClosedError("registration is closed")
        cur.execute(_ADVISORY_LOCK_SQL, ("omnicio-registration-capacity",))
        cur.execute("SELECT count(*) AS total FROM users WHERE status <> 'deleted'")
        count = cur.fetchone()
        if count is None:
            raise RuntimeError("registration_capacity_unavailable")
        if int(cast(dict[str, Any], count)["total"]) >= registration_max_users:
            raise RegistrationCapacityError("registration capacity reached")
        cur.execute("INSERT INTO users DEFAULT VALUES RETURNING id, public_id, status, role")
        inserted = cur.fetchone()
        if inserted is None:
            raise RuntimeError("user_creation_unavailable")
        return _user(cast(dict[str, Any], inserted))

    def identity_providers(self, user_id: UUID) -> list[str]:
        """Expose provider names only, never external identifiers."""
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT 'vkid' AS provider FROM vkid_identities WHERE user_id = %s "
                "UNION ALL SELECT 'tid' AS provider FROM tid_identities WHERE user_id = %s",
                (user_id, user_id),
            )
            return [str(row["provider"]) for row in cast(list[dict[str, Any]], cur.fetchall())]

    def refresh_session_digest(
        self,
        token_digest: bytes,
        *,
        session_ttl_seconds: int,
    ) -> UserRecord | None:
        """Validate an active identity-backed session and extend its rolling expiry."""

        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE sessions AS s
                SET
                    last_seen_at = now(),
                    expires_at = now() + make_interval(secs => %s)
                FROM users AS u
                WHERE s.user_id = u.id
                  AND (EXISTS (SELECT 1 FROM vkid_identities AS v WHERE v.user_id = u.id)
                       OR EXISTS (SELECT 1 FROM tid_identities AS t WHERE t.user_id = u.id))
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

    def recent_activity(self, user_id: UUID, *, limit: int = 20) -> list[dict[str, object]]:
        """Expose only allowlisted event kinds and times for the session owner."""
        if not 1 <= limit <= 50:
            raise ValueError("activity limit must be between 1 and 50")
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT event_type, created_at
                FROM audit_events
                WHERE user_id = %s
                  AND event_type = ANY (%s)
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                (user_id, [
                    "account_created", "login_succeeded", "tbank_connected",
                    "tbank_disconnected", "investment_profile_saved",
                    "balancing_policy_saved", "support_sessions_revoked",
                ], limit),
            )
            rows = cast(list[dict[str, Any]], cur.fetchall())
            return [
                {"event_type": row["event_type"], "created_at": row["created_at"]}
                for row in rows
            ]

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
                _ADVISORY_LOCK_SQL,
                (live_execution_lock_key(user_id),),
            )
            cur.execute(
                """
                SELECT 'vkid' AS provider, vk_user_id AS subject
                FROM vkid_identities WHERE user_id = %s
                UNION ALL
                SELECT 'tid' AS provider, tid_subject AS subject
                FROM tid_identities WHERE user_id = %s
                ORDER BY provider, subject
                """,
                (user_id, user_id),
            )
            identities = cast(list[dict[str, Any]], cur.fetchall())
            if not identities:
                return False
            for identity in identities:
                cur.execute(
                    _ADVISORY_LOCK_SQL,
                    (f"identity:{identity['provider']}:{identity['subject']}",),
                )
            cur.execute(
                """
                SELECT u.id, u.public_id, u.status, u.role
                FROM users AS u
                WHERE u.id = %s
                FOR UPDATE
                """,
                (user_id,),
            )
            fetched = cur.fetchone()
            if fetched is None:
                return False

            user = _user(cast(dict[str, Any], fetched))
            if user.status != "active":
                raise PermissionError("account is not active")

            cur.execute(
                _SET_USER_CONTEXT_SQL,
                (str(user.id),),
            )
            cur.execute(
                """
                SELECT 1
                FROM portfolio_execution_runs
                WHERE user_id = %s
                  AND mode = 'live'
                  AND status IN ('created', 'running', 'reconciling')
                LIMIT 1
                FOR UPDATE
                """,
                (user.id,),
            )
            if cur.fetchone() is not None:
                raise ActiveLiveExecutionError(
                    "active live execution must be reconciled before account deletion"
                )

            cur.execute(
                """
                INSERT INTO audit_events (user_id, event_type, metadata)
                VALUES (%s, 'self_account_deleted', '{"source":"settings"}'::jsonb)
                """,
                (user.id,),
            )
            cur.execute(
                "SELECT set_config('omnicio.financial_cleanup', 'account_delete', true)"
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
            cur.execute(_ADVISORY_LOCK_SQL, (live_execution_lock_key(user_id),))
            cur.execute(_SET_USER_CONTEXT_SQL, (str(user_id),))
            cur.execute(
                "SELECT id FROM users WHERE id = %s AND status = 'active' FOR UPDATE",
                (user_id,),
            )
            if cur.fetchone() is None:
                raise BrokerConnectionConflict("broker_account_unavailable")
            cur.execute(
                "SELECT account_id, environment FROM tbank_connection WHERE user_id = %s",
                (user_id,),
            )
            current = cast(dict[str, Any] | None, cur.fetchone())
            if current is not None and (
                current["account_id"] != account_id or current["environment"] != environment
            ):
                raise BrokerConnectionConflict("broker_disconnect_required")
            cur.execute(
                """
                SELECT 1 FROM portfolio_execution_runs
                WHERE user_id = %s AND mode = 'live'
                  AND status IN ('created', 'running', 'reconciling')
                LIMIT 1
                """,
                (user_id,),
            )
            if cur.fetchone() is not None:
                raise ActiveLiveExecutionError(
                    "active live execution blocks credential replacement"
                )
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
                _ADVISORY_LOCK_SQL,
                (live_execution_lock_key(user_id),),
            )
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
                _SET_USER_CONTEXT_SQL,
                (str(user_id),),
            )
            cur.execute(
                "SELECT set_config('omnicio.financial_cleanup', 'broker_disconnect', true)"
            )
            cur.execute(
                """
                SELECT 1
                FROM portfolio_execution_runs
                WHERE user_id = %s
                  AND mode = 'live'
                  AND status IN ('created', 'running', 'reconciling')
                LIMIT 1
                FOR UPDATE
                """,
                (user_id,),
            )
            if cur.fetchone() is not None:
                raise ActiveLiveExecutionError(
                    "active live execution must be reconciled before broker disconnect"
                )
            cur.execute(
                """
                UPDATE portfolio_live_execution_mandates
                SET revoked_at = COALESCE(revoked_at, now())
                WHERE user_id = %s
                  AND revoked_at IS NULL
                """,
                (user_id,),
            )
            cur.execute("DELETE FROM broker_sync_state WHERE user_id = %s", (user_id,))
            cur.execute("DELETE FROM account_instrument_access WHERE user_id = %s", (user_id,))
            cur.execute("DELETE FROM operation_observations WHERE user_id = %s", (user_id,))
            cur.execute("DELETE FROM portfolio_snapshots WHERE user_id = %s", (user_id,))
            cur.execute(
                """
                DELETE FROM job_runs
                WHERE user_id = %s
                  AND job_type IN ('portfolio_daily', 'portfolio_refresh')
                """,
                (user_id,),
            )

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
