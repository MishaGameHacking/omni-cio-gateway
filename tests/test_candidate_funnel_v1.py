from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from pydantic import ValidationError
import pytest

from omni_cio.candidates import CandidateFunnelEvaluationError, build_candidate_funnel
from omni_cio.contracts.v1.candidate_funnel import (
    CandidateBlockerCode,
    CandidateCostBasisV1,
    CandidateEvidenceV1,
    CandidateExposureContextV1,
    CandidateFactorGradesV1,
    CandidateGlobalBlockerCode,
    CandidateKind,
    CandidatePriceBasis,
    CandidateRiskScreenV1,
    CandidateRole,
    CandidateScoreV1,
    GapUrgency,
    PortfolioGapV1,
    PreliminaryLossStatus,
)
from omni_cio.contracts.v1.common import (
    Completeness,
    DataQuality,
    Money,
    QualityMetadata,
)
from omni_cio.contracts.v1.investment_policy import (
    AccountPolicyType,
    InvestmentObjective,
    InvestmentPolicyStatementV1,
    LiquidityReserveV1,
    PolicyField,
    PolicyFieldProvenanceV1,
    PolicyLifecycle,
    PolicySourceKind,
    RiskLevel,
    TaxConstraintStatus,
)
from omni_cio.contracts.v1.market import (
    MarketLiquidityV1,
    MarketQuoteV1,
    MarketSourceV1,
    SourceAuthority,
)
from omni_cio.contracts.v1.portfolio import InstrumentIdentity, InstrumentType
from omni_cio.contracts.v1.universe import (
    MarketUniverseSnapshotV1,
    REQUIRED_UNIVERSE_OPERATIONS,
    UniverseAccountEligibilityV1,
    UniverseInstrumentV1,
    UniverseSourceOperation,
)


NOW = datetime(2026, 8, 3, 18, 0, tzinfo=timezone.utc)


_OWNER_FIELDS = (
    PolicyField.OBJECTIVE,
    PolicyField.TIME_HORIZON,
    PolicyField.LIQUIDITY_RESERVE,
    PolicyField.RISK_WILLINGNESS,
    PolicyField.RISK_CAPACITY,
    PolicyField.MAX_DRAWDOWN,
    PolicyField.MAX_POSITION_WEIGHT,
    PolicyField.MAX_GROUP_WEIGHT,
    PolicyField.MAX_SECTOR_WEIGHT,
    PolicyField.MAX_CURRENCY_WEIGHT,
    PolicyField.MINIMUM_CREDIT_QUALITY,
    PolicyField.ALLOWED_MARKETS,
    PolicyField.PROHIBITED_INSTRUMENT_TYPES,
    PolicyField.ALLOWED_INSTRUMENT_TYPES,
    PolicyField.TAX_STATUS,
    PolicyField.REBALANCE_BAND,
)


def _policy_provenance() -> tuple[PolicyFieldProvenanceV1, ...]:
    rows = [
        PolicyFieldProvenanceV1(
            field=field,
            source_kind=PolicySourceKind.OWNER_INPUT,
            owner_confirmed=True,
            confirmed_at=NOW - timedelta(days=1),
            source_id=f"owner-{field.value}",
        )
        for field in _OWNER_FIELDS
    ]
    rows.append(
        PolicyFieldProvenanceV1(
            field=PolicyField.ACCOUNT_TYPE,
            source_kind=PolicySourceKind.VERIFIED_ACCOUNT_DATA,
            owner_confirmed=False,
            confirmed_at=NOW - timedelta(days=1),
            source_id="masked-account-fact",
        )
    )
    return tuple(rows)


