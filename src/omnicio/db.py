"""PostgreSQL persistence boundary for authentication."""

from __future__ import annotations

import hmac
import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import BoundedSemaphore
from typing import Any, cast
from uuid import UUID

from psycopg import Error as DatabaseError
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .schema import READINESS_QUERY
from .security import EMAIL_CODE_MAX_ATTEMPTS, EMAIL_CODE_TTL_SECONDS, EMAIL_RESEND_SECONDS

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
            cur.execute(READINESS_QUERY)
            fetched = cur.fetchone()
            if fetched is None:
                return False
            row = cast(dict[str, Any], fetched)
            return bool(row["ready"])

    def consume_auth_budget(self, buckets: list[tuple[bytes, int, int]]) -> bool:
        """Durable fixed windows shared by workers; denied attempts still count."""
        allowed = True
        with self.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            for digest, limit, window_seconds in sorted(buckets):
                cur.execute(
                    "INSERT INTO email_auth_rate_limits "
                    "(bucket_digest, expires_at, attempts) "
                    "VALUES (%s, clock_timestamp() + make_interval(secs => %s), 1) "
                    "ON CONFLICT (bucket_digest) DO UPDATE SET "
                    "attempts = CASE WHEN email_auth_rate_limits.expires_at <= clock_timestamp() "
                    "THEN 1 ELSE LEAST(email_auth_rate_limits.attempts + 1, 1000000000) END, "
                    "window_started_at = CASE WHEN email_auth_rate_limits.expires_at "
                    "<= clock_timestamp() THEN clock_timestamp() "
                    "ELSE email_auth_rate_limits.window_started_at END, "
                    "expires_at = CASE WHEN email_auth_rate_limits.expires_at <= clock_timestamp() "
                    "THEN EXCLUDED.expires_at ELSE email_auth_rate_limits.expires_at END "
                    "RETURNING attempts", (digest, window_seconds),
                )
                row = cast(dict[str, Any], cur.fetchone())
                allowed = int(row["attempts"]) <= limit and allowed
            cur.execute(
                "DELETE FROM email_auth_rate_limits WHERE bucket_digest IN "
                "(SELECT bucket_digest FROM email_auth_rate_limits WHERE expires_at "
                "< clock_timestamp() - interval '1 day' LIMIT 100 FOR UPDATE SKIP LOCKED)"
            )
        return allowed

    def email_identity(self, email: str) -> dict[str, Any] | None:
        """Internal credential lookup, never serialized at the HTTP boundary."""
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT e.user_id, e.email, e.password_hash, e.password_version "
                "FROM email_identities e JOIN users u ON u.id = e.user_id "
                "WHERE e.email = %s AND u.status = 'active'", (email,),
            )
            return cast(dict[str, Any] | None, cur.fetchone())

    def email_identity_status(self, user_id: UUID) -> dict[str, Any]:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT email FROM email_identities WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
            email = cast(dict[str, Any], row)["email"] if row is not None else None
            return {"email": email, "email_verified": row is not None,
                    "migration_required": row is None,
                    "providers": ["email"] if row is not None else []}

    def create_email_challenge(
        self, *, challenge_id: UUID, purpose: str, email: str, password_hash: str | None,
        flow_digest: bytes, code_digest: bytes, client_ip_hash: bytes,
        legal_versions: dict[str, str], delivery_ciphertext: bytes,
        user_id: UUID | None = None, enrollment_session_digest: bytes | None = None,
    ) -> None:
        if purpose not in {"register", "enroll", "reset"}:
            raise ValueError("auth_purpose_invalid")
        with self.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            if purpose == "enroll":
                if user_id is None or enrollment_session_digest is None:
                    raise PermissionError("enrollment_session_required")
                self._active_session(cur, user_id, enrollment_session_digest)
                cur.execute("SELECT 1 FROM email_identities WHERE user_id = %s", (user_id,))
                if cur.fetchone() is not None:
                    raise ValueError("email_already_enrolled")
            cur.execute(_ADVISORY_LOCK_SQL, (f"email-identity:{email}",))
            cur.execute(
                "SELECT e.user_id, e.password_version, u.status FROM email_identities e "
                "JOIN users u ON u.id = e.user_id WHERE e.email = %s", (email,),
            )
            identity = cast(dict[str, Any] | None, cur.fetchone())
            suppressed = identity is not None if purpose != "reset" else (
                identity is None or identity["status"] != "active"
            )
            if purpose == "reset" and not suppressed and identity is not None:
                user_id = identity["user_id"]
            # New requests cancel older codes and their queued deliveries. No
            # password or existing identity is changed until successful proof.
            cur.execute(
                "UPDATE email_auth_challenges SET consumed_at = clock_timestamp(), "
                "delivery_ciphertext = NULL WHERE email = %s AND purpose = %s "
                "AND consumed_at IS NULL", (email, purpose),
            )
            cur.execute(
                "INSERT INTO email_auth_challenges "
                "(id, purpose, email, user_id, enrollment_session_digest, password_hash, "
                "password_version, flow_digest, code_digest, client_ip_hash, legal_versions, "
                "attempts_remaining, suppressed, expires_at, resend_at, delivery_ciphertext, "
                "delivery_state) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s, "
                "clock_timestamp() + make_interval(secs => %s), "
                "clock_timestamp() + make_interval(secs => %s),%s,%s)",
                (challenge_id, purpose, email, user_id, enrollment_session_digest, password_hash,
                 identity["password_version"] if identity else None, flow_digest, code_digest,
                 client_ip_hash, json.dumps(legal_versions), EMAIL_CODE_MAX_ATTEMPTS, suppressed,
                 EMAIL_CODE_TTL_SECONDS, EMAIL_RESEND_SECONDS,
                 None if suppressed else delivery_ciphertext,
                 "suppressed" if suppressed else "pending"),
            )

    def email_challenge(self, challenge_id: UUID, flow_digest: bytes) -> dict[str, Any] | None:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, purpose, expires_at FROM email_auth_challenges "
                "WHERE id = %s AND flow_digest = %s AND consumed_at IS NULL "
                "AND expires_at > clock_timestamp() AND attempts_remaining > 0",
                (challenge_id, flow_digest),
            )
            return cast(dict[str, Any] | None, cur.fetchone())

    def resend_email_challenge(
        self, challenge_id: UUID, flow_digest: bytes, code_digest: bytes,
        delivery_ciphertext: bytes,
    ) -> int | None:
        with self.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute(
                "UPDATE email_auth_challenges SET code_digest = %s, "
                "delivery_ciphertext = CASE WHEN suppressed THEN NULL ELSE %s END, "
                "delivery_state = CASE WHEN suppressed THEN 'suppressed' ELSE 'pending' END, "
                "delivery_attempts = 0, next_delivery_at = clock_timestamp(), "
                "resend_at = clock_timestamp() + make_interval(secs => %s) "
                "WHERE id = %s AND flow_digest = %s AND consumed_at IS NULL "
                "AND expires_at > clock_timestamp() AND attempts_remaining > 0 "
                "AND resend_at <= clock_timestamp() "
                "RETURNING CEIL(EXTRACT(epoch FROM (expires_at - clock_timestamp()))) AS ttl",
                (code_digest, delivery_ciphertext, EMAIL_RESEND_SECONDS, challenge_id, flow_digest),
            )
            row = cur.fetchone()
            return int(cast(dict[str, Any], row)["ttl"]) if row is not None else None

    @staticmethod
    def _insert_email_session(
        cur: Any, user_id: UUID, *, token_digest: bytes, client_ip_hash: bytes,
        session_ttl_seconds: int,
    ) -> None:
        cur.execute(
            "INSERT INTO sessions (user_id, token_digest, client_ip_hash, expires_at, "
            "authenticated_provider, authenticated_at) "
            "VALUES (%s, %s, %s, now() + make_interval(secs => %s), 'email', now())",
            (user_id, token_digest, client_ip_hash, session_ttl_seconds),
        )

    def complete_email_login(
        self, identity: dict[str, Any], *, token_digest: bytes, client_ip_hash: bytes,
        session_ttl_seconds: int,
    ) -> UserRecord | None:
        with self.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            user_id = identity["user_id"]
            cur.execute(_ADVISORY_LOCK_SQL, (live_execution_lock_key(user_id),))
            cur.execute(
                "SELECT u.id, u.public_id, u.status, u.role FROM users u "
                "JOIN email_identities e ON e.user_id = u.id "
                "WHERE u.id = %s AND u.status = 'active' AND e.email = %s "
                "AND e.password_hash = %s AND e.password_version = %s FOR UPDATE OF u, e",
                (user_id, identity["email"], identity["password_hash"],
                 identity["password_version"]),
            )
            row = cur.fetchone()
            if row is None:
                return None
            user = _user(cast(dict[str, Any], row))
            self._insert_email_session(cur, user.id, token_digest=token_digest,
                                       client_ip_hash=client_ip_hash,
                                       session_ttl_seconds=session_ttl_seconds)
            cur.execute(
                "INSERT INTO audit_events (user_id, event_type, metadata) "
                "VALUES (%s, 'login_succeeded', '{\"method\":\"email\"}'::jsonb)", (user.id,),
            )
            self._prune_sessions(cur, user.id)
            return user

    def consume_email_challenge(
        self, *, challenge_id: UUID, flow_digest: bytes, code_digest: bytes,
        purpose: str, client_ip_hash: bytes, legal_versions: dict[str, str],
        token_digest: bytes, session_ttl_seconds: int,
        enrollment_session_digest: bytes | None = None, password_hash: str | None = None,
    ) -> tuple[UserRecord, bool] | None:
        """Proof, identity creation/password change, and session mutation are atomic."""
        with self.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            # Resolve only lock keys before taking a row lock. Enrollment requests
            # and account deletion lock tenant -> email -> challenge in this order.
            cur.execute(
                "SELECT user_id, email FROM email_auth_challenges "
                "WHERE id = %s AND flow_digest = %s AND purpose = %s",
                (challenge_id, flow_digest, purpose),
            )
            context = cast(dict[str, Any] | None, cur.fetchone())
            if context is None:
                return None
            if context["user_id"] is not None:
                cur.execute(_ADVISORY_LOCK_SQL, (live_execution_lock_key(context["user_id"]),))
            cur.execute(_ADVISORY_LOCK_SQL, (f"email-identity:{context['email']}",))
            cur.execute(
                "SELECT * FROM email_auth_challenges WHERE id = %s AND flow_digest = %s "
                "AND purpose = %s AND consumed_at IS NULL AND expires_at > clock_timestamp() "
                "FOR UPDATE", (challenge_id, flow_digest, purpose),
            )
            row = cast(dict[str, Any] | None, cur.fetchone())
            if row is None or row["attempts_remaining"] <= 0:
                return None
            if not hmac.compare_digest(bytes(row["code_digest"]), code_digest):
                cur.execute(
                    "UPDATE email_auth_challenges SET attempts_remaining = attempts_remaining - 1, "
                    "delivery_ciphertext = CASE WHEN attempts_remaining = 1 "
                    "THEN NULL ELSE delivery_ciphertext END "
                    "WHERE id = %s", (challenge_id,),
                )
                return None  # Returning commits the failed attempt; raising would roll it back.
            cur.execute(
                "UPDATE email_auth_challenges SET consumed_at = clock_timestamp(), "
                "delivery_ciphertext = NULL WHERE id = %s", (challenge_id,),
            )
            if row["suppressed"] or (
                purpose != "reset" and row["legal_versions"] != legal_versions
            ):
                return None
            if purpose == "reset":
                user = self._reset_email_password(cur, row, password_hash)
            else:
                user = self._enroll_email_identity(cur, row, enrollment_session_digest)
            if user is None:
                return None
            cur.execute(
                "UPDATE email_auth_challenges SET user_id = %s WHERE id = %s",
                (user.id, challenge_id),
            )
            created = purpose == "register"
            if purpose != "reset":
                for document_type, version in legal_versions.items():
                    cur.execute(
                        "INSERT INTO legal_acceptances "
                        "(user_id, document_type, document_version, client_ip_hash) "
                        "VALUES (%s, %s, %s, %s) ON CONFLICT "
                        "(user_id, document_type, document_version) DO NOTHING",
                        (user.id, document_type, version, client_ip_hash),
                    )
                self._insert_email_session(cur, user.id, token_digest=token_digest,
                                           client_ip_hash=client_ip_hash,
                                           session_ttl_seconds=session_ttl_seconds)
            cur.execute(
                "INSERT INTO audit_events (user_id, event_type, metadata) "
                "VALUES (%s, %s, '{\"method\":\"email\"}'::jsonb)",
                (user.id, {
                    "register": "account_created", "reset": "password_reset",
                    "enroll": "email_enrolled",
                }[purpose]),
            )
            return user, created

    @staticmethod
    def _enroll_email_identity(
        cur: Any, row: dict[str, Any], session_token_digest: bytes | None,
    ) -> UserRecord | None:
        if row["purpose"] == "enroll":
            original = bytes(row["enrollment_session_digest"])
            if session_token_digest is None or not hmac.compare_digest(
                original, session_token_digest,
            ):
                return None
            Database._active_session(cur, row["user_id"], original)
            cur.execute("SELECT 1 FROM email_identities WHERE user_id = %s", (row["user_id"],))
            if cur.fetchone() is not None:
                return None
        cur.execute("SELECT 1 FROM email_identities WHERE email = %s", (row["email"],))
        if cur.fetchone() is not None:
            return None  # Never attach a new email request to an existing account.
        if row["purpose"] == "register":
            cur.execute("INSERT INTO users DEFAULT VALUES RETURNING id, public_id, status, role")
        else:
            cur.execute(
                "SELECT id, public_id, status, role FROM users WHERE id = %s AND status = 'active'",
                (row["user_id"],),
            )
        fetched = cur.fetchone()
        if fetched is None:
            return None
        user = _user(cast(dict[str, Any], fetched))
        cur.execute(
            "INSERT INTO email_identities (user_id, email, password_hash) VALUES (%s, %s, %s)",
            (user.id, row["email"], row["password_hash"]),
        )
        if row["purpose"] == "enroll":
            cur.execute(
                "UPDATE sessions SET revoked_at = clock_timestamp() "
                "WHERE user_id = %s AND revoked_at IS NULL", (user.id,),
            )
        return user

    @staticmethod
    def _reset_email_password(
        cur: Any, row: dict[str, Any], password_hash: str | None,
    ) -> UserRecord | None:
        if password_hash is None:
            return None
        cur.execute(
            "SELECT u.id, u.public_id, u.status, u.role FROM users u JOIN email_identities e "
            "ON e.user_id = u.id WHERE u.id = %s AND u.status = 'active' AND e.email = %s "
            "AND e.password_version = %s FOR UPDATE OF u, e",
            (row["user_id"], row["email"], row["password_version"]),
        )
        fetched = cur.fetchone()
        if fetched is None:
            return None
        user = _user(cast(dict[str, Any], fetched))
        cur.execute(
            "UPDATE email_identities SET password_hash = %s, "
            "password_version = password_version + 1, "
            "password_changed_at = clock_timestamp() WHERE user_id = %s", (password_hash, user.id),
        )
        cur.execute(
            "UPDATE sessions SET revoked_at = clock_timestamp() "
            "WHERE user_id = %s AND revoked_at IS NULL", (user.id,),
        )
        cur.execute(
            "UPDATE email_auth_challenges SET consumed_at = clock_timestamp(), "
            "delivery_ciphertext = NULL WHERE email = %s AND consumed_at IS NULL", (row["email"],),
        )
        return user

    def claim_email_delivery(self, *, delivery_enabled: bool = True) -> dict[str, Any] | None:
        with self.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            # A crashed sender may have reached SMTP DATA. Do not automatically
            # repeat that ambiguous attempt; the user can request a fresh code.
            cur.execute(
                "UPDATE email_auth_challenges SET delivery_state = 'uncertain', "
                "delivery_ciphertext = NULL, delivery_code = 'email_result_unknown' "
                "WHERE delivery_state = 'sending' AND delivery_started_at "
                "< clock_timestamp() - interval '1 minute'"
            )
            cur.execute(
                "DELETE FROM email_auth_challenges WHERE id IN "
                "(SELECT id FROM email_auth_challenges WHERE expires_at "
                "< clock_timestamp() - interval '1 hour' LIMIT 100 FOR UPDATE SKIP LOCKED)"
            )
            if not delivery_enabled:
                return None
            cur.execute(
                "SELECT id, code_digest, delivery_ciphertext, purpose FROM email_auth_challenges "
                "WHERE delivery_state = 'pending' AND delivery_ciphertext IS NOT NULL "
                "AND consumed_at IS NULL AND attempts_remaining > 0 "
                "AND expires_at > clock_timestamp() "
                "AND next_delivery_at <= clock_timestamp() "
                "ORDER BY next_delivery_at, created_at LIMIT 1 FOR UPDATE SKIP LOCKED"
            )
            row = cast(dict[str, Any] | None, cur.fetchone())
            if row is not None:
                cur.execute(
                    "UPDATE email_auth_challenges SET delivery_state = 'sending', "
                    "delivery_started_at = clock_timestamp(), "
                    "delivery_attempts = delivery_attempts + 1 "
                    "WHERE id = %s", (row["id"],),
                )
            return row

    def complete_email_delivery(
        self, challenge_id: UUID, code_digest: bytes, *, delivery_status: str, delivery_code: str,
    ) -> None:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE email_auth_challenges SET delivery_state = CASE "
                "WHEN %s = 'queued' AND delivery_attempts < 3 THEN 'pending' "
                "WHEN %s = 'queued' THEN 'failed' ELSE %s END, delivery_code = %s, "
                "delivery_ciphertext = CASE WHEN %s = 'queued' AND delivery_attempts < 3 "
                "THEN delivery_ciphertext ELSE NULL END, "
                "next_delivery_at = clock_timestamp() + interval '1 minute' "
                "WHERE id = %s AND code_digest = %s AND delivery_state = 'sending'",
                (delivery_status, delivery_status, delivery_status, delivery_code, delivery_status,
                 challenge_id, code_digest),
            )

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
                  AND (EXISTS (SELECT 1 FROM email_identities AS e WHERE e.user_id = u.id)
                       OR EXISTS (SELECT 1 FROM vkid_identities AS v WHERE v.user_id = u.id)
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
                    "session_revoked", "other_sessions_revoked", "identity_unlinked",
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

    @staticmethod
    def _active_session(cur: Any, user_id: UUID, token_digest: bytes) -> dict[str, Any]:
        """Serialize self-service security mutations with login and account deletion."""
        # Authentication mutations and account deletion share this tenant lock
        # before locking users or sessions, avoiding opposite row-order deadlocks.
        cur.execute(_ADVISORY_LOCK_SQL, (live_execution_lock_key(user_id),))
        cur.execute(
            "SELECT s.id, s.authenticated_provider, s.authenticated_at, "
            "s.authenticated_at BETWEEN now() - interval '5 minutes' AND now() "
            "AS recently_authenticated "
            "FROM users u JOIN sessions s ON s.user_id = u.id "
            "WHERE u.id = %s AND u.status = 'active' AND s.token_digest = %s "
            "AND s.revoked_at IS NULL AND s.expires_at > now() FOR UPDATE OF u, s",
            (user_id, token_digest),
        )
        row = cur.fetchone()
        if row is None:
            raise PermissionError("session_expired")
        return cast(dict[str, Any], row)

    @staticmethod
    def _prune_sessions(cur: Any, user_id: UUID | None = None) -> int:
        """Bound housekeeping to 500 auth rows; never touch financial or audit history."""
        cur.execute(
            "DELETE FROM sessions WHERE id IN (SELECT id FROM sessions "
            "WHERE (%s::uuid IS NULL OR user_id = %s::uuid) AND "
            "(expires_at < now() - interval '30 days' OR "
            "revoked_at < now() - interval '30 days') "
            "ORDER BY expires_at, id LIMIT 500 FOR UPDATE SKIP LOCKED)",
            (user_id, user_id),
        )
        return int(cur.rowcount)

    def prune_sessions(self) -> int:
        """Operator housekeeping: one bounded batch, without granting user authority."""
        with self.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            return self._prune_sessions(cur)

    def active_sessions(self, user_id: UUID, current_digest: bytes) -> dict[str, Any]:
        with self.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            current = self._active_session(cur, user_id, current_digest)
            self._prune_sessions(cur, user_id)
            cur.execute(
                "SELECT id, created_at, last_seen_at, expires_at, authenticated_provider, "
                "count(*) OVER () AS total FROM sessions WHERE user_id = %s "
                "AND revoked_at IS NULL AND expires_at > now() "
                "ORDER BY (id = %s) DESC, last_seen_at DESC, id LIMIT 100",
                (user_id, current["id"]),
            )
            rows = cast(list[dict[str, Any]], cur.fetchall())
            total = int(rows[0]["total"]) if rows else 0
            return {
                "sessions": [{
                    "id": str(row["id"]), "created_at": row["created_at"],
                    "last_seen_at": row["last_seen_at"], "expires_at": row["expires_at"],
                    "current": row["id"] == current["id"],
                    "auth_provider": row["authenticated_provider"],
                } for row in rows],
                "total": total, "truncated": total > len(rows),
            }

    def revoke_session_for_user(
        self, user_id: UUID, current_digest: bytes, session_id: UUID,
    ) -> bool:
        with self.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            current = self._active_session(cur, user_id, current_digest)
            if session_id == current["id"]:
                raise ValueError("use_logout_for_current_session")
            cur.execute(
                "UPDATE sessions SET revoked_at = now() WHERE user_id = %s AND id = %s "
                "AND revoked_at IS NULL AND expires_at > now() RETURNING id",
                (user_id, session_id),
            )
            changed = cur.fetchone() is not None
            if changed:
                cur.execute(
                    "INSERT INTO audit_events (user_id, event_type, metadata) "
                    "VALUES (%s, 'session_revoked', %s::jsonb)",
                    (user_id, json.dumps({"session_id": str(session_id)})),
                )
            return changed

    def revoke_other_sessions(self, user_id: UUID, current_digest: bytes) -> int:
        with self.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            current = self._active_session(cur, user_id, current_digest)
            cur.execute(
                "UPDATE sessions SET revoked_at = now() WHERE user_id = %s AND id <> %s "
                "AND revoked_at IS NULL AND expires_at > now()",
                (user_id, current["id"]),
            )
            count = int(cur.rowcount)
            if count:
                cur.execute(
                    "INSERT INTO audit_events (user_id, event_type, metadata) "
                    "VALUES (%s, 'other_sessions_revoked', %s::jsonb)",
                    (user_id, json.dumps({"count": count})),
                )
            return count

    def operational_metrics(
        self, operator_user_id: UUID, current_digest: bytes, *,
        configured_operator_id: UUID | None,
    ) -> dict[str, Any]:
        """Server-configured operator only; browser roles never grant this authority."""
        if configured_operator_id is None or operator_user_id != configured_operator_id:
            raise PermissionError("operator_required")
        with self.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            self._active_session(cur, operator_user_id, current_digest)
        # Do not borrow a second pool connection while holding the authorization
        # lock: simultaneous owner requests could otherwise exhaust the pool.
        return self.collect_operational_metrics()

    def record_worker_heartbeat(self, worker_name: str, *, status: str = "ok") -> None:
        """Persist service progress only; no user identity or provider text is stored."""
        if worker_name not in {"notifications", "portfolio_refresh", "portfolio_daily"}:
            raise ValueError("worker_name_invalid")
        if status not in {"running", "ok", "attention", "stopped"}:
            raise ValueError("worker_status_invalid")
        with self.pool.connection() as conn:
            conn.execute(
                "INSERT INTO worker_heartbeats (worker_name, checked_at, completed_at, status, "
                "completed_status) "
                "VALUES (%s, clock_timestamp(), CASE WHEN %s IN ('ok', 'attention') "
                "THEN clock_timestamp() ELSE NULL END, %s, "
                "CASE WHEN %s IN ('ok', 'attention') THEN %s ELSE NULL END) "
                "ON CONFLICT (worker_name) DO UPDATE SET checked_at = EXCLUDED.checked_at, "
                "status = EXCLUDED.status, completed_at = COALESCE(EXCLUDED.completed_at, "
                "worker_heartbeats.completed_at), completed_status = "
                "COALESCE(EXCLUDED.completed_status, worker_heartbeats.completed_status)",
                (worker_name, status, status, status, status),
            )

    @staticmethod
    def _observer_metrics(cur: Any, user_id: UUID) -> dict[str, Any]:
        cur.execute(
            "SELECT count(*) FILTER (WHERE status = 'queued') AS queued, "
            "count(*) FILTER (WHERE status = 'running') AS running, "
            "count(*) FILTER (WHERE status IN ('queued', 'running') "
            "AND next_attempt_at < now() - interval '30 minutes') AS stale, "
            "count(*) FILTER (WHERE status = 'failed' "
            "AND finished_at > now() - interval '24 hours') AS failed_24h, "
            "count(*) FILTER (WHERE status = 'degraded' "
            "AND finished_at > now() - interval '24 hours') AS degraded_24h, "
            "min(requested_at) FILTER (WHERE status IN ('queued', 'running')) "
            "AS oldest_pending, max(finished_at) FILTER (WHERE status = 'succeeded') "
            "AS latest_success FROM job_runs WHERE user_id = %s", (user_id,),
        )
        return cast(dict[str, Any], cur.fetchone())

    @staticmethod
    def _notification_metrics(cur: Any, user_id: UUID) -> dict[str, Any]:
        cur.execute(
            "SELECT count(*) FILTER (WHERE o.status = 'queued') AS queued, "
            "count(*) FILTER (WHERE o.status = 'sending') AS sending, "
            "count(*) FILTER (WHERE (o.status = 'queued' "
            "AND o.next_attempt_at < now() - interval '15 minutes') "
            "OR (o.status = 'sending' AND o.lease_until < now())) AS stale, "
            "count(*) FILTER (WHERE o.status = 'failed' "
            "AND o.updated_at > now() - interval '24 hours') AS failed_24h, "
            "count(*) FILTER (WHERE o.status = 'uncertain') AS uncertain, "
            "min(o.next_attempt_at) FILTER (WHERE o.status = 'queued') AS oldest_due_at, "
            "max(o.accepted_at) AS last_accepted_at FROM notification_outbox o "
            "JOIN notification_channels c ON c.id = o.channel_id AND c.user_id = o.user_id "
            "WHERE o.user_id = %s AND c.status <> 'revoked'", (user_id,),
        )
        return cast(dict[str, Any], cur.fetchone())

    @staticmethod
    def _worker_health(
        name: str, row: dict[str, Any] | None, checked_at: datetime,
    ) -> dict[str, Any]:
        timeout = 2100 if name == "portfolio_daily" else 300
        if row is None:
            return {"status": "not_reported", "checked_at": None, "completed_at": None,
                    "stale_after_seconds": timeout}
        if name == "portfolio_refresh" and row["status"] == "running":
            timeout = 1800
        status = row["status"]
        if row["checked_at"] < checked_at - timedelta(seconds=timeout):
            status = "stale"
        elif status == "running" and row.get("completed_status") == "attention":
            status = "attention"
        return {"status": status, "checked_at": row["checked_at"],
                "completed_at": row["completed_at"], "stale_after_seconds": timeout}

    @staticmethod
    def _workers_metrics(
        cur: Any, checked_at: datetime, *, active_users: int, connected_accounts: int,
    ) -> tuple[dict[str, Any], list[str]]:
        cur.execute("SELECT worker_name, checked_at, completed_at, status, completed_status "
                    "FROM worker_heartbeats")
        stored = {row["worker_name"]: dict(row) for row in cur.fetchall()}
        workers: dict[str, Any] = {}
        issues: list[str] = []
        for name in ("notifications", "portfolio_refresh", "portfolio_daily"):
            health = Database._worker_health(name, stored.get(name), checked_at)
            workers[name] = health
            required = active_users if name == "notifications" else connected_accounts
            if required and health["status"] in {"not_reported", "stale", "attention", "stopped"}:
                issues.append(name + "_worker_" + health["status"])
        return workers, issues

    @staticmethod
    def _combine_metric_time(
        current: datetime | None, candidate: datetime | None, *, latest: bool = False,
    ) -> datetime | None:
        if candidate is None:
            return current
        if current is None:
            return candidate
        return max(current, candidate) if latest else min(current, candidate)

    def _operational_user(
        self, cur: Any, user_id: UUID, checked_at: datetime,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        # Runtime keeps FORCE RLS. Aggregate one server-resolved tenant at a
        # time; do not expose identities, bodies, destinations or credentials.
        cur.execute(_SET_USER_CONTEXT_SQL, (str(user_id),))
        cur.execute("SELECT verified_at FROM tbank_connection WHERE user_id = %s", (user_id,))
        connection = cast(dict[str, Any] | None, cur.fetchone())
        row = self._observer_metrics(cur, user_id)
        row.update(connected_accounts=int(connection is not None), stale_success_accounts=0)
        if connection is not None:
            threshold = checked_at - (timedelta(hours=36) if row["latest_success"]
                                      else timedelta(minutes=30))
            observation = row["latest_success"] or connection["verified_at"]
            row["stale_success_accounts"] = int(observation < threshold)
        return row, self._notification_metrics(cur, user_id)

    def collect_operational_metrics(self) -> dict[str, Any]:
        """Internal monitor consumer; HTTP callers must use operational_metrics."""
        with self.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("SELECT now() AS checked_at")
            checked_at = cast(dict[str, Any], cur.fetchone())["checked_at"]
            cur.execute("SELECT id FROM users WHERE status = 'active' ORDER BY id")
            users = cast(list[dict[str, Any]], cur.fetchall())
            totals = dict.fromkeys(("connected_accounts", "queued", "running", "stale",
                                   "failed_24h", "degraded_24h", "stale_success_accounts"), 0)
            notifications: dict[str, Any] = dict.fromkeys(
                ("queued", "sending", "stale", "failed_24h", "uncertain"), 0,
            )
            notifications.update(oldest_due_at=None, last_accepted_at=None,
                                 stale_after_seconds=900)
            oldest_pending = None
            latest_success = None
            for user in users:
                row, delivery = self._operational_user(cur, user["id"], checked_at)
                for key in totals:
                    totals[key] += int(row[key])
                oldest_pending = self._combine_metric_time(oldest_pending, row["oldest_pending"])
                latest_success = self._combine_metric_time(latest_success, row["latest_success"],
                                                            latest=True)
                for key in ("queued", "sending", "stale", "failed_24h", "uncertain"):
                    notifications[key] += int(delivery[key])
                for key in ("oldest_due_at", "last_accepted_at"):
                    notifications[key] = self._combine_metric_time(
                        notifications[key], delivery[key], latest=key == "last_accepted_at",
                    )
            workers, issues = self._workers_metrics(
                cur, checked_at, active_users=len(users),
                connected_accounts=totals["connected_accounts"],
            )
            issues.extend("observer_" + key for key in (
                "stale", "failed_24h", "degraded_24h", "stale_success_accounts",
            ) if totals[key])
            issues.extend("notifications_" + key for key in (
                "stale", "failed_24h", "uncertain",
            ) if notifications[key])
            return {
                "checked_at": checked_at, "active_users": len(users), "observer": totals,
                "oldest_pending_at": oldest_pending, "latest_success_at": latest_success,
                "stale_after_seconds": 1800, "observation_stale_after_seconds": 129600,
                "notifications": notifications, "workers": workers, "issues": issues,
                "status": "attention" if issues else "ok",
            }

    def delete_user_account(self, user_id: UUID) -> bool:
        """Permanently delete one authenticated user's account and linked data."""

        with self.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute(
                _ADVISORY_LOCK_SQL,
                (live_execution_lock_key(user_id),),
            )
            cur.execute("SELECT email FROM email_identities WHERE user_id = %s", (user_id,))
            identity = cast(dict[str, Any] | None, cur.fetchone())
            if identity is not None:
                cur.execute(_ADVISORY_LOCK_SQL, (f"email-identity:{identity['email']}",))
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
            if identity is not None:
                # Include unverified/suppressed requests whose user_id is still
                # NULL. They must not retain the deleted login or its verifier.
                cur.execute("DELETE FROM email_auth_challenges WHERE email = %s",
                            (identity["email"],))

            cur.execute(
                _SET_USER_CONTEXT_SQL,
                (str(user.id),),
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

    def accept_legal_versions(
        self, user_id: UUID, current_digest: bytes, legal_versions: dict[str, str],
        *, client_ip_hash: bytes,
    ) -> dict[str, Any]:
        """Record explicit current consent atomically under the existing session lock."""
        if (set(legal_versions) != {"privacy_policy", "personal_data_consent", "terms"}
                or any(not value for value in legal_versions.values())):
            raise ValueError("legal_versions_unavailable")
        with self.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            self._active_session(cur, user_id, current_digest)
            for document_type, version in legal_versions.items():
                cur.execute(
                    "INSERT INTO legal_acceptances "
                    "(user_id, document_type, document_version, client_ip_hash) "
                    "VALUES (%s, %s, %s, %s) ON CONFLICT "
                    "(user_id, document_type, document_version) DO NOTHING",
                    (user_id, document_type, version, client_ip_hash),
                )
        return {"accepted": True, "legal_versions": legal_versions}

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
