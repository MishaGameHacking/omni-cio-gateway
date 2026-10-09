"""Delivery boundaries and RFC known-answer checks; no provider connections."""

from __future__ import annotations

import base64
import json
import smtplib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils
from psycopg_pool import PoolClosed, PoolTimeout

from omnicio.db import Database
from omnicio.notifications import (
    NotificationConfig,
    NotificationService,
    NotificationTransport,
    _log_worker_failure,
    _public_address,
    delivery_error,
    delivery_time,
    encrypt_push,
    normalize_email,
    normalize_subscription,
    push_public_key,
    validate_push_configuration,
    vapid_authorization,
)
from omnicio.workspace import default_preferences

AUTH = "BTBZMqHH6r4Tts7J_aSIgg"
RECEIVER = (
    "BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcx"
    "aOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4"
)
SENDER = "yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw"


def test_disabled_email_cannot_break_configured_push_startup() -> None:
    config = NotificationConfig(
        crypto_key="test-unused", enabled=True, vapid_private_key=SENDER,
        vapid_subject="https://omnicio.ru", smtp_port=-1,
        smtp_mode="invalid", smtp_sender="invalid\r\nheader", smtp_host="legacy.example.org",
    )
    database = Mock(spec=Database)
    service = NotificationService(database, config, legal_versions={})
    assert service.push_configured
    assert not service.email_configured
    enabled = replace(config, email_enabled=True)
    with pytest.raises(ValueError, match="notification_smtp_invalid"):
        NotificationService(database, enabled, legal_versions={})


@pytest.mark.parametrize("private_key,subject", [
    ("invalid-key", "https://omnicio.ru"),
    (base64.urlsafe_b64encode(bytes(32)).decode("ascii"), "https://omnicio.ru"),
    (SENDER, "http://omnicio.ru"),
    (SENDER, "https://omnicio.ru\r\ninvalid"),
    (SENDER, "mailto:not-an-email"),
])
def test_push_configuration_rejects_unusable_keys_and_subjects_before_startup(
    private_key: str, subject: str,
) -> None:
    database, transport = Mock(spec=Database), Mock(spec=NotificationTransport)
    config = NotificationConfig(
        crypto_key="unused", enabled=True, vapid_private_key=private_key,
        vapid_subject=subject,
    )
    with pytest.raises(ValueError):
        validate_push_configuration(private_key, subject)
    with pytest.raises(ValueError):
        NotificationService(database, config, legal_versions={}, transport=transport)
    assert database.mock_calls == []
    assert transport.mock_calls == []


@pytest.mark.parametrize("private_key,subject,configured", [
    ("", "unused-invalid-subject", False),
    (SENDER, "https://omnicio.ru", True),
    (SENDER, "mailto:operator@example.org", True),
])
def test_push_configuration_keeps_missing_key_optional_and_accepts_valid_keys(
    private_key: str, subject: str, configured: bool,
) -> None:
    validate_push_configuration(private_key, subject)
    service = NotificationService(Mock(spec=Database), NotificationConfig(
        crypto_key="unused", enabled=True, vapid_private_key=private_key,
        vapid_subject=subject,
    ), legal_versions={})
    assert service.push_configured is configured


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


def test_subscription_canonicalizes_only_authority_and_key_encoding() -> None:
    raw = subscription("https://FCM.GOOGLEAPIS.COM:443/a%2Fb/../opaque?token=%2f%2E")
    raw["keys"]["auth"] += "=="
    canonical = normalize_subscription(raw)
    assert canonical["endpoint"] == "https://fcm.googleapis.com/a%2Fb/../opaque?token=%2f%2E"
    assert canonical["keys"]["auth"] == AUTH
    assert normalize_subscription(canonical) == canonical


@pytest.mark.parametrize("failure", [PoolTimeout("private-database-detail"),
                                    PoolClosed("private-database-detail")])
