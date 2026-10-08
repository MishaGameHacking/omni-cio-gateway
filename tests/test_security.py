from __future__ import annotations

import asyncio
import base64
import io
import os
import urllib.request
import urllib.response
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import Message
from unittest.mock import Mock, patch
from uuid import UUID

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import ClientDisconnect, Request

from omnicio.config import ConfigurationError, load_settings, optional_uuid, positive_numeric_id
from omnicio.db import Database, UserRecord
from omnicio.main import (
    CANONICAL_ORIGIN,
    _market_stream_response,
    app,
    client_ip,
    require_same_origin,
)
from omnicio.market import MarketService, MarketStreamLimit
from omnicio.security import (
    OAuthFlow,
    SecurityValueError,
    client_ip_digest,
    decrypt_secret,
    encrypt_secret,
    format_public_id,
    generate_oauth_state,
    generate_pkce_verifier,
    open_oauth_flow,
    parse_public_id,
    pkce_challenge,
    seal_oauth_flow,
    validate_auth_return_to,
)
from omnicio.tbank import TBankInvestClient, TBankUnavailable
from omnicio.vkid import VKIDClient, VKIDUnavailable


@pytest.mark.parametrize("provider", ["broker", "vkid"])
@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_credentialed_provider_requests_never_follow_redirects(provider, status) -> None:
    headers = Message()
    headers["Location"] = "https://untrusted.invalid/collect"
    response = urllib.response.addinfourl(io.BytesIO(), headers, "https://provider.invalid", status)
    response.msg = "redirect"
    with patch.object(urllib.request.HTTPSHandler, "https_open", return_value=response) as request:
        if provider == "broker":
            with pytest.raises(TBankUnavailable):
                TBankInvestClient().get_accounts("synthetic-credential-must-not-leak", "prod")
        else:
            with pytest.raises(VKIDUnavailable):
                VKIDClient("123", "https://omnicio.ru/api/auth/vkid/callback").exchange_code(
                    code="synthetic-code", device_id="device", code_verifier="v" * 64,
                    expected_state="state",
                )
    request.assert_called_once()
    assert response.closed


@pytest.mark.parametrize("value", ["²", "１２３", "١٢٣", "0", "9" * 129, "9" * 5000])
def test_provider_numeric_ids_are_bounded_ascii_without_conversion_errors(value) -> None:
    assert not positive_numeric_id(value)
    assert positive_numeric_id("123456789")


def test_operator_configuration_is_explicit_and_credentials_preserve_exact_bytes() -> None:
    environment = {
        "DATABASE_URL": "postgresql://synthetic.invalid/example",
        "CLIENT_IP_KEY": "synthetic-client-key",
        "BROKER_TOKEN_CRYPTO_KEY": "synthetic-broker-key",
        "VKID_FLOW_CRYPTO_KEY": "synthetic-flow-key",
        "TID_CLIENT_SECRET": "  synthetic-tid-secret  ",
        "ASSISTANT_API_KEY": "  synthetic-assistant-key  ",
        "OPERATOR_USER_ID": str(UUID(int=501)),
    }
    with patch.dict(os.environ, environment, clear=True):
        cfg = load_settings()
    assert cfg.operator_user_id == UUID(int=501)
    assert cfg.tid_client_secret == environment["TID_CLIENT_SECRET"]
    assert cfg.assistant_api_key == environment["ASSISTANT_API_KEY"]
    with patch.dict(os.environ, {}, clear=True):
        assert optional_uuid("OPERATOR_USER_ID") is None


def test_disabled_email_ignores_legacy_smtp_environment_but_enabled_remains_strict() -> None:
    environment = {
        "DATABASE_URL": "postgresql://synthetic.invalid/example",
        "CLIENT_IP_KEY": "synthetic-client-key",
        "BROKER_TOKEN_CRYPTO_KEY": "synthetic-broker-key",
        "VKID_FLOW_CRYPTO_KEY": "synthetic-flow-key",
        "NOTIFICATIONS_ENABLED": "true", "NOTIFICATION_EMAIL_ENABLED": "false",
        "NOTIFICATION_SMTP_PORT": "invalid", "NOTIFICATION_SMTP_MODE": "invalid",
        "NOTIFICATION_SMTP_SENDER": "invalid\r\nheader",
        "NOTIFICATION_SMTP_HOST": "legacy.example.org",
    }
    with patch.dict(os.environ, environment, clear=True):
        cfg = load_settings()
    assert cfg.notifications_enabled
    assert not cfg.notification_email_enabled
    assert cfg.notification_smtp_port == 465
    assert cfg.notification_smtp_mode == "tls"
    assert cfg.notification_smtp_sender == cfg.notification_smtp_host == ""
    with (
        patch.dict(os.environ, {**environment, "NOTIFICATION_EMAIL_ENABLED": "true"}, clear=True),
        pytest.raises(ConfigurationError, match="NOTIFICATION_SMTP_PORT"),
    ):
        load_settings()


