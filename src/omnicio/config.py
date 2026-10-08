"""Application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from uuid import UUID


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


def positive_numeric_id(value: str) -> bool:
    return bool(1 <= len(value) <= 128 and value.isascii() and value.isdecimal()
                and value.strip("0"))


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
    vkid_flow_crypto_key: str
    vkid_app_id: str
    vkid_login_enabled: bool
    registration_enabled: bool
    registration_max_users: int
    privacy_version: str
    consent_version: str
    terms_version: str
    vkid_flow_ttl_seconds: int
    session_ttl_seconds: int
    portfolio_live_execution_enabled: bool
    portfolio_live_max_order_rub: int
    portfolio_live_max_daily_rub: int
    tid_client_id: str = ""
    tid_client_secret: str = ""
    tid_login_enabled: bool = False
    tid_pkce_enabled: bool = True
    assistant_base_url: str = ""
    assistant_api_key: str = ""
    assistant_model: str = ""
    notifications_enabled: bool = False
    notification_email_enabled: bool = False
    notification_crypto_key: str = ""
    notification_vapid_private_key: str = ""
    notification_vapid_subject: str = ""
    notification_smtp_host: str = ""
    notification_smtp_port: int = 465
    notification_smtp_username: str = ""
    notification_smtp_password: str = ""
    notification_smtp_sender: str = ""
    notification_smtp_mode: str = "tls"
    billing_enabled: bool = False
    billing_terminal_key: str = ""
    billing_password: str = ""
    billing_amount_kopecks: int = 0
    billing_period_days: int = 30
    billing_offer_version: str = ""
    billing_description: str = ""
    billing_taxation: str = ""
    billing_tax: str = ""
    assistant_enabled: bool = False
    assistant_allowed_endpoints: tuple[str, ...] = ()
    assistant_daily_request_limit: int = 30
    operator_user_id: UUID | None = None
    legal_operator_name: str = ""
    legal_operator_email: str = ""
    release_build: str = ""

    @property
    def vkid_ready(self) -> bool:
        return self.vkid_login_enabled and positive_numeric_id(self.vkid_app_id)

    @property
    def tid_ready(self) -> bool:
        return self.tid_login_enabled and bool(self.tid_client_id and self.tid_client_secret)

    @property
    def login_ready(self) -> bool:
        return self.vkid_ready or self.tid_ready

    @property
    def access_mode(self) -> str:
        return "limited_registration" if self.registration_enabled else "closed"


def load_settings() -> Settings:
    email_enabled = boolean("NOTIFICATION_EMAIL_ENABLED", False)
    live_max_order = positive_int("PORTFOLIO_LIVE_MAX_ORDER_RUB", 10_000)
    live_max_daily = positive_int("PORTFOLIO_LIVE_MAX_DAILY_RUB", 20_000)
    if live_max_daily < live_max_order:
        raise ConfigurationError(
            "PORTFOLIO_LIVE_MAX_DAILY_RUB must be >= PORTFOLIO_LIVE_MAX_ORDER_RUB"
        )
    return Settings(
        database_url=required("DATABASE_URL"),
        ip_key=required("CLIENT_IP_KEY"),
        broker_token_crypto_key=required("BROKER_TOKEN_CRYPTO_KEY"),
        vkid_flow_crypto_key=required("VKID_FLOW_CRYPTO_KEY"),
        vkid_app_id=os.environ.get("VKID_APP_ID", "").strip(),
        vkid_login_enabled=boolean("VKID_LOGIN_ENABLED", False),
        registration_enabled=boolean("REGISTRATION_ENABLED", False),
        registration_max_users=positive_int("REGISTRATION_MAX_USERS", 1),
        privacy_version=os.environ.get("LEGAL_PRIVACY_VERSION", "").strip(),
        consent_version=os.environ.get("LEGAL_CONSENT_VERSION", "").strip(),
        terms_version=os.environ.get("LEGAL_TERMS_VERSION", "").strip(),
        vkid_flow_ttl_seconds=positive_int("VKID_FLOW_TTL_SECONDS", 600),
        session_ttl_seconds=positive_int("SESSION_TTL_SECONDS", 34_560_000),
        portfolio_live_execution_enabled=boolean(
            "PORTFOLIO_LIVE_EXECUTION_ENABLED",
            False,
        ),
        portfolio_live_max_order_rub=live_max_order,
        portfolio_live_max_daily_rub=live_max_daily,
        tid_client_id=os.environ.get("TID_CLIENT_ID", "").strip(),
        tid_client_secret=os.environ.get("TID_CLIENT_SECRET", ""),
        tid_login_enabled=boolean("TID_LOGIN_ENABLED", False),
        tid_pkce_enabled=boolean("TID_PKCE_ENABLED", True),
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
        notification_smtp_port=(positive_int("NOTIFICATION_SMTP_PORT", 465)
                               if email_enabled else 465),
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
        billing_period_days=positive_int("BILLING_PERIOD_DAYS", 30),
        billing_offer_version=os.environ.get("BILLING_OFFER_VERSION", "").strip(),
        billing_description=os.environ.get("BILLING_DESCRIPTION", "").strip(),
        billing_taxation=os.environ.get("BILLING_TAXATION", "").strip(),
        billing_tax=os.environ.get("BILLING_TAX", "").strip(),
        assistant_enabled=boolean("ASSISTANT_ENABLED", False),
        assistant_allowed_endpoints=tuple(
            value.strip() for value in os.environ.get("ASSISTANT_ALLOWED_ENDPOINTS", "").split(",")
            if value.strip()
        ),
        assistant_daily_request_limit=positive_int("ASSISTANT_DAILY_REQUEST_LIMIT", 30),
        operator_user_id=optional_uuid("OPERATOR_USER_ID"),
        legal_operator_name=os.environ.get("LEGAL_OPERATOR_NAME", "").strip(),
        legal_operator_email=os.environ.get("LEGAL_OPERATOR_EMAIL", "").strip(),
        release_build=os.environ.get("OMNICIO_RELEASE_BUILD", "").strip(),
    )
