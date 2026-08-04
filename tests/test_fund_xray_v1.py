from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from omni_cio.contracts.v1.common import (
    Completeness,
    DataQuality,
    QualityMetadata,
)
from omni_cio.contracts.v1.fund_xray import (
    DirectUnderlyingExposureV1,
    FundBlockerCode,
    FundCompositionMode,
    FundCompositionV1,
    FundExposureBucketV1,
    FundExposureDimension,
    FundHoldingV1,
    FundOverlapKind,
    FundProfileV1,
    OtherFundCompositionV1,
)
from omni_cio.contracts.v1.investment_policy import AccountPolicyType
from omni_cio.contracts.v1.market import (
    MarketLiquidityV1,
    MarketSourceV1,
    SourceAuthority,
)
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
UID = "fund-1"
TARGET = ResearchTargetV1(
    funnel_sha256="1" * 64,
    candidate_id=f"uid:{UID}",
    instrument_uid=UID,
    instrument_type=InstrumentType.ETF,
)
IDENTITY = InstrumentIdentity(
    name="Fund One",
    instrument_type=InstrumentType.ETF,
    currency="RUB",
    lot=1,
    ticker="FUND",
    class_code="TQTF",
    uid=UID,
)


def _source(
    source_class: EvidenceSourceClass = EvidenceSourceClass.OFFICIAL_DISCLOSURE,
) -> ResearchSourceV1:
    return ResearchSourceV1(
        provider="fund-manager-test",
        source_class=source_class,
        authority=(
            SourceAuthority.OFFICIAL
            if source_class is not EvidenceSourceClass.MEDIA_CONTEXT
            else SourceAuthority.SECONDARY
        ),
        source_id=f"source:{source_class.value}",
        retrieved_at=NOW,
    )


def _record(
    key: str,
    value: str,
    *,
    source_class: EvidenceSourceClass = EvidenceSourceClass.OFFICIAL_DISCLOSURE,
    use: EvidenceUse = EvidenceUse.DECISION_GRADE,
):
    return make_evidence_record(
        instrument_uid=UID,
        fact_type=EvidenceFactType.MATERIAL_EVENT,
        fact_key=key,
        value=EvidenceValueV1(
            value_type=EvidenceValueType.TEXT,
            canonical_value=value,
        ),
        source=_source(source_class),
        use=use,
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
        benchmark="MOEX Test Index",
        strategy="Index tracking",
        constituent_count=2,
        expense_ratio_percent=Decimal("0.70"),
        tracking_error=Decimal("0.20"),
        as_of=NOW,
        source_record_sha256s=(source_hash,),
    )


def _holding(
    source_hash: str,
    key: str,
    weight: str,
    *,
    sector: str,
    currency: str,
    issuer: str,
    geography: str = "RU",
) -> FundHoldingV1:
    return FundHoldingV1(
        holding_key=key,
        name=key.upper(),
        weight=Decimal(weight),
        instrument_uid=key,
        issuer_key=issuer,
        asset_class="equity",
        sector=sector,
        currency=currency,
        geography=geography,
        source_record_sha256s=(source_hash,),
    )


def _liquidity() -> MarketLiquidityV1:
    source = MarketSourceV1(
        provider="T-Invest",
        authority=SourceAuthority.PRIMARY,
        retrieved_at=NOW,
        source_id="orderbook",
    )
    return MarketLiquidityV1(
        instrument_key=f"uid:{UID}",
        currency="RUB",
        as_of=NOW,
        source=source,
        best_bid=Decimal("99"),
        best_ask=Decimal("101"),
        spread_absolute=Decimal("2"),
        spread_bps=Decimal("200"),
    )


