"""Email ownership, reset races and session isolation on disposable PostgreSQL."""

from __future__ import annotations

import os
import secrets
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from threading import Barrier
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from cryptography.fernet import Fernet
from psycopg import sql
from test_workspace_postgres import workspace_database as workspace_database

from omnicio.config import Settings
from omnicio.db import Database, UserRecord
from omnicio.security import encrypt_secret, hash_password, session_digest
from omnicio.service import AuthService
from omnicio.workspace import default_preferences
from omnicio.workspace_store import WorkspaceStore

pytestmark = pytest.mark.skipif(
    not os.environ.get("OMNICIO_TEST_DATABASE_URL"),
    reason="ephemeral PostgreSQL is required",
)
VERSIONS = {"privacy_policy": "test-current", "personal_data_consent": "test-current",
            "terms": "test-current"}
PASSWORD = "A unique synthetic phrase 39"
PASSWORD_HASH = hash_password(PASSWORD)
CRYPTO_KEY = Fernet.generate_key().decode()


@dataclass(frozen=True)
class Challenge:
    id: UUID
    email: str
    flow: bytes
    code: bytes
    purpose: str
    enrollment_session: bytes | None = None


def start(
    database: Database, *, email: str | None = None, purpose: str = "register",
    owner: UserRecord | None = None, enrollment_session: bytes | None = None,
) -> Challenge:
    proof = Challenge(uuid4(), email or uuid4().hex + "@gmail.com", secrets.token_bytes(32),
                      secrets.token_bytes(32), purpose, enrollment_session)
    database.create_email_challenge(
        challenge_id=proof.id, purpose=purpose, email=proof.email,
        password_hash=PASSWORD_HASH if purpose != "reset" else None,
        flow_digest=proof.flow, code_digest=proof.code, client_ip_hash=b"i" * 32,
        legal_versions=VERSIONS if purpose != "reset" else {},
        delivery_ciphertext=encrypt_secret('{"code":"01234567"}', CRYPTO_KEY),
        user_id=owner.id if owner else None, enrollment_session_digest=enrollment_session,
    )
    return proof


def consume(database: Database, proof: Challenge, **changes: Any):
    return database.consume_email_challenge(**{
        "challenge_id": proof.id, "purpose": proof.purpose,
        "flow_digest": proof.flow, "code_digest": proof.code,
        "client_ip_hash": b"i" * 32, "legal_versions": VERSIONS,
        "token_digest": secrets.token_bytes(32), "session_ttl_seconds": 3600,
        "enrollment_session_digest": proof.enrollment_session, **changes,
    })


def login(database: Database, *, subject: str | None = None) -> tuple[UserRecord, bool, bytes]:
    email, token = (subject or uuid4().hex) + "@gmail.com", secrets.token_bytes(32)
    identity = database.email_identity(email)
    if identity is None:
        proof = start(database, email=email)
        result = consume(database, proof, token_digest=token)
        assert result is not None
        user, created = result
    else:
        existing = database.complete_email_login(
            identity, token_digest=token, client_ip_hash=b"i" * 32, session_ttl_seconds=3600,
        )
        assert existing is not None
        user, created = existing, False
    return user, created, token


def legacy_login(database: Database) -> tuple[UserRecord, bytes]:
    token = secrets.token_bytes(32)
    with database.pool.connection() as conn:
        row = conn.execute("INSERT INTO users DEFAULT VALUES RETURNING *").fetchone()
        owner = UserRecord(row["id"], row["public_id"], row["status"], row["role"])
        conn.execute("INSERT INTO vkid_identities (user_id, vk_user_id) VALUES (%s, %s)",
                     (owner.id, str(uuid4().int)))
        conn.execute(
            "INSERT INTO sessions (user_id, token_digest, client_ip_hash, expires_at, "
            "authenticated_provider, authenticated_at) VALUES (%s, %s, %s, "
            "clock_timestamp() + interval '1 hour', 'vkid', now())",
            (owner.id, token, b"i" * 32),
        )
    return owner, token


