from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from omni_cio.contracts.v1.investment_policy import (
    AccountPolicyType,
    InvestmentObjective,
    InvestmentPolicyAssessmentV1,
    InvestmentPolicyStatementV1,
    LiquidityReserveV1,
    PolicyField,
    PolicyFieldProvenanceV1,
    PolicyLifecycle,
    PolicySourceKind,
    RiskLevel,
    TaxConstraintStatus,
)
from omni_cio.contracts.v1.portfolio import InstrumentType
from omni_cio.contracts.v1.portfolio_risk import (
    FundCreditRiskInputV1,
    MacroRiskAssumptionsV1,
    PermanentLossStatus,
    PortfolioRiskInputV1,
    PositionLiquidityRiskInputV1,
    PositionPermanentLossInputV1,
    ProposedTradeRiskEffectV1,
    RiskBlockerCode,
    RiskExposureDimension,
    RiskExposureMode,
    RiskExposureSliceV1,
    RiskFxConversionV1,
    RiskPositionV1,
    RiskSeverity,
    RiskVectorKind,
)
from omni_cio.policy import assess_investment_policy
from omni_cio.risk import assess_portfolio_risk


EFFECTIVE = datetime(2026, 1, 1, tzinfo=timezone.utc)
ASSESS_AT = datetime(2026, 8, 4, 8, 0, tzinfo=timezone.utc)
SOURCE_SHA = "a" * 64
FUND_SHA = "b" * 64
SNAPSHOT_SHA = "c" * 64

_FIELDS = (
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
    PolicyField.ALLOWED_INSTRUMENT_TYPES,
    PolicyField.PROHIBITED_INSTRUMENT_TYPES,
    PolicyField.TAX_STATUS,
    PolicyField.ACCOUNT_TYPE,
    PolicyField.REBALANCE_BAND,
)


def _policy() -> InvestmentPolicyStatementV1:
    provenance = tuple(
        PolicyFieldProvenanceV1(
            field=field,
            source_kind=(
                PolicySourceKind.VERIFIED_ACCOUNT_DATA
                if field is PolicyField.ACCOUNT_TYPE
                else PolicySourceKind.OWNER_INPUT
            ),
            owner_confirmed=field is not PolicyField.ACCOUNT_TYPE,
            confirmed_at=EFFECTIVE,
            source_id=f"source-{field.value}",
        )
        for field in _FIELDS
    )
    return InvestmentPolicyStatementV1(
        policy_id="ips_risk_hardening_v9",
        version="1",
        lifecycle=PolicyLifecycle.ACTIVE,
        created_at=EFFECTIVE,
        effective_at=EFFECTIVE,
        review_due_at=datetime(2026, 12, 31, tzinfo=timezone.utc),
        base_currency="RUB",
        objective=InvestmentObjective.PRESERVE_PURCHASING_POWER,
        time_horizon_years=Decimal("10"),
        liquidity_reserve=LiquidityReserveV1(
            amount=Decimal("100000"),
            currency="RUB",
        ),
        risk_willingness=RiskLevel.MODERATE,
        risk_capacity=RiskLevel.MODERATE,
        max_drawdown=Decimal("0.35"),
        max_position_weight=Decimal("0.80"),
        max_group_weight=Decimal("0.90"),
        max_sector_weight=Decimal("0.90"),
        max_currency_weight=Decimal("1"),
        minimum_credit_rating="A-",
        credit_rating_scale="AKRA_RU",
        allowed_markets=("MOEX",),
        allowed_instrument_types=(
            InstrumentType.SHARE,
            InstrumentType.BOND,
            InstrumentType.ETF,
        ),
        prohibited_instrument_types=(
            InstrumentType.FUTURE,
            InstrumentType.OPTION,
            InstrumentType.STRUCTURED_PRODUCT,
        ),
        tax_constraint_status=TaxConstraintStatus.REVIEWED,
        account_type=AccountPolicyType.BROKERAGE,
        rebalance_band_weight=Decimal("0.05"),
        provenance=provenance,
    )


def _macro() -> MacroRiskAssumptionsV1:
    return MacroRiskAssumptionsV1(
        annual_inflation_rate=Decimal("0.04"),
        annual_cash_opportunity_rate=Decimal("0.05"),
    )


