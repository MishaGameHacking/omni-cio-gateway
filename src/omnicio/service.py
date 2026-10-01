"""Owner authentication business logic."""

from __future__ import annotations

from dataclasses import dataclass

from .config import Settings
from .db import Database, UserRecord
from .security import (
    client_ip_digest,
    format_public_id,
    generate_session_token,
    session_digest,
)


class AuthError(RuntimeError):
    """Base authentication service error."""


class LoginUnavailable(AuthError):
    """Owner login is not operationally ready."""


class OwnerAccessDenied(AuthError):
    """The VK ID subject does not match the configured private owner."""


@dataclass(frozen=True, slots=True)
class LoginSucceeded:
    session_token: str
    public_id: str
    created: bool
    expires_in_seconds: int


class AuthService:
    def __init__(self, settings: Settings, database: Database) -> None:
        self.settings = settings
        self.database = database

    def legal_versions(self) -> dict[str, str]:
        return {
            "privacy_policy": self.settings.privacy_version,
            "personal_data_consent": self.settings.consent_version,
            "terms": self.settings.terms_version,
        }

    def complete_vkid_login(
        self,
        *,
        vk_user_id: str,
        client_ip: str,
        accepted_legal_versions: dict[str, str],
    ) -> LoginSucceeded:
        if not self.settings.vkid_ready:
            raise LoginUnavailable("VK ID owner login is not enabled")
        if vk_user_id != self.settings.owner_vk_id:
            raise OwnerAccessDenied("VK ID account is not the configured owner")
        if accepted_legal_versions != self.legal_versions():
            raise LoginUnavailable("legal document versions changed")

        token = generate_session_token()
        token_hash = session_digest(token)
        ip_hash = client_ip_digest(client_ip, self.settings.ip_key)

        user, created = self.database.complete_vkid_login(
            vk_user_id=vk_user_id,
            client_ip_hash=ip_hash,
            session_token_digest=token_hash,
            session_ttl_seconds=self.settings.session_ttl_seconds,
            legal_versions=accepted_legal_versions,
        )
        return LoginSucceeded(
            session_token=token,
            public_id=format_public_id(user.public_id),
            created=created,
            expires_in_seconds=self.settings.session_ttl_seconds,
        )

    def refresh_session(self, token: str) -> UserRecord | None:
        if not token or not self.settings.vkid_ready:
            return None
        return self.database.refresh_session_digest(
            session_digest(token),
            owner_vk_id=self.settings.owner_vk_id,
            session_ttl_seconds=self.settings.session_ttl_seconds,
        )

    def logout(self, token: str) -> None:
        if token:
            self.database.revoke_session(session_digest(token))