def test_install_route_survives_authenticated_oauth_round_trip() -> None:
    destination = "/#account/install"
    key = Fernet.generate_key().decode()
    token = seal_oauth_flow(state="state", code_verifier="v" * 64, legal_versions={},
                           crypto_key=key, return_to=destination)
    assert open_oauth_flow(token, crypto_key=key, ttl_seconds=600).return_to == destination
    for invalid in ("https://example.org/#account/install", "/#account/install\\other",
                    "/#account/install?next=%0d%0aX-Test:bad"):
        with pytest.raises(SecurityValueError, match="oauth_return_to_invalid"):
            validate_auth_return_to(invalid)


@pytest.mark.parametrize("raw", ("owner", "000000501", str(UUID(int=0))))
def test_invalid_operator_configuration_never_assigns_authority(raw: str) -> None:
    with (
        patch.dict(os.environ, {"OPERATOR_USER_ID": raw}, clear=True),
        pytest.raises(ConfigurationError),
    ):
        optional_uuid("OPERATOR_USER_ID")


def test_public_id_is_exactly_nine_digits() -> None:
    assert format_public_id(1) == "000000001"
    assert format_public_id(999_999_999) == "999999999"

    with pytest.raises(SecurityValueError):
        format_public_id(0)
    with pytest.raises(SecurityValueError):
        format_public_id(1_000_000_000)


def test_public_id_parser_rejects_malformed_or_zero_values() -> None:
    assert parse_public_id("000000001") == 1
    assert parse_public_id("999999999") == 999_999_999

    for value in ("1", "000000000", "1000000000", "00000000x", "²" * 9, "１２３４５６７８９"):
        with pytest.raises(SecurityValueError):
            parse_public_id(value)


def test_secret_encryption_does_not_store_plaintext() -> None:
    key = Fernet.generate_key().decode("ascii")
    plaintext = "t.example-owner-credential"
    encrypted = encrypt_secret(plaintext, key)

    assert encrypted != plaintext.encode()
    assert plaintext.encode() not in encrypted


def test_secret_encryption_round_trip() -> None:
    key = Fernet.generate_key().decode("ascii")
    plaintext = "t.example-owner-credential"
    encrypted = encrypt_secret(plaintext, key)

    assert decrypt_secret(encrypted, key) == plaintext

    wrong_key = Fernet.generate_key().decode("ascii")
    with pytest.raises(SecurityValueError):
        decrypt_secret(encrypted, wrong_key)


def test_pkce_challenge_is_stable_and_urlsafe() -> None:
    verifier = generate_pkce_verifier()
    challenge = pkce_challenge(verifier)

    assert 43 <= len(verifier) <= 128
    assert "=" not in challenge
    assert challenge == pkce_challenge(verifier)


def test_vkid_flow_round_trip_and_tamper_rejection() -> None:
    key = Fernet.generate_key().decode("ascii")
    state = generate_oauth_state()
    verifier = generate_pkce_verifier()
    versions = {
        "privacy_policy": "2026-10-02-v3",
        "personal_data_consent": "2026-10-02-v3",
        "terms": "2026-10-02-v3",
    }
    token = seal_oauth_flow(
        state=state,
        code_verifier=verifier,
        legal_versions=versions,
        crypto_key=key,
    )

    assert open_oauth_flow(
        token,
        crypto_key=key,
        ttl_seconds=600,
    ) == OAuthFlow(state, verifier, versions)

    with pytest.raises(SecurityValueError):
        open_oauth_flow(
            token[:-1] + ("A" if token[-1] != "A" else "B"),
            crypto_key=key,
            ttl_seconds=600,
        )


