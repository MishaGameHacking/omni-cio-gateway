from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import os
import re
import secrets
from urllib.parse import urlsplit

from omni_cio.persistence.migration import ConnectionLike
from omni_cio.web.browser_security_v1 import BrowserCookiePolicyV1
from omni_cio.web.product_identity_v1 import (
    PostgresProductIdentityRepositoryV1,
    ProductAuthenticationServiceV1,
    ProductIdentityServiceV1,
    SessionIssuerLike,
)
from omni_cio.web.provider_auth_routes_v1 import (
    TELEGRAM_CALLBACK_PATH,
    VK_ID_CALLBACK_PATH,
    ProviderAuthRouteServicesV1,
)
from omni_cio.web.provider_auth_v1 import PostgresAuthorizationTransactionStoreV1
from omni_cio.web.telegram_oidc_v1 import TelegramOidcConfigV1, TelegramOidcRuntimeV1
from omni_cio.web.vk_id_oauth_v1 import VkIdOauthConfigV1, VkIdOauthRuntimeV1


_TELEGRAM_CLIENT_ID = "OMNI_V10_TELEGRAM_OIDC_CLIENT_ID"
_TELEGRAM_CLIENT_SECRET = "OMNI_V10_TELEGRAM_OIDC_CLIENT_SECRET"
_VK_CLIENT_ID = "OMNI_V10_VK_ID_CLIENT_ID"
_IDENTITY_BINDING_KEY = "OMNI_V10_IDENTITY_BINDING_KEY_HEX"
_CSRF_BINDING_KEY = "OMNI_V10_CSRF_BINDING_KEY_HEX"
_HEX_32_BYTES = re.compile(r"^[0-9a-fA-F]{64}$")


class Phase5ProviderAuthConfigurationError(RuntimeError):
    """Fail-closed deployed provider-auth composition error."""


def _value(env: Mapping[str, str], name: str) -> str:
    return env.get(name, "").strip()


def _key(env: Mapping[str, str], name: str) -> bytes:
    value = _value(env, name)
    if not value:
        raise Phase5ProviderAuthConfigurationError(f"{name}_REQUIRED")
    if _HEX_32_BYTES.fullmatch(value) is None:
        raise Phase5ProviderAuthConfigurationError(f"{name}_INVALID")
    return bytes.fromhex(value)


def _canonical_origin(value: str) -> str:
    if not isinstance(value, str) or value != value.strip():
        raise Phase5ProviderAuthConfigurationError("WP22A_PHASE5_ORIGIN_INVALID")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise Phase5ProviderAuthConfigurationError(
            "WP22A_PHASE5_ORIGIN_INVALID"
        ) from exc
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise Phase5ProviderAuthConfigurationError("WP22A_PHASE5_ORIGIN_INVALID")
    host = parsed.hostname.lower().rstrip(".")
    return f"https://{host}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def build_wp22a_phase5_provider_auth(
    *,
    connection: ConnectionLike,
    sessions: SessionIssuerLike,
    canonical_origin: str,
    env: Mapping[str, str] | None = None,
    now: Callable[[], datetime] = _now,
) -> ProviderAuthRouteServicesV1:
    """Compose deployed Telegram/VK auth without any human session bypass.

    Provider secrets are runtime-only. No provider configured is a valid fail-closed
    state for the synthetic hosted technical boundary. Partial provider
    configuration is not valid and aborts startup rather than silently weakening
    authentication.
    """

    environment = os.environ if env is None else env
    origin = _canonical_origin(canonical_origin)
    telegram_client_id = _value(environment, _TELEGRAM_CLIENT_ID)
    telegram_client_secret = _value(environment, _TELEGRAM_CLIENT_SECRET)
    vk_client_id = _value(environment, _VK_CLIENT_ID)

    if bool(telegram_client_id) != bool(telegram_client_secret):
        raise Phase5ProviderAuthConfigurationError(
            "WP22A_PHASE5_TELEGRAM_CONFIGURATION_INCOMPLETE"
        )

    provider_configured = bool(telegram_client_id or vk_client_id)
    if provider_configured:
        csrf_binding_key = _key(environment, _CSRF_BINDING_KEY)
        identity_binding_key = _key(environment, _IDENTITY_BINDING_KEY)
    else:
        # No provider can issue a session in this state. An ephemeral key keeps
        # the disabled route surface operational without introducing a new
        # OWNER-held prerequisite for synthetic technical acceptance.
        csrf_binding_key = secrets.token_bytes(32)
        identity_binding_key = b""

    cookies = BrowserCookiePolicyV1(csrf_binding_key=csrf_binding_key)
    if not provider_configured:
        return ProviderAuthRouteServicesV1(
            runtimes=(),
            authentication=None,
            cookies=cookies,
            now=now,
        )

    transactions = PostgresAuthorizationTransactionStoreV1(connection)
    identities = ProductIdentityServiceV1(
        PostgresProductIdentityRepositoryV1(
            connection,
            binding_key=identity_binding_key,
        ),
        registration_enabled=False,
    )
    authentication = ProductAuthenticationServiceV1(
        identities=identities,
        sessions=sessions,
    )

    runtimes = []
    if telegram_client_id:
        runtimes.append(
            TelegramOidcRuntimeV1(
                config=TelegramOidcConfigV1(
                    client_id=telegram_client_id,
                    client_secret=telegram_client_secret,
                    redirect_uri=origin + TELEGRAM_CALLBACK_PATH,
                ),
                transactions=transactions,
            )
        )
    if vk_client_id:
        runtimes.append(
            VkIdOauthRuntimeV1(
                config=VkIdOauthConfigV1(
                    client_id=vk_client_id,
                    redirect_uri=origin + VK_ID_CALLBACK_PATH,
                ),
                transactions=transactions,
            )
        )

    return ProviderAuthRouteServicesV1(
        runtimes=tuple(runtimes),
        authentication=authentication,
        cookies=cookies,
        now=now,
    )