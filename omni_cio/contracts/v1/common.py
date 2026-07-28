from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


SchemaVersion = Literal["1.0"]
CurrencyCode = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
FiniteDecimal = Annotated[Decimal, Field(allow_inf_nan=False)]


class ContractModel(BaseModel):
    """Strict, immutable base for externally exchanged contracts."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class DataQuality(StrEnum):
    VERIFIED = "verified"
    PARTIAL = "partial"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class Completeness(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    INCOMPLETE = "incomplete"


class IssueSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class AccountReference(ContractModel):
    masked_id: Annotated[str, Field(min_length=4, max_length=64)]
    account_type: Annotated[str | None, Field(max_length=64)] = None

    @field_validator("masked_id")
    @classmethod
    def require_masked_identifier(cls, value: str) -> str:
        mask_characters = {"*", "•", "…", "x", "X"}
        if not any(character in value for character in mask_characters):
            raise ValueError("account identifier must be masked")
        return value


class SourceReference(ContractModel):
    provider: Annotated[str, Field(min_length=1, max_length=128)]
    operation: Annotated[str, Field(min_length=1, max_length=128)]
    retrieved_at: datetime
    source_id: Annotated[str | None, Field(max_length=256)] = None

    @field_validator("retrieved_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("retrieved_at must be timezone-aware")
        return value.astimezone(timezone.utc)


class DataIssue(ContractModel):
    code: Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$")]
    severity: IssueSeverity
    message: Annotated[str, Field(min_length=1, max_length=512)]
    component: Annotated[str | None, Field(max_length=128)] = None


class QualityMetadata(ContractModel):
    quality: DataQuality
    completeness: Completeness
    issues: tuple[DataIssue, ...] = ()
    warnings: tuple[Annotated[str, Field(min_length=1, max_length=512)], ...] = ()


class ContractMetadata(ContractModel):
    schema_name: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.]{2,127}$")]
    schema_version: SchemaVersion = "1.0"
    retrieved_at: datetime
    account: AccountReference
    provenance: Annotated[tuple[SourceReference, ...], Field(min_length=1)]
    quality: QualityMetadata

    @field_validator("retrieved_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("retrieved_at must be timezone-aware")
        return value.astimezone(timezone.utc)


class Money(ContractModel):
    amount: FiniteDecimal
    currency: CurrencyCode

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value