def test_client_ip_digest_is_keyed() -> None:
    first = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
    second = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")

    assert client_ip_digest("203.0.113.10", first) != client_ip_digest(
        "203.0.113.10",
        second,
    )


def test_auth_route_validator_preserves_filters_and_rejects_injected_flow_payload() -> None:
    import json

    destination = "/#account/market/news?q=%D0%A6%D0%91&filter=all"
    assert validate_auth_return_to(destination) == destination
    key = Fernet.generate_key().decode("ascii")
    token = seal_oauth_flow(state="state", code_verifier="v" * 64, legal_versions={},
                            crypto_key=key, return_to=destination)
    cipher = Fernet(key.encode())
    document = json.loads(cipher.decrypt(token.encode()))
    document["return_to"] = "https://untrusted.invalid"
    injected = cipher.encrypt(json.dumps(document).encode()).decode()
    with pytest.raises(SecurityValueError, match="oauth_return_to_invalid"):
        open_oauth_flow(injected, crypto_key=key, ttl_seconds=600)
    del document["return_to"]
    legacy = cipher.encrypt(json.dumps(document).encode()).decode()
    assert open_oauth_flow(legacy, crypto_key=key, ttl_seconds=600).return_to == "/#account/home"


def _request(client_host: str, headers: dict[str, str]) -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "https",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": [
                (name.lower().encode("ascii"), value.encode("ascii"))
                for name, value in headers.items()
            ],
            "client": (client_host, 12345),
            "server": ("omnicio.ru", 443),
        }
    )


def test_client_ip_ignores_untrusted_forwarded_headers() -> None:
    request = _request(
        "198.51.100.20",
        {
            "x-real-ip": "203.0.113.10",
            "x-forwarded-for": "203.0.113.11",
        },
    )

    assert client_ip(request) == "198.51.100.20"


def test_client_ip_trusts_nginx_overwritten_real_ip_only_from_loopback() -> None:
    request = _request(
        "127.0.0.1",
        {
            "x-real-ip": "203.0.113.10",
            "x-forwarded-for": "192.0.2.55, 203.0.113.10",
        },
    )

    assert client_ip(request) == "203.0.113.10"


def test_client_ip_rejects_invalid_proxy_value() -> None:
    request = _request(
        "127.0.0.1",
        {
            "x-real-ip": "not-an-ip",
            "x-forwarded-for": "203.0.113.10",
        },
    )

    assert client_ip(request) == "unknown"


def test_state_changing_requests_require_canonical_origin() -> None:
    accepted = _request("127.0.0.1", {"origin": CANONICAL_ORIGIN})
    require_same_origin(accepted)

    for headers in ({}, {"origin": "https://evil.example"}):
        rejected = _request("127.0.0.1", headers)
        with pytest.raises(HTTPException) as error:
            require_same_origin(rejected)
        assert error.value.status_code == 403



