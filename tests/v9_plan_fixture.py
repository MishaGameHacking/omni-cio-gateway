from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
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
from omni_cio.contracts.v1.meta_strategy import (
    MetaStrategySelectionV1,
    StrategyComponentKind,
    StrategyFrictionEvidenceV1,
    StrategyRegime,
)
from omni_cio.contracts.v1.portfolio import InstrumentType
from omni_cio.contracts.v1.portfolio_optimizer import (
    OptimizerAssetV1,
    OptimizerMarketEvidenceV1,
    PortfolioOptimizerResultV1,
)
from omni_cio.contracts.v1.portfolio_plan import (
    PlanMarketObservationV1,
    PortfolioPlanSettingsV1,
    PortfolioPlanV1,
)
from omni_cio.contracts.v1.portfolio_risk import (
    PermanentLossStatus,
    PortfolioRiskAssessmentV1,
    PortfolioRiskInputV1,
    PositionCreditRiskInputV1,
    PositionLiquidityRiskInputV1,
    PositionPermanentLossInputV1,
    RiskExposureDimension,
    RiskExposureMode,
    RiskExposureSliceV1,
    RiskPositionV1,
)
from omni_cio.optimizer import optimize_portfolio
from omni_cio.plans import build_portfolio_plan
from omni_cio.policy import assess_investment_policy
from omni_cio.risk import assess_portfolio_risk
from omni_cio.strategy import select_meta_strategy


NOW = datetime(2026, 8, 4, 10, 0, tzinfo=timezone.utc)
EFFECTIVE = datetime(2026, 1, 1, tzinfo=timezone.utc)
REVIEW_DUE = datetime(2026, 12, 31, tzinfo=timezone.utc)
SNAPSHOT_SHA = "1" * 64