def _policy(**updates: object) -> InvestmentPolicyStatementV1:
    payload: dict[str, object] = {
        "policy_id": "ips_wp4_test",
        "version": "1",
        "lifecycle": PolicyLifecycle.ACTIVE,
        "created_at": NOW - timedelta(days=10),
        "effective_at": NOW - timedelta(days=9),
        "review_due_at": NOW + timedelta(days=300),
        "base_currency": "RUB",
        "objective": InvestmentObjective.PRESERVE_PURCHASING_POWER,
        "time_horizon_years": Decimal("10"),
        "liquidity_reserve": LiquidityReserveV1(
            amount=Decimal("100000"),
            currency="RUB",
        ),
        "risk_willingness": RiskLevel.MODERATE,
        "risk_capacity": RiskLevel.MODERATE,
        "max_drawdown": Decimal("0.20"),
        "max_position_weight": Decimal("0.20"),
        "max_group_weight": Decimal("0.30"),
        "max_sector_weight": Decimal("0.40"),
        "max_currency_weight": Decimal("0.90"),
        "minimum_credit_rating": "A-",
        "credit_rating_scale": "AKRA_RU",
        "allowed_markets": ("MOEX",),
        "allowed_instrument_types": (
            InstrumentType.SHARE,
            InstrumentType.BOND,
            InstrumentType.ETF,
        ),
        "prohibited_instrument_types": (
            InstrumentType.FUTURE,
            InstrumentType.OPTION,
        ),
        "tax_constraint_status": TaxConstraintStatus.REVIEWED,
        "account_type": AccountPolicyType.BROKERAGE,
        "rebalance_band_weight": Decimal("0.05"),
        "provenance": _policy_provenance(),
    }
    payload.update(updates)
    return InvestmentPolicyStatementV1.model_validate(payload)


def _gap(
    *,
    role: CandidateRole = CandidateRole.EQUITY_GROWTH,
    urgency: GapUrgency = GapUrgency.NORMAL,
    budget: Decimal | None = Decimal("100000"),
    max_research_candidates: int = 5,
) -> PortfolioGapV1:
    return PortfolioGapV1(
        gap_id="gap_wp4_test",
        role=role,
        urgency=urgency,
        target_currency="RUB",
        portfolio_snapshot_sha256="a" * 64,
        budget=(Money(amount=budget, currency="RUB") if budget is not None else None),
        max_research_candidates=max_research_candidates,
    )


def _universe_row(
    uid: str,
    ticker: str,
    instrument_type: InstrumentType = InstrumentType.SHARE,
    *,
    currency: str = "RUB",
    market: str = "REAL_EXCHANGE_MOEX",
    lot: int = 1,
    liquidity_sufficient: bool | None = True,
) -> UniverseInstrumentV1:
    operation = {
        InstrumentType.SHARE: UniverseSourceOperation.SHARES,
        InstrumentType.BOND: UniverseSourceOperation.BONDS,
        InstrumentType.ETF: UniverseSourceOperation.ETFS,
    }[instrument_type]
    return UniverseInstrumentV1(
        source_operation=operation,
        identity=InstrumentIdentity(
            name=ticker,
            instrument_type=instrument_type,
            currency=currency,
            lot=lot,
            ticker=ticker,
            class_code="TQBR",
            uid=uid,
            figi=f"FIGI-{uid}",
            position_uid=f"POS-{uid}",
        ),
        exchange="MOEX",
        real_exchange=market,
        api_trade_available=True,
        buy_available=True,
        sell_available=True,
        for_iis=True,
        for_qual_investor=False,
        blocked_tca=False,
        liquidity_sufficient=liquidity_sufficient,
    )


def _universe(
    *rows: UniverseInstrumentV1,
    decision_ready: bool = True,
    sha: str = "b" * 64,
) -> MarketUniverseSnapshotV1:
    return MarketUniverseSnapshotV1(
        retrieved_at=NOW,
        account=UniverseAccountEligibilityV1(
            account_type=AccountPolicyType.BROKERAGE,
            qualified_investor=False,
        ),
        completed_operations=REQUIRED_UNIVERSE_OPERATIONS,
        instruments=rows,
        content_sha256=sha,
        quality=QualityMetadata(
            quality=(DataQuality.VERIFIED if decision_ready else DataQuality.DEGRADED),
            completeness=(Completeness.COMPLETE if decision_ready else Completeness.INCOMPLETE),
        ),
        decision_ready=decision_ready,
    )


def _source(authority: SourceAuthority = SourceAuthority.OFFICIAL) -> MarketSourceV1:
    return MarketSourceV1(
        provider="T-Invest",
        authority=authority,
        retrieved_at=NOW,
        source_id="market-evidence",
    )


