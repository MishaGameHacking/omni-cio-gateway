from __future__ import annotations

from typing import Any, cast

from apps.api.wp22a_phase5_auth import build_wp22a_phase5_provider_auth
from omni_cio.web.telegram_jwks_v1 import TelegramJwksSingleFlightVerifierV1
from omni_cio.web.telegram_oidc_v1 import TelegramOidcRuntimeV1
from omni_cio.web.session_v1 import SessionRegistryV1


def test_deployed_telegram_runtime_uses_single_flight_jwks_verifier() -> None:
    services = build_wp22a_phase5_provider_auth(
        connection=cast(Any, object()),
        sessions=SessionRegistryV1(),
        canonical_origin="https://omni.example",
        env={
            "OMNI_V10_TELEGRAM_OIDC_CLIENT_ID": "123456",
            "OMNI_V10_TELEGRAM_OIDC_CLIENT_SECRET": "s" * 32,
            "OMNI_V10_CSRF_BINDING_KEY_HEX": "11" * 32,
            "OMNI_V10_IDENTITY_BINDING_KEY_HEX": "22" * 32,
        },
    )

    assert len(services.runtimes) == 1
    runtime = services.runtimes[0]
    assert isinstance(runtime, TelegramOidcRuntimeV1)
    assert isinstance(runtime._verifier, TelegramJwksSingleFlightVerifierV1)
