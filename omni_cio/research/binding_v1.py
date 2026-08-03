from __future__ import annotations

from omni_cio.contracts.v1.candidate_funnel import (
    CandidateFunnelResultV1,
    CandidateKind,
)
from omni_cio.contracts.v1.research_evidence import (
    ResearchSourceV1,
    ResearchTargetV1,
)


class ResearchTargetBindingError(ValueError):
    """The requested research target is not an exact WP4 shortlist candidate."""


def bind_research_target(
    funnel: CandidateFunnelResultV1,
    *,
    instrument_uid: str,
    asset_uid: str | None = None,
    asset_uid_source: ResearchSourceV1 | None = None,
) -> ResearchTargetV1:
    if not funnel.decision_ready:
        raise ResearchTargetBindingError("RESEARCH_FUNNEL_NOT_DECISION_READY")

    matches = [
        row
        for row in funnel.research_shortlist
        if row.kind is CandidateKind.SECURITY and row.instrument_uid == instrument_uid
    ]
    if len(matches) != 1:
        raise ResearchTargetBindingError("RESEARCH_TARGET_NOT_IN_WP4_SHORTLIST")

    candidate = matches[0]
    if candidate.instrument_type is None:
        raise ResearchTargetBindingError("RESEARCH_TARGET_INSTRUMENT_TYPE_MISSING")

    return ResearchTargetV1(
        funnel_sha256=funnel.funnel_sha256,
        candidate_id=candidate.candidate_id,
        instrument_uid=instrument_uid,
        instrument_type=candidate.instrument_type,
        asset_uid=asset_uid,
        asset_uid_source=asset_uid_source,
    )
