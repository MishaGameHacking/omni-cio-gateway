from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.market import SourceAuthority


UnitInterval = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("1"), allow_inf_nan=False),
]
NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]
QueryTerm = Annotated[str, Field(min_length=2, max_length=64)]


class NewsRetrievalStatus(StrEnum):
    READY = "ready"
    EMPTY = "empty"


class NewsRetrievalWarning(StrEnum):
    LEXICAL_ONLY_RETRIEVAL = "lexical_only_retrieval"
    SEMANTIC_RERANK_NOT_APPLIED = "semantic_rerank_not_applied"
    CONTEXT_ONLY_DOCUMENTS_EXCLUDED = "context_only_documents_excluded"
    REJECTED_DOCUMENTS_EXCLUDED = "rejected_documents_excluded"
    WRONG_INSTRUMENT_DOCUMENTS_EXCLUDED = "wrong_instrument_documents_excluded"
    UNTRUSTED_AUTHORITY_DOCUMENTS_EXCLUDED = (
        "untrusted_authority_documents_excluded"
    )
    FUTURE_DOCUMENTS_EXCLUDED = "future_documents_excluded"
    STALE_DOCUMENTS_EXCLUDED = "stale_documents_excluded"
    NO_QUERY_TERM_MATCH = "no_query_term_match"
    SINGLE_PUBLISHER_COVERAGE = "single_publisher_coverage"
    EVENT_CLUSTER_LIMIT_APPLIED = "event_cluster_limit_applied"


class NewsRetrievalPolicyV1(ContractModel):
    maximum_document_age_days: PositiveInt = 30
    future_tolerance_seconds: NonNegativeInt = 60
    chunk_max_chars: Annotated[int, Field(ge=256, le=4_000)] = 1_200
    chunk_overlap_chars: Annotated[int, Field(ge=0, le=1_000)] = 160
    maximum_results: Annotated[int, Field(ge=1, le=20)] = 8
    maximum_chunks_per_event_cluster: Annotated[int, Field(ge=1, le=5)] = 2
    trusted_authorities: tuple[SourceAuthority, ...] = (
        SourceAuthority.PRIMARY,
        SourceAuthority.OFFICIAL,
        SourceAuthority.REGULATED,
    )
    accepted_documents_only: Literal[True] = True
    facts_only: Literal[True] = True

    @model_validator(mode="after")
    def validate_policy(self) -> NewsRetrievalPolicyV1:
        if self.chunk_overlap_chars >= self.chunk_max_chars:
            raise ValueError("news chunk overlap must be below chunk size")
        if not self.trusted_authorities:
            raise ValueError("news retrieval policy requires trusted authorities")
        if len(set(self.trusted_authorities)) != len(self.trusted_authorities):
            raise ValueError("news retrieval trusted authorities must be unique")
        return self


