from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from omni_cio.contracts.v1.meta_strategy import StrategyComponentKind
from omni_cio.contracts.v1.portfolio import InstrumentType
from omni_cio.contracts.v1.portfolio_optimizer import (
    OptimizerAssetV1,
    OptimizerMarketEvidenceV1,
    PortfolioOptimizerSettingsV1,
)
from omni_cio.contracts.v1.portfolio_risk import (
    PermanentLossStatus,
    PositionPermanentLossInputV1,
    RiskExposureDimension,
    RiskExposureMode,
    RiskExposureSliceV1,
    RiskPositionV1,
)
from omni_cio.optimizer.engine_v1 import _build_legs


AS_OF = datetime(2026, 8, 4, 10, 0, tzinfo=timezone.utc)


def _asset(stable_key: str, source_digit: str) -> OptimizerAssetV1:
    position = RiskPositionV1(
        stable_key=stable_key,
        instrument_type=InstrumentType.SHARE,
        native_currency="RUB",
        native_market_value=Decimal("100"),
        base_currency="RUB",
        base_market_value=Decimal("100"),
        exposure_mode=RiskExposureMode.DIRECT,
        exposures=(
            RiskExposureSliceV1(
                dimension=RiskExposureDimension.ASSET_CLASS,
                bucket_key="share",
                weight_within_position=Decimal("1"),
            ),
        ),
        permanent_loss=PositionPermanentLossInputV1(
            status=PermanentLossStatus.PASS,
        ),
    )
    return OptimizerAssetV1(
        stable_key=stable_key,
        component=StrategyComponentKind.DIVERSIFIED_CORE,
        current_lots=1,
        lot_size=1,
        native_currency="RUB",
        base_currency="RUB",
        unit_full_value_native=Decimal("100"),
        unit_full_value_base=Decimal("100"),
        risk_template=position,
        account_eligible=True,
        commission_bps=Decimal("10"),
        estimated_sell_tax_bps=Decimal("0"),
        friction_as_of=AS_OF,
        friction_source_sha256s=(source_digit * 64,),
        market_evidence=OptimizerMarketEvidenceV1(
            stable_key=stable_key,
            as_of=AS_OF,
            source_sha256=("f" if source_digit != "f" else "e") * 64,
            clean_unit_price_base=Decimal("100"),
            spread_bps=Decimal("10"),
            average_daily_turnover_base=Decimal("1000000"),
            top_of_book_depth_base=Decimal("100000"),
        ),
    )


def test_multi_leg_builder_returns_canonical_trade_id_order() -> None:
    # These keys normalize to the same slug but have different SHA suffixes.
    slash = _asset("a/zz", "1")
    colon = _asset("a:zz", "2")
    assets = tuple(sorted((slash, colon), key=lambda row: row.stable_key))

    legs = _build_legs(
        assets=assets,
        target_lots={"a/zz": 2, "a:zz": 2},
        settings=PortfolioOptimizerSettingsV1(),
    )

    trade_ids = tuple(row.trade_id for row in legs)
    assert trade_ids == tuple(sorted(trade_ids))
    assert len(set(trade_ids)) == 2