def test_full_holdings_produce_true_lookthrough_and_concentration() -> None:
    profile_record = _record("fund.profile", "profile")
    holdings_record = _record("fund.holdings", "holdings")
    dossier = _dossier(profile_record, holdings_record)
    composition = FundCompositionV1(
        mode=FundCompositionMode.FULL_HOLDINGS,
        as_of=NOW,
        holdings=(
            _holding(
                holdings_record.record_sha256,
                "uid:sber",
                "0.60",
                sector="financials",
                currency="RUB",
                issuer="issuer:sber",
            ),
            _holding(
                holdings_record.record_sha256,
                "uid:lukoil",
                "0.40",
                sector="energy",
                currency="RUB",
                issuer="issuer:lukoil",
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
        liquidity=_liquidity(),
        assessed_at=NOW,
    )

    assert result.decision_ready is True
    assert result.unknown_weight == 0
    assert result.concentration is not None
    assert result.concentration.top_1_weight == Decimal("0.60")
    assert result.concentration.top_5_weight == Decimal("1.00")
    assert result.concentration.hhi == Decimal("0.52")
    sector = {
        row.bucket_key: row.weight
        for row in result.exposures
        if row.dimension is FundExposureDimension.SECTOR
    }
    assert sector == {
        "energy": Decimal("0.40"),
        "financials": Decimal("0.60"),
    }


def test_partial_holdings_preserve_unknown_residual_without_rescaling() -> None:
    profile_record = _record("fund.profile", "profile")
    holdings_record = _record("fund.holdings", "top holdings")
    dossier = _dossier(profile_record, holdings_record)
    composition = FundCompositionV1(
        mode=FundCompositionMode.PARTIAL_HOLDINGS,
        as_of=NOW,
        holdings=(
            _holding(
                holdings_record.record_sha256,
                "uid:sber",
                "0.30",
                sector="financials",
                currency="RUB",
                issuer="issuer:sber",
            ),
            _holding(
                holdings_record.record_sha256,
                "uid:lukoil",
                "0.20",
                sector="energy",
                currency="RUB",
                issuer="issuer:lukoil",
            ),
        ),
        reported_coverage_weight=Decimal("0.50"),
        source_record_sha256s=(holdings_record.record_sha256,),
    )
    result = build_fund_xray(
        dossier=dossier,
        universe=_universe(),
        profile=_profile(profile_record.record_sha256),
        composition=composition,
        assessed_at=NOW,
    )

    assert result.decision_ready is True
    assert result.unknown_weight == Decimal("0.50")
    sector = {
        row.bucket_key: row.weight
        for row in result.exposures
        if row.dimension is FundExposureDimension.SECTOR
    }
    assert sector["financials"] == Decimal("0.30")
    assert sector["energy"] == Decimal("0.20")
    assert sector["UNKNOWN"] == Decimal("0.50")


def test_documented_buckets_preserve_dimension_specific_unknown() -> None:
    profile_record = _record("fund.profile", "profile")
    buckets_record = _record("fund.buckets", "buckets")
    dossier = _dossier(profile_record, buckets_record)
    composition = FundCompositionV1(
        mode=FundCompositionMode.DOCUMENTED_BUCKETS,
        as_of=NOW,
        documented_buckets=(
            FundExposureBucketV1(
                dimension=FundExposureDimension.SECTOR,
                bucket_key="financials",
                weight=Decimal("0.70"),
                source_record_sha256s=(buckets_record.record_sha256,),
            ),
            FundExposureBucketV1(
                dimension=FundExposureDimension.CURRENCY,
                bucket_key="RUB",
                weight=Decimal("0.90"),
                source_record_sha256s=(buckets_record.record_sha256,),
            ),
        ),
        reported_coverage_weight=Decimal("0.90"),
        source_record_sha256s=(buckets_record.record_sha256,),
    )
    result = build_fund_xray(
        dossier=dossier,
        universe=_universe(),
        profile=_profile(profile_record.record_sha256),
        composition=composition,
        assessed_at=NOW,
    )

    sector = {
        row.bucket_key: row.weight
        for row in result.exposures
        if row.dimension is FundExposureDimension.SECTOR
    }
    currency = {
        row.bucket_key: row.weight
        for row in result.exposures
        if row.dimension is FundExposureDimension.CURRENCY
    }
    assert sector == {
        "UNKNOWN": Decimal("0.30"),
        "financials": Decimal("0.70"),
    }
    assert currency == {"RUB": Decimal("0.90"), "UNKNOWN": Decimal("0.10")}
    assert result.concentration is None


def test_direct_and_fund_overlap_are_deterministic() -> None:
    profile_record = _record("fund.profile", "profile")
    holdings_record = _record("fund.holdings", "holdings")
    dossier = _dossier(profile_record, holdings_record)
    holdings = (
        _holding(
            holdings_record.record_sha256,
            "uid:sber",
            "0.60",
            sector="financials",
            currency="RUB",
            issuer="issuer:sber",
        ),
        _holding(
            holdings_record.record_sha256,
            "uid:lukoil",
            "0.40",
            sector="energy",
            currency="RUB",
            issuer="issuer:lukoil",
        ),
    )
    composition = FundCompositionV1(
        mode=FundCompositionMode.FULL_HOLDINGS,
        as_of=NOW,
        holdings=holdings,
        reported_coverage_weight=Decimal("1"),
        source_record_sha256s=(holdings_record.record_sha256,),
    )
    other = OtherFundCompositionV1(
        fund_key="uid:fund-2",
        holdings=(
            _holding(
                holdings_record.record_sha256,
                "uid:sber",
                "0.25",
                sector="financials",
                currency="RUB",
                issuer="issuer:sber",
            ),
            _holding(
                holdings_record.record_sha256,
                "uid:gazp",
                "0.75",
                sector="energy",
                currency="RUB",
                issuer="issuer:gazp",
            ),
        ),
    )
    result = build_fund_xray(
        dossier=dossier,
        universe=_universe(),
        profile=_profile(profile_record.record_sha256),
        composition=composition,
        direct_exposures=(
            DirectUnderlyingExposureV1(
                holding_key="uid:sber",
                portfolio_weight=Decimal("0.15"),
            ),
        ),
        other_funds=(other,),
        assessed_at=NOW,
    )

    overlaps = {(row.kind, row.counterpart_key): row for row in result.overlaps}
    direct = overlaps[(FundOverlapKind.DIRECT_HOLDINGS, "portfolio:direct")]
    fund = overlaps[(FundOverlapKind.OTHER_FUND, "uid:fund-2")]
    assert direct.overlap_weight == Decimal("0.60")
    assert direct.shared_holding_keys == ("uid:sber",)
    assert fund.overlap_weight == Decimal("0.25")
    assert fund.shared_holding_keys == ("uid:sber",)


def test_stale_composition_blocks_decision_ready_state() -> None:
    profile_record = _record("fund.profile", "profile")
    holdings_record = _record("fund.holdings", "holdings")
    dossier = _dossier(profile_record, holdings_record)
    composition = FundCompositionV1(
        mode=FundCompositionMode.FULL_HOLDINGS,
        as_of=NOW - timedelta(days=8),
        holdings=(
            _holding(
                holdings_record.record_sha256,
                "uid:sber",
                "1",
                sector="financials",
                currency="RUB",
                issuer="issuer:sber",
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

    assert FundBlockerCode.COMPOSITION_STALE in result.blockers
    assert result.decision_ready is False


def test_unavailable_composition_stays_explicit_and_unknown() -> None:
    profile_record = _record("fund.profile", "profile")
    dossier = _dossier(profile_record)
    result = build_fund_xray(
        dossier=dossier,
        universe=_universe(),
        profile=_profile(profile_record.record_sha256),
        composition=FundCompositionV1(mode=FundCompositionMode.UNAVAILABLE),
        assessed_at=NOW,
    )

    assert FundBlockerCode.COMPOSITION_MISSING in result.blockers
    assert result.unknown_weight == Decimal("1")
    assert result.exposures == ()
    assert result.concentration is None


def test_missing_or_context_only_provenance_fails_closed() -> None:
    profile_record = _record("fund.profile", "profile")
    holdings_record = _record(
        "fund.holdings.context",
        "rumor",
        source_class=EvidenceSourceClass.MEDIA_CONTEXT,
        use=EvidenceUse.CONTEXT_ONLY,
    )
    dossier = _dossier(profile_record, holdings_record)
    composition = FundCompositionV1(
        mode=FundCompositionMode.FULL_HOLDINGS,
        as_of=NOW,
        holdings=(
            _holding(
                holdings_record.record_sha256,
                "uid:sber",
                "1",
                sector="financials",
                currency="RUB",
                issuer="issuer:sber",
            ),
        ),
        reported_coverage_weight=Decimal("1"),
        source_record_sha256s=(holdings_record.record_sha256,),
    )
    context_result = build_fund_xray(
        dossier=dossier,
        universe=_universe(),
        profile=_profile(profile_record.record_sha256),
        composition=composition,
        assessed_at=NOW,
    )
    missing_result = build_fund_xray(
        dossier=_dossier(profile_record),
        universe=_universe(),
        profile=_profile(profile_record.record_sha256),
        composition=composition,
        assessed_at=NOW,
    )

    assert FundBlockerCode.SOURCE_NOT_DECISION_GRADE in context_result.blockers
    assert FundBlockerCode.SOURCE_PROVENANCE_MISSING in missing_result.blockers


def test_source_order_does_not_change_xray_fingerprint() -> None:
    profile_record = _record("fund.profile", "profile")
    holdings_record = _record("fund.holdings", "holdings")
    dossier = _dossier(profile_record, holdings_record)
    first = _holding(
        holdings_record.record_sha256,
        "uid:sber",
        "0.60",
        sector="financials",
        currency="RUB",
        issuer="issuer:sber",
    )
    second = _holding(
        holdings_record.record_sha256,
        "uid:lukoil",
        "0.40",
        sector="energy",
        currency="RUB",
        issuer="issuer:lukoil",
    )
    left = build_fund_xray(
        dossier=dossier,
        universe=_universe(),
        profile=_profile(profile_record.record_sha256),
        composition=FundCompositionV1(
            mode=FundCompositionMode.FULL_HOLDINGS,
            as_of=NOW,
            holdings=(first, second),
            reported_coverage_weight=Decimal("1"),
            source_record_sha256s=(holdings_record.record_sha256,),
        ),
        assessed_at=NOW,
    )
    right = build_fund_xray(
        dossier=dossier,
        universe=_universe(),
        profile=_profile(profile_record.record_sha256),
        composition=FundCompositionV1(
            mode=FundCompositionMode.FULL_HOLDINGS,
            as_of=NOW,
            holdings=(second, first),
            reported_coverage_weight=Decimal("1"),
            source_record_sha256s=(holdings_record.record_sha256,),
        ),
        assessed_at=NOW,
    )

    assert left.xray_sha256 == right.xray_sha256
    assert left.exposures == right.exposures
    assert left.composition.holdings == right.composition.holdings
