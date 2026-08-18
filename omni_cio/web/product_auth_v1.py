from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Protocol

from omni_cio.web.identity_v1 import VerifiedExternalIdentityV1
from omni_cio.web.product_identity_v1 import (
    PostgresProductIdentityRepositoryV1,
    ProductAccountScopeV1,
    ProductIdentityError,
)
from omni_cio.web.session_v1 import SessionRegistryV1, SessionScopeV1


class ProductSessionRegistryV1(Protocol):
    def create(
        self,
        *,
        user_id: str,
        tenant_id: str,
        now: datetime | None = None,
    ) -> tuple[str, SessionScopeV1]: ...

    def resolve(
        self,
        token: str,
        *,
        now: datetime | None = None,
        touch: bool = True,
    ) -> SessionScopeV1 | None: ...

    def revoke(self, token: str, *, now: datetime | None = None) -> bool: ...


class ProductAuthenticationError(RuntimeError):
    """Fail-closed product authentication transition error."""


class ProductAuthenticationServiceV1:
    """Convert a verified Telegram/VK identity into an Omni-CIO session.

    Provider verification happens before this boundary. This service accepts no
    Cloudflare/GitHub/provider-engineering identity type and therefore cannot
    treat infrastructure membership as product authentication.
    """

    def __init__(
        self,
        *,
        identities: PostgresProductIdentityRepositoryV1,
        sessions: ProductSessionRegistryV1 | SessionRegistryV1,
        now: Callable[[], datetime],
    ) -> None:
        self._identities = identities
        self._sessions = sessions
        self._now = now

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ProductAuthenticationError("AUTH_TIME_NOT_TIMEZONE_AWARE")
        return value.astimezone(timezone.utc)

    def authenticate_verified(
        self,
        identity: VerifiedExternalIdentityV1,
        *,
        current_session_token: str | None = None,
    ) -> tuple[str, SessionScopeV1]:
        now = self._utc(self._now())
        try:
            account = self._identities.resolve_or_register(identity, now=now)
        except ProductIdentityError as exc:
            raise ProductAuthenticationError(str(exc)) from exc

        if current_session_token:
            self._sessions.revoke(current_session_token, now=now)

        token, session = self._sessions.create(
            user_id=account.user_id,
            tenant_id=account.tenant_id,
            now=now,
        )
        if (session.user_id, session.tenant_id) != (
            account.user_id,
            account.tenant_id,
        ):
            self._sessions.revoke(token, now=now)
            raise ProductAuthenticationError("SESSION_SCOPE_MISMATCH")
        return token, session

    def link_verified_to_authenticated_account(
        self,
        *,
        current_session_token: str,
        identity: VerifiedExternalIdentityV1,
    ) -> ProductAccountScopeV1:
        now = self._utc(self._now())
        session = self._sessions.resolve(current_session_token, now=now, touch=True)
        if session is None:
            raise ProductAuthenticationError("AUTHENTICATED_ACCOUNT_REQUIRED")

        scope = ProductAccountScopeV1(
            user_id=session.user_id,
            tenant_id=session.tenant_id,
        )
        try:
            self._identities.link_verified(scope, identity, now=now)
        except ProductIdentityError as exc:
            raise ProductAuthenticationError(str(exc)) from exc
        return scope
