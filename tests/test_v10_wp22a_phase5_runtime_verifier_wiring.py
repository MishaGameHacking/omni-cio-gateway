from __future__ import annotations

import secrets
from typing import Any, cast

from apps.api.wp22a_phase5_auth import build_wp22a_phase5_provider_auth
from omni_cio.web.telegram_jwks_v1 import TelegramJwksSingleFlightVerifierV1
from omni_cio.web.telegram_oidc_v1 import TelegramOidcRuntimeV1
from omni_cio.web.session_v1 import SessionRegistryV1


TELEGRAM_CLIENT_SECRET = secrets.token_urlsafe(32)
CSRF_BINDING_KEY_HEX = secrets.token_hex(32)
IDENTITY_BINDING_KEY_HEX = secrets.token_hex(32)


def test_deployed_telegram_runtime_uses_single_flight_jwks_verifier() -> None:
    services = build_wp22a_phase5_provider_auth(
        connection=cast(Any, object()),
        sessions=SessionRegistryV1(),
        canonical_origin="https://omni.example",
        env={
            "PUBLIC_MULTI_USER_ENABLED": "true",
            "OMNI_V10_TELEGRAM_LOGIN_ENABLED": "true",
            "OMNI_V10_TELEGRAM_OIDC_CLIENT_ID": "123456",
            "OMNI_V10_TELEGRAM_OIDC_CLIENT_SECRET": TELEGRAM_CLIENT_SECRET,
            "OMNI_V10_CSRF_BINDING_KEY_HEX": CSRF_BINDING_KEY_HEX,
            "OMNI_V10_IDENTITY_BINDING_KEY_HEX": IDENTITY_BINDING_KEY_HEX,
        },
    )

    assert len(services.runtimes) == 1
    runtime = services.runtimes[0]
    assert isinstance(runtime, TelegramOidcRuntimeV1)
    assert isinstance(runtime._verifier, TelegramJwksSingleFlightVerifierV1)
