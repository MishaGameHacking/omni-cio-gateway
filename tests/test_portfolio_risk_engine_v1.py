from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from pydantic import ValidationError
import pytest

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
from omni_cio.contracts.v1.portfolio import InstrumentType
from omni_cio.contracts.v1.portfolio_risk import (
    MacroRiskAssumptionsV1,
    PermanentLossStatus,
    PortfolioRiskInputV1,
    PositionCreditRiskInputV1,
    PositionLiquidityRiskInputV1,
    PositionPermanentLossInputV1,
    ProposedTradeRiskEffectV1,
    RiskBlockerCode,
    RiskEngineSettingsV1,
    RiskExposureDimension,
    RiskExposureMode,
    RiskExposureSliceV1,
    RiskFxConversionV1,
    RiskLimitSource,
    RiskLimitV1,
    RiskPositionV1,
    RiskSeverity,
    RiskVectorKind,
)
from omni_cio.policy import assess_investment_policy
from omni_cio.risk.engine_v1 import assess_portfolio_risk


EFFECTIVE = datetime(2026, 1, 1, tzinfo=timezone.utc)
REVIEW_DUE = datetime(2026, 12, 31, tzinfo=timezone.utc)
ASSESS_AT = datetime(2026, 8, 4, 7, 0, tzinfo=timezone.utc)
SNAPSHOT_SHA = "1" * 64
SOURCE_SHA = "2" * 64
FUND_SHA = "3" * 64
CREDIT_SHA = "4" * 64

_REQUIRED_PROVENANCE_FIELDS = (
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


def _provenance() -> tuple[PolicyFieldProvenanceV1, ...]:
    rows: list[PolicyFieldProvenanceV1] = []
    for field in _REQUIRED_PROVENANCE_FIELDS:
        verified_account = field is PolicyField.ACCOUNT_TYPE
        rows.append(
            PolicyFieldProvenanceV1(
                field=field,
                source_kind=(
                    PolicySourceKind.VERIFIED_ACCOUNT_DATA
                    if verified_account
                    else PolicySourceKind.OWNER_INPUT
                ),
                owner_confirmed=not verified_account,
                confirmed_at=EFFECTIVE,
                source_id=(
                    "masked-account-fact"
                    if verified_account
                    else f"owner-{field.value}"
                ),
            )
        )
    return tuple(rows)


def _policy(**updates: object) -> InvestmentPolicyStatementV1:
    payload: dict[str, object] = {
        "policy_id": "ips_owner_risk_v9",
        "version": "1",
        "lifecycle": PolicyLifecycle.ACTIVE,
        "created_at": EFFECTIVE,
        "effective_at": EFFECTIVE,
        "review_due_at": REVIEW_DUE,
        "base_currency": "RUB",
        "objective": InvestmentObjective.PRESERVE_PURCHASING_POWER,
        "time_horizon_years": Decimal("10"),
        "liquidity_reserve": LiquidityReserveV1(
            amount=Decimal("100000"),
            currency="RUB",
        ),
        "risk_willingness": RiskLevel.MODERATE,
        "risk_capacity": RiskLevel.MODERATE,
        "max_drawdown": Decimal("0.35"),
        "max_position_weight": Decimal("0.50"),
        "max_group_weight": Decimal("0.80"),
        "max_sector_weight": Decimal("0.80"),
        "max_currency_weight": Decimal("0.95"),
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
            InstrumentType.STRUCTURED_PRODUCT,
        ),
        "tax_constraint_status": TaxConstraintStatus.REVIEWED,
        "account_type": AccountPolicyType.BROKERAGE,
        "rebalance_band_weight": Decimal("0.05"),
        "provenance": _provenance(),
    }
    payload.update(updates)
    return InvestmentPolicyStatementV1.model_validate(payload)


def _macro() -> MacroRiskAssumptionsV1:
    return MacroRiskAssumptionsV1(
        annual_inflation_rate=Decimal("0.04"),
        annual_cash_opportunity_rate=Decimal("0.05"),
    )