def _evidence(
    row: UniverseInstrumentV1,
    *,
    bid: Decimal = Decimal("99.90"),
    ask: Decimal = Decimal("100.00"),
    as_of: datetime = NOW,
    authority: SourceAuthority = SourceAuthority.OFFICIAL,
    portfolio_snapshot_sha256: str = "a" * 64,
    portfolio_value: Decimal = Decimal("1000000"),
    position_weight: Decimal = Decimal("0"),
    group_weight: Decimal = Decimal("0"),
    sector_weight: Decimal = Decimal("0"),
    currency_weight: Decimal = Decimal("0"),
    risk_status: PreliminaryLossStatus = PreliminaryLossStatus.PASS,
    price_basis: CandidatePriceBasis | None = None,
    nominal: Decimal = Decimal("1000"),
    accrued: Decimal = Decimal("0"),
) -> CandidateEvidenceV1:
    uid = row.identity.uid
    assert uid is not None
    midpoint = (bid + ask) / Decimal("2")
    spread = ask - bid
    spread_bps = spread / midpoint * Decimal("10000")
    source = _source(authority)
    if price_basis is None:
        price_basis = (
            CandidatePriceBasis.PERCENT_OF_NOMINAL
            if row.identity.instrument_type is InstrumentType.BOND
            else CandidatePriceBasis.CURRENCY
        )
    if price_basis is CandidatePriceBasis.PERCENT_OF_NOMINAL:
        cost_basis = CandidateCostBasisV1(
            instrument_uid=uid,
            price_basis=price_basis,
            nominal=Money(amount=nominal, currency=row.identity.currency),
            accrued_interest_per_unit=Money(
                amount=accrued,
                currency=row.identity.currency,
            ),
        )
    else:
        cost_basis = CandidateCostBasisV1(
            instrument_uid=uid,
            price_basis=price_basis,
        )
    return CandidateEvidenceV1(
        instrument_uid=uid,
        quote=MarketQuoteV1(
            instrument_key=f"uid:{uid}",
            currency=row.identity.currency,
            as_of=as_of,
            source=source,
            best_bid=bid,
            best_ask=ask,
        ),
        liquidity=MarketLiquidityV1(
            instrument_key=f"uid:{uid}",
            currency=row.identity.currency,
            as_of=as_of,
            source=source,
            best_bid=bid,
            best_ask=ask,
            spread_absolute=spread,
            spread_bps=spread_bps,
        ),
        exposure=CandidateExposureContextV1(
            instrument_uid=uid,
            portfolio_snapshot_sha256=portfolio_snapshot_sha256,
            portfolio_value=Money(amount=portfolio_value, currency=row.identity.currency),
            current_position_weight=position_weight,
            current_group_weight=group_weight,
            current_sector_weight=sector_weight,
            current_currency_weight=currency_weight,
        ),
        cost_basis=cost_basis,
        risk_screen=CandidateRiskScreenV1(
            instrument_uid=uid,
            status=risk_status,
            evidence_codes=("PRELIMINARY_SCREEN",),
        ),
    )


def test_score_contract_rejects_arbitrary_rank_points() -> None:
    factors = CandidateFactorGradesV1(
        role_fit=4,
        diversification=4,
        liquidity=4,
        cost=4,
        permanent_loss=4,
        freshness=4,
    )
    with pytest.raises(ValidationError, match="rank_points must reconcile"):
        CandidateScoreV1(
            kind=CandidateKind.NO_ACTION_CASH,
            candidate_id="cash:no_action",
            role=CandidateRole.EQUITY_GROWTH,
            rank_points=1,
            factors=factors,
            research_required=False,
        )


def test_valid_funnel_contains_cash_and_security_shortlist() -> None:
    share = _universe_row("uid-share", "AAA")
    result = build_candidate_funnel(
        gap=_gap(urgency=GapUrgency.HIGH),
        policy=_policy(),
        universe=_universe(share),
        evidence=(_evidence(share),),
        assessed_at=NOW,
    )

    assert result.decision_ready is True
    assert any(row.kind is CandidateKind.NO_ACTION_CASH for row in result.ranked_alternatives)
    assert result.research_shortlist[0].instrument_uid == "uid-share"
    assert result.research_shortlist[0].research_required is True
    assert result.trading_methods is False


def test_no_action_cash_can_rank_first() -> None:
    share = _universe_row("uid-wide", "WIDE")
    result = build_candidate_funnel(
        gap=_gap(urgency=GapUrgency.NORMAL),
        policy=_policy(),
        universe=_universe(share),
        evidence=(
            _evidence(
                share,
                bid=Decimal("98"),
                ask=Decimal("100"),
                risk_status=PreliminaryLossStatus.UNKNOWN,
            ),
        ),
        assessed_at=NOW,
    )

    assert result.ranked_alternatives[0].kind is CandidateKind.NO_ACTION_CASH


