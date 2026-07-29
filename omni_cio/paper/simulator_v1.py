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
    PaperPurchaseResultV1,
    PaperRejectReason,
)
from omni_cio.contracts.v1.pretrade import PreTradePreviewV1


_ALLOCATION_QUANTUM = Decimal("0.000000001")


class PaperSimulatorError(ValueError):
    """The requested paper scenario cannot be represented safely."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise PaperSimulatorError("PAPER_TIMESTAMP_MUST_BE_AWARE")
    return result.astimezone(timezone.utc)


def _non_negative_decimal(value: Decimal, code: str) -> Decimal:
    if not value.is_finite() or value < 0:
        raise PaperSimulatorError(code)
    return value


def _non_negative_int(value: int, code: str) -> int:
    if isinstance(value, bool) or value < 0:
        raise PaperSimulatorError(code)
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
    preview: PreTradePreviewV1,
    simulated_at: datetime,
    reject_reasons: tuple[PaperRejectReason, ...],
) -> ContractMetadata:
    preview_blocked = PaperRejectReason.PREVIEW_NOT_READY in reject_reasons
    issues = tuple(
        DataIssue(
            code=f"PAPER_{reason.value.upper()}",
            severity=(
                IssueSeverity.ERROR
                if reason == PaperRejectReason.PREVIEW_NOT_READY
                else IssueSeverity.INFO
            ),
            message=f"Paper scenario rejected: {reason.value}.",
            component="paper_simulator",
        )
        for reason in reject_reasons
    )
    return ContractMetadata(
        schema_name="paper_purchase_result",
        retrieved_at=simulated_at,
        account=preview.metadata.account,
        provenance=(
            *preview.metadata.provenance,
            SourceReference(
                provider="omni-cio",
                operation="simulate_paper_purchase",
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
                "Paper-only result; no broker order is created or transmitted.",
            ),
        ),
    )


def simulate_paper_purchase(
    preview: PreTradePreviewV1,
    *,
    scenario_id: str,
    fill_lots: int,
    paper_cash: Decimal,
    position_lots: int = 0,
    simulated_at: datetime | None = None,
) -> PaperPurchaseResultV1:
    """Simulate one purchase outcome without any broker or network interaction."""

    event_time = _aware_utc(simulated_at)
    cash_before_amount = _non_negative_decimal(
        paper_cash,
        "INVALID_PAPER_CASH",
    )
    position_before = _non_negative_int(
        position_lots,
        "INVALID_PAPER_POSITION_LOTS",
    )

    requested_lots = preview.quantity_lots
    lot_size = preview.lot_size
    if requested_lots is None or requested_lots <= 0:
        raise PaperSimulatorError("PAPER_PREVIEW_MISSING_REQUESTED_LOTS")
    if lot_size is None or lot_size <= 0:
        raise PaperSimulatorError("PAPER_PREVIEW_MISSING_LOT_SIZE")

    currency = preview.currency
    reject_reasons: list[PaperRejectReason] = []
    if not preview.preview_ready:
        reject_reasons.append(PaperRejectReason.PREVIEW_NOT_READY)
    if isinstance(fill_lots, bool) or fill_lots <= 0:
        reject_reasons.append(PaperRejectReason.INVALID_FILL_LOTS)
    elif fill_lots > requested_lots:
        reject_reasons.append(PaperRejectReason.FILL_EXCEEDS_REQUESTED)

    critical_amounts = (
        preview.initial_order_amount,
        preview.canonical_commission,
        preview.total_order_amount,
    )
    if preview.preview_ready and any(value is None for value in critical_amounts):
        raise PaperSimulatorError("READY_PREVIEW_MISSING_CRITICAL_AMOUNT")

    candidate_gross = Decimal("0")
    candidate_commission = Decimal("0")
    candidate_accrued_interest = Decimal("0")
    candidate_total = Decimal("0")
    if not reject_reasons:
        assert preview.initial_order_amount is not None
        assert preview.canonical_commission is not None
        candidate_gross = _allocated(
            preview.initial_order_amount.amount,
            fill_lots,
            requested_lots,
        )
        candidate_commission = _allocated(
            preview.canonical_commission.amount,
            fill_lots,
            requested_lots,
        )
        if preview.accrued_interest is not None:
            candidate_accrued_interest = _allocated(
                preview.accrued_interest.amount,
                fill_lots,
                requested_lots,
            )
        candidate_total = (
            candidate_gross
            + candidate_commission
            + candidate_accrued_interest
        )
        if candidate_total > cash_before_amount:
            reject_reasons.append(PaperRejectReason.INSUFFICIENT_PAPER_CASH)

    reason_tuple = tuple(reject_reasons)
    cash_before = Money(amount=cash_before_amount, currency=currency)
    journal: tuple[PaperJournalEventV1, ...]
    if reason_tuple:
        status = PaperOrderStatus.REJECTED
        actual_filled_lots = 0
        gross = _zero(currency)
        commission = _zero(currency)
        accrued_interest = _zero(currency)
        total_cost = _zero(currency)
        cash_after = cash_before
        position_after = position_before
        journal = (
            PaperJournalEventV1(
                sequence=1,
                occurred_at=event_time,
                kind=PaperJournalEventKind.REJECTED,
                message=(
                    "Paper purchase rejected without changing simulated cash or position."
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
        gross = Money(amount=candidate_gross, currency=currency)
        commission = Money(amount=candidate_commission, currency=currency)
        accrued_interest = Money(
            amount=candidate_accrued_interest,
            currency=currency,
        )
        total_cost = Money(amount=candidate_total, currency=currency)
        cash_after = Money(
            amount=cash_before_amount - candidate_total,
            currency=currency,
        )
        position_after = position_before + fill_lots
        journal = (
            PaperJournalEventV1(
                sequence=1,
                occurred_at=event_time,
                kind=PaperJournalEventKind.ACCEPTED,
                message="Paper purchase accepted by the offline simulator.",
            ),
            PaperJournalEventV1(
                sequence=2,
                occurred_at=event_time,
                kind=PaperJournalEventKind.FILL,
                message=(
                    f"Paper fill recorded for {fill_lots} of {requested_lots} lots."
                ),
            ),
        )

    return PaperPurchaseResultV1(
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
        gross_amount=gross,
        commission=commission,
        accrued_interest=accrued_interest,
        total_cost=total_cost,
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
