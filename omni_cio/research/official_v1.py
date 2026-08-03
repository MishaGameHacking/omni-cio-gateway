from __future__ import annotations

from datetime import datetime

from omni_cio.contracts.v1.market import SourceAuthority
from omni_cio.contracts.v1.research_evidence import (
    EvidenceFactType,
    EvidenceRecordV1,
    EvidenceSourceClass,
    EvidenceUse,
    EvidenceValueV1,
    ResearchSourceV1,
    ResearchTargetV1,
    make_evidence_record,
)


_ALLOWED_OFFICIAL_CLASSES = {
    EvidenceSourceClass.EXCHANGE,
    EvidenceSourceClass.ISSUER,
    EvidenceSourceClass.OFFICIAL_DISCLOSURE,
    EvidenceSourceClass.REGULATOR,
    EvidenceSourceClass.RATING_AGENCY,
}
_TRUSTED_AUTHORITIES = {
    SourceAuthority.PRIMARY,
    SourceAuthority.OFFICIAL,
    SourceAuthority.REGULATED,
}


class OfficialEvidenceError(ValueError):
    """Typed official evidence has invalid provenance or target identity."""


def official_evidence_record(
    *,
    target: ResearchTargetV1,
    fact_type: EvidenceFactType,
    fact_key: str,
    value: EvidenceValueV1,
    source: ResearchSourceV1,
    source_record_id: str | None = None,
    published_at: datetime | None = None,
    effective_at: datetime | None = None,
    material: bool = True,
) -> EvidenceRecordV1:
    """Normalize already-extracted official facts without persisting raw documents."""

    if source.source_class not in _ALLOWED_OFFICIAL_CLASSES:
        raise OfficialEvidenceError("OFFICIAL_EVIDENCE_SOURCE_CLASS_INVALID")
    if source.authority not in _TRUSTED_AUTHORITIES:
        raise OfficialEvidenceError("OFFICIAL_EVIDENCE_SOURCE_NOT_TRUSTED")

    return make_evidence_record(
        instrument_uid=target.instrument_uid,
        fact_type=fact_type,
        fact_key=fact_key,
        value=value,
        source=source,
        use=EvidenceUse.DECISION_GRADE,
        source_record_id=source_record_id,
        published_at=published_at,
        effective_at=effective_at,
        material=material,
    )