def test_source_order_does_not_change_ranking_or_fingerprint() -> None:
    first = _universe_row("uid-a", "AAA")
    second = _universe_row("uid-b", "BBB")
    kwargs = {
        "gap": _gap(urgency=GapUrgency.HIGH),
        "policy": _policy(),
        "assessed_at": NOW,
    }
    left = build_candidate_funnel(
        **kwargs,
        universe=_universe(first, second),
        evidence=(_evidence(first), _evidence(second)),
    )
    right = build_candidate_funnel(
        **kwargs,
        universe=_universe(second, first),
        evidence=(_evidence(second), _evidence(first)),
    )

    assert left.funnel_sha256 == right.funnel_sha256
    assert [row.candidate_id for row in left.ranked_alternatives] == [
        row.candidate_id for row in right.ranked_alternatives
    ]


def test_equal_security_scores_use_stable_candidate_id_tie_breaker() -> None:
    first = _universe_row("uid-a", "AAA")
    second = _universe_row("uid-b", "BBB")
    result = build_candidate_funnel(
        gap=_gap(urgency=GapUrgency.HIGH),
        policy=_policy(),
        universe=_universe(second, first),
        evidence=(_evidence(second), _evidence(first)),
        assessed_at=NOW,
    )

    security_ids = [
        row.candidate_id
        for row in result.ranked_alternatives
        if row.kind is CandidateKind.SECURITY
    ]
    assert security_ids == sorted(security_ids)


def test_missing_evidence_for_any_eligible_security_blocks_partial_ranking() -> None:
    first = _universe_row("uid-a", "AAA")
    second = _universe_row("uid-b", "BBB")
    result = build_candidate_funnel(
        gap=_gap(),
        policy=_policy(),
        universe=_universe(first, second),
        evidence=(_evidence(first),),
        assessed_at=NOW,
    )

    assert result.decision_ready is False
    assert CandidateGlobalBlockerCode.EVIDENCE_COVERAGE_INCOMPLETE in result.global_blockers
    assert result.research_shortlist == ()
    assert result.ranked_alternatives[0].kind is CandidateKind.NO_ACTION_CASH
    assert all(row.kind is CandidateKind.NO_ACTION_CASH for row in result.ranked_alternatives)


def test_duplicate_evidence_blocks_funnel() -> None:
    share = _universe_row("uid-a", "AAA")
    evidence = _evidence(share)
    result = build_candidate_funnel(
        gap=_gap(),
        policy=_policy(),
        universe=_universe(share),
        evidence=(evidence, evidence),
        assessed_at=NOW,
    )

    assert CandidateGlobalBlockerCode.DUPLICATE_EVIDENCE in result.global_blockers
    assert result.decision_ready is False


def test_duplicate_evidence_for_static_rejection_does_not_block_eligible_universe() -> None:
    eligible = _universe_row("uid-a", "AAA")
    rejected = _universe_row("uid-usd", "USD", currency="USD")
    rejected_evidence = _evidence(rejected)
    result = build_candidate_funnel(
        gap=_gap(urgency=GapUrgency.HIGH),
        policy=_policy(),
        universe=_universe(eligible, rejected),
        evidence=(
            _evidence(eligible),
            rejected_evidence,
            rejected_evidence,
        ),
        assessed_at=NOW,
    )

    assert CandidateGlobalBlockerCode.DUPLICATE_EVIDENCE not in result.global_blockers
    assert result.decision_ready is True
    assert result.research_shortlist[0].instrument_uid == "uid-a"


def test_stale_or_future_market_evidence_cannot_receive_score() -> None:
    share = _universe_row("uid-a", "AAA")
    stale = build_candidate_funnel(
        gap=_gap(),
        policy=_policy(),
        universe=_universe(share),
        evidence=(_evidence(share, as_of=NOW - timedelta(minutes=6)),),
        assessed_at=NOW,
    )
    future = build_candidate_funnel(
        gap=_gap(),
        policy=_policy(),
        universe=_universe(share),
        evidence=(_evidence(share, as_of=NOW + timedelta(minutes=2)),),
        assessed_at=NOW,
    )

    assert CandidateBlockerCode.MARKET_STALE in stale.rejected[0].blockers
    assert CandidateBlockerCode.MARKET_FUTURE_TIMESTAMP in future.rejected[0].blockers
    assert stale.research_shortlist == ()
    assert future.research_shortlist == ()


