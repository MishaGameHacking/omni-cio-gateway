from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from apps.api.private_remote import _PRIVATE_REMOTE_SESSION_POLICY
from omni_cio.web.remote_security_v1 import (
    CSRF_HEADER_NAME,
    TAILSCALE_LOGIN_HEADER,
    PrivateRemoteSecurityMiddlewareV1,
    PrivateRemoteSecurityPolicyV1,
    csrf_token_for_session,
    install_private_remote_session_routes,
    tailscale_login_sha256,
)
from omni_cio.web.session_v1 import SessionPolicyV1, SessionRegistryV1


HOST = "omni-owner.example-tailnet.ts.net"
OWNER_LOGIN = "owner@example.test"
COOKIE = "omni_v10_session"
ORIGIN = f"https://{HOST}"
NOW = datetime(2026, 8, 14, 13, 30, tzinfo=timezone.utc)


@dataclass
class Clock:
    value: datetime = NOW

    def __call__(self) -> datetime:
        return self.value


def owner_headers(*, origin: bool = False) -> dict[str, str]:
    headers = {TAILSCALE_LOGIN_HEADER: OWNER_LOGIN}
    if origin:
        headers["Origin"] = ORIGIN
    return headers


def make_client(
    *,
    login_limit: int = 6,
    mutation_limit: int = 60,
    session_policy: SessionPolicyV1 | None = None,
    client_host: str = "127.0.0.1",
) -> tuple[TestClient, SessionRegistryV1, Clock]:
    clock = Clock()
    sessions = SessionRegistryV1(session_policy)
    app = FastAPI()
    install_private_remote_session_routes(
        app,
        sessions=sessions,
        session_cookie_name=COOKIE,
        now=clock,
    )

    @app.get("/monitor")
    def monitor() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/mutate")
    def mutate() -> dict[str, bool]:
        return {"ok": True}

    app.add_middleware(
        PrivateRemoteSecurityMiddlewareV1,
        policy=PrivateRemoteSecurityPolicyV1(
            expected_host=HOST,
            owner_login_sha256=tailscale_login_sha256(OWNER_LOGIN),
            login_attempts_per_minute=login_limit,
            mutations_per_minute=mutation_limit,
        ),
        session_cookie_name=COOKIE,
        sessions=sessions,
        now=clock,
    )
    client = TestClient(
        app,
        base_url=ORIGIN,
        client=(client_host, 50000),
    )
    return client, sessions, clock


def remote_login(client: TestClient) -> str:
    response = client.post(
        "/api/v10/web/private-remote-login",
        headers=owner_headers(origin=True),
        json={},
    )
    assert response.status_code == 200
    token = client.cookies.get(COOKIE)
    assert token is not None
    return token


def csrf(client: TestClient) -> str:
    response = client.get(
        "/api/v10/web/session/csrf",
        headers=owner_headers(),
    )
    assert response.status_code == 200
    value = response.json()["csrf_token"]
    assert isinstance(value, str)
    assert len(value) == 64
    return value


def test_remote_session_policy_is_short_and_defined() -> None:
    assert _PRIVATE_REMOTE_SESSION_POLICY.idle_lifetime == timedelta(hours=2)
    assert _PRIVATE_REMOTE_SESSION_POLICY.absolute_lifetime == timedelta(hours=24)


def test_policy_requires_exact_tsnet_host_and_owner_fingerprint() -> None:
    with pytest.raises(ValueError, match="WP22A_TAILSCALE_HOST_INVALID"):
        PrivateRemoteSecurityPolicyV1(
            expected_host="public.example.com",
            owner_login_sha256="a" * 64,
        )
    with pytest.raises(ValueError, match="WP22A_TAILSCALE_HOST_INVALID"):
        PrivateRemoteSecurityPolicyV1(
            expected_host="bad..tail.ts.net",
            owner_login_sha256="a" * 64,
        )
    with pytest.raises(ValueError, match="WP22A_OWNER_LOGIN_FINGERPRINT_INVALID"):
        PrivateRemoteSecurityPolicyV1(
            expected_host=HOST,
            owner_login_sha256="not-a-hash",
        )