def _exposures(*, issuer: str, asset_class: str, currency: str = "RUB"):
    return (
        RiskExposureSliceV1(
            dimension=RiskExposureDimension.ISSUER,
            bucket_key=issuer,
            weight_within_position=Decimal("1"),
        ),
        RiskExposureSliceV1(
            dimension=RiskExposureDimension.GROUP,
            bucket_key="group:test",
            weight_within_position=Decimal("1"),
        ),
        RiskExposureSliceV1(
            dimension=RiskExposureDimension.SECTOR,
            bucket_key="sector:test",
            weight_within_position=Decimal("1"),
        ),
        RiskExposureSliceV1(
            dimension=RiskExposureDimension.ASSET_CLASS,
            bucket_key=asset_class,
            weight_within_position=Decimal("1"),
        ),
        RiskExposureSliceV1(
            dimension=RiskExposureDimension.CURRENCY,
            bucket_key=currency,
            weight_within_position=Decimal("1"),
        ),
    )


def _liquidity() -> PositionLiquidityRiskInputV1:
    return PositionLiquidityRiskInputV1(
        daily_exit_capacity_base=Decimal("1000000"),
        spread_bps=Decimal("10"),
        as_of=ASSESS_AT,
        source_sha256=SOURCE_SHA,
    )


def _share(key: str, value: str) -> RiskPositionV1:
    amount = Decimal(value)
    return RiskPositionV1(
        stable_key=key,
        instrument_type=InstrumentType.SHARE,
        native_currency="RUB",
        native_market_value=amount,
        base_currency="RUB",
        base_market_value=amount,
        exposure_mode=RiskExposureMode.DIRECT,
        exposures=_exposures(issuer=f"issuer:{key}", asset_class="share"),
        liquidity=_liquidity(),
        permanent_loss=PositionPermanentLossInputV1(
            status=PermanentLossStatus.PASS
        ),
    )


def _fund(
    *,
    fund_credit: FundCreditRiskInputV1 | None,
    value: str = "300000",
) -> RiskPositionV1:
    amount = Decimal(value)
    return RiskPositionV1(
        stable_key="uid:fund-credit",
        instrument_type=InstrumentType.ETF,
        native_currency="RUB",
        native_market_value=amount,
        base_currency="RUB",
        base_market_value=amount,
        exposure_mode=RiskExposureMode.FUND_LOOKTHROUGH,
        exposures=_exposures(
            issuer="issuer:underlying",
            asset_class="bond",
        ),
        fund_xray_sha256=FUND_SHA,
        fund_xray_decision_ready=True,
        fund_credit=fund_credit,
        liquidity=_liquidity(),
        permanent_loss=PositionPermanentLossInputV1(
            status=PermanentLossStatus.PASS
        ),
    )


def _portfolio(
    positions: tuple[RiskPositionV1, ...],
    *,
    cash: str = "400000",
) -> tuple[
    InvestmentPolicyStatementV1,
    InvestmentPolicyAssessmentV1,
    PortfolioRiskInputV1,
]:
    policy = _policy()
    assessment = assess_investment_policy(policy, assessed_at=ASSESS_AT)
    assert assessment.ready_for_personal_sizing
    return (
        policy,
        assessment,
        PortfolioRiskInputV1(
            portfolio_snapshot_sha256=SNAPSHOT_SHA,
            policy_reference=assessment.reference,
            base_currency="RUB",
            cash_base=Decimal(cash),
            positions=positions,
        ),
    )


def _vector(result, kind: RiskVectorKind):
    return next(row for row in result.after.vectors if row.kind is kind)


def test_fund_credit_unknown_weight_blocks_decision_readiness() -> None:
    credit = FundCreditRiskInputV1(
        fund_xray_sha256=FUND_SHA,
        applicable_weight=Decimal("0.60"),
        assessed_weight=Decimal("0.40"),
        unknown_weight=Decimal("0.20"),
        source_sha256s=(SOURCE_SHA,),
    )
    policy, policy_assessment, portfolio = _portfolio((_fund(fund_credit=credit),))

    result = assess_portfolio_risk(
        portfolio=portfolio,
        policy=policy,
        policy_assessment=policy_assessment,
        macro=_macro(),
        assessed_at=ASSESS_AT,
    )

    assert RiskBlockerCode.CREDIT_NOT_READY in result.after.blockers
    assert result.decision_ready is False
    assert _vector(result, RiskVectorKind.CREDIT).severity is RiskSeverity.UNKNOWN