def test_untrusted_market_source_is_rejected_before_scoring() -> None:
    share = _universe_row("uid-a", "AAA")
    result = build_candidate_funnel(
        gap=_gap(),
        policy=_policy(),
        universe=_universe(share),
        evidence=(_evidence(share, authority=SourceAuthority.UNTRUSTED),),
        assessed_at=NOW,
    )

    assert CandidateBlockerCode.MARKET_SOURCE_UNTRUSTED in result.rejected[0].blockers


def test_policy_deny_and_role_mismatch_happen_before_market_coverage() -> None:
    share = _universe_row("uid-share", "AAA")
    bond = _universe_row("uid-bond", "BOND", InstrumentType.BOND)
    deny_policy = _policy(prohibited_instrument_types=(InstrumentType.SHARE,))
    deny = build_candidate_funnel(
        gap=_gap(),
        policy=deny_policy,
        universe=_universe(share),
        evidence=(),
        assessed_at=NOW,
    )
    mismatch = build_candidate_funnel(
        gap=_gap(role=CandidateRole.DEFENSIVE_BOND),
        policy=_policy(),
        universe=_universe(share, bond),
        evidence=(_evidence(bond),),
        assessed_at=NOW,
    )

    assert deny.decision_ready is True
    assert CandidateBlockerCode.POLICY_INSTRUMENT_PROHIBITED in deny.rejected[0].blockers
    share_rejection = next(row for row in mismatch.rejected if row.instrument_uid == "uid-share")
    assert CandidateBlockerCode.ROLE_MISMATCH in share_rejection.blockers
    assert mismatch.decision_ready is True


def test_target_currency_mismatch_is_static_blocker() -> None:
    share = _universe_row("uid-usd", "USD", currency="USD")
    result = build_candidate_funnel(
        gap=_gap(),
        policy=_policy(),
        universe=_universe(share),
        evidence=(),
        assessed_at=NOW,
    )

    assert CandidateBlockerCode.TARGET_CURRENCY_MISMATCH in result.rejected[0].blockers
    assert result.decision_ready is True


def test_unaffordable_minimum_lot_is_rejected() -> None:
    share = _universe_row("uid-expensive", "EXP", lot=10)
    result = build_candidate_funnel(
        gap=_gap(budget=Decimal("500")),
        policy=_policy(),
        universe=_universe(share),
        evidence=(_evidence(share, ask=Decimal("100"), bid=Decimal("99")),),
        assessed_at=NOW,
    )

    assert CandidateBlockerCode.UNAFFORDABLE_MIN_LOT in result.rejected[0].blockers


def test_exposure_must_match_gap_portfolio_snapshot() -> None:
    share = _universe_row("uid-snapshot", "SNAP")
    result = build_candidate_funnel(
        gap=_gap(),
        policy=_policy(),
        universe=_universe(share),
        evidence=(_evidence(share, portfolio_snapshot_sha256="c" * 64),),
        assessed_at=NOW,
    )

    assert CandidateBlockerCode.PORTFOLIO_SNAPSHOT_MISMATCH in result.rejected[0].blockers
    assert result.research_shortlist == ()


def test_one_lot_concentration_headroom_is_hard_blocker() -> None:
    share = _universe_row("uid-limit", "LIM")
    result = build_candidate_funnel(
        gap=_gap(),
        policy=_policy(max_position_weight=Decimal("0.20")),
        universe=_universe(share),
        evidence=(
            _evidence(
                share,
                portfolio_value=Decimal("1000"),
                position_weight=Decimal("0.15"),
                group_weight=Decimal("0.15"),
                sector_weight=Decimal("0.15"),
                currency_weight=Decimal("0.15"),
                bid=Decimal("99"),
                ask=Decimal("100"),
            ),
        ),
        assessed_at=NOW,
    )

    assert CandidateBlockerCode.POSITION_LIMIT in result.rejected[0].blockers


def test_bond_minimum_lot_cost_uses_percent_nominal_plus_accrued_interest() -> None:
    bond = _universe_row(
        "uid-bond",
        "BOND",
        InstrumentType.BOND,
        lot=2,
    )
    result = build_candidate_funnel(
        gap=_gap(role=CandidateRole.DEFENSIVE_BOND, urgency=GapUrgency.HIGH),
        policy=_policy(),
        universe=_universe(bond),
        evidence=(
            _evidence(
                bond,
                bid=Decimal("94.9"),
                ask=Decimal("95"),
                nominal=Decimal("1000"),
                accrued=Decimal("10"),
            ),
        ),
        assessed_at=NOW,
    )

    security = next(
        row for row in result.ranked_alternatives if row.kind is CandidateKind.SECURITY
    )
    assert security.minimum_lot_cost == Money(amount=Decimal("1920"), currency="RUB")


