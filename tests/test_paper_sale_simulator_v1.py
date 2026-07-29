from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.common import (
    AccountReference,
    Completeness,
    ContractMetadata,
    DataQuality,
    Money,
    QualityMetadata,
    SourceReference,
)
from omni_cio.contracts.v1.paper import PaperOrderStatus
from omni_cio.contracts.v1.paper_sell import (
    PaperSaleRejectReason,
    PaperSaleResultV1,
)
from omni_cio.contracts.v1.pretrade import PreviewFreshnessStatus
from omni_cio.contracts.v1.sell_pretrade import (
    SellPreTradeBlocker,
    SellPreTradePreviewV1,
    SellPreviewPriceBasis,
)
from omni_cio.paper import PaperSaleSimulatorError, simulate_paper_sale


NOW = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)


def _metadata() -> ContractMetadata:
    return ContractMetadata(
        schema_name="sell_pretrade_preview",
        retrieved_at=NOW,
        account=AccountReference(masked_id="***3118", account_type="ИИС"),
        provenance=(
            SourceReference(
                provider="omni-cio-test",
                operation="build_sell_pretrade_preview",
                retrieved_at=NOW,
                source_id="1.0",
            ),
        ),
        quality=QualityMetadata(
            quality=DataQuality.VERIFIED,
            completeness=Completeness.COMPLETE,
        ),
    )


def _money(amount: str) -> Money:
    return Money(amount=Decimal(amount), currency="RUB")


def _preview() -> SellPreTradePreviewV1:
    post_weight = Decimal("300") / Decimal("990")
    return SellPreTradePreviewV1(
        metadata=_metadata(),
        stable_key="uid:asset-a",
        instrument_uid="asset-a",
        currency="RUB",
        price_basis=SellPreviewPriceBasis.BEST_BID,
        price_source="T-Invest GetOrderBook best bid",
        price_time=NOW - timedelta(seconds=30),
        evaluated_at=NOW,
        price_age_seconds=Decimal("30"),
        max_price_age_seconds=Decimal("120"),
        freshness_status=PreviewFreshnessStatus.FRESH,
        unit_price=Decimal("98"),
        lot_size=1,
        quantity_lots=2,
        quantity_units=2,
        position_lots=5,
        sell_max_lots=5,
        conflicting_open_sell_lots=0,
        available_after_open_orders_lots=5,
        remaining_position_lots=3,
        current_position_value=_money("500"),
        sold_position_value=_money("200"),
        gross_security_proceeds=_money("196"),
        accrued_interest_proceeds=_money("4"),
        gross_proceeds=_money("200"),
        canonical_commission=_money("2"),
        estimated_tax=_money("8"),
        net_proceeds=_money("190"),
        estimated_post_sale_position_value=_money("300"),
        estimated_portfolio_value_before=_money("1000"),
        estimated_portfolio_value_after=_money("990"),
        current_weight=Decimal("0.5"),
        lower_weight=Decimal("0.2"),
        target_weight=Decimal("0.3"),
        upper_weight=Decimal("0.45"),
        estimated_post_sale_weight=post_weight,
        reduction_value_limit=_money("200"),
        tax_basis_confirmed=True,
        open_orders_checked=True,
        position_availability_confirmed=True,
        source_complete=True,
        integrity_confirmed=True,
        blockers=(),
        preview_ready=True,
        no_short_sale=True,
        no_cross_currency_aggregation=True,
        execution_ready=False,
        trading_methods=False,
    )


def _blocked_preview() -> SellPreTradePreviewV1:
    payload = _preview().model_dump(mode="python")
    payload["source_complete"] = False
    payload["blockers"] = (SellPreTradeBlocker.SOURCE_INCOMPLETE,)
    payload["preview_ready"] = False
    return SellPreTradePreviewV1.model_validate(payload)


def test_full_paper_sale_increases_cash_and_reduces_position() -> None:
    result = simulate_paper_sale(
        _preview(),
        scenario_id="paper.sale.full",
        fill_lots=2,
        paper_cash=Decimal("1000"),
        position_lots=5,
        simulated_at=NOW,
    )

    assert result.status == PaperOrderStatus.FILLED
    assert result.filled_lots == 2
    assert result.unfilled_lots == 0
    assert result.gross_security_proceeds.amount == Decimal("196")
    assert result.accrued_interest_proceeds.amount == Decimal("4")
    assert result.gross_proceeds.amount == Decimal("200")
    assert result.commission.amount == Decimal("2")
    assert result.estimated_tax.amount == Decimal("8")
    assert result.net_proceeds.amount == Decimal("190")
    assert result.paper_cash_after.amount == Decimal("1190")
    assert result.position_lots_after == 3
    assert result.paper_only is True
    assert result.broker_order_created is False
    assert result.execution_ready is False
    assert result.trading_methods is False


