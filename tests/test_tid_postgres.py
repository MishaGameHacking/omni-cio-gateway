"""New identity and replay invariants against disposable PostgreSQL only."""

from __future__ import annotations

import os
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from typing import Any
from uuid import UUID, uuid4

import pytest
from test_workspace_postgres import workspace_database as workspace_database

from omnicio.db import Database, RegistrationCapacityError, RegistrationClosedError, UserRecord
from omnicio.workspace import default_preferences
from omnicio.workspace_store import WorkspaceStore

pytestmark = pytest.mark.skipif(
    not os.environ.get("OMNICIO_TEST_DATABASE_URL"),
    reason="ephemeral PostgreSQL is required",
)


def login(
    database: Database,
    *,
    provider: str = "tid",
    subject: str | None = None,
    **changes: Any,
) -> tuple[UserRecord, bool, bytes]:
    digest = secrets.token_bytes(32)
    context = {
        "client_ip_hash": b"i" * 32,
        "session_token_digest": digest,
        "session_ttl_seconds": 3600,
        "legal_versions": {"terms": "test-current"},
        "registration_enabled": True,
        "registration_max_users": 1000,
        **changes,
    }
    if provider == "tid":
        user, created = database.complete_tid_login(tid_subject=subject or uuid4().hex, **context)
    else:
        user, created = database.complete_vkid_login(
            vk_user_id=subject or str(uuid4().int), **context
        )
    return user, created, digest


