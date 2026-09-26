from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from omni_cio.web.browser_security_v1 import (
    BROWSER_CSRF_COOKIE,
    BROWSER_SESSION_COOKIE,
    BrowserCookiePolicyV1,
)
from omni_cio.web.identity_v1 import IdentityProviderV1, VerifiedExternalIdentityV1
from omni_cio.web.product_identity_v1 import ProductAccountScopeV1
from omni_cio.web.provider_auth_routes_v1 import (
    TELEGRAM_CALLBACK_PATH,
    TELEGRAM_START_PATH,
    VK_ID_CALLBACK_PATH,
    VK_ID_START_PATH,
    ProviderAuthRouteServicesV1,
    install_provider_auth_routes_v1,
)
from omni_cio.web.provider_auth_v1 import ProviderAuthorizationStartV1
from omni_cio.web.session_v1 import SessionScopeV1
from omni_cio.web.telegram_oidc_v1 import TELEGRAM_OIDC_AUTHORIZATION_ENDPOINT
from omni_cio.web.vk_id_oauth_v1 import VK_ID_AUTHORIZATION_ENDPOINT


NOW = datetime(2026, 8, 25, 9, 0, tzinfo=timezone.utc)
CSRF_KEY = bytes([171]) * 32
SESSION_TOKEN = "s" * 43
OLD_SESSION_TOKEN = "o" * 43
TEST_COOKIE_DOMAIN = "omni.example"
PRODUCT_SCOPE = ProductAccountScopeV1(
    user_id="user:v1:product",
    tenant_id="tenant:v1:product",
)


def _provider_endpoint(provider: IdentityProviderV1) -> str:
    if provider == IdentityProviderV1.TELEGRAM:
        return TELEGRAM_OIDC_AUTHORIZATION_ENDPOINT
    if provider == IdentityProviderV1.VK_ID:
        return VK_ID_AUTHORIZATION_ENDPOINT
    raise AssertionError("unexpected provider")