def test_rfc2047_tailscale_identity_decodes_before_fingerprint() -> None:
    encoded = "=?utf-8?q?Ferris_B=C3=BCller?="
    assert tailscale_login_sha256(encoded) == tailscale_login_sha256("Ferris Büller")


def test_backend_peer_must_be_loopback_even_with_valid_identity_headers() -> None:
    client, _, _ = make_client(client_host="100.64.0.10")
    response = client.get("/monitor", headers=owner_headers())
    assert response.status_code == 403
    assert response.json()["detail"] == "BACKEND_PEER_NOT_LOOPBACK"


def test_host_and_tailscale_owner_identity_fail_closed() -> None:
    client, _, _ = make_client()
    missing_identity = client.get("/monitor")
    assert missing_identity.status_code == 403
    assert missing_identity.json()["detail"] == "PRIVATE_REMOTE_OWNER_REQUIRED"

    wrong_identity = client.get(
        "/monitor",
        headers={TAILSCALE_LOGIN_HEADER: "other@example.test"},
    )
    assert wrong_identity.status_code == 403

    wrong_host = client.get(
        "https://other.example-tailnet.ts.net/monitor",
        headers=owner_headers(),
    )
    assert wrong_host.status_code == 400
    assert wrong_host.json()["detail"] == "HOST_NOT_ALLOWED"


def test_host_header_accepts_only_exact_hostname_and_default_https_port() -> None:
    client, _, _ = make_client()
    accepted = client.get(
        "/monitor",
        headers={**owner_headers(), "Host": f"{HOST}:443"},
    )
    assert accepted.status_code == 200

    for hostile_host in (
        f"{HOST}:444",
        f"{HOST}:evil",
        f"{HOST}.",
        f"{HOST}.evil.example",
    ):
        rejected = client.get(
            "/monitor",
            headers={**owner_headers(), "Host": hostile_host},
        )
        assert rejected.status_code == 400
        assert rejected.json()["detail"] == "HOST_NOT_ALLOWED"


def test_private_remote_responses_have_security_headers() -> None:
    client, _, _ = make_client()
    response = client.get("/monitor", headers=owner_headers())
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["strict-transport-security"] == "max-age=31536000"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"


def test_private_remote_login_sets_secure_cookie_and_rotates_session() -> None:
    client, sessions, clock = make_client()
    first = remote_login(client)
    cookie = client.cookies.jar.get(COOKIE)
    assert cookie is not None
    assert cookie.secure is True
    assert cookie.has_nonstandard_attr("HttpOnly")
    assert cookie.get_nonstandard_attr("SameSite") == "strict"
    assert sessions.stored_plaintext_token_count() == 0

    second = remote_login(client)
    assert second != first
    assert sessions.resolve(first, now=clock()) is None
    assert sessions.resolve(second, now=clock()) is not None