def test_partial_paper_sale_allocates_costs_proportionally() -> None:
    result = simulate_paper_sale(
        _preview(),
        scenario_id="paper.sale.partial",
        fill_lots=1,
        paper_cash=Decimal("1000"),
        position_lots=5,
        simulated_at=NOW,
    )

    assert result.status == PaperOrderStatus.PARTIALLY_FILLED
    assert result.filled_lots == 1
    assert result.unfilled_lots == 1
    assert result.gross_security_proceeds.amount == Decimal("98.000000000")
    assert result.accrued_interest_proceeds.amount == Decimal("2.000000000")
    assert result.commission.amount == Decimal("1.000000000")
    assert result.estimated_tax.amount == Decimal("4.000000000")
    assert result.net_proceeds.amount == Decimal("95.000000000")
    assert result.paper_cash_after.amount == Decimal("1095.000000000")
    assert result.position_lots_after == 4


def test_blocked_preview_rejects_without_state_change() -> None:
    result = simulate_paper_sale(
        _blocked_preview(),
        scenario_id="paper.sale.blocked",
        fill_lots=2,
        paper_cash=Decimal("1000"),
        position_lots=5,
        simulated_at=NOW,
    )

    assert result.status == PaperOrderStatus.REJECTED
    assert PaperSaleRejectReason.PREVIEW_NOT_READY in result.reject_reasons
    assert result.net_proceeds.amount == 0
    assert result.paper_cash_after == result.paper_cash_before
    assert result.position_lots_after == result.position_lots_before


def test_invalid_or_excess_fill_is_rejected() -> None:
    invalid = simulate_paper_sale(
        _preview(),
        scenario_id="paper.sale.invalid",
        fill_lots=0,
        paper_cash=Decimal("1000"),
        position_lots=5,
        simulated_at=NOW,
    )
    assert PaperSaleRejectReason.INVALID_FILL_LOTS in invalid.reject_reasons

    excess = simulate_paper_sale(
        _preview(),
        scenario_id="paper.sale.excess",
        fill_lots=3,
        paper_cash=Decimal("1000"),
        position_lots=5,
        simulated_at=NOW,
    )
    assert PaperSaleRejectReason.FILL_EXCEEDS_REQUESTED in excess.reject_reasons
    assert excess.position_lots_after == 5


def test_position_state_mismatch_and_insufficient_position_are_fail_closed() -> None:
    mismatch = simulate_paper_sale(
        _preview(),
        scenario_id="paper.sale.state_mismatch",
        fill_lots=2,
        paper_cash=Decimal("1000"),
        position_lots=4,
        simulated_at=NOW,
    )
    assert PaperSaleRejectReason.POSITION_STATE_MISMATCH in mismatch.reject_reasons
    assert mismatch.position_lots_after == 4

    insufficient = simulate_paper_sale(
        _preview(),
        scenario_id="paper.sale.insufficient",
        fill_lots=2,
        paper_cash=Decimal("1000"),
        position_lots=1,
        simulated_at=NOW,
    )
    assert (
        PaperSaleRejectReason.INSUFFICIENT_PAPER_POSITION
        in insufficient.reject_reasons
    )
    assert insufficient.position_lots_after == 1


def test_invalid_paper_state_raises_before_simulation() -> None:
    with pytest.raises(PaperSaleSimulatorError, match="INVALID_PAPER_SALE_CASH"):
        simulate_paper_sale(
            _preview(),
            scenario_id="paper.sale.negative_cash",
            fill_lots=1,
            paper_cash=Decimal("-1"),
            position_lots=5,
            simulated_at=NOW,
        )

    with pytest.raises(
        PaperSaleSimulatorError,
        match="INVALID_PAPER_SALE_POSITION_LOTS",
    ):
        simulate_paper_sale(
            _preview(),
            scenario_id="paper.sale.negative_position",
            fill_lots=1,
            paper_cash=Decimal("1000"),
            position_lots=-1,
            simulated_at=NOW,
        )


def test_contract_rejects_tampered_sale_arithmetic() -> None:
    result = simulate_paper_sale(
        _preview(),
        scenario_id="paper.sale.tamper",
        fill_lots=2,
        paper_cash=Decimal("1000"),
        position_lots=5,
        simulated_at=NOW,
    )
    payload = result.model_dump(mode="python")
    payload["paper_cash_after"]["amount"] = Decimal("9999")

    with pytest.raises(ValidationError, match="paper sale cash"):
        PaperSaleResultV1.model_validate(payload)


def test_simulation_is_deterministic_and_does_not_mutate_preview() -> None:
    preview = _preview()
    preview_before = preview.model_copy(deep=True)
    first = simulate_paper_sale(
        preview,
        scenario_id="paper.sale.deterministic",
        fill_lots=1,
        paper_cash=Decimal("1000"),
        position_lots=5,
        simulated_at=NOW,
    )
    second = simulate_paper_sale(
        preview,
        scenario_id="paper.sale.deterministic",
        fill_lots=1,
        paper_cash=Decimal("1000"),
        position_lots=5,
        simulated_at=NOW,
    )

    assert first == second
    assert preview == preview_before


def test_paper_sale_has_no_network_or_broker_execution_surface() -> None:
    source = Path("omni_cio/paper/sell_simulator_v1.py").read_text(
        encoding="utf-8"
    )
    lowered = source.casefold()
    assert "requests" not in lowered
    assert "httpx" not in lowered
    assert "grpc" not in lowered
    assert "t_tech.invest" not in lowered
    assert "trading_methods=true" not in lowered
