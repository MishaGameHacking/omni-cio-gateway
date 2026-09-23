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
from omni_cio.web.provider_auth_routes_v1 import (
    TELEGRAM_CALLBACK_PATH,
    VK_ID_CALLBACK_PATH,
    ProviderAuthRouteServicesV1,
)
from omni_cio.web.provider_auth_v1 import (
    PostgresAuthorizationTransactionStoreV1,
    ProviderAuthenticationRuntimeLike,
)
from omni_cio.web.provider_start_adapter_v1 import (
    BrowserBoundTelegramOidcRuntimeV1,
    BrowserBoundVkIdOauthRuntimeV1,
)
from omni_cio.web.telegram_jwks_v1 import TelegramJwksSingleFlightVerifierV1
from omni_cio.web.telegram_oidc_v1 import TelegramOidcConfigV1
from omni_cio.web.vk_id_oauth_v1 import VkIdOauthConfigV1


_TELEGRAM_CLIENT_ID = "OMNI_V10_TELEGRAM_OIDC_CLIENT_ID"
_TELEGRAM_CLIENT_AUTH_ENV = "OMNI_V10_TELEGRAM_OIDC_CLIENT_SECRET"
_VK_CLIENT_ID = "OMNI_V10_VK_ID_CLIENT_ID"
_IDENTITY_BINDING_KEY = "OMNI_V10_IDENTITY_BINDING_KEY_HEX"
_CSRF_BINDING_KEY = "OMNI_V10_CSRF_BINDING_KEY_HEX"
_PUBLIC_MULTI_USER_ENABLED = "PUBLIC_MULTI_USER_ENABLED"
_TELEGRAM_LOGIN_ENABLED = "OMNI_V10_TELEGRAM_LOGIN_ENABLED"
_VK_ID_LOGIN_ENABLED = "OMNI_V10_VK_ID_LOGIN_ENABLED"
_HEX_32_BYTES = re.compile(r"^[0-9a-fA-F]{64}$")


class Phase5ProviderAuthConfigurationError(RuntimeError):
    """Fail-closed deployed provider-auth composition error."""


def _value(env: Mapping[str, str], name: str) -> str:
    return env.get(name, "").strip()


def _flag(env: Mapping[str, str], name: str) -> bool:
    value = _value(env, name)
    if not value:
        return False
    if value == "true":
        return True
    if value == "false":
        return False
    raise Phase5ProviderAuthConfigurationError(f"{name}_INVALID")


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


def _provider_configuration(
    environment: Mapping[str, str],
) -> tuple[str, str, str]:
    telegram_client_id = _value(environment, _TELEGRAM_CLIENT_ID)
    telegram_client_secret = _value(environment, _TELEGRAM_CLIENT_AUTH_ENV)
    vk_client_id = _value(environment, _VK_CLIENT_ID)
    if bool(telegram_client_id) != bool(telegram_client_secret):
        raise Phase5ProviderAuthConfigurationError(
            "WP22A_PHASE5_TELEGRAM_CONFIGURATION_INCOMPLETE"
        )
    return telegram_client_id, telegram_client_secret, vk_client_id


def _require_activation_configuration(
    *,
    enabled: bool,
    configured: bool,
    error_code: str,
) -> None:
    if enabled and not configured:
        raise Phase5ProviderAuthConfigurationError(error_code)


def _activation_flags(
    environment: Mapping[str, str],
    *,
    telegram_configured: bool,
    vk_configured: bool,
) -> tuple[bool, bool, bool]:
    public_multi_user_enabled = _flag(environment, _PUBLIC_MULTI_USER_ENABLED)
    telegram_login_enabled = _flag(environment, _TELEGRAM_LOGIN_ENABLED)
    vk_id_login_enabled = _flag(environment, _VK_ID_LOGIN_ENABLED)
    _require_activation_configuration(
        enabled=telegram_login_enabled,
        configured=telegram_configured,
        error_code="WP22A_PHASE5_TELEGRAM_ACTIVATION_CONFIGURATION_REQUIRED",
    )
    _require_activation_configuration(
        enabled=vk_id_login_enabled,
        configured=vk_configured,
        error_code="WP22A_PHASE5_VK_ID_ACTIVATION_CONFIGURATION_REQUIRED",
    )
    return public_multi_user_enabled, telegram_login_enabled, vk_id_login_enabled


