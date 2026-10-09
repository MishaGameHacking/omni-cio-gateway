from __future__ import annotations

import asyncio
import base64
import json
import os
import runpy
import tomllib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import UUID, uuid4, uuid5

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from starlette.requests import Request

from omnicio import APPLICATION_USER_AGENT, __version__
from omnicio.config import Settings
from omnicio.db import Database, UserRecord, live_execution_lock_key
from omnicio.main import CANONICAL_ORIGIN, app, instrument_market_stream, usd_rub_market_stream
from omnicio.market import PUBLIC_MARKET_SCOPE
from omnicio.notifications import DeliveryResult, NotificationTransport
from omnicio.security import (
    SecurityValueError,
    decrypt_secret,
    email_code_digest,
    hash_password,
    session_digest,
    verify_password,
)
from omnicio.service import (
    AccountDeletionRejected,
    AuthRateLimited,
    AuthService,
    InvalidCredentials,
    InvalidEmailChallenge,
    LoginUnavailable,
    normalize_login_email,
)

PASSWORD = "Луна и лес у моря 37!"
OWNER = UserRecord(UUID(int=101), 101, "active", "user")


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "postgresql://example.invalid/db",
        "ip_key": base64.urlsafe_b64encode(os.urandom(32)).decode("ascii"),
        "broker_token_crypto_key": Fernet.generate_key().decode("ascii"),
        "privacy_version": "test-current", "consent_version": "test-current",
        "terms_version": "test-current", "session_ttl_seconds": 34_560_000,
        "auth_smtp_host": "smtp.example.invalid", "auth_smtp_sender": "auth@example.org",
    }
    values.update(overrides)
    return Settings(**values)


def auth_service(**overrides: object) -> tuple[AuthService, Mock, Mock]:
    db, transport = Mock(spec=Database), Mock(spec=NotificationTransport)
    db.consume_auth_budget.return_value = True
    db.email_identity.return_value = None
    db.consume_email_challenge.return_value = (OWNER, True)
    db.complete_email_login.return_value = OWNER
    db.refresh_session_digest.return_value = OWNER
    db.delete_user_account.return_value = True
    return AuthService(settings(**overrides), db, transport=transport), db, transport


def test_tenant_cleanup_lock_is_stable_and_user_scoped() -> None:
    user_id = UUID(int=123)
    assert live_execution_lock_key(user_id) == (
        "portfolio-live-execution:00000000-0000-0000-0000-00000000007b"
    )


def test_one_package_release_reaches_framework_http_and_public_config() -> None:
    project = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    expected = project["project"]["version"]
    assert version("omnicio-gateway") == expected == __version__ == app.version
    assert f"OMNICIO/{expected} (+https://omnicio.ru)" == APPLICATION_USER_AGENT
    auth, _, _ = auth_service(release_build="a" * 12)
    with (
        patch.object(app.state, "settings", auth.settings, create=True),
        patch.object(app.state, "auth_service", auth, create=True),
    ):
        response = TestClient(app).get("/api/auth/config")
    assert response.status_code == 200
    assert response.headers["X-Omnicio-Version"] == expected
    config = response.json()
    assert config["release"] == {"version": expected, "build": "a" * 12}
    assert config["mode"] == "public"
    assert config["registration_enabled"] and config["login_enabled"]
    assert config["auth_providers"] == ["email"]
    assert config["email_domains"] == ["gmail.com", "mail.ru", "xmail.ru"]
    assert "registration_max_users" not in config
    assert "vkid" not in str(config) and "tid_enabled" not in config


def test_missing_package_metadata_cannot_silently_report_an_old_release() -> None:
    package_init = str(Path(__file__).parents[1] / "src" / "omnicio" / "__init__.py")
    with (
        patch("importlib.metadata.version", side_effect=PackageNotFoundError("omnicio-gateway")),
        pytest.raises(PackageNotFoundError),
    ):
        runpy.run_path(package_init)


@pytest.mark.parametrize("instrument", [False, True])
def test_public_market_stream_uses_shared_data_and_individual_admission_scope(instrument) -> None:
    request = Request({
        "type": "http", "method": "GET", "path": "/", "headers": [],
        "query_string": b"", "client": ("203.0.113.11", 1234),
    })
    auth, market = Mock(), Mock()
    market.acquire_stream.return_value = "synthetic-lease"

    async def exercise():
        response = (await instrument_market_stream("uid-1", request) if instrument
                    else await usd_rub_market_stream(request))
        await response.body_iterator.aclose()
        return response

    with (
        patch("omnicio.main.service", return_value=auth),
        patch("omnicio.main.market_service", return_value=market),
    ):
        response = asyncio.run(exercise())
    assert response.status_code == 200
    assert response.media_type == "text/event-stream"
    auth.refresh_session.assert_not_called()
    market.acquire_stream.assert_called_once_with(uuid5(PUBLIC_MARKET_SCOPE, "203.0.113.11"))


