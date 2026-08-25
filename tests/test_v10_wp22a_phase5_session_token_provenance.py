from __future__ import annotations

from datetime import datetime, timezone

import pytest

from omni_cio.web.identity_v1 import VerifiedExternalIdentityV1
from omni_cio.web.product_identity_v1 import (
    ProductAccountScopeV1,
    ProductAuthenticationServiceV1,
    ProductIdentityRepositoryLike,
    ProductIdentityServiceV1,
)
from omni_cio.web.session_v1 import SessionRegistryV1, new_session_token_v1


NOW = datetime(2026, 8, 25, 20, 30, tzinfo=timezone.utc)
SCOPE = ProductAccountScopeV1(
    user_id="user:v1:session_provenance",
    tenant_id="tenant:v1:session_provenance",
)


class UnusedIdentityRepository(ProductIdentityRepositoryLike):
    def resolve_verified_identity(
        self,
        identity: VerifiedExternalIdentityV1,
    ) -> ProductAccountScopeV1 | None:
        del identity
        return None

    def create_account(
        self,
        identity: VerifiedExternalIdentityV1,
        *,
        now: datetime,
    ) -> ProductAccountScopeV1:
        del identity, now
        return SCOPE

    def link_identity(
        self,
        scope: ProductAccountScopeV1,
        identity: VerifiedExternalIdentityV1,
        *,
        now: datetime,
    ) -> None:
        del scope, identity, now


def test_preminted_session_token_binds_without_plaintext_storage() -> None:
    sessions = SessionRegistryV1()
    identities = ProductIdentityServiceV1(UnusedIdentityRepository())
    authentication = ProductAuthenticationServiceV1(
        identities=identities,
        sessions=sessions,
    )

    token = new_session_token_v1()
    scope = authentication.bind_session(token, SCOPE, now=NOW)

    assert len(token) == 43
    assert scope.user_id == SCOPE.user_id
    assert scope.tenant_id == SCOPE.tenant_id
    assert sessions.resolve(token, now=NOW) is not None
    assert sessions.stored_plaintext_token_count() == 0


def test_session_bind_rejects_non_csprng_token_shape_and_duplicate_binding() -> None:
    sessions = SessionRegistryV1()
    with pytest.raises(ValueError, match="SESSION_TOKEN_INVALID"):
        sessions.bind(
            token="attacker-controlled",
            user_id=SCOPE.user_id,
            tenant_id=SCOPE.tenant_id,
            now=NOW,
        )

    token = new_session_token_v1()
    sessions.bind(
        token=token,
        user_id=SCOPE.user_id,
        tenant_id=SCOPE.tenant_id,
        now=NOW,
    )
    with pytest.raises(ValueError, match="SESSION_TOKEN_ALREADY_BOUND"):
        sessions.bind(
            token=token,
            user_id=SCOPE.user_id,
            tenant_id=SCOPE.tenant_id,
            now=NOW,
        )