def test_authorization_preflight_failure_retries_without_a_provider_request(
    failure: Exception, caplog: pytest.LogCaptureFixture,
) -> None:
    database = Mock(spec=Database)
    database.pool = Mock()
    database.pool.connection.side_effect = failure
    transport = NotificationTransport(NotificationConfig(
        crypto_key="unused", vapid_private_key=SENDER, vapid_subject="https://omnicio.ru",
    ), database=database)
    with patch("omnicio.notifications._public_address") as dns, \
            patch("omnicio.notifications._PinnedHTTPSConnection") as connect:
        result = transport.send_push(subscription(), {"tag": "test"})
    assert result.status == "queued"
    assert result.code == "push_authorization_unavailable"
    assert result.retry_after == 60
    assert "private-database-detail" not in caplog.text
    dns.assert_not_called()
    connect.assert_not_called()


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
                       "sub": "mailto:operator@example.org", "exp": int(now.timestamp()) + 7200}
    raw = decode(signature)
    public = ec.EllipticCurvePublicKey.from_encoded_point(
        ec.SECP256R1(), decode(push_public_key(SENDER)),
    )
    public.verify(utils.encode_dss_signature(int.from_bytes(raw[:32]), int.from_bytes(raw[32:])),
                  f"{header}.{claims}".encode(), ec.ECDSA(hashes.SHA256()))


def test_vapid_origin_cache_reuses_one_signed_token_concurrently_for_an_hour() -> None:
    transport = NotificationTransport(NotificationConfig(
        crypto_key="unused", vapid_private_key=SENDER, vapid_subject="https://omnicio.ru",
    ))
    now = datetime(2026, 10, 7, 12, tzinfo=UTC)
    apple = "https://web.push.apple.com/push/"
    with ThreadPoolExecutor(max_workers=8) as workers:
        tokens = list(workers.map(
            lambda n: transport._authorization(apple + str(n), now), range(32),
        ))
    assert tokens[0] is not None
    assert len(set(tokens)) == 1
    assert transport._authorization(apple + "later", now + timedelta(seconds=3599)) == tokens[0]
    google = transport._authorization(subscription()["endpoint"], now)
    assert google != tokens[0]
    renewed = transport._authorization(apple + "later", now + timedelta(hours=1))
    assert renewed is not None
    assert renewed != tokens[0]
    jwt = renewed.split("t=", 1)[1].split(",", 1)[0]
    claims = json.loads(decode(jwt.split(".")[1]))
    assert claims == {"aud": "https://web.push.apple.com", "sub": "https://omnicio.ru",
                      "exp": int((now + timedelta(hours=3)).timestamp())}


def test_vapid_cache_bounds_new_origins_without_eviction_and_handles_clock_jump() -> None:
    transport = NotificationTransport(NotificationConfig(
        crypto_key="unused", vapid_private_key=SENDER, vapid_subject="https://omnicio.ru",
    ))
    now = datetime(2026, 10, 7, 12, tzinfo=UTC)
    first = transport._authorization("https://node-0.push.apple.com/path", now)
    for number in range(1, 128):
        assert transport._authorization(f"https://node-{number}.push.apple.com/path", now)
    assert transport._authorization("https://extra.push.apple.com/path", now) is None
    assert transport._authorization("https://node-0.push.apple.com/other", now) == first
    earlier = now - timedelta(days=1)
    repaired = transport._authorization("https://node-0.push.apple.com/path", earlier)
    assert repaired is not None
    assert repaired != first
    jwt = repaired.split("t=", 1)[1].split(",", 1)[0]
    claims = json.loads(decode(jwt.split(".")[1]))
    assert claims["exp"] == int((earlier + timedelta(hours=2)).timestamp())


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


