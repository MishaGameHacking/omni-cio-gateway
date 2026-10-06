"""T-ID provider contracts and browser-bound OAuth authority without live services."""

from __future__ import annotations

import base64
import json
import time
from collections.abc import Iterator
from dataclasses import dataclass, replace
from typing import Any
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from omnicio.config import Settings
from omnicio.db import Database, UserRecord
from omnicio.main import CANONICAL_ORIGIN, TID_CALLBACK, VKID_CALLBACK, app
from omnicio.security import (
    SecurityValueError,
    open_oauth_flow,
    seal_oauth_flow,
    session_digest,
)
from omnicio.service import AuthService, LoginSucceeded, LoginUnavailable
from omnicio.tid import TIDClient, TIDIdentity, TIDRejected, TIDUnavailable
from omnicio.vkid import VKIDClient, VKIDIdentity

OWNER = UserRecord(UUID(int=701), 701, "active", "user")
OTHER = UserRecord(UUID(int=702), 702, "active", "user")
HEADERS = {"origin": CANONICAL_ORIGIN, "X-Omnicio-Profile": "000000701"}
CONSENT = {
    "accept_privacy": True,
    "accept_personal_data": True,
    "accept_terms": True,
    "confirm_age_18": True,
}


def configuration() -> Settings:
    return Settings(
        database_url="postgresql://unused.invalid/db",
        ip_key=base64.urlsafe_b64encode(b"i" * 32).decode(),
        broker_token_crypto_key=Fernet.generate_key().decode(),
        vkid_flow_crypto_key=Fernet.generate_key().decode(),
        vkid_app_id="123456",
        vkid_login_enabled=True,
        registration_enabled=True,
        registration_max_users=2,
        privacy_version="test-current",
        consent_version="test-current",
        terms_version="test-current",
        vkid_flow_ttl_seconds=600,
        session_ttl_seconds=3600,
        portfolio_live_execution_enabled=False,
        portfolio_live_max_order_rub=10000,
        portfolio_live_max_daily_rub=20000,
        tid_client_id="test-client",
        tid_client_secret="test-client-secret",
        tid_login_enabled=True,
    )


def provider() -> TIDClient:
    return TIDClient(
        client_id="test-client",
        client_secret="test-client-secret",
        redirect_uri=TID_CALLBACK,
    )


def test_tid_authorization_url_pins_provider_callback_and_optional_pkce() -> None:
    client = provider()
    url = urlsplit(client.authorization_url(state="test-state", code_challenge="test-challenge"))
    assert (url.scheme, url.netloc, url.path) == ("https", "id.tbank.ru", "/auth/authorize")
    fields = parse_qs(url.query)
    assert fields["redirect_uri"] == [TID_CALLBACK]
    assert fields["state"] == ["test-state"]
    assert fields["response_type"] == ["code"]
    assert fields["code_challenge_method"] == ["S256"]
    assert fields["code_challenge"] == ["test-challenge"]
    assert "client_secret" not in fields
    disabled = replace(client, pkce_enabled=False)
    assert "code_challenge" not in parse_qs(
        urlsplit(
            disabled.authorization_url(
                state="test-state",
                code_challenge="test-challenge",
            )
        ).query
    )


def test_tid_identity_comes_only_from_authenticated_userinfo_and_headers_are_bounded() -> None:
    token_response = Mock(status=200)
    token_response.read.return_value = json.dumps(
        {
            "access_token": "test-access-token",
            "sub": "untrusted-token-field",
            "id_token": "unverified.jwt.cannot.be.authority",
        }
    ).encode()
    userinfo_response = Mock(status=200)
    userinfo_response.read.return_value = json.dumps({"sub": "verified-provider-subject"}).encode()
    connection = Mock()
    connection.getresponse.side_effect = [token_response, userinfo_response]
    with patch("omnicio.tid.http.client.HTTPSConnection", return_value=connection) as factory:
        identity = provider().exchange_code(code="test-code", code_verifier="v" * 64)
    assert identity == TIDIdentity("verified-provider-subject")
    assert factory.call_count == 2
    assert all(call.args == ("id.tbank.ru",) for call in factory.call_args_list)
    first, second = connection.request.call_args_list
    assert first.args == ("POST", "/auth/token")
    token_body = parse_qs(first.kwargs["body"].decode())
    assert token_body["code_verifier"] == ["v" * 64]
    assert token_body["redirect_uri"] == [TID_CALLBACK]
    assert first.kwargs["headers"]["Authorization"].startswith("Basic ")
    assert second.args == ("POST", "/userinfo/userinfo")
    assert second.kwargs["headers"]["Authorization"] == "Bearer test-access-token"
    assert parse_qs(second.kwargs["body"].decode())["client_id"] == ["test-client"]
    token_response.read.assert_called_once_with(65537)
    userinfo_response.read.assert_called_once_with(65537)


