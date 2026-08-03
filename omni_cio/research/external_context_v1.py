from __future__ import annotations

from omni_cio.contracts.v1.news import (
    EntityResolutionStatus,
    NewsDisposition,
    SanitizedNewsDocumentV1,
)
from omni_cio.contracts.v1.research_evidence import (
    EvidenceFactType,
    EvidenceSourceClass,
    EvidenceUse,
    EvidenceValueType,
    EvidenceValueV1,
    ResearchSourceV1,
    ResearchTargetV1,
    EvidenceRecordV1,
    make_evidence_record,
)


def context_record_from_sanitized_document(
    document: SanitizedNewsDocumentV1,
    *,
    target: ResearchTargetV1,
) -> EvidenceRecordV1 | None:
    """Convert already-sanitized external text into inert context, never a fact claim."""

    if document.disposition is NewsDisposition.REJECTED:
        return None
    if document.entity_resolution is not EntityResolutionStatus.RESOLVED:
        return None
    if document.instrument_key != f"uid:{target.instrument_uid}":
        return None
    if not document.sanitized_text:
        return None

    source = ResearchSourceV1(
        provider=document.publisher,
        source_class=EvidenceSourceClass.MEDIA_CONTEXT,
        authority=document.authority,
        source_id=document.source_document_id,
        retrieved_at=document.retrieved_at,
    )
    text = f"{document.title}\n{document.sanitized_text}".strip()
    return make_evidence_record(
        instrument_uid=target.instrument_uid,
        fact_type=EvidenceFactType.MATERIAL_EVENT,
        fact_key=f"context.document.{document.event_cluster_id[:32]}",
        value=EvidenceValueV1(
            value_type=EvidenceValueType.TEXT,
            canonical_value=text[:4096],
        ),
        source=source,
        use=EvidenceUse.CONTEXT_ONLY,
        source_record_id=document.occurrence_id,
        published_at=document.published_at,
        effective_at=document.event_at,
        material=False,
    )