def challenge_row(database: Database, proof: Challenge) -> dict[str, Any]:
    with database.pool.connection() as conn:
        return conn.execute("SELECT * FROM email_auth_challenges WHERE id = %s",
                            (proof.id,)).fetchone()


def test_email_migration_reapply_preserves_accounts_credentials_sessions_and_tenant_data(
    workspace_database: tuple[Database, str, str],
) -> None:
    database, admin_dsn, schema = workspace_database
    subject = uuid4().hex
    email_owner, _, email_session = login(database, subject=subject)
    legacy_owner, legacy_session = legacy_login(database)
    tid_session = secrets.token_bytes(32)
    with database.pool.connection() as conn:
        conn.execute("INSERT INTO tid_identities (user_id, tid_subject) VALUES (%s, %s)",
                     (legacy_owner.id, uuid4().hex))
        conn.execute(
            "INSERT INTO sessions (user_id, token_digest, client_ip_hash, expires_at, "
            "authenticated_provider, authenticated_at) VALUES (%s, %s, %s, "
            "clock_timestamp() + interval '1 hour', 'tid', now())",
            (legacy_owner.id, tid_session, b"i" * 32),
        )
    store = WorkspaceStore(database)
    saved_preferences = {}
    for owner, name in ((email_owner, "Почтовый профиль"), (legacy_owner, "Прежний профиль")):
        preferences = {**default_preferences(), "display_name": name}
        store.save_preferences(owner.id, preferences, expected_version=0)
        saved_preferences[owner.id] = store.preferences(owner.id)
    identity = database.email_identity(subject + "@gmail.com")
    pending = start(database, purpose="enroll", owner=legacy_owner,
                    enrollment_session=legacy_session)
    pending_before = challenge_row(database, pending)

    # The fixture already applied 0029. Repeat its exact SQL as a migration
    # owner, with all three accepted session providers and tenant rows present.
    migration = Path(__file__).resolve().parents[1] / "migrations" / "0029_email_auth.sql"
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema)))
        admin.execute(migration.read_text(encoding="utf-8"))

    assert database.email_identity(subject + "@gmail.com") == identity
    assert challenge_row(database, pending) == pending_before
    assert database.has_legal_versions(email_owner.id, VERSIONS)
    for owner, token in ((email_owner, email_session), (legacy_owner, legacy_session),
                         (legacy_owner, tid_session)):
        assert database.refresh_session_digest(token, session_ttl_seconds=3600) == owner
        assert store.preferences(owner.id) == saved_preferences[owner.id]
    assert {row["auth_provider"] for row in database.active_sessions(
        legacy_owner.id, legacy_session,
    )["sessions"]} == {"vkid", "tid"}

    # Exercise the actual password verifier and new-session write after retry.
    # SMTP configuration/delivery is independent of an existing account login.
    auth = AuthService(Settings(
        database_url=database.pool.conninfo, ip_key=CRYPTO_KEY,
        broker_token_crypto_key=CRYPTO_KEY, privacy_version=VERSIONS["privacy_policy"],
        consent_version=VERSIONS["personal_data_consent"], terms_version=VERSIONS["terms"],
        session_ttl_seconds=3600,
    ), database)
    assert not auth.settings.auth_email_ready
    result = auth.login_email(subject + "@gmail.com", PASSWORD, client_ip="192.0.2.24")
    assert not result.created
    assert database.refresh_session_digest(
        session_digest(result.session_token), session_ttl_seconds=3600,
    ) == email_owner