@pytest.mark.parametrize("subject", [None, 701, "", " ", "bad\nsubject", "x" * 129])
def test_tid_rejects_missing_or_unstable_provider_subject(subject: object) -> None:
    with (
        patch.object(
            TIDClient,
            "_post",
            side_effect=[
                {"access_token": "test-access-token"},
                {"sub": subject},
            ],
        ),
        pytest.raises(TIDRejected, match="tid_subject_invalid"),
    ):
        provider().exchange_code(code="test-code", code_verifier="v" * 64)


@pytest.mark.parametrize("status", [302, 401, 500])
def test_tid_never_follows_redirects_or_leaks_provider_error_body(status: int) -> None:
    response = Mock(status=status)
    response.read.return_value = b"private-provider-error-and-token"
    connection = Mock()
    connection.getresponse.return_value = response
    expected = TIDRejected if status == 401 else TIDUnavailable
    with (
        patch("omnicio.tid.http.client.HTTPSConnection", return_value=connection) as factory,
        pytest.raises(expected) as error,
    ):
        provider().exchange_code(code="test-code", code_verifier="v" * 64)
    factory.assert_called_once()
    connection.request.assert_called_once()
    assert "private-provider" not in str(error.value)
    response.read.assert_not_called()


def test_tid_rejects_large_response_and_unconfigured_or_unregistered_callback() -> None:
    response = Mock(status=200)
    response.read.return_value = b"x" * 65537
    connection = Mock()
    connection.getresponse.return_value = response
    with (
        patch("omnicio.tid.http.client.HTTPSConnection", return_value=connection),
        pytest.raises(TIDUnavailable, match="too_large"),
    ):
        provider().exchange_code(code="test-code", code_verifier="v" * 64)
    with patch("omnicio.tid.http.client.HTTPSConnection") as factory:
        for client in (
            replace(provider(), client_secret=""),
            replace(provider(), redirect_uri="https://untrusted.invalid/callback"),
        ):
            with pytest.raises(TIDUnavailable):
                client.exchange_code(code="test-code", code_verifier="v" * 64)
        factory.assert_not_called()


def test_oauth_cookie_is_provider_bound_and_expires() -> None:
    cfg = configuration()
    token = seal_oauth_flow(
        state="random-test-state",
        code_verifier="v" * 64,
        legal_versions={"terms": "test-current"},
        crypto_key=cfg.vkid_flow_crypto_key,
        provider="tid",
        link_user_id=str(OWNER.id),
        link_session_digest=session_digest("owner-token").hex(),
    )
    flow = open_oauth_flow(
        token, crypto_key=cfg.vkid_flow_crypto_key, ttl_seconds=600, provider="tid"
    )
    assert flow.link_user_id == str(OWNER.id)
    assert flow.link_session_digest == session_digest("owner-token").hex()
    with pytest.raises(SecurityValueError, match="provider mismatch"):
        open_oauth_flow(
            token, crypto_key=cfg.vkid_flow_crypto_key, ttl_seconds=600, provider="vkid"
        )
    cipher = Fernet(cfg.vkid_flow_crypto_key.encode())
    expired = cipher.encrypt_at_time(
        cipher.decrypt(token.encode()), int(time.time()) - 601
    ).decode()
    with pytest.raises(SecurityValueError, match="expired"):
        open_oauth_flow(
            expired, crypto_key=cfg.vkid_flow_crypto_key, ttl_seconds=600, provider="tid"
        )


@dataclass
class AuthHTTP:
    client: TestClient
    cfg: Settings
    auth: Mock
    database: Mock
    tid: Mock
    vkid: Mock
    sessions: dict[str, UserRecord]


