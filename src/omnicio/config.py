"""Application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigurationError(RuntimeError):
    """Raised when required configuration is missing."""


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigurationError(f"{name} is required")
    return value


def positive_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ConfigurationError(f"{name} must be positive")
    return value


def boolean(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} must be boolean")


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    crypto_key: str
    lookup_key: str
    otp_key: str
    ip_key: str
    broker_token_crypto_key: str
    sms_provider: str
    sms_login: str
    sms_token: str
    sms_sender: str
    owner_phone: str
    owner_login_enabled: bool
    registration_enabled: bool
    privacy_version: str
    consent_version: str
    terms_version: str
    otp_ttl_seconds: int
    otp_max_attempts: int
    otp_resend_cooldown_seconds: int
    otp_phone_hourly_limit: int
    otp_ip_hourly_limit: int
    session_ttl_seconds: int

    @property
    def sms_ready(self) -> bool:
        return (
            self.sms_provider == "smsaero"
            and bool(self.sms_login)
            and bool(self.sms_token)
            and bool(self.sms_sender)
        )

    @property
    def owner_login_ready(self) -> bool:
        return (
            self.owner_login_enabled
            and self.sms_ready
            and bool(self.owner_phone)
        )


def load_settings() -> Settings:
    return Settings(
        database_url=required("DATABASE_URL"),
        crypto_key=required("PHONE_CRYPTO_KEY"),
        lookup_key=required("PHONE_LOOKUP_KEY"),
        otp_key=required("OTP_SIGNING_KEY"),
        ip_key=required("CLIENT_IP_KEY"),
        broker_token_crypto_key=required("BROKER_TOKEN_CRYPTO_KEY"),
        sms_provider=os.environ.get("SMS_PROVIDER", "disabled").strip().lower(),
        sms_login=os.environ.get("SMS_PROVIDER_LOGIN", "").strip(),
        sms_token=os.environ.get("SMS_PROVIDER_TOKEN", "").strip(),
        sms_sender=os.environ.get("SMS_SENDER", "").strip(),
        owner_phone=os.environ.get("OWNER_PHONE", "").strip(),
        owner_login_enabled=boolean("OWNER_LOGIN_ENABLED", False),
        registration_enabled=boolean("REGISTRATION_ENABLED", False),
        privacy_version=os.environ.get("LEGAL_PRIVACY_VERSION", "").strip(),
        consent_version=os.environ.get("LEGAL_CONSENT_VERSION", "").strip(),
        terms_version=os.environ.get("LEGAL_TERMS_VERSION", "").strip(),
        otp_ttl_seconds=positive_int("OTP_TTL_SECONDS", 300),
        otp_max_attempts=positive_int("OTP_MAX_ATTEMPTS", 5),
        otp_resend_cooldown_seconds=positive_int("OTP_RESEND_COOLDOWN_SECONDS", 60),
        otp_phone_hourly_limit=positive_int("OTP_PHONE_HOURLY_LIMIT", 5),
        otp_ip_hourly_limit=positive_int("OTP_IP_HOURLY_LIMIT", 20),
        session_ttl_seconds=positive_int("SESSION_TTL_SECONDS", 34_560_000),
    )