@pytest.mark.parametrize(("now", "frequency", "expected"), [
    ("2026-10-07T17:29:00+00:00", "daily", "2026-10-06T17:30:00+00:00"),
    ("2026-10-07T17:30:00+00:00", "daily", "2026-10-07T17:30:00+00:00"),
    ("2026-10-05T17:29:00+00:00", "weekly", "2026-09-28T17:30:00+00:00"),
    ("2026-10-07T17:30:00+00:00", "weekly", "2026-10-05T17:30:00+00:00"),
])
def test_digest_obeys_selected_local_time_and_latest_complete_period(
    now: str, frequency: str, expected: str,
) -> None:
    prefs = {**default_preferences(), "digest_time": "20:30", "digest_timezone": "Europe/Moscow",
             "digest_frequency": frequency}
    actual = NotificationService._digest_boundary(prefs, datetime.fromisoformat(now))
    assert actual.astimezone(UTC) == datetime.fromisoformat(expected)


@pytest.mark.parametrize(("now", "expected"), [
    ("2026-03-29T01:05:00+00:00", "2026-03-29T01:00:00+00:00"),
    ("2026-10-25T00:45:00+00:00", "2026-10-24T00:30:00+00:00"),
    ("2026-10-25T01:45:00+00:00", "2026-10-25T01:30:00+00:00"),
])
def test_digest_skipped_or_repeated_local_minute_has_one_delivery_boundary(
    now: str, expected: str,
) -> None:
    prefs = {**default_preferences(), "digest_time": "02:30", "digest_timezone": "Europe/Berlin",
             "digest_frequency": "daily"}
    actual = NotificationService._digest_boundary(prefs, datetime.fromisoformat(now))
    assert actual.astimezone(UTC) == datetime.fromisoformat(expected)


def test_delivery_diagnostics_explain_ambiguity_without_promising_retry_or_receipt() -> None:
    unknown = delivery_error("email_result_unknown", "uncertain")
    assert unknown is not None
    assert unknown["retryable"] is False
    assert unknown["action_code"] == "check_inbox"
    expired = delivery_error("push_subscription_expired", "failed")
    assert expired is not None
    assert expired["action_code"] == "reconnect"
    backoff = delivery_error("push_rate_limited", "queued")
    assert backoff is not None
    assert backoff["retryable"] is True
    exhausted = delivery_error("push_rate_limited", "failed")
    assert exhausted is not None
    assert exhausted["retryable"] is False
    assert exhausted["action_code"] == "contact_support"
    assert delivery_error("push_provider_accepted", "accepted") is None
    safe = delivery_error("secret-provider-token", "failed")
    assert safe is not None
    assert safe["code"] == "delivery_error_unknown"
    assert "secret-provider-token" not in json.dumps(safe)


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
    assert conn.request.call_args.kwargs["headers"]["TTL"] == "86400"


def test_push_uses_the_remaining_test_lifetime_at_the_provider_boundary() -> None:
    config = NotificationConfig(crypto_key="unused", vapid_private_key=SENDER,
                                vapid_subject="https://omnicio.ru")
    conn = Mock()
    conn.getresponse.return_value.status = 201
    conn.getresponse.return_value.getheader.return_value = ""
    transport = NotificationTransport(config)
    document = subscription()
    payload = {"tag": "explicit-device-test", "title": "Test", "body": "Generic"}
    with patch("omnicio.notifications._public_address", return_value="142.250.1.1"), \
            patch("omnicio.notifications._PinnedHTTPSConnection", return_value=conn):
        result = transport.send_push(document, payload, ttl_seconds=17)
    assert result.status == "accepted"
    assert conn.request.call_args.kwargs["headers"]["TTL"] == "17"
    assert conn.request.call_count == 1
    assert conn.close.call_count == 1


