"""One-use mobile OAuth proofs and atomic identity/session changes in PostgreSQL."""

from __future__ import annotations

import hmac
from typing import Any, cast
from uuid import UUID

from psycopg import sql

from .db import Database, UserRecord, live_execution_lock_key

FLOW_TTL_SECONDS = 600
_IDENTITY_TABLES = {
    "vkid": ("vkid_identities", "vk_user_id"),
    "telegram": ("telegram_identities", "telegram_subject"),
}
_LOCK_SQL = "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))"


def _identity(cur: Any, provider: str, subject: str) -> UUID | None:
    table, column = _IDENTITY_TABLES[provider]
    cur.execute(sql.SQL("SELECT user_id FROM {} WHERE {} = %s").format(
        sql.Identifier(table), sql.Identifier(column)), (subject,))
    row = cur.fetchone()
    return cast(UUID, row["user_id"]) if row else None


class SocialAuthStore:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(
        self, *, flow_id: UUID, provider: str, purpose: str, flow_digest: bytes,
        state_digest: bytes, secrets_ciphertext: bytes, android_package: str,
        user_id: UUID | None, session_digest: bytes | None,
    ) -> None:
        with self.database.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            if purpose == "link":
                if user_id is None or session_digest is None:
                    raise PermissionError("session_required")
                current = self.database._active_session(cur, user_id, session_digest)
                if not current["recently_authenticated"]:
                    raise ValueError("recent_login_required")
            cur.execute(
                "DELETE FROM social_auth_flows WHERE id IN (SELECT id FROM social_auth_flows "
                "WHERE expires_at < now() - interval '1 hour' LIMIT 100 FOR UPDATE SKIP LOCKED)"
            )
            cur.execute(
                "INSERT INTO social_auth_flows (id, provider, purpose, flow_digest, state_digest, "
                "secrets_ciphertext, android_package, user_id, session_digest, expires_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,now() + make_interval(secs => %s))",
                (flow_id, provider, purpose, flow_digest, state_digest, secrets_ciphertext,
                 android_package, user_id, session_digest, FLOW_TTL_SECONDS),
            )

    def claim(self, provider: str, state_digest: bytes) -> dict[str, Any] | None:
        # Commit before the token exchange. An ambiguous provider response must
        # never cause a second exchange of the same authorization code.
        with self.database.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM social_auth_flows WHERE provider = %s AND state_digest = %s "
                "AND status = 'pending' AND expires_at > now() FOR UPDATE",
                (provider, state_digest),
            )
            row = cast(dict[str, Any] | None, cur.fetchone())
            if row:
                cur.execute("UPDATE social_auth_flows SET status = 'exchanging', "
                            "secrets_ciphertext = NULL WHERE id = %s", (row["id"],))
            return row

    def verified(self, flow_id: UUID, subject: str | None) -> None:
        with self.database.pool.connection() as conn:
            conn.execute(
                "UPDATE social_auth_flows SET status = %s, subject = %s "
                "WHERE id = %s AND status = 'exchanging' AND expires_at > now()",
                ("verified" if subject else "failed", subject, flow_id),
            )

    def cancel(self, flow_id: UUID, flow_digest: bytes) -> None:
        with self.database.pool.connection() as conn:
            conn.execute(
                "UPDATE social_auth_flows SET status = 'failed', secrets_ciphertext = NULL, "
                "subject = NULL WHERE id = %s AND flow_digest = %s AND status <> 'consumed'",
                (flow_id, flow_digest),
            )

    def finish(
        self, *, flow_id: UUID, flow_digest: bytes, token_digest: bytes,
        client_ip_hash: bytes, session_ttl_seconds: int,
        legal_versions: dict[str, str], current_session_digest: bytes | None,
    ) -> tuple[UserRecord, bool] | str:
        with self.database.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM social_auth_flows WHERE id = %s AND flow_digest = %s "
                "AND expires_at > now()", (flow_id, flow_digest),
            )
            context = cast(dict[str, Any] | None, cur.fetchone())
            if context is None:
                return "social_flow_expired"
            if context["status"] in {"pending", "exchanging"}:
                return "pending"
            if context["status"] != "verified":
                return "social_flow_failed"
            # Serialize competing first logins before resolving the owner. This
            # lock is never acquired by tenant deletion; tenant lock precedes rows.
            cur.execute(_LOCK_SQL, (f"social-identity:{context['provider']}:{context['subject']}",))
            owner = _identity(cur, context["provider"], context["subject"])
            user_id = context["user_id"] if context["purpose"] == "link" else owner
            if user_id is not None:
                cur.execute(_LOCK_SQL, (live_execution_lock_key(user_id),))
            cur.execute(
                "SELECT * FROM social_auth_flows WHERE id = %s AND flow_digest = %s "
                "AND status = 'verified' AND expires_at > clock_timestamp() FOR UPDATE",
                (flow_id, flow_digest),
            )
            row = cast(dict[str, Any] | None, cur.fetchone())
            if row is None:
                return "social_flow_failed"
            if row["purpose"] == "link":
                if current_session_digest is None or not hmac.compare_digest(
                    bytes(row["session_digest"]), current_session_digest,
                ):
                    return "social_session_changed"
                if user_id is None:
                    return self._reject(cur, flow_id, "social_session_changed")
                self.database._active_session(cur, user_id, current_session_digest)
                if owner is not None and owner != user_id:
                    return self._reject(cur, flow_id, "identity_already_linked")
            elif current_session_digest is not None:
                return self._reject(cur, flow_id, "social_session_changed")
            elif user_id is None and not legal_versions:
                return "registration_required"
            created = user_id is None
            user = self._resolve_user(cur, user_id)
            if user is None:
                return self._reject(cur, flow_id, "social_account_unavailable")
            result = self._attach(cur, row, user.id)
            if result:
                return self._reject(cur, flow_id, result)
            if created:
                for document, version in legal_versions.items():
                    cur.execute(
                        "INSERT INTO legal_acceptances "
                        "(user_id, document_type, document_version, client_ip_hash) "
                        "VALUES (%s,%s,%s,%s)", (user.id, document, version, client_ip_hash),
                    )
            self.database._insert_session(
                cur, user.id, token_digest=token_digest, client_ip_hash=client_ip_hash,
                session_ttl_seconds=session_ttl_seconds, provider=row["provider"],
            )
            if current_session_digest is not None:
                cur.execute("UPDATE sessions SET revoked_at = now() WHERE token_digest = %s",
                            (current_session_digest,))
            cur.execute(
                "UPDATE social_auth_flows SET status = 'consumed', subject = NULL, user_id = %s "
                "WHERE id = %s", (user.id, flow_id),
            )
            cur.execute(
                "INSERT INTO audit_events (user_id, event_type, metadata) "
                "VALUES (%s,%s,jsonb_build_object('method', %s::text))",
                (user.id, "identity_linked" if row["purpose"] == "link" else
                 "account_created" if created else "login_succeeded", row["provider"]),
            )
            return user, created

    @staticmethod
    def _resolve_user(cur: Any, user_id: UUID | None) -> UserRecord | None:
        if user_id is None:
            cur.execute("INSERT INTO users DEFAULT VALUES RETURNING id, public_id, status, role")
        else:
            cur.execute("SELECT id, public_id, status, role FROM users "
                        "WHERE id = %s AND status = 'active' FOR UPDATE", (user_id,))
        row = cur.fetchone()
        return UserRecord(**row) if row else None

    @staticmethod
    def _attach(cur: Any, flow: dict[str, Any], user_id: UUID) -> str | None:
        table, column = _IDENTITY_TABLES[flow["provider"]]
        cur.execute(sql.SQL("SELECT {} AS subject FROM {} WHERE user_id = %s").format(
            sql.Identifier(column), sql.Identifier(table)), (user_id,))
        existing = cur.fetchone()
        if existing:
            return None if existing["subject"] == flow["subject"] else "provider_already_linked"
        cur.execute(sql.SQL("INSERT INTO {} (user_id, {}) VALUES (%s,%s)").format(
            sql.Identifier(table), sql.Identifier(column)), (user_id, flow["subject"]))
        return None

    @staticmethod
    def _reject(cur: Any, flow_id: UUID, code: str) -> str:
        cur.execute("UPDATE social_auth_flows SET status = 'failed', subject = NULL "
                    "WHERE id = %s", (flow_id,))
        return code

    def identities(self, user_id: UUID) -> dict[str, Any]:
        result = self.database.email_identity_status(user_id)
        with self.database.pool.connection() as conn:
            for provider, (table, _) in _IDENTITY_TABLES.items():
                row = conn.execute(sql.SQL("SELECT 1 FROM {} WHERE user_id = %s").format(
                    sql.Identifier(table)), (user_id,)).fetchone()
                if row:
                    result["providers"].append(provider)
        # Email is an optional alternative, no longer a forced provider migration.
        result["migration_required"] = False
        return result