def test_self_service_sessions_are_owner_scoped_and_preserve_current_session(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    subject = uuid4().hex
    owner, _, current = login(database, subject=subject)
    _, _, previous = login(database, subject=subject)
    other, _, foreign = login(database)
    listing = database.active_sessions(owner.id, current)
    assert listing["total"] == 2
    assert listing["truncated"] is False
    assert listing["sessions"][0]["current"] is True
    assert listing["sessions"][0]["auth_provider"] == "email"
    assert all(set(row) == {
        "id", "created_at", "last_seen_at", "expires_at", "current", "auth_provider",
    } for row in listing["sessions"])
    target = UUID(next(row["id"] for row in listing["sessions"] if not row["current"]))
    foreign_id = UUID(database.active_sessions(other.id, foreign)["sessions"][0]["id"])
    assert not database.revoke_session_for_user(owner.id, current, foreign_id)
    with pytest.raises(ValueError, match="use_logout"):
        database.revoke_session_for_user(owner.id, current, UUID(listing["sessions"][0]["id"]))
    assert database.revoke_session_for_user(owner.id, current, target)
    assert not database.revoke_session_for_user(owner.id, current, target)
    assert database.refresh_session_digest(previous, session_ttl_seconds=3600) is None
    assert database.refresh_session_digest(foreign, session_ttl_seconds=3600) == other
    login(database, subject=subject)
    login(database, subject=subject)
    assert database.revoke_other_sessions(owner.id, current) == 2
    assert database.revoke_other_sessions(owner.id, current) == 0
    assert database.refresh_session_digest(current, session_ttl_seconds=3600) == owner
    database.revoke_session(current)
    with pytest.raises(PermissionError, match="session_expired"):
        database.active_sessions(owner.id, current)



def test_expired_session_cleanup_is_bounded_and_preserves_recent_sessions_and_history(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner, _, current = login(database)
    with database.pool.connection() as conn, conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO sessions (user_id, token_digest, client_ip_hash, created_at, "
            "expires_at, revoked_at) VALUES (%s, %s, %s, now() - interval '60 days', "
            "now() - interval '40 days', NULL)",
            [(owner.id, secrets.token_bytes(32), b"i" * 32) for _ in range(600)],
        )
        audit_count = conn.execute(
            "SELECT count(*) AS n FROM audit_events WHERE user_id = %s", (owner.id,),
        ).fetchone()["n"]
    listing = database.active_sessions(owner.id, current)
    assert listing["total"] == 1
    with database.pool.connection() as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM sessions WHERE user_id = %s", (owner.id,),
        ).fetchone()["n"] == 101
        assert conn.execute(
            "SELECT count(*) AS n FROM audit_events WHERE user_id = %s", (owner.id,),
        ).fetchone()["n"] == audit_count
    assert database.refresh_session_digest(current, session_ttl_seconds=3600) == owner



def test_operational_metrics_require_configured_operator_and_aggregate_without_tenant_identifiers(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner, _, current = login(database)
    other, _, other_session = login(database)
    assert owner.role == "user"
    with pytest.raises(PermissionError, match="operator_required"):
        database.operational_metrics(other.id, other_session, configured_operator_id=owner.id)
    with pytest.raises(PermissionError, match="operator_required"):
        database.operational_metrics(owner.id, current, configured_operator_id=None)
    with pytest.raises(PermissionError):
        database.operational_metrics(owner.id, other_session, configured_operator_id=owner.id)
    with database.pool.connection() as conn:
        conn.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(other.id),))
        conn.execute(
            "INSERT INTO job_runs (user_id, job_type, scheduled_for, status, requested_at, "
            "next_attempt_at) VALUES (%s, 'portfolio_refresh', NULL, 'queued', "
            "now() - interval '31 minutes', now() - interval '31 minutes')",
            (other.id,),
        )
    result = database.operational_metrics(owner.id, current, configured_operator_id=owner.id)
    assert result["observer"]["stale"] >= 1
    assert result["status"] == "attention"
    assert str(owner.id) not in str(result)
    assert str(other.id) not in str(result)
    assert "token" not in str(result)
    assert "digest" not in str(result)
    with database.pool.connection() as conn:
        assert conn.execute("SELECT current_setting('omnicio.user_id', true)").fetchone()[
            "current_setting"
        ] in {"", None}