def test_stolen_session_without_matching_tailnet_identity_is_rejected() -> None:
    client, _, _ = make_client()
    remote_login(client)
    response = client.get(
        "/monitor",
        headers={TAILSCALE_LOGIN_HEADER: "attacker@example.test"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "PRIVATE_REMOTE_OWNER_REQUIRED"


def test_forged_session_with_matching_derived_csrf_is_rejected() -> None:
    client, _, _ = make_client()
    forged = "synthetic-forged-session"
    client.cookies.set(COOKIE, forged)
    response = client.post(
        "/mutate",
        headers={
            **owner_headers(origin=True),
            CSRF_HEADER_NAME: csrf_token_for_session(forged),
        },
        json={},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "AUTHENTICATION_REQUIRED"


def test_unsafe_request_requires_exact_origin_session_and_session_bound_csrf() -> None:
    client, _, _ = make_client()
    remote_login(client)
    csrf_token = csrf(client)

    no_origin = client.post(
        "/mutate",
        headers={TAILSCALE_LOGIN_HEADER: OWNER_LOGIN, CSRF_HEADER_NAME: csrf_token},
        json={},
    )
    assert no_origin.status_code == 403
    assert no_origin.json()["detail"] == "ORIGIN_REQUIRED"

    wrong_origin = client.post(
        "/mutate",
        headers={
            TAILSCALE_LOGIN_HEADER: OWNER_LOGIN,
            "Origin": "https://evil.example",
            CSRF_HEADER_NAME: csrf_token,
        },
        json={},
    )
    assert wrong_origin.status_code == 403
    assert wrong_origin.json()["detail"] == "ORIGIN_NOT_ALLOWED"

    trailing_slash_origin = client.post(
        "/mutate",
        headers={
            TAILSCALE_LOGIN_HEADER: OWNER_LOGIN,
            "Origin": f"{ORIGIN}/",
            CSRF_HEADER_NAME: csrf_token,
        },
        json={},
    )
    assert trailing_slash_origin.status_code == 403
    assert trailing_slash_origin.json()["detail"] == "ORIGIN_NOT_ALLOWED"

    missing_csrf = client.post(
        "/mutate",
        headers=owner_headers(origin=True),
        json={},
    )
    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["detail"] == "CSRF_VALIDATION_FAILED"

    accepted = client.post(
        "/mutate",
        headers={
            **owner_headers(origin=True),
            CSRF_HEADER_NAME: csrf_token,
        },
        json={},
    )
    assert accepted.status_code == 200


def test_foreign_cors_preflight_is_denied_and_monitoring_get_is_not_rate_limited() -> (
    None
):
    client, _, _ = make_client(mutation_limit=1)
    preflight = client.options(
        "/mutate",
        headers={
            TAILSCALE_LOGIN_HEADER: OWNER_LOGIN,
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert preflight.status_code == 403
    assert "access-control-allow-origin" not in preflight.headers

    for _ in range(100):
        response = client.get("/monitor", headers=owner_headers())
        assert response.status_code == 200


def test_login_and_mutation_rate_limits_are_bounded() -> None:
    client, _, _ = make_client(login_limit=2, mutation_limit=1)
    remote_login(client)
    remote_login(client)
    third = client.post(
        "/api/v10/web/private-remote-login",
        headers=owner_headers(origin=True),
        json={},
    )
    assert third.status_code == 429
    assert third.json()["detail"] == "LOGIN_RATE_LIMITED"

    csrf_token = csrf(client)
    first_mutation = client.post(
        "/mutate",
        headers={**owner_headers(origin=True), CSRF_HEADER_NAME: csrf_token},
        json={},
    )
    assert first_mutation.status_code == 200
    second_mutation = client.post(
        "/mutate",
        headers={**owner_headers(origin=True), CSRF_HEADER_NAME: csrf_token},
        json={},
    )
    assert second_mutation.status_code == 429
    assert second_mutation.json()["detail"] == "API_MUTATION_RATE_LIMITED"


def test_expired_session_cannot_obtain_csrf_or_mutate() -> None:
    policy = SessionPolicyV1(
        idle_lifetime=timedelta(seconds=1),
        absolute_lifetime=timedelta(seconds=2),
    )
    client, _, clock = make_client(session_policy=policy)
    token = remote_login(client)
    csrf_token = csrf(client)
    clock.value += timedelta(seconds=2)

    expired = client.get(
        "/api/v10/web/session/csrf",
        headers=owner_headers(),
    )
    assert expired.status_code == 401

    client.cookies.set(COOKIE, token)
    mutation = client.post(
        "/mutate",
        headers={**owner_headers(origin=True), CSRF_HEADER_NAME: csrf_token},
        json={},
    )
    assert mutation.status_code == 401
    assert mutation.json()["detail"] == "AUTHENTICATION_REQUIRED"


def test_telegram_initdata_cannot_bootstrap_wp22a_owner_authority() -> None:
    client, _, _ = make_client()
    header_replay = client.get(
        "/monitor",
        headers={
            **owner_headers(),
            "X-Telegram-Init-Data": "synthetic-replayed-init-data",
        },
    )
    assert header_replay.status_code == 403
    assert header_replay.json()["detail"] == "TELEGRAM_MINI_APP_AUTH_NOT_ACTIVE"

    query_replay = client.get(
        "/monitor?tgWebAppData=synthetic",
        headers=owner_headers(),
    )
    assert query_replay.status_code == 403
    assert query_replay.json()["detail"] == "TELEGRAM_MINI_APP_AUTH_NOT_ACTIVE"
