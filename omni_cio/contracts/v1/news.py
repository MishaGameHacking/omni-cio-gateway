from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.market import SourceAuthority


class NewsContentFormat(StrEnum):
    PLAIN_TEXT = "plain_text"
    HTML = "html"


class NewsContentKind(StrEnum):
    FACT = "fact"
    OPINION = "opinion"
    FORECAST = "forecast"
    MIXED = "mixed"


class EntityResolutionStatus(StrEnum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"


class NewsDisposition(StrEnum):
    ACCEPTED = "accepted"
    CONTEXT_ONLY = "context_only"
    REJECTED = "rejected"


class InjectionFlag(StrEnum):
    SYSTEM_OVERRIDE = "system_override"
    TOOL_CALL = "tool_call"
    SECRET_REQUEST = "secret_request"
    CODE_EXECUTION = "code_execution"
    TRADING_INSTRUCTION = "trading_instruction"
    TRANSFER_OR_WITHDRAWAL = "transfer_or_withdrawal"
    HIDDEN_CONTENT = "hidden_content"
    SUSPICIOUS_UNICODE = "suspicious_unicode"
    OVERSIZED_CONTENT = "oversized_content"
    EMPTY_AFTER_SANITIZATION = "empty_after_sanitization"


class NewsDocumentInputV1(ContractModel):
    document_id: Annotated[str, Field(min_length=1, max_length=256)]
    publisher: Annotated[str, Field(min_length=1, max_length=128)]
    authority: SourceAuthority
    published_at: datetime
    retrieved_at: datetime
    title: Annotated[str, Field(min_length=1, max_length=512)]
    raw_content: Annotated[str, Field(min_length=1, max_length=1_000_000)]
    content_format: NewsContentFormat
    content_kind: NewsContentKind
    event_at: datetime | None = None
    entity_resolution: EntityResolutionStatus
    instrument_key: Annotated[str | None, Field(max_length=256)] = None
    source_record_id: Annotated[str | None, Field(max_length=256)] = None

    @field_validator("published_at", "retrieved_at", "event_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("news timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_entity_resolution(self) -> NewsDocumentInputV1:
        if (
            self.entity_resolution == EntityResolutionStatus.RESOLVED
            and not self.instrument_key
        ):
            raise ValueError("resolved entity requires instrument_key")
        if (
            self.entity_resolution != EntityResolutionStatus.RESOLVED
            and self.instrument_key is not None
        ):
            raise ValueError(
                "ambiguous/unresolved entity cannot claim instrument_key"
            )
        return self


class SanitizedNewsDocumentV1(ContractModel):
    occurrence_id: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    source_document_id: Annotated[str, Field(min_length=1, max_length=256)]
    publisher: Annotated[str, Field(min_length=1, max_length=128)]
    authority: SourceAuthority
    published_at: datetime
    retrieved_at: datetime
    event_at: datetime | None
    title: Annotated[str, Field(min_length=1, max_length=512)]
    sanitized_text: Annotated[str, Field(max_length=50_000)]
    content_kind: NewsContentKind
    entity_resolution: EntityResolutionStatus
    instrument_key: Annotated[str | None, Field(max_length=256)]
    disposition: NewsDisposition
    injection_flags: tuple[InjectionFlag, ...]
    content_fingerprint: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    event_cluster_id: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    truncated: bool
    raw_content_stored: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("published_at", "retrieved_at", "event_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("sanitized news timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_security_state(self) -> SanitizedNewsDocumentV1:
        if len(self.injection_flags) != len(set(self.injection_flags)):
            raise ValueError("injection flags must be unique")
        if (
            self.entity_resolution == EntityResolutionStatus.RESOLVED
            and not self.instrument_key
        ):
            raise ValueError("resolved entity requires instrument_key")
        if (
            self.entity_resolution != EntityResolutionStatus.RESOLVED
            and self.instrument_key is not None
        ):
            raise ValueError(
                "ambiguous/unresolved entity cannot claim instrument_key"
            )
        if self.disposition == NewsDisposition.ACCEPTED:
            if not self.sanitized_text:
                raise ValueError("accepted document requires text")
            if self.injection_flags:
                raise ValueError("accepted document cannot contain security flags")
            if self.entity_resolution != EntityResolutionStatus.RESOLVED:
                raise ValueError("accepted document requires resolved entity")
            if self.content_kind != NewsContentKind.FACT:
                raise ValueError("accepted document must be classified as fact")
            if self.authority not in (
                SourceAuthority.PRIMARY,
                SourceAuthority.OFFICIAL,
                SourceAuthority.REGULATED,
            ):
                raise ValueError("accepted document requires trusted authority")
        if self.disposition == NewsDisposition.REJECTED and not self.injection_flags:
            raise ValueError("rejected document requires a security flag")
        if self.truncated != (
            InjectionFlag.OVERSIZED_CONTENT in self.injection_flags
        ):
            raise ValueError("truncated must match oversized-content flag")
        return self


class DuplicateNewsOccurrenceV1(ContractModel):
    content_fingerprint: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    canonical_occurrence_id: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    duplicate_occurrence_id: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]

    @model_validator(mode="after")
    def validate_occurrences(self) -> DuplicateNewsOccurrenceV1:
        if self.canonical_occurrence_id == self.duplicate_occurrence_id:
            raise ValueError("duplicate occurrence must differ from canonical")
        return self


class NewsDeduplicationResultV1(ContractModel):
    canonical_documents: tuple[SanitizedNewsDocumentV1, ...]
    duplicates: tuple[DuplicateNewsOccurrenceV1, ...]
    input_count: Annotated[int, Field(ge=0)]
    canonical_count: Annotated[int, Field(ge=0)]
    duplicate_count: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def validate_counts(self) -> NewsDeduplicationResultV1:
        if self.canonical_count != len(self.canonical_documents):
            raise ValueError("canonical_count does not match documents")
        if self.duplicate_count != len(self.duplicates):
            raise ValueError("duplicate_count does not match duplicate rows")
        if self.input_count != self.canonical_count + self.duplicate_count:
            raise ValueError("deduplication counts do not reconcile")
        occurrence_ids = [
            document.occurrence_id for document in self.canonical_documents
        ]
        if len(occurrence_ids) != len(set(occurrence_ids)):
            raise ValueError("canonical occurrence IDs must be unique")
        return self