_REQUIRED_FIELDS = (
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


@dataclass(frozen=True)
class PlanFixture:
    policy: InvestmentPolicyStatementV1
    assessment: InvestmentPolicyAssessmentV1
    portfolio: PortfolioRiskInputV1
    current_risk: PortfolioRiskAssessmentV1
    strategy: MetaStrategySelectionV1
    optimizer: PortfolioOptimizerResultV1
    assets: tuple[OptimizerAssetV1, ...]
    plan: PortfolioPlanV1


def _provenance() -> tuple[PolicyFieldProvenanceV1, ...]:
    return tuple(
        PolicyFieldProvenanceV1(
            field=field,
            source_kind=(
                PolicySourceKind.VERIFIED_ACCOUNT_DATA
                if field is PolicyField.ACCOUNT_TYPE
                else PolicySourceKind.OWNER_INPUT
            ),
            owner_confirmed=field is not PolicyField.ACCOUNT_TYPE,
            confirmed_at=EFFECTIVE,
            source_id=(
                "masked-account-fact"
                if field is PolicyField.ACCOUNT_TYPE
                else f"owner-{field.value}"
            ),
        )
        for field in _REQUIRED_FIELDS
    )


def policy() -> InvestmentPolicyStatementV1:
    return InvestmentPolicyStatementV1(
        policy_id="ips_owner_plan_v9",
        version="1",
        lifecycle=PolicyLifecycle.ACTIVE,
        created_at=EFFECTIVE,
        effective_at=EFFECTIVE,
        review_due_at=REVIEW_DUE,
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
        max_position_weight=Decimal("0.50"),
        max_group_weight=Decimal("0.80"),
        max_sector_weight=Decimal("0.80"),
        max_currency_weight=Decimal("0.95"),
        minimum_credit_rating="A-",
        credit_rating_scale="AKRA_RU",
        allowed_markets=("MOEX",),
        allowed_instrument_types=(InstrumentType.SHARE, InstrumentType.BOND),
        prohibited_instrument_types=(
            InstrumentType.FUTURE,
            InstrumentType.OPTION,
            InstrumentType.STRUCTURED_PRODUCT,
        ),
        tax_constraint_status=TaxConstraintStatus.REVIEWED,
        account_type=AccountPolicyType.BROKERAGE,
        rebalance_band_weight=Decimal("0.05"),
        provenance=_provenance(),
    )


def _exposures(kind: str, issuer: str) -> tuple[RiskExposureSliceV1, ...]:
    return (
        RiskExposureSliceV1(
            dimension=RiskExposureDimension.ISSUER,
            bucket_key=issuer,
            weight_within_position=Decimal("1"),
        ),
        RiskExposureSliceV1(
            dimension=RiskExposureDimension.GROUP,
            bucket_key=f"group_{issuer}",
            weight_within_position=Decimal("1"),
        ),
        RiskExposureSliceV1(
            dimension=RiskExposureDimension.SECTOR,
            bucket_key="fixed_income" if kind == "bond" else "equity",
            weight_within_position=Decimal("1"),
        ),
        RiskExposureSliceV1(
            dimension=RiskExposureDimension.ASSET_CLASS,
            bucket_key=kind,
            weight_within_position=Decimal("1"),
        ),
        RiskExposureSliceV1(
            dimension=RiskExposureDimension.CURRENCY,
            bucket_key="RUB",
            weight_within_position=Decimal("1"),
        ),
    )


def _position(
    *,
    stable_key: str,
    instrument_type: InstrumentType,
    value: Decimal,
    issuer: str,
) -> RiskPositionV1:
    credit = (
        PositionCreditRiskInputV1(
            credit_passport_sha256="c" * 64,
            decision_ready=True,
            policy_floor_passed=True,
            active_default_event=False,
        )
        if instrument_type is InstrumentType.BOND
        else None
    )
    return RiskPositionV1(
        stable_key=stable_key,
        instrument_type=instrument_type,
        native_currency="RUB",
        native_market_value=value,
        base_currency="RUB",
        base_market_value=value,
        exposure_mode=RiskExposureMode.DIRECT,
        exposures=_exposures(instrument_type.value, issuer),
        liquidity=PositionLiquidityRiskInputV1(
            daily_exit_capacity_base=Decimal("5000000"),
            spread_bps=Decimal("20"),
            as_of=NOW,
            source_sha256="d" * 64,
        ),
        credit=credit,
        permanent_loss=PositionPermanentLossInputV1(
            status=PermanentLossStatus.PASS,
            evidence_sha256s=("e" * 64,),
        ),
    )


def _market(
    stable_key: str,
    clean_price: Decimal,
    source: str,
    *,
    accrued_interest: Decimal | None = None,
    turnover: Decimal = Decimal("5000000"),
    depth: Decimal = Decimal("1000000"),
) -> OptimizerMarketEvidenceV1:
    return OptimizerMarketEvidenceV1(
        stable_key=stable_key,
        as_of=NOW,
        source_sha256=source,
        clean_unit_price_base=clean_price,
        accrued_interest_per_lot_base=accrued_interest,
        spread_bps=Decimal("20"),
        average_daily_turnover_base=turnover,
        top_of_book_depth_base=depth,
    )


def build_fixture(
    *,
    plan_settings: PortfolioPlanSettingsV1 | None = None,
) -> PlanFixture:
    ips = policy()
    assessment = assess_investment_policy(ips, assessed_at=NOW)
    assert assessment.ready_for_personal_sizing

    bond = _position(
        stable_key="bond:QUALITY-1",
        instrument_type=InstrumentType.BOND,
        value=Decimal("350000"),
        issuer="issuer_quality",
    )
    share = _position(
        stable_key="share:CORE-1",
        instrument_type=InstrumentType.SHARE,
        value=Decimal("350000"),
        issuer="issuer_core",
    )
    portfolio = PortfolioRiskInputV1(
        portfolio_snapshot_sha256=SNAPSHOT_SHA,
        policy_reference=assessment.reference,
        base_currency="RUB",
        cash_base=Decimal("300000"),
        positions=(bond, share),
    )
    current_risk = assess_portfolio_risk(
        portfolio=portfolio,
        policy=ips,
        policy_assessment=assessment,
        assessed_at=NOW,
    )
    assert current_risk.plan_eligible

    friction = tuple(
        StrategyFrictionEvidenceV1(
            regime=regime,
            transition_cost_weight=Decimal("0.003"),
            tax_cost_weight=Decimal("0.001"),
            as_of=NOW,
            source_sha256s=(source,),
        )
        for regime, source in (
            (StrategyRegime.CAPITAL_PRESERVATION, "a" * 64),
            (StrategyRegime.DEFENSIVE_BALANCED, "b" * 64),
            (StrategyRegime.BALANCED_CORE, "f" * 64),
            (StrategyRegime.GROWTH_CORE, "9" * 64),
        )
    )
    strategy = select_meta_strategy(
        portfolio_snapshot_sha256=SNAPSHOT_SHA,
        policy=ips,
        policy_assessment=assessment,
        risk=current_risk,
        friction_evidence=friction,
        selected_at=NOW,
    )
    assert strategy.selected_regime is StrategyRegime.DEFENSIVE_BALANCED

    assets = (
        OptimizerAssetV1(
            stable_key=bond.stable_key,
            component=StrategyComponentKind.QUALITY_DEBT,
            current_lots=350,
            lot_size=1,
            native_currency="RUB",
            base_currency="RUB",
            unit_full_value_native=Decimal("1000"),
            unit_full_value_base=Decimal("1000"),
            risk_template=bond,
            account_eligible=True,
            commission_bps=Decimal("10"),
            estimated_sell_tax_bps=Decimal("0"),
            friction_as_of=NOW,
            friction_source_sha256s=("1" * 64,),
            market_evidence=_market(
                bond.stable_key,
                Decimal("1000"),
                "2" * 64,
                accrued_interest=Decimal("0"),
            ),
        ),
        OptimizerAssetV1(
            stable_key=share.stable_key,
            component=StrategyComponentKind.DIVERSIFIED_CORE,
            current_lots=3500,
            lot_size=1,
            native_currency="RUB",
            base_currency="RUB",
            unit_full_value_native=Decimal("100"),
            unit_full_value_base=Decimal("100"),
            risk_template=share,
            account_eligible=True,
            commission_bps=Decimal("10"),
            estimated_sell_tax_bps=Decimal("0"),
            friction_as_of=NOW,
            friction_source_sha256s=("3" * 64,),
            market_evidence=_market(
                share.stable_key,
                Decimal("100"),
                "4" * 64,
                turnover=Decimal("10000000"),
                depth=Decimal("2000000"),
            ),
        ),
    )
    optimizer = optimize_portfolio(
        portfolio=portfolio,
        policy=ips,
        policy_assessment=assessment,
        current_risk=current_risk,
        strategy=strategy,
        assets=assets,
        optimized_at=NOW,
    )
    assert optimizer.plan_eligible

    plan = build_portfolio_plan(
        portfolio=portfolio,
        policy=ips,
        policy_assessment=assessment,
        current_risk=current_risk,
        strategy=strategy,
        optimizer=optimizer,
        optimizer_assets=assets,
        settings=plan_settings,
        created_at=NOW,
    )
    return PlanFixture(
        policy=ips,
        assessment=assessment,
        portfolio=portfolio,
        current_risk=current_risk,
        strategy=strategy,
        optimizer=optimizer,
        assets=assets,
        plan=plan,
    )


def build_no_action_fixture() -> PlanFixture:
    payload = policy().model_dump(mode="python")
    payload.update(
        objective=InvestmentObjective.INCOME,
        risk_willingness=RiskLevel.LOW,
        risk_capacity=RiskLevel.LOW,
        allowed_instrument_types=(InstrumentType.SHARE,),
    )
    ips = InvestmentPolicyStatementV1.model_validate(payload)
    assessment = assess_investment_policy(ips, assessed_at=NOW)
    assert assessment.ready_for_personal_sizing

    share = _position(
        stable_key="share:NO-ACTION-CORE",
        instrument_type=InstrumentType.SHARE,
        value=Decimal("400000"),
        issuer="issuer_no_action",
    )
    portfolio = PortfolioRiskInputV1(
        portfolio_snapshot_sha256="5" * 64,
        policy_reference=assessment.reference,
        base_currency="RUB",
        cash_base=Decimal("600000"),
        positions=(share,),
    )
    current_risk = assess_portfolio_risk(
        portfolio=portfolio,
        policy=ips,
        policy_assessment=assessment,
        assessed_at=NOW,
    )
    assert current_risk.plan_eligible

    strategy = select_meta_strategy(
        portfolio_snapshot_sha256=portfolio.portfolio_snapshot_sha256,
        policy=ips,
        policy_assessment=assessment,
        risk=current_risk,
        friction_evidence=(),
        selected_at=NOW,
    )
    assert strategy.decision_ready
    assert strategy.selected_regime is StrategyRegime.NO_ACTION
    assert strategy.optimizer_eligible is False

    assets = (
        OptimizerAssetV1(
            stable_key=share.stable_key,
            component=StrategyComponentKind.DIVERSIFIED_CORE,
            current_lots=4000,
            lot_size=1,
            native_currency="RUB",
            base_currency="RUB",
            unit_full_value_native=Decimal("100"),
            unit_full_value_base=Decimal("100"),
            risk_template=share,
            account_eligible=True,
        ),
    )
    optimizer = optimize_portfolio(
        portfolio=portfolio,
        policy=ips,
        policy_assessment=assessment,
        current_risk=current_risk,
        strategy=strategy,
        assets=assets,
        optimized_at=NOW,
    )
    assert optimizer.optimizer_ready
    assert optimizer.plan_eligible is False
    assert optimizer.legs == ()

    plan = build_portfolio_plan(
        portfolio=portfolio,
        policy=ips,
        policy_assessment=assessment,
        current_risk=current_risk,
        strategy=strategy,
        optimizer=optimizer,
        optimizer_assets=assets,
        created_at=NOW,
    )
    return PlanFixture(
        policy=ips,
        assessment=assessment,
        portfolio=portfolio,
        current_risk=current_risk,
        strategy=strategy,
        optimizer=optimizer,
        assets=assets,
        plan=plan,
    )


def exact_observations(plan: PortfolioPlanV1) -> tuple[PlanMarketObservationV1, ...]:
    return tuple(
        PlanMarketObservationV1(
            stable_key=row.stable_key,
            observed_at=NOW,
            market_source_sha256=row.market_source_sha256,
            clean_unit_price_base=row.clean_unit_price_base,
            accrued_interest_per_lot_base=row.accrued_interest_per_lot_base,
            spread_bps=row.spread_bps,
            average_daily_turnover_base=row.average_daily_turnover_base,
            top_of_book_depth_base=row.top_of_book_depth_base,
            friction_as_of=row.friction_as_of,
            friction_source_sha256s=row.friction_source_sha256s,
            commission_bps=row.commission_bps,
            estimated_sell_tax_bps=row.estimated_sell_tax_bps,
            account_eligible=row.account_eligible,
            fx_rate_to_base=row.fx_rate_to_base,
            fx_source_sha256=row.fx_source_sha256,
            fx_as_of=row.fx_as_of,
        )
        for row in plan.market_baselines
    )
