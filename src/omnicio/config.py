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


def positive_numeric_id(value: str) -> bool:
    return value.isdigit() and int(value) > 0


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

    @property
    def vkid_ready(self) -> bool:
        return self.vkid_login_enabled and positive_numeric_id(self.vkid_app_id)

    @property
    def access_mode(self) -> str:
        return "limited_registration" if self.registration_enabled else "closed"


def load_settings() -> Settings:
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
    )
