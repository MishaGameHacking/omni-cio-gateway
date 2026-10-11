"""Real PostgreSQL proof reuse, account races, legacy users and link revocation."""

from __future__ import annotations

import os
import secrets
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from test_email_auth_postgres import VERSIONS, legacy_login, login
from test_workspace_postgres import workspace_database as workspace_database

from omnicio.social_store import SocialAuthStore

pytestmark = pytest.mark.skipif(not os.environ.get("OMNICIO_TEST_DATABASE_URL"),
                                reason="ephemeral PostgreSQL is required")


@dataclass
class Flow:
    id: UUID
    secret: bytes
    state: bytes


def proof(store, provider="telegram", subject=None, owner=None, session=None):
    flow = Flow(uuid4(), secrets.token_bytes(32), secrets.token_bytes(32))
    store.create(flow_id=flow.id, provider=provider, purpose="link" if owner else "login",
                 flow_digest=flow.secret, state_digest=flow.state, secrets_ciphertext=b"encrypted",
                 android_package="ru.omnicio.app", user_id=owner.id if owner else None,
                 session_digest=session)
    assert store.claim(provider, flow.state)
    assert store.claim(provider, flow.state) is None
    store.verified(flow.id, subject or str(uuid4().int))
    return flow


def finish(store, flow, **changes):
    return store.finish(**{"flow_id": flow.id, "flow_digest": flow.secret,
                           "token_digest": secrets.token_bytes(32), "client_ip_hash": b"i" * 32,
                           "session_ttl_seconds": 3600, "legal_versions": VERSIONS,
                           "current_session_digest": None, **changes})


def test_create_login_consent_replay_and_cookie_binding(workspace_database):
    database, _, _ = workspace_database
    store = SocialAuthStore(database)
    subject = str(uuid4().int)
    flow = proof(store, subject=subject)
    assert finish(store, flow, flow_digest=b"x" * 32) == "social_flow_expired"
    assert finish(store, flow, legal_versions={}) == "registration_required"
    token = secrets.token_bytes(32)
    owner, created = finish(store, flow, token_digest=token)
    assert created
    assert database.refresh_session_digest(token, session_ttl_seconds=3600) == owner
    assert database.has_legal_versions(owner.id, VERSIONS)
    assert finish(store, flow) == "social_flow_failed"
    another = proof(store, subject=subject)
    same, created = finish(store, another, legal_versions={})
    assert same.id == owner.id
    assert not created
    assert store.identities(owner.id)["providers"] == ["telegram"]


def test_two_first_logins_share_one_account(workspace_database):
    database, _, _ = workspace_database
    store = SocialAuthStore(database)
    subject = str(uuid4().int)
    flows = [proof(store, subject=subject), proof(store, subject=subject)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda flow: finish(store, flow), flows))
    assert len({owner.id for owner, _ in results}) == 1
    assert sum(created for _, created in results) == 1


def test_link_preserves_owner_requires_live_session_and_rejects_conflicts(workspace_database):
    database, _, _ = workspace_database
    store = SocialAuthStore(database)
    owner, _, session = login(database)
    subject = str(uuid4().int)
    flow = proof(store, owner=owner, session=session, subject=subject)
    assert finish(store, flow, current_session_digest=b"x" * 32) == "social_session_changed"
    linked, created = finish(store, flow, current_session_digest=session)
    assert linked.id == owner.id
    assert not created
    assert database.refresh_session_digest(session, session_ttl_seconds=3600) is None
    assert store.identities(owner.id)["providers"] == ["email", "telegram"]
    other, _, other_session = login(database)
    conflict = proof(store, owner=other, session=other_session, subject=subject)
    result = finish(store, conflict, current_session_digest=other_session)
    assert result == "identity_already_linked"
    assert store.identities(other.id)["providers"] == ["email"]
    revoked = proof(store, owner=other, session=other_session)
    database.revoke_session(other_session)
    with pytest.raises(PermissionError):
        finish(store, revoked, current_session_digest=other_session)


def test_existing_vk_login_keeps_legacy_account_and_role(workspace_database):
    database, _, _ = workspace_database
    store = SocialAuthStore(database)
    owner, _ = legacy_login(database)
    with database.pool.connection() as conn:
        row = conn.execute("SELECT vk_user_id FROM vkid_identities WHERE user_id = %s",
                           (owner.id,)).fetchone()
    flow = proof(store, provider="vkid", subject=row["vk_user_id"])
    authenticated, created = finish(store, flow, legal_versions={})
    assert authenticated == owner
    assert not created


def test_expired_cancelled_blocked_and_changed_session_do_not_grant_login(workspace_database):
    database, _, _ = workspace_database
    store = SocialAuthStore(database)
    flow = proof(store)
    store.cancel(flow.id, flow.secret)
    assert finish(store, flow) == "social_flow_failed"
    changed = proof(store)
    assert finish(store, changed, current_session_digest=b"c" * 32) == "social_session_changed"
    expired = proof(store)
    with database.pool.connection() as conn:
        conn.execute("UPDATE social_auth_flows SET created_at = now() - interval '1 hour', "
                     "expires_at = now() - interval '1 second' WHERE id = %s", (expired.id,))
    assert finish(store, expired) == "social_flow_expired"
    subject = str(uuid4().int)
    owner, _ = finish(store, proof(store, subject=subject))
    with database.pool.connection() as conn:
        conn.execute("UPDATE users SET status = 'blocked' WHERE id = %s", (owner.id,))
    assert finish(store, proof(store, subject=subject)) == "social_account_unavailable"
