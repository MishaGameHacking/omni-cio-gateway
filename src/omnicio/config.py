"""Application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from uuid import UUID

# Environment defaults live beside their validation, not in provider adapters.
# TTLs are seconds; the long session lifetime remains subject to server revocation.
DEFAULT_SESSION_TTL_SECONDS = 34_560_000
DEFAULT_SMTP_PORT = 465
DEFAULT_BILLING_PERIOD_DAYS = 30
DEFAULT_ASSISTANT_DAILY_REQUEST_LIMIT = 30


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


def optional_uuid(name: str) -> UUID | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    try:
        value = UUID(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be a nonzero UUID") from exc
    if value.int == 0:
        raise ConfigurationError(f"{name} must be a nonzero UUID")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    ip_key: str
    broker_token_crypto_key: str
    privacy_version: str
    consent_version: str
    terms_version: str
    session_ttl_seconds: int
    auth_smtp_host: str = ""
    auth_smtp_port: int = DEFAULT_SMTP_PORT
    auth_smtp_username: str = ""
    auth_smtp_password: str = ""
    auth_smtp_sender: str = ""
    auth_smtp_mode: str = "tls"
    market_data_token: str = ""
    market_data_distribution_approved: bool = False
    assistant_base_url: str = ""
    assistant_api_key: str = ""
    assistant_model: str = ""
    notifications_enabled: bool = False
    notification_email_enabled: bool = False
    notification_crypto_key: str = ""
    notification_vapid_private_key: str = ""
    notification_vapid_subject: str = ""
    notification_smtp_host: str = ""
    notification_smtp_port: int = DEFAULT_SMTP_PORT
    notification_smtp_username: str = ""
    notification_smtp_password: str = ""
    notification_smtp_sender: str = ""
    notification_smtp_mode: str = "tls"
    billing_enabled: bool = False
    billing_terminal_key: str = ""
    billing_password: str = ""
    billing_amount_kopecks: int = 0
    billing_period_days: int = DEFAULT_BILLING_PERIOD_DAYS
    billing_offer_version: str = ""
    billing_description: str = ""
    billing_taxation: str = ""
    billing_tax: str = ""
    assistant_enabled: bool = False
    assistant_allowed_endpoints: tuple[str, ...] = ()
    assistant_daily_request_limit: int = DEFAULT_ASSISTANT_DAILY_REQUEST_LIMIT
    operator_user_id: UUID | None = None
    legal_operator_name: str = ""
    legal_operator_email: str = ""
    release_build: str = ""

    @property
    def login_ready(self) -> bool:
        # Password verification never depends on SMTP availability.
        return True

    @property
    def auth_email_ready(self) -> bool:
        return bool(self.auth_smtp_host and self.auth_smtp_sender)

    @property
    def access_mode(self) -> str:
        return "public"


def load_settings() -> Settings:
    email_enabled = boolean("NOTIFICATION_EMAIL_ENABLED", False)
    auth_host = os.environ.get("AUTH_SMTP_HOST", "").strip()
    auth_mode = os.environ.get("AUTH_SMTP_MODE", "tls").strip() if auth_host else "tls"
    auth_port = (
        positive_int("AUTH_SMTP_PORT", DEFAULT_SMTP_PORT) if auth_host else DEFAULT_SMTP_PORT
    )
    if auth_mode not in {"tls", "starttls"} or auth_port > 65535:
        raise ConfigurationError("AUTH_SMTP_MODE or AUTH_SMTP_PORT is invalid")
    return Settings(
        database_url=required("DATABASE_URL"),
        ip_key=required("CLIENT_IP_KEY"),
        broker_token_crypto_key=required("BROKER_TOKEN_CRYPTO_KEY"),
        privacy_version=os.environ.get("LEGAL_PRIVACY_VERSION", "").strip(),
        consent_version=os.environ.get("LEGAL_CONSENT_VERSION", "").strip(),
        terms_version=os.environ.get("LEGAL_TERMS_VERSION", "").strip(),
        session_ttl_seconds=positive_int("SESSION_TTL_SECONDS", DEFAULT_SESSION_TTL_SECONDS),
        auth_smtp_host=auth_host,
        auth_smtp_port=auth_port,
        auth_smtp_username=os.environ.get("AUTH_SMTP_USERNAME", "").strip(),
        auth_smtp_password=os.environ.get("AUTH_SMTP_PASSWORD", ""),
        auth_smtp_sender=os.environ.get("AUTH_SMTP_SENDER", "").strip(),
        auth_smtp_mode=auth_mode,
        market_data_token=os.environ.get("MARKET_DATA_TOKEN", ""),
        market_data_distribution_approved=boolean("MARKET_DATA_DISTRIBUTION_APPROVED", False),
        assistant_base_url=(os.environ.get("ASSISTANT_BASE_URL", "").strip()
                            if boolean("ASSISTANT_ENABLED", False) else ""),
        assistant_api_key=os.environ.get("ASSISTANT_API_KEY", ""),
        assistant_model=os.environ.get("ASSISTANT_MODEL", "").strip(),
        notifications_enabled=boolean("NOTIFICATIONS_ENABLED", False),
        notification_email_enabled=email_enabled,
        notification_crypto_key=os.environ.get("NOTIFICATION_CRYPTO_KEY", "").strip(),
        notification_vapid_private_key=os.environ.get("NOTIFICATION_VAPID_PRIVATE_KEY", "").strip(),
        notification_vapid_subject=os.environ.get("NOTIFICATION_VAPID_SUBJECT", "").strip(),
        notification_smtp_host=(os.environ.get("NOTIFICATION_SMTP_HOST", "").strip()
                                if email_enabled else ""),
        notification_smtp_port=(positive_int("NOTIFICATION_SMTP_PORT", DEFAULT_SMTP_PORT)
                               if email_enabled else DEFAULT_SMTP_PORT),
        notification_smtp_username=(os.environ.get("NOTIFICATION_SMTP_USERNAME", "").strip()
                                    if email_enabled else ""),
        notification_smtp_password=(os.environ.get("NOTIFICATION_SMTP_PASSWORD", "")
                                    if email_enabled else ""),
        notification_smtp_sender=(os.environ.get("NOTIFICATION_SMTP_SENDER", "").strip()
                                  if email_enabled else ""),
        notification_smtp_mode=(os.environ.get("NOTIFICATION_SMTP_MODE", "tls").strip()
                                if email_enabled else "tls"),
        billing_enabled=boolean("BILLING_ENABLED", False),
        billing_terminal_key=os.environ.get("BILLING_TERMINAL_KEY", "").strip(),
        billing_password=os.environ.get("BILLING_PASSWORD", ""),
        billing_amount_kopecks=positive_int("BILLING_AMOUNT_KOPECKS", 0),
        billing_period_days=positive_int("BILLING_PERIOD_DAYS", DEFAULT_BILLING_PERIOD_DAYS),
        billing_offer_version=os.environ.get("BILLING_OFFER_VERSION", "").strip(),
        billing_description=os.environ.get("BILLING_DESCRIPTION", "").strip(),
        billing_taxation=os.environ.get("BILLING_TAXATION", "").strip(),
        billing_tax=os.environ.get("BILLING_TAX", "").strip(),
        assistant_enabled=boolean("ASSISTANT_ENABLED", False),
        assistant_allowed_endpoints=tuple(
            value.strip() for value in os.environ.get("ASSISTANT_ALLOWED_ENDPOINTS", "").split(",")
            if value.strip()
        ),
        assistant_daily_request_limit=positive_int(
            "ASSISTANT_DAILY_REQUEST_LIMIT", DEFAULT_ASSISTANT_DAILY_REQUEST_LIMIT,
        ),
        operator_user_id=optional_uuid("OPERATOR_USER_ID"),
        legal_operator_name=os.environ.get("LEGAL_OPERATOR_NAME", "").strip(),
        legal_operator_email=os.environ.get("LEGAL_OPERATOR_EMAIL", "").strip(),
        release_build=os.environ.get("OMNICIO_RELEASE_BUILD", "").strip(),
    )
