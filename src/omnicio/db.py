"""PostgreSQL persistence boundary for authentication."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


@dataclass(frozen=True, slots=True)
class ChallengeRecord:
    id: UUID
    phone_lookup: bytes
    phone_ciphertext: bytes
    code_digest: bytes
    attempts_remaining: int
    expires_at: datetime
    consumed_at: datetime | None
    legal_versions: dict[str, str]


@dataclass(frozen=True, slots=True)
class UserRecord:
    id: UUID
    public_id: int
    status: str


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
            cur.execute("SELECT 1")
            return cur.fetchone() is not None

    def recent_challenge_counts(
        self,
        *,
        phone_lookup: bytes,
        client_ip_hash: bytes,
        since: datetime,
    ) -> tuple[int, int]:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    count(*) FILTER (WHERE phone_lookup = %(phone_lookup)s) AS phone_count,
                    count(*) FILTER (WHERE client_ip_hash = %(client_ip_hash)s) AS ip_count
                FROM otp_challenges
                WHERE created_at >= %(since)s
                """,
                {
                    "phone_lookup": phone_lookup,
                    "client_ip_hash": client_ip_hash,
                    "since": since,
                },
            )
            fetched = cur.fetchone()
            if fetched is None:
                return 0, 0
            row = cast(dict[str, Any], fetched)
            return int(row["phone_count"]), int(row["ip_count"])

    def latest_challenge_created_at(self, phone_lookup: bytes) -> datetime | None:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT created_at
                FROM otp_challenges
                WHERE phone_lookup = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (phone_lookup,),
            )
            fetched = cur.fetchone()
            if fetched is None:
                return None
            row = cast(dict[str, Any], fetched)
            return cast(datetime, row["created_at"])

    def create_challenge(
        self,
        *,
        challenge_id: UUID,
        phone_lookup: bytes,
        phone_ciphertext: bytes,
        code_digest: bytes,
        client_ip_hash: bytes,
        attempts_remaining: int,
        ttl_seconds: int,
        legal_versions: dict[str, str],
    ) -> UUID:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO otp_challenges (
                    id,
                    phone_lookup,
                    phone_ciphertext,
                    code_digest,
                    client_ip_hash,
                    attempts_remaining,
                    expires_at,
                    legal_versions
                )
                VALUES (
                    %(challenge_id)s,
                    %(phone_lookup)s,
                    %(phone_ciphertext)s,
                    %(code_digest)s,
                    %(client_ip_hash)s,
                    %(attempts_remaining)s,
                    now() + make_interval(secs => %(ttl_seconds)s),
                    %(legal_versions)s::jsonb
                )
                RETURNING id
                """,
                {
                    "challenge_id": challenge_id,
                    "phone_lookup": phone_lookup,
                    "phone_ciphertext": phone_ciphertext,
                    "code_digest": code_digest,
                    "client_ip_hash": client_ip_hash,
                    "attempts_remaining": attempts_remaining,
                    "ttl_seconds": ttl_seconds,
                    "legal_versions": json.dumps(legal_versions),
                },
            )
            fetched = cur.fetchone()
            if fetched is None:
                raise RuntimeError("challenge insert returned no id")
            row = cast(dict[str, Any], fetched)
            return cast(UUID, row["id"])

    def mark_challenge_sent(self, challenge_id: UUID, provider_message_id: str | None) -> None:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE otp_challenges
                SET sent_at = now(), provider_message_id = %s
                WHERE id = %s
                """,
                (provider_message_id, challenge_id),
            )

    def load_challenge(self, challenge_id: UUID) -> ChallengeRecord | None:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM otp_challenges WHERE id = %s", (challenge_id,))
            fetched = cur.fetchone()
            if fetched is None:
                return None
            return _challenge(cast(dict[str, Any], fetched))

    def record_failed_challenge_attempt(self, challenge_id: UUID) -> bool:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE otp_challenges
                SET attempts_remaining = GREATEST(attempts_remaining - 1, 0)
                WHERE id = %s
                  AND consumed_at IS NULL
                  AND expires_at > now()
                  AND attempts_remaining > 0
                RETURNING id
                """,
                (challenge_id,),
            )
            return cur.fetchone() is not None

    def complete_verified_challenge(
        self,
        *,
        challenge_id: UUID,
        client_ip_hash: bytes,
        session_token_digest: bytes,
        session_ttl_seconds: int,
        legal_versions: dict[str, str],
    ) -> tuple[UserRecord, bool] | None:
        """Atomically consume OTP, resolve account, record consent, and create session."""

        with (
            self.pool.connection() as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            cur.execute(
                """
                UPDATE otp_challenges
                SET consumed_at = now()
                WHERE id = %(challenge_id)s
                  AND consumed_at IS NULL
                  AND expires_at > now()
                  AND attempts_remaining > 0
                  AND legal_versions = %(legal_versions)s::jsonb
                RETURNING phone_lookup, phone_ciphertext, legal_versions
                """,
                {
                    "challenge_id": challenge_id,
                    "legal_versions": json.dumps(legal_versions),
                },
            )
            fetched_challenge = cur.fetchone()
            if fetched_challenge is None:
                return None
            challenge_row = cast(dict[str, Any], fetched_challenge)

            lookup = bytes(challenge_row["phone_lookup"])
            ciphertext = bytes(challenge_row["phone_ciphertext"])
            accepted_versions = dict(challenge_row["legal_versions"])

            cur.execute(
                """
                SELECT pg_advisory_xact_lock(
                    hashtextextended(encode(%s::bytea, 'hex'), 0)
                )
                """,
                (lookup,),
            )

            cur.execute(
                """
                SELECT u.id, u.public_id, u.status
                FROM users AS u
                JOIN phone_identities AS p ON p.user_id = u.id
                WHERE p.phone_lookup = %s
                """,
                (lookup,),
            )
            fetched_user = cur.fetchone()
            created = fetched_user is None

            if fetched_user is None:
                cur.execute(
                    "INSERT INTO users DEFAULT VALUES RETURNING id, public_id, status"
                )
                inserted = cur.fetchone()
                if inserted is None:
                    raise RuntimeError("user insert returned no row")
                user = _user(cast(dict[str, Any], inserted))
                cur.execute(
                    """
                    INSERT INTO phone_identities (
                        user_id,
                        phone_lookup,
                        phone_ciphertext,
                        verified_at
                    )
                    VALUES (%s, %s, %s, now())
                    """,
                    (user.id, lookup, ciphertext),
                )
            else:
                user = _user(cast(dict[str, Any], fetched_user))

            if user.status != "active":
                raise PermissionError("account is not active")

            for document_type, version in accepted_versions.items():
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
                    '{"method":"phone_otp"}',
                ),
            )
            return user, created

    def user_from_session_digest(self, token_digest: bytes) -> UserRecord | None:
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.id, u.public_id, u.status
                FROM sessions AS s
                JOIN users AS u ON u.id = s.user_id
                WHERE s.token_digest = %s
                  AND s.revoked_at IS NULL
                  AND s.expires_at > now()
                  AND u.status = 'active'
                """,
                (token_digest,),
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


def utcnow() -> datetime:
    return datetime.now(UTC)


def one_hour_ago() -> datetime:
    return utcnow() - timedelta(hours=1)


def _challenge(row: dict[str, Any]) -> ChallengeRecord:
    return ChallengeRecord(
        id=row["id"],
        phone_lookup=bytes(row["phone_lookup"]),
        phone_ciphertext=bytes(row["phone_ciphertext"]),
        code_digest=bytes(row["code_digest"]),
        attempts_remaining=int(row["attempts_remaining"]),
        expires_at=row["expires_at"],
        consumed_at=row["consumed_at"],
        legal_versions=dict(row["legal_versions"]),
    )


def _user(row: dict[str, Any]) -> UserRecord:
    return UserRecord(
        id=row["id"],
        public_id=int(row["public_id"]),
        status=str(row["status"]),
    )
