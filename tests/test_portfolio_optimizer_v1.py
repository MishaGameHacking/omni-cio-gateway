from __future__ import annotations

from dataclasses import dataclass
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
from omni_cio.contracts.v1.meta_strategy import (
    MetaStrategySelectionV1,
    StrategyComponentKind,
    StrategyFrictionEvidenceV1,
    StrategyRegime,
)
from omni_cio.contracts.v1.portfolio import InstrumentType
from omni_cio.contracts.v1.portfolio_optimizer import (
    OptimizerAssetV1,
    OptimizerBlockerCode,
    OptimizerMarketEvidenceV1,
    OptimizerScenarioKind,
    OptimizerTradeSide,
    OptimizerWarningCode,
    PortfolioOptimizerResultV1,
    PortfolioOptimizerSettingsV1,
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
from omni_cio.policy import assess_investment_policy
from omni_cio.risk import assess_portfolio_risk
from omni_cio.strategy import select_meta_strategy


ASSESS_AT = datetime(2026, 8, 4, 10, 0, tzinfo=timezone.utc)
EFFECTIVE = datetime(2026, 1, 1, tzinfo=timezone.utc)
REVIEW_DUE = datetime(2026, 12, 31, tzinfo=timezone.utc)
SNAPSHOT_SHA = "1" * 64

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


@dataclass(frozen=True)
class BaseInputs:
    policy: InvestmentPolicyStatementV1
    assessment: InvestmentPolicyAssessmentV1
    portfolio: PortfolioRiskInputV1
    risk: PortfolioRiskAssessmentV1
    strategy: MetaStrategySelectionV1
    assets: tuple[OptimizerAssetV1, ...]


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
        "policy_id": "ips_owner_optimizer_v9",
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


def _exposures(
    *,
    issuer: str,
    group: str,
    sector: str,
    asset_class: str,
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
            bucket_key="RUB",
            weight_within_position=Decimal("1"),
        ),
    )


def _position(
    *,
    stable_key: str,
    instrument_type: InstrumentType,
    market_value: Decimal,
    issuer: str,
    group: str,
    sector: str,
    asset_class: str,
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
        native_market_value=market_value,
        base_currency="RUB",
        base_market_value=market_value,
        exposure_mode=RiskExposureMode.DIRECT,
        exposures=_exposures(
            issuer=issuer,
            group=group,
            sector=sector,
            asset_class=asset_class,
        ),
        liquidity=PositionLiquidityRiskInputV1(
            daily_exit_capacity_base=Decimal("5000000"),
            spread_bps=Decimal("20"),
            as_of=ASSESS_AT,
            source_sha256="d" * 64,
        ),
        credit=credit,
        permanent_loss=PositionPermanentLossInputV1(
            status=PermanentLossStatus.PASS,
            evidence_sha256s=("e" * 64,),
        ),
    )


def _market(
    *,
    stable_key: str,
    clean_price: Decimal,
    source_sha256: str,
    accrued_interest_per_lot: Decimal | None = None,
    average_daily_turnover: Decimal = Decimal("5000000"),
    top_of_book_depth: Decimal = Decimal("1000000"),
    as_of: datetime = ASSESS_AT,
) -> OptimizerMarketEvidenceV1:
    return OptimizerMarketEvidenceV1(
        stable_key=stable_key,
        as_of=as_of,
        source_sha256=source_sha256,
        clean_unit_price_base=clean_price,
        accrued_interest_per_lot_base=accrued_interest_per_lot,
        spread_bps=Decimal("20"),
        average_daily_turnover_base=average_daily_turnover,
        top_of_book_depth_base=top_of_book_depth,
    )


