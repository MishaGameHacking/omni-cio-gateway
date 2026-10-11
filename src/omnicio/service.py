"""Email/password authentication and browser-bound ownership verification."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from threading import BoundedSemaphore, Event, Thread
from typing import Any
from uuid import UUID, uuid4

from psycopg import Error as DatabaseError

from .config import Settings
from .db import Database, UserRecord
from .notifications import NotificationConfig, NotificationTransport, normalize_email
from .security import (
    EMAIL_CODE_TTL_SECONDS,
    EMAIL_DOMAINS,
    EMAIL_RESEND_SECONDS,
    SecurityValueError,
    auth_rate_digest,
    client_ip_digest,
    decrypt_secret,
    email_code_digest,
    encrypt_secret,
    format_public_id,
    generate_email_code,
    generate_session_token,
    hash_password,
    session_digest,
    validate_new_password,
    verify_password,
)
from .social_auth import SocialAuthService

logger = logging.getLogger(__name__)


class AuthError(RuntimeError):
    """An authentication operation could not complete."""


class LoginUnavailable(AuthError):
    """Email enrollment or recovery is not configured."""


class AuthRateLimited(AuthError):
    """A durable abuse-prevention budget is exhausted."""


class InvalidCredentials(AuthError):
    """The email/password pair cannot establish an authenticated session."""


class InvalidEmailChallenge(AuthError):
    """Ownership proof is invalid, expired, used, or belongs to another browser."""


class AccountDeletionRejected(AuthError):
    """A self-service account deletion confirmation is invalid."""


@dataclass(frozen=True, slots=True)
class LoginSucceeded:
    session_token: str
    public_id: str
    created: bool
    expires_in_seconds: int


@dataclass(frozen=True, slots=True)
class EmailChallengeStarted:
    challenge_id: UUID
    flow_token: str
    expires_in_seconds: int = EMAIL_CODE_TTL_SECONDS
    resend_after_seconds: int = EMAIL_RESEND_SECONDS


def normalize_login_email(value: str) -> str:
    """Reuse the mail validator; preserve local-part case, dots, and plus aliases."""
    try:
        email = normalize_email(value.strip())
    except ValueError as exc:
        raise SecurityValueError("email_invalid") from exc
    if email.rsplit("@", 1)[1] not in EMAIL_DOMAINS:
        raise SecurityValueError("email_domain_not_allowed")
    return email


def validate_auth_email_configuration(settings: Settings) -> str:
    """Validate local mail configuration and return its selected encryption key."""
    crypto_key = settings.notification_crypto_key or settings.broker_token_crypto_key
    if settings.auth_smtp_sender:
        normalize_email(settings.auth_smtp_sender)
    if settings.auth_email_ready:
        probe = "omnicio-auth-email-configuration"
        if decrypt_secret(encrypt_secret(probe, crypto_key), crypto_key) != probe:
            raise SecurityValueError("auth_email_key_verification_failed")
    return crypto_key


class AuthService:
    def __init__(
        self, settings: Settings, database: Database, *,
        transport: NotificationTransport | None = None,
    ) -> None:
        self.settings = settings
        self.database = database
        self.social = SocialAuthService(settings, database)
        self._crypto_key = validate_auth_email_configuration(settings)
        self._transport = transport or NotificationTransport(NotificationConfig(
            crypto_key=self._crypto_key, email_enabled=True,
            smtp_host=settings.auth_smtp_host, smtp_port=settings.auth_smtp_port,
            smtp_username=settings.auth_smtp_username, smtp_password=settings.auth_smtp_password,
            smtp_sender=settings.auth_smtp_sender, smtp_mode=settings.auth_smtp_mode,
        ))
        # A missing account performs the same KDF work as a known account.
        self._dummy_password_hash = hash_password(generate_session_token())
        self._password_slots = BoundedSemaphore(4)
        self._stop = Event()
        self._wake = Event()
        self._thread: Thread | None = None

    def legal_versions(self) -> dict[str, str]:
        return {
            "privacy_policy": self.settings.privacy_version,
            "personal_data_consent": self.settings.consent_version,
            "terms": self.settings.terms_version,
        }

    @property
    def registration_available(self) -> bool:
        return self.settings.auth_email_ready and all(self.legal_versions().values())

    def _require_email(self) -> None:
        if not self.settings.auth_email_ready:
            raise LoginUnavailable("email_not_configured")

    def _budget(self, scope: str, email: str, client_ip: str, *, sending: bool = False) -> None:
        key = self.settings.ip_key
        buckets = [
            (auth_rate_digest(scope + ":email", email, key), 10, 900),
            (auth_rate_digest(scope + ":ip", client_ip, key), 60, 300),
            (auth_rate_digest(scope + ":global", "all", key), 10000, 60),
        ]
        if sending:
            buckets.extend([
                (auth_rate_digest("mail:email:minute", email, key), 1, EMAIL_RESEND_SECONDS),
                (auth_rate_digest("mail:email:hour", email, key), 5, 3600),
                (auth_rate_digest("mail:ip:hour", client_ip, key), 30, 3600),
            ])
        if not self.database.consume_auth_budget(buckets):
            raise AuthRateLimited("auth_rate_limited")

    def _password_hash(self, password: str, email: str) -> str:
        validate_new_password(password, email)
        if not self._password_slots.acquire(blocking=False):
            raise AuthRateLimited("auth_busy")
        try:
            return hash_password(password)
        finally:
            self._password_slots.release()

    def _delivery(self, email: str, code: str) -> bytes:
        return encrypt_secret(json.dumps({"email": email, "code": code}), self._crypto_key)

    def request_email(
        self, *, email: str, password: str | None, client_ip: str, purpose: str,
        accepted_legal_versions: dict[str, str] | None = None,
        user: UserRecord | None = None, enrollment_session: str | None = None,
    ) -> EmailChallengeStarted:
        self._require_email()
        email = normalize_login_email(email)
        self._budget("request", email, client_ip, sending=True)
        if purpose not in {"register", "enroll", "reset"}:
            raise SecurityValueError("auth_purpose_invalid")
        if purpose != "reset" and (not self.registration_available
                or accepted_legal_versions != self.legal_versions()):
            raise LoginUnavailable("legal_versions_unavailable")
        encoded = self._password_hash(password or "", email) if purpose != "reset" else None
        challenge_id, flow_token, code = uuid4(), generate_session_token(), generate_email_code()
        self.database.create_email_challenge(
            challenge_id=challenge_id, purpose=purpose, email=email, password_hash=encoded,
            flow_digest=session_digest(flow_token),
            code_digest=email_code_digest(str(challenge_id), code, self.settings.ip_key),
            client_ip_hash=client_ip_digest(client_ip, self.settings.ip_key),
            legal_versions=accepted_legal_versions or {},
            delivery_ciphertext=self._delivery(email, code),
            user_id=user.id if user else None,
            enrollment_session_digest=session_digest(enrollment_session)
            if enrollment_session else None,
        )
        self._wake.set()
        return EmailChallengeStarted(challenge_id, flow_token)

    def resend_email(
        self, challenge_id: UUID, flow_token: str, *, client_ip: str,
    ) -> EmailChallengeStarted:
        self._require_email()
        challenge = self._challenge(challenge_id, flow_token)
        self._budget("resend", challenge["email"], client_ip, sending=True)
        code = generate_email_code()
        ttl = self.database.resend_email_challenge(
            challenge_id, session_digest(flow_token),
            email_code_digest(str(challenge_id), code, self.settings.ip_key),
            self._delivery(challenge["email"], code),
        )
        if ttl is None:
            raise AuthRateLimited("auth_resend_unavailable")
        self._wake.set()
        return EmailChallengeStarted(challenge_id, flow_token, expires_in_seconds=ttl)

    def _challenge(self, challenge_id: UUID, flow_token: str) -> dict[str, Any]:
        if not flow_token or len(flow_token) > 256:
            raise InvalidEmailChallenge("email_code_invalid_or_expired")
        challenge = self.database.email_challenge(challenge_id, session_digest(flow_token))
        if challenge is None:
            raise InvalidEmailChallenge("email_code_invalid_or_expired")
        return challenge

    def verify_email(
        self, challenge_id: UUID, code: str, flow_token: str, *, client_ip: str,
        enrollment_session: str | None = None,
    ) -> LoginSucceeded:
        challenge = self._challenge(challenge_id, flow_token)
        if challenge["purpose"] not in {"register", "enroll"}:
            raise InvalidEmailChallenge("email_code_invalid_or_expired")
        self._budget("verify", challenge["email"], client_ip)
        token = generate_session_token()
        result = self.database.consume_email_challenge(
            challenge_id=challenge_id, flow_digest=session_digest(flow_token),
            code_digest=email_code_digest(str(challenge_id), code, self.settings.ip_key),
            purpose=challenge["purpose"],
            client_ip_hash=client_ip_digest(client_ip, self.settings.ip_key),
            legal_versions=self.legal_versions(), token_digest=session_digest(token),
            session_ttl_seconds=self.settings.session_ttl_seconds,
            enrollment_session_digest=session_digest(enrollment_session)
            if enrollment_session else None,
        )
        if result is None:
            raise InvalidEmailChallenge("email_code_invalid_or_expired")
        user, created = result
        return LoginSucceeded(token, format_public_id(user.public_id), created,
                              self.settings.session_ttl_seconds)

    def login_email(self, email: str, password: str, *, client_ip: str) -> LoginSucceeded:
        try:
            email = normalize_login_email(email)
        except SecurityValueError as exc:
            raise InvalidCredentials("email_or_password_invalid") from exc
        self._budget("login", email, client_ip)
        identity = self.database.email_identity(email)
        encoded = identity["password_hash"] if identity else self._dummy_password_hash
        if not self._password_slots.acquire(blocking=False):
            raise AuthRateLimited("auth_busy")
        try:
            valid = verify_password(password, encoded)
        finally:
            self._password_slots.release()
        if not valid or identity is None:
            raise InvalidCredentials("email_or_password_invalid")
        token = generate_session_token()
        user = self.database.complete_email_login(
            identity, token_digest=session_digest(token),
            client_ip_hash=client_ip_digest(client_ip, self.settings.ip_key),
            session_ttl_seconds=self.settings.session_ttl_seconds,
        )
        if user is None:
            raise InvalidCredentials("email_or_password_invalid")
        return LoginSucceeded(token, format_public_id(user.public_id), False,
                              self.settings.session_ttl_seconds)

    def reset_password(
        self, challenge_id: UUID, code: str, flow_token: str, *, password: str, client_ip: str,
    ) -> None:
        challenge = self._challenge(challenge_id, flow_token)
        if challenge["purpose"] != "reset":
            raise InvalidEmailChallenge("email_code_invalid_or_expired")
        self._budget("verify", challenge["email"], client_ip)
        encoded = self._password_hash(password, challenge["email"])
        result = self.database.consume_email_challenge(
            challenge_id=challenge_id, flow_digest=session_digest(flow_token),
            code_digest=email_code_digest(str(challenge_id), code, self.settings.ip_key),
            purpose="reset", password_hash=encoded,
            client_ip_hash=client_ip_digest(client_ip, self.settings.ip_key), legal_versions={},
            token_digest=session_digest(generate_session_token()),
            session_ttl_seconds=self.settings.session_ttl_seconds,
        )
        if result is None:
            raise InvalidEmailChallenge("email_code_invalid_or_expired")

    def refresh_session(self, token: str) -> UserRecord | None:
        # SMTP failure must not lock out a verified account or an existing legacy
        # session that still needs to enroll its new email credentials.
        if not token or len(token) > 256:
            return None
        return self.database.refresh_session_digest(
            session_digest(token), session_ttl_seconds=self.settings.session_ttl_seconds,
        )

    def delete_account(self, user: UserRecord, confirmation_public_id: str) -> bool:
        if confirmation_public_id != format_public_id(user.public_id):
            raise AccountDeletionRejected("profile ID confirmation does not match")
        return self.database.delete_user_account(user.id)

    def logout(self, token: str) -> None:
        if token:
            self.database.revoke_session(session_digest(token))

    def start(self) -> None:
        if self._thread is None:
            self._thread = Thread(target=self._send_loop, name="email-auth", daemon=True)
            self._thread.start()

    def close(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=15)

    def _send_loop(self) -> None:
        while not self._stop.is_set():
            try:
                delivered = self.deliver_next_email()
            except (DatabaseError, ValueError) as exc:
                # Safe class only; neither SQL parameters nor mail contents are logged.
                logger.warning("auth_email_worker_failed error_type=%s", type(exc).__name__)
                delivered = False
            if not delivered:
                self._wake.wait(timeout=2)
                self._wake.clear()

    def deliver_next_email(self) -> bool:
        """Claim one durable message; ambiguous SMTP outcomes require a fresh user request."""
        row = self.database.claim_email_delivery(delivery_enabled=self.settings.auth_email_ready)
        if row is None:
            return False
        destination = json.loads(decrypt_secret(
            bytes(row["delivery_ciphertext"]), self._crypto_key,
        ))
        action = "восстановления пароля" if row["purpose"] == "reset" else "подтверждения почты"
        result = self._transport.send_email({"email": destination["email"]}, {
            "title": "OMNICIO — код " + action,
            "body": (f"Ваш код {action}: {destination['code']}\n\n"
                     "Код действует до 10 минут. Пароль от вашей почты не требуется. "
                     "Если вы не запрашивали код, проигнорируйте это письмо."),
            "tag": "auth-" + str(row["id"]),
        })
        self.database.complete_email_delivery(
            row["id"], bytes(row["code_digest"]),
            delivery_status=result.status, delivery_code=result.code,
        )
        return True
