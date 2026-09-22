from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import os
import re
import secrets
from urllib.parse import urlsplit

from omni_cio.persistence.migration import ConnectionLike
from omni_cio.web.browser_security_v1 import BrowserCookiePolicyV1
from omni_cio.web.identity_v1 import IdentityProviderV1
from omni_cio.web.product_identity_v1 import (
    PostgresProductIdentityRepositoryV1,
    ProductAuthenticationServiceV1,
    ProductIdentityServiceV1,
    SessionIssuerLike,
)
from omni_cio.web.provider_auth_routes_v1 import ProviderAuthRouteServicesV1
from omni_cio.web.provider_auth_v1 import (
    PostgresAuthorizationTransactionStoreV1,
    ProviderAuthenticationRuntimeLike,
)
from omni_cio.web.telegram_auth_routes_v1 import TELEGRAM_CALLBACK_PATH
from omni_cio.web.telegram_jwks_v1 import TelegramJwksSingleFlightVerifierV1
from omni_cio.web.telegram_oidc_v1 import TelegramOidcConfigV1, TelegramOidcRuntimeV1


_TELEGRAM_CLIENT_ID = "OMNI_V10_TELEGRAM_OIDC_CLIENT_ID"
_TELEGRAM_CLIENT_SECRET = "OMNI_V10_TELEGRAM_OIDC_CLIENT_SECRET"
_IDENTITY_BINDING_KEY = "OMNI_V10_IDENTITY_BINDING_KEY_HEX"
_CSRF_BINDING_KEY = "OMNI_V10_CSRF_BINDING_KEY_HEX"
_PUBLIC_MULTI_USER_ENABLED = "PUBLIC_MULTI_USER_ENABLED"
_TELEGRAM_LOGIN_ENABLED = "OMNI_V10_TELEGRAM_LOGIN_ENABLED"
_HEX_32_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


class TelegramAuthConfigurationError(RuntimeError):
    """Fail-closed Timeweb Telegram composition error."""


def _value(environment: Mapping[str, str], name: str) -> str:
    return environment.get(name, "").strip()


def _flag(environment: Mapping[str, str], name: str) -> bool:
    raw = _value(environment, name).lower()
    if raw in {"", "0", "false"}:
        return False
    if raw in {"1", "true"}:
        return True
    raise TelegramAuthConfigurationError(f"{name}_INVALID")


def _key(environment: Mapping[str, str], name: str) -> bytes:
    value = _value(environment, name)
    if _HEX_32_PATTERN.fullmatch(value) is None:
        raise TelegramAuthConfigurationError(f"{name}_INVALID")
    return bytes.fromhex(value)


def _canonical_origin(value: str) -> str:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise TelegramAuthConfigurationError("TELEGRAM_AUTH_ORIGIN_INVALID") from exc
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or not parsed.hostname
        or port not in {None, 443}
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise TelegramAuthConfigurationError("TELEGRAM_AUTH_ORIGIN_INVALID")
    return f"https://{parsed.hostname.lower().rstrip('.')}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def build_telegram_provider_auth(
    *,
    connection: ConnectionLike,
    sessions: SessionIssuerLike,
    canonical_origin: str,
    env: Mapping[str, str] | None = None,
    now: Callable[[], datetime] = _now,
) -> ProviderAuthRouteServicesV1:
    """Compose only Telegram Login; public activation remains independently gated."""

    environment = os.environ if env is None else env
    origin = _canonical_origin(canonical_origin)
    client_id = _value(environment, _TELEGRAM_CLIENT_ID)
    client_secret = _value(environment, _TELEGRAM_CLIENT_SECRET)
    if bool(client_id) != bool(client_secret):
        raise TelegramAuthConfigurationError("TELEGRAM_AUTH_CONFIGURATION_INCOMPLETE")

    configured = bool(client_id)
    public_enabled = _flag(environment, _PUBLIC_MULTI_USER_ENABLED)
    login_enabled = _flag(environment, _TELEGRAM_LOGIN_ENABLED)
    if login_enabled and not configured:
        raise TelegramAuthConfigurationError(
            "TELEGRAM_AUTH_ACTIVATION_CONFIGURATION_REQUIRED"
        )

    if configured:
        csrf_binding_key = _key(environment, _CSRF_BINDING_KEY)
        identity_binding_key = _key(environment, _IDENTITY_BINDING_KEY)
    else:
        csrf_binding_key = secrets.token_bytes(32)
        identity_binding_key = b""

    cookies = BrowserCookiePolicyV1(
        csrf_binding_key=csrf_binding_key,
        allowed_providers=(IdentityProviderV1.TELEGRAM,),
    )
    disabled: dict[IdentityProviderV1, str] = {}
    if configured and not public_enabled:
        disabled[IdentityProviderV1.TELEGRAM] = "PUBLIC_MULTI_USER_DISABLED"
    elif configured and not login_enabled:
        disabled[IdentityProviderV1.TELEGRAM] = "PROVIDER_ACTIVATION_DISABLED"

    base_kwargs = {
        "cookies": cookies,
        "now": now,
        "disabled_reasons": disabled,
        "descriptor_providers": (IdentityProviderV1.TELEGRAM,),
    }
    if not configured or not (public_enabled and login_enabled):
        return ProviderAuthRouteServicesV1(
            runtimes=(),
            authentication=None,
            registration_enabled=False,
            **base_kwargs,
        )

    transactions = PostgresAuthorizationTransactionStoreV1(connection)
    identities = ProductIdentityServiceV1(
        PostgresProductIdentityRepositoryV1(
            connection,
            binding_key=identity_binding_key,
        ),
        registration_enabled=True,
    )
    authentication = ProductAuthenticationServiceV1(
        identities=identities,
        sessions=sessions,
    )
    telegram_config = TelegramOidcConfigV1(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=origin + TELEGRAM_CALLBACK_PATH,
    )
    runtime: ProviderAuthenticationRuntimeLike = TelegramOidcRuntimeV1(
        config=telegram_config,
        transactions=transactions,
        verifier=TelegramJwksSingleFlightVerifierV1(telegram_config),
    )
    return ProviderAuthRouteServicesV1(
        runtimes=(runtime,),
        authentication=authentication,
        registration_enabled=True,
        **base_kwargs,
    )
