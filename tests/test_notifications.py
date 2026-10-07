"""Delivery boundaries and RFC known-answer checks; no provider connections."""

from __future__ import annotations

import base64
import json
import smtplib
from datetime import UTC, datetime
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils

from omnicio.notifications import (
    NotificationConfig,
    NotificationService,
    NotificationTransport,
    _log_worker_failure,
    _public_address,
    delivery_time,
    encrypt_push,
    normalize_email,
    normalize_subscription,
    push_public_key,
    vapid_authorization,
)
from omnicio.workspace import default_preferences

AUTH = "BTBZMqHH6r4Tts7J_aSIgg"
RECEIVER = (
    "BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcx"
    "aOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4"
)
SENDER = "yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw"


def test_worker_failure_logs_only_safe_type_without_original_message_or_traceback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "private-provider-token-canary"
    try:
        raise ValueError(secret)
    except ValueError as error:
        _log_worker_failure("notification_worker_failed", error)
    assert secret not in caplog.text
    assert "notification_worker_failed" in caplog.text
    assert "ValueError" in caplog.text
    record = caplog.records[-1]
    assert record.exc_info is not None
    assert record.exc_info[2] is None
    sanitized = record.exc_info[1]
    assert sanitized is not None
    assert sanitized.__context__ is None
    assert sanitized.__cause__ is None


@pytest.mark.parametrize("configured", [True, False])
def test_operational_alert_recipient_is_server_configured_not_a_database_role(
    configured: bool,
) -> None:
    operator, ordinary = uuid4(), uuid4()
    database = Mock()
    database.collect_operational_metrics.return_value = {"status": "attention"}
    database.has_legal_versions.return_value = True
    database.pool.connection.return_value.__enter__ = Mock(return_value=database)
    database.pool.connection.return_value.__exit__ = Mock(return_value=False)
    # The accepted schema keeps every application user's database role 'user'.
    database.execute.return_value.fetchall.return_value = [
        {"id": operator, "role": "user"}, {"id": ordinary, "role": "user"},
    ]
    service = NotificationService(
        database,
        NotificationConfig(crypto_key="test-unused",
                           operator_user_id=operator if configured else None),
        legal_versions={}, transport=Mock(),
    )
    with patch.object(service, "queue_events") as queue_events, \
            patch.object(service, "queue_operator_alert") as queue_alert, \
            patch.object(service, "deliver_one", return_value=False):
        service.run_pending()
    assert queue_events.call_count == 2
    assert queue_alert.call_count == int(configured)
    if configured:
        assert queue_alert.call_args.args[0] == operator


def decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def subscription(endpoint: str = "https://fcm.googleapis.com/fcm/send/test-only") -> dict:
    return {"endpoint": endpoint, "keys": {"p256dh": RECEIVER, "auth": AUTH}}


def test_rfc8291_encrypted_payload_matches_published_known_answer() -> None:
    """Section 5 and Appendix A, independent of our own decrypt implementation."""
    private = ec.derive_private_key(int.from_bytes(decode(SENDER)), ec.SECP256R1())
    encrypted = encrypt_push(
        subscription(), b"When I grow up, I want to be a watermelon",
        salt=decode("DGv6ra1nlYgDCS1FRnbzlw"), sender_private=private,
    )
    expected = decode(
        "DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27ml"
        "mlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A_yl95bQpu6cVPT"
        "pK4Mqgkf1CXztLVBSt2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgSxsj_Qulcy4a-fN"
    )
    assert encrypted == expected


def test_vapid_jwt_is_bound_to_origin_and_verifies_with_public_key() -> None:
    config = NotificationConfig(crypto_key="test-unused", vapid_private_key=SENDER,
                                vapid_subject="mailto:operator@example.org")
    now = datetime(2026, 10, 7, 12, tzinfo=UTC)
    authorization = vapid_authorization(config, subscription()["endpoint"], now)
    jwt = authorization.split("t=", 1)[1].split(",", 1)[0]
    header, claims, signature = jwt.split(".")
    payload = json.loads(decode(claims))
    assert payload == {"aud": "https://fcm.googleapis.com",
                       "sub": "mailto:operator@example.org", "exp": int(now.timestamp()) + 3600}
    raw = decode(signature)
    public = ec.EllipticCurvePublicKey.from_encoded_point(
        ec.SECP256R1(), decode(push_public_key(SENDER)),
    )
    public.verify(utils.encode_dss_signature(int.from_bytes(raw[:32]), int.from_bytes(raw[32:])),
                  f"{header}.{claims}".encode(), ec.ECDSA(hashes.SHA256()))


