from __future__ import annotations

import pytest

from omni_cio.contracts.v1.candidate_funnel import (
    CandidateFunnelResultV1,
    CandidateKind,
    CandidateScoreV1,
)
from omni_cio.contracts.v1.market import SourceAuthority
from omni_cio.contracts.v1.portfolio import InstrumentType
from omni_cio.contracts.v1.research_evidence import (
    EvidenceSourceClass,
    ResearchSourceV1,
)
from omni_cio.research import ResearchTargetBindingError, bind_research_target



def _funnel(*, ready: bool = True) -> CandidateFunnelResultV1:
    candidate = CandidateScoreV1.model_construct(
        kind=CandidateKind.SECURITY,
        candidate_id="uid:instrument-1",
        instrument_uid="instrument-1",
        instrument_type=InstrumentType.SHARE,
    )
    return CandidateFunnelResultV1.model_construct(
        decision_ready=ready,
        funnel_sha256="f" * 64,
        research_shortlist=(candidate,),
    )


def _asset_source() -> ResearchSourceV1:
    from datetime import datetime, timezone

    return ResearchSourceV1(
        provider="T-Invest",
        source_class=EvidenceSourceClass.BROKER,
        authority=SourceAuthority.PRIMARY,
        source_id="GetAssetBy",
        retrieved_at=datetime(2026, 8, 3, 18, 0, tzinfo=timezone.utc),
    )


def test_binder_copies_exact_funnel_and_candidate_identity() -> None:
    target = bind_research_target(
        _funnel(),
        instrument_uid="instrument-1",
        asset_uid="asset-1",
        asset_uid_source=_asset_source(),
    )

    assert target.funnel_sha256 == "f" * 64
    assert target.candidate_id == "uid:instrument-1"
    assert target.instrument_uid == "instrument-1"
    assert target.instrument_type is InstrumentType.SHARE
    assert target.asset_uid == "asset-1"


def test_binder_rejects_candidate_outside_wp4_shortlist() -> None:
    with pytest.raises(ResearchTargetBindingError, match="NOT_IN_WP4_SHORTLIST"):
        bind_research_target(_funnel(), instrument_uid="other")


def test_binder_rejects_non_ready_funnel() -> None:
    with pytest.raises(ResearchTargetBindingError, match="FUNNEL_NOT_DECISION_READY"):
        bind_research_target(_funnel(ready=False), instrument_uid="instrument-1")
