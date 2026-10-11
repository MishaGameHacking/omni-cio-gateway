"""OAuth cryptographic proof, provider boundaries and the native HTTP handoff."""

from __future__ import annotations

import base64
import json
import time
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi.testclient import TestClient
from test_service import OWNER, auth_service, settings

from omnicio.main import app
from omnicio.social_auth import (
    TELEGRAM_ISSUER,
    SocialAuthError,
    SocialAuthService,
    SocialProvider,
)
from omnicio.social_store import SocialAuthStore


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


@pytest.fixture
def signed_proof():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = private.public_key().public_numbers()
    provider = SocialProvider(settings(telegram_client_id="123456"))
    provider._json = Mock(return_value={"keys": [{
        "kid": "test-key", "alg": "RS256", "kty": "RSA", "use": "sig",
        "n": b64(numbers.n.to_bytes(256, "big")), "e": b64(numbers.e.to_bytes(3, "big")),
    }]})

    def token(**changes):
        claims = {"iss": TELEGRAM_ISSUER, "aud": "123456", "sub": "123456789",
                  "iat": int(time.time()), "exp": int(time.time()) + 300, "nonce": "test-nonce"}
        claims.update(changes)
        head = b64(json.dumps({"alg": "RS256", "kid": "test-key"}).encode())
        body = b64(json.dumps(claims).encode())
        message = (head + "." + body).encode()
        signature = private.sign(message, padding.PKCS1v15(), hashes.SHA256())
        return message.decode() + "." + b64(signature)
    return provider, token


def test_telegram_requires_signed_subject_audience_issuer_time_and_nonce(signed_proof):
    provider, token = signed_proof
    assert provider._telegram_subject(token(), "test-nonce") == "123456789"
    for changes in [{"aud": "another-app"}, {"iss": "https://attacker.invalid"},
                    {"exp": int(time.time()) - 1}, {"iat": int(time.time()) + 300},
                    {"iat": True}, {"nonce": "another-flow"}, {"sub": True}, {"sub": "0"}]:
        with pytest.raises(SocialAuthError, match="social_proof_invalid"):
            provider._telegram_subject(token(**changes), "test-nonce")
    valid = token()
    parts = valid.split(".")
    parts[1] = b64(json.dumps({"sub": "999"}).encode())
    with pytest.raises(SocialAuthError):
        provider._telegram_subject(".".join(parts), "test-nonce")
    parts[0] = b64(b'{"alg":"none","kid":"test-key"}')
    with pytest.raises(SocialAuthError):
        provider._telegram_subject(".".join(parts), "test-nonce")


def test_vk_exchange_binds_state_device_verifier_and_verified_user():
    provider = SocialProvider(settings(vkid_app_id="3456"))
    provider._json = Mock(side_effect=[
        {"state": "request-state", "user_id": 1234, "access_token": "ephemeral-provider-token"},
        {"user": {"user_id": "1234", "email": "never-merge@gmail.com"}},
    ])
    result = provider.exchange("vkid", "code", "device", "request-state", {"verifier": "secret"})
    assert result == "1234"
    request = provider._json.call_args_list[0].args[1]
    assert request["device_id"] == "device"
    assert request["code_verifier"] == "secret"
    assert request["redirect_uri"].endswith("/vkid/callback")
    provider._json = Mock(return_value={"state": "other-flow"})
    with pytest.raises(SocialAuthError):
        provider.exchange("vkid", "code", "device", "request-state", {"verifier": "secret"})
    provider._json = Mock(side_effect=[
        {"state": "request-state", "user_id": 1234, "access_token": "token"},
        {"user": {"user_id": "9876"}},
    ])
    with pytest.raises(SocialAuthError):
        provider.exchange("vkid", "code", "device", "request-state", {"verifier": "secret"})


def test_start_uses_independent_app_secret_state_and_pkce_and_no_extra_scopes():
    auth, db, _ = auth_service(telegram_client_id="1234", telegram_client_secret="test-only")
    auth.social.store = Mock(spec=SocialAuthStore)
    result = auth.social.start("telegram", purpose="login", android_package="ru.omnicio.app",
                               client_ip="127.0.0.1", user=None, current_session=None)
    params = parse_qs(urlsplit(result["authorization_url"]).query)
    assert params["scope"] == ["openid"]
    assert params["code_challenge_method"] == ["S256"]
    assert params["state"][0] != result["flow_token"]
    assert result["flow_token"] not in result["authorization_url"]
    assert "test-only" not in result["authorization_url"]
    assert db.consume_auth_budget.called


def test_native_handoff_has_no_browser_session_and_requires_app_cookie_and_origin():
    auth, db, _ = auth_service(telegram_client_id="1234", telegram_client_secret="test-only")
    auth.social = Mock(spec=SocialAuthService)
    flow = str(uuid4())
    auth.social.start.return_value = {"flow_id": flow, "flow_token": "a" * 43,
                                     "authorization_url": TELEGRAM_ISSUER + "/auth?state=opaque",
                                     "expires_in_seconds": 600}
    auth.social.callback.return_value = ("ru.omnicio.app.debug", True)
    auth.social.complete.return_value = (OWNER, False, "new-session-secret")
    with (patch.object(app.state, "auth_service", auth, create=True),
          patch.object(app.state, "settings", auth.settings, create=True),
          patch.object(app.state, "database", db, create=True)):
        client = TestClient(app, base_url="https://omnicio.ru")
        start = client.post("/api/auth/social/telegram/start", headers={"Origin": "https://omnicio.ru"},
                            json={"android_package": "ru.omnicio.app.debug"})
        assert start.status_code == 200
        assert "flow_token" not in start.json()
        assert "httponly" in start.headers["set-cookie"].lower()
        assert "secure" in start.headers["set-cookie"].lower()
        callback = client.get("/api/auth/social/telegram/callback?state=opaque&code=secret-code")
        assert callback.status_code == 200
        assert "ru.omnicio.app.debug://auth" in callback.text
        assert "secret-code" not in callback.text
        assert "set-cookie" not in callback.headers
        assert callback.headers["Referrer-Policy"] == "no-referrer"
        denied = client.post("/api/auth/social/complete", json={"flow_id": flow})
        assert denied.status_code == 403
        completed = client.post("/api/auth/social/complete", json={"flow_id": flow},
                                headers={"Origin": "https://omnicio.ru"})
        assert completed.json()["public_id"] == "000000101"
        assert auth.social.complete.call_args.args[1] == "a" * 43
        assert "new-session-secret" not in completed.text
        duplicate = client.get("/api/auth/social/telegram/callback?state=a&state=b&code=secret")
        assert duplicate.status_code == 400


def test_unconfigured_provider_and_malformed_state_never_call_provider():
    auth, _, _ = auth_service()
    auth.social.provider = Mock(spec=SocialProvider)
    with pytest.raises(SocialAuthError, match="not_configured"):
        auth.social.start("telegram", purpose="login", android_package="ru.omnicio.app",
                          client_ip="127.0.0.1", user=None, current_session=None)
    assert not auth.social.provider.exchange.called
