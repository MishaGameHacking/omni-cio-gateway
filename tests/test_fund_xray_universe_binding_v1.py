from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from omni_cio.contracts.v1.common import Completeness, DataQuality, QualityMetadata
from omni_cio.contracts.v1.fund_xray import (
    FundBlockerCode,
    FundCompositionMode,
    FundCompositionV1,
    FundHoldingV1,
    FundProfileV1,
)
from omni_cio.contracts.v1.investment_policy import AccountPolicyType
from omni_cio.contracts.v1.portfolio import InstrumentIdentity, InstrumentType
from omni_cio.contracts.v1.research_evidence import (
    EvidenceFactType,
    EvidenceSourceClass,
    EvidenceUse,
    EvidenceValueType,
    EvidenceValueV1,
    ResearchDossierV1,
    ResearchSourceV1,
    ResearchTargetV1,
    make_evidence_record,
    research_dossier_sha256,
)
from omni_cio.contracts.v1.universe import (
    MarketUniverseSnapshotV1,
    UniverseAccountEligibilityV1,
    UniverseInstrumentV1,
    UniverseSourceOperation,
)
from omni_cio.contracts.v1.market import SourceAuthority
from omni_cio.funds import build_fund_xray


NOW = datetime(2026, 8, 4, 8, 0, tzinfo=timezone.utc)
UID = "fund-identity-1"
TARGET = ResearchTargetV1(
    funnel_sha256="1" * 64,
    candidate_id=f"uid:{UID}",
    instrument_uid=UID,
    instrument_type=InstrumentType.ETF,
)
PROFILE_IDENTITY = InstrumentIdentity(
    name="Identity Fund",
    instrument_type=InstrumentType.ETF,
    currency="RUB",
    lot=1,
    ticker="IDFUND",
    class_code="TQTF",
    uid=UID,
)


def _record(key: str):
    source = ResearchSourceV1(
        provider="official-fund-test",
        source_class=EvidenceSourceClass.OFFICIAL_DISCLOSURE,
        authority=SourceAuthority.OFFICIAL,
        source_id=f"source:{key}",
        retrieved_at=NOW,
    )
    return make_evidence_record(
        instrument_uid=UID,
        fact_type=EvidenceFactType.MATERIAL_EVENT,
        fact_key=key,
        value=EvidenceValueV1(
            value_type=EvidenceValueType.TEXT,
            canonical_value=key,
        ),
        source=source,
        use=EvidenceUse.DECISION_GRADE,
        published_at=NOW,
        effective_at=NOW,
    )


def _dossier(*records) -> ResearchDossierV1:
    values = {
        "schema_version": "1.0",
        "target": TARGET,
        "assessed_at": NOW,
        "requirements": (),
        "probes": (),
        "records": tuple(records),
        "contradictions": (),
        "coverage_gaps": (),
        "duplicate_records_removed": 0,
        "dossier_sha256": "0" * 64,
        "decision_ready": True,
        "strong_recommendation_allowed": True,
        "raw_content_stored": False,
        "trading_methods": False,
    }
    provisional = ResearchDossierV1.model_construct(**values)
    values["dossier_sha256"] = research_dossier_sha256(provisional)
    return ResearchDossierV1.model_validate(values)


def _universe(identity: InstrumentIdentity) -> MarketUniverseSnapshotV1:
    return MarketUniverseSnapshotV1(
        retrieved_at=NOW,
        account=UniverseAccountEligibilityV1(
            account_type=AccountPolicyType.BROKERAGE,
            qualified_investor=False,
        ),
        completed_operations=(
            UniverseSourceOperation.SHARES,
            UniverseSourceOperation.BONDS,
            UniverseSourceOperation.ETFS,
        ),
        instruments=(
            UniverseInstrumentV1(
                source_operation=UniverseSourceOperation.ETFS,
                identity=identity,
                exchange="MOEX",
                real_exchange="REAL_EXCHANGE_MOEX",
                api_trade_available=True,
                buy_available=True,
                sell_available=True,
                for_iis=True,
                for_qual_investor=False,
                blocked_tca=False,
            ),
        ),
        content_sha256="2" * 64,
        quality=QualityMetadata(
            quality=DataQuality.VERIFIED,
            completeness=Completeness.COMPLETE,
        ),
        decision_ready=True,
    )


def test_same_uid_with_different_currency_fails_exact_universe_binding() -> None:
    profile_record = _record("fund.profile")
    holdings_record = _record("fund.holdings")
    dossier = _dossier(profile_record, holdings_record)
    profile = FundProfileV1(
        instrument=PROFILE_IDENTITY,
        manager="Manager",
        as_of=NOW,
        source_record_sha256s=(profile_record.record_sha256,),
    )
    composition = FundCompositionV1(
        mode=FundCompositionMode.FULL_HOLDINGS,
        as_of=NOW,
        holdings=(
            FundHoldingV1(
                holding_key="uid:underlying-1",
                name="Underlying",
                weight=Decimal("1"),
                source_record_sha256s=(holdings_record.record_sha256,),
            ),
        ),
        reported_coverage_weight=Decimal("1"),
        source_record_sha256s=(holdings_record.record_sha256,),
    )
    conflicting_identity = PROFILE_IDENTITY.model_copy(update={"currency": "USD"})

    result = build_fund_xray(
        dossier=dossier,
        universe=_universe(conflicting_identity),
        profile=profile,
        composition=composition,
        assessed_at=NOW,
    )

    assert FundBlockerCode.UNIVERSE_BINDING_MISMATCH in result.blockers
    assert result.decision_ready is False
