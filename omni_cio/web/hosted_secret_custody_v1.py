from __future__ import annotations

from dataclasses import dataclass
import re
import secrets
from typing import Protocol


_TENANT_ID_RE = re.compile(r"^tenant:v1:[a-z0-9][a-z0-9_-]{2,63}$")
_HOSTED_SECRET_REF_RE = re.compile(r"^hosted-read:v1:[a-f0-9]{64}$")
_RESERVED_OWNER_TENANT_ID = "tenant:v1:owner"


class HostedReadSecretCustodyError(RuntimeError):
    """Fail-closed error for tenant-scoped hosted READ credential custody."""


@dataclass(frozen=True, slots=True)
class HostedReadSecretDescriptorV1:
    tenant_id: str
    secret_ref: str
    purpose: str = "broker_read"

    def __post_init__(self) -> None:
        validate_hosted_read_secret_scope(
            tenant_id=self.tenant_id,
            secret_ref=self.secret_ref,
        )
        if self.purpose != "broker_read":
            raise HostedReadSecretCustodyError("HOSTED_SECRET_PURPOSE_INVALID")


class HostedReadSecretBackendV1(Protocol):
    """Provider-backed encryption boundary for hosted tenant READ credentials.

    Implementations own encryption-at-rest, key access and ciphertext persistence.
    Callers pass the authenticated tenant scope on every operation. Implementations
    must reject cross-tenant access and must never return ciphertext/plaintext to
    browser-facing callers or persist plaintext outside process memory.
    """

    def store(
        self,
        *,
        tenant_id: str,
        secret_ref: str,
        plaintext: bytes,
    ) -> None: ...

    def load(self, *, tenant_id: str, secret_ref: str) -> bytes: ...

    def revoke(self, *, tenant_id: str, secret_ref: str) -> bool: ...


def new_hosted_read_secret_ref() -> str:
    return f"hosted-read:v1:{secrets.token_hex(32)}"


def validate_hosted_read_secret_scope(*, tenant_id: str, secret_ref: str) -> None:
    if _TENANT_ID_RE.fullmatch(tenant_id) is None:
        raise HostedReadSecretCustodyError("HOSTED_SECRET_TENANT_INVALID")
    if tenant_id == _RESERVED_OWNER_TENANT_ID:
        raise HostedReadSecretCustodyError("HOSTED_SECRET_TENANT_RESERVED")
    if _HOSTED_SECRET_REF_RE.fullmatch(secret_ref) is None:
        raise HostedReadSecretCustodyError("HOSTED_SECRET_REF_INVALID")