@pytest.fixture
def auth_http() -> Iterator[AuthHTTP]:
    cfg = configuration()
    auth, database = Mock(spec=AuthService), Mock(spec=Database)
    auth.legal_versions.return_value = {
        "privacy_policy": "test-current",
        "personal_data_consent": "test-current",
        "terms": "test-current",
    }
    sessions = {"owner-token": OWNER, "other-token": OTHER, "new-owner-token": OWNER}
    auth.refresh_session.side_effect = sessions.get
    result = LoginSucceeded("new-session-token", "000000701", False, 3600)
    auth.complete_tid_login.return_value = auth.complete_vkid_login.return_value = result
    claimed: set[bytes] = set()

    def claim(digest: bytes, provider_name: str, ttl: int) -> bool:
        assert provider_name in {"tid", "vkid"} and ttl == 600
        if digest in claimed:
            return False
        claimed.add(digest)
        return True

    database.claim_oauth_flow.side_effect = claim
    tid, vkid = Mock(spec=TIDClient), Mock(spec=VKIDClient)
    tid.authorization_url.side_effect = provider().authorization_url
    vkid.authorization_url.side_effect = VKIDClient(
        cfg.vkid_app_id, VKID_CALLBACK
    ).authorization_url
    tid.exchange_code.return_value = TIDIdentity("verified-tid-subject")
    vkid.exchange_code.return_value = VKIDIdentity("987654321")
    with (
        patch.object(app.state, "settings", cfg, create=True),
        patch.object(app.state, "auth_service", auth, create=True),
        patch.object(app.state, "database", database, create=True),
        patch.object(app.state, "tid_client", tid, create=True),
        patch.object(app.state, "vkid_client", vkid, create=True),
    ):
        client = TestClient(
            app, base_url=CANONICAL_ORIGIN, cookies={"omnicio_session": "owner-token"}
        )
        try:
            yield AuthHTTP(client, cfg, auth, database, tid, vkid, sessions)
        finally:
            client.close()


def start(harness: AuthHTTP, *, provider_name: str = "tid", link: bool = False) -> tuple[str, str]:
    response = harness.client.post(
        f"/api/auth/{provider_name}/start",
        headers=HEADERS,
        json={**CONSENT, "link_current_account": link},
    )
    assert response.status_code == 200
    cookie = response.cookies[f"omnicio_{provider_name}_flow"]
    state = parse_qs(urlsplit(response.json()["authorize_url"]).query)["state"][0]
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "Secure" in response.headers["set-cookie"]
    assert f"Path=/api/auth/{provider_name}" in response.headers["set-cookie"]
    return state, cookie


def callback(
    harness: AuthHTTP,
    state: str,
    cookie: str,
    *,
    provider_name: str = "tid",
    session: str | None = None,
    extra: dict[str, Any] | None = None,
) -> Any:
    harness.client.cookies.clear()
    harness.client.cookies.set(
        f"omnicio_{provider_name}_flow",
        cookie,
        domain="omnicio.ru",
        path=f"/api/auth/{provider_name}",
    )
    if session is not None:
        harness.client.cookies.set("omnicio_session", session, domain="omnicio.ru", path="/")
    return harness.client.get(
        f"/api/auth/{provider_name}/callback",
        params={"code": "test-code", "state": state, "device_id": "test-device", **(extra or {})},
        follow_redirects=False,
    )


@pytest.mark.parametrize("provider_name", ["tid", "vkid"])
def test_oauth_callback_consumes_state_once_and_never_uses_browser_subject(
    auth_http: AuthHTTP,
    provider_name: str,
) -> None:
    state, cookie = start(auth_http, provider_name=provider_name)
    first = callback(
        auth_http, state, cookie, provider_name=provider_name, extra={"sub": str(OTHER.id)}
    )
    assert first.status_code == 303 and first.headers["location"] == "/?auth=success"
    assert first.headers["referrer-policy"] == "no-referrer"
    assert first.cookies["omnicio_session"] == "new-session-token"
    complete = getattr(auth_http.auth, f"complete_{provider_name}_login")
    assert complete.call_args.kwargs["link_user_id"] is None
    identity_field = "tid_subject" if provider_name == "tid" else "vk_user_id"
    assert complete.call_args.kwargs[identity_field] == (
        "verified-tid-subject" if provider_name == "tid" else "987654321"
    )
    second = callback(auth_http, state, cookie, provider_name=provider_name)
    assert second.headers["location"] == "/?auth_error=flow"
    getattr(auth_http, provider_name).exchange_code.assert_called_once()
    complete.assert_called_once()


