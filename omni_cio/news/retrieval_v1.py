from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import hashlib

from omni_cio.contracts.v1.market import SourceAuthority
from omni_cio.contracts.v1.news import (
    NewsDisposition,
    SanitizedNewsDocumentV1,
)
from omni_cio.contracts.v1.news_retrieval import (
    NewsCitationV1,
    NewsRetrievalExclusionCountsV1,
    NewsRetrievalPolicyV1,
    NewsRetrievalQueryV1,
    NewsRetrievalResultV1,
    NewsRetrievalStatus,
    NewsRetrievalWarning,
    RetrievedNewsChunkV1,
)
from omni_cio.news.pipeline_v1 import deduplicate_news_documents


_SECONDS_PER_DAY = Decimal("86400")
_AUTHORITY_SCORES = {
    SourceAuthority.PRIMARY: Decimal("1.00"),
    SourceAuthority.OFFICIAL: Decimal("0.90"),
    SourceAuthority.REGULATED: Decimal("0.80"),
}


class NewsRetrievalError(ValueError):
    """The supplied retrieval request cannot be processed safely."""


@dataclass(frozen=True)
class _Candidate:
    document: SanitizedNewsDocumentV1
    chunk_index: int
    char_start: int
    char_end: int
    excerpt: str
    matched_terms: tuple[str, ...]
    term_coverage_score: Decimal
    authority_score: Decimal
    recency_score: Decimal
    total_score: Decimal
    citation_id: str


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise NewsRetrievalError("NEWS_RETRIEVAL_TIMESTAMP_MUST_BE_AWARE")
    return result.astimezone(timezone.utc)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _append_unique[T](target: list[T], value: T) -> None:
    if value not in target:
        target.append(value)


