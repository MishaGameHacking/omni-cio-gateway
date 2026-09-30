"""PostgreSQL persistence boundary for authentication."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
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


@dataclass(frozen=True, slots=True)
class UserRecord:
    id: UUID
    public_id: int
    status: str


class Database:
    """Thin persistence adapter for auth state."""

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
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                return cur.fetchone() is not None

    def recent_challenge_counts(
        self,
        *,
        phone_lookup: bytes,
        client_ip_hash: bytes,
        since: datetime,
    ) -> tuple[int, int]:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        count(*) FILTER (WHERE phone_lookup = %(phone_lookup)s) AS phone_count,
                        count(*) FILTER (WHERE client_ip_hash = %(client_ip_hash)s) AS ip_count
                    FROM otp_challenges
                    WHERE created_at >= %(since)s
                    """,
                    {
                        "challenge_id": challenge_id,
                        "phone_lookup": phone_lookup,
                        "client_ip_hash": client_ip_hash,
                        "since": since,
                    },
                )
                row = cur.fetchone()
                if row is None:
                    return 0, 0
                return int(row["phone_count"]), int(row["ip_count"])

    def latest_challenge_created_at(self, phone_lookup: bytes) -> datetime | None:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
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
                row = cur.fetchone()
                return None if row is None else row["created_at"]

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
    ) -> UUID:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO otp_challenges (
                        id,
                        phone_lookup,
                        phone_ciphertext,
                        code_digest,
                        client_ip_hash,
                        attempts_remaining,
                        expires_at
                    )
                    VALUES (
                        %(challenge_id)s,
                        %(phone_lookup)s,
                        %(phone_ciphertext)s,
                        %(code_digest)s,
                        %(client_ip_hash)s,
                        %(attempts_remaining)s,
                        now() + make_interval(secs => %(ttl_seconds)s)
                    )
                    RETURNING id
                    """,
                    {
                        "phone_lookup": phone_lookup,
                        "phone_ciphertext": phone_ciphertext,
                        "code_digest": code_digest,
                        "client_ip_hash": client_ip_hash,
                        "attempts_remaining": attempts_remaining,
                        "ttl_seconds": ttl_seconds,
                    },
                )
                row = cur.fetchone()
                if row is None:
                    raise RuntimeError("challenge insert returned no id")
                return row["id"]

    def mark_challenge_sent(self, challenge_id: UUID, provider_message_id: str | None) -> None:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE otp_challenges
                    SET sent_at = now(), provider_message_id = %s
                    WHERE id = %s
                    """,
                    (provider_message_id, challenge_id),
                )

    def load_challenge(self, challenge_id: UUID) -> ChallengeRecord | None:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM otp_challenges WHERE id = %s", (challenge_id,))
                row = cur.fetchone()
                return None if row is None else _challenge(row)

    def consume_challenge(
        self,
        challenge_id: UUID,
        *,
        code_matches: bool,
    ) -> ChallengeRecord | None:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                if code_matches:
                    cur.execute(
                        """
                        UPDATE otp_challenges
                        SET consumed_at = now()
                        WHERE id = %s
                          AND consumed_at IS NULL
                          AND expires_at > now()
                          AND attempts_remaining > 0
                        RETURNING *
                        """,
                        (challenge_id,),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE otp_challenges
                        SET attempts_remaining = GREATEST(attempts_remaining - 1, 0)
                        WHERE id = %s
                          AND consumed_at IS NULL
                          AND expires_at > now()
                          AND attempts_remaining > 0
                        RETURNING *
                        """,
                        (challenge_id,),
                    )
                row = cur.fetchone()
                return None if row is None else _challenge(row)

    def resolve_user_and_create_session(
        self,
        *,
        phone_lookup: bytes,
        phone_ciphertext: bytes,
        client_ip_hash: bytes,
        session_token_digest: bytes,
        session_ttl_seconds: int,
        legal_versions: dict[str, str],
    ) -> tuple[UserRecord, bool]:
        with self.pool.connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT u.id, u.public_id, u.status
                        FROM users AS u
                        JOIN phone_identities AS p ON p.user_id = u.id
                        WHERE p.phone_lookup = %s
                        """,
                        (phone_lookup,),
                    )
                    row = cur.fetchone()

                    created = row is None
                    if row is None:
                        cur.execute(
                            "INSERT INTO users DEFAULT VALUES RETURNING id, public_id, status"
                        )
                        row = cur.fetchone()
                        if row is None:
                            raise RuntimeError("user insert returned no row")
                        user = _user(row)
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
                            (user.id, phone_lookup, phone_ciphertext),
                        )
                    else:
                        user = _user(row)

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
                            '{"method":"phone_otp"}',
                        ),
                    )
                    return user, created

    def user_from_session_digest(self, token_digest: bytes) -> UserRecord | None:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
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
                row = cur.fetchone()
                return None if row is None else _user(row)

    def revoke_session(self, token_digest: bytes) -> None:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE sessions
                    SET revoked_at = COALESCE(revoked_at, now())
                    WHERE token_digest = %s
                    """,
                    (token_digest,),
                )


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


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
    )


def _user(row: dict[str, Any]) -> UserRecord:
    return UserRecord(
        id=row["id"],
        public_id=int(row["public_id"]),
        status=str(row["status"]),
    )