@pytest.mark.parametrize(("status", "raw_retry", "expected", "delay"), [
    pytest.param(201, "²", "accepted", 0, id="accepted-unicode-digit"),
    pytest.param(201, "9" * 9000, "accepted", 0, id="accepted-oversized-digits"),
    pytest.param(429, "²", "queued", 60, id="rate-limited-unicode-digit"),
    pytest.param(503, "9" * 9000, "queued", 86400, id="unavailable-oversized-digits"),
    pytest.param(429, "0" * 9000 + "120", "queued", 120, id="rate-limited-leading-zeros"),
    pytest.param(503, " 12 ", "queued", 30, id="unavailable-short-delay"),
    pytest.param(429, "not-a-delay", "queued", 60, id="rate-limited-malformed"),
])
def test_push_receipt_ignores_irrelevant_retry_headers_and_bounds_retry_decimal(
    status: int, raw_retry: str, expected: str, delay: int,
) -> None:
    config = NotificationConfig(crypto_key="unused", vapid_private_key=SENDER,
                                vapid_subject="https://omnicio.ru")
    conn = Mock()
    conn.getresponse.return_value.status = status
    conn.getresponse.return_value.getheader.return_value = raw_retry
    with patch("omnicio.notifications._public_address", return_value="142.250.1.1"), \
            patch("omnicio.notifications._PinnedHTTPSConnection", return_value=conn):
        result = NotificationTransport(config).send_push(subscription(), {
            "tag": "safe-retry", "title": "Test", "body": "Generic",
        })
    assert result.status == expected
    assert result.retry_after == delay
    assert conn.request.call_count == 1
    assert conn.close.call_count == 1
    if status == 201:
        conn.getresponse.return_value.getheader.assert_not_called()