@pytest.mark.parametrize("email,expected", [
    (" User.Name+portfolio@GMAIL.COM ", "User.Name+portfolio@gmail.com"),
    ("user@mail.ru", "user@mail.ru"), ("user@xmail.ru", "user@xmail.ru"),
])
def test_login_email_has_exact_domain_allowlist_without_unsafe_alias_merging(email, expected):
    assert normalize_login_email(email) == expected


@pytest.mark.parametrize("email", [
    "user@gmail.com.evil.invalid", "user@sub.gmail.com", "user@gmail.com.",
    "user@googlemail.com", "user@yandex.ru", "user@gmаil.com", "user@@gmail.com",
    "User <user@gmail.com>", "user@gmail.com\r\nBcc:other@gmail.com", "user @gmail.com",
])
def test_login_email_rejects_lookalikes_headers_and_other_domains(email):
    with pytest.raises(SecurityValueError):
        normalize_login_email(email)


def test_registration_queues_encrypted_mail_and_hashes_password_before_ownership_proof() -> None:
    auth, db, transport = auth_service()
    result = auth.request_email(
        email="User@GMAIL.COM", password=PASSWORD, client_ip="203.0.113.10", purpose="register",
        accepted_legal_versions=auth.legal_versions(),
    )
    args = db.create_email_challenge.call_args.kwargs
    assert args["email"] == "User@gmail.com"
    assert args["password_hash"].startswith("$argon2id$v=19$m=19456,t=2,p=1$")
    assert verify_password(PASSWORD, args["password_hash"])
    assert args["flow_digest"] == session_digest(result.flow_token)
    document = json.loads(decrypt_secret(args["delivery_ciphertext"], auth._crypto_key))
    assert document["email"] == "User@gmail.com"
    assert len(document["code"]) == 8 and document["code"].isascii()
    assert args["code_digest"] == email_code_digest(
        str(result.challenge_id), document["code"], auth.settings.ip_key,
    )
    assert PASSWORD not in str(args)
    assert document["code"].encode() not in args["delivery_ciphertext"]
    db.complete_email_login.assert_not_called()
    db.consume_email_challenge.assert_not_called()
    transport.send_email.assert_not_called()
    assert result.expires_in_seconds == 600 and result.resend_after_seconds == 60


def test_unavailable_mail_blocks_new_registration_but_not_verified_login_or_legacy_session():
    auth, db, _ = auth_service(auth_smtp_host="", auth_smtp_sender="")
    db.email_identity.return_value = {
        "user_id": OWNER.id, "email": "owner@gmail.com", "password_hash": hash_password(PASSWORD),
        "password_version": 1,
    }
    assert auth.settings.login_ready and not auth.registration_available
    login = auth.login_email("owner@gmail.com", PASSWORD, client_ip="203.0.113.10")
    assert login.public_id == "000000101"
    assert auth.refresh_session("legacy-session") == OWNER
    with pytest.raises(LoginUnavailable, match="email_not_configured"):
        auth.request_email(email="new@gmail.com", password=PASSWORD, purpose="register",
                           client_ip="203.0.113.10", accepted_legal_versions=auth.legal_versions())
    db.create_email_challenge.assert_not_called()


@pytest.mark.parametrize("known", [False, True])
def test_unknown_account_and_wrong_password_have_identical_result_and_one_kdf(known):
    auth, db, _ = auth_service()
    if known:
        db.email_identity.return_value = {"password_hash": hash_password(PASSWORD)}
    with (
        patch("omnicio.service.verify_password", wraps=verify_password) as kdf,
        pytest.raises(InvalidCredentials, match="email_or_password_invalid"),
    ):
        auth.login_email("owner@gmail.com", "Another valid long password", client_ip="test")
    kdf.assert_called_once()
    db.complete_email_login.assert_not_called()


def test_stale_password_snapshot_cannot_create_a_new_session_after_password_reset() -> None:
    auth, db, _ = auth_service()
    identity = {"password_hash": hash_password(PASSWORD), "password_version": 1}
    db.email_identity.return_value = identity
    db.complete_email_login.return_value = None
    with pytest.raises(InvalidCredentials):
        auth.login_email("owner@gmail.com", PASSWORD, client_ip="test")
    assert db.complete_email_login.call_args.args == (identity,)