def test_wrong_price_basis_is_rejected_for_bond_and_share() -> None:
    bond = _universe_row("uid-bond", "BOND", InstrumentType.BOND)
    share = _universe_row("uid-share", "AAA")
    bond_bad = build_candidate_funnel(
        gap=_gap(role=CandidateRole.DEFENSIVE_BOND),
        policy=_policy(),
        universe=_universe(bond),
        evidence=(
            _evidence(bond, price_basis=CandidatePriceBasis.CURRENCY),
        ),
        assessed_at=NOW,
    )
    share_bad_basis = CandidateCostBasisV1(
        instrument_uid="uid-share",
        price_basis=CandidatePriceBasis.PERCENT_OF_NOMINAL,
        nominal=Money(amount=Decimal("1000"), currency="RUB"),
    )
    share_evidence = _evidence(share).model_copy(
        update={"cost_basis": share_bad_basis}
    )
    share_bad = build_candidate_funnel(
        gap=_gap(),
        policy=_policy(),
        universe=_universe(share),
        evidence=(share_evidence,),
        assessed_at=NOW,
    )

    assert CandidateBlockerCode.COST_BASIS_INVALID in bond_bad.rejected[0].blockers
    assert CandidateBlockerCode.COST_BASIS_INVALID in share_bad.rejected[0].blockers


def test_preliminary_loss_block_rejects_but_unknown_remains_researchable() -> None:
    blocked_row = _universe_row("uid-block", "BLOCK")
    unknown_row = _universe_row("uid-unknown", "UNKNOWN")
    result = build_candidate_funnel(
        gap=_gap(urgency=GapUrgency.HIGH),
        policy=_policy(),
        universe=_universe(blocked_row, unknown_row),
        evidence=(
            _evidence(blocked_row, risk_status=PreliminaryLossStatus.BLOCK),
            _evidence(unknown_row, risk_status=PreliminaryLossStatus.UNKNOWN),
        ),
        assessed_at=NOW,
    )

    blocked = next(row for row in result.rejected if row.instrument_uid == "uid-block")
    assert CandidateBlockerCode.PERMANENT_LOSS_BLOCKED in blocked.blockers
    unknown = next(
        row for row in result.ranked_alternatives if row.instrument_uid == "uid-unknown"
    )
    assert unknown.factors.permanent_loss == 1
    assert unknown.research_required is True


def test_shortlist_is_bounded_after_deterministic_ranking() -> None:
    rows = tuple(_universe_row(f"uid-{index}", f"T{index}") for index in range(4))
    result = build_candidate_funnel(
        gap=_gap(urgency=GapUrgency.HIGH, max_research_candidates=2),
        policy=_policy(),
        universe=_universe(*reversed(rows)),
        evidence=tuple(_evidence(row) for row in reversed(rows)),
        assessed_at=NOW,
    )

    assert len(result.research_shortlist) == 2
    assert [row.candidate_id for row in result.research_shortlist] == [
        "uid:uid-0",
        "uid:uid-1",
    ]


def test_invalid_ips_or_universe_blocks_security_ranking() -> None:
    share = _universe_row("uid-a", "AAA")
    draft = build_candidate_funnel(
        gap=_gap(),
        policy=_policy(lifecycle=PolicyLifecycle.DRAFT),
        universe=_universe(share),
        evidence=(_evidence(share),),
        assessed_at=NOW,
    )
    bad_universe = build_candidate_funnel(
        gap=_gap(),
        policy=_policy(),
        universe=_universe(share, decision_ready=False),
        evidence=(_evidence(share),),
        assessed_at=NOW,
    )

    assert CandidateGlobalBlockerCode.IPS_NOT_READY in draft.global_blockers
    assert CandidateGlobalBlockerCode.UNIVERSE_NOT_READY in bad_universe.global_blockers
    assert draft.research_shortlist == ()
    assert bad_universe.research_shortlist == ()


def test_naive_assessment_timestamp_fails_closed() -> None:
    share = _universe_row("uid-a", "AAA")
    with pytest.raises(CandidateFunnelEvaluationError, match="TIMESTAMP_MUST_BE_AWARE"):
        build_candidate_funnel(
            gap=_gap(),
            policy=_policy(),
            universe=_universe(share),
            evidence=(_evidence(share),),
            assessed_at=datetime(2026, 8, 3, 18, 0),
        )