def test_opposite_session_revocations_serialize_and_preserve_the_winning_session(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    subject = uuid4().hex
    owner, _, first = login(database, subject=subject)
    _, _, second = login(database, subject=subject)
    ready = Barrier(2)

    def revoke(digest: bytes) -> int | str:
        ready.wait(timeout=5)
        try:
            return database.revoke_other_sessions(owner.id, digest)
        except PermissionError:
            return "already_revoked"

    with ThreadPoolExecutor(max_workers=2) as workers:
        outcomes = list(workers.map(revoke, (first, second)))
    assert sorted(map(str, outcomes)) == ["1", "already_revoked"]
    still_active = [digest for digest in (first, second)
                    if database.refresh_session_digest(digest, session_ttl_seconds=3600)]
    assert len(still_active) == 1



def test_operational_metrics_do_not_borrow_a_second_connection_under_authority_lock(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner, _, current = login(database)
    single = Database(database.pool.conninfo)
    single.pool.resize(min_size=1, max_size=1)
    single.pool.timeout = 1
    single.open()
    try:
        assert "observer" in single.operational_metrics(
            owner.id, current, configured_operator_id=owner.id,
        )
    finally:
        single.close()



def test_no_account_or_broker_authority_exists_before_email_proof(workspace_database):
    database = workspace_database[0]
    proof = start(database)
    assert database.email_identity(proof.email) is None
    with database.pool.connection() as conn:
        before = conn.execute("SELECT count(*) AS n FROM users").fetchone()["n"]
    user, created = consume(database, proof)
    assert created
    assert user.role == "user"
    assert database.email_identity(proof.email)["user_id"] == user.id
    assert database.has_legal_versions(user.id, VERSIONS)
    with database.pool.connection() as conn:
        assert conn.execute("SELECT count(*) AS n FROM users").fetchone()["n"] == before + 1
        assert conn.execute("SELECT count(*) AS n FROM tbank_connection WHERE user_id = %s",
                            (user.id,)).fetchone()["n"] == 0
    assert challenge_row(database, proof)["delivery_ciphertext"] is None
    assert challenge_row(database, proof)["user_id"] == user.id
    assert consume(database, proof) is None


def test_browser_binding_failures_do_not_consume_another_browsers_challenge(workspace_database):
    database = workspace_database[0]
    proof = start(database)
    assert consume(database, proof, flow_digest=secrets.token_bytes(32)) is None
    assert challenge_row(database, proof)["attempts_remaining"] == 5
    assert consume(database, proof) is not None


def test_bad_otp_attempts_commit_across_connections_and_exhaustion_survives_resend(
    workspace_database,
):
    database = workspace_database[0]
    proof = start(database)
    for remaining in range(4, -1, -1):
        assert consume(database, proof, code_digest=secrets.token_bytes(32)) is None
        assert challenge_row(database, proof)["attempts_remaining"] == remaining
    assert consume(database, proof) is None
    with database.pool.connection() as conn:
        conn.execute("UPDATE email_auth_challenges SET resend_at = now() WHERE id = %s",
                     (proof.id,))
    assert database.resend_email_challenge(proof.id, proof.flow, b"c" * 32, b"ciphertext") is None
    assert database.email_identity(proof.email) is None


def test_resend_invalidates_previous_code_without_extending_expiry_or_resetting_attempts(
    workspace_database,
):
    database = workspace_database[0]
    proof = start(database)
    assert consume(database, proof, code_digest=b"w" * 32) is None
    original = challenge_row(database, proof)
    assert database.resend_email_challenge(proof.id, proof.flow, b"n" * 32, b"ciphertext") is None
    with database.pool.connection() as conn:
        conn.execute("UPDATE email_auth_challenges SET resend_at = now() WHERE id = %s",
                     (proof.id,))
    ttl = database.resend_email_challenge(proof.id, proof.flow, b"n" * 32, b"ciphertext")
    assert ttl is not None
    assert 0 < ttl <= 600
    row = challenge_row(database, proof)
    assert row["expires_at"] == original["expires_at"]
    assert row["attempts_remaining"] == 4
    assert consume(database, proof) is None
    assert consume(database, proof, code_digest=b"n" * 32) is not None


def test_concurrent_verification_creates_one_tenant_and_one_session(workspace_database):
    database = workspace_database[0]
    proof = start(database)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: consume(database, proof), range(4)))
    successes = [result for result in results if result is not None]
    assert len(successes) == 1
    user, created = successes[0]
    assert created
    with database.pool.connection() as conn:
        assert conn.execute("SELECT count(*) AS n FROM sessions WHERE user_id = %s",
                            (user.id,)).fetchone()["n"] == 1