def _chunk_text(
    text: str,
    *,
    maximum_chars: int,
    overlap_chars: int,
) -> tuple[tuple[int, int, str], ...]:
    chunks: list[tuple[int, int, str]] = []
    cursor = 0
    text_length = len(text)
    while cursor < text_length:
        start = cursor
        while start < text_length and text[start].isspace():
            start += 1
        if start >= text_length:
            break

        limit = min(start + maximum_chars, text_length)
        end = limit
        if limit < text_length:
            boundary = text.rfind(" ", start + maximum_chars // 2, limit)
            if boundary > start:
                end = boundary
        while end > start and text[end - 1].isspace():
            end -= 1
        if end <= start:
            end = limit
        excerpt = text[start:end]
        chunks.append((start, end, excerpt))
        if end >= text_length:
            break

        next_cursor = max(start + 1, end - overlap_chars)
        if (
            next_cursor > 0
            and next_cursor < text_length
            and not text[next_cursor - 1].isspace()
            and not text[next_cursor].isspace()
        ):
            prior_boundary = text.rfind(" ", start + 1, next_cursor)
            if prior_boundary > start:
                next_cursor = prior_boundary + 1
        cursor = next_cursor
    return tuple(chunks)


def _recency_score(
    event_time: datetime,
    *,
    as_of: datetime,
    maximum_age_days: int,
) -> Decimal:
    age_seconds = max(
        Decimal("0"),
        Decimal(str((as_of - event_time).total_seconds())),
    )
    maximum_seconds = Decimal(maximum_age_days) * _SECONDS_PER_DAY
    return max(Decimal("0"), Decimal("1") - age_seconds / maximum_seconds)


def _candidate_sort_key(candidate: _Candidate) -> tuple[object, ...]:
    event_time = candidate.document.event_at or candidate.document.published_at
    return (
        -candidate.total_score,
        -candidate.term_coverage_score,
        -candidate.authority_score,
        -candidate.recency_score,
        -event_time.timestamp(),
        candidate.citation_id,
    )


def retrieve_safe_news_chunks(
    documents: Iterable[SanitizedNewsDocumentV1],
    query: NewsRetrievalQueryV1,
    *,
    policy: NewsRetrievalPolicyV1 | None = None,
    retrieved_at: datetime | None = None,
) -> NewsRetrievalResultV1:
    """Retrieve citation-backed factual chunks without executing source instructions."""

    active_policy = policy or NewsRetrievalPolicyV1()
    evaluation_time = _aware_utc(retrieved_at)
    rows = tuple(documents)
    deduplicated = deduplicate_news_documents(rows)

    context_only_count = 0
    rejected_count = 0
    wrong_instrument_count = 0
    untrusted_authority_count = 0
    future_count = 0
    stale_count = 0
    no_term_match_count = 0
    eligible_document_count = 0
    candidates: list[_Candidate] = []

    maximum_age_seconds = (
        active_policy.maximum_document_age_days * 24 * 60 * 60
    )
    for document in deduplicated.canonical_documents:
        if document.disposition is NewsDisposition.CONTEXT_ONLY:
            context_only_count += 1
            continue
        if document.disposition is NewsDisposition.REJECTED:
            rejected_count += 1
            continue
        if document.instrument_key != query.instrument_key:
            wrong_instrument_count += 1
            continue
        if document.authority not in active_policy.trusted_authorities:
            untrusted_authority_count += 1
            continue

        event_time = document.event_at or document.published_at
        age_seconds = (query.as_of - event_time).total_seconds()
        if age_seconds < -active_policy.future_tolerance_seconds:
            future_count += 1
            continue
        if age_seconds > maximum_age_seconds:
            stale_count += 1
            continue

        eligible_document_count += 1
        document_matched = False
        for chunk_index, (char_start, char_end, excerpt) in enumerate(
            _chunk_text(
                document.sanitized_text,
                maximum_chars=active_policy.chunk_max_chars,
                overlap_chars=active_policy.chunk_overlap_chars,
            )
        ):
            normalized_excerpt = excerpt.casefold()
            matched_terms = tuple(
                term for term in query.terms if term in normalized_excerpt
            )
            if not matched_terms:
                continue
            document_matched = True
            term_coverage_score = Decimal(len(matched_terms)) / Decimal(
                len(query.terms)
            )
            authority_score = _AUTHORITY_SCORES[document.authority]
            recency_score = _recency_score(
                event_time,
                as_of=query.as_of,
                maximum_age_days=active_policy.maximum_document_age_days,
            )
            total_score = (
                term_coverage_score * Decimal("0.50")
                + authority_score * Decimal("0.30")
                + recency_score * Decimal("0.20")
            )
            citation_id = _sha256(
                "|".join(
                    (
                        document.occurrence_id,
                        str(chunk_index),
                        str(char_start),
                        str(char_end),
                    )
                )
            )
            candidates.append(
                _Candidate(
                    document=document,
                    chunk_index=chunk_index,
                    char_start=char_start,
                    char_end=char_end,
                    excerpt=excerpt,
                    matched_terms=matched_terms,
                    term_coverage_score=term_coverage_score,
                    authority_score=authority_score,
                    recency_score=recency_score,
                    total_score=total_score,
                    citation_id=citation_id,
                )
            )
        if not document_matched:
            no_term_match_count += 1

    ordered = sorted(candidates, key=_candidate_sort_key)
    result_limit = min(
        query.requested_results,
        active_policy.maximum_results,
    )
    selected: list[_Candidate] = []
    cluster_counts: dict[str, int] = {}
    cluster_limit_applied = False
    for candidate in ordered:
        cluster_id = candidate.document.event_cluster_id
        current_count = cluster_counts.get(cluster_id, 0)
        if current_count >= active_policy.maximum_chunks_per_event_cluster:
            cluster_limit_applied = True
            continue
        selected.append(candidate)
        cluster_counts[cluster_id] = current_count + 1
        if len(selected) >= result_limit:
            break

    chunks: list[RetrievedNewsChunkV1] = []
    for rank, candidate in enumerate(selected, start=1):
        document = candidate.document
        chunks.append(
            RetrievedNewsChunkV1(
                rank=rank,
                total_score=candidate.total_score,
                term_coverage_score=candidate.term_coverage_score,
                authority_score=candidate.authority_score,
                recency_score=candidate.recency_score,
                matched_terms=candidate.matched_terms,
                citation=NewsCitationV1(
                    citation_id=candidate.citation_id,
                    occurrence_id=document.occurrence_id,
                    source_document_id=document.source_document_id,
                    event_cluster_id=document.event_cluster_id,
                    publisher=document.publisher,
                    authority=document.authority,
                    title=document.title,
                    published_at=document.published_at,
                    event_at=document.event_at,
                    retrieved_at=document.retrieved_at,
                    chunk_index=candidate.chunk_index,
                    char_start=candidate.char_start,
                    char_end=candidate.char_end,
                    excerpt=candidate.excerpt,
                ),
            )
        )

    exclusions = NewsRetrievalExclusionCountsV1(
        context_only=context_only_count,
        rejected=rejected_count,
        wrong_instrument=wrong_instrument_count,
        untrusted_authority=untrusted_authority_count,
        future=future_count,
        stale=stale_count,
        no_term_match=no_term_match_count,
        exact_duplicates=deduplicated.duplicate_count,
    )
    warnings: list[NewsRetrievalWarning] = [
        NewsRetrievalWarning.LEXICAL_ONLY_RETRIEVAL,
        NewsRetrievalWarning.SEMANTIC_RERANK_NOT_APPLIED,
    ]
    warning_conditions = (
        (
            context_only_count > 0,
            NewsRetrievalWarning.CONTEXT_ONLY_DOCUMENTS_EXCLUDED,
        ),
        (rejected_count > 0, NewsRetrievalWarning.REJECTED_DOCUMENTS_EXCLUDED),
        (
            wrong_instrument_count > 0,
            NewsRetrievalWarning.WRONG_INSTRUMENT_DOCUMENTS_EXCLUDED,
        ),
        (
            untrusted_authority_count > 0,
            NewsRetrievalWarning.UNTRUSTED_AUTHORITY_DOCUMENTS_EXCLUDED,
        ),
        (future_count > 0, NewsRetrievalWarning.FUTURE_DOCUMENTS_EXCLUDED),
        (stale_count > 0, NewsRetrievalWarning.STALE_DOCUMENTS_EXCLUDED),
        (no_term_match_count > 0, NewsRetrievalWarning.NO_QUERY_TERM_MATCH),
        (cluster_limit_applied, NewsRetrievalWarning.EVENT_CLUSTER_LIMIT_APPLIED),
    )
    for condition, warning in warning_conditions:
        if condition:
            _append_unique(warnings, warning)

    unique_publishers = {chunk.citation.publisher.casefold() for chunk in chunks}
    if chunks and len(unique_publishers) == 1:
        _append_unique(warnings, NewsRetrievalWarning.SINGLE_PUBLISHER_COVERAGE)

    retrieval_ready = bool(chunks)
    status = (
        NewsRetrievalStatus.READY if retrieval_ready else NewsRetrievalStatus.EMPTY
    )
    return NewsRetrievalResultV1(
        retrieved_at=evaluation_time,
        status=status,
        retrieval_ready=retrieval_ready,
        query=query,
        policy=active_policy,
        input_document_count=len(rows),
        canonical_document_count=deduplicated.canonical_count,
        eligible_document_count=eligible_document_count,
        eligible_chunk_count=len(candidates),
        returned_chunk_count=len(chunks),
        unique_event_cluster_count=len(
            {chunk.citation.event_cluster_id for chunk in chunks}
        ),
        unique_publisher_count=len(unique_publishers),
        exclusions=exclusions,
        chunks=tuple(chunks),
        warnings=tuple(warnings),
    )
