from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib
from typing import Final


class IdentityProviderV1(StrEnum):
    TELEGRAM = "telegram"
    VK_ID = "vk_id"


class ProviderAvailabilityV1(StrEnum):
    NOT_CONFIGURED = "not_configured"
    PRIVATE_ACCEPTANCE = "private_acceptance"
    CONFIGURED = "configured"


@dataclass(frozen=True, slots=True)
class ProviderDescriptorV1:
    provider: IdentityProviderV1
    availability: ProviderAvailabilityV1

    @property
    def enabled(self) -> bool:
        return self.availability in {
            ProviderAvailabilityV1.PRIVATE_ACCEPTANCE,
            ProviderAvailabilityV1.CONFIGURED,
        }


@dataclass(frozen=True, slots=True)
class VerifiedExternalIdentityV1:
    """Server-verified identity proof stripped of profile authorization fields."""

    provider: IdentityProviderV1
    subject: str

    def __post_init__(self) -> None:
        if not self.subject or len(self.subject) > 256:
            raise ValueError("external identity subject is invalid")

    def binding_fingerprint_sha256(self) -> str:
        payload = f"{self.provider.value}:{self.subject}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


ORDINARY_LOGIN_PROVIDERS: Final[tuple[IdentityProviderV1, ...]] = (
    IdentityProviderV1.TELEGRAM,
)


def default_provider_descriptors() -> tuple[ProviderDescriptorV1, ...]:
    return tuple(
        ProviderDescriptorV1(
            provider=provider,
            availability=ProviderAvailabilityV1.NOT_CONFIGURED,
        )
        for provider in ORDINARY_LOGIN_PROVIDERS
    )