def test_duplicate_registration_never_merges_into_existing_account(workspace_database):
    database = workspace_database[0]
    subject = uuid4().hex
    owner, _, current = login(database, subject=subject)
    proof = start(database, email=subject + "@gmail.com")
    row = challenge_row(database, proof)
    assert row["suppressed"]
    assert row["delivery_ciphertext"] is None
    assert consume(database, proof) is None
    assert database.email_identity(proof.email)["user_id"] == owner.id
    assert database.refresh_session_digest(current, session_ttl_seconds=3600) == owner
    assert database.active_sessions(owner.id, current)["total"] == 1


def test_public_registration_has_no_two_user_capacity_limit(workspace_database):
    database = workspace_database[0]
    with ThreadPoolExecutor(max_workers=4) as pool:
        accounts = list(pool.map(lambda _: login(database), range(4)))
    assert len({account[0].id for account in accounts}) == 4
    assert all(account[1] for account in accounts)


@pytest.mark.parametrize("condition", ["expired", "stale_legal"])
def test_expired_or_stale_legal_proof_cannot_create_credentials(workspace_database, condition):
    database = workspace_database[0]
    proof = start(database)
    changes = {}
    if condition == "expired":
        with database.pool.connection() as conn:
            conn.execute("UPDATE email_auth_challenges SET created_at = now() - interval '1 day', "
                         "expires_at = now() - interval '1 hour' WHERE id = %s", (proof.id,))
    else:
        changes["legal_versions"] = {"terms": "new-version"}
    assert consume(database, proof, **changes) is None
    assert database.email_identity(proof.email) is None


def test_reset_changes_password_version_revokes_all_sessions_and_blocks_old_login_snapshot(
    workspace_database,
):
    database = workspace_database[0]
    subject = uuid4().hex
    owner, _, first = login(database, subject=subject)
    _, _, second = login(database, subject=subject)
    email = subject + "@gmail.com"
    previous = database.email_identity(email)
    proof = start(database, email=email, purpose="reset")
    replacement = hash_password("A replacement synthetic phrase 42")
    user, created = consume(database, proof, password_hash=replacement)
    assert user == owner
    assert not created
    current = database.email_identity(email)
    assert current["password_hash"] == replacement
    assert current["password_version"] == previous["password_version"] + 1
    assert database.refresh_session_digest(first, session_ttl_seconds=3600) is None
    assert database.refresh_session_digest(second, session_ttl_seconds=3600) is None
    assert consume(database, proof, password_hash=replacement) is None
    assert database.complete_email_login(
        previous, token_digest=secrets.token_bytes(32), client_ip_hash=b"i" * 32,
        session_ttl_seconds=3600,
    ) is None


def test_reset_unknown_email_remains_generic_and_never_creates_account(workspace_database):
    database = workspace_database[0]
    proof = start(database, purpose="reset")
    assert challenge_row(database, proof)["suppressed"]
    assert challenge_row(database, proof)["delivery_ciphertext"] is None
    assert consume(database, proof, password_hash=PASSWORD_HASH) is None
    assert database.email_identity(proof.email) is None