@pytest.mark.parametrize(("error", "expected"), [
    (smtplib.SMTPDataError(451, b"temporary rejection"), "queued"),
    (smtplib.SMTPDataError(550, b"permanent rejection"), "failed"),
    (smtplib.SMTPRecipientsRefused({"verified@example.org": (450, b"try later")}), "queued"),
    (smtplib.SMTPRecipientsRefused({"verified@example.org": (550, b"no mailbox")}), "failed"),
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
    smtp.close.assert_called_once()


@pytest.mark.parametrize("error", [
    smtplib.SMTPResponseException(451, b"temporary QUIT rejection"),
    smtplib.SMTPServerDisconnected("disconnected after DATA acceptance"),
])
def test_email_cleanup_failure_cannot_retry_an_accepted_message(error: Exception) -> None:
    smtp = Mock()
    smtp.__enter__ = Mock(return_value=smtp)
    smtp.__exit__ = Mock(side_effect=error)
    smtp.quit.side_effect = error
    config = NotificationConfig(crypto_key="unused", smtp_host="smtp.example.org",
                                smtp_sender="operator@example.org")
    with patch("omnicio.notifications.smtplib.SMTP_SSL", return_value=smtp):
        result = NotificationTransport(config).send_email({"email": "verified@example.org"}, {
            "title": "Test", "body": "No real delivery", "tag": "stable-dedup-key",
        })
    assert result.status == "accepted"
    smtp.send_message.assert_called_once()
    smtp.close.assert_called_once()


def test_email_cleanup_cannot_replace_an_ambiguous_send_with_a_retryable_error() -> None:
    smtp = Mock()
    smtp.__enter__ = Mock(return_value=smtp)
    smtp.__exit__ = Mock(side_effect=smtplib.SMTPResponseException(451, b"QUIT unavailable"))
    smtp.send_message.side_effect = smtplib.SMTPServerDisconnected("DATA result unknown")
    config = NotificationConfig(crypto_key="unused", smtp_host="smtp.example.org",
                                smtp_sender="operator@example.org")
    with patch("omnicio.notifications.smtplib.SMTP_SSL", return_value=smtp):
        result = NotificationTransport(config).send_email({"email": "verified@example.org"}, {
            "title": "Test", "body": "No real delivery", "tag": "stable-dedup-key",
        })
    assert result.status == "uncertain"
    smtp.quit.assert_not_called()
    smtp.close.assert_called_once()


@pytest.mark.parametrize(("target", "expected"), [
    ("/#events", "/#events"),
    ("/#events?event=" + "a" * 64, "/#events?event=" + "a" * 64),
    ("/#settings", "/#settings"),
    ("https://untrusted.example/path", "/#settings"),
    ("//untrusted.example/#events", "/#settings"),
    ("/#events?event=bad\r\nhttps://untrusted.example", "/#settings"),
])
def test_email_opens_its_confirmed_cabinet_target_and_rejects_external_routes(
    target: str, expected: str,
) -> None:
    smtp = Mock()
    smtp.__enter__ = Mock(return_value=smtp)
    smtp.__exit__ = Mock(return_value=False)
    config = NotificationConfig(crypto_key="unused", smtp_host="smtp.example.org",
                                smtp_sender="operator@example.org")
    with patch("omnicio.notifications.smtplib.SMTP_SSL", return_value=smtp):
        outcome = NotificationTransport(config).send_email({"email": "test@example.org"}, {
            "title": "Test", "body": "Synthetic event", "tag": "fixed", "url": target,
        })
    assert outcome.status == "accepted"
    body = smtp.send_message.call_args.args[0].get_content()
    assert body.strip().endswith("https://omnicio.ru" + expected)
    assert "untrusted.example" not in body


def test_worker_health_reports_missing_stale_and_failed_progress_without_tenant_data() -> None:
    now = datetime(2026, 10, 7, 12, tzinfo=UTC)
    cur = Mock()
    cur.fetchall.return_value = [
        {"worker_name": "notifications", "checked_at": now - timedelta(minutes=6),
         "completed_at": now - timedelta(minutes=6), "status": "ok"},
        {"worker_name": "portfolio_refresh", "checked_at": now,
         "completed_at": now, "status": "attention"},
    ]
    workers, issues = Database._workers_metrics(cur, now, active_users=2, connected_accounts=1)
    assert workers["notifications"]["status"] == "stale"
    assert workers["portfolio_refresh"]["status"] == "attention"
    assert workers["portfolio_daily"]["status"] == "not_reported"
    assert set(issues) == {"notifications_worker_stale", "portfolio_refresh_worker_attention",
                           "portfolio_daily_worker_not_reported"}
    cur.fetchall.return_value = []
    assert Database._workers_metrics(cur, now, active_users=0, connected_accounts=0)[1] == []


def test_notification_heartbeat_reports_owner_failure_while_others_continue() -> None:
    database = Mock()
    database.collect_operational_metrics.return_value = {"status": "ok"}
    database.has_legal_versions.return_value = True
    database.pool.connection.return_value.__enter__ = Mock(return_value=database)
    database.pool.connection.return_value.__exit__ = Mock(return_value=False)
    database.execute.return_value.fetchall.return_value = [{"id": uuid4()}, {"id": uuid4()}]
    service = NotificationService(database, NotificationConfig(crypto_key="test-unused"),
                                  legal_versions={}, transport=Mock())
    with patch.object(service, "_process_pending_user",
                      side_effect=[ValueError("synthetic"), None]) as process:
        service.run_pending()
    assert process.call_count == 2
    database.record_worker_heartbeat.assert_called_with("notifications", status="attention")


def test_previous_worker_failure_remains_visible_during_the_next_live_attempt() -> None:
    now = datetime(2026, 10, 7, 12, tzinfo=UTC)
    row = {"checked_at": now, "completed_at": now - timedelta(seconds=30),
           "status": "running", "completed_status": "attention"}
    cur = Mock()
    cur.fetchall.return_value = [{"worker_name": "notifications", **row}]
    workers, issues = Database._workers_metrics(cur, now, active_users=2, connected_accounts=0)
    assert workers["notifications"]["status"] == "attention"
    assert issues == ["notifications_worker_attention"]
    row["checked_at"] = now - timedelta(minutes=6)
    assert Database._worker_health("notifications", row, now)["status"] == "stale"
    row.update(checked_at=now, completed_status="ok")
    assert Database._worker_health("notifications", row, now)["status"] == "running"
