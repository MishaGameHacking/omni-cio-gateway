from __future__ import annotations

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
from omni_cio.contracts.v1.paper import (
    PaperJournalEventKind,
    PaperJournalEventV1,
    PaperOrderStatus,
)


NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), allow_inf_nan=False),
]
NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]


class PaperSaleRejectReason(StrEnum):
    PREVIEW_NOT_READY = "preview_not_ready"
    INVALID_FILL_LOTS = "invalid_fill_lots"
    FILL_EXCEEDS_REQUESTED = "fill_exceeds_requested"
    INSUFFICIENT_PAPER_POSITION = "insufficient_paper_position"
    POSITION_STATE_MISMATCH = "position_state_mismatch"


class PaperSaleResultV1(ContractModel):
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
    reject_reasons: tuple[PaperSaleRejectReason, ...] = ()
    requested_lots: PositiveInt
    filled_lots: NonNegativeInt
    unfilled_lots: NonNegativeInt
    lot_size: PositiveInt
    filled_units: NonNegativeInt
    gross_security_proceeds: Money
    accrued_interest_proceeds: Money
    gross_proceeds: Money
    commission: Money
    estimated_tax: Money
    net_proceeds: Money
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
    def validate_result(self) -> PaperSaleResultV1:
        if self.metadata.schema_name != "paper_sale_result":
            raise ValueError("schema_name must be paper_sale_result")
        if len(self.reject_reasons) != len(set(self.reject_reasons)):
            raise ValueError("paper sale rejection reasons must be unique")
        if self.filled_lots + self.unfilled_lots != self.requested_lots:
            raise ValueError("paper sale filled and unfilled lots must reconcile")
        if self.filled_units != self.filled_lots * self.lot_size:
            raise ValueError("paper sale filled units must equal lots times lot size")

        money_values = (
            self.gross_security_proceeds,
            self.accrued_interest_proceeds,
            self.gross_proceeds,
            self.commission,
            self.estimated_tax,
            self.net_proceeds,
            self.paper_cash_before,
            self.paper_cash_after,
        )
        if any(money.currency != self.currency for money in money_values):
            raise ValueError("paper sale money must use one currency")
        if any(money.amount < 0 for money in money_values):
            raise ValueError("paper sale money cannot be negative")
        if self.gross_proceeds.amount != (
            self.gross_security_proceeds.amount
            + self.accrued_interest_proceeds.amount
        ):
            raise ValueError("paper sale gross proceeds do not reconcile")
        if self.net_proceeds.amount != (
            self.gross_proceeds.amount
            - self.commission.amount
            - self.estimated_tax.amount
        ):
            raise ValueError("paper sale net proceeds do not reconcile")
        if self.paper_cash_after.amount != (
            self.paper_cash_before.amount + self.net_proceeds.amount
        ):
            raise ValueError("paper sale cash does not reconcile")
        if self.position_lots_after != self.position_lots_before - self.filled_lots:
            raise ValueError("paper sale position lots do not reconcile")

        sequences = [event.sequence for event in self.journal]
        if sequences != list(range(1, len(self.journal) + 1)):
            raise ValueError("paper sale journal sequences must be contiguous")

        if self.status == PaperOrderStatus.REJECTED:
            if not self.reject_reasons:
                raise ValueError("rejected paper sale requires a reason")
            if self.filled_lots != 0 or self.net_proceeds.amount != 0:
                raise ValueError("rejected paper sale cannot contain a fill")
            if any(
                money.amount != 0
                for money in (
                    self.gross_security_proceeds,
                    self.accrued_interest_proceeds,
                    self.gross_proceeds,
                    self.commission,
                    self.estimated_tax,
                )
            ):
                raise ValueError("rejected paper sale cannot contain allocated amounts")
            if self.paper_cash_after != self.paper_cash_before:
                raise ValueError("rejected paper sale cannot change cash")
            if self.position_lots_after != self.position_lots_before:
                raise ValueError("rejected paper sale cannot change position")
            if tuple(event.kind for event in self.journal) != (
                PaperJournalEventKind.REJECTED,
            ):
                raise ValueError("rejected paper sale requires one rejection event")
        else:
            if self.reject_reasons:
                raise ValueError("filled paper sale cannot contain rejection reasons")
            if self.filled_lots <= 0:
                raise ValueError("filled paper sale requires positive filled lots")
            if tuple(event.kind for event in self.journal) != (
                PaperJournalEventKind.ACCEPTED,
                PaperJournalEventKind.FILL,
            ):
                raise ValueError("filled paper sale requires accepted and fill events")
            if self.status == PaperOrderStatus.FILLED:
                if self.unfilled_lots != 0:
                    raise ValueError("filled paper sale cannot contain unfilled lots")
            elif self.unfilled_lots <= 0:
                raise ValueError("partial paper sale requires unfilled lots")
        return self