def _binding_keys(
    environment: Mapping[str, str],
    *,
    provider_configured: bool,
) -> tuple[bytes, bytes]:
    if not provider_configured:
        return secrets.token_bytes(32), b""
    return (
        _key(environment, _CSRF_BINDING_KEY),
        _key(environment, _IDENTITY_BINDING_KEY),
    )


def _provider_disabled_reason(
    *,
    public_multi_user_enabled: bool,
    provider_enabled: bool,
) -> str | None:
    if not public_multi_user_enabled:
        return "PUBLIC_MULTI_USER_DISABLED"
    if not provider_enabled:
        return "PROVIDER_ACTIVATION_DISABLED"
    return None


def _disabled_reasons(
    *,
    public_multi_user_enabled: bool,
    telegram_configured: bool,
    telegram_login_enabled: bool,
    vk_configured: bool,
    vk_id_login_enabled: bool,
) -> dict[IdentityProviderV1, str]:
    candidates = (
        (
            IdentityProviderV1.TELEGRAM,
            telegram_configured,
            telegram_login_enabled,
        ),
        (IdentityProviderV1.VK_ID, vk_configured, vk_id_login_enabled),
    )
    result: dict[IdentityProviderV1, str] = {}
    for provider, configured, enabled in candidates:
        reason = _provider_disabled_reason(
            public_multi_user_enabled=public_multi_user_enabled,
            provider_enabled=enabled,
        )
        if configured and reason is not None:
            result[provider] = reason
    return result


def _provider_runtime_enabled(
    *,
    public_multi_user_enabled: bool,
    telegram_configured: bool,
    telegram_login_enabled: bool,
    vk_configured: bool,
    vk_id_login_enabled: bool,
) -> bool:
    return public_multi_user_enabled and (
        (telegram_configured and telegram_login_enabled)
        or (vk_configured and vk_id_login_enabled)
    )


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
    (
        telegram_client_id,
        telegram_client_secret,
        vk_client_id,
    ) = _provider_configuration(environment)
    telegram_configured = bool(telegram_client_id)
    vk_configured = bool(vk_client_id)
    provider_configured = telegram_configured or vk_configured
    (
        public_multi_user_enabled,
        telegram_login_enabled,
        vk_id_login_enabled,
    ) = _activation_flags(
        environment,
        telegram_configured=telegram_configured,
        vk_configured=vk_configured,
    )
    csrf_binding_key, identity_binding_key = _binding_keys(
        environment,
        provider_configured=provider_configured,
    )
    historical_providers = (
        IdentityProviderV1.TELEGRAM,
        IdentityProviderV1.VK_ID,
    )
    cookies = BrowserCookiePolicyV1(
        csrf_binding_key=csrf_binding_key,
        allowed_providers=historical_providers,
    )

    if not provider_configured:
        return ProviderAuthRouteServicesV1(
            runtimes=(),
            authentication=None,
            cookies=cookies,
            now=now,
        )

    disabled = _disabled_reasons(
        public_multi_user_enabled=public_multi_user_enabled,
        telegram_configured=telegram_configured,
        telegram_login_enabled=telegram_login_enabled,
        vk_configured=vk_configured,
        vk_id_login_enabled=vk_id_login_enabled,
    )
    if not _provider_runtime_enabled(
        public_multi_user_enabled=public_multi_user_enabled,
        telegram_configured=telegram_configured,
        telegram_login_enabled=telegram_login_enabled,
        vk_configured=vk_configured,
        vk_id_login_enabled=vk_id_login_enabled,
    ):
        return ProviderAuthRouteServicesV1(
            runtimes=(),
            authentication=None,
            cookies=cookies,
            now=now,
            disabled_reasons=disabled,
            registration_enabled=False,
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

    runtimes: list[ProviderAuthenticationRuntimeLike] = []
    if telegram_client_id and telegram_login_enabled:
        telegram_config = TelegramOidcConfigV1(
            client_id=telegram_client_id,
            client_secret=telegram_client_secret,
            redirect_uri=origin + TELEGRAM_CALLBACK_PATH,
        )
        runtimes.append(
            BrowserBoundTelegramOidcRuntimeV1(
                config=telegram_config,
                transactions=transactions,
                verifier=TelegramJwksSingleFlightVerifierV1(telegram_config),
            )
        )
    if vk_client_id and vk_id_login_enabled:
        runtimes.append(
            BrowserBoundVkIdOauthRuntimeV1(
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
        disabled_reasons=disabled,
        registration_enabled=True,
    )
