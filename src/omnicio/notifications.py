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
from contextlib import closing, suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from threading import Event, Lock, Thread
from typing import Any, cast
from urllib.parse import urlsplit
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from psycopg import Error as PostgresError
from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row

from .db import Database
from .payouts import visible_event_sql
from .security import SecurityValueError, decrypt_secret, encrypt_secret
from .workspace import quiet_now
from .workspace_store import WorkspaceNotFound, WorkspaceStore, _event_record, _json

logger = logging.getLogger(__name__)
_EMAIL = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@[A-Za-z0-9.-]{1,189}")
_PUSH_HOSTS = {"fcm.googleapis.com", "updates.push.services.mozilla.com", "web.push.apple.com"}
_PUSH_SUFFIXES = (".push.apple.com", ".notify.windows.com")
_MAILTO_SCHEME = "mailto:"
_HTTPS_SCHEME = "https://"
_SETTINGS_TARGET = "/#settings"
_EVENTS_TARGET = "/#events"
_VISIBLE_EVENTS_SQL = visible_event_sql()
_VISIBLE_MEMBERS_SQL = visible_event_sql("e")


def _notification_target(payload: Mapping[str, Any]) -> str:
    """Only server-owned cabinet routes can become a notification's navigation."""
    value = payload.get("url", _SETTINGS_TARGET)
    if isinstance(value, str) and (
        value in {_SETTINGS_TARGET, _EVENTS_TARGET}
        or re.fullmatch(r"/#events\?event=[0-9a-f]{64}", value) is not None
    ):
        return value
    return _SETTINGS_TARGET


def _log_worker_failure(code: str, error: Exception) -> None:
    # Preserve a useful failure class without provider messages, destinations,
    # credentials, chained exceptions or the original traceback in logs.
    sanitized = RuntimeError(type(error).__name__)
    logger.exception(code, exc_info=(RuntimeError, sanitized, None))


class NotificationUnavailable(RuntimeError):
    """The requested channel is not configured; no provider mutation occurred."""


class NotificationConflict(RuntimeError):
    """A device cannot be activated under the requested binding."""


class NotificationRateLimited(RuntimeError):
    """The owner already queued an explicit device test in the last minute."""


@dataclass(frozen=True, slots=True)
class NotificationConfig:
    crypto_key: str
    public_origin: str = "https://omnicio.ru"
    enabled: bool = False
    email_enabled: bool = False
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


_DELIVERY_ERRORS = {
    "push_dns_unavailable": ("Сервис push временно недоступен.", "wait"),
    "push_result_unknown": ("Сервис push не подтвердил результат отправки.", "check_device"),
    "push_subscription_expired": ("Подписка этого устройства истекла.", "reconnect"),
    "push_rate_limited": ("Сервис push попросил повторить отправку позже.", "wait"),
    "push_provider_rejected": ("Сервис push отклонил уведомление.", "reconnect"),
    "push_authorization_unavailable": (
        "Сервер временно не может подготовить авторизацию push.", "wait",
    ),
    "email_temporary_rejection": ("Почтовый сервер временно отложил отправку.", "wait"),
    "email_provider_rejected": ("Почтовый сервер отклонил письмо.", "contact_support"),
    "email_recipient_rejected": ("Почтовый сервер не принял адрес получателя.", "verify_email"),
    "email_result_unknown": ("Почтовый сервер не подтвердил результат отправки.", "check_inbox"),
    "verification_replaced": ("Этот код заменён новым кодом подтверждения.", "use_latest_code"),
    "channel_revoked": ("Канал уведомлений отключён пользователем.", "reconnect"),
    "push_binding_expired": ("Привязка устройства к сеансу завершена.", "reconnect"),
    "push_binding_changed": ("Привязка устройства обновлена.", "reconnect"),
    "email_disabled": ("Отправка по электронной почте отключена.", "open_events"),
    "legacy_digest_membership_unknown": (
        "Для прежнего дайджеста нет подтверждения состава отправленных событий.", "open_events",
    ),
    "delivery_preference_changed": (
        "Отправка отменена после изменения настроек или прочтения событий.", "open_events",
    ),
    "worker_result_unknown": (
        "Сервер не получил подтверждение результата отправки.", "open_events",
    ),
    "delivery_expired": (
        "Срок отправки уведомления истёк; события доступны в кабинете.", "open_events",
    ),
}


def delivery_error(code: str | None, status: str) -> dict[str, Any] | None:
    """Stable public diagnostics, never raw provider payloads or destinations."""
    if status == "accepted" or not code:
        return None
    public_code = code if code in _DELIVERY_ERRORS else "delivery_error_unknown"
    title, action = _DELIVERY_ERRORS.get(public_code, (
        "Причину отправки пока не удалось определить.", "contact_support",
    ))
    retryable = status == "queued" and public_code in {
        "push_dns_unavailable", "push_rate_limited", "push_authorization_unavailable",
        "email_temporary_rejection",
    }
    if status == "failed" and action == "wait":
        title += " Автоматические попытки завершены."
        action = "contact_support"
    return {"code": public_code, "title": title, "action_code": action, "retryable": retryable}


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
    auth = _decode(keys["auth"], 16)
    canonical = _HTTPS_SCHEME + host + parsed.path + ("?" + parsed.query if parsed.query else "")
    return {"endpoint": canonical, "keys": {"p256dh": _b64(public), "auth": _b64(auth)}}


def push_public_key(private_key: str) -> str:
    key = ec.derive_private_key(int.from_bytes(_decode(private_key, 32)), ec.SECP256R1())
    return _b64(key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint,
    ))


def validate_push_configuration(private_key: str, subject: str) -> None:
    """Check a configured VAPID key and subject without contacting a provider."""
    if not private_key:
        return
    push_public_key(private_key)
    if (any(ord(char) < 33 or ord(char) > 126 for char in subject)
            or not subject.startswith((_MAILTO_SCHEME, _HTTPS_SCHEME))):
        raise ValueError("notification_vapid_subject_invalid")
    if subject.startswith(_MAILTO_SCHEME):
        normalize_email(subject.removeprefix(_MAILTO_SCHEME))


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
        "exp": int(now.timestamp()) + 7200, "sub": config.vapid_subject,
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


def _push_retry_delay(value: str) -> int:
    """Bound provider delta-seconds without accepting Unicode digits or huge ints."""
    value = value.strip()
    if re.fullmatch(r"\d+", value, flags=re.ASCII) is None:
        return 60
    significant = value.lstrip("0") or "0"
    if len(significant) > 5:
        return 86400
    return min(86400, max(30, int(significant)))


