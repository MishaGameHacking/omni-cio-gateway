from __future__ import annotations

from datetime import datetime, timezone

import pytest

from omni_cio.contracts.v1.market import SourceAuthority
from omni_cio.contracts.v1.portfolio import InstrumentType
from omni_cio.contracts.v1.research_evidence import (
    EvidenceFactType,
    EvidenceSourceClass,
    EvidenceUse,
    EvidenceValueType,
    EvidenceValueV1,
    ResearchSourceV1,
    ResearchTargetV1,
)
from omni_cio.research import OfficialEvidenceError, official_evidence_record


NOW = datetime(2026, 8, 3, 18, 0, tzinfo=timezone.utc)
TARGET = ResearchTargetV1(
    funnel_sha256="a" * 64,
    candidate_id="uid:instrument-1",
    instrument_uid="instrument-1",
    instrument_type=InstrumentType.SHARE,
)


def _source(
    source_class: EvidenceSourceClass,
    authority: SourceAuthority,
) -> ResearchSourceV1:
    return ResearchSourceV1(
        provider="Official provider",
        source_class=source_class,
        authority=authority,
        source_id="official-record-1",
        retrieved_at=NOW,
    )


def test_regulator_fact_becomes_decision_grade_without_raw_document() -> None:
    record = official_evidence_record(
        target=TARGET,
        fact_type=EvidenceFactType.IDENTITY,
        fact_key="identity.issuer.registration",
        value=EvidenceValueV1(
            value_type=EvidenceValueType.TEXT,
            canonical_value="registered",
        ),
        source=_source(EvidenceSourceClass.REGULATOR, SourceAuthority.REGULATED),
        source_record_id="cbr-row-1",
        effective_at=NOW,
    )

    assert record.instrument_uid == "instrument-1"
    assert record.use is EvidenceUse.DECISION_GRADE
    assert record.source.source_class is EvidenceSourceClass.REGULATOR


def test_untrusted_or_media_source_cannot_use_official_normalizer() -> None:
    with pytest.raises(OfficialEvidenceError, match="SOURCE_NOT_TRUSTED"):
        official_evidence_record(
            target=TARGET,
            fact_type=EvidenceFactType.MATERIAL_EVENT,
            fact_key="material_event.example",
            value=EvidenceValueV1(
                value_type=EvidenceValueType.TEXT,
                canonical_value="event",
            ),
            source=_source(EvidenceSourceClass.ISSUER, SourceAuthority.SECONDARY),
        )

    with pytest.raises(OfficialEvidenceError, match="SOURCE_CLASS_INVALID"):
        official_evidence_record(
            target=TARGET,
            fact_type=EvidenceFactType.MATERIAL_EVENT,
            fact_key="material_event.example",
            value=EvidenceValueV1(
                value_type=EvidenceValueType.TEXT,
                canonical_value="event",
            ),
            source=_source(EvidenceSourceClass.MEDIA_CONTEXT, SourceAuthority.OFFICIAL),
        )
