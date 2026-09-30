from __future__ import annotations

import base64
import os
from datetime import timedelta
from uuid import UUID

from cryptography.fernet import Fernet

from omnicio.config import Settings
from omnicio.db import ChallengeRecord, UserRecord, utcnow
from omnicio.service import AuthService


class FakeSms:
    def __init__(self) -> None:
        self.phone = ""
        self.code = ""

    def send_otp(self, phone: str, code: str) -> str:
        self.phone = phone
        self.code = code
        return "provider-message-1"


class FakeDatabase:
    def __init__(self) -> None:
        self.challenge: ChallengeRecord | None = None
        self.sent = False
        self.session_digest: bytes | None = None
        self.refreshed_ttl: int | None = None
        self.user = UserRecord(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            public_id=1,
            status="active",
        )

    def latest_challenge_created_at(self, phone_lookup: bytes):
        return None

    def recent_challenge_counts(self, **kwargs):
        return (0, 0)

    def create_challenge(self, **kwargs):
        challenge_id = kwargs["challenge_id"]
        self.challenge = ChallengeRecord(
            id=challenge_id,
            phone_lookup=kwargs["phone_lookup"],
            phone_ciphertext=kwargs["phone_ciphertext"],
            code_digest=kwargs["code_digest"],
            attempts_remaining=kwargs["attempts_remaining"],
            expires_at=utcnow() + timedelta(seconds=kwargs["ttl_seconds"]),
            consumed_at=None,
            legal_versions=kwargs["legal_versions"],
        )
        return challenge_id

    def mark_challenge_sent(self, challenge_id, provider_message_id):
        self.sent = True

    def load_challenge(self, challenge_id):
        if self.challenge and self.challenge.id == challenge_id:
            return self.challenge
        return None

    def record_failed_challenge_attempt(self, challenge_id):
        return self.challenge is not None and self.challenge.id == challenge_id

    def complete_verified_challenge(self, **kwargs):
        challenge_id = kwargs["challenge_id"]
        if not self.challenge or self.challenge.id != challenge_id:
            return None
        if self.challenge.consumed_at is not None:
            return None
        self.challenge = ChallengeRecord(
            id=self.challenge.id,
            phone_lookup=self.challenge.phone_lookup,
            phone_ciphertext=self.challenge.phone_ciphertext,
            code_digest=self.challenge.code_digest,
            attempts_remaining=self.challenge.attempts_remaining,
            expires_at=self.challenge.expires_at,
            consumed_at=utcnow(),
            legal_versions=self.challenge.legal_versions,
        )
        self.session_digest = kwargs["session_token_digest"]
        return self.user, True

    def refresh_session_digest(self, token_digest, *, session_ttl_seconds):
        self.refreshed_ttl = session_ttl_seconds
        if token_digest == self.session_digest:
            return self.user
        return None

    def revoke_session(self, token_digest):
        if token_digest == self.session_digest:
            self.session_digest = None


def settings() -> Settings:
    return Settings(
        database_url="postgresql://example.invalid/db",
        crypto_key=Fernet.generate_key().decode("ascii"),
        lookup_key=base64.urlsafe_b64encode(os.urandom(32)).decode("ascii"),
        otp_key=base64.urlsafe_b64encode(os.urandom(32)).decode("ascii"),
        ip_key=base64.urlsafe_b64encode(os.urandom(32)).decode("ascii"),
        sms_provider="mts_exolve",
        sms_token="test-token",
        sms_sender="79990000000",
        registration_enabled=True,
        operator_name="Test Operator",
        operator_address="Moscow",
        privacy_contact="privacy@example.test",
        privacy_version="2026-09-30",
        consent_version="2026-09-30",
        terms_version="2026-09-30",
        otp_ttl_seconds=300,
        otp_max_attempts=5,
        otp_resend_cooldown_seconds=60,
        otp_phone_hourly_limit=5,
        otp_ip_hourly_limit=20,
        session_ttl_seconds=34_560_000,
    )


def test_issue_and_verify_creates_public_id_and_session() -> None:
    db = FakeDatabase()
    sms = FakeSms()
    service = AuthService(settings(), db, sms)

    issued = service.issue_challenge(
        phone_raw="+79161234567",
        client_ip="203.0.113.10",
        accepted_privacy=True,
        accepted_personal_data=True,
        accepted_terms=True,
        confirmed_age_18=True,
    )

    assert db.sent
    assert sms.phone == "+79161234567"
    assert len(sms.code) == 6

    result = service.verify_challenge(
        challenge_id=issued.challenge_id,
        code=sms.code,
        client_ip="203.0.113.10",
    )

    assert result.public_id == "000000001"
    assert result.created is True
    assert service.refresh_session(result.session_token) == db.user
    assert db.refreshed_ttl == 34_560_000