class NotificationTransport:
    def __init__(self, config: NotificationConfig, *, database: Database | None = None) -> None:
        self.config = config
        self.database = database
        self._authorization_lock = Lock()
        self._authorizations: dict[str, tuple[datetime, str]] = {}

    def _authorization(self, endpoint: str, now: datetime) -> str | None:
        if self.database is not None:
            return self._shared_authorization(endpoint)
        # Isolated transport/RFC tests need no database. Application instances
        # always use the durable store shared by workers and process restarts.
        origin = _HTTPS_SCHEME + (urlsplit(endpoint).hostname or "")
        with self._authorization_lock:
            # Apple requires reusing a JWT for at least one hour. Keep a second
            # hour of validity so a just-reused token does not expire in transit.
            # A clock discontinuity must not keep stale or far-future claims.
            self._authorizations = {
                key: entry for key, entry in self._authorizations.items()
                if entry[0] <= now < entry[0] + timedelta(hours=1)
            }
            existing = self._authorizations.get(origin)
            if existing:
                return existing[1]
            if len(self._authorizations) >= 128:
                # Do not evict an unexpired origin and then regenerate its JWT
                # too frequently. Defer excess work through the existing queue.
                return None
            header = vapid_authorization(self.config, endpoint, now)
            self._authorizations[origin] = (now, header)
            return header

    def _shared_authorization(self, endpoint: str) -> str | None:
        if self.database is None:
            raise NotificationUnavailable("notification_authorization_store_unavailable")
        origin = _HTTPS_SCHEME + (urlsplit(endpoint).hostname or "")
        identity = hashlib.sha256(_json([
            push_public_key(self.config.vapid_private_key), self.config.vapid_subject,
        ]).encode()).hexdigest()
        with (self.database.pool.connection() as conn, conn.transaction(),
              conn.cursor(row_factory=dict_row) as cur):
            # A short operational lock also makes the global bound exact. No
            # provider request happens while it is held; no user data is stored.
            cur.execute("SELECT pg_advisory_xact_lock("
                        "hashtextextended('omnicio:notification-vapid', 0))")
            cur.execute("SELECT clock_timestamp() AS now")
            now = cast(dict[str, Any], cur.fetchone())["now"]
            cur.execute(
                "DELETE FROM notification_push_authorizations WHERE issued_at <= %s "
                "OR issued_at > %s OR expires_at <= %s", (now - timedelta(hours=1), now, now),
            )
            cur.execute(
                "SELECT authorization_ciphertext FROM notification_push_authorizations "
                "WHERE origin = %s AND identity_hash = %s", (origin, identity),
            )
            found = cur.fetchone()
            if found is not None:
                return decrypt_secret(bytes(found["authorization_ciphertext"]),
                                      self.config.crypto_key)
            cur.execute("SELECT count(*) AS total FROM notification_push_authorizations")
            if cast(dict[str, Any], cur.fetchone())["total"] >= 128:
                return None
            header = vapid_authorization(self.config, endpoint, now)
            expires = datetime.fromtimestamp(int(now.timestamp()) + 7200, UTC)
            cur.execute(
                "INSERT INTO notification_push_authorizations "
                "(origin, identity_hash, issued_at, expires_at, authorization_ciphertext) "
                "VALUES (%s, %s, %s, %s, %s)",
                (origin, identity, now, expires, encrypt_secret(header, self.config.crypto_key)),
            )
            return header

    def send_push(
        self, destination: Mapping[str, Any], payload: dict[str, Any], *, ttl_seconds: int = 86400,
    ) -> DeliveryResult:
        if type(ttl_seconds) is not int or not 0 <= ttl_seconds <= 86400:
            raise ValueError("notification_ttl_invalid")
        subscription = normalize_subscription(destination)
        endpoint = subscription["endpoint"]
        try:
            authorization = self._authorization(endpoint, datetime.now(UTC))
        except (PostgresError, SecurityValueError):
            # This failure precedes DNS, connection creation and every provider
            # request. Retrying is safe; it is not an ambiguous network receipt.
            return DeliveryResult("queued", "push_authorization_unavailable", 60)
        if authorization is None:
            return DeliveryResult("queued", "push_rate_limited", 300)
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
                                 "Authorization": authorization,
                                 "Content-Encoding": "aes128gcm",
                                 "TTL": str(ttl_seconds),
                                 "Content-Type": "application/octet-stream",
                                 "Topic": hashlib.sha256(payload["tag"].encode()).hexdigest()[:32],
                             })
                response = conn.getresponse()
                status = response.status
                raw_retry = (response.getheader("Retry-After", "")
                             if status in {429, 503} else "")
                response.read(4096)
        except (OSError, http.client.HTTPException):
            return DeliveryResult("uncertain", "push_result_unknown")
        if status in {200, 201, 202}:
            return DeliveryResult("accepted", "push_provider_accepted")
        if status in {404, 410}:
            return DeliveryResult("failed", "push_subscription_expired", expired=True)
        if status in {429, 503}:
            return DeliveryResult("queued", "push_rate_limited", _push_retry_delay(raw_retry))
        return DeliveryResult("failed", "push_provider_rejected")

    def send_email(self, destination: Mapping[str, Any], payload: dict[str, Any]) -> DeliveryResult:
        message = EmailMessage()
        message["From"] = self.config.smtp_sender
        message["To"] = normalize_email(destination["email"])
        message["Subject"] = payload["title"]
        message["Message-ID"] = f"<{payload['tag']}@{urlsplit(self.config.public_origin).hostname}>"
        message.set_content(payload["body"] + "\n\n" + self.config.public_origin
                            + _notification_target(payload))
        context = ssl.create_default_context()
        try:
            client = (smtplib.SMTP_SSL(self.config.smtp_host, self.config.smtp_port,
                                      timeout=10, context=context)
                      if self.config.smtp_mode == "tls" else smtplib.SMTP(
                          self.config.smtp_host, self.config.smtp_port, timeout=10,
                      ))
            # SMTP.__exit__ sends QUIT and can raise after DATA was already
            # accepted, or replace the original send failure. Neither cleanup
            # outcome may change the delivery receipt or trigger a duplicate.
            with closing(client):
                if self.config.smtp_mode == "starttls":
                    client.ehlo()
                    client.starttls(context=context)
                    client.ehlo()
                if self.config.smtp_username:
                    client.login(self.config.smtp_username, self.config.smtp_password)
                client.send_message(message)
                # DATA succeeded; closing the connection is sufficient if QUIT fails.
                with suppress(OSError, smtplib.SMTPException):
                    client.quit()
        except smtplib.SMTPResponseException as exc:
            if 400 <= exc.smtp_code < 500:
                return DeliveryResult("queued", "email_temporary_rejection", 300)
            return DeliveryResult("failed", "email_provider_rejected")
        except smtplib.SMTPRecipientsRefused as exc:
            if exc.recipients and all(400 <= error[0] < 500
                                      for error in exc.recipients.values()):
                return DeliveryResult("queued", "email_temporary_rejection", 300)
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
        self.transport = transport or NotificationTransport(config, database=database)
        self._stop = Event()
        self._wake = Event()
        self._thread: Thread | None = None
        self._maintenance_at = datetime.min.replace(tzinfo=UTC)
        self._user_cursor: UUID | None = None
        if config.public_origin != "https://omnicio.ru":
            raise ValueError("notification_origin_invalid")
        if config.email_enabled and (
            config.smtp_mode not in {"tls", "starttls"} or not 1 <= config.smtp_port <= 65535
        ):
            raise ValueError("notification_smtp_invalid")
        if config.email_enabled and config.smtp_sender:
            normalize_email(config.smtp_sender)
        validate_push_configuration(config.vapid_private_key, config.vapid_subject)

    @property
    def push_configured(self) -> bool:
        return bool(self.config.enabled and self.config.vapid_private_key
                    and self.config.vapid_subject)

    @property
    def email_configured(self) -> bool:
        return bool(self.config.enabled and self.config.email_enabled
                    and self.config.smtp_host and self.config.smtp_sender)

    def _seal(self, value: object) -> bytes:
        return encrypt_secret(_json(value), self.config.crypto_key)

    def _open(self, value: bytes) -> dict[str, Any]:
        parsed = json.loads(decrypt_secret(bytes(value), self.config.crypto_key))
        if not isinstance(parsed, dict):
            raise ValueError("notification_stored_payload_invalid")
        return parsed

    def _hash(self, value: str) -> str:
        return hmac.new(self.config.crypto_key.encode(), value.encode(), hashlib.sha256).hexdigest()

    @staticmethod
    def _session(cur: Any, user_id: UUID, digest: bytes) -> UUID:
        cur.execute(
            "SELECT id FROM sessions WHERE user_id = %s AND token_digest = %s "
            "AND revoked_at IS NULL AND expires_at > clock_timestamp() FOR SHARE",
            (user_id, digest),
        )
        row = cur.fetchone()
        if row is None:
            raise PermissionError("session_expired")
        return UUID(str(row["id"]))

    def _maintain_channels(self, cur: Any, user_id: UUID, now: datetime) -> None:
        """Enforce authority before status, queueing or claiming, retaining receipts."""
        cur.execute(
            "UPDATE notification_channels SET status = 'expired', verification_digest = NULL, "
            "updated_at = %s WHERE user_id = %s AND kind = 'email' "
            "AND status IN ('active', 'pending') AND NOT %s",
            (now, user_id, self.config.email_enabled),
        )
        cur.execute(
            "UPDATE notification_channels c SET status = 'expired', updated_at = %s "
            "WHERE c.user_id = %s AND c.kind = 'push' AND c.status = 'active' "
            "AND (c.binding_id IS NULL OR NOT EXISTS (SELECT 1 FROM sessions s "
            "WHERE s.user_id = c.user_id AND s.id = c.session_id "
            "AND s.revoked_at IS NULL AND s.expires_at > %s))", (now, user_id, now),
        )
        cur.execute(
            "UPDATE notification_outbox o SET status = 'cancelled', "
            "last_error = CASE WHEN c.kind = 'email' THEN 'email_disabled' "
            "ELSE 'push_binding_expired' END, updated_at = %s "
            "FROM notification_channels c WHERE o.user_id = %s "
            "AND c.user_id = o.user_id AND c.id = o.channel_id AND o.status = 'queued' "
            "AND ((c.kind = 'email' AND NOT %s) OR (c.kind = 'push' AND "
            "(c.status <> 'active' OR o.binding_id IS DISTINCT FROM c.binding_id)))",
            (now, user_id, self.config.email_enabled),
        )

    def _configured_kinds(self) -> list[str]:
        return [kind for kind, configured in (
            ("push", self.push_configured), ("email", self.email_configured),
        ) if configured]

    def status(self, user_id: UUID, *, session_digest: bytes | None = None) -> dict[str, Any]:
        with self.workspace._transaction(user_id) as cur:
            session_id = self._session(cur, user_id, session_digest) if session_digest else None
            self._maintain_channels(cur, user_id, datetime.now(UTC))
            cur.execute(
                "UPDATE notification_channels SET status = 'expired', "
                "verification_digest = NULL WHERE user_id = %s AND status = 'pending' "
                "AND (verification_expires_at <= now() OR verification_attempts >= 5)", (user_id,),
            )
            cur.execute(
                "SELECT id, kind, label, status, verified_at, created_at, "
                "verification_expires_at, verification_attempts, destination_ciphertext, "
                "session_id, binding_id "
                "FROM notification_channels WHERE user_id = %s "
                "AND (kind = 'push' OR status <> 'revoked') "
                "ORDER BY (status IN ('active', 'pending')) DESC, updated_at DESC, id DESC "
                "LIMIT 32", (user_id,),
            )
            channels = [dict(row) for row in cur.fetchall()]
            for channel in channels:
                channel_session = channel.pop("session_id")
                channel["current_session"] = bool(
                    session_id and channel_session == session_id,
                )
                destination = self._open(channel.pop("destination_ciphertext"))
                channel["endpoint_fingerprint"] = (hashlib.sha256(
                    destination["endpoint"].encode(),
                ).hexdigest() if channel["kind"] == "push" else None)
                channel["verification_attempts_remaining"] = max(
                    0, 5 - channel.pop("verification_attempts"),
                )
            cur.execute(
                "SELECT o.id, o.channel_id, o.kind, o.status, o.attempts, o.last_error, "
                "o.created_at, o.accepted_at, o.next_attempt_at, c.kind AS channel_kind, "
                "c.label AS channel_label, c.status AS channel_status "
                "FROM notification_outbox o JOIN notification_channels c "
                "ON c.user_id = o.user_id AND c.id = o.channel_id WHERE o.user_id = %s "
                "ORDER BY o.created_at DESC, o.id DESC LIMIT 30", (user_id,),
            )
            deliveries = [dict(row) for row in cur.fetchall()]
            for delivery in deliveries:
                delivery["channel"] = {
                    "id": delivery["channel_id"], "kind": delivery.pop("channel_kind"),
                    "label": delivery.pop("channel_label"),
                    "status": delivery.pop("channel_status"),
                }
                delivery["error"] = delivery_error(delivery["last_error"], delivery["status"])
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
            "verification_expires_at, last_verification_at, event_revision, verified_at, "
            "digest_cursor_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
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
            "digest_cursor_at = CASE WHEN notification_channels.status = 'active' "
            "AND EXCLUDED.status = 'active' THEN notification_channels.digest_cursor_at "
            "ELSE EXCLUDED.digest_cursor_at END, "
            "digest_period = CASE WHEN notification_channels.status = 'active' "
            "AND EXCLUDED.status = 'active' THEN notification_channels.digest_period "
            "ELSE NULL END, "
            "updated_at = now() RETURNING id",
            (ident, user_id, kind, identity_hash, self._seal(destination), label, status,
             None,
             now + timedelta(minutes=15) if code else None, now if code else None,
             revision, now if status == "active" else None, now if status == "active" else None),
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
        *, session_digest: bytes, intent: str = "enable",
    ) -> dict[str, Any]:
        if not self.push_configured:
            raise NotificationUnavailable("notification_push_not_configured")
        normalized = normalize_subscription(subscription)
        if intent not in {"enable", "sync"}:
            raise ValueError("notification_intent_invalid")
        if (not isinstance(label, str) or not 1 <= len(label.strip()) <= 100
                or any(ord(char) < 32 for char in label)):
            raise ValueError("notification_label_invalid")
        try:
            with self.workspace._transaction(user_id) as cur:
                session_id = self._session(cur, user_id, session_digest)
                now = datetime.now(UTC)
                self._maintain_channels(cur, user_id, now)
                result = self._bind_push(cur, user_id, normalized, label.strip(),
                                         session_id, intent, now)
        except UniqueViolation as exc:
            if exc.diag.constraint_name != "notification_push_active_destination_key":
                raise
            raise NotificationConflict("notification_device_conflict") from None
        self._wake.set()
        return result

    def _bind_push(
        self, cur: Any, user_id: UUID, subscription: dict[str, Any], label: str,
        session_id: UUID, intent: str, now: datetime,
    ) -> dict[str, Any]:
        cur.execute(
            "SELECT id, status, session_id, binding_id, destination_ciphertext "
            "FROM notification_channels WHERE user_id = %s AND kind = 'push' "
            "AND destination_hash = %s FOR UPDATE",
            (user_id, self._hash(subscription["endpoint"])),
        )
        previous = cur.fetchone()
        if previous and previous["status"] == "revoked" and intent == "sync":
            return {"id": str(previous["id"]), "status": "revoked",
                    "binding_id": str(previous["binding_id"]) if previous["binding_id"] else None,
                    "current_session": previous["session_id"] == session_id}
        unchanged = bool(previous and previous["status"] == "active"
                         and previous["session_id"] == session_id and previous["binding_id"]
                         and self._open(previous["destination_ciphertext"]) == subscription)
        binding = previous["binding_id"] if unchanged else uuid4()
        ident = self._insert_channel(cur, user_id, kind="push", destination=subscription,
                                     label=label, status="active", now=now)
        cur.execute(
            "UPDATE notification_channels SET session_id = %s, binding_id = %s "
            "WHERE user_id = %s AND id = %s", (session_id, binding, user_id, ident),
        )
        if not unchanged:
            cur.execute(
                "UPDATE notification_outbox SET status = 'cancelled', "
                "last_error = 'push_binding_changed', updated_at = clock_timestamp() "
                "WHERE user_id = %s AND channel_id = %s AND status = 'queued'",
                (user_id, ident),
            )
        return {"id": str(ident), "status": "active", "binding_id": str(binding),
                "current_session": True}

    def test_push(
        self, user_id: UUID, channel_id: UUID, *, session_digest: bytes,
    ) -> dict[str, Any]:
        if not self.push_configured:
            raise NotificationUnavailable("notification_push_not_configured")
        now = datetime.now(UTC)
        with self.workspace._transaction(user_id) as cur:
            session_id = self._session(cur, user_id, session_digest)
            self._maintain_channels(cur, user_id, now)
            cur.execute(
                "SELECT status FROM notification_channels WHERE user_id = %s AND id = %s "
                "AND kind = 'push' AND session_id = %s", (user_id, channel_id, session_id),
            )
            channel = cur.fetchone()
            if channel is None:
                raise WorkspaceNotFound("notification_channel_not_found")
            if channel["status"] != "active":
                raise NotificationConflict("notification_channel_inactive")
            cur.execute(
                "SELECT 1 FROM notification_outbox WHERE user_id = %s AND kind = 'test' "
                "AND created_at > %s LIMIT 1", (user_id, now - timedelta(minutes=1)),
            )
            if cur.fetchone() is not None:
                raise NotificationRateLimited("notification_test_rate_limited")
            key = "test:" + str(uuid4())
            self._enqueue(cur, user_id, channel_id, key, "test", {
                "title": "Проверка уведомлений OMNICIO",
                "body": "Уведомления на этом устройстве подключены.",
                "url": _SETTINGS_TARGET,
            }, now)
            cur.execute(
                "SELECT id FROM notification_outbox WHERE user_id = %s AND channel_id = %s "
                "AND message_key = %s", (user_id, channel_id, key),
            )
            ident = cur.fetchone()["id"]
        self._wake.set()
        return {"id": str(ident), "status": "queued"}

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
                "last_error = 'verification_replaced', updated_at = clock_timestamp() "
                "WHERE user_id = %s AND channel_id = %s "
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
        if not self.email_configured:
            raise NotificationUnavailable("notification_email_not_configured")
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
                    "digest_cursor_at = CASE WHEN %s THEN %s ELSE digest_cursor_at END, "
                    "verification_digest = CASE WHEN %s THEN NULL ELSE verification_digest END, "
                    "updated_at = %s WHERE user_id = %s AND id = %s",
                    ("active" if accepted else "pending", now if accepted else None,
                     accepted, now, accepted, now, user_id, channel_id),
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
                "last_error = 'channel_revoked', updated_at = clock_timestamp() "
                "WHERE user_id = %s AND channel_id = %s AND status = 'queued'",
                (user_id, channel_id),
            )
        return {"revoked": True}

    def _enqueue(
        self, cur: Any, user_id: UUID, channel_id: UUID, message_key: str, kind: str,
        payload: dict[str, Any], due: datetime, *, members: list[dict[str, Any]] | None = None,
    ) -> None:
        tag = hashlib.sha256(f"{user_id}:{channel_id}:{message_key}".encode()).hexdigest()
        content = {**payload, "tag": tag}
        cur.execute(
            "SELECT binding_id FROM notification_channels WHERE user_id = %s AND id = %s",
            (user_id, channel_id),
        )
        binding_id = cur.fetchone()["binding_id"]
        if members is not None:
            content["membership_version"] = 1
        sealed = self._seal(content)
        cur.execute(
            "INSERT INTO notification_outbox (user_id, channel_id, message_key, kind, "
            "payload_ciphertext, next_attempt_at, binding_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (user_id, channel_id, message_key) DO NOTHING RETURNING id",
            (user_id, channel_id, message_key, kind, sealed, due, binding_id),
        )
        stored = cur.fetchone()
        if members is None:
            return
        if stored is None:
            # A mode change can return to the same event or digest. Only an
            # unsubmitted message cancelled for that change may be reactivated.
            cur.execute(
                "UPDATE notification_outbox SET status = 'queued', payload_ciphertext = %s, "
                "next_attempt_at = %s, created_at = clock_timestamp(), "
                "updated_at = clock_timestamp(), last_error = NULL, binding_id = %s "
                "WHERE user_id = %s AND channel_id = %s AND message_key = %s "
                "AND status = 'cancelled' AND last_error = 'delivery_preference_changed' "
                "AND attempts < 6 RETURNING id",
                (sealed, due, binding_id, user_id, channel_id, message_key),
            )
            stored = cur.fetchone()
        if stored is not None:
            self._bind_members(cur, user_id, channel_id, stored["id"], members)

    @staticmethod
    def _bind_members(
        cur: Any, user_id: UUID, channel_id: UUID, outbox_id: UUID,
        members: list[dict[str, Any]],
    ) -> None:
        if members:
            cur.executemany(
                "INSERT INTO notification_outbox_events "
                "(user_id, channel_id, event_id, event_revision, outbox_id) "
                "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                [(user_id, channel_id, event["id"], event["revision"], outbox_id)
                 for event in members],
            )

    @staticmethod
    def _unassigned_events(
        cur: Any, user_id: UUID, channel_id: UUID, payload: Mapping[str, Any],
        preferences: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        enabled = [key for key, value in preferences["notifications"].items() if value]
        event_id = payload.get("event_id")
        available = payload.get("period_basis") == "available_at"
        cur.execute(
            "SELECT e.id, e.category, e.target, e.source, e.revision, e.occurred_at, e.updated_at "
            "FROM workspace_events e WHERE e.user_id = %s AND e.category = ANY (%s) "
            f"AND {_VISIBLE_MEMBERS_SQL} "
            "AND e.read_at IS NULL AND ((%s::text IS NOT NULL AND e.id = %s "
            "AND e.revision = %s) OR (%s::text IS NULL "
            "AND CASE WHEN %s THEN e.updated_at ELSE e.occurred_at END >= %s::timestamptz "
            "AND CASE WHEN %s THEN e.updated_at ELSE e.occurred_at END < %s::timestamptz)) "
            "AND NOT EXISTS (SELECT 1 FROM notification_outbox_events m "
            "WHERE m.user_id = e.user_id AND m.channel_id = %s "
            "AND m.event_id = e.id AND m.event_revision = e.revision) "
            "AND NOT EXISTS (SELECT 1 FROM notification_outbox o WHERE o.user_id = e.user_id "
            "AND o.channel_id = %s AND o.kind = 'event' "
            "AND o.status IN ('accepted', 'sending', 'uncertain') "
            "AND o.message_key = 'event:' || e.id || ':' || e.revision::text) "
            "ORDER BY e.revision",
            (user_id, enabled, event_id, event_id, payload.get("event_revision"), event_id,
             available, payload.get("from"), available, payload.get("to"),
             channel_id, channel_id),
        )
        return [dict(row) for row in cur.fetchall()]

    @staticmethod
    def _message_members(
        cur: Any, user_id: UUID, outbox_ids: list[UUID], preferences: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        enabled = [key for key, value in preferences["notifications"].items() if value]
        cur.execute(
            "SELECT e.id, e.category, e.target, e.source, e.revision, e.occurred_at, "
            "e.updated_at, m.outbox_id FROM notification_outbox_events m "
            "JOIN workspace_events e ON e.user_id = m.user_id AND e.id = m.event_id "
            "AND e.revision = m.event_revision WHERE m.user_id = %s "
            "AND m.outbox_id = ANY (%s::uuid[]) AND e.read_at IS NULL "
            f"AND {_VISIBLE_MEMBERS_SQL} "
            "AND e.category = ANY (%s) ORDER BY e.revision", (user_id, outbox_ids, enabled),
        )
        return [dict(row) for row in cur.fetchall()]

    def _legacy_membership_ambiguous(
        self, cur: Any, user_id: UUID, channel_id: UUID, members: list[dict[str, Any]],
    ) -> bool:
        if not members:
            return False
        cur.execute(
            "SELECT payload_ciphertext, status, accepted_at FROM notification_outbox "
            "WHERE user_id = %s AND channel_id = %s AND kind = 'digest' "
            "AND status IN ('accepted', 'sending', 'uncertain')", (user_id, channel_id),
        )
        for row in cur.fetchall():
            receipt = self._open(row["payload_ciphertext"])
            if receipt.get("membership_version") == 1:
                continue
            start, end = (datetime.fromisoformat(receipt[key]) for key in ("from", "to"))
            for event in members:
                at = event["updated_at" if receipt.get("period_basis") == "available_at"
                           else "occurred_at"]
                if start <= at < end and (row["accepted_at"] is None
                                         or event["updated_at"] <= row["accepted_at"]):
                    return True
        return False

    def _adopt_queued_message(
        self, cur: Any, user_id: UUID, channel_id: UUID, row: dict[str, Any],
        preferences: Mapping[str, Any],
    ) -> None:
        payload = self._open(row["payload_ciphertext"])
        row["payload"] = payload
        if payload.get("membership_version") == 1:
            return
        members = self._unassigned_events(cur, user_id, channel_id, payload, preferences)
        # An old accepted aggregate has no exact membership proof. Do not label
        # history delivered, and do not replay a potentially accepted revision.
        ambiguous = self._legacy_membership_ambiguous(cur, user_id, channel_id, members)
        self._bind_members(cur, user_id, channel_id, row["id"], members)
        payload["membership_version"] = 1
        row["status"] = "uncertain" if ambiguous else "queued"
        cur.execute(
            "UPDATE notification_outbox SET payload_ciphertext = %s, status = %s, "
            "last_error = CASE WHEN %s THEN 'legacy_digest_membership_unknown' "
            "ELSE last_error END, updated_at = clock_timestamp() "
            "WHERE user_id = %s AND id = %s AND status = 'queued'",
            (self._seal(payload), row["status"], ambiguous, user_id, row["id"]),
        )

    @staticmethod
    def _digest_calendar_time(preferences: Mapping[str, Any], day: datetime) -> datetime:
        zone = ZoneInfo(preferences.get("digest_timezone")
                        or preferences["quiet_hours"]["timezone"])
        hour, minute = (int(part) for part in preferences.get("digest_time", "00:00").split(":"))
        local = day.astimezone(zone).replace(hour=hour, minute=minute, second=0, microsecond=0)
        # A repeated local minute is delivered once, after its second occurrence.
        # A skipped minute is postponed to the first existing local minute. Store
        # the actual instant so a DST retry cannot create another digest period.
        for _ in range(24 * 60 + 1):
            candidate = local.replace(fold=1)
            returned = candidate.astimezone(UTC).astimezone(zone)
            if returned.replace(tzinfo=None) == candidate.replace(tzinfo=None):
                return returned
            local += timedelta(minutes=1)
        raise ValueError("notification_digest_time_invalid")

    @classmethod
    def _digest_boundary(cls, preferences: Mapping[str, Any], now: datetime) -> datetime:
        local = now.astimezone(ZoneInfo(preferences.get("digest_timezone")
                                      or preferences["quiet_hours"]["timezone"]))
        if preferences["digest_frequency"] == "weekly":
            local -= timedelta(days=local.weekday())
        end = cls._digest_calendar_time(preferences, local)
        if end.astimezone(UTC) > now.astimezone(UTC):
            end = cls._digest_calendar_time(preferences, local - timedelta(
                days=7 if preferences["digest_frequency"] == "weekly" else 1,
            ))
        return end

    @classmethod
    def _next_digest_boundary(
        cls, preferences: Mapping[str, Any], boundary: datetime,
    ) -> datetime:
        return cls._digest_calendar_time(preferences, boundary + timedelta(
            days=7 if preferences["digest_frequency"] == "weekly" else 1,
        ))

    def _queue_event(
        self, cur: Any, user_id: UUID, channel_id: UUID, event: dict[str, Any],
        preferences: Mapping[str, Any], now: datetime,
    ) -> None:
        cur.execute(
            "SELECT 1 FROM notification_outbox_events WHERE user_id = %s AND channel_id = %s "
            "AND event_id = %s AND event_revision = %s",
            (user_id, channel_id, event["id"], event["revision"]),
        )
        if cur.fetchone() is not None:
            return
        self._enqueue(cur, user_id, channel_id, f"event:{event['id']}:{event['revision']}",
                      "event", {"title": "Новое событие OMNICIO",
                                "body": "В кабинете появилось подтверждённое событие. "
                                        "Откройте OMNICIO, чтобы посмотреть подробности.",
                                "url": "/#events?event=" + event["id"],
                                "category": event["category"], "event_id": event["id"],
                                "event_revision": event["revision"],
                                "destination": _event_record(event)["destination"]},
                      delivery_time(preferences, now), members=[event])

    def _handoff_messages(
        self, cur: Any, user_id: UUID, channel_id: UUID, rows: list[dict[str, Any]],
        preferences: Mapping[str, Any], now: datetime,
    ) -> None:
        identifiers = [row["id"] for row in rows]
        members = self._message_members(cur, user_id, identifiers, preferences)
        if members:
            cur.executemany(
                "DELETE FROM notification_outbox_events WHERE user_id = %s AND outbox_id = %s "
                "AND event_id = %s AND event_revision = %s",
                [(user_id, row["outbox_id"], row["id"], row["revision"]) for row in members],
            )
        cur.execute(
            "UPDATE notification_outbox SET status = 'cancelled', "
            "last_error = 'delivery_preference_changed', updated_at = clock_timestamp() "
            "WHERE user_id = %s AND id = ANY (%s::uuid[]) AND status = 'queued'",
            (user_id, identifiers),
        )
        if preferences["digest_frequency"] == "off":
            for event in members:
                self._queue_event(cur, user_id, channel_id, event, preferences, now)
        elif members:
            end = self._digest_boundary(preferences, now)
            frequency = preferences["digest_frequency"]
            if any(event["updated_at"] >= end for event in members):
                end = self._next_digest_boundary(preferences, end)
            key = hashlib.sha256((frequency + ":" + ":".join(
                sorted(str(ident) for ident in identifiers),
            )).encode()).hexdigest()
            self._enqueue(cur, user_id, channel_id, "transfer:" + key, "digest", {
                "title": "Дайджест OMNICIO", "url": _EVENTS_TARGET, "frequency": frequency,
                "from": min(event["updated_at"] for event in members).isoformat(),
                "to": end.isoformat(), "period_basis": "available_at",
                "channel_id": str(channel_id), "body": self._digest_body(len(members)),
            }, delivery_time(preferences, max(now, end)), members=members)

    def _prepare_channel_messages(
        self, cur: Any, user_id: UUID, channel_id: UUID, preferences: Mapping[str, Any],
        now: datetime,
    ) -> None:
        cur.execute(
            "SELECT id, kind, status, payload_ciphertext, attempts, next_attempt_at "
            "FROM notification_outbox "
            "WHERE user_id = %s AND channel_id = %s AND status = 'queued' "
            "AND kind IN ('event', 'digest') ORDER BY created_at, id FOR UPDATE",
            (user_id, channel_id),
        )
        rows = [dict(row) for row in cur.fetchall()]
        for row in rows:
            self._adopt_queued_message(cur, user_id, channel_id, row, preferences)
        frequency = preferences["digest_frequency"]
        changed = [row for row in rows if row["status"] == "queued" and (
            (row["kind"] == "event" and frequency != "off")
            or (row["kind"] == "digest" and row["payload"].get("frequency") != frequency)
        )]
        if changed:
            self._handoff_messages(cur, user_id, channel_id, changed, preferences, now)
        changed_ids = {row["id"] for row in changed}
        for row in rows:
            if row["id"] in changed_ids or row["status"] != "queued" or row["attempts"]:
                continue
            self._reschedule_unsubmitted(cur, user_id, row, preferences, now)

    def _reschedule_unsubmitted(
        self, cur: Any, user_id: UUID, row: dict[str, Any], preferences: Mapping[str, Any],
        now: datetime,
    ) -> None:
        earliest = now
        boundary_changed = False
        if row["kind"] == "digest":
            end = datetime.fromisoformat(row["payload"]["to"])
            if end > now:
                # Membership is fixed, but a not-yet-due calendar boundary must
                # follow the user's current timezone without starting a new
                # period on every retry. Already submitted payloads stay fixed.
                members = self._message_members(cur, user_id, [row["id"]], preferences)
                previous_end = end
                end = self._digest_boundary(preferences, now)
                if any(event["updated_at"] >= end for event in members):
                    end = self._next_digest_boundary(preferences, end)
                row["payload"]["to"] = end.isoformat()
                boundary_changed = end != previous_end
            earliest = max(now, end)
        due = delivery_time(preferences, earliest)
        if due != row["next_attempt_at"] or boundary_changed:
            # Changing quiet hours can release unsubmitted work immediately.
            # A provider's retry backoff is preserved once attempts > 0.
            cur.execute(
                "UPDATE notification_outbox SET next_attempt_at = %s, payload_ciphertext = %s, "
                "updated_at = clock_timestamp() WHERE user_id = %s AND id = %s "
                "AND status = 'queued' AND attempts = 0",
                (due, self._seal(row["payload"]), user_id, row["id"]),
            )

    def queue_events(self, user_id: UUID, *, now: datetime | None = None) -> None:
        now = now or datetime.now(UTC)
        self.workspace.synchronize_events(user_id)
        with self.workspace._transaction(user_id) as cur:
            self._maintain_channels(cur, user_id, now)
            preferences = self.workspace._preferences(cur, user_id)["document"]
            cur.execute(
                "SELECT * FROM notification_channels WHERE user_id = %s AND status = 'active' "
                "AND kind = ANY (%s) ORDER BY id FOR UPDATE", (user_id, self._configured_kinds()),
            )
            channels = cur.fetchall()
            for channel in channels:
                self._queue_channel(cur, user_id, channel, preferences, now)

    def _queue_channel(
        self, cur: Any, user_id: UUID, channel: Mapping[str, Any],
        preferences: Mapping[str, Any], now: datetime,
    ) -> None:
        self._prepare_channel_messages(cur, user_id, channel["id"], preferences, now)
        cur.execute(
            "SELECT id, category, title, detail, target, source, revision, occurred_at, updated_at "
            "FROM workspace_events WHERE user_id = %s AND revision > %s "
            f"AND {_VISIBLE_EVENTS_SQL} "
            "ORDER BY revision LIMIT 200", (user_id, channel["event_revision"]),
        )
        rows = cur.fetchall()
        frequency = preferences["digest_frequency"]
        if frequency == "off":
            for row in rows:
                if not preferences["notifications"][row["category"]]:
                    continue
                self._queue_event(cur, user_id, channel["id"], dict(row), preferences, now)
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
        end = self._digest_boundary(preferences, now)
        frequency = preferences["digest_frequency"]
        period = f"{frequency}:{end.isoformat()}"
        start = channel["digest_cursor_at"]
        if start is None:
            # Accepted channels have a persisted legacy calendar boundary. New
            # channels start exactly at their own verification, never at a
            # hard-coded previous day that loses several days after downtime.
            previous = channel["digest_period"]
            start = (datetime.fromisoformat(previous.split(":", 1)[1])
                     if previous else channel["verified_at"])
        start = max(start, channel["verified_at"])
        if start >= end:
            return
        payload = {
            "title": "Дайджест OMNICIO", "url": _EVENTS_TARGET, "frequency": frequency,
            "from": start.isoformat(), "to": end.isoformat(),
            "period_basis": "available_at", "channel_id": str(channel["id"]),
        }
        members = self._unassigned_events(cur, user_id, channel["id"], payload, preferences)
        if members:
            self._enqueue(cur, user_id, channel["id"], period, "digest",
                          {**payload, "body": self._digest_body(len(members))},
                          delivery_time(preferences, now), members=members)
        cur.execute(
            "UPDATE notification_channels SET digest_period = %s, digest_cursor_at = %s "
            "WHERE user_id = %s AND id = %s", (period, end, user_id, channel["id"]),
        )

    @staticmethod
    def _digest_body(count: int) -> str:
        return (f"Новых или уточнённых непрочитанных событий: {count}. "
                "Включены сведения, поступившие с задержкой. "
                "Исходные даты и подробности доступны после входа в кабинет.")

    def _event_delivery_allowed(
        self, cur: Any, user_id: UUID, payload: dict[str, Any], preferences: Mapping[str, Any],
        outbox_id: UUID,
    ) -> bool:
        if (preferences["digest_frequency"] != "off"
                or not preferences["notifications"].get(payload.get("category"), False)):
            return False
        return any(event["id"] == payload.get("event_id")
                   and event["revision"] == payload.get("event_revision")
                   for event in self._message_members(cur, user_id, [outbox_id], preferences))

    def _digest_delivery_allowed(
        self, cur: Any, user_id: UUID, payload: dict[str, Any], preferences: Mapping[str, Any],
        outbox_id: UUID,
    ) -> bool:
        if preferences["digest_frequency"] != payload.get("frequency"):
            return False
        count = len(self._message_members(cur, user_id, [outbox_id], preferences))
        payload["body"] = self._digest_body(count)
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
        if row["channel_kind"] == "push" and (
            not row["binding_id"] or row["binding_id"] != row["channel_binding_id"]
        ):
            return False
        if row["kind"] == "test":
            return bool(row["channel_kind"] == "push")
        if row["kind"] == "event":
            return self._event_delivery_allowed(cur, user_id, payload, preferences, row["id"])
        if row["kind"] == "digest":
            return self._digest_delivery_allowed(cur, user_id, payload, preferences, row["id"])
        return (row["kind"] == "operational" and user_id == self.config.operator_user_id
                and bool(preferences["notifications"]["system"]))

    @staticmethod
    def _delivery_expired(
        row: Mapping[str, Any], payload: Mapping[str, Any], now: datetime,
    ) -> bool:
        if row["kind"] == "verification":
            return False
        eligible_at = cast(datetime, row["created_at"])
        if row["kind"] == "test":
            return eligible_at + timedelta(minutes=5) <= now
        if row["kind"] == "digest":
            # A frequency handoff can queue a full weekly period in advance.
            # Give that period its delivery window after it closes, including
            # quiet hours and DST. Retry backoff never moves this fixed boundary;
            # only an unsubmitted calendar may follow a timezone preference change.
            eligible_at = max(eligible_at, datetime.fromisoformat(payload["to"]))
        return eligible_at + timedelta(days=7) < now

    def _claim(self, user_id: UUID, now: datetime) -> dict[str, Any] | None:
        if not self.config.enabled or not self.database.has_legal_versions(
            user_id, self.legal_versions,
        ):
            return None
        with self.workspace._transaction(user_id) as cur:
            self._maintain_channels(cur, user_id, now)
            preferences = self.workspace._preferences(cur, user_id)["document"]
            cur.execute(
                "SELECT id FROM notification_channels WHERE user_id = %s AND status = 'active' "
                "AND kind = ANY (%s)", (user_id, self._configured_kinds()),
            )
            for channel in cur.fetchall():
                self._prepare_channel_messages(cur, user_id, channel["id"], preferences, now)
            cur.execute(
                "UPDATE notification_outbox SET status = 'uncertain', "
                "last_error = 'worker_result_unknown', updated_at = clock_timestamp() "
                "WHERE user_id = %s "
                "AND status = 'sending' AND lease_until < %s", (user_id, now),
            )
            cur.execute(
                "SELECT o.*, c.kind AS channel_kind, c.status AS channel_status, "
                "c.destination_ciphertext, c.verification_expires_at, c.verification_attempts, "
                "c.binding_id AS channel_binding_id "
                "FROM notification_outbox o JOIN notification_channels c "
                "ON c.id = o.channel_id AND c.user_id = o.user_id "
                "WHERE o.user_id = %s AND o.status = 'queued' AND o.next_attempt_at <= %s "
                "AND c.kind = ANY (%s) "
                "AND (c.kind <> 'push' OR EXISTS (SELECT 1 FROM sessions s "
                "WHERE s.user_id = c.user_id AND s.id = c.session_id "
                "AND s.revoked_at IS NULL AND s.expires_at > %s)) "
                "ORDER BY o.next_attempt_at, o.created_at LIMIT 1 FOR UPDATE OF o SKIP LOCKED",
                (user_id, now, self._configured_kinds(), now),
            )
            found = cur.fetchone()
            if found is None:
                return None
            row = dict(found)
            payload = self._open(row["payload_ciphertext"])
            expired = self._delivery_expired(row, payload, now)
            allowed = self._delivery_allowed(cur, user_id, row, payload, preferences, now)
            if not allowed or expired:
                cur.execute(
                    "UPDATE notification_outbox SET status = 'cancelled', last_error = %s, "
                    "updated_at = clock_timestamp() "
                    "WHERE user_id = %s AND id = %s",
                    ("delivery_expired" if expired else "delivery_preference_changed",
                     user_id, row["id"]),
                )
                return None
            due = (now if row["kind"] in {"verification", "test"}
                   else delivery_time(preferences, now))
            if due > now:
                cur.execute(
                    "UPDATE notification_outbox SET next_attempt_at = %s, "
                    "updated_at = clock_timestamp() "
                    "WHERE user_id = %s AND id = %s", (due, user_id, row["id"]),
                )
                return None
            lease = uuid4()
            cur.execute(
                "UPDATE notification_outbox SET status = 'sending', attempts = attempts + 1, "
                "lease_token = %s, lease_until = %s, updated_at = clock_timestamp() "
                "WHERE user_id = %s AND id = %s",
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
            # Push providers and lock screens get no instrument or event source
            # metadata. An opaque binding lets the service worker reject an old
            # account's notification after a shared-device account switch.
            payload = {key: row["payload"][key] for key in ("title", "body", "tag")}
            payload.update(url=_notification_target(row["payload"]),
                           binding_id=str(row["binding_id"]), kind=row["kind"])
            ttl = 86400
            if row["kind"] == "test":
                ttl = max(0, min(300, int((
                    row["created_at"] + timedelta(minutes=5) - now
                ).total_seconds())))
            result = self.transport.send_push(row["destination"], payload, ttl_seconds=ttl)
        else:
            result = self.transport.send_email(row["destination"], row["payload"])
        state = result.status
        if state == "queued" and row["attempts"] >= 6:
            state = "failed"
        delay = max(result.retry_after, min(21600, 30 * 2 ** row["attempts"]))
        with self.workspace._transaction(user_id) as cur:
            if state == "queued" and row["channel_kind"] == "push":
                self._maintain_channels(cur, user_id, now)
                cur.execute(
                    "SELECT 1 FROM notification_channels WHERE user_id = %s AND id = %s "
                    "AND status = 'active' AND binding_id = %s",
                    (user_id, row["channel_id"], row["binding_id"]),
                )
                if cur.fetchone() is None:
                    state = "cancelled"
            cur.execute(
                "UPDATE notification_outbox SET status = %s, last_error = %s, "
                "next_attempt_at = %s, accepted_at = %s, lease_until = NULL, "
                "updated_at = clock_timestamp() "
                "WHERE user_id = %s AND id = %s AND status = 'sending' AND lease_token = %s",
                (state, result.code, now + timedelta(seconds=delay),
                 now if state == "accepted" else None, user_id, row["id"], row["lease_token"]),
            )
            if result.expired:
                cur.execute(
                    "UPDATE notification_channels SET status = 'expired', updated_at = %s "
                    "WHERE user_id = %s AND id = %s AND status = 'active' "
                    "AND binding_id IS NOT DISTINCT FROM %s",
                    (now, user_id, row["channel_id"], row["binding_id"]),
                )
        return True

    def queue_operator_alert(self, user_id: UUID, key: str, title: str) -> None:
        """Called only by server-owned operational monitoring, to opted-in channels."""
        if user_id != self.config.operator_user_id:
            return
        if re.fullmatch(r"[a-z0-9_-]{1,100}", key) is None or not 1 <= len(title) <= 160:
            raise ValueError("notification_operational_alert_invalid")
        with self.workspace._transaction(user_id) as cur:
            self._maintain_channels(cur, user_id, datetime.now(UTC))
            prefs = self.workspace._preferences(cur, user_id)["document"]
            if not prefs["notifications"]["system"]:
                return
            cur.execute(
                "SELECT id FROM notification_channels WHERE user_id = %s AND status = 'active' "
                "AND kind = ANY (%s)", (user_id, self._configured_kinds()),
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
        self.queue_events(user_id, now=now)
        if user_id == self.config.operator_user_id and needs_attention:
            self.queue_operator_alert(
                user_id, "health-" + now.strftime("%Y%m%d%H"),
                "Мониторинг обнаружил задержку или ошибку фоновой обработки данных "
                "или уведомлений. "
                "Откройте состояние сервиса в настройках для проверки.",
            )
        for _ in range(5):
            if self._stop.is_set() or not self.deliver_one(user_id):
                break

    def run_pending(self) -> None:
        now = datetime.now(UTC)
        self.database.record_worker_heartbeat("notifications", status="running")
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
        failed = False
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
                failed = True
            self.database.record_worker_heartbeat("notifications", status="running")
        self.database.record_worker_heartbeat(
            "notifications", status="attention" if failed else "ok",
        )

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
                try:
                    self.database.record_worker_heartbeat("notifications", status="attention")
                except Exception as heartbeat_error:
                    _log_worker_failure("notification_heartbeat_failed", heartbeat_error)
            self._wake.wait(timeout=30)
            self._wake.clear()