def test_legacy_migration_preserves_tenant_data_requires_session_and_revokes_old_sessions(
    workspace_database,
):
    database = workspace_database[0]
    owner, current = legacy_login(database)
    assert database.refresh_session_digest(current, session_ttl_seconds=3600) == owner
    store = WorkspaceStore(database)
    prefs = {**default_preferences(), "display_name": "Сохранённый профиль"}
    store.save_preferences(owner.id, prefs, expected_version=0)
    proof = start(database, purpose="enroll", owner=owner, enrollment_session=current)
    new_session = secrets.token_bytes(32)
    result = consume(database, proof, token_digest=new_session)
    assert result == (owner, False)
    assert store.preferences(owner.id)["document"] == prefs
    assert database.refresh_session_digest(current, session_ttl_seconds=3600) is None
    assert database.refresh_session_digest(new_session, session_ttl_seconds=3600) == owner
    assert database.email_identity_status(owner.id)["migration_required"] is False
    with database.pool.connection() as conn:
        assert conn.execute("SELECT count(*) AS n FROM vkid_identities WHERE user_id = %s",
                            (owner.id,)).fetchone()["n"] == 1


@pytest.mark.parametrize("condition", ["revoked", "foreign", "blocked"])
def test_legacy_enrollment_revalidates_exact_session_and_active_owner(
    workspace_database, condition,
):
    database = workspace_database[0]
    owner, current = legacy_login(database)
    proof = start(database, purpose="enroll", owner=owner, enrollment_session=current)
    if condition == "foreign":
        _, other = legacy_login(database)
        assert consume(database, proof, enrollment_session_digest=other) is None
    else:
        if condition == "revoked":
            database.revoke_session(current)
        else:
            with database.pool.connection() as conn:
                conn.execute("UPDATE users SET status = 'blocked' WHERE id = %s", (owner.id,))
        with pytest.raises(PermissionError):
            consume(database, proof)
    assert database.email_identity(proof.email) is None


def test_enrollment_never_takes_email_or_data_from_another_tenant(workspace_database):
    database = workspace_database[0]
    subject = uuid4().hex
    other, _, other_session = login(database, subject=subject)
    owner, current = legacy_login(database)
    proof = start(database, email=subject + "@gmail.com", purpose="enroll",
                  owner=owner, enrollment_session=current)
    assert consume(database, proof) is None
    assert database.email_identity_status(owner.id)["email"] is None
    assert database.email_identity_status(other.id)["email"] == proof.email
    assert database.refresh_session_digest(other_session, session_ttl_seconds=3600) == other
    assert database.refresh_session_digest(current, session_ttl_seconds=3600) == owner


def test_rate_windows_are_atomic_shared_and_expire_without_sleep(workspace_database):
    database = workspace_database[0]
    digest = secrets.token_bytes(32)
    with ThreadPoolExecutor(max_workers=6) as pool:
        admitted = list(pool.map(lambda _: database.consume_auth_budget([(digest, 3, 60)]),
                                 range(6)))
    assert sum(admitted) == 3
    with database.pool.connection() as conn:
        row = conn.execute("SELECT * FROM email_auth_rate_limits WHERE bucket_digest = %s",
                           (digest,)).fetchone()
        assert row["attempts"] == 6
        conn.execute("UPDATE email_auth_rate_limits SET expires_at = now() - interval '1 second' "
                     "WHERE bucket_digest = %s", (digest,))
    assert database.consume_auth_budget([(digest, 3, 60)])


def test_delivery_is_claimed_once_ambiguous_outcomes_are_not_replayed_and_secrets_are_purged(
    workspace_database,
):
    database = workspace_database[0]
    proof = start(database)
    with database.pool.connection() as conn:
        conn.execute("UPDATE email_auth_challenges SET delivery_ciphertext = NULL "
                     "WHERE id <> %s", (proof.id,))
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda _: database.claim_email_delivery(), range(3)))
    assert sum(result is not None for result in results) == 1
    assert next(result for result in results if result is not None)["id"] == proof.id
    with database.pool.connection() as conn:
        conn.execute("UPDATE email_auth_challenges SET delivery_started_at = "
                     "now() - interval '2 minutes' WHERE id = %s", (proof.id,))
    assert database.claim_email_delivery() is None
    row = challenge_row(database, proof)
    assert row["delivery_state"] == "uncertain"
    assert row["delivery_ciphertext"] is None
    assert row["delivery_code"] == "email_result_unknown"