def test_tid_verified_subject_is_stable_and_login_does_not_create_broker_authority(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    subject = uuid4().hex
    first, created, digest = login(database, subject=subject)
    assert created
    assert database.refresh_session_digest(digest, session_ttl_seconds=3600) == first
    again, created_again, _ = login(database, subject=subject, registration_enabled=False)
    assert again.id == first.id
    assert not created_again
    assert database.identity_providers(first.id) == ["tid"]
    with database.pool.connection() as connection:
        assert (
            connection.execute(
                "SELECT count(*) AS n FROM tbank_connection WHERE user_id = %s",
                (first.id,),
            ).fetchone()["n"]
            == 0
        )
    with pytest.raises(RegistrationClosedError):
        login(database, registration_enabled=False)


def test_concurrent_same_subject_creates_one_tenant_and_state_is_consumed_once(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    subject = uuid4().hex
    with ThreadPoolExecutor(max_workers=4) as workers:
        identities = list(workers.map(lambda _: login(database, subject=subject), range(4)))
    assert len({item[0].id for item in identities}) == 1
    assert sum(item[1] for item in identities) == 1
    digest = secrets.token_bytes(32)
    with ThreadPoolExecutor(max_workers=4) as workers:
        claims = list(
            workers.map(lambda _: database.claim_oauth_flow(digest, "tid", 600), range(4))
        )
    assert sum(claims) == 1
    assert not database.claim_oauth_flow(digest, "vkid", 600)


def test_registration_capacity_is_shared_between_providers_under_concurrency(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    with database.pool.connection() as connection:
        total = connection.execute(
            "SELECT count(*) AS n FROM users WHERE status <> 'deleted'",
        ).fetchone()["n"]

    def attempt(provider: str) -> tuple[UserRecord, bool, bytes] | str:
        try:
            return login(database, provider=provider, registration_max_users=total + 1)
        except RegistrationCapacityError:
            return "capacity"

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(attempt, ("tid", "vkid")))
    assert sum(isinstance(item, tuple) for item in results) == 1
    assert results.count("capacity") == 1


def test_explicit_identity_link_preserves_workspace_and_rejects_another_tenant(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner, _, session = login(database, provider="vkid")
    other, _, other_session = login(database, provider="vkid")
    store = WorkspaceStore(database)
    prefs = {**default_preferences(), "display_name": "Сохранённое имя"}
    store.save_preferences(owner.id, prefs, expected_version=0)
    subject = uuid4().hex
    linked, created, _ = login(
        database,
        subject=subject,
        link_user_id=owner.id,
        link_session_digest=session,
        registration_enabled=False,
    )
    assert linked.id == owner.id
    assert not created
    assert set(database.identity_providers(owner.id)) == {"tid", "vkid"}
    assert store.preferences(owner.id)["document"] == prefs
    with pytest.raises(PermissionError, match="already_linked"):
        login(database, subject=subject, link_user_id=other.id, link_session_digest=other_session)
    with pytest.raises(PermissionError, match="provider_already_linked"):
        login(database, link_user_id=owner.id, link_session_digest=session)
    assert database.identity_providers(other.id) == ["vkid"]
    assert store.preferences(other.id)["version"] == 0


@pytest.mark.parametrize("condition", ["revoked", "expired", "wrong_user", "blocked", "deleted"])
def test_linking_revalidates_exact_live_session_and_active_user_in_transaction(
    workspace_database: tuple[Database, str, str],
    condition: str,
) -> None:
    database = workspace_database[0]
    owner, _, digest = login(database, provider="vkid")
    if condition == "revoked":
        database.revoke_session(digest)
    elif condition == "deleted":
        assert database.delete_user_account(owner.id)
    elif condition == "wrong_user":
        _, _, digest = login(database, provider="vkid")
    else:
        with database.pool.connection() as connection:
            if condition == "expired":
                connection.execute(
                    "UPDATE sessions SET created_at = %s, expires_at = %s WHERE token_digest = %s",
                    (
                        datetime.now(UTC) - timedelta(days=2),
                        datetime.now(UTC) - timedelta(days=1),
                        digest,
                    ),
                )
            else:
                connection.execute("UPDATE users SET status = 'blocked' WHERE id = %s", (owner.id,))
    subject = uuid4().hex
    with pytest.raises(PermissionError):
        login(database, subject=subject, link_user_id=owner.id, link_session_digest=digest)
    with database.pool.connection() as connection:
        assert (
            connection.execute(
                "SELECT count(*) AS n FROM tid_identities WHERE tid_subject = %s",
                (subject,),
            ).fetchone()["n"]
            == 0
        )


def test_logout_committed_during_link_callback_prevents_identity_creation(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner, _, digest = login(database, provider="vkid")
    subject = uuid4().hex
    with ThreadPoolExecutor(max_workers=1) as workers:
        with database.pool.connection() as connection:
            # Hold the session row through a concurrent callback. PostgreSQL must
            # re-evaluate revoked_at after waiting for this transaction to commit.
            connection.execute(
                "UPDATE sessions SET revoked_at = now() WHERE token_digest = %s",
                (digest,),
            )
            attempt = workers.submit(
                login,
                database,
                subject=subject,
                link_user_id=owner.id,
                link_session_digest=digest,
            )
        with pytest.raises(PermissionError, match="session_expired"):
            attempt.result(timeout=10)
    assert database.identity_providers(owner.id) == ["vkid"]


def test_self_service_sessions_are_owner_scoped_and_preserve_current_session(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    subject = uuid4().hex
    owner, _, current = login(database, subject=subject)
    _, _, previous = login(database, subject=subject)
    other, _, foreign = login(database)
    listing = database.active_sessions(owner.id, current)
    assert listing["total"] == 2 and listing["truncated"] is False
    assert listing["sessions"][0]["current"] is True
    assert listing["sessions"][0]["auth_provider"] == "tid"
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


def test_identity_unlink_requires_recent_other_identity_and_revokes_removed_provider_sessions(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner, _, vk_session = login(database, provider="vkid")
    _, _, tid_session = login(
        database, link_user_id=owner.id, link_session_digest=vk_session,
    )
    store = WorkspaceStore(database)
    store.save_preferences(owner.id, default_preferences(), expected_version=0)
    assert database.unlink_identity(
        owner.id, tid_session, "vkid", enabled_providers=frozenset({"tid", "vkid"}),
    )
    assert database.identity_providers(owner.id) == ["tid"]
    assert database.refresh_session_digest(vk_session, session_ttl_seconds=3600) is None
    assert database.refresh_session_digest(tid_session, session_ttl_seconds=3600) == owner
    assert store.preferences(owner.id)["version"] == 1
    assert not database.unlink_identity(
        owner.id, tid_session, "vkid", enabled_providers=frozenset({"tid", "vkid"}),
    )
    with pytest.raises(PermissionError, match="reauthentication_required"):
        database.unlink_identity(
            owner.id, tid_session, "tid", enabled_providers=frozenset({"tid", "vkid"}),
        )
    # Replacement uses the remaining authenticated identity and the existing
    # explicit OAuth-link flow; no intermediate step can leave zero identities.
    _, _, new_vk = login(
        database, provider="vkid", link_user_id=owner.id, link_session_digest=tid_session,
        registration_enabled=False,
    )
    assert set(database.identity_providers(owner.id)) == {"tid", "vkid"}
    assert database.refresh_session_digest(new_vk, session_ttl_seconds=3600) == owner


@pytest.mark.parametrize(
    "condition", ["stale", "future", "legacy", "disabled", "foreign", "revoked"],
)
def test_unlink_rejects_unproven_or_unavailable_alternative_identity(
    workspace_database: tuple[Database, str, str], condition: str,
) -> None:
    database = workspace_database[0]
    owner, _, vk_session = login(database, provider="vkid")
    _, _, tid_session = login(database, link_user_id=owner.id, link_session_digest=vk_session)
    enabled = frozenset({"tid", "vkid"})
    if condition in {"stale", "future", "legacy"}:
        with database.pool.connection() as conn:
            if condition == "legacy":
                conn.execute(
                    "UPDATE sessions SET authenticated_at = NULL, authenticated_provider = NULL "
                    "WHERE token_digest = %s", (tid_session,),
                )
            else:
                instant = datetime.now(UTC) + timedelta(minutes=6 if condition == "future" else -6)
                conn.execute(
                    "UPDATE sessions SET authenticated_at = %s WHERE token_digest = %s",
                    (instant, tid_session),
                )
    elif condition == "disabled":
        enabled = frozenset({"vkid"})
    elif condition == "foreign":
        _, _, tid_session = login(database)
    else:
        database.revoke_session(tid_session)
    with pytest.raises(PermissionError):
        database.unlink_identity(owner.id, tid_session, "vkid", enabled_providers=enabled)
    assert set(database.identity_providers(owner.id)) == {"tid", "vkid"}


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
            "INSERT INTO job_runs (user_id, job_type, scheduled_for, status, requested_at) "
            "VALUES (%s, 'portfolio_refresh', NULL, 'queued', now() - interval '31 minutes')",
            (other.id,),
        )
    result = database.operational_metrics(owner.id, current, configured_operator_id=owner.id)
    assert result["observer"]["stale"] >= 1
    assert result["status"] == "attention"
    assert str(owner.id) not in str(result) and str(other.id) not in str(result)
    assert "token" not in str(result) and "digest" not in str(result)
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
