from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from omni_cio.contracts.v1.common import Completeness, DataQuality, QualityMetadata
from omni_cio.contracts.v1.fund_xray import (
    FundBlockerCode,
    FundCompositionMode,
    FundCompositionV1,
    FundExposureBucketV1,
    FundExposureDimension,
    FundHoldingV1,
    FundProfileV1,
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


def _dossier(*records, target: ResearchTargetV1 = TARGET) -> ResearchDossierV1:
    values = {
        "schema_version": "1.0",
        "target": target,
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


def _universe(*, uid: str = UID, ready: bool = True) -> MarketUniverseSnapshotV1:
    identity = IDENTITY.model_copy(update={"uid": uid})
    row = UniverseInstrumentV1(
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
            quality=(DataQuality.VERIFIED if ready else DataQuality.DEGRADED),
            completeness=(Completeness.COMPLETE if ready else Completeness.PARTIAL),
        ),
        decision_ready=ready,
    )


def _profile(source_hash: str) -> FundProfileV1:
    return FundProfileV1(
        instrument=IDENTITY,
        manager="Manager One",
        benchmark="Index One",
        expense_ratio_percent=Decimal("0.50"),
        as_of=NOW,
        source_record_sha256s=(source_hash,),
    )


def _holding(source_hash: str, key: str, weight: str) -> FundHoldingV1:
    return FundHoldingV1(
        holding_key=key,
        name=key,
        weight=Decimal(weight),
        source_record_sha256s=(source_hash,),
    )


def _full_composition(source_hash: str) -> FundCompositionV1:
    return FundCompositionV1(
        mode=FundCompositionMode.FULL_HOLDINGS,
        as_of=NOW,
        holdings=(_holding(source_hash, "uid:sber", "1"),),
        reported_coverage_weight=Decimal("1"),
        source_record_sha256s=(source_hash,),
    )


def test_holding_weights_above_100_percent_are_rejected() -> None:
    with pytest.raises(ValueError, match="cannot exceed 100%"):
        FundCompositionV1(
            mode=FundCompositionMode.PARTIAL_HOLDINGS,
            as_of=NOW,
            holdings=(
                _holding("a" * 64, "uid:a", "0.60"),
                _holding("a" * 64, "uid:b", "0.50"),
            ),
            reported_coverage_weight=Decimal("1"),
            source_record_sha256s=("a" * 64,),
        )


def test_full_holdings_must_reconcile_to_100_percent() -> None:
    with pytest.raises(ValueError, match="full holdings must reconcile"):
        FundCompositionV1(
            mode=FundCompositionMode.FULL_HOLDINGS,
            as_of=NOW,
            holdings=(_holding("a" * 64, "uid:a", "0.99"),),
            reported_coverage_weight=Decimal("0.99"),
            source_record_sha256s=("a" * 64,),
        )


def test_documented_dimension_above_100_percent_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot exceed 100%"):
        FundCompositionV1(
            mode=FundCompositionMode.DOCUMENTED_BUCKETS,
            as_of=NOW,
            documented_buckets=(
                FundExposureBucketV1(
                    dimension=FundExposureDimension.SECTOR,
                    bucket_key="financials",
                    weight=Decimal("0.70"),
                    source_record_sha256s=("a" * 64,),
                ),
                FundExposureBucketV1(
                    dimension=FundExposureDimension.SECTOR,
                    bucket_key="energy",
                    weight=Decimal("0.40"),
                    source_record_sha256s=("a" * 64,),
                ),
            ),
            reported_coverage_weight=Decimal("1"),
            source_record_sha256s=("a" * 64,),
        )


def test_aum_requires_explicit_currency() -> None:
    with pytest.raises(ValueError, match="AUM and currency"):
        FundProfileV1(
            instrument=IDENTITY,
            aum=Decimal("1000000"),
            as_of=NOW,
            source_record_sha256s=("a" * 64,),
        )


def test_stale_liquidity_is_explicit_blocker() -> None:
    profile_record = _record("fund.profile")
    holdings_record = _record("fund.holdings")
    dossier = _dossier(profile_record, holdings_record)
    source = MarketSourceV1(
        provider="T-Invest",
        authority=SourceAuthority.PRIMARY,
        retrieved_at=NOW,
        source_id="orderbook",
    )
    liquidity = MarketLiquidityV1(
        instrument_key=f"uid:{UID}",
        currency="RUB",
        as_of=NOW - timedelta(minutes=6),
        source=source,
        best_bid=Decimal("99"),
        best_ask=Decimal("101"),
        spread_absolute=Decimal("2"),
        spread_bps=Decimal("200"),
    )
    result = build_fund_xray(
        dossier=dossier,
        universe=_universe(),
        profile=_profile(profile_record.record_sha256),
        composition=_full_composition(holdings_record.record_sha256),
        liquidity=liquidity,
        assessed_at=NOW,
    )

    assert FundBlockerCode.LIQUIDITY_STALE in result.blockers
    assert result.decision_ready is False


def test_liquidity_identity_mismatch_is_explicit_blocker() -> None:
    profile_record = _record("fund.profile")
    holdings_record = _record("fund.holdings")
    dossier = _dossier(profile_record, holdings_record)
    source = MarketSourceV1(
        provider="T-Invest",
        authority=SourceAuthority.PRIMARY,
        retrieved_at=NOW,
        source_id="orderbook",
    )
    liquidity = MarketLiquidityV1(
        instrument_key="uid:other-fund",
        currency="RUB",
        as_of=NOW,
        source=source,
        best_bid=Decimal("99"),
        best_ask=Decimal("101"),
        spread_absolute=Decimal("2"),
        spread_bps=Decimal("200"),
    )
    result = build_fund_xray(
        dossier=dossier,
        universe=_universe(),
        profile=_profile(profile_record.record_sha256),
        composition=_full_composition(holdings_record.record_sha256),
        liquidity=liquidity,
        assessed_at=NOW,
    )

    assert FundBlockerCode.LIQUIDITY_IDENTITY_MISMATCH in result.blockers


def test_wrong_or_degraded_universe_fails_closed() -> None:
    profile_record = _record("fund.profile")
    holdings_record = _record("fund.holdings")
    dossier = _dossier(profile_record, holdings_record)
    kwargs = {
        "dossier": dossier,
        "profile": _profile(profile_record.record_sha256),
        "composition": _full_composition(holdings_record.record_sha256),
        "assessed_at": NOW,
    }
    wrong = build_fund_xray(universe=_universe(uid="other-fund"), **kwargs)
    degraded = build_fund_xray(universe=_universe(ready=False), **kwargs)

    assert FundBlockerCode.UNIVERSE_BINDING_MISMATCH in wrong.blockers
    assert FundBlockerCode.UNIVERSE_BINDING_MISMATCH in degraded.blockers


def test_non_etf_target_is_rejected() -> None:
    profile_record = _record("fund.profile")
    holdings_record = _record("fund.holdings")
    share_target = TARGET.model_copy(update={"instrument_type": InstrumentType.SHARE})
    dossier = _dossier(profile_record, holdings_record, target=share_target)
    result = build_fund_xray(
        dossier=dossier,
        universe=_universe(),
        profile=_profile(profile_record.record_sha256),
        composition=_full_composition(holdings_record.record_sha256),
        assessed_at=NOW,
    )

    assert FundBlockerCode.NOT_ETF in result.blockers
    assert result.decision_ready is False