@pytest.mark.parametrize("endpoint", [
    "http://fcm.googleapis.com/send/a", "https://fcm.googleapis.com.evil.test/send/a",
    "https://localhost/send/a", "https://127.0.0.1/send/a", "https://[::1]/send/a",
    "https://fcm.googleapis.com:8443/send/a", "https://user@fcm.googleapis.com/send/a",
    "https://fcm.googleapis.com/send/a#fragment", "https://notify.windows.com.evil.test/send/a",
])
def test_push_endpoints_cannot_target_arbitrary_or_insecure_servers(endpoint: str) -> None:
    document = subscription(endpoint)
    with pytest.raises(ValueError):
        normalize_subscription(document)


def test_push_validation_rejects_non_curve_key_and_dns_rebinding_targets() -> None:
    invalid = subscription()
    invalid["keys"]["p256dh"] = base64.urlsafe_b64encode(b"\x04" + bytes(64)).decode()
    with pytest.raises(ValueError):
        normalize_subscription(invalid)
    answers = [
        (2, 1, 6, "", ("142.250.1.1", 443)),
        (2, 1, 6, "", ("127.0.0.1", 443)),
    ]
    with patch("omnicio.notifications.socket.getaddrinfo", return_value=answers), \
            pytest.raises(ValueError, match="notification_endpoint_dns"):
        _public_address("fcm.googleapis.com")


@pytest.mark.parametrize("address", ["a@example.org\r\nBcc:x@evil.test", "a@localhost",
                                      "a..b@example.org", "a@-example.org", "a@exam..org"])
def test_email_header_injection_and_invalid_addresses_are_rejected(address: str) -> None:
    with pytest.raises(ValueError):
        normalize_email(address)


def test_quiet_delivery_crosses_midnight_and_obeys_timezone() -> None:
    prefs = default_preferences()
    prefs["quiet_hours"]["enabled"] = True
    now = datetime(2026, 10, 7, 20, 15, tzinfo=UTC)
    assert delivery_time(prefs, now) == datetime(2026, 10, 8, 5, tzinfo=UTC)
    outside = datetime(2026, 10, 8, 6, tzinfo=UTC)
    assert delivery_time(prefs, outside) == outside


@pytest.mark.parametrize(("status", "expected", "expired"), [
    (201, "accepted", False), (410, "failed", True),
    (429, "queued", False), (302, "failed", False),
])
def test_push_status_and_no_redirect_following(status: int, expected: str, expired: bool) -> None:
    config = NotificationConfig(crypto_key="unused", vapid_private_key=SENDER,
                                vapid_subject="mailto:operator@example.org")
    conn = Mock()
    conn.getresponse.return_value.status = status
    conn.getresponse.return_value.getheader.return_value = "120"
    with patch("omnicio.notifications._public_address", return_value="142.250.1.1"), \
            patch("omnicio.notifications._PinnedHTTPSConnection", return_value=conn) as factory:
        result = NotificationTransport(config).send_push(subscription(), {
            "tag": "test-delivery", "title": "Test", "body": "No personal data", "url": "/#events",
        })
    assert result.status == expected
    assert result.expired == expired
    factory.assert_called_once_with("fcm.googleapis.com", "142.250.1.1")
    assert conn.request.call_count == 1
    assert conn.request.call_args.kwargs["headers"]["Content-Encoding"] == "aes128gcm"


@pytest.mark.parametrize(("error", "expected"), [
    (smtplib.SMTPDataError(451, b"temporary rejection"), "queued"),
    (smtplib.SMTPDataError(550, b"permanent rejection"), "failed"),
    (smtplib.SMTPServerDisconnected("unknown after DATA"), "uncertain"),
    (None, "accepted"),
])
def test_email_uses_tls_and_retains_ambiguous_outcome(
    error: Exception | None, expected: str,
) -> None:
    smtp = Mock()
    smtp.__enter__ = Mock(return_value=smtp)
    smtp.__exit__ = Mock(return_value=False)
    smtp.send_message.side_effect = error
    config = NotificationConfig(crypto_key="unused", smtp_host="smtp.example.org",
                                smtp_sender="operator@example.org")
    with patch("omnicio.notifications.smtplib.SMTP_SSL", return_value=smtp) as connect:
        result = NotificationTransport(config).send_email({"email": "verified@example.org"}, {
            "title": "Test", "body": "No real delivery", "tag": "stable-dedup-key",
        })
    assert result.status == expected
    assert connect.call_args.kwargs["context"].check_hostname is True
    assert smtp.send_message.call_args.args[0]["Message-ID"] == "<stable-dedup-key@omnicio.ru>"
