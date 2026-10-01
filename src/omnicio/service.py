"""Phone authentication business logic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

from .config import Settings
from .db import Database, UserRecord, one_hour_ago, utcnow
from .security import (
    client_ip_digest,
    encrypt_phone,
    format_public_id,
    generate_otp,
    generate_session_token,
    normalize_russian_mobile,
    otp_digest,
    phone_lookup,
    session_digest,
    verify_otp_digest,
)
from .sms import SmsProvider


class AuthError(RuntimeError):
    """Base authentication service error."""


class RegistrationClosed(AuthError):
    """Registration is not legally or operationally ready."""


class OwnerAccessDenied(AuthError):
    """The submitted phone is not the configured private owner."""


class RateLimited(AuthError):
    """OTP send rate limit was exceeded."""


class InvalidChallenge(AuthError):
    """OTP challenge/code is invalid, expired, or already consumed."""


@dataclass(frozen=True, slots=True)
class ChallengeIssued:
    challenge_id: UUID
    expires_in_seconds: int


@dataclass(frozen=True, slots=True)
class LoginSucceeded:
    session_token: str
    public_id: str
    created: bool
    expires_in_seconds: int


class AuthService:
    def __init__(self, settings: Settings, database: Database, sms: SmsProvider) -> None:
        self.settings = settings
        self.database = database
        self.sms = sms

    def legal_versions(self) -> dict[str, str]:
        return {
            "privacy_policy": self.settings.privacy_version,
            "personal_data_consent": self.settings.consent_version,
            "terms": self.settings.terms_version,
        }

    def issue_challenge(
        self,
        *,
        phone_raw: str,
        client_ip: str,
        accepted_privacy: bool,
        accepted_personal_data: bool,
        accepted_terms: bool,
        confirmed_age_18: bool,
    ) -> ChallengeIssued:
        if not self.settings.owner_login_ready:
            raise RegistrationClosed("owner login is not enabled")

        phone = normalize_russian_mobile(phone_raw)
        owner_phone = normalize_russian_mobile(self.settings.owner_phone)
        if phone != owner_phone:
            raise OwnerAccessDenied("phone is not allowed for this private account")

        if not (accepted_privacy and accepted_personal_data and accepted_terms):
            raise RegistrationClosed("required legal documents are not accepted")
        if not confirmed_age_18:
            raise RegistrationClosed("service is available only to users aged 18+")

        lookup = phone_lookup(phone, self.settings.lookup_key)
        ip_hash = client_ip_digest(client_ip, self.settings.ip_key)

        now = utcnow()
        latest = self.database.latest_challenge_created_at(lookup)
        if latest is not None:
            cooldown = timedelta(seconds=self.settings.otp_resend_cooldown_seconds)
            if now - latest < cooldown:
                raise RateLimited("OTP resend cooldown is active")

        phone_count, ip_count = self.database.recent_challenge_counts(
            phone_lookup=lookup,
            client_ip_hash=ip_hash,
            since=one_hour_ago(),
        )
        if phone_count >= self.settings.otp_phone_hourly_limit:
            raise RateLimited("phone OTP limit exceeded")
        if ip_count >= self.settings.otp_ip_hourly_limit:
            raise RateLimited("IP OTP limit exceeded")

        challenge_id = uuid4()
        code = generate_otp()
        self.database.create_challenge(
            challenge_id=challenge_id,
            phone_lookup=lookup,
            phone_ciphertext=encrypt_phone(phone, self.settings.crypto_key),
            code_digest=otp_digest(str(challenge_id), code, self.settings.otp_key),
            client_ip_hash=ip_hash,
            attempts_remaining=self.settings.otp_max_attempts,
            ttl_seconds=self.settings.otp_ttl_seconds,
            legal_versions=self.legal_versions(),
        )

        provider_message_id = self.sms.send_otp(phone, code)
        self.database.mark_challenge_sent(challenge_id, provider_message_id)

        return ChallengeIssued(
            challenge_id=challenge_id,
            expires_in_seconds=self.settings.otp_ttl_seconds,
        )

    def verify_challenge(
        self,
        *,
        challenge_id: UUID,
        code: str,
        client_ip: str,
    ) -> LoginSucceeded:
        if not self.settings.owner_login_ready:
            raise RegistrationClosed("owner login is not enabled")
        if len(code) != 6 or not code.isdigit():
            raise InvalidChallenge("invalid verification code")

        challenge = self.database.load_challenge(challenge_id)
        if challenge is None:
            raise InvalidChallenge("challenge not found")
        if challenge.consumed_at is not None or challenge.expires_at <= utcnow():
            raise InvalidChallenge("challenge expired or consumed")
        if challenge.attempts_remaining <= 0:
            raise InvalidChallenge("challenge attempts exhausted")
        if challenge.legal_versions != self.legal_versions():
            raise InvalidChallenge("legal document versions changed")

        matches = verify_otp_digest(
            str(challenge.id),
            code,
            challenge.code_digest,
            self.settings.otp_key,
        )
        if not matches:
            self.database.record_failed_challenge_attempt(challenge.id)
            raise InvalidChallenge("invalid verification code")

        ip_hash = client_ip_digest(client_ip, self.settings.ip_key)
        token = generate_session_token()
        token_hash = session_digest(token)

        completed = self.database.complete_verified_challenge(
            challenge_id=challenge.id,
            client_ip_hash=ip_hash,
            session_token_digest=token_hash,
            session_ttl_seconds=self.settings.session_ttl_seconds,
            legal_versions=self.legal_versions(),
        )
        if completed is None:
            raise InvalidChallenge("challenge expired or already consumed")

        user, created = completed
        return LoginSucceeded(
            session_token=token,
            public_id=format_public_id(user.public_id),
            created=created,
            expires_in_seconds=self.settings.session_ttl_seconds,
        )

    def refresh_session(self, token: str) -> UserRecord | None:
        if not token:
            return None
        return self.database.refresh_session_digest(
            session_digest(token),
            session_ttl_seconds=self.settings.session_ttl_seconds,
        )

    def logout(self, token: str) -> None:
        if token:
            self.database.revoke_session(session_digest(token))
