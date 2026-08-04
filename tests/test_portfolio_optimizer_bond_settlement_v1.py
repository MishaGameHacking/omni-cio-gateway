from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from omni_cio.contracts.v1.meta_strategy import StrategyComponentKind
from omni_cio.contracts.v1.portfolio import InstrumentType
from omni_cio.contracts.v1.portfolio_optimizer import (
    OptimizerAssetV1,
    OptimizerMarketEvidenceV1,
    OptimizerTradeSide,
    PortfolioOptimizerSettingsV1,
)
from omni_cio.contracts.v1.portfolio_risk import (
    PermanentLossStatus,
    PositionCreditRiskInputV1,
    PositionPermanentLossInputV1,
    RiskExposureDimension,
    RiskExposureMode,
    RiskExposureSliceV1,
    RiskPositionV1,
)
from omni_cio.optimizer.engine_v1 import _leg, _risk_position_for_target


AS_OF = datetime(2026, 8, 4, 10, 0, tzinfo=timezone.utc)


def _bond_asset() -> OptimizerAssetV1:
    position = RiskPositionV1(
        stable_key="bond:ACI-1",
        instrument_type=InstrumentType.BOND,
        native_currency="RUB",
        native_market_value=Decimal("1005"),
        base_currency="RUB",
        base_market_value=Decimal("1005"),
        exposure_mode=RiskExposureMode.DIRECT,
        exposures=(
            RiskExposureSliceV1(
                dimension=RiskExposureDimension.ASSET_CLASS,
                bucket_key="bond",
                weight_within_position=Decimal("1"),
            ),
        ),
        credit=PositionCreditRiskInputV1(
            credit_passport_sha256="a" * 64,
            decision_ready=True,
            policy_floor_passed=True,
            active_default_event=False,
        ),
        permanent_loss=PositionPermanentLossInputV1(
            status=PermanentLossStatus.PASS,
        ),
    )
    return OptimizerAssetV1(
        stable_key=position.stable_key,
        component=StrategyComponentKind.QUALITY_DEBT,
        current_lots=1,
        lot_size=1,
        native_currency="RUB",
        base_currency="RUB",
        unit_full_value_native=Decimal("1005"),
        unit_full_value_base=Decimal("1005"),
        risk_template=position,
        account_eligible=True,
        commission_bps=Decimal("10"),
        estimated_sell_tax_bps=Decimal("0"),
        friction_as_of=AS_OF,
        friction_source_sha256s=("b" * 64,),
        market_evidence=OptimizerMarketEvidenceV1(
            stable_key=position.stable_key,
            as_of=AS_OF,
            source_sha256="c" * 64,
            clean_unit_price_base=Decimal("1000"),
            accrued_interest_per_lot_base=Decimal("5"),
            spread_bps=Decimal("10"),
            average_daily_turnover_base=Decimal("1000000"),
            top_of_book_depth_base=Decimal("100000"),
        ),
    )


def test_bond_buy_separates_clean_gross_aci_and_full_value() -> None:
    asset = _bond_asset()

    leg = _leg(
        asset=asset,
        target_lots=2,
        settings=PortfolioOptimizerSettingsV1(),
    )
    target = _risk_position_for_target(asset, 2)

    assert leg.side is OptimizerTradeSide.BUY
    assert leg.reference_clean_unit_price_base == Decimal("1000")
    assert leg.gross_notional_base == Decimal("1000")
    assert leg.accrued_interest_per_lot_base == Decimal("5")
    assert leg.accrued_interest_base == Decimal("5")
    assert leg.settlement_notional_base == Decimal("1005")
    assert leg.commission_base == Decimal("1.00")
    assert leg.cash_delta_base == Decimal("-1006.00")
    assert target is not None
    assert target.base_market_value == Decimal("2010")
    assert target.native_market_value == Decimal("2010")
