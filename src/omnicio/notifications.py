"""Opt-in notification delivery with encrypted custody and a durable tenant outbox.

Web Push implements RFC 8291 / RFC 8292 using the existing cryptography dependency.
An accepted provider response is not a receipt from the person's device. Ambiguous
SMTP/network outcomes are retained for review, never blindly retried as delivered.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import http.client
import ipaddress
import json
import logging
import re
import secrets
import smtplib
import socket
import ssl
import struct
from collections.abc import Mapping
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from threading import Event, Thread
from typing import Any, cast
from urllib.parse import urlsplit
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .db import Database
from .security import decrypt_secret, encrypt_secret
from .workspace import quiet_now
from .workspace_store import WorkspaceNotFound, WorkspaceStore, _event_record, _json

logger = logging.getLogger(__name__)
_EMAIL = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@[A-Za-z0-9.-]{1,189}")
_PUSH_HOSTS = {"fcm.googleapis.com", "updates.push.services.mozilla.com", "web.push.apple.com"}
_PUSH_SUFFIXES = (".push.apple.com", ".notify.windows.com")
_MAILTO_SCHEME = "mailto:"
_SETTINGS_TARGET = "/#settings"


def _log_worker_failure(code: str, error: Exception) -> None:
    # Preserve a useful failure class without provider messages, destinations,
    # credentials, chained exceptions or the original traceback in logs.
    sanitized = RuntimeError(type(error).__name__)
    logger.exception(code, exc_info=(RuntimeError, sanitized, None))


class NotificationUnavailable(RuntimeError):
    """The requested channel is not configured; no provider mutation occurred."""


@dataclass(frozen=True, slots=True)
class NotificationConfig:
    crypto_key: str
    public_origin: str = "https://omnicio.ru"
    enabled: bool = False
    vapid_private_key: str = ""
    vapid_subject: str = ""
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_sender: str = ""
    smtp_mode: str = "tls"
    operator_user_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    status: str
    code: str
    retry_after: int = 0
    expired: bool = False


def _decode(value: str, length: int) -> bytes:
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9_-]+={0,2}", value) is None:
        raise ValueError("notification_key_invalid")
    try:
        decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except ValueError as exc:
        raise ValueError("notification_key_invalid") from exc
    if len(decoded) != length:
        raise ValueError("notification_key_invalid")
    return decoded


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def normalize_email(value: str) -> str:
    if not isinstance(value, str) or len(value) > 254 or _EMAIL.fullmatch(value) is None:
        raise ValueError("notification_email_invalid")
    local, domain = value.rsplit("@", 1)
    if (".." in local or local.startswith(".") or local.endswith(".")
            or "." not in domain or ".." in domain
            or any(not label or label.startswith("-") or label.endswith("-")
                   for label in domain.split("."))):
        raise ValueError("notification_email_invalid")
    return local + "@" + domain.lower()


def normalize_subscription(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) - {"endpoint", "keys", "expirationTime"}:
        raise ValueError("notification_subscription_invalid")
    endpoint = value.get("endpoint")
    if not isinstance(endpoint, str) or not 20 <= len(endpoint) <= 2048:
        raise ValueError("notification_endpoint_invalid")
    parsed = urlsplit(endpoint)
    host = parsed.hostname or ""
    if (parsed.scheme != "https" or parsed.port not in {None, 443}
            or parsed.username or parsed.password or parsed.fragment
            or not parsed.path or not parsed.path.startswith("/")
            or any(ord(char) < 33 or ord(char) > 126 for char in endpoint)
            or not (host in _PUSH_HOSTS or host.endswith(_PUSH_SUFFIXES))):
        raise ValueError("notification_endpoint_invalid")
    keys = value.get("keys")
    if not isinstance(keys, dict) or set(keys) != {"p256dh", "auth"}:
        raise ValueError("notification_subscription_invalid")
    public = _decode(keys["p256dh"], 65)
    ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), public)
    _decode(keys["auth"], 16)
    return {"endpoint": endpoint, "keys": {"p256dh": _b64(public), "auth": keys["auth"]}}


def push_public_key(private_key: str) -> str:
    key = ec.derive_private_key(int.from_bytes(_decode(private_key, 32)), ec.SECP256R1())
    return _b64(key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint,
    ))


def encrypt_push(
    subscription: Mapping[str, Any], message: bytes, *,
    salt: bytes | None = None, sender_private: ec.EllipticCurvePrivateKey | None = None,
) -> bytes:
    """RFC 8291 aes128gcm single-record envelope; injectable entropy for RFC vectors."""
    if len(message) > 3993:
        raise ValueError("notification_payload_too_large")
    receiver = _decode(subscription["keys"]["p256dh"], 65)
    auth = _decode(subscription["keys"]["auth"], 16)
    key = sender_private or ec.generate_private_key(ec.SECP256R1())
    sender = key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint,
    )
    secret = key.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(
        ec.SECP256R1(), receiver,
    ))
    ikm = HKDF(algorithm=hashes.SHA256(), length=32, salt=auth,
               info=b"WebPush: info\x00" + receiver + sender).derive(secret)
    salt = salt or secrets.token_bytes(16)
    if len(salt) != 16:
        raise ValueError("notification_salt_invalid")
    cek = HKDF(algorithm=hashes.SHA256(), length=16, salt=salt,
               info=b"Content-Encoding: aes128gcm\x00").derive(ikm)
    nonce = HKDF(algorithm=hashes.SHA256(), length=12, salt=salt,
                 info=b"Content-Encoding: nonce\x00").derive(ikm)
    return salt + struct.pack("!IB", 4096, len(sender)) + sender + AESGCM(cek).encrypt(
        nonce, message + b"\x02", None,
    )


def vapid_authorization(config: NotificationConfig, endpoint: str, now: datetime) -> str:
    parsed = urlsplit(endpoint)
    header = _b64(b'{"typ":"JWT","alg":"ES256"}')
    body = _b64(_json({
        "aud": f"{parsed.scheme}://{parsed.hostname}",
        "exp": int(now.timestamp()) + 3600, "sub": config.vapid_subject,
    }).encode())
    private = ec.derive_private_key(
        int.from_bytes(_decode(config.vapid_private_key, 32)), ec.SECP256R1(),
    )
    r, s = utils.decode_dss_signature(private.sign(
        f"{header}.{body}".encode(), ec.ECDSA(hashes.SHA256()),
    ))
    token = f"{header}.{body}.{_b64(r.to_bytes(32) + s.to_bytes(32))}"
    return f"vapid t={token}, k={push_public_key(config.vapid_private_key)}"


def _public_address(host: str) -> str:
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    if not addresses:
        raise ValueError("notification_endpoint_dns")
    for result in addresses:
        address = ipaddress.ip_address(result[4][0])
        if (not address.is_global or address.is_multicast or address.is_reserved
                or address.is_loopback or address.is_link_local):
            raise ValueError("notification_endpoint_dns")
    return str(addresses[0][4][0])


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, address: str) -> None:
        self.tls_context = ssl.create_default_context()
        super().__init__(host, timeout=10, context=self.tls_context)
        self.address = address

    def connect(self) -> None:
        # Resolve once, reject all non-public answers, connect to that exact IP,
        # and still validate TLS against the original allowlisted hostname.
        raw = socket.create_connection((self.address, 443), timeout=10)
        try:
            self.sock = self.tls_context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


class NotificationTransport:
    def __init__(self, config: NotificationConfig) -> None:
        self.config = config

    def send_push(self, destination: Mapping[str, Any], payload: dict[str, Any]) -> DeliveryResult:
        subscription = normalize_subscription(destination)
        endpoint = subscription["endpoint"]
        parsed = urlsplit(endpoint)
        host = parsed.hostname or ""
        try:
            address = _public_address(host)
        except (OSError, ValueError):
            return DeliveryResult("queued", "push_dns_unavailable", 300)
        content = encrypt_push(subscription, _json(payload).encode())
        try:
            with closing(_PinnedHTTPSConnection(host, address)) as conn:
                conn.request("POST", parsed.path + ("?" + parsed.query if parsed.query else ""),
                             body=content, headers={
                                 "Authorization": vapid_authorization(
                                     self.config, endpoint, datetime.now(UTC),
                                 ),
                                 "Content-Encoding": "aes128gcm", "TTL": "86400",
                                 "Content-Type": "application/octet-stream",
                                 "Topic": hashlib.sha256(payload["tag"].encode()).hexdigest()[:32],
                             })
                response = conn.getresponse()
                status = response.status
                raw_retry = response.getheader("Retry-After", "")
                retry = min(86400, max(30, int(raw_retry))) if raw_retry.isdigit() else 60
                response.read(4096)
        except (OSError, http.client.HTTPException):
            return DeliveryResult("uncertain", "push_result_unknown")
        if status in {200, 201, 202}:
            return DeliveryResult("accepted", "push_provider_accepted")
        if status in {404, 410}:
            return DeliveryResult("failed", "push_subscription_expired", expired=True)
        if status in {429, 503}:
            return DeliveryResult("queued", "push_rate_limited", retry)
        return DeliveryResult("failed", "push_provider_rejected")

    def send_email(self, destination: Mapping[str, Any], payload: dict[str, Any]) -> DeliveryResult:
        message = EmailMessage()
        message["From"] = self.config.smtp_sender
        message["To"] = normalize_email(destination["email"])
        message["Subject"] = payload["title"]
        message["Message-ID"] = f"<{payload['tag']}@{urlsplit(self.config.public_origin).hostname}>"
        message.set_content(payload["body"] + "\n\n" + self.config.public_origin + _SETTINGS_TARGET)
        context = ssl.create_default_context()
        try:
            client = (smtplib.SMTP_SSL(self.config.smtp_host, self.config.smtp_port,
                                      timeout=10, context=context)
                      if self.config.smtp_mode == "tls" else smtplib.SMTP(
                          self.config.smtp_host, self.config.smtp_port, timeout=10,
                      ))
            with client:
                if self.config.smtp_mode == "starttls":
                    client.ehlo()
                    client.starttls(context=context)
                    client.ehlo()
                if self.config.smtp_username:
                    client.login(self.config.smtp_username, self.config.smtp_password)
                client.send_message(message)
        except smtplib.SMTPResponseException as exc:
            if 400 <= exc.smtp_code < 500:
                return DeliveryResult("queued", "email_temporary_rejection", 300)
            return DeliveryResult("failed", "email_provider_rejected")
        except smtplib.SMTPRecipientsRefused:
            return DeliveryResult("failed", "email_recipient_rejected")
        except (OSError, smtplib.SMTPException):
            return DeliveryResult("uncertain", "email_result_unknown")
        return DeliveryResult("accepted", "email_provider_accepted")


def delivery_time(preferences: Mapping[str, Any], now: datetime) -> datetime:
    if not quiet_now(preferences, now):
        return now
    # Iterate real UTC minutes so daylight-saving gaps and repeated local times
    # behave exactly like the cabinet's timezone-aware quiet-hours predicate.
    candidate = now.replace(second=0, microsecond=0)
    for _ in range(26 * 60):
        candidate += timedelta(minutes=1)
        if not quiet_now(preferences, candidate):
            return candidate
    raise ValueError("notification_quiet_schedule_invalid")


class NotificationService:
    def __init__(
        self, database: Database, config: NotificationConfig, *,
        legal_versions: dict[str, str], transport: NotificationTransport | None = None,
    ) -> None:
        self.database = database
        self.workspace = WorkspaceStore(database)
        self.config = config
        self.legal_versions = dict(legal_versions)
        self.transport = transport or NotificationTransport(config)
        self._stop = Event()
        self._wake = Event()
        self._thread: Thread | None = None
        self._maintenance_at = datetime.min.replace(tzinfo=UTC)
        self._user_cursor: UUID | None = None
        if config.public_origin != "https://omnicio.ru":
            raise ValueError("notification_origin_invalid")
        if config.smtp_mode not in {"tls", "starttls"} or not 1 <= config.smtp_port <= 65535:
            raise ValueError("notification_smtp_invalid")
        if config.smtp_sender:
            normalize_email(config.smtp_sender)
        if config.vapid_private_key:
            push_public_key(config.vapid_private_key)
            subject = config.vapid_subject
            if (any(ord(char) < 33 or ord(char) > 126 for char in subject)
                    or not subject.startswith((_MAILTO_SCHEME, "https://"))):
                raise ValueError("notification_vapid_subject_invalid")
            if subject.startswith(_MAILTO_SCHEME):
                normalize_email(subject.removeprefix(_MAILTO_SCHEME))

    @property
    def push_configured(self) -> bool:
        return bool(self.config.enabled and self.config.vapid_private_key
                    and self.config.vapid_subject)

    @property
    def email_configured(self) -> bool:
        return bool(self.config.enabled and self.config.smtp_host and self.config.smtp_sender)

    def _seal(self, value: object) -> bytes:
        return encrypt_secret(_json(value), self.config.crypto_key)

    def _open(self, value: bytes) -> dict[str, Any]:
        parsed = json.loads(decrypt_secret(bytes(value), self.config.crypto_key))
        if not isinstance(parsed, dict):
            raise ValueError("notification_stored_payload_invalid")
        return parsed

    def _hash(self, value: str) -> str:
        return hmac.new(self.config.crypto_key.encode(), value.encode(), hashlib.sha256).hexdigest()

    def status(self, user_id: UUID) -> dict[str, Any]:
        with self.workspace._transaction(user_id) as cur:
            cur.execute(
                "UPDATE notification_channels SET status = 'expired', "
                "verification_digest = NULL WHERE user_id = %s AND status = 'pending' "
                "AND (verification_expires_at <= now() OR verification_attempts >= 5)", (user_id,),
            )
            cur.execute(
                "SELECT id, kind, label, status, verified_at, created_at, "
                "verification_expires_at, verification_attempts, destination_ciphertext "
                "FROM notification_channels WHERE user_id = %s "
                "AND status <> 'revoked' ORDER BY created_at", (user_id,),
            )
            channels = [dict(row) for row in cur.fetchall()]
            for channel in channels:
                destination = self._open(channel.pop("destination_ciphertext"))
                channel["endpoint_fingerprint"] = (hashlib.sha256(
                    destination["endpoint"].encode(),
                ).hexdigest() if channel["kind"] == "push" else None)
                channel["verification_attempts_remaining"] = max(
                    0, 5 - channel.pop("verification_attempts"),
                )
            cur.execute(
                "SELECT id, channel_id, kind, status, attempts, last_error, created_at, "
                "accepted_at, next_attempt_at FROM notification_outbox WHERE user_id = %s "
                "ORDER BY created_at DESC, id DESC LIMIT 30", (user_id,),
            )
            deliveries = [dict(row) for row in cur.fetchall()]
        return {
            "push_configured": self.push_configured, "email_configured": self.email_configured,
            "vapid_public_key": push_public_key(self.config.vapid_private_key)
            if self.push_configured else None,
            "channels": channels, "deliveries": deliveries,
            "receipt_scope": "provider_acceptance_only",
        }

    def _insert_channel(
        self, cur: Any, user_id: UUID, *, kind: str, destination: dict[str, Any], label: str,
        status: str, now: datetime, code: str | None = None,
    ) -> UUID:
        identity = destination.get("endpoint") or destination["email"]
        identity_hash = self._hash(identity)
        cur.execute(
            "SELECT count(*) AS total FROM notification_channels WHERE user_id = %s "
            "AND status IN ('active', 'pending') AND NOT (kind = %s AND destination_hash = %s)",
            (user_id, kind, identity_hash),
        )
        if cur.fetchone()["total"] >= 8:
            raise ValueError("notification_channel_limit")
        cur.execute(
            "SELECT COALESCE(max(revision), 0) AS revision FROM workspace_events "
            "WHERE user_id = %s", (user_id,),
        )
        revision = int(cur.fetchone()["revision"])
        ident = uuid4()
        cur.execute(
            "INSERT INTO notification_channels (id, user_id, kind, destination_hash, "
            "destination_ciphertext, label, status, verification_digest, "
            "verification_expires_at, last_verification_at, event_revision, verified_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (user_id, kind, destination_hash) DO UPDATE SET "
            "destination_ciphertext = EXCLUDED.destination_ciphertext, label = EXCLUDED.label, "
            "status = EXCLUDED.status, verification_digest = EXCLUDED.verification_digest, "
            "verification_expires_at = EXCLUDED.verification_expires_at, "
            "verification_attempts = 0, last_verification_at = EXCLUDED.last_verification_at, "
            "event_revision = CASE WHEN notification_channels.status = 'active' "
            "AND EXCLUDED.status = 'active' THEN notification_channels.event_revision "
            "ELSE EXCLUDED.event_revision END, "
            "verified_at = CASE WHEN notification_channels.status = 'active' "
            "AND EXCLUDED.status = 'active' THEN notification_channels.verified_at "
            "ELSE EXCLUDED.verified_at END, "
            "updated_at = now() RETURNING id",
            (ident, user_id, kind, identity_hash, self._seal(destination), label, status,
             None,
             now + timedelta(minutes=15) if code else None, now if code else None,
             revision, now if status == "active" else None),
        )
        channel_id = UUID(str(cur.fetchone()["id"]))
        if code:
            cur.execute(
                "UPDATE notification_channels SET verification_digest = %s "
                "WHERE user_id = %s AND id = %s",
                (bytes.fromhex(self._hash(f"{user_id}:{channel_id}:{code}")),
                 user_id, channel_id),
            )
        return channel_id

    def subscribe_push(
        self, user_id: UUID, subscription: dict[str, Any], label: str = "Это устройство",
    ) -> dict[str, Any]:
        if not self.push_configured:
            raise NotificationUnavailable("notification_push_not_configured")
        normalized = normalize_subscription(subscription)
        if (not isinstance(label, str) or not 1 <= len(label.strip()) <= 100
                or any(ord(char) < 32 for char in label)):
            raise ValueError("notification_label_invalid")
        with self.workspace._transaction(user_id) as cur:
            ident = self._insert_channel(
                cur, user_id, kind="push", destination=normalized, label=label.strip(),
                status="active", now=datetime.now(UTC),
            )
        self._wake.set()
        return {"id": str(ident), "status": "active"}

    def request_email_verification(self, user_id: UUID, email: str) -> dict[str, Any]:
        if not self.email_configured:
            raise NotificationUnavailable("notification_email_not_configured")
        email = normalize_email(email)
        now = datetime.now(UTC)
        code = f"{secrets.randbelow(1_000_000):06d}"
        local, domain = email.rsplit("@", 1)
        label = local[:1] + "***@" + domain
        with self.workspace._transaction(user_id) as cur:
            cur.execute(
                "SELECT count(*) AS total, max(created_at) AS latest "
                "FROM notification_outbox WHERE user_id = %s AND kind = 'verification' "
                "AND created_at > %s", (user_id, now - timedelta(hours=1)),
            )
            recent = cur.fetchone()
            if (recent["total"] >= 3 or recent["latest"] is not None
                    and recent["latest"] > now - timedelta(minutes=2)):
                raise ValueError("notification_verification_rate_limited")
            ident = self._insert_channel(
                cur, user_id, kind="email", destination={"email": email}, label=label,
                status="pending", now=now, code=code,
            )
            cur.execute(
                "UPDATE notification_outbox SET status = 'cancelled', "
                "last_error = 'verification_replaced' WHERE user_id = %s AND channel_id = %s "
                "AND status = 'queued'", (user_id, ident),
            )
            self._enqueue(cur, user_id, ident, "verification:" + str(uuid4()), "verification", {
                "title": "Подтверждение уведомлений OMNICIO",
                "body": f"Ваш код подтверждения: {code}. Срок действия — 15 минут. "
                        "Введите его в настройках OMNICIO. Если вы не запрашивали подключение, "
                        "проигнорируйте письмо. Финансовые действия этот код не разрешает.",
                "url": _SETTINGS_TARGET,
            }, now)
        self._wake.set()
        return {"id": str(ident), "status": "pending", "label": label,
                "expires_at": (now + timedelta(minutes=15)).isoformat()}

    def verify_email(self, user_id: UUID, channel_id: UUID, code: str) -> dict[str, Any]:
        if not isinstance(code, str) or re.fullmatch(r"\d{6}", code, flags=re.ASCII) is None:
            raise ValueError("notification_verification_invalid")
        now = datetime.now(UTC)
        accepted = False
        with self.workspace._transaction(user_id) as cur:
            cur.execute(
                "SELECT * FROM notification_channels WHERE user_id = %s AND id = %s "
                "AND kind = 'email' FOR UPDATE", (user_id, channel_id),
            )
            row = cur.fetchone()
            if row is None:
                raise WorkspaceNotFound("notification_channel_not_found")
            if (row["status"] == "pending" and row["verification_expires_at"] > now
                    and row["verification_attempts"] < 5):
                accepted = hmac.compare_digest(
                    bytes(row["verification_digest"]),
                    bytes.fromhex(self._hash(f"{user_id}:{channel_id}:{code}")),
                )
                cur.execute(
                    "UPDATE notification_channels SET verification_attempts = "
                    "verification_attempts + 1, status = %s, verified_at = %s, "
                    "verification_digest = CASE WHEN %s THEN NULL ELSE verification_digest END, "
                    "updated_at = %s WHERE user_id = %s AND id = %s",
                    ("active" if accepted else "pending", now if accepted else None,
                     accepted, now, user_id, channel_id),
                )
        # Wrong attempts must commit instead of being rolled back by the exception.
        if not accepted:
            raise ValueError("notification_verification_invalid")
        self._wake.set()
        return {"id": str(channel_id), "status": "active"}

    def revoke_channel(self, user_id: UUID, channel_id: UUID) -> dict[str, bool]:
        with self.workspace._transaction(user_id) as cur:
            cur.execute(
                "UPDATE notification_channels SET status = 'revoked', verification_digest = NULL, "
                "updated_at = now() WHERE user_id = %s AND id = %s RETURNING id",
                (user_id, channel_id),
            )
            if cur.fetchone() is None:
                raise WorkspaceNotFound("notification_channel_not_found")
            cur.execute(
                "UPDATE notification_outbox SET status = 'cancelled', "
                "last_error = 'channel_revoked' "
                "WHERE user_id = %s AND channel_id = %s AND status = 'queued'",
                (user_id, channel_id),
            )
        return {"revoked": True}

    def _enqueue(
        self, cur: Any, user_id: UUID, channel_id: UUID, message_key: str, kind: str,
        payload: dict[str, Any], due: datetime,
    ) -> None:
        tag = hashlib.sha256(f"{user_id}:{channel_id}:{message_key}".encode()).hexdigest()
        cur.execute(
            "INSERT INTO notification_outbox (user_id, channel_id, message_key, kind, "
            "payload_ciphertext, next_attempt_at) VALUES (%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (user_id, channel_id, message_key) DO NOTHING",
            (user_id, channel_id, message_key, kind, self._seal({**payload, "tag": tag}), due),
        )

    def queue_events(self, user_id: UUID, *, now: datetime | None = None) -> None:
        now = now or datetime.now(UTC)
        self.workspace.synchronize_events(user_id)
        with self.workspace._transaction(user_id) as cur:
            preferences = self.workspace._preferences(cur, user_id)["document"]
            cur.execute(
                "SELECT * FROM notification_channels WHERE user_id = %s AND status = 'active' "
                "ORDER BY id FOR UPDATE", (user_id,),
            )
            channels = cur.fetchall()
            for channel in channels:
                self._queue_channel(cur, user_id, channel, preferences, now)

    def _queue_channel(
        self, cur: Any, user_id: UUID, channel: Mapping[str, Any],
        preferences: Mapping[str, Any], now: datetime,
    ) -> None:
        cur.execute(
            "SELECT id, category, title, detail, target, source, revision, occurred_at "
            "FROM workspace_events WHERE user_id = %s AND revision > %s "
            "ORDER BY revision LIMIT 200", (user_id, channel["event_revision"]),
        )
        rows = cur.fetchall()
        frequency = preferences["digest_frequency"]
        if frequency == "off":
            for row in rows:
                if not preferences["notifications"][row["category"]]:
                    continue
                self._enqueue(cur, user_id, channel["id"], f"event:{row['id']}:{row['revision']}",
                              "event", {"title": "Новое событие OMNICIO",
                                        "body": "В кабинете появилось подтверждённое событие. "
                                                "Откройте OMNICIO, чтобы посмотреть подробности.",
                                        "url": "/#events?event=" + row["id"],
                                        "category": row["category"],
                                        "event_id": row["id"],
                                        "event_revision": row["revision"],
                                        "destination": _event_record(row)["destination"]},
                              delivery_time(preferences, now))
        if rows:
            cur.execute(
                "UPDATE notification_channels SET event_revision = %s "
                "WHERE user_id = %s AND id = %s",
                (rows[-1]["revision"], user_id, channel["id"]),
            )
        if frequency != "off":
            self._queue_digest(cur, user_id, channel, preferences, now)

    def _queue_digest(
        self, cur: Any, user_id: UUID, channel: Mapping[str, Any],
        preferences: Mapping[str, Any], now: datetime,
    ) -> None:
        local = now.astimezone(ZoneInfo(preferences["quiet_hours"]["timezone"]))
        end = local.replace(hour=0, minute=0, second=0, microsecond=0)
        frequency = preferences["digest_frequency"]
        if frequency == "weekly":
            end -= timedelta(days=end.weekday())
        start = end - timedelta(days=7 if frequency == "weekly" else 1)
        period = f"{frequency}:{end.isoformat()}"
        if channel["digest_period"] == period or channel["verified_at"] >= end:
            return
        enabled = [key for key, value in preferences["notifications"].items() if value]
        cur.execute(
            "SELECT count(*) AS total FROM workspace_events WHERE user_id = %s "
            "AND category = ANY (%s) AND occurred_at >= %s AND occurred_at < %s "
            "AND read_at IS NULL", (user_id, enabled, max(start, channel["verified_at"]), end),
        )
        count = int(cur.fetchone()["total"])
        if count:
            self._enqueue(cur, user_id, channel["id"], period, "digest", {
                "title": "Дайджест OMNICIO",
                "body": f"За завершённый период: {count} непрочитанных событий. "
                        "Подробности доступны после входа в кабинет.",
                "url": "/#events", "frequency": frequency,
                "from": max(start, channel["verified_at"]).isoformat(), "to": end.isoformat(),
            }, delivery_time(preferences, now))
        cur.execute(
            "UPDATE notification_channels SET digest_period = %s WHERE user_id = %s AND id = %s",
            (period, user_id, channel["id"]),
        )

    def _event_delivery_allowed(
        self, cur: Any, user_id: UUID, payload: dict[str, Any], preferences: Mapping[str, Any],
    ) -> bool:
        if (preferences["digest_frequency"] != "off"
                or not preferences["notifications"].get(payload.get("category"), False)):
            return False
        cur.execute(
            "SELECT revision, read_at FROM workspace_events WHERE user_id = %s AND id = %s",
            (user_id, payload.get("event_id")),
        )
        event = cur.fetchone()
        return (event is not None and event["read_at"] is None
                and event["revision"] == payload.get("event_revision"))

    def _digest_delivery_allowed(
        self, cur: Any, user_id: UUID, payload: dict[str, Any], preferences: Mapping[str, Any],
    ) -> bool:
        if preferences["digest_frequency"] != payload.get("frequency"):
            return False
        enabled = [key for key, value in preferences["notifications"].items() if value]
        cur.execute(
            "SELECT count(*) AS total FROM workspace_events WHERE user_id = %s "
            "AND category = ANY (%s) AND occurred_at >= %s AND occurred_at < %s "
            "AND read_at IS NULL", (user_id, enabled, payload["from"], payload["to"]),
        )
        count = int(cur.fetchone()["total"])
        payload["body"] = (f"За завершённый период: {count} непрочитанных событий. "
                           "Подробности доступны после входа в кабинет.")
        return count > 0

    def _delivery_allowed(
        self, cur: Any, user_id: UUID, row: Mapping[str, Any], payload: dict[str, Any],
        preferences: Mapping[str, Any], now: datetime,
    ) -> bool:
        if row["kind"] == "verification":
            return bool(row["channel_status"] == "pending"
                        and row["verification_expires_at"] > now
                        and row["verification_attempts"] < 5)
        if row["channel_status"] != "active":
            return False
        if row["kind"] == "event":
            return self._event_delivery_allowed(cur, user_id, payload, preferences)
        if row["kind"] == "digest":
            return self._digest_delivery_allowed(cur, user_id, payload, preferences)
        return (row["kind"] == "operational" and user_id == self.config.operator_user_id
                and bool(preferences["notifications"]["system"]))

    def _claim(self, user_id: UUID, now: datetime) -> dict[str, Any] | None:
        if not self.config.enabled or not self.database.has_legal_versions(
            user_id, self.legal_versions,
        ):
            return None
        with self.workspace._transaction(user_id) as cur:
            cur.execute(
                "UPDATE notification_outbox SET status = 'uncertain', "
                "last_error = 'worker_result_unknown' WHERE user_id = %s "
                "AND status = 'sending' AND lease_until < %s", (user_id, now),
            )
            cur.execute(
                "SELECT o.*, c.kind AS channel_kind, c.status AS channel_status, "
                "c.destination_ciphertext, c.verification_expires_at, c.verification_attempts "
                "FROM notification_outbox o JOIN notification_channels c "
                "ON c.id = o.channel_id AND c.user_id = o.user_id "
                "WHERE o.user_id = %s AND o.status = 'queued' AND o.next_attempt_at <= %s "
                "AND c.kind = ANY (%s) "
                "ORDER BY o.next_attempt_at, o.created_at LIMIT 1 FOR UPDATE OF o SKIP LOCKED",
                (user_id, now, [kind for kind, configured in (
                    ("push", self.push_configured), ("email", self.email_configured),
                ) if configured]),
            )
            found = cur.fetchone()
            if found is None:
                return None
            row = dict(found)
            payload = self._open(row["payload_ciphertext"])
            preferences = self.workspace._preferences(cur, user_id)["document"]
            expired = row["kind"] != "verification" and row["created_at"] < now - timedelta(days=7)
            allowed = self._delivery_allowed(cur, user_id, row, payload, preferences, now)
            if not allowed or expired:
                cur.execute(
                    "UPDATE notification_outbox SET status = 'cancelled', last_error = %s "
                    "WHERE user_id = %s AND id = %s",
                    ("delivery_expired" if expired else "delivery_preference_changed",
                     user_id, row["id"]),
                )
                return None
            due = now if row["kind"] == "verification" else delivery_time(preferences, now)
            if due > now:
                cur.execute(
                    "UPDATE notification_outbox SET next_attempt_at = %s "
                    "WHERE user_id = %s AND id = %s", (due, user_id, row["id"]),
                )
                return None
            lease = uuid4()
            cur.execute(
                "UPDATE notification_outbox SET status = 'sending', attempts = attempts + 1, "
                "lease_token = %s, lease_until = %s WHERE user_id = %s AND id = %s",
                (lease, now + timedelta(minutes=2), user_id, row["id"]),
            )
            row.update(payload=payload, destination=self._open(row["destination_ciphertext"]),
                       lease_token=lease, attempts=row["attempts"] + 1)
            return row

    def deliver_one(self, user_id: UUID, *, now: datetime | None = None) -> bool:
        now = now or datetime.now(UTC)
        row = self._claim(user_id, now)
        if row is None:
            return False
        if row["channel_kind"] == "push":
            result = self.transport.send_push(row["destination"], row["payload"])
        else:
            result = self.transport.send_email(row["destination"], row["payload"])
        state = result.status
        if state == "queued" and row["attempts"] >= 6:
            state = "failed"
        delay = max(result.retry_after, min(21600, 30 * 2 ** row["attempts"]))
        with self.workspace._transaction(user_id) as cur:
            cur.execute(
                "UPDATE notification_outbox SET status = %s, last_error = %s, "
                "next_attempt_at = %s, accepted_at = %s, lease_until = NULL "
                "WHERE user_id = %s AND id = %s AND status = 'sending' AND lease_token = %s",
                (state, result.code, now + timedelta(seconds=delay),
                 now if state == "accepted" else None, user_id, row["id"], row["lease_token"]),
            )
            if result.expired:
                cur.execute(
                    "UPDATE notification_channels SET status = 'expired', updated_at = %s "
                    "WHERE user_id = %s AND id = %s AND status = 'active'",
                    (now, user_id, row["channel_id"]),
                )
        return True

    def queue_operator_alert(self, user_id: UUID, key: str, title: str) -> None:
        """Called only by server-owned operational monitoring, to opted-in channels."""
        if user_id != self.config.operator_user_id:
            return
        if re.fullmatch(r"[a-z0-9_-]{1,100}", key) is None or not 1 <= len(title) <= 160:
            raise ValueError("notification_operational_alert_invalid")
        with self.workspace._transaction(user_id) as cur:
            prefs = self.workspace._preferences(cur, user_id)["document"]
            if not prefs["notifications"]["system"]:
                return
            cur.execute(
                "SELECT id FROM notification_channels WHERE user_id = %s AND status = 'active'",
                (user_id,),
            )
            for channel in cur.fetchall():
                self._enqueue(cur, user_id, channel["id"], "operational:" + key,
                              "operational", {"title": "Состояние OMNICIO", "body": title,
                                              "url": _SETTINGS_TARGET},
                              delivery_time(prefs, datetime.now(UTC)))
        self._wake.set()

    def _process_pending_user(self, user_id: UUID, now: datetime, needs_attention: bool) -> None:
        if not self.database.has_legal_versions(user_id, self.legal_versions):
            return
        self.queue_events(user_id)
        if user_id == self.config.operator_user_id and needs_attention:
            self.queue_operator_alert(
                user_id, "health-" + now.strftime("%Y%m%d%H"),
                "Мониторинг обнаружил задержку или ошибку обновления данных. "
                "Откройте состояние сервиса в настройках для проверки.",
            )
        for _ in range(5):
            if self._stop.is_set() or not self.deliver_one(user_id):
                break

    def run_pending(self) -> None:
        now = datetime.now(UTC)
        metrics = self.database.collect_operational_metrics()
        if now >= self._maintenance_at:
            self.database.prune_sessions()
            self._maintenance_at = now + timedelta(minutes=15)
        with self.database.pool.connection() as conn:
            rows = conn.execute(
                "SELECT id FROM users WHERE status = 'active' "
                "AND (%s::uuid IS NULL OR id > %s::uuid) ORDER BY id LIMIT 1000",
                (self._user_cursor, self._user_cursor),
            ).fetchall()
        self._user_cursor = (UUID(str(cast(dict[str, Any], rows[-1])["id"]))
                             if len(rows) == 1000 else None)
        for row in rows:
            if self._stop.is_set():
                return
            user_id = UUID(str(cast(dict[str, Any], row)["id"]))
            try:
                self._process_pending_user(user_id, now, metrics["status"] == "attention")
            except Exception as exc:
                # A single unavailable tenant must not starve every other owner's
                # queue. No destination, code, body, or identity is logged.
                _log_worker_failure("notification_owner_failed", exc)

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = Thread(target=self._loop, name="workspace-notifications", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.run_pending()
            except Exception as exc:
                _log_worker_failure("notification_worker_failed", exc)
            self._wake.wait(timeout=30)
            self._wake.clear()
