from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from omni_cio.web.identity_v1 import IdentityProviderV1, VerifiedExternalIdentityV1
from omni_cio.web.product_identity_v1 import (
    ProductAccountScopeV1,
    ProductAuthenticationServiceV1,
    ProductIdentityError,
    ProductIdentityRepositoryLike,
    ProductIdentityServiceV1,
    protected_identity_binding_hmac_sha256,
)
from omni_cio.web.session_v1 import SessionRegistryV1


NOW = datetime(2026, 8, 19, 4, 0, tzinfo=timezone.utc)
BINDING_KEY = bytes([120]) * 32
OTHER_BINDING_KEY = bytes([121]) * 32
SCOPE_A = ProductAccountScopeV1(
    user_id="user:v1:product_a",
    tenant_id="tenant:v1:product_a",
)
SCOPE_B = ProductAccountScopeV1(
    user_id="user:v1:product_b",
    tenant_id="tenant:v1:product_b",
)
OWNER_SCOPE = ProductAccountScopeV1(
    user_id="user:v1:owner",
    tenant_id="tenant:v1:owner",
)


def identity(provider: IdentityProviderV1, subject: str) -> VerifiedExternalIdentityV1:
    return VerifiedExternalIdentityV1(provider=provider, subject=subject)


class FakeIdentityRepository(ProductIdentityRepositoryLike):
    def __init__(
        self,
        scopes: tuple[ProductAccountScopeV1, ...] = (SCOPE_A, SCOPE_B),
    ) -> None:
        self._available = list(scopes)
        self._bindings: dict[tuple[IdentityProviderV1, str], ProductAccountScopeV1] = {}
        self._provider_by_scope: set[tuple[str, IdentityProviderV1]] = set()

    def resolve_verified_identity(
        self,
        external_identity: VerifiedExternalIdentityV1,
    ) -> ProductAccountScopeV1 | None:
        return self._bindings.get(
            (external_identity.provider, external_identity.subject)
        )

    def create_account(
        self,
        external_identity: VerifiedExternalIdentityV1,
        *,
        now: datetime,
    ) -> ProductAccountScopeV1:
        assert now.tzinfo is not None
        existing = self.resolve_verified_identity(external_identity)
        if existing is not None:
            return existing
        if not self._available:
            raise AssertionError("fake account scopes exhausted")
        scope = self._available.pop(0)
        self._bindings[(external_identity.provider, external_identity.subject)] = scope
        self._provider_by_scope.add((scope.user_id, external_identity.provider))
        return scope

    def link_identity(
        self,
        scope: ProductAccountScopeV1,
        external_identity: VerifiedExternalIdentityV1,
        *,
        now: datetime,
    ) -> None:
        assert now.tzinfo is not None
        key = (external_identity.provider, external_identity.subject)
        existing = self._bindings.get(key)
        if existing is not None:
            if existing != scope:
                raise ProductIdentityError("IDENTITY_ALREADY_BOUND")
            return
        provider_key = (scope.user_id, external_identity.provider)
        if provider_key in self._provider_by_scope:
            raise ProductIdentityError("PROVIDER_ALREADY_LINKED")
        self._bindings[key] = scope
        self._provider_by_scope.add(provider_key)


def test_provider_subject_binding_is_keyed_not_enumerable_plain_hash() -> None:
    external_identity = identity(IdentityProviderV1.TELEGRAM, "123456789")
    digest = protected_identity_binding_hmac_sha256(
        external_identity,
        binding_key=BINDING_KEY,
    )
    other_key_digest = protected_identity_binding_hmac_sha256(
        external_identity,
        binding_key=OTHER_BINDING_KEY,
    )

    assert len(digest) == 64
    assert digest != external_identity.binding_fingerprint_sha256()
    assert digest != other_key_digest
    assert external_identity.subject not in digest


def test_binding_key_is_bounded_and_never_optional() -> None:
    external_identity = identity(IdentityProviderV1.VK_ID, "vk-subject-001")
    with pytest.raises(ValueError, match="PRODUCT_IDENTITY_BINDING_KEY_TOO_SHORT"):
        protected_identity_binding_hmac_sha256(
            external_identity,
            binding_key=b"too-short",
        )


def test_registration_is_fail_closed_by_default() -> None:
    repository = FakeIdentityRepository()
    service = ProductIdentityServiceV1(repository)

    assert service.registration_enabled is False
    with pytest.raises(ProductIdentityError, match="PUBLIC_REGISTRATION_DISABLED"):
        service.authenticate(
            identity(IdentityProviderV1.TELEGRAM, "new-user"),
            now=NOW,
        )


def test_historical_owner_scope_cannot_become_product_identity() -> None:
    repository = FakeIdentityRepository(scopes=(OWNER_SCOPE,))
    service = ProductIdentityServiceV1(repository, registration_enabled=True)
    telegram = identity(IdentityProviderV1.TELEGRAM, "owner-product-attempt")

    with pytest.raises(ProductIdentityError, match="OWNER_IDENTITY_RESERVED"):
        service.authenticate(telegram, now=NOW)
    with pytest.raises(ProductIdentityError, match="OWNER_IDENTITY_RESERVED"):
        service.link_authenticated_identity(
            OWNER_SCOPE,
            identity(IdentityProviderV1.VK_ID, "owner-link-attempt"),
            now=NOW + timedelta(seconds=1),
        )


