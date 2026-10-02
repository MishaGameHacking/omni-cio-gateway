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
    owner_vk_id: str
    vkid_login_enabled: bool
    registration_enabled: bool
    privacy_version: str
    consent_version: str
    terms_version: str
    vkid_flow_ttl_seconds: int
    session_ttl_seconds: int

    @property
    def vkid_ready(self) -> bool:
        owner_requirement_met = (
            self.registration_enabled
            or positive_numeric_id(self.owner_vk_id)
        )
        return (
            self.vkid_login_enabled
            and positive_numeric_id(self.vkid_app_id)
            and owner_requirement_met
        )

    @property
    def access_mode(self) -> str:
        return "open" if self.registration_enabled else "owner_only"


def load_settings() -> Settings:
    return Settings(
        database_url=required("DATABASE_URL"),
        ip_key=required("CLIENT_IP_KEY"),
        broker_token_crypto_key=required("BROKER_TOKEN_CRYPTO_KEY"),
        vkid_flow_crypto_key=required("VKID_FLOW_CRYPTO_KEY"),
        vkid_app_id=os.environ.get("VKID_APP_ID", "").strip(),
        owner_vk_id=os.environ.get("OWNER_VK_ID", "").strip(),
        vkid_login_enabled=boolean("VKID_LOGIN_ENABLED", False),
        registration_enabled=boolean("REGISTRATION_ENABLED", False),
        privacy_version=os.environ.get("LEGAL_PRIVACY_VERSION", "").strip(),
        consent_version=os.environ.get("LEGAL_CONSENT_VERSION", "").strip(),
        terms_version=os.environ.get("LEGAL_TERMS_VERSION", "").strip(),
        vkid_flow_ttl_seconds=positive_int("VKID_FLOW_TTL_SECONDS", 600),
        session_ttl_seconds=positive_int("SESSION_TTL_SECONDS", 34_560_000),
    )
