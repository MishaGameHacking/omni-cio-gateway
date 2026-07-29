from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import (
    ContractMetadata,
    ContractModel,
    CurrencyCode,
    Money,
)


NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), allow_inf_nan=False),
]
NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]


class PaperOrderStatus(StrEnum):
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    REJECTED = "rejected"


class PaperRejectReason(StrEnum):
    PREVIEW_NOT_READY = "preview_not_ready"
    INVALID_FILL_LOTS = "invalid_fill_lots"
    FILL_EXCEEDS_REQUESTED = "fill_exceeds_requested"
    INSUFFICIENT_PAPER_CASH = "insufficient_paper_cash"


class PaperJournalEventKind(StrEnum):
    ACCEPTED = "accepted"
    FILL = "fill"
    REJECTED = "rejected"


class PaperJournalEventV1(ContractModel):
    sequence: PositiveInt
    occurred_at: datetime
    kind: PaperJournalEventKind
    message: Annotated[str, Field(min_length=1, max_length=512)]

    @field_validator("occurred_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("paper event timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)


class PaperPurchaseResultV1(ContractModel):
    metadata: ContractMetadata
    scenario_id: Annotated[
        str,
        Field(pattern=r"^[a-z0-9][a-z0-9_.:-]{2,255}$"),
    ]
    source_preview_schema_version: Annotated[str, Field(min_length=1, max_length=32)]
    stable_key: Annotated[str, Field(min_length=3, max_length=256)]
    instrument_uid: Annotated[str | None, Field(max_length=256)] = None
    currency: CurrencyCode
    status: PaperOrderStatus
    reject_reasons: tuple[PaperRejectReason, ...] = ()
    requested_lots: PositiveInt
    filled_lots: NonNegativeInt
    unfilled_lots: NonNegativeInt
    lot_size: PositiveInt
    filled_units: NonNegativeInt
    gross_amount: Money
    commission: Money
    accrued_interest: Money
    total_cost: Money
    paper_cash_before: Money
    paper_cash_after: Money
    position_lots_before: NonNegativeInt
    position_lots_after: NonNegativeInt
    journal: Annotated[tuple[PaperJournalEventV1, ...], Field(min_length=1)]
    paper_only: Literal[True] = True
    broker_order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_result(self) -> PaperPurchaseResultV1:
        if self.metadata.schema_name != "paper_purchase_result":
            raise ValueError("schema_name must be paper_purchase_result")
        if len(self.reject_reasons) != len(set(self.reject_reasons)):
            raise ValueError("paper rejection reasons must be unique")
        if self.filled_lots + self.unfilled_lots != self.requested_lots:
            raise ValueError("filled and unfilled lots must reconcile")
        if self.filled_units != self.filled_lots * self.lot_size:
            raise ValueError("filled units must equal lots times lot size")

        money_values = (
            self.gross_amount,
            self.commission,
            self.accrued_interest,
            self.total_cost,
            self.paper_cash_before,
            self.paper_cash_after,
        )
        if any(money.currency != self.currency for money in money_values):
            raise ValueError("paper purchase money must use one currency")
        expected_total = (
            self.gross_amount.amount
            + self.commission.amount
            + self.accrued_interest.amount
        )
        if self.total_cost.amount != expected_total:
            raise ValueError("paper total cost does not reconcile")
        if self.paper_cash_after.amount != (
            self.paper_cash_before.amount - self.total_cost.amount
        ):
            raise ValueError("paper cash does not reconcile")
        if self.position_lots_after != self.position_lots_before + self.filled_lots:
            raise ValueError("paper position lots do not reconcile")
        if self.paper_cash_after.amount < 0:
            raise ValueError("paper cash cannot become negative")

        sequences = [event.sequence for event in self.journal]
        if sequences != list(range(1, len(self.journal) + 1)):
            raise ValueError("paper journal sequences must be contiguous")

        if self.status == PaperOrderStatus.REJECTED:
            if not self.reject_reasons:
                raise ValueError("rejected paper result requires a reason")
            if self.filled_lots != 0 or self.total_cost.amount != 0:
                raise ValueError("rejected paper result cannot contain a fill")
            if self.paper_cash_after != self.paper_cash_before:
                raise ValueError("rejected paper result cannot change cash")
            if self.position_lots_after != self.position_lots_before:
                raise ValueError("rejected paper result cannot change position")
            if tuple(event.kind for event in self.journal) != (
                PaperJournalEventKind.REJECTED,
            ):
                raise ValueError("rejected result requires one rejection event")
        else:
            if self.reject_reasons:
                raise ValueError("filled paper result cannot contain rejection reasons")
            if self.filled_lots <= 0:
                raise ValueError("filled paper result requires positive filled lots")
            if tuple(event.kind for event in self.journal) != (
                PaperJournalEventKind.ACCEPTED,
                PaperJournalEventKind.FILL,
            ):
                raise ValueError("filled result requires accepted and fill events")
            if self.status == PaperOrderStatus.FILLED:
                if self.unfilled_lots != 0:
                    raise ValueError("filled result cannot contain unfilled lots")
            elif self.unfilled_lots <= 0:
                raise ValueError("partial fill requires unfilled lots")
        return self
