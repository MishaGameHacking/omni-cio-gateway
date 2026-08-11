from __future__ import annotations

from datetime import datetime, timedelta, timezone

from omni_cio.contracts.v1.domain import OWNER_TENANT_ID, OWNER_USER_ID
from omni_cio.web.session_v1 import SessionPolicyV1, SessionRegistryV1


NOW = datetime(2026, 8, 11, 7, 0, tzinfo=timezone.utc)


def test_session_token_is_opaque_and_plaintext_is_not_retained() -> None:
    registry = SessionRegistryV1()
    token, scope = registry.create(
        user_id=OWNER_USER_ID,
        tenant_id=OWNER_TENANT_ID,
        now=NOW,
    )

    assert len(token) >= 40
    assert scope.user_id == OWNER_USER_ID
    assert scope.tenant_id == OWNER_TENANT_ID
    assert registry.stored_plaintext_token_count() == 0
    assert registry.resolve(token, now=NOW + timedelta(minutes=1)) is not None


def test_unknown_revoked_idle_and_absolute_sessions_fail_closed() -> None:
    registry = SessionRegistryV1(
        SessionPolicyV1(
            idle_lifetime=timedelta(minutes=10),
            absolute_lifetime=timedelta(minutes=30),
        )
    )
    token, _ = registry.create(
        user_id=OWNER_USER_ID,
        tenant_id=OWNER_TENANT_ID,
        now=NOW,
    )
    assert registry.resolve("unknown", now=NOW + timedelta(minutes=1)) is None
    assert registry.resolve(token, now=NOW + timedelta(minutes=9)) is not None
    assert registry.resolve(token, now=NOW + timedelta(minutes=18)) is not None
    assert registry.resolve(token, now=NOW + timedelta(minutes=31)) is None

    token2, _ = registry.create(
        user_id=OWNER_USER_ID,
        tenant_id=OWNER_TENANT_ID,
        now=NOW,
    )
    assert registry.revoke(token2, now=NOW + timedelta(minutes=1)) is True
    assert registry.resolve(token2, now=NOW + timedelta(minutes=2)) is None


def test_revoke_all_sessions_is_user_scoped() -> None:
    registry = SessionRegistryV1()
    first, _ = registry.create(
        user_id=OWNER_USER_ID,
        tenant_id=OWNER_TENANT_ID,
        now=NOW,
    )
    second, _ = registry.create(
        user_id=OWNER_USER_ID,
        tenant_id=OWNER_TENANT_ID,
        now=NOW + timedelta(seconds=1),
    )

    assert registry.revoke_all_for_user(OWNER_USER_ID, now=NOW + timedelta(minutes=1)) == 2
    assert registry.resolve(first, now=NOW + timedelta(minutes=2)) is None
    assert registry.resolve(second, now=NOW + timedelta(minutes=2)) is None