def test_tid_callback_rejects_provider_swap_bad_state_and_duplicate_parameters(
    auth_http: AuthHTTP,
) -> None:
    state, cookie = start(auth_http, provider_name="vkid")
    swapped = callback(auth_http, state, cookie)
    assert swapped.headers["location"] == "/?auth_error=flow"
    state, cookie = start(auth_http)
    mismatch = callback(auth_http, "wrong-state", cookie)
    assert mismatch.headers["location"] == "/?auth_error=flow"
    auth_http.client.cookies.set(
        "omnicio_tid_flow",
        cookie,
        domain="omnicio.ru",
        path="/api/auth/tid",
    )
    duplicate = auth_http.client.get(
        "/api/auth/tid/callback",
        params=[("code", "a"), ("code", "b"), ("state", state)],
        follow_redirects=False,
    )
    assert duplicate.headers["location"] == "/?auth_error=flow"
    auth_http.database.claim_oauth_flow.assert_not_called()
    auth_http.tid.exchange_code.assert_not_called()


@pytest.mark.parametrize("session", [None, "other-token", "new-owner-token", "revoked-token"])
def test_identity_link_rejects_logout_other_tenant_and_replaced_session(
    auth_http: AuthHTTP,
    session: str | None,
) -> None:
    state, cookie = start(auth_http, link=True)
    response = callback(auth_http, state, cookie, session=session)
    assert response.headers["location"] == "/?auth_error=account"
    auth_http.database.claim_oauth_flow.assert_not_called()
    auth_http.tid.exchange_code.assert_not_called()
    auth_http.auth.complete_tid_login.assert_not_called()


def test_identity_link_binds_exact_original_session_and_provider_only(auth_http: AuthHTTP) -> None:
    state, cookie = start(auth_http, link=True)
    flow = open_oauth_flow(
        cookie,
        crypto_key=auth_http.cfg.vkid_flow_crypto_key,
        ttl_seconds=600,
        provider="tid",
    )
    assert flow.link_user_id == str(OWNER.id)
    response = callback(auth_http, state, cookie, session="owner-token")
    assert response.headers["location"] == "/?auth=success"
    context = auth_http.auth.complete_tid_login.call_args.kwargs
    assert context["link_user_id"] == OWNER.id
    assert context["link_session_digest"] == session_digest("owner-token")
    assert context["tid_subject"] == "verified-tid-subject"


def test_identity_link_deletion_or_logout_during_exchange_is_rejected(auth_http: AuthHTTP) -> None:
    state, cookie = start(auth_http, link=True)
    # The real database repeats the exact session check in its linking transaction.
    auth_http.auth.complete_tid_login.side_effect = PermissionError("oauth_link_session_expired")
    response = callback(auth_http, state, cookie, session="owner-token")
    assert response.headers["location"] == "/?auth_error=account"
    assert "omnicio_session" not in response.cookies
    assert "oauth_link_session_expired" not in response.text


def test_tid_start_requires_readiness_consent_origin_and_never_accepts_user_id(
    auth_http: AuthHTTP,
) -> None:
    for body, headers, expected in (
        (CONSENT, {}, 403),
        ({**CONSENT, "accept_terms": False}, HEADERS, 400),
        ({**CONSENT, "confirm_age_18": False}, HEADERS, 400),
        ({**CONSENT, "user_id": str(OTHER.id)}, HEADERS, 422),
        ({**CONSENT, "link_current_account": True}, {"origin": CANONICAL_ORIGIN}, 409),
    ):
        response = auth_http.client.post("/api/auth/tid/start", json=body, headers=headers)
        assert response.status_code == expected
    with patch.object(app.state, "settings", replace(auth_http.cfg, tid_login_enabled=False)):
        assert (
            auth_http.client.post("/api/auth/tid/start", json=CONSENT, headers=HEADERS).status_code
            == 503
        )
    auth_http.tid.authorization_url.assert_not_called()


def test_tid_service_remains_available_without_vkid_and_rejects_stale_legal_versions() -> None:
    cfg = replace(configuration(), vkid_login_enabled=False)
    database = Mock(spec=Database)
    database.complete_tid_login.return_value = (OWNER, False)
    database.refresh_session_digest.return_value = OWNER
    auth = AuthService(cfg, database)
    result = auth.complete_tid_login(
        tid_subject="verified-subject",
        client_ip="203.0.113.1",
        accepted_legal_versions=auth.legal_versions(),
    )
    assert auth.refresh_session(result.session_token) == OWNER
    database.complete_vkid_login.assert_not_called()
    context = database.complete_tid_login.call_args.kwargs
    assert context["session_token_digest"] == session_digest(result.session_token)
    assert context["tid_subject"] == "verified-subject"
    with pytest.raises(LoginUnavailable, match="versions changed"):
        auth.complete_tid_login(
            tid_subject="verified-subject",
            client_ip="203.0.113.1",
            accepted_legal_versions={"terms": "old"},
        )
    database.complete_tid_login.assert_called_once()