def _base_inputs(
    *,
    policy: InvestmentPolicyStatementV1 | None = None,
) -> BaseInputs:
    policy_value = policy or _policy()
    assessment = assess_investment_policy(
        policy_value,
        assessed_at=ASSESS_AT,
    )
    assert assessment.ready_for_personal_sizing

    bond = _position(
        stable_key="bond:QUALITY-1",
        instrument_type=InstrumentType.BOND,
        market_value=Decimal("350000"),
        issuer="issuer_quality",
        group="group_quality",
        sector="fixed_income",
        asset_class="bond",
    )
    share = _position(
        stable_key="share:CORE-1",
        instrument_type=InstrumentType.SHARE,
        market_value=Decimal("350000"),
        issuer="issuer_core",
        group="group_core",
        sector="equity",
        asset_class="share",
    )
    portfolio = PortfolioRiskInputV1(
        portfolio_snapshot_sha256=SNAPSHOT_SHA,
        policy_reference=assessment.reference,
        base_currency="RUB",
        cash_base=Decimal("300000"),
        positions=(bond, share),
    )
    risk = assess_portfolio_risk(
        portfolio=portfolio,
        policy=policy_value,
        policy_assessment=assessment,
        assessed_at=ASSESS_AT,
    )
    assert risk.decision_ready
    assert risk.after.policy_compliant

    friction = tuple(
        StrategyFrictionEvidenceV1(
            regime=regime,
            transition_cost_weight=Decimal("0.003"),
            tax_cost_weight=Decimal("0.001"),
            as_of=ASSESS_AT,
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
        policy=policy_value,
        policy_assessment=assessment,
        risk=risk,
        friction_evidence=friction,
        selected_at=ASSESS_AT,
    )
    assert strategy.selected_regime is StrategyRegime.DEFENSIVE_BALANCED

    bond_asset = OptimizerAssetV1(
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
        friction_as_of=ASSESS_AT,
        friction_source_sha256s=("1" * 64,),
        market_evidence=_market(
            stable_key=bond.stable_key,
            clean_price=Decimal("1000"),
            accrued_interest_per_lot=Decimal("0"),
            source_sha256="2" * 64,
        ),
    )
    share_asset = OptimizerAssetV1(
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
        friction_as_of=ASSESS_AT,
        friction_source_sha256s=("3" * 64,),
        market_evidence=_market(
            stable_key=share.stable_key,
            clean_price=Decimal("100"),
            source_sha256="4" * 64,
            average_daily_turnover=Decimal("10000000"),
            top_of_book_depth=Decimal("2000000"),
        ),
    )
    return BaseInputs(
        policy=policy_value,
        assessment=assessment,
        portfolio=portfolio,
        risk=risk,
        strategy=strategy,
        assets=(bond_asset, share_asset),
    )


def _target(
    result: PortfolioOptimizerResultV1,
    stable_key: str,
):
    return next(row for row in result.targets if row.stable_key == stable_key)


def _scenario(
    result: PortfolioOptimizerResultV1,
    kind: OptimizerScenarioKind,
):
    return next(row for row in result.scenarios if row.kind is kind)


def _optimize(
    base: BaseInputs,
    *,
    assets: tuple[OptimizerAssetV1, ...] | None = None,
    settings: PortfolioOptimizerSettingsV1 | None = None,
) -> PortfolioOptimizerResultV1:
    return optimize_portfolio(
        portfolio=base.portfolio,
        policy=base.policy,
        policy_assessment=base.assessment,
        current_risk=base.risk,
        strategy=base.strategy,
        assets=assets or base.assets,
        settings=settings,
        optimized_at=ASSESS_AT,
    )


def test_optimizer_builds_lot_executable_target_and_revalidates_wp8() -> None:
    result = _optimize(_base_inputs())

    assert result.optimizer_ready is True
    assert result.plan_eligible is True
    assert result.trading_methods is False
    assert len(result.legs) == 1
    leg = result.legs[0]
    assert leg.side is OptimizerTradeSide.BUY
    assert leg.stable_key == "bond:QUALITY-1"
    assert leg.quantity_lots == 100
    assert leg.gross_notional_base == Decimal("100000")
    assert leg.accrued_interest_base == Decimal("0")
    assert leg.settlement_notional_base == Decimal("100000")
    assert leg.commission_base == Decimal("100.00")
    assert leg.cash_delta_base == Decimal("-100100.00")
    assert leg.partial_fill_aware is True
    assert _target(result, "bond:QUALITY-1").target_lots == 450
    assert result.target_risk_assessment is not None
    assert result.target_risk_assessment.plan_eligible is True
    assert _scenario(result, OptimizerScenarioKind.TARGET).cash_base == Decimal(
        "199900.00"
    )


def test_optimizer_is_source_order_invariant() -> None:
    base = _base_inputs()
    first = _optimize(base)
    reordered = _optimize(base, assets=tuple(reversed(base.assets)))

    assert first.optimizer_sha256 == reordered.optimizer_sha256
    assert first.legs == reordered.legs
    assert first.targets == reordered.targets


def test_large_capital_capacity_scales_target_and_requires_staging() -> None:
    base = _base_inputs()
    bond, share = base.assets
    constrained_bond = bond.model_copy(
        update={
            "market_evidence": _market(
                stable_key=bond.stable_key,
                clean_price=Decimal("1000"),
                accrued_interest_per_lot=Decimal("0"),
                source_sha256="5" * 64,
                average_daily_turnover=Decimal("300000"),
                top_of_book_depth=Decimal("100000"),
            )
        }
    )

    result = _optimize(base, assets=(constrained_bond, share))

    assert result.optimizer_ready is True
    assert OptimizerWarningCode.CAPACITY_SCALED in result.warnings
    assert OptimizerWarningCode.STAGED_EXECUTION_REQUIRED in result.warnings
    assert _target(result, bond.stable_key).target_lots == 425
    leg = result.legs[0]
    assert leg.quantity_lots == 75
    assert leg.required_execution_days == 5


def test_commission_cannot_spend_owner_liquidity_reserve() -> None:
    base = _base_inputs(
        policy=_policy(
            liquidity_reserve=LiquidityReserveV1(
                amount=Decimal("200000"),
                currency="RUB",
            )
        )
    )

    result = _optimize(base)

    assert result.optimizer_ready is True
    assert OptimizerWarningCode.CASH_RESERVE_SCALED_BUYS in result.warnings
    assert _target(result, "bond:QUALITY-1").target_lots == 449
    assert _scenario(result, OptimizerScenarioKind.TARGET).cash_base >= Decimal(
        "200000"
    )


def test_missing_market_evidence_fails_closed_without_assuming_capacity() -> None:
    base = _base_inputs()
    bond, share = base.assets
    missing_market = bond.model_copy(update={"market_evidence": None})

    result = _optimize(base, assets=(missing_market, share))

    assert result.optimizer_ready is False
    assert OptimizerBlockerCode.MARKET_EVIDENCE_MISSING in result.blockers
    assert _target(result, bond.stable_key).target_lots == bond.current_lots
    assert result.plan_eligible is False


def test_missing_friction_evidence_fails_closed_without_zero_fee_assumption() -> None:
    base = _base_inputs()
    bond, share = base.assets
    missing_friction = bond.model_copy(
        update={
            "commission_bps": None,
            "friction_as_of": None,
            "friction_source_sha256s": (),
        }
    )

    result = _optimize(base, assets=(missing_friction, share))

    assert result.optimizer_ready is False
    assert OptimizerBlockerCode.FRICTION_EVIDENCE_MISSING in result.blockers
    assert result.plan_eligible is False


def test_missing_bond_accrued_interest_fails_closed_instead_of_using_zero() -> None:
    base = _base_inputs()
    bond, share = base.assets
    assert bond.market_evidence is not None
    missing_aci_market = bond.market_evidence.model_copy(
        update={"accrued_interest_per_lot_base": None}
    )
    missing_aci = bond.model_copy(update={"market_evidence": missing_aci_market})

    result = _optimize(base, assets=(missing_aci, share))

    assert result.optimizer_ready is False
    assert OptimizerBlockerCode.ACCRUED_INTEREST_EVIDENCE_MISSING in result.blockers
    assert _target(result, bond.stable_key).target_lots == bond.current_lots


def test_market_price_binding_mismatch_fails_closed() -> None:
    base = _base_inputs()
    bond, share = base.assets
    assert bond.market_evidence is not None
    mismatched_market = bond.market_evidence.model_copy(
        update={"clean_unit_price_base": Decimal("999")}
    )
    mismatched = bond.model_copy(update={"market_evidence": mismatched_market})

    result = _optimize(base, assets=(mismatched, share))

    assert result.optimizer_ready is False
    assert OptimizerBlockerCode.MARKET_PRICE_BINDING_MISMATCH in result.blockers
    assert result.plan_eligible is False


def test_stale_market_evidence_blocks_target() -> None:
    base = _base_inputs()
    bond, share = base.assets
    assert bond.market_evidence is not None
    stale_market = bond.market_evidence.model_copy(
        update={"as_of": ASSESS_AT - timedelta(hours=1)}
    )
    stale = bond.model_copy(update={"market_evidence": stale_market})

    result = _optimize(base, assets=(stale, share))

    assert result.optimizer_ready is False
    assert OptimizerBlockerCode.MARKET_EVIDENCE_STALE in result.blockers


def test_wp8_target_sector_breach_blocks_plan_eligibility() -> None:
    base = _base_inputs(
        policy=_policy(
            max_position_weight=Decimal("0.40"),
            max_sector_weight=Decimal("0.40"),
        )
    )

    result = _optimize(base)

    assert result.target_risk_assessment is not None
    assert result.target_risk_assessment.after.policy_compliant is False
    assert OptimizerBlockerCode.TARGET_POLICY_BREACH in result.blockers
    assert result.plan_eligible is False


def test_same_version_policy_mutation_breaks_binding() -> None:
    base = _base_inputs()
    mutated = _policy(max_position_weight=Decimal("0.45"))

    result = optimize_portfolio(
        portfolio=base.portfolio,
        policy=mutated,
        policy_assessment=base.assessment,
        current_risk=base.risk,
        strategy=base.strategy,
        assets=base.assets,
        optimized_at=ASSESS_AT,
    )

    assert result.optimizer_ready is False
    assert OptimizerBlockerCode.POLICY_BINDING_MISMATCH in result.blockers
    assert result.legs == ()


def test_small_capital_skips_candidate_that_cannot_form_meaningful_lot() -> None:
    base = _base_inputs()
    bond, share = base.assets
    candidate_template = _position(
        stable_key="bond:BIG-LOT",
        instrument_type=InstrumentType.BOND,
        market_value=Decimal("0"),
        issuer="issuer_biglot",
        group="group_biglot",
        sector="fixed_income",
        asset_class="bond",
    )
    big_lot = OptimizerAssetV1(
        stable_key=candidate_template.stable_key,
        component=StrategyComponentKind.QUALITY_DEBT,
        current_lots=0,
        lot_size=300,
        native_currency="RUB",
        base_currency="RUB",
        unit_full_value_native=Decimal("1000"),
        unit_full_value_base=Decimal("1000"),
        risk_template=candidate_template,
        account_eligible=True,
        commission_bps=Decimal("10"),
        estimated_sell_tax_bps=Decimal("0"),
        friction_as_of=ASSESS_AT,
        friction_source_sha256s=("6" * 64,),
        market_evidence=_market(
            stable_key=candidate_template.stable_key,
            clean_price=Decimal("1000"),
            accrued_interest_per_lot=Decimal("0"),
            source_sha256="7" * 64,
        ),
    )

    result = _optimize(
        base,
        assets=(bond, share, big_lot),
        settings=PortfolioOptimizerSettingsV1(
            minimum_meaningful_position_weight=Decimal("0.15")
        ),
    )

    assert OptimizerWarningCode.MICROPOSITION_SKIPPED in result.warnings
    assert _target(result, big_lot.stable_key).target_lots == 0