def test_rate_limit_is_checked_before_expensive_kdf_and_never_stores_raw_identifiers() -> None:
    auth, db, _ = auth_service()
    db.consume_auth_budget.return_value = False
    with patch("omnicio.service.hash_password") as kdf, pytest.raises(AuthRateLimited):
        auth.request_email(email="owner@gmail.com", password=PASSWORD, purpose="register",
                           client_ip="203.0.113.11",
                           accepted_legal_versions=auth.legal_versions())
    kdf.assert_not_called()
    db.create_email_challenge.assert_not_called()
    buckets = db.consume_auth_budget.call_args.args[0]
    assert all(isinstance(digest, bytes) and len(digest) == 32 for digest, _, _ in buckets)
    assert "owner@gmail.com" not in str(buckets) and "203.0.113.11" not in str(buckets)


def test_email_proof_is_bound_to_browser_and_never_reuses_password_reset_for_registration():
    auth, db, _ = auth_service()
    with pytest.raises(InvalidEmailChallenge):
        auth.verify_email(uuid4(), "12345678", "", client_ip="test")
    db.email_challenge.assert_not_called()
    db.email_challenge.return_value = {"email": "owner@gmail.com", "purpose": "reset"}
    with pytest.raises(InvalidEmailChallenge):
        auth.verify_email(uuid4(), "12345678", "flow", client_ip="test")
    db.consume_email_challenge.assert_not_called()


def test_email_verification_passes_exact_original_enrollment_session_and_rotates_session():
    auth, db, _ = auth_service()
    db.email_challenge.return_value = {"email": "owner@gmail.com", "purpose": "enroll"}
    result = auth.verify_email(uuid4(), "12345678", "flow", client_ip="test",
                               enrollment_session="original-session")
    args = db.consume_email_challenge.call_args.kwargs
    assert args["enrollment_session_digest"] == session_digest("original-session")
    assert args["token_digest"] == session_digest(result.session_token)
    assert result.session_token != "original-session"


def test_reset_never_returns_session_and_passes_new_password_verifier_only() -> None:
    auth, db, _ = auth_service()
    db.email_challenge.return_value = {"email": "owner@gmail.com", "purpose": "reset"}
    result = auth.reset_password(uuid4(), "12345678", "flow", password=PASSWORD, client_ip="test")
    assert result is None
    args = db.consume_email_challenge.call_args.kwargs
    assert args["purpose"] == "reset"
    assert verify_password(PASSWORD, args["password_hash"])
    assert PASSWORD not in str(args)
    db.complete_email_login.assert_not_called()


def test_mail_worker_sends_only_claimed_message_then_records_safe_delivery_receipt():
    auth, db, transport = auth_service()
    identity, digest = uuid4(), b"c" * 32
    db.claim_email_delivery.return_value = {
        "id": identity, "purpose": "register", "code_digest": digest,
        "delivery_ciphertext": auth._delivery("owner@gmail.com", "01234567"),
    }
    transport.send_email.return_value = DeliveryResult("accepted", "email_accepted")
    assert auth.deliver_next_email()
    destination, payload = transport.send_email.call_args.args
    assert destination == {"email": "owner@gmail.com"}
    assert "01234567" in payload["body"] and PASSWORD not in payload["body"]
    db.complete_email_delivery.assert_called_once_with(
        identity, digest, delivery_status="accepted", delivery_code="email_accepted",
    )


def registration_payload(auth: AuthService) -> dict[str, object]:
    return {"email": "owner@gmail.com", "password": PASSWORD, "accept_privacy": True,
            "accept_personal_data": True, "accept_terms": True, "confirm_age_18": True,
            "legal_versions": auth.legal_versions()}


def test_http_registration_requires_origin_current_consent_and_returns_only_flow_cookie():
    auth, db, _ = auth_service()
    with patch.object(app.state, "auth_service", auth, create=True):
        client = TestClient(app, base_url=CANONICAL_ORIGIN)
        rejected = client.post("/api/auth/email/register", json=registration_payload(auth))
        assert rejected.status_code == 403
        db.create_email_challenge.assert_not_called()
        stale = client.post("/api/auth/email/register", headers={"Origin": CANONICAL_ORIGIN},
                            json={**registration_payload(auth), "legal_versions": {}})
        assert stale.status_code == 409
        db.create_email_challenge.assert_not_called()
        response = client.post("/api/auth/email/register", headers={"Origin": CANONICAL_ORIGIN},
                               json=registration_payload(auth))
    assert response.status_code == 202
    assert response.json()["status"] == "verification_required"
    cookie = response.headers["set-cookie"]
    assert "omnicio_email_flow=" in cookie and "HttpOnly" in cookie and "Secure" in cookie
    assert "SameSite=strict" in cookie and "Path=/api/auth/email" in cookie
    assert "omnicio_session" not in cookie
    assert set(response.json()) == {
        "status", "challenge_id", "expires_in_seconds", "resend_after_seconds",
    }
    assert PASSWORD not in response.text