def test_private_errors_have_unique_server_traces_without_secret_leaks(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "test-credential-must-not-leak"
    with patch("omnicio.main.service") as auth:
        auth.return_value.refresh_session.side_effect = RuntimeError(secret)
        client = TestClient(app)
        first = client.get("/api/me?token=" + secret, headers={"X-Request-ID": secret})
        second = client.get("/api/me")
    assert first.status_code == 500
    request_id = first.headers["x-request-id"]
    assert len(request_id) == 32
    assert all(char in "0123456789abcdef" for char in request_id)
    assert first.json()["request_id"] == request_id
    assert second.headers["x-request-id"] != request_id
    assert first.headers["cache-control"] == "private, no-store"
    assert request_id in caplog.text
    assert secret not in first.text
    assert secret not in caplog.text


@pytest.mark.parametrize("path", ["/api/me", "/api/me/activity", "/api/portfolio/executions"])
def test_private_unauthorized_responses_cannot_be_cached(path: str) -> None:
    with patch("omnicio.main.service") as auth:
        auth.return_value.refresh_session.return_value = None
        response = TestClient(app).get(path)
    assert response.status_code == 401
    assert response.headers["cache-control"] == "private, no-store"
    assert len(response.headers["x-request-id"]) == 32


def test_activity_uses_each_session_owner_and_ignores_browser_identity() -> None:
    a = UserRecord(UUID(int=101), 101, "active", "user")
    b = UserRecord(UUID(int=102), 102, "active", "user")
    database = Mock(spec=Database)
    events = {
        a.id: [{"event_type": "account_created", "created_at": datetime(2026, 10, 1, tzinfo=UTC)}],
        b.id: [{"event_type": "login_succeeded", "created_at": datetime(2026, 10, 2, tzinfo=UTC)}],
    }
    database.recent_activity.side_effect = lambda user_id, *, limit: events[user_id][:limit]
    with (
        patch("omnicio.main.service") as auth,
        patch.object(app.state, "database", database, create=True),
    ):
        auth.return_value.refresh_session.side_effect = lambda token: {"a": a, "b": b}.get(token)
        one = TestClient(app, cookies={"omnicio_session": "a"})
        two = TestClient(app, cookies={"omnicio_session": "b"})
        first = one.get(f"/api/me/activity?user_id={b.id}&limit=1")
        second = two.get(f"/api/me/activity?user_id={a.id}&limit=1")
        invalid = one.get("/api/me/activity?limit=500")
        anonymous = TestClient(app).get("/api/me/activity")
    assert first.status_code == second.status_code == 200
    assert first.json()["events"][0]["event_type"] == "account_created"
    assert second.json()["events"][0]["event_type"] == "login_succeeded"
    assert invalid.status_code == 422
    assert anonymous.status_code == 401
    assert database.recent_activity.call_count == 2
    assert database.recent_activity.call_args_list[0].args == (a.id,)
    assert database.recent_activity.call_args_list[1].args == (b.id,)


@pytest.mark.parametrize("expected", [None, "", "102", "000000000", "000000101"])
def test_stale_tab_cannot_attach_its_broker_token_to_another_session_user(expected) -> None:
    active_user = UserRecord(UUID(int=102), 102, "active", "user")
    with (
        patch("omnicio.main.service") as auth,
        patch("omnicio.main.broker_service") as broker,
        patch("omnicio.main.settings") as configuration,
    ):
        auth.return_value.refresh_session.return_value = active_user
        configuration.return_value.terms_version = "test"
        broker.return_value.connect.return_value = Mock(
            connected=True, environment="prod", account_id="synthetic-account",
            account_name="Synthetic", verified_at=datetime.now(UTC),
        )
        response = TestClient(app, cookies={"omnicio_session": "session-b"}).put(
            "/api/broker/tbank",
            headers={"Origin": CANONICAL_ORIGIN, **(
                {"X-Omnicio-Profile": expected} if expected is not None else {}
            )},
            json={
                "credential": "synthetic-token-from-tab-a", "environment": "prod",
                "account_id": "synthetic-account", "accept_personal_terms": True,
            },
        )
    assert response.status_code == 409
    assert response.json()["detail"] == (
        "profile_context_required" if expected is None else "profile_context_changed"
    )
    assert response.headers["cache-control"] == "private, no-store"
    broker.assert_not_called()


@pytest.mark.parametrize("method,path,payload", [
    ("GET", "/api/me/activity", None),
    ("GET", "/api/portfolio/executions", None),
    ("POST", "/api/broker/tbank/accounts", {
        "credential": "synthetic-token-from-tab-a", "environment": "prod",
        "accept_personal_terms": True,
    }),
    ("DELETE", "/api/broker/tbank", None),
    ("POST", "/api/auth/logout", None),
])
def test_profile_header_never_selects_a_different_tenant(method, path, payload) -> None:
    active_user = UserRecord(UUID(int=102), 102, "active", "user")
    database = Mock(spec=Database)
    with (
        patch("omnicio.main.service") as auth,
        patch("omnicio.main.broker_service") as broker,
        patch("omnicio.main.execution_store") as ledger,
        patch.object(app.state, "database", database, create=True),
    ):
        auth.return_value.refresh_session.return_value = active_user
        response = TestClient(app, cookies={"omnicio_session": "session-b"}).request(
            method, path, json=payload,
            headers={"Origin": CANONICAL_ORIGIN, "X-Omnicio-Profile": "000000101"},
        )
    assert response.status_code == 409
    assert response.json()["detail"] == "profile_context_changed"
    assert response.headers["cache-control"] == "private, no-store"
    assert "set-cookie" not in response.headers
    broker.assert_not_called()
    ledger.assert_not_called()
    database.recent_activity.assert_not_called()
    auth.return_value.logout.assert_not_called()


def test_matching_view_allows_only_session_user_and_expired_logout_still_clears_cookie() -> None:
    active_user = UserRecord(UUID(int=102), 102, "active", "user")
    headers = {"Origin": CANONICAL_ORIGIN, "X-Omnicio-Profile": "000000102"}
    with (
        patch("omnicio.main.service") as auth,
        patch("omnicio.main.broker_service") as broker,
        patch("omnicio.main.execution_store") as ledger,
    ):
        auth.return_value.refresh_session.return_value = active_user
        ledger.return_value.has_active_live_execution.return_value = False
        client = TestClient(app, cookies={"omnicio_session": "session-b"})
        disconnected = client.delete("/api/broker/tbank?user_id=other", headers=headers)
        assert disconnected.status_code == 204
        broker.return_value.disconnect.assert_called_once_with(active_user.id)
        ledger.return_value.revoke_live_mandate.assert_called_once_with(active_user.id)
        logged_out = client.post("/api/auth/logout", headers=headers)
        assert logged_out.status_code == 204
        assert "Max-Age=0" in logged_out.headers["set-cookie"]
        auth.return_value.logout.assert_called_once_with("session-b")
        auth.return_value.refresh_session.return_value = None
        expired = client.post("/api/auth/logout", headers={"Origin": CANONICAL_ORIGIN})
        assert expired.status_code == 204
        assert "Max-Age=0" in expired.headers["set-cookie"]
        anonymous = client.delete("/api/broker/tbank", headers=headers)
        assert anonymous.status_code == 401
        assert broker.return_value.disconnect.call_count == 1


@pytest.mark.parametrize("path", [
    "/api/market/instruments/uid-1/stream", "/api/market/usd-rub/stream",
])
@pytest.mark.parametrize("revoked_during_read", [False, True])
def test_market_stream_suppresses_data_after_session_revocation(path, revoked_during_read) -> None:
    @dataclass
    class PrivateMarketData:
        marker: str = "synthetic-private-market-data"

    active_user = UserRecord(UUID(int=102), 102, "active", "user")
    with (
        patch("omnicio.main.service") as auth,
        patch("omnicio.main.market_service") as market,
    ):
        auth.return_value.refresh_session.return_value = active_user
        client = TestClient(app, cookies={"omnicio_session": "session-b"})
        for query in ("", "?profile_context=000000101"):
            rejected = client.get(path + query)
            assert rejected.status_code == 409
        market.assert_not_called()
        auth.return_value.refresh_session.side_effect = (
            [active_user, active_user, None] if revoked_during_read else [active_user, None]
        )
        market.return_value.instrument_live_state.return_value = PrivateMarketData()
        market.return_value.usd_rub.return_value = PrivateMarketData()
        response = client.get(path + "?profile_context=000000102")
        reads = (market.return_value.instrument_live_state.call_count
                 + market.return_value.usd_rub.call_count)
    assert response.status_code == 200
    assert "profile_context_changed" in response.text
    assert "synthetic-private-market-data" not in response.text
    assert "event: market" not in response.text
    assert "event: quote" not in response.text
    assert reads == int(revoked_during_read)


@pytest.mark.parametrize("disconnect_at", [1, 2])
def test_market_stream_releases_its_slot_even_if_disconnect_precedes_first_chunk(
    disconnect_at: int,
) -> None:
    market = MarketService(broker=Mock(), cbr=Mock())
    owner, other = UUID(int=102), UUID(int=103)
    other_lease = market.acquire_stream(other)

    async def exercise() -> None:
        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def events():
            yield "event: quote\ndata: {}\n\n"

        for _ in range(3):
            sent = 0

            async def send(message):
                nonlocal sent
                sent += 1
                if sent == disconnect_at:
                    raise OSError("synthetic disconnected socket")

            response = _market_stream_response(market, owner, events())
            with pytest.raises(ClientDisconnect):
                await response({"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send)

    try:
        asyncio.run(exercise())
        # Repeated disconnects leave both of this owner's admission slots free.
        owner_leases = [market.acquire_stream(owner), market.acquire_stream(owner)]
        for lease in owner_leases:
            market.release_stream(owner, lease)
        second_other_lease = market.acquire_stream(other)
        with pytest.raises(MarketStreamLimit):
            market.acquire_stream(other)
        market.release_stream(other, second_other_lease)
        market.release_stream(other, other_lease)
    finally:
        market.close()