class NewsRetrievalQueryV1(ContractModel):
    query_id: Annotated[str, Field(min_length=1, max_length=128)]
    instrument_key: Annotated[str, Field(min_length=3, max_length=256)]
    as_of: datetime
    terms: tuple[QueryTerm, ...]
    requested_results: Annotated[int, Field(ge=1, le=20)] = 8
    trading_methods: Literal[False] = False

    @field_validator("as_of")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("news retrieval as_of must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("terms")
    @classmethod
    def normalize_terms(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(" ".join(term.split()).casefold() for term in value)
        if not normalized:
            raise ValueError("news retrieval requires query terms")
        if any(not term for term in normalized):
            raise ValueError("news retrieval query terms cannot be empty")
        if len(set(normalized)) != len(normalized):
            raise ValueError("news retrieval query terms must be unique")
        return normalized


class NewsCitationV1(ContractModel):
    citation_id: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    occurrence_id: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    source_document_id: Annotated[str, Field(min_length=1, max_length=256)]
    event_cluster_id: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    publisher: Annotated[str, Field(min_length=1, max_length=128)]
    authority: SourceAuthority
    title: Annotated[str, Field(min_length=1, max_length=512)]
    published_at: datetime
    event_at: datetime | None
    retrieved_at: datetime
    chunk_index: NonNegativeInt
    char_start: NonNegativeInt
    char_end: PositiveInt
    excerpt: Annotated[str, Field(min_length=1, max_length=4_000)]

    @field_validator("published_at", "event_at", "retrieved_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("news citation timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_offsets(self) -> NewsCitationV1:
        if self.char_end <= self.char_start:
            raise ValueError("news citation end must exceed start")
        if self.char_end - self.char_start != len(self.excerpt):
            raise ValueError("news citation offsets do not match excerpt length")
        return self


class RetrievedNewsChunkV1(ContractModel):
    rank: PositiveInt
    total_score: UnitInterval
    term_coverage_score: UnitInterval
    authority_score: UnitInterval
    recency_score: UnitInterval
    matched_terms: tuple[QueryTerm, ...]
    citation: NewsCitationV1

    @model_validator(mode="after")
    def validate_score(self) -> RetrievedNewsChunkV1:
        expected = (
            self.term_coverage_score * Decimal("0.50")
            + self.authority_score * Decimal("0.30")
            + self.recency_score * Decimal("0.20")
        )
        if self.total_score != expected:
            raise ValueError("news retrieval total score does not reconcile")
        if not self.matched_terms:
            raise ValueError("retrieved news chunk requires a matched term")
        if len(set(self.matched_terms)) != len(self.matched_terms):
            raise ValueError("retrieved news matched terms must be unique")
        return self


class NewsRetrievalExclusionCountsV1(ContractModel):
    context_only: NonNegativeInt = 0
    rejected: NonNegativeInt = 0
    wrong_instrument: NonNegativeInt = 0
    untrusted_authority: NonNegativeInt = 0
    future: NonNegativeInt = 0
    stale: NonNegativeInt = 0
    no_term_match: NonNegativeInt = 0
    exact_duplicates: NonNegativeInt = 0

    @property
    def total(self) -> int:
        return (
            self.context_only
            + self.rejected
            + self.wrong_instrument
            + self.untrusted_authority
            + self.future
            + self.stale
            + self.no_term_match
            + self.exact_duplicates
        )


class NewsRetrievalResultV1(ContractModel):
    schema_name: Literal["news_retrieval_result"] = "news_retrieval_result"
    schema_version: Literal["1.0"] = "1.0"
    retrieved_at: datetime
    status: NewsRetrievalStatus
    retrieval_ready: bool
    query: NewsRetrievalQueryV1
    policy: NewsRetrievalPolicyV1
    input_document_count: NonNegativeInt
    canonical_document_count: NonNegativeInt
    eligible_document_count: NonNegativeInt
    eligible_chunk_count: NonNegativeInt
    returned_chunk_count: NonNegativeInt
    unique_event_cluster_count: NonNegativeInt
    unique_publisher_count: NonNegativeInt
    exclusions: NewsRetrievalExclusionCountsV1
    chunks: tuple[RetrievedNewsChunkV1, ...]
    warnings: tuple[NewsRetrievalWarning, ...] = ()
    accepted_documents_only: Literal[True] = True
    facts_only: Literal[True] = True
    source_text_treated_as_data: Literal[True] = True
    external_instructions_executed: Literal[False] = False
    raw_content_stored: Literal[False] = False
    no_price_forecast: Literal[True] = True
    no_investment_recommendation: Literal[True] = True
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("retrieved_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("news retrieval timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_result(self) -> NewsRetrievalResultV1:
        if self.returned_chunk_count != len(self.chunks):
            raise ValueError("returned news chunk count does not reconcile")
        if self.returned_chunk_count > self.eligible_chunk_count:
            raise ValueError("returned news chunks exceed eligible chunks")
        if self.input_document_count != (
            self.canonical_document_count + self.exclusions.exact_duplicates
        ):
            raise ValueError("news input, canonical and duplicate counts do not reconcile")
        if self.eligible_document_count > self.canonical_document_count:
            raise ValueError("eligible news documents exceed canonical documents")
        expected_ranks = tuple(range(1, len(self.chunks) + 1))
        if tuple(chunk.rank for chunk in self.chunks) != expected_ranks:
            raise ValueError("news retrieval ranks must be contiguous")
        cluster_count = len(
            {chunk.citation.event_cluster_id for chunk in self.chunks}
        )
        if self.unique_event_cluster_count != cluster_count:
            raise ValueError("news event cluster count does not reconcile")
        publisher_count = len(
            {chunk.citation.publisher.casefold() for chunk in self.chunks}
        )
        if self.unique_publisher_count != publisher_count:
            raise ValueError("news publisher count does not reconcile")
        expected_ready = bool(self.chunks)
        if self.retrieval_ready is not expected_ready:
            raise ValueError("news retrieval readiness is inconsistent")
        expected_status = (
            NewsRetrievalStatus.READY if expected_ready else NewsRetrievalStatus.EMPTY
        )
        if self.status is not expected_status:
            raise ValueError("news retrieval status is inconsistent")
        if len(set(self.warnings)) != len(self.warnings):
            raise ValueError("news retrieval warnings must be unique")
        return self