@pytest.mark.parametrize("changes", [
    {"password": "sensitive-secret" * 20}, {"password": {"secret": "must-not-leak"}},
    {"role": "admin"}, {"user_id": str(UUID(int=102))},
])
def test_invalid_auth_payloads_do_not_reflect_passwords_or_accept_browser_authority(changes):
    auth, db, _ = auth_service()
    with patch.object(app.state, "auth_service", auth, create=True):
        response = TestClient(app).post(
            "/api/auth/email/register", headers={"Origin": CANONICAL_ORIGIN},
            json={**registration_payload(auth), **changes},
        )
    assert response.status_code == 422
    assert "sensitive-secret" not in response.text and "must-not-leak" not in response.text
    assert "input" not in response.text
    db.create_email_challenge.assert_not_called()


def test_legacy_enrollment_uses_session_owner_and_rejects_stale_tab_before_mail_is_sent():
    auth, db, _ = auth_service()
    with patch.object(app.state, "auth_service", auth, create=True):
        client = TestClient(app, base_url=CANONICAL_ORIGIN,
                            cookies={"omnicio_session": "legacy-session"})
        rejected = client.post("/api/auth/email/enroll", json=registration_payload(auth),
                               headers={"Origin": CANONICAL_ORIGIN,
                                        "X-Omnicio-Profile": "000000102"})
        assert rejected.status_code == 409
        db.create_email_challenge.assert_not_called()
        accepted = client.post("/api/auth/email/enroll", json=registration_payload(auth),
                               headers={"Origin": CANONICAL_ORIGIN,
                                        "X-Omnicio-Profile": "000000101"})
    assert accepted.status_code == 202
    args = db.create_email_challenge.call_args.kwargs
    assert args["user_id"] == OWNER.id
    assert args["enrollment_session_digest"] == session_digest("legacy-session")


def test_removed_social_authentication_and_execution_routes_have_no_handlers():
    paths = {getattr(route, "path", "") for route in app.routes}
    assert not any("/auth/vkid" in path or "/auth/tid" in path for path in paths)
    assert not any("/executions" in path or "/mandates" in path for path in paths)
    assert "/api/portfolio/proposals" not in paths


def test_self_service_account_deletion_requires_exact_session_profile_confirmation():
    auth, db, _ = auth_service()
    with pytest.raises(AccountDeletionRejected):
        auth.delete_account(OWNER, "000000102")
    db.delete_user_account.assert_not_called()
    assert auth.delete_account(OWNER, "000000101")
    db.delete_user_account.assert_called_once_with(OWNER.id)


def test_http_email_proof_rotates_cookie_and_revokes_previous_browser_session():
    auth, db, _ = auth_service()
    db.email_challenge.return_value = {"email": "owner@gmail.com", "purpose": "register"}
    with patch.object(app.state, "auth_service", auth, create=True):
        client = TestClient(app, base_url=CANONICAL_ORIGIN, cookies={
            "omnicio_session": "previous-browser-session", "omnicio_email_flow": "flow",
        })
        response = client.post("/api/auth/email/verify", headers={"Origin": CANONICAL_ORIGIN},
                               json={"challenge_id": str(uuid4()), "code": "12345678"})
    assert response.status_code == 200
    assert response.json() == {"public_id": "000000101", "created": True}
    db.revoke_session.assert_called_once_with(session_digest("previous-browser-session"))
    cookies = response.headers.get_list("set-cookie")
    assert any("omnicio_session=" in value and "HttpOnly" in value and "Secure" in value
               for value in cookies)
    assert "previous-browser-session" not in str(cookies)
    assert any("omnicio_email_flow=" in value and "Max-Age=0" in value for value in cookies)


def test_own_email_is_not_disclosed_after_session_is_revoked_during_read():
    auth, db, _ = auth_service()
    db.refresh_session_digest.side_effect = [OWNER, None]
    db.email_identity_status.return_value = {"email": "private-address@gmail.com"}
    with (
        patch.object(app.state, "auth_service", auth, create=True),
        patch.object(app.state, "database", db, create=True),
    ):
        response = TestClient(app, cookies={"omnicio_session": "session"}).get(
            "/api/auth/identities", headers={"X-Omnicio-Profile": "000000101"},
        )
    assert response.status_code in {401, 409}
    assert "private-address@gmail.com" not in response.text
    db.email_identity_status.assert_called_once_with(OWNER.id)
