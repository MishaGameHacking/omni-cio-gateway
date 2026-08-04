from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from omni_cio.contracts.v1.common import Completeness, DataQuality, QualityMetadata
from omni_cio.contracts.v1.fund_xray import (
    FundCompositionMode,
    FundCompositionV1,
    FundExposureDimension,
    FundHoldingV1,
    FundProfileV1,
)
from omni_cio.contracts.v1.investment_policy import AccountPolicyType
from omni_cio.contracts.v1.market import SourceAuthority
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
from omni_cio.funds import build_fund_xray


NOW = datetime(2026, 8, 4, 8, 0, tzinfo=timezone.utc)
UID = "fund-duration-credit"
IDENTITY = InstrumentIdentity(
    name="Mixed Bond Fund",
    instrument_type=InstrumentType.ETF,
    currency="RUB",
    lot=1,
    ticker="MIXB",
    class_code="TQTF",
    uid=UID,
)
TARGET = ResearchTargetV1(
    funnel_sha256="1" * 64,
    candidate_id=f"uid:{UID}",
    instrument_uid=UID,
    instrument_type=InstrumentType.ETF,
)


def _source() -> ResearchSourceV1:
    return ResearchSourceV1(
        provider="fund-manager-test",
        source_class=EvidenceSourceClass.OFFICIAL_DISCLOSURE,
        authority=SourceAuthority.OFFICIAL,
        source_id="fund-composition",
        retrieved_at=NOW,
    )


def _record(key: str, value: str):
    return make_evidence_record(
        instrument_uid=UID,
        fact_type=EvidenceFactType.MATERIAL_EVENT,
        fact_key=key,
        value=EvidenceValueV1(
            value_type=EvidenceValueType.TEXT,
            canonical_value=value,
        ),
        source=_source(),
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


def _universe() -> MarketUniverseSnapshotV1:
    row = UniverseInstrumentV1(
        source_operation=UniverseSourceOperation.ETFS,
        identity=IDENTITY,
        exchange="MOEX",
        real_exchange="REAL_EXCHANGE_MOEX",
        api_trade_available=True,
        buy_available=True,
        sell_available=True,
        for_iis=True,
        for_qual_investor=False,
        blocked_tca=False,
    )
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
        instruments=(row,),
        content_sha256="2" * 64,
        quality=QualityMetadata(
            quality=DataQuality.VERIFIED,
            completeness=Completeness.COMPLETE,
        ),
        decision_ready=True,
    )


def _profile(source_hash: str) -> FundProfileV1:
    return FundProfileV1(
        instrument=IDENTITY,
        manager="Manager One",
        benchmark="Mixed Bond Benchmark",
        strategy="Mixed bond/equity test strategy",
        constituent_count=2,
        as_of=NOW,
        source_record_sha256s=(source_hash,),
    )


def _holding(
    source_hash: str,
    *,
    key: str,
    weight: str,
    asset_class: str,
    duration_years: str | None,
    credit_quality: str | None,
) -> FundHoldingV1:
    return FundHoldingV1(
        holding_key=key,
        name=key,
        weight=Decimal(weight),
        instrument_uid=key,
        issuer_key=f"issuer:{key}",
        asset_class=asset_class,
        sector="mixed",
        currency="RUB",
        geography="RU",
        duration_years=(
            Decimal(duration_years) if duration_years is not None else None
        ),
        credit_quality=credit_quality,
        source_record_sha256s=(source_hash,),
    )


def test_credit_quality_unknown_and_duration_coverage_are_explicit() -> None:
    profile_record = _record("fund.profile", "profile")
    holdings_record = _record("fund.holdings", "holdings")
    dossier = _dossier(profile_record, holdings_record)
    composition = FundCompositionV1(
        mode=FundCompositionMode.FULL_HOLDINGS,
        as_of=NOW,
        holdings=(
            _holding(
                holdings_record.record_sha256,
                key="uid:bond-a",
                weight="0.60",
                asset_class="bond",
                duration_years="4.5",
                credit_quality="A+(RU)",
            ),
            _holding(
                holdings_record.record_sha256,
                key="uid:share-a",
                weight="0.40",
                asset_class="share",
                duration_years=None,
                credit_quality=None,
            ),
        ),
        reported_coverage_weight=Decimal("1"),
        source_record_sha256s=(holdings_record.record_sha256,),
    )

    result = build_fund_xray(
        dossier=dossier,
        universe=_universe(),
        profile=_profile(profile_record.record_sha256),
        composition=composition,
        assessed_at=NOW,
    )

    assert result.schema_version == "1.1"
    assert result.decision_ready is True
    assert result.duration is not None
    assert result.duration.weighted_duration_years == Decimal("4.5")
    assert result.duration.measured_weight == Decimal("0.60")
    credit = {
        row.bucket_key: row.weight
        for row in result.exposures
        if row.dimension is FundExposureDimension.CREDIT_QUALITY
    }
    assert credit == {
        "A+(RU)": Decimal("0.60"),
        "UNKNOWN": Decimal("0.40"),
    }


def test_partial_duration_and_credit_coverage_never_rescales_to_full_fund() -> None:
    profile_record = _record("fund.profile", "profile")
    holdings_record = _record("fund.holdings", "top holdings")
    dossier = _dossier(profile_record, holdings_record)
    bond = _holding(
        holdings_record.record_sha256,
        key="uid:bond-a",
        weight="0.30",
        asset_class="bond",
        duration_years="5",
        credit_quality="A(RU)",
    )
    share = _holding(
        holdings_record.record_sha256,
        key="uid:share-a",
        weight="0.20",
        asset_class="share",
        duration_years=None,
        credit_quality=None,
    )
    left = FundCompositionV1(
        mode=FundCompositionMode.PARTIAL_HOLDINGS,
        as_of=NOW,
        holdings=(bond, share),
        reported_coverage_weight=Decimal("0.50"),
        source_record_sha256s=(holdings_record.record_sha256,),
    )
    right = FundCompositionV1(
        mode=FundCompositionMode.PARTIAL_HOLDINGS,
        as_of=NOW,
        holdings=(share, bond),
        reported_coverage_weight=Decimal("0.50"),
        source_record_sha256s=(holdings_record.record_sha256,),
    )

    first = build_fund_xray(
        dossier=dossier,
        universe=_universe(),
        profile=_profile(profile_record.record_sha256),
        composition=left,
        assessed_at=NOW,
    )
    second = build_fund_xray(
        dossier=dossier,
        universe=_universe(),
        profile=_profile(profile_record.record_sha256),
        composition=right,
        assessed_at=NOW,
    )

    assert first.unknown_weight == Decimal("0.50")
    assert first.duration is not None
    assert first.duration.weighted_duration_years == Decimal("5")
    assert first.duration.measured_weight == Decimal("0.30")
    credit = {
        row.bucket_key: row.weight
        for row in first.exposures
        if row.dimension is FundExposureDimension.CREDIT_QUALITY
    }
    assert credit == {
        "A(RU)": Decimal("0.30"),
        "UNKNOWN": Decimal("0.70"),
    }
    assert first.xray_sha256 == second.xray_sha256
    assert first == second