def test_fund_credit_floor_or_default_weight_is_hard_breach() -> None:
    credit = FundCreditRiskInputV1(
        fund_xray_sha256=FUND_SHA,
        applicable_weight=Decimal("0.60"),
        assessed_weight=Decimal("0.60"),
        floor_breach_weight=Decimal("0.15"),
        active_default_weight=Decimal("0.05"),
        unknown_weight=Decimal("0"),
        source_sha256s=(SOURCE_SHA,),
    )
    policy, policy_assessment, portfolio = _portfolio((_fund(fund_credit=credit),))

    result = assess_portfolio_risk(
        portfolio=portfolio,
        policy=policy,
        policy_assessment=policy_assessment,
        macro=_macro(),
        assessed_at=ASSESS_AT,
    )

    assert RiskBlockerCode.CREDIT_FLOOR_BREACH in result.after.blockers
    assert RiskBlockerCode.ACTIVE_DEFAULT in result.after.blockers
    credit_vector = _vector(result, RiskVectorKind.CREDIT)
    assert credit_vector.hard_breach is True
    assert credit_vector.severity is RiskSeverity.BREACH
    assert result.plan_eligible is False


def test_etf_without_fund_credit_summary_fails_closed() -> None:
    policy, policy_assessment, portfolio = _portfolio((_fund(fund_credit=None),))

    result = assess_portfolio_risk(
        portfolio=portfolio,
        policy=policy,
        policy_assessment=policy_assessment,
        macro=_macro(),
        assessed_at=ASSESS_AT,
    )

    assert RiskBlockerCode.CREDIT_EVIDENCE_REQUIRED in result.after.blockers
    assert result.decision_ready is False


def test_stale_fx_is_explicit_readiness_blocker() -> None:
    stale = ASSESS_AT - timedelta(hours=2)
    position = RiskPositionV1(
        stable_key="uid:usd-share",
        instrument_type=InstrumentType.SHARE,
        native_currency="USD",
        native_market_value=Decimal("1000"),
        base_currency="RUB",
        base_market_value=Decimal("80000"),
        fx=RiskFxConversionV1(
            native_currency="USD",
            base_currency="RUB",
            rate_to_base=Decimal("80"),
            source_sha256=SOURCE_SHA,
            as_of=stale,
        ),
        exposure_mode=RiskExposureMode.DIRECT,
        exposures=_exposures(
            issuer="issuer:usd",
            asset_class="share",
            currency="USD",
        ),
        liquidity=_liquidity(),
        permanent_loss=PositionPermanentLossInputV1(
            status=PermanentLossStatus.PASS
        ),
    )
    policy, policy_assessment, portfolio = _portfolio((position,), cash="920000")

    result = assess_portfolio_risk(
        portfolio=portfolio,
        policy=policy,
        policy_assessment=policy_assessment,
        macro=_macro(),
        assessed_at=ASSESS_AT,
    )

    assert RiskBlockerCode.FX_EVIDENCE_STALE in result.after.blockers
    assert result.decision_ready is False
    assert _vector(result, RiskVectorKind.DATA_QUALITY).severity is RiskSeverity.UNKNOWN


def test_proposed_trade_order_does_not_change_assessment_sha() -> None:
    first = _share("uid:share-a", "200000")
    second = _share("uid:share-b", "200000")
    policy, policy_assessment, portfolio = _portfolio((first, second), cash="600000")
    effect_a = ProposedTradeRiskEffectV1(
        trade_id="trade_add_a",
        stable_key="uid:share-a",
        expected_before_value_base=Decimal("200000"),
        cash_delta_base=Decimal("-50000"),
        after_position=_share("uid:share-a", "250000"),
    )
    effect_b = ProposedTradeRiskEffectV1(
        trade_id="trade_add_b",
        stable_key="uid:share-b",
        expected_before_value_base=Decimal("200000"),
        cash_delta_base=Decimal("-50000"),
        after_position=_share("uid:share-b", "250000"),
    )

    left = assess_portfolio_risk(
        portfolio=portfolio,
        policy=policy,
        policy_assessment=policy_assessment,
        proposed_trades=(effect_a, effect_b),
        macro=_macro(),
        assessed_at=ASSESS_AT,
    )
    right = assess_portfolio_risk(
        portfolio=portfolio,
        policy=policy,
        policy_assessment=policy_assessment,
        proposed_trades=(effect_b, effect_a),
        macro=_macro(),
        assessed_at=ASSESS_AT,
    )

    assert left.proposed_trade_ids == ("trade_add_a", "trade_add_b")
    assert left.assessment_sha256 == right.assessment_sha256
    assert left == right
