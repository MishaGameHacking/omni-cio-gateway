"""New identity and replay invariants against disposable PostgreSQL only."""

from __future__ import annotations

import os
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

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
