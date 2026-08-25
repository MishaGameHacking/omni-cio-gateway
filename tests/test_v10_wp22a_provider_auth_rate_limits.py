from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from omni_cio.web.browser_security_v1 import BrowserCookiePolicyV1
from omni_cio.web.identity_v1 import IdentityProviderV1, VerifiedExternalIdentityV1
from omni_cio.web.provider_auth_routes_v1 import (
    TELEGRAM_CALLBACK_PATH,
    TELEGRAM_START_PATH,
    ProviderAuthRouteServicesV1,
    install_provider_auth_routes_v1,
)
from omni_cio.web.provider_auth_v1 import ProviderAuthorizationStartV1
from omni_cio.web.request_limits_v1 import (
    ProviderAuthAbuseControlV1,
    RequestRatePolicyV1,
)
from omni_cio.web.session_v1 import SessionScopeV1


NOW = datetime(2026, 8, 25, 20, 0, tzinfo=timezone.utc)
CSRF_KEY = bytes([81]) * 32
SESSION_TOKEN = "s" * 43


@dataclass(slots=True)
class _Runtime:
    provider: IdentityProviderV1 = IdentityProviderV1.TELEGRAM

    def start(self, *, now: datetime) -> ProviderAuthorizationStartV1:
        assert now == NOW
        return ProviderAuthorizationStartV1(
            authorization_url="https://provider.example/telegram",
            browser_proof="p" * 43,
            expires_at=NOW + timedelta(minutes=5),
        )

    def complete(
        self,
        *,
        state: str,
        code: str,
        browser_proof: str,
        now: datetime,
        device_id: str | None = None,
    ) -> VerifiedExternalIdentityV1:
        assert state == "a" * 43
        assert code == "accepted"
        assert browser_proof == "p" * 43
        assert now == NOW
        assert device_id is None
        return VerifiedExternalIdentityV1(
            provider=IdentityProviderV1.TELEGRAM,
            subject="rate-limit-test",
        )


class _Authentication:
    def authenticate_verified_identity(
        self,
        identity: VerifiedExternalIdentityV1,
        *,
        current_session_token: str | None,
        now: datetime,
    ) -> tuple[str, SessionScopeV1]:
        assert identity.provider == IdentityProviderV1.TELEGRAM
        assert now == NOW
        return (
            SESSION_TOKEN,
            SessionScopeV1(
                user_id="user:v1:rate_limit",
                tenant_id="tenant:v1:rate_limit",
                expires_at=NOW + timedelta(hours=1),
            ),
        )


def _services(policy: RequestRatePolicyV1) -> ProviderAuthRouteServicesV1:
    return ProviderAuthRouteServicesV1(
        runtimes=(_Runtime(),),
        authentication=_Authentication(),
        cookies=BrowserCookiePolicyV1(csrf_binding_key=CSRF_KEY),
        now=lambda: NOW,
        abuse=ProviderAuthAbuseControlV1(policy),
    )


def _client(services: ProviderAuthRouteServicesV1) -> TestClient:
    app = FastAPI()
    install_provider_auth_routes_v1(app, services=services)
    return TestClient(app, base_url="https://omni.example")


def test_provider_start_rate_limit_returns_retry_after() -> None:
    services = _services(RequestRatePolicyV1(provider_starts=1))
    client = _client(services)

    first = client.post(TELEGRAM_START_PATH, follow_redirects=False)
    limited = client.post(TELEGRAM_START_PATH, follow_redirects=False)

    assert first.status_code == 303
    assert limited.status_code == 429
    assert limited.json() == {"detail": "RATE_LIMITED"}
    assert limited.headers["retry-after"] == "1"


def test_outbound_capacity_429_preserves_browser_proof_for_retry() -> None:
    services = _services(RequestRatePolicyV1(outbound_provider_concurrency=1))
    client = _client(services)
    proof_cookie = services.cookies.proof_cookie(IdentityProviderV1.TELEGRAM)

    start = client.post(TELEGRAM_START_PATH, follow_redirects=False)
    assert start.status_code == 303
    assert client.cookies.get(proof_cookie) == "p" * 43

    assert services.abuse.acquire_outbound()
    try:
        limited = client.get(
            TELEGRAM_CALLBACK_PATH + "?state=" + "a" * 43 + "&code=accepted",
            follow_redirects=False,
        )
    finally:
        services.abuse.release_outbound()

    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "1"
    assert client.cookies.get(proof_cookie) == "p" * 43

    accepted = client.get(
        TELEGRAM_CALLBACK_PATH + "?state=" + "a" * 43 + "&code=accepted",
        follow_redirects=False,
    )
    assert accepted.status_code == 303
    assert client.cookies.get(proof_cookie) is None


def test_callback_rate_limit_is_independent_of_start_limit() -> None:
    services = _services(
        RequestRatePolicyV1(provider_starts=2, provider_callbacks=1)
    )
    client = _client(services)

    client.cookies.set(
        services.cookies.proof_cookie(IdentityProviderV1.TELEGRAM),
        "p" * 43,
    )
    first = client.get(
        TELEGRAM_CALLBACK_PATH + "?state=" + "a" * 43 + "&code=accepted",
        follow_redirects=False,
    )
    assert first.status_code == 303

    client.cookies.set(
        services.cookies.proof_cookie(IdentityProviderV1.TELEGRAM),
        "p" * 43,
    )
    limited = client.get(
        TELEGRAM_CALLBACK_PATH + "?state=" + "a" * 43 + "&code=accepted",
        follow_redirects=False,
    )
    assert limited.status_code == 429
    assert limited.json() == {"detail": "RATE_LIMITED"}
