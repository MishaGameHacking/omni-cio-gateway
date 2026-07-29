from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN

from omni_cio.contracts.v1.common import (
    Completeness,
    ContractMetadata,
    DataIssue,
    DataQuality,
    IssueSeverity,
    Money,
    QualityMetadata,
    SourceReference,
)
from omni_cio.contracts.v1.paper import (
    PaperJournalEventKind,
    PaperJournalEventV1,
    PaperOrderStatus,
)
from omni_cio.contracts.v1.paper_sell import (
    PaperSaleRejectReason,
    PaperSaleResultV1,
)
from omni_cio.contracts.v1.sell_pretrade import SellPreTradePreviewV1


_ALLOCATION_QUANTUM = Decimal("0.000000001")


class PaperSaleSimulatorError(ValueError):
    """The requested paper sale cannot be represented safely."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise PaperSaleSimulatorError("PAPER_SALE_TIMESTAMP_MUST_BE_AWARE")
    return result.astimezone(timezone.utc)


def _non_negative_decimal(value: Decimal, code: str) -> Decimal:
    if not value.is_finite() or value < 0:
        raise PaperSaleSimulatorError(code)
    return value


def _non_negative_int(value: int, code: str) -> int:
    if isinstance(value, bool) or value < 0:
        raise PaperSaleSimulatorError(code)
    return value


def _allocated(full_amount: Decimal, filled_lots: int, requested_lots: int) -> Decimal:
    if filled_lots == requested_lots:
        return full_amount
    ratio = Decimal(filled_lots) / Decimal(requested_lots)
    return (full_amount * ratio).quantize(
        _ALLOCATION_QUANTUM,
        rounding=ROUND_HALF_EVEN,
    )


def _zero(currency: str) -> Money:
    return Money(amount=Decimal("0"), currency=currency)


def _metadata(
    preview: SellPreTradePreviewV1,
    simulated_at: datetime,
    reject_reasons: tuple[PaperSaleRejectReason, ...],
) -> ContractMetadata:
    preview_blocked = PaperSaleRejectReason.PREVIEW_NOT_READY in reject_reasons
    issues = tuple(
        DataIssue(
            code=f"PAPER_SALE_{reason.value.upper()}",
            severity=(
                IssueSeverity.ERROR
                if reason
                in {
                    PaperSaleRejectReason.PREVIEW_NOT_READY,
                    PaperSaleRejectReason.POSITION_STATE_MISMATCH,
                }
                else IssueSeverity.INFO
            ),
            message=f"Paper sale rejected: {reason.value}.",
            component="paper_sale_simulator",
        )
        for reason in reject_reasons
    )
    return ContractMetadata(
        schema_name="paper_sale_result",
        retrieved_at=simulated_at,
        account=preview.metadata.account,
        provenance=(
            *preview.metadata.provenance,
            SourceReference(
                provider="omni-cio",
                operation="simulate_paper_sale",
                retrieved_at=simulated_at,
                source_id="1.0",
            ),
        ),
        quality=QualityMetadata(
            quality=DataQuality.DEGRADED if preview_blocked else DataQuality.VERIFIED,
            completeness=(
                Completeness.INCOMPLETE if preview_blocked else Completeness.COMPLETE
            ),
            issues=issues,
            warnings=(
                "Paper-only sale result; no broker order is created or transmitted.",
                "Tax and commission are allocated proportionally from the source sell preview.",
            ),
        ),
    )


def simulate_paper_sale(
    preview: SellPreTradePreviewV1,
    *,
    scenario_id: str,
    fill_lots: int,
    paper_cash: Decimal,
    position_lots: int,
    simulated_at: datetime | None = None,
) -> PaperSaleResultV1:
    """Simulate one sale outcome without broker or network interaction."""

    event_time = _aware_utc(simulated_at)
    cash_before_amount = _non_negative_decimal(
        paper_cash,
        "INVALID_PAPER_SALE_CASH",
    )
    position_before = _non_negative_int(
        position_lots,
        "INVALID_PAPER_SALE_POSITION_LOTS",
    )

    requested_lots = preview.quantity_lots
    lot_size = preview.lot_size
    if requested_lots is None or requested_lots <= 0:
        raise PaperSaleSimulatorError("PAPER_SALE_PREVIEW_MISSING_REQUESTED_LOTS")
    if lot_size is None or lot_size <= 0:
        raise PaperSaleSimulatorError("PAPER_SALE_PREVIEW_MISSING_LOT_SIZE")

    currency = preview.currency
    reject_reasons: list[PaperSaleRejectReason] = []
    if not preview.preview_ready:
        reject_reasons.append(PaperSaleRejectReason.PREVIEW_NOT_READY)
    if isinstance(fill_lots, bool) or fill_lots <= 0:
        reject_reasons.append(PaperSaleRejectReason.INVALID_FILL_LOTS)
    elif fill_lots > requested_lots:
        reject_reasons.append(PaperSaleRejectReason.FILL_EXCEEDS_REQUESTED)
    if preview.position_lots is not None and position_before != preview.position_lots:
        reject_reasons.append(PaperSaleRejectReason.POSITION_STATE_MISMATCH)
    if not isinstance(fill_lots, bool) and fill_lots > position_before:
        reject_reasons.append(PaperSaleRejectReason.INSUFFICIENT_PAPER_POSITION)

    critical_amounts = (
        preview.gross_security_proceeds,
        preview.gross_proceeds,
        preview.canonical_commission,
        preview.estimated_tax,
        preview.net_proceeds,
    )
    if preview.preview_ready and any(value is None for value in critical_amounts):
        raise PaperSaleSimulatorError("READY_SELL_PREVIEW_MISSING_CRITICAL_AMOUNT")

    candidate_security = Decimal("0")
    candidate_accrued_interest = Decimal("0")
    candidate_commission = Decimal("0")
    candidate_tax = Decimal("0")
    candidate_gross = Decimal("0")
    candidate_net = Decimal("0")
    if not reject_reasons:
        assert preview.gross_security_proceeds is not None
        assert preview.canonical_commission is not None
        assert preview.estimated_tax is not None
        candidate_security = _allocated(
            preview.gross_security_proceeds.amount,
            fill_lots,
            requested_lots,
        )
        if preview.accrued_interest_proceeds is not None:
            candidate_accrued_interest = _allocated(
                preview.accrued_interest_proceeds.amount,
                fill_lots,
                requested_lots,
            )
        candidate_commission = _allocated(
            preview.canonical_commission.amount,
            fill_lots,
            requested_lots,
        )
        candidate_tax = _allocated(
            preview.estimated_tax.amount,
            fill_lots,
            requested_lots,
        )
        candidate_gross = candidate_security + candidate_accrued_interest
        candidate_net = candidate_gross - candidate_commission - candidate_tax
        if candidate_net < 0:
            raise PaperSaleSimulatorError("PAPER_SALE_NET_PROCEEDS_NEGATIVE")

    reason_tuple = tuple(dict.fromkeys(reject_reasons))
    cash_before = Money(amount=cash_before_amount, currency=currency)
    journal: tuple[PaperJournalEventV1, ...]
    if reason_tuple:
        status = PaperOrderStatus.REJECTED
        actual_filled_lots = 0
        gross_security = _zero(currency)
        accrued_interest = _zero(currency)
        gross = _zero(currency)
        commission = _zero(currency)
        estimated_tax = _zero(currency)
        net = _zero(currency)
        cash_after = cash_before
        position_after = position_before
        journal = (
            PaperJournalEventV1(
                sequence=1,
                occurred_at=event_time,
                kind=PaperJournalEventKind.REJECTED,
                message=(
                    "Paper sale rejected without changing simulated cash or position."
                ),
            ),
        )
    else:
        actual_filled_lots = fill_lots
        status = (
            PaperOrderStatus.FILLED
            if fill_lots == requested_lots
            else PaperOrderStatus.PARTIALLY_FILLED
        )
        gross_security = Money(amount=candidate_security, currency=currency)
        accrued_interest = Money(
            amount=candidate_accrued_interest,
            currency=currency,
        )
        gross = Money(amount=candidate_gross, currency=currency)
        commission = Money(amount=candidate_commission, currency=currency)
        estimated_tax = Money(amount=candidate_tax, currency=currency)
        net = Money(amount=candidate_net, currency=currency)
        cash_after = Money(
            amount=cash_before_amount + candidate_net,
            currency=currency,
        )
        position_after = position_before - fill_lots
        journal = (
            PaperJournalEventV1(
                sequence=1,
                occurred_at=event_time,
                kind=PaperJournalEventKind.ACCEPTED,
                message="Paper sale accepted by the offline simulator.",
            ),
            PaperJournalEventV1(
                sequence=2,
                occurred_at=event_time,
                kind=PaperJournalEventKind.FILL,
                message=(
                    f"Paper sale fill recorded for {fill_lots} of "
                    f"{requested_lots} lots."
                ),
            ),
        )

    return PaperSaleResultV1(
        metadata=_metadata(preview, event_time, reason_tuple),
        scenario_id=scenario_id,
        source_preview_schema_version=preview.metadata.schema_version,
        stable_key=preview.stable_key,
        instrument_uid=preview.instrument_uid,
        currency=currency,
        status=status,
        reject_reasons=reason_tuple,
        requested_lots=requested_lots,
        filled_lots=actual_filled_lots,
        unfilled_lots=requested_lots - actual_filled_lots,
        lot_size=lot_size,
        filled_units=actual_filled_lots * lot_size,
        gross_security_proceeds=gross_security,
        accrued_interest_proceeds=accrued_interest,
        gross_proceeds=gross,
        commission=commission,
        estimated_tax=estimated_tax,
        net_proceeds=net,
        paper_cash_before=cash_before,
        paper_cash_after=cash_after,
        position_lots_before=position_before,
        position_lots_after=position_after,
        journal=journal,
        paper_only=True,
        broker_order_created=False,
        execution_ready=False,
        trading_methods=False,
    )
