from __future__ import annotations

import base64
import os
from uuid import UUID

import pytest
from cryptography.fernet import Fernet

from omnicio.config import Settings
from omnicio.db import (
    RegistrationCapacityError,
    RegistrationClosedError,
    UserRecord,
    live_execution_lock_key,
)
from omnicio.service import (
    AccountDeletionRejected,
    AuthService,
    LoginUnavailable,
    RegistrationCapacityReached,
    RegistrationClosed,
)


class FakeDatabase:
    def __init__(self) -> None:
        self.session_digest: bytes | None = None
        self.refreshed_ttl: int | None = None
        self.completed_vk_user_id: str | None = None
        self.accepted_versions: dict[str, str] | None = None
        self.registration_enabled: bool | None = None
        self.registration_max_users: int | None = None
        self.login_error: RuntimeError | None = None
        self.deleted_user_id: UUID | None = None
        self.user = UserRecord(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            public_id=1,
            status="active",
            role="user",
        )

    def complete_vkid_login(self, **kwargs):
        if self.login_error is not None:
            raise self.login_error
        self.completed_vk_user_id = kwargs["vk_user_id"]
        self.accepted_versions = kwargs["legal_versions"]
        self.registration_enabled = kwargs["registration_enabled"]
        self.registration_max_users = kwargs["registration_max_users"]
        self.session_digest = kwargs["session_token_digest"]
        return self.user, True

    def refresh_session_digest(
        self,
        token_digest,
        *,
        session_ttl_seconds,
    ):
        self.refreshed_ttl = session_ttl_seconds
        if token_digest == self.session_digest:
            return self.user
        return None

    def delete_user_account(self, user_id: UUID) -> bool:
        self.deleted_user_id = user_id
        return True

    def revoke_session(self, token_digest):
        if token_digest == self.session_digest:
            self.session_digest = None


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "postgresql://example.invalid/db",
        "ip_key": base64.urlsafe_b64encode(os.urandom(32)).decode("ascii"),
        "broker_token_crypto_key": Fernet.generate_key().decode("ascii"),
        "vkid_flow_crypto_key": Fernet.generate_key().decode("ascii"),
        "vkid_app_id": "123456",
        "vkid_login_enabled": True,
        "registration_enabled": True,
        "registration_max_users": 2,
        "privacy_version": "2026-10-02-v5",
        "consent_version": "2026-10-02-v5",
        "terms_version": "2026-10-02-v5",
        "vkid_flow_ttl_seconds": 600,
        "session_ttl_seconds": 34_560_000,
        "portfolio_live_execution_enabled": False,
        "portfolio_live_max_order_rub": 10_000,
        "portfolio_live_max_daily_rub": 20_000,
    }
    values.update(overrides)
    return Settings(**values)


def test_live_execution_cleanup_lock_is_stable_and_user_scoped() -> None:
    user_id = UUID("00000000-0000-0000-0000-000000000123")
    assert live_execution_lock_key(user_id) == (
        "portfolio-live-execution:00000000-0000-0000-0000-000000000123"
    )


def test_vkid_login_creates_user_session_without_owner_binding() -> None:
    db = FakeDatabase()
    auth = AuthService(settings(), db)

    result = auth.complete_vkid_login(
        vk_user_id="111111111",
        client_ip="203.0.113.11",
        accepted_legal_versions=auth.legal_versions(),
    )

    assert result.public_id == "000000001"
    assert result.created is True
    assert db.completed_vk_user_id == "111111111"
    assert db.accepted_versions == auth.legal_versions()
    assert db.registration_enabled is True
    assert db.registration_max_users == 2
    assert auth.refresh_session(result.session_token) == db.user
    assert db.refreshed_ttl == 34_560_000


def test_unknown_identity_fails_closed_when_registration_is_closed() -> None:
    db = FakeDatabase()
    db.login_error = RegistrationClosedError("registration is closed")
    auth = AuthService(settings(registration_enabled=False), db)

    accepted_versions = auth.legal_versions()
    with pytest.raises(RegistrationClosed):
        auth.complete_vkid_login(
            vk_user_id="111111111",
            client_ip="203.0.113.11",
            accepted_legal_versions=accepted_versions,
        )


def test_unknown_identity_fails_closed_when_capacity_is_full() -> None:
    db = FakeDatabase()
    db.login_error = RegistrationCapacityError("registration capacity reached")
    auth = AuthService(settings(registration_max_users=2), db)

    accepted_versions = auth.legal_versions()
    with pytest.raises(RegistrationCapacityReached):
        auth.complete_vkid_login(
            vk_user_id="222222222",
            client_ip="203.0.113.12",
            accepted_legal_versions=accepted_versions,
        )


def test_vkid_login_rejects_malformed_provider_subject() -> None:
    db = FakeDatabase()
    auth = AuthService(settings(), db)

    accepted_versions = auth.legal_versions()
    with pytest.raises(LoginUnavailable):
        auth.complete_vkid_login(
            vk_user_id="not-a-vk-id",
            client_ip="203.0.113.10",
            accepted_legal_versions=accepted_versions,
        )

    assert db.session_digest is None


def test_vkid_login_rejects_stale_legal_versions() -> None:
    db = FakeDatabase()
    auth = AuthService(settings(), db)

    with pytest.raises(LoginUnavailable):
        auth.complete_vkid_login(
            vk_user_id="111111111",
            client_ip="203.0.113.10",
            accepted_legal_versions={
                "privacy_policy": "old",
                "personal_data_consent": "old",
                "terms": "old",
            },
        )

    assert db.session_digest is None


def test_self_service_account_deletion_requires_exact_public_id() -> None:
    db = FakeDatabase()
    auth = AuthService(settings(), db)

    assert auth.delete_account(db.user, "000000001") is True
    assert db.deleted_user_id == db.user.id


def test_self_service_account_deletion_rejects_wrong_public_id() -> None:
    db = FakeDatabase()
    auth = AuthService(settings(), db)

    with pytest.raises(AccountDeletionRejected):
        auth.delete_account(db.user, "000000002")

    assert db.deleted_user_id is None


def test_access_mode_reflects_registration_gate() -> None:
    assert settings(registration_enabled=True).access_mode == "limited_registration"
    assert settings(registration_enabled=False).access_mode == "closed"


def test_session_fails_closed_when_vkid_is_not_configured() -> None:
    db = FakeDatabase()
    auth = AuthService(settings(vkid_login_enabled=False), db)

    assert auth.refresh_session("anything") is None


@pytest.mark.parametrize("app_id", ["app", "0", ""])
def test_session_fails_closed_for_invalid_vkid_app_id(app_id: str) -> None:
    db = FakeDatabase()
    auth = AuthService(settings(vkid_app_id=app_id), db)

    assert auth.refresh_session("anything") is None
