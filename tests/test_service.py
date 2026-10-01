from __future__ import annotations

import base64
import os
from uuid import UUID

import pytest
from cryptography.fernet import Fernet

from omnicio.config import Settings
from omnicio.db import UserRecord
from omnicio.service import AuthService, LoginUnavailable, OwnerAccessDenied


class FakeDatabase:
    def __init__(self) -> None:
        self.session_digest: bytes | None = None
        self.refreshed_owner_vk_id: str | None = None
        self.refreshed_ttl: int | None = None
        self.completed_vk_user_id: str | None = None
        self.accepted_versions: dict[str, str] | None = None
        self.user = UserRecord(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            public_id=1,
            status="active",
        )

    def complete_vkid_login(self, **kwargs):
        self.completed_vk_user_id = kwargs["vk_user_id"]
        self.accepted_versions = kwargs["legal_versions"]
        self.session_digest = kwargs["session_token_digest"]
        return self.user, True

    def refresh_session_digest(
        self,
        token_digest,
        *,
        owner_vk_id,
        session_ttl_seconds,
    ):
        self.refreshed_owner_vk_id = owner_vk_id
        self.refreshed_ttl = session_ttl_seconds
        if token_digest == self.session_digest:
            return self.user
        return None

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
        "owner_vk_id": "987654321",
        "vkid_login_enabled": True,
        "privacy_version": "2026-10-01-v2",
        "consent_version": "2026-10-01-v2",
        "terms_version": "2026-10-01-v2",
        "vkid_flow_ttl_seconds": 600,
        "session_ttl_seconds": 34_560_000,
    }
    values.update(overrides)
    return Settings(**values)


def test_vkid_owner_login_creates_session() -> None:
    db = FakeDatabase()
    auth = AuthService(settings(), db)

    result = auth.complete_vkid_login(
        vk_user_id="987654321",
        client_ip="203.0.113.10",
        accepted_legal_versions=auth.legal_versions(),
    )

    assert result.public_id == "000000001"
    assert result.created is True
    assert db.completed_vk_user_id == "987654321"
    assert db.accepted_versions == auth.legal_versions()
    assert auth.refresh_session(result.session_token) == db.user
    assert db.refreshed_owner_vk_id == "987654321"
    assert db.refreshed_ttl == 34_560_000


def test_vkid_login_rejects_non_owner_before_session_creation() -> None:
    db = FakeDatabase()
    auth = AuthService(settings(), db)

    with pytest.raises(OwnerAccessDenied):
        auth.complete_vkid_login(
            vk_user_id="111111111",
            client_ip="203.0.113.10",
            accepted_legal_versions=auth.legal_versions(),
        )

    assert db.session_digest is None
    assert db.completed_vk_user_id is None


def test_vkid_login_rejects_stale_legal_versions() -> None:
    db = FakeDatabase()
    auth = AuthService(settings(), db)

    with pytest.raises(LoginUnavailable):
        auth.complete_vkid_login(
            vk_user_id="987654321",
            client_ip="203.0.113.10",
            accepted_legal_versions={
                "privacy_policy": "old",
                "personal_data_consent": "old",
                "terms": "old",
            },
        )

    assert db.session_digest is None


def test_session_fails_closed_when_vkid_is_not_configured() -> None:
    db = FakeDatabase()
    auth = AuthService(
        settings(vkid_login_enabled=False, owner_vk_id=""),
        db,
    )

    assert auth.refresh_session("anything") is None


@pytest.mark.parametrize(
    ("app_id", "owner_vk_id"),
    [
        ("app", "987654321"),
        ("123456", "owner"),
        ("0", "987654321"),
        ("123456", "0"),
    ],
)
def test_session_fails_closed_for_invalid_vkid_ids(
    app_id: str,
    owner_vk_id: str,
) -> None:
    db = FakeDatabase()
    auth = AuthService(
        settings(vkid_app_id=app_id, owner_vk_id=owner_vk_id),
        db,
    )

    assert auth.refresh_session("anything") is None