@dataclass(slots=True)
class FakeProviderRuntime:
    provider: IdentityProviderV1
    completions: list[tuple[str, str, str, str | None]]
    authorization_url_override: str | None = None
    authorization_query_override: str | None = None
    returned_browser_proof_override: str | None = None
    returned_provider_override: IdentityProviderV1 | None = None
    started_browser_proof: str | None = None

    def start(
        self,
        *,
        now: datetime,
        browser_proof: str | None = None,
    ) -> ProviderAuthorizationStartV1:
        assert now == NOW
        assert browser_proof is not None
        self.started_browser_proof = browser_proof
        return ProviderAuthorizationStartV1(
            authorization_url=(
                self.authorization_url_override or _provider_endpoint(self.provider)
            ),
            browser_proof=self.returned_browser_proof_override or "z" * 43,
            expires_at=NOW + timedelta(minutes=5),
            authorization_query=self.authorization_query_override or "fixture=1",
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
        assert now == NOW
        assert browser_proof == self.started_browser_proof
        self.completions.append((state, code, browser_proof, device_id))
        return VerifiedExternalIdentityV1(
            provider=self.returned_provider_override or self.provider,
            subject=f"subject-{self.provider.value}",
        )


class FakeProductAuthentication:
    def __init__(self) -> None:
        self.current_tokens: list[str | None] = []
        self.identities: list[VerifiedExternalIdentityV1] = []
        self.bound_scopes: list[ProductAccountScopeV1] = []
        self.bound_tokens: list[str] = []
        self.events: list[str] = []

    def resolve_verified_identity(
        self,
        identity: VerifiedExternalIdentityV1,
        *,
        now: datetime,
    ) -> ProductAccountScopeV1:
        assert now == NOW
        self.identities.append(identity)
        self.events.append("resolve")
        return PRODUCT_SCOPE

    def revoke_session(self, token: str | None, *, now: datetime) -> bool:
        assert now == NOW
        self.current_tokens.append(token)
        self.events.append("revoke")
        return token is not None

    def bind_session(
        self,
        token: str,
        account_scope: ProductAccountScopeV1,
        *,
        now: datetime,
    ) -> SessionScopeV1:
        assert now == NOW
        self.bound_tokens.append(token)
        self.bound_scopes.append(account_scope)
        self.events.append("bind")
        return SessionScopeV1(
            user_id=account_scope.user_id,
            tenant_id=account_scope.tenant_id,
            expires_at=NOW + timedelta(hours=1),
        )


def _app(
    *providers: IdentityProviderV1,
) -> tuple[FastAPI, tuple[FakeProviderRuntime, ...], FakeProductAuthentication]:
    app = FastAPI()
    runtimes = tuple(FakeProviderRuntime(provider, []) for provider in providers)
    authentication = FakeProductAuthentication()
    install_provider_auth_routes_v1(
        app,
        services=ProviderAuthRouteServicesV1(
            runtimes=runtimes,
            authentication=authentication,
            cookies=BrowserCookiePolicyV1(
                csrf_binding_key=CSRF_KEY,
                allowed_providers=providers or (IdentityProviderV1.TELEGRAM,),
            ),
            now=lambda: NOW,
            descriptor_providers=providers or (IdentityProviderV1.TELEGRAM,),
        ),
    )
    return app, runtimes, authentication


def _set_cookie_headers(response: object) -> list[str]:
    return response.headers.get_list("set-cookie")  # type: ignore[attr-defined]


def test_cookie_policy_binds_csrf_to_opaque_session_without_exposing_key() -> None:
    policy = BrowserCookiePolicyV1(csrf_binding_key=CSRF_KEY)
    token = policy.csrf_token(SESSION_TOKEN)
    assert policy.csrf_matches(session_token=SESSION_TOKEN, csrf_token=token)
    assert not policy.csrf_matches(session_token="z" * 43, csrf_token=token)
    assert CSRF_KEY.hex() not in repr(policy)
    assert policy.session_cookie.startswith("__Host-")
    assert policy.csrf_cookie.startswith("__Host-")


def test_host_cookie_policy_cannot_disable_secure_or_use_short_key() -> None:
    with pytest.raises(ValueError, match="BROWSER_CSRF_BINDING_KEY_INVALID"):
        BrowserCookiePolicyV1(csrf_binding_key=b"short")
    with pytest.raises(ValueError, match="BROWSER_HOST_COOKIE_REQUIRES_SECURE"):
        BrowserCookiePolicyV1(csrf_binding_key=CSRF_KEY, secure=False)


def test_start_is_fixed_post_route_and_sets_only_httponly_browser_proof() -> None:
    app, runtimes, _ = _app(IdentityProviderV1.TELEGRAM)
    client = TestClient(app, base_url="https://omni.example")
    assert client.get(TELEGRAM_START_PATH).status_code == 405
    response = client.post(TELEGRAM_START_PATH, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == (
        TELEGRAM_OIDC_AUTHORIZATION_ENDPOINT + "?fixture=1"
    )
    runtime = runtimes[0]
    assert runtime.started_browser_proof is not None
    assert runtime.started_browser_proof not in response.text
    cookies = _set_cookie_headers(response)
    proof = next(value for value in cookies if "oauth_telegram" in value)
    assert runtime.started_browser_proof in proof
    assert "HttpOnly" in proof
    assert "Secure" in proof
    assert "SameSite=lax" in proof
    assert "Path=/" in proof
    assert "Domain=" not in proof


def test_runtime_output_cannot_override_redirect_origin_or_proof_cookie() -> None:
    app, runtimes, _ = _app(IdentityProviderV1.TELEGRAM)
    runtime = runtimes[0]
    runtime.authorization_url_override = "https://evil.example/steal"
    runtime.authorization_query_override = (
        "next=https://evil.example/\r\nX-Evil: injected"
    )
    runtime.returned_browser_proof_override = "z" * 43
    client = TestClient(app, base_url="https://omni.example")
    response = client.post(TELEGRAM_START_PATH, follow_redirects=False)
    assert response.status_code == 303
    location = response.headers["location"]
    parsed = urlsplit(location)
    expected = urlsplit(TELEGRAM_OIDC_AUTHORIZATION_ENDPOINT)
    assert (parsed.scheme, parsed.hostname, parsed.path) == (
        expected.scheme,
        expected.hostname,
        expected.path,
    )
    assert "evil.example" not in parsed.netloc
    assert "\r" not in location
    assert "\n" not in location
    proof_cookie = "__Host-omni_v10_oauth_telegram"
    minted = client.cookies.get(proof_cookie)
    assert minted == runtime.started_browser_proof
    assert minted is not None
    assert minted != runtime.returned_browser_proof_override


def test_callback_requires_initiating_browser_and_rotates_session() -> None:
    app, runtimes, authentication = _app(IdentityProviderV1.TELEGRAM)
    client = TestClient(app, base_url="https://omni.example")
    missing = client.get(
        TELEGRAM_CALLBACK_PATH + "?state=" + "a" * 43 + "&code=accepted",
        follow_redirects=False,
    )
    assert missing.status_code == 400
    assert runtimes[0].completions == []
    client.cookies.set(
        BROWSER_SESSION_COOKIE,
        OLD_SESSION_TOKEN,
        domain=TEST_COOKIE_DOMAIN,
        path="/",
    )
    assert client.post(TELEGRAM_START_PATH, follow_redirects=False).status_code == 303
    response = client.get(
        TELEGRAM_CALLBACK_PATH + "?state=" + "a" * 43 + "&code=accepted",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert authentication.current_tokens == [OLD_SESSION_TOKEN]
    assert authentication.identities[0].provider == IdentityProviderV1.TELEGRAM
    assert authentication.bound_scopes == [PRODUCT_SCOPE]
    assert authentication.events == ["resolve", "revoke", "bind"]
    assert len(authentication.bound_tokens) == 1
    fresh_token = authentication.bound_tokens[0]
    assert len(fresh_token) == 43
    assert fresh_token != OLD_SESSION_TOKEN
    assert fresh_token != "a" * 43
    assert fresh_token != "accepted"
    assert fresh_token != runtimes[0].started_browser_proof
    assert (
        client.cookies.get(
            BROWSER_SESSION_COOKIE,
            domain=TEST_COOKIE_DOMAIN,
            path="/",
        )
        == fresh_token
    )
    csrf = client.cookies.get(BROWSER_CSRF_COOKIE, domain=TEST_COOKIE_DOMAIN, path="/")
    assert csrf is not None
    assert BrowserCookiePolicyV1(csrf_binding_key=CSRF_KEY).csrf_matches(
        session_token=fresh_token,
        csrf_token=csrf,
    )
    cookies = _set_cookie_headers(response)
    session_header = next(value for value in cookies if BROWSER_SESSION_COOKIE in value)
    csrf_header = next(value for value in cookies if BROWSER_CSRF_COOKIE in value)
    assert "HttpOnly" in session_header
    assert "Secure" in session_header
    assert "SameSite=strict" in session_header
    assert "HttpOnly" in csrf_header
    assert "Secure" in csrf_header
    assert "SameSite=strict" in csrf_header
    assert (
        client.cookies.get(
            "__Host-omni_v10_oauth_telegram",
            domain=TEST_COOKIE_DOMAIN,
            path="/",
        )
        is None
    )


def test_callback_rejects_runtime_identity_provider_mismatch() -> None:
    app, runtimes, authentication = _app(IdentityProviderV1.TELEGRAM)
    runtimes[0].returned_provider_override = IdentityProviderV1.VK_ID
    client = TestClient(app, base_url="https://omni.example")
    assert client.post(TELEGRAM_START_PATH, follow_redirects=False).status_code == 303

    response = client.get(
        TELEGRAM_CALLBACK_PATH + "?state=" + "a" * 43 + "&code=accepted",
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "AUTHENTICATION_REJECTED"}
    assert authentication.identities == []
    assert authentication.bound_tokens == []


def test_provider_proof_cannot_be_reused_across_fixed_callback_routes() -> None:
    app, runtimes, _ = _app(IdentityProviderV1.TELEGRAM, IdentityProviderV1.VK_ID)
    client = TestClient(app, base_url="https://omni.example")
    client.post(TELEGRAM_START_PATH, follow_redirects=False)
    mixed = client.get(
        VK_ID_CALLBACK_PATH
        + "?state="
        + "a" * 43
        + "&code=accepted&device_id=device-1",
        follow_redirects=False,
    )
    assert mixed.status_code == 400
    assert runtimes[1].completions == []
    assert client.cookies.get("__Host-omni_v10_oauth_telegram") is not None


def test_vk_callback_requires_single_device_id_and_rejects_duplicate_state() -> None:
    app, runtimes, _ = _app(IdentityProviderV1.VK_ID)
    client = TestClient(app, base_url="https://omni.example")
    client.post(VK_ID_START_PATH, follow_redirects=False)
    duplicate = client.get(
        VK_ID_CALLBACK_PATH
        + "?state="
        + "a" * 43
        + "&state="
        + "b" * 43
        + "&code=accepted&device_id=device-1",
        follow_redirects=False,
    )
    assert duplicate.status_code == 400
    assert runtimes[0].completions == []


def test_unconfigured_fixed_provider_routes_fail_closed() -> None:
    app, _, _ = _app()
    client = TestClient(app, base_url="https://omni.example")
    assert client.post(TELEGRAM_START_PATH).status_code == 503
    assert client.post(VK_ID_START_PATH).status_code == 503
    assert (
        client.get(
            TELEGRAM_CALLBACK_PATH + "?state=" + "a" * 43 + "&code=accepted"
        ).status_code
        == 503
    )
