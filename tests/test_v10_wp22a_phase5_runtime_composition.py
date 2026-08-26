from __future__ import annotations

from datetime import datetime, timezone
import secrets
from typing import Any, cast

import pytest

from apps.api.wp22a_phase5_auth import (
    Phase5ProviderAuthConfigurationError,
    build_wp22a_phase5_provider_auth,
)
from omni_cio.web.identity_v1 import IdentityProviderV1
from omni_cio.web.session_v1 import SessionRegistryV1
from omni_cio.web.telegram_oidc_v1 import TelegramOidcRuntimeV1
from omni_cio.web.vk_id_oauth_v1 import VkIdOauthRuntimeV1


NOW = datetime(2026, 8, 25, 18, 30, tzinfo=timezone.utc)
ORIGIN = "https://omni-cio-v10-web.onrender.com"
TELEGRAM_CLIENT_SECRET = secrets.token_urlsafe(32)
KEY_A = secrets.token_hex(32)
KEY_B = secrets.token_hex(32)


def _build(env: dict[str, str]):
    return build_wp22a_phase5_provider_auth(
        connection=cast(Any, object()),
        sessions=SessionRegistryV1(),
        canonical_origin=ORIGIN,
        env=env,
        now=lambda: NOW,
    )


def test_no_provider_configuration_is_valid_fail_closed_state() -> None:
    services = _build({})
    descriptors = services.descriptors()
    assert services.authentication is None
    assert services.runtimes == ()
    assert [item.provider for item in descriptors] == [
        IdentityProviderV1.TELEGRAM,
        IdentityProviderV1.VK_ID,
    ]
    assert all(not item.enabled for item in descriptors)


def test_partial_telegram_configuration_aborts_startup() -> None:
    with pytest.raises(
        Phase5ProviderAuthConfigurationError,
        match="WP22A_PHASE5_TELEGRAM_CONFIGURATION_INCOMPLETE",
    ):
        _build({"OMNI_V10_TELEGRAM_OIDC_CLIENT_ID": "123456"})
    with pytest.raises(
        Phase5ProviderAuthConfigurationError,
        match="WP22A_PHASE5_TELEGRAM_CONFIGURATION_INCOMPLETE",
    ):
        _build({"OMNI_V10_TELEGRAM_OIDC_CLIENT_SECRET": TELEGRAM_CLIENT_SECRET})


def test_configured_provider_requires_both_server_side_binding_keys() -> None:
    telegram = {
        "OMNI_V10_TELEGRAM_OIDC_CLIENT_ID": "123456",
        "OMNI_V10_TELEGRAM_OIDC_CLIENT_SECRET": TELEGRAM_CLIENT_SECRET,
    }
    with pytest.raises(
        Phase5ProviderAuthConfigurationError,
        match="OMNI_V10_CSRF_BINDING_KEY_HEX_REQUIRED",
    ):
        _build(telegram)
    telegram["OMNI_V10_CSRF_BINDING_KEY_HEX"] = KEY_A
    with pytest.raises(
        Phase5ProviderAuthConfigurationError,
        match="OMNI_V10_IDENTITY_BINDING_KEY_HEX_REQUIRED",
    ):
        _build(telegram)


def test_invalid_binding_key_encoding_is_rejected_without_echoing_value() -> None:
    invalid_binding_material = "invalid_" + secrets.token_urlsafe(8)
    with pytest.raises(Phase5ProviderAuthConfigurationError) as error:
        _build(
            {
                "OMNI_V10_VK_ID_CLIENT_ID": "123456",
                "OMNI_V10_CSRF_BINDING_KEY_HEX": invalid_binding_material,
                "OMNI_V10_IDENTITY_BINDING_KEY_HEX": KEY_B,
            }
        )
    assert str(error.value) == "OMNI_V10_CSRF_BINDING_KEY_HEX_INVALID"
    assert invalid_binding_material not in str(error.value)


def test_telegram_and_vk_runtime_composition_uses_fixed_https_callbacks() -> None:
    services = _build(
        {
            "OMNI_V10_TELEGRAM_OIDC_CLIENT_ID": "123456",
            "OMNI_V10_TELEGRAM_OIDC_CLIENT_SECRET": TELEGRAM_CLIENT_SECRET,
            "OMNI_V10_VK_ID_CLIENT_ID": "654321",
            "OMNI_V10_CSRF_BINDING_KEY_HEX": KEY_A,
            "OMNI_V10_IDENTITY_BINDING_KEY_HEX": KEY_B,
        }
    )
    assert services.authentication is not None
    assert [runtime.provider for runtime in services.runtimes] == [
        IdentityProviderV1.TELEGRAM,
        IdentityProviderV1.VK_ID,
    ]
    telegram, vk = services.runtimes
    assert isinstance(telegram, TelegramOidcRuntimeV1)
    assert isinstance(vk, VkIdOauthRuntimeV1)
    assert (
        telegram._config.redirect_uri
        == ORIGIN + "/api/v10/web/auth/telegram/callback"
    )
    assert vk._config.redirect_uri == ORIGIN + "/api/v10/web/auth/vk_id/callback"


def test_origin_must_be_exact_https_origin_without_path_or_query() -> None:
    def clock() -> datetime:
        return NOW

    for invalid in (
        "http://omni.example",
        "https://omni.example/path",
        "https://omni.example?x=1",
        "https://user@omni.example",
    ):
        connection = cast(Any, object())
        sessions = SessionRegistryV1()
        with pytest.raises(
            Phase5ProviderAuthConfigurationError,
            match="WP22A_PHASE5_ORIGIN_INVALID",
        ):
            build_wp22a_phase5_provider_auth(
                connection=connection,
                sessions=sessions,
                canonical_origin=invalid,
                env={},
                now=clock,
            )