def test_registration_maps_external_identity_to_stable_internal_account() -> None:
    repository = FakeIdentityRepository()
    service = ProductIdentityServiceV1(repository, registration_enabled=True)
    telegram = identity(IdentityProviderV1.TELEGRAM, "tg-user-a")

    first = service.authenticate(telegram, now=NOW)
    second = service.authenticate(telegram, now=NOW + timedelta(seconds=1))

    assert first == SCOPE_A
    assert second == SCOPE_A
    assert first.user_id != telegram.subject
    assert first.tenant_id != telegram.subject


def test_second_provider_can_link_only_to_authenticated_account() -> None:
    repository = FakeIdentityRepository()
    service = ProductIdentityServiceV1(repository, registration_enabled=True)
    telegram_a = identity(IdentityProviderV1.TELEGRAM, "tg-a")
    telegram_b = identity(IdentityProviderV1.TELEGRAM, "tg-b")
    vk_a = identity(IdentityProviderV1.VK_ID, "vk-a")

    scope_a = service.authenticate(telegram_a, now=NOW)
    scope_b = service.authenticate(telegram_b, now=NOW + timedelta(seconds=1))
    service.link_authenticated_identity(scope_a, vk_a, now=NOW + timedelta(seconds=2))

    assert service.authenticate(vk_a, now=NOW + timedelta(seconds=3)) == scope_a
    with pytest.raises(ProductIdentityError, match="IDENTITY_ALREADY_BOUND"):
        service.link_authenticated_identity(
            scope_b,
            vk_a,
            now=NOW + timedelta(seconds=4),
        )


def test_same_provider_cannot_be_silently_merged_into_one_account() -> None:
    repository = FakeIdentityRepository()
    service = ProductIdentityServiceV1(repository, registration_enabled=True)
    scope = service.authenticate(
        identity(IdentityProviderV1.TELEGRAM, "tg-a"),
        now=NOW,
    )

    with pytest.raises(ProductIdentityError, match="PROVIDER_ALREADY_LINKED"):
        service.link_authenticated_identity(
            scope,
            identity(IdentityProviderV1.TELEGRAM, "tg-other"),
            now=NOW + timedelta(seconds=1),
        )


def test_verified_login_rotates_server_side_session_and_preserves_tenant_scope() -> (
    None
):
    repository = FakeIdentityRepository()
    identities = ProductIdentityServiceV1(repository, registration_enabled=True)
    telegram = identity(IdentityProviderV1.TELEGRAM, "tg-a")
    scope = identities.authenticate(telegram, now=NOW)
    sessions = SessionRegistryV1()
    old_token, _ = sessions.create(
        user_id=scope.user_id,
        tenant_id=scope.tenant_id,
        now=NOW,
    )
    authentication = ProductAuthenticationServiceV1(
        identities=identities,
        sessions=sessions,
    )

    new_token, session_scope = authentication.authenticate_verified_identity(
        telegram,
        current_session_token=old_token,
        now=NOW + timedelta(minutes=1),
    )

    assert new_token != old_token
    assert session_scope.user_id == scope.user_id
    assert session_scope.tenant_id == scope.tenant_id
    assert sessions.resolve(old_token, now=NOW + timedelta(minutes=2)) is None
    assert sessions.resolve(new_token, now=NOW + timedelta(minutes=2)) is not None
    assert sessions.stored_plaintext_token_count() == 0


def test_split_login_boundary_separates_untrusted_old_token_from_fresh_issue() -> None:
    repository = FakeIdentityRepository()
    identities = ProductIdentityServiceV1(repository, registration_enabled=True)
    telegram = identity(IdentityProviderV1.TELEGRAM, "tg-split")
    scope = identities.authenticate(telegram, now=NOW)
    sessions = SessionRegistryV1()
    old_token, _ = sessions.create(
        user_id=scope.user_id,
        tenant_id=scope.tenant_id,
        now=NOW,
    )
    authentication = ProductAuthenticationServiceV1(
        identities=identities,
        sessions=sessions,
    )
    rotated_at = NOW + timedelta(minutes=1)

    resolved_scope = authentication.resolve_verified_identity(
        telegram,
        now=rotated_at,
    )
    assert resolved_scope == scope
    assert sessions.resolve(old_token, now=rotated_at) is not None

    assert authentication.revoke_session(old_token, now=rotated_at)
    assert sessions.resolve(old_token, now=rotated_at) is None

    new_token, session_scope = authentication.issue_session(
        resolved_scope,
        now=rotated_at,
    )
    assert new_token != old_token
    assert session_scope.user_id == scope.user_id
    assert session_scope.tenant_id == scope.tenant_id
    assert sessions.resolve(new_token, now=rotated_at) is not None
    assert sessions.stored_plaintext_token_count() == 0


def test_provider_link_uses_resolved_server_session_scope() -> None:
    repository = FakeIdentityRepository()
    identities = ProductIdentityServiceV1(repository, registration_enabled=True)
    telegram = identity(IdentityProviderV1.TELEGRAM, "tg-a")
    scope = identities.authenticate(telegram, now=NOW)
    sessions = SessionRegistryV1()
    token, _ = sessions.create(
        user_id=scope.user_id,
        tenant_id=scope.tenant_id,
        now=NOW,
    )
    resolved = sessions.resolve(token, now=NOW + timedelta(seconds=1))
    assert resolved is not None
    authentication = ProductAuthenticationServiceV1(
        identities=identities,
        sessions=sessions,
    )
    vk = identity(IdentityProviderV1.VK_ID, "vk-a")

    authentication.link_verified_identity(
        resolved,
        vk,
        now=NOW + timedelta(seconds=2),
    )

    assert identities.authenticate(vk, now=NOW + timedelta(seconds=3)) == scope
