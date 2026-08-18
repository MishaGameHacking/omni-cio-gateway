from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from omni_cio.web.identity_v1 import IdentityProviderV1, VerifiedExternalIdentityV1
from omni_cio.web.product_auth_v1 import (
    ProductAuthenticationError,
    ProductAuthenticationServiceV1,
)
from omni_cio.web.product_identity_v1 import ProductAccountScopeV1, ProductIdentityError
from omni_cio.web.session_v1 import SessionRegistryV1


NOW = datetime(2026, 8, 18, 20, 30, tzinfo=timezone.utc)
USER_A = ProductAccountScopeV1(
    user_id="user:v1:user_a",
    tenant_id="tenant:v1:tenant_a",
)
USER_B = ProductAccountScopeV1(
    user_id="user:v1:user_b",
    tenant_id="tenant:v1:tenant_b",
)


class _FakeIdentities:
    def __init__(self, scope: ProductAccountScopeV1 | None) -> None:
        self.scope = scope
        self.links: list[tuple[ProductAccountScopeV1, VerifiedExternalIdentityV1]] = []

    def resolve_or_register(
        self,
        identity: VerifiedExternalIdentityV1,
        *,
        now: datetime,
    ) -> ProductAccountScopeV1:
        del identity, now
        if self.scope is None:
            raise ProductIdentityError("PRODUCT_REGISTRATION_DISABLED")
        return self.scope

    def link_verified(
        self,
        scope: ProductAccountScopeV1,
        identity: VerifiedExternalIdentityV1,
        *,
        now: datetime,
    ) -> None:
        del now
        self.links.append((scope, identity))


def _identity() -> VerifiedExternalIdentityV1:
    return VerifiedExternalIdentityV1(
        provider=IdentityProviderV1.TELEGRAM,
        subject="telegram-stable-subject",
    )


def _service(
    identities: _FakeIdentities,
    sessions: SessionRegistryV1,
) -> ProductAuthenticationServiceV1:
    return ProductAuthenticationServiceV1(
        identities=identities,  # type: ignore[arg-type]
        sessions=sessions,
        now=lambda: NOW,
    )


def test_verified_external_identity_mints_only_internal_account_scope() -> None:
    sessions = SessionRegistryV1()
    token, scope = _service(_FakeIdentities(USER_A), sessions).authenticate_verified(
        _identity()
    )

    assert scope.user_id == USER_A.user_id
    assert scope.tenant_id == USER_A.tenant_id
    assert sessions.resolve(token, now=NOW + timedelta(seconds=1)) is not None
    assert "telegram-stable-subject" not in repr(scope)


def test_authentication_rotates_existing_session_before_new_session() -> None:
    sessions = SessionRegistryV1()
    old_token, _ = sessions.create(
        user_id=USER_A.user_id,
        tenant_id=USER_A.tenant_id,
        now=NOW - timedelta(minutes=1),
    )
    new_token, _ = _service(_FakeIdentities(USER_A), sessions).authenticate_verified(
        _identity(),
        current_session_token=old_token,
    )

    assert new_token != old_token
    assert sessions.resolve(old_token, now=NOW + timedelta(seconds=1)) is None
    assert sessions.resolve(new_token, now=NOW + timedelta(seconds=1)) is not None


def test_unknown_identity_cannot_create_session_when_registration_is_disabled() -> None:
    sessions = SessionRegistryV1()
    with pytest.raises(ProductAuthenticationError, match="PRODUCT_REGISTRATION_DISABLED"):
        _service(_FakeIdentities(None), sessions).authenticate_verified(_identity())
    assert sessions.stored_plaintext_token_count() == 0


def test_linking_requires_existing_authenticated_session() -> None:
    sessions = SessionRegistryV1()
    identities = _FakeIdentities(USER_A)
    service = _service(identities, sessions)

    with pytest.raises(ProductAuthenticationError, match="AUTHENTICATED_ACCOUNT_REQUIRED"):
        service.link_verified_to_authenticated_account(
            current_session_token="forged-session",
            identity=_identity(),
        )
    assert identities.links == []


def test_linking_uses_server_session_scope_not_client_selector() -> None:
    sessions = SessionRegistryV1()
    token, _ = sessions.create(
        user_id=USER_A.user_id,
        tenant_id=USER_A.tenant_id,
        now=NOW,
    )
    identities = _FakeIdentities(USER_B)
    scope = _service(identities, sessions).link_verified_to_authenticated_account(
        current_session_token=token,
        identity=VerifiedExternalIdentityV1(
            provider=IdentityProviderV1.VK_ID,
            subject="vk-stable-subject",
        ),
    )

    assert scope == USER_A
    assert identities.links[0][0] == USER_A


def test_revoke_all_remains_user_scoped_across_two_tenants() -> None:
    sessions = SessionRegistryV1()
    token_a, _ = sessions.create(
        user_id=USER_A.user_id,
        tenant_id=USER_A.tenant_id,
        now=NOW,
    )
    token_b, _ = sessions.create(
        user_id=USER_B.user_id,
        tenant_id=USER_B.tenant_id,
        now=NOW,
    )

    assert sessions.revoke_all_for_user(USER_A.user_id, now=NOW + timedelta(seconds=1)) == 1
    assert sessions.resolve(token_a, now=NOW + timedelta(seconds=2)) is None
    assert sessions.resolve(token_b, now=NOW + timedelta(seconds=2)) is not None