def _exposures(
    *,
    issuer: str,
    group: str = "group_core",
    sector: str = "sector_core",
    asset_class: str = "share",
    currency: str = "RUB",
) -> tuple[RiskExposureSliceV1, ...]:
    return (
        RiskExposureSliceV1(
            dimension=RiskExposureDimension.ISSUER,
            bucket_key=issuer,
            weight_within_position=Decimal("1"),
        ),
        RiskExposureSliceV1(
            dimension=RiskExposureDimension.GROUP,
            bucket_key=group,
            weight_within_position=Decimal("1"),
        ),
        RiskExposureSliceV1(
            dimension=RiskExposureDimension.SECTOR,
            bucket_key=sector,
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


def _liquidity(capacity: str = "300000") -> PositionLiquidityRiskInputV1:
    return PositionLiquidityRiskInputV1(
        daily_exit_capacity_base=Decimal(capacity),
        spread_bps=Decimal("20"),
        as_of=ASSESS_AT,
        source_sha256=SOURCE_SHA,
    )


def _direct_position(
    *,
    key: str,
    value: str,
    issuer: str,
    instrument_type: InstrumentType = InstrumentType.SHARE,
    credit: PositionCreditRiskInputV1 | None = None,
    permanent_loss: PermanentLossStatus = PermanentLossStatus.PASS,
    liquidity: PositionLiquidityRiskInputV1 | None = None,
) -> RiskPositionV1:
    return RiskPositionV1(
        stable_key=key,
        instrument_type=instrument_type,
        native_currency="RUB",
        native_market_value=Decimal(value),
        base_currency="RUB",
        base_market_value=Decimal(value),
        exposure_mode=RiskExposureMode.DIRECT,
        exposures=_exposures(
            issuer=issuer,
            asset_class=instrument_type.value,
        ),
        liquidity=liquidity or _liquidity(),
        credit=credit,
        permanent_loss=PositionPermanentLossInputV1(status=permanent_loss),
    )


def _portfolio(
    policy: InvestmentPolicyStatementV1,
    *,
    positions: tuple[RiskPositionV1, ...] | None = None,
    cash: str = "400000",
    data_quality_codes: tuple[str, ...] = (),
) -> tuple[PortfolioRiskInputV1, object]:
    policy_assessment = assess_investment_policy(policy, assessed_at=ASSESS_AT)
    assert policy_assessment.ready_for_personal_sizing
    selected = positions or (
        _direct_position(key="uid:share_a", value="300000", issuer="issuer_a"),
        _direct_position(key="uid:share_b", value="300000", issuer="issuer_b"),
    )
    return (
        PortfolioRiskInputV1(
            portfolio_snapshot_sha256=SNAPSHOT_SHA,
            policy_reference=policy_assessment.reference,
            base_currency="RUB",
            cash_base=Decimal(cash),
            positions=selected,
            data_quality_codes=data_quality_codes,
        ),
        policy_assessment,
    )


def _vector(assessment: object, kind: RiskVectorKind):
    return next(row for row in assessment.after.vectors if row.kind is kind)


def test_before_after_trade_exposes_new_hard_position_breach() -> None:
    policy = _policy()
    portfolio, policy_assessment = _portfolio(policy)
    after_a = _direct_position(
        key="uid:share_a",
        value="600000",
        issuer="issuer_a",
        liquidity=_liquidity("300000"),
    )
    effect = ProposedTradeRiskEffectV1(
        trade_id="trade_buy_share_a",
        stable_key="uid:share_a",
        expected_before_value_base=Decimal("300000"),
        cash_delta_base=Decimal("-300000"),
        after_position=after_a,
    )

    assessment = assess_portfolio_risk(
        portfolio=portfolio,
        policy=policy,
        policy_assessment=policy_assessment,
        proposed_trades=(effect,),
        macro=_macro(),
        assessed_at=ASSESS_AT,
    )

    assert assessment.before.policy_compliant is True
    assert assessment.after.policy_compliant is False
    assert assessment.plan_eligible is False
    assert RiskBlockerCode.POSITION_LIMIT_BREACH in assessment.new_blockers
    assert _vector(assessment, RiskVectorKind.CONCENTRATION).severity is RiskSeverity.BREACH
    assert assessment.after.concentration.top_1_weight == Decimal("0.6")
    assert assessment.after.concentration.top_3_weight == Decimal("0.9")
    assert assessment.trading_methods is False


def test_cross_currency_position_requires_explicit_fx_provenance() -> None:
    with pytest.raises(ValidationError, match="explicit FX provenance"):
        RiskPositionV1(
            stable_key="uid:usd_share",
            instrument_type=InstrumentType.SHARE,
            native_currency="USD",
            native_market_value=Decimal("1000"),
            base_currency="RUB",
            base_market_value=Decimal("80000"),
            exposure_mode=RiskExposureMode.DIRECT,
            exposures=_exposures(
                issuer="issuer_usd",
                currency="USD",
            ),
            liquidity=_liquidity(),
            permanent_loss=PositionPermanentLossInputV1(
                status=PermanentLossStatus.PASS
            ),
        )

    position = RiskPositionV1(
        stable_key="uid:usd_share",
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
            as_of=ASSESS_AT,
        ),
        exposure_mode=RiskExposureMode.DIRECT,
        exposures=_exposures(
            issuer="issuer_usd",
            currency="USD",
        ),
        liquidity=_liquidity(),
        permanent_loss=PositionPermanentLossInputV1(
            status=PermanentLossStatus.PASS
        ),
    )
    assert position.base_market_value == Decimal("80000")


def test_etf_requires_lookthrough_and_position_dimension_cannot_be_double_counted() -> None:
    with pytest.raises(ValidationError, match="ETF risk position requires fund look-through"):
        RiskPositionV1(
            stable_key="uid:fund",
            instrument_type=InstrumentType.ETF,
            native_currency="RUB",
            native_market_value=Decimal("100000"),
            base_currency="RUB",
            base_market_value=Decimal("100000"),
            exposure_mode=RiskExposureMode.DIRECT,
            exposures=_exposures(issuer="fund_wrapper", asset_class="etf"),
            liquidity=_liquidity(),
            permanent_loss=PositionPermanentLossInputV1(
                status=PermanentLossStatus.PASS
            ),
        )

    with pytest.raises(ValidationError, match="engine-derived"):
        RiskPositionV1(
            stable_key="uid:fund",
            instrument_type=InstrumentType.ETF,
            native_currency="RUB",
            native_market_value=Decimal("100000"),
            base_currency="RUB",
            base_market_value=Decimal("100000"),
            exposure_mode=RiskExposureMode.FUND_LOOKTHROUGH,
            exposures=(
                *_exposures(issuer="issuer_underlying", asset_class="share"),
                RiskExposureSliceV1(
                    dimension=RiskExposureDimension.POSITION,
                    bucket_key="uid:fund",
                    weight_within_position=Decimal("1"),
                ),
            ),
            fund_xray_sha256=FUND_SHA,
            fund_xray_decision_ready=True,
            liquidity=_liquidity(),
            permanent_loss=PositionPermanentLossInputV1(
                status=PermanentLossStatus.PASS
            ),
        )


def test_not_ready_fund_xray_blocks_decision_readiness_without_fabrication() -> None:
    policy = _policy()
    fund = RiskPositionV1(
        stable_key="uid:fund",
        instrument_type=InstrumentType.ETF,
        native_currency="RUB",
        native_market_value=Decimal("300000"),
        base_currency="RUB",
        base_market_value=Decimal("300000"),
        exposure_mode=RiskExposureMode.FUND_LOOKTHROUGH,
        exposures=_exposures(issuer="issuer_underlying", asset_class="share"),
        fund_xray_sha256=FUND_SHA,
        fund_xray_decision_ready=False,
        liquidity=_liquidity(),
        permanent_loss=PositionPermanentLossInputV1(status=PermanentLossStatus.PASS),
    )
    portfolio, policy_assessment = _portfolio(
        policy,
        positions=(fund,),
        cash="700000",
    )

    assessment = assess_portfolio_risk(
        portfolio=portfolio,
        policy=policy,
        policy_assessment=policy_assessment,
        macro=_macro(),
        assessed_at=ASSESS_AT,
    )

    assert RiskBlockerCode.FUND_XRAY_NOT_READY in assessment.after.blockers
    assert assessment.decision_ready is False
    assert _vector(assessment, RiskVectorKind.DATA_QUALITY).severity is RiskSeverity.UNKNOWN


def test_exact_ips_fingerprint_binding_detects_same_version_policy_mutation() -> None:
    policy = _policy()
    portfolio, policy_assessment = _portfolio(policy)
    mutated_policy = _policy(max_position_weight=Decimal("0.40"))

    assessment = assess_portfolio_risk(
        portfolio=portfolio,
        policy=mutated_policy,
        policy_assessment=policy_assessment,
        macro=_macro(),
        assessed_at=ASSESS_AT,
    )

    assert RiskBlockerCode.POLICY_BINDING_MISMATCH in assessment.before.blockers
    assert assessment.decision_ready is False


def test_system_guardrail_cannot_impersonate_owner_hard_limit() -> None:
    with pytest.raises(ValidationError, match="system guardrail"):
        RiskLimitV1(
            dimension=RiskExposureDimension.ISSUER,
            max_weight=Decimal("0.20"),
            source=RiskLimitSource.SYSTEM_GUARDRAIL,
            hard=True,
            owner_confirmed=False,
        )


def test_owner_confirmed_issuer_overlay_can_create_hard_breach() -> None:
    policy = _policy()
    shared = (
        _direct_position(key="uid:share_a", value="300000", issuer="issuer_same"),
        _direct_position(key="uid:share_b", value="300000", issuer="issuer_same"),
    )
    portfolio, policy_assessment = _portfolio(policy, positions=shared)
    settings = RiskEngineSettingsV1(
        additional_limits=(
            RiskLimitV1(
                dimension=RiskExposureDimension.ISSUER,
                max_weight=Decimal("0.40"),
                source=RiskLimitSource.OWNER_OVERLAY,
                hard=True,
                owner_confirmed=True,
            ),
        )
    )

    assessment = assess_portfolio_risk(
        portfolio=portfolio,
        policy=policy,
        policy_assessment=policy_assessment,
        settings=settings,
        macro=_macro(),
        assessed_at=ASSESS_AT,
    )

    assert RiskBlockerCode.ISSUER_LIMIT_BREACH in assessment.after.blockers
    assert assessment.after.policy_compliant is False


def test_credit_floor_and_active_default_are_hard_credit_breaches() -> None:
    policy = _policy()
    bond = _direct_position(
        key="uid:bond_a",
        value="300000",
        issuer="issuer_bond",
        instrument_type=InstrumentType.BOND,
        credit=PositionCreditRiskInputV1(
            credit_passport_sha256=CREDIT_SHA,
            decision_ready=True,
            policy_floor_passed=False,
            active_default_event=True,
        ),
    )
    portfolio, policy_assessment = _portfolio(
        policy,
        positions=(bond,),
        cash="700000",
    )

    assessment = assess_portfolio_risk(
        portfolio=portfolio,
        policy=policy,
        policy_assessment=policy_assessment,
        macro=_macro(),
        assessed_at=ASSESS_AT,
    )

    credit = _vector(assessment, RiskVectorKind.CREDIT)
    assert RiskBlockerCode.CREDIT_FLOOR_BREACH in assessment.after.blockers
    assert RiskBlockerCode.ACTIVE_DEFAULT in assessment.after.blockers
    assert credit.hard_breach is True
    assert credit.severity is RiskSeverity.BREACH
    assert assessment.plan_eligible is False


def test_stress_drawdown_breach_is_hard_and_not_averaged_away() -> None:
    policy = _policy(max_drawdown=Decimal("0.15"))
    portfolio, policy_assessment = _portfolio(policy)

    assessment = assess_portfolio_risk(
        portfolio=portfolio,
        policy=policy,
        policy_assessment=policy_assessment,
        macro=_macro(),
        assessed_at=ASSESS_AT,
    )

    market = _vector(assessment, RiskVectorKind.MARKET)
    assert RiskBlockerCode.MAX_DRAWDOWN_BREACH in assessment.after.blockers
    assert market.hard_breach is True
    assert market.severity is RiskSeverity.BREACH
    assert assessment.after.policy_compliant is False


def test_missing_liquidity_is_explicit_data_quality_blocker() -> None:
    policy = _policy()
    position = _direct_position(
        key="uid:share_a",
        value="300000",
        issuer="issuer_a",
    ).model_copy(update={"liquidity": None})
    portfolio, policy_assessment = _portfolio(
        policy,
        positions=(position,),
        cash="700000",
    )

    assessment = assess_portfolio_risk(
        portfolio=portfolio,
        policy=policy,
        policy_assessment=policy_assessment,
        macro=_macro(),
        assessed_at=ASSESS_AT,
    )

    assert RiskBlockerCode.LIQUIDITY_EVIDENCE_MISSING in assessment.after.blockers
    assert assessment.decision_ready is False
    assert _vector(assessment, RiskVectorKind.LIQUIDITY).severity is RiskSeverity.UNKNOWN


def test_trade_binding_mismatch_fails_closed_and_preserves_before_state() -> None:
    policy = _policy()
    portfolio, policy_assessment = _portfolio(policy)
    effect = ProposedTradeRiskEffectV1(
        trade_id="trade_bad_binding",
        stable_key="uid:share_a",
        expected_before_value_base=Decimal("299999"),
        cash_delta_base=Decimal("-100000"),
        after_position=_direct_position(
            key="uid:share_a",
            value="400000",
            issuer="issuer_a",
        ),
    )

    assessment = assess_portfolio_risk(
        portfolio=portfolio,
        policy=policy,
        policy_assessment=policy_assessment,
        proposed_trades=(effect,),
        macro=_macro(),
        assessed_at=ASSESS_AT,
    )

    assert RiskBlockerCode.TRADE_BINDING_MISMATCH in assessment.after.blockers
    assert assessment.after.total_value_base == assessment.before.total_value_base
    assert assessment.decision_ready is False
    assert assessment.plan_eligible is False


def test_input_order_does_not_change_risk_assessment_sha() -> None:
    policy = _policy()
    position_a = _direct_position(
        key="uid:share_a",
        value="300000",
        issuer="issuer_a",
    )
    position_b = _direct_position(
        key="uid:share_b",
        value="300000",
        issuer="issuer_b",
    )
    portfolio_a, policy_assessment = _portfolio(
        policy,
        positions=(position_a, position_b),
    )
    portfolio_b, _ = _portfolio(
        policy,
        positions=(position_b, position_a),
    )

    left = assess_portfolio_risk(
        portfolio=portfolio_a,
        policy=policy,
        policy_assessment=policy_assessment,
        macro=_macro(),
        assessed_at=ASSESS_AT,
    )
    right = assess_portfolio_risk(
        portfolio=portfolio_b,
        policy=policy,
        policy_assessment=policy_assessment,
        macro=_macro(),
        assessed_at=ASSESS_AT,
    )

    assert left.assessment_sha256 == right.assessment_sha256
    assert left == right
