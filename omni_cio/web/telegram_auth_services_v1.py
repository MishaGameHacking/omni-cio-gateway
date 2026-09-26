from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from omni_cio.web.browser_security_v1 import BrowserCookiePolicyV1
from omni_cio.web.identity_v1 import (
    IdentityProviderV1,
    ProviderAvailabilityV1,
    ProviderDescriptorV1,
    VerifiedExternalIdentityV1,
)
from omni_cio.web.product_identity_v1 import ProductAccountScopeV1
from omni_cio.web.provider_auth_v1 import ProviderAuthenticationRuntimeLike
from omni_cio.web.request_limits_v1 import ProviderAuthAbuseControlV1
from omni_cio.web.session_v1 import SessionScopeV1


_ALLOWED_DISABLED_REASONS = frozenset(
    {
        "PUBLIC_MULTI_USER_DISABLED",
        "PROVIDER_ACTIVATION_DISABLED",
    }
)


class TelegramProductAuthenticationLike(Protocol):
    def resolve_verified_identity(
        self,
        identity: VerifiedExternalIdentityV1,
        *,
        now: datetime,
    ) -> ProductAccountScopeV1: ...

    def revoke_session(self, token: str | None, *, now: datetime) -> bool: ...

    def bind_session(
        self,
        token: str,
        account_scope: ProductAccountScopeV1,
        *,
        now: datetime,
    ) -> SessionScopeV1: ...


@dataclass(slots=True)
class TelegramAuthRouteServicesV1:
    """Current Telegram-only login route composition."""

    runtimes: tuple[ProviderAuthenticationRuntimeLike, ...]
    authentication: TelegramProductAuthenticationLike | None
    cookies: BrowserCookiePolicyV1
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
    disabled_reasons: Mapping[IdentityProviderV1, str] = field(default_factory=dict)
    registration_enabled: bool = False
    abuse: ProviderAuthAbuseControlV1 = field(
        default_factory=ProviderAuthAbuseControlV1
    )

    def __post_init__(self) -> None:
        providers = tuple(runtime.provider for runtime in self.runtimes)
        if len(providers) != len(set(providers)) or len(providers) > 1:
            raise ValueError("TELEGRAM_AUTH_RUNTIME_DUPLICATE")
        if any(provider != IdentityProviderV1.TELEGRAM for provider in providers):
            raise ValueError("TELEGRAM_AUTH_RUNTIME_PROVIDER_INVALID")
        if self.runtimes and self.authentication is None:
            raise ValueError("TELEGRAM_AUTH_AUTHENTICATION_REQUIRED")
        if self.registration_enabled and self.authentication is None:
            raise ValueError("TELEGRAM_AUTH_REGISTRATION_REQUIRES_AUTHENTICATION")
        blocked = set(self.disabled_reasons)
        if blocked - {IdentityProviderV1.TELEGRAM}:
            raise ValueError("TELEGRAM_AUTH_DISABLED_PROVIDER_INVALID")
        if blocked & set(providers):
            raise ValueError("TELEGRAM_AUTH_ENABLED_PROVIDER_CANNOT_BE_DISABLED")
        if any(
            reason not in _ALLOWED_DISABLED_REASONS
            for reason in self.disabled_reasons.values()
        ):
            raise ValueError("TELEGRAM_AUTH_DISABLED_REASON_INVALID")
        if self.cookies.allowed_providers != (IdentityProviderV1.TELEGRAM,):
            raise ValueError("TELEGRAM_AUTH_COOKIE_PROVIDER_INVALID")

    def runtime(self) -> ProviderAuthenticationRuntimeLike | None:
        return self.runtimes[0] if self.runtimes else None

    def disabled_reason(
        self,
        provider: IdentityProviderV1,
    ) -> str | None:
        if provider != IdentityProviderV1.TELEGRAM:
            raise ValueError("TELEGRAM_AUTH_PROVIDER_INVALID")
        if self.runtime() is not None:
            return None
        return self.disabled_reasons.get(
            IdentityProviderV1.TELEGRAM,
            "NOT_CONFIGURED",
        )

    def descriptors(self) -> tuple[ProviderDescriptorV1, ...]:
        availability = (
            ProviderAvailabilityV1.CONFIGURED
            if self.runtime() is not None
            else ProviderAvailabilityV1.NOT_CONFIGURED
        )
        return (
            ProviderDescriptorV1(
                provider=IdentityProviderV1.TELEGRAM,
                availability=availability,
            ),
        )