def test_mail_receipt_from_before_resend_cannot_overwrite_new_code_or_delivery(workspace_database):
    database = workspace_database[0]
    proof = start(database)
    with database.pool.connection() as conn:
        conn.execute("UPDATE email_auth_challenges SET delivery_ciphertext = NULL WHERE id <> %s",
                     (proof.id,))
        conn.execute("UPDATE email_auth_challenges SET resend_at = now() WHERE id = %s",
                     (proof.id,))
    assert database.claim_email_delivery()["id"] == proof.id
    assert database.resend_email_challenge(proof.id, proof.flow, b"n" * 32, b"ciphertext")
    database.complete_email_delivery(proof.id, proof.code, delivery_status="accepted",
                                     delivery_code="email_accepted")
    row = challenge_row(database, proof)
    assert row["delivery_state"] == "pending"
    assert bytes(row["code_digest"]) == b"n" * 32
    assert bytes(row["delivery_ciphertext"]) == b"ciphertext"


def test_email_only_account_can_delete_itself_and_auth_records_cascade(workspace_database):
    database = workspace_database[0]
    subject = uuid4().hex
    owner, _, token = login(database, subject=subject)
    proof = start(database, email=subject + "@gmail.com", purpose="reset")
    duplicate = start(database, email=subject + "@gmail.com")
    assert database.delete_user_account(owner.id)
    assert database.email_identity(subject + "@gmail.com") is None
    assert database.email_challenge(proof.id, proof.flow) is None
    assert database.email_challenge(duplicate.id, duplicate.flow) is None
    assert database.refresh_session_digest(token, session_ttl_seconds=3600) is None
    with database.pool.connection() as conn:
        assert conn.execute("SELECT count(*) AS n FROM email_auth_challenges WHERE email = %s",
                            (proof.email,)).fetchone()["n"] == 0


def test_disabling_mail_does_not_stop_expired_challenge_cleanup(workspace_database):
    database = workspace_database[0]
    proof = start(database)
    fresh = start(database)
    with database.pool.connection() as conn:
        conn.execute("UPDATE email_auth_challenges SET created_at = now() - interval '1 day', "
                     "expires_at = now() - interval '2 hours' WHERE id = %s", (proof.id,))
    assert database.claim_email_delivery(delivery_enabled=False) is None
    with database.pool.connection() as conn:
        assert conn.execute("SELECT 1 FROM email_auth_challenges WHERE id = %s",
                            (proof.id,)).fetchone() is None
    assert challenge_row(database, fresh)["delivery_state"] == "pending"
    assert challenge_row(database, fresh)["delivery_attempts"] == 0


def test_legal_renewal_is_idempotent_and_bound_to_live_owner_session(workspace_database):
    database, _, _ = workspace_database
    owner, _, token = login(database)
    other, _, other_token = login(database)
    versions = dict.fromkeys(VERSIONS, "new-current")
    assert not database.has_legal_versions(owner.id, versions)
    with pytest.raises(PermissionError):
        database.accept_legal_versions(owner.id, other_token, versions, client_ip_hash=b"i" * 32)
    assert not database.has_legal_versions(owner.id, versions)
    for _ in range(2):
        assert database.accept_legal_versions(owner.id, token, versions,
                                             client_ip_hash=b"i" * 32)["accepted"] is True
    assert database.has_legal_versions(owner.id, versions)
    assert not database.has_legal_versions(other.id, versions)
    with database.pool.connection() as conn:
        row = conn.execute("SELECT count(*) AS n FROM legal_acceptances "
                           "WHERE user_id=%s AND document_version=%s",
                           (owner.id, "new-current")).fetchone()
        assert row["n"] == 3
    database.revoke_session(token)
    revoked_versions = dict.fromkeys(VERSIONS, "revoked")
    with pytest.raises(PermissionError):
        database.accept_legal_versions(owner.id, token, revoked_versions,
                                       client_ip_hash=b"i" * 32)
    assert not database.has_legal_versions(owner.id, dict.fromkeys(VERSIONS, "revoked"))
