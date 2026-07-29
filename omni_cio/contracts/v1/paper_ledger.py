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
from omni_cio.contracts.v1.paper import PaperOrderStatus


NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]


class PaperLedgerSide(StrEnum):
    PURCHASE = "purchase"
    SALE = "sale"


class PaperLedgerPositionV1(ContractModel):
    stable_key: Annotated[str, Field(min_length=3, max_length=256)]
    instrument_uid: Annotated[str | None, Field(max_length=256)] = None
    lot_size: PositiveInt
    lots: PositiveInt


class PaperLedgerEventV1(ContractModel):
    sequence: PositiveInt
    occurred_at: datetime
    scenario_id: Annotated[
        str,
        Field(pattern=r"^[a-z0-9][a-z0-9_.:-]{2,255}$"),
    ]
    side: PaperLedgerSide
    status: PaperOrderStatus
    source_schema: Literal["paper_purchase_result", "paper_sale_result"]
    stable_key: Annotated[str, Field(min_length=3, max_length=256)]
    instrument_uid: Annotated[str | None, Field(max_length=256)] = None
    lot_size: PositiveInt
    requested_lots: PositiveInt
    filled_lots: NonNegativeInt
    cash_before: Money
    cash_after: Money
    position_lots_before: NonNegativeInt
    position_lots_after: NonNegativeInt
    purchase_cost: Money
    sale_net_proceeds: Money
    commission: Money
    estimated_tax: Money
    paper_only: Literal[True] = True
    broker_order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("occurred_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("paper ledger event timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_event(self) -> PaperLedgerEventV1:
        money_values = (
            self.cash_before,
            self.cash_after,
            self.purchase_cost,
            self.sale_net_proceeds,
            self.commission,
            self.estimated_tax,
        )
        currencies = {money.currency for money in money_values}
        if len(currencies) != 1:
            raise ValueError("paper ledger event money must use one currency")
        if any(money.amount < 0 for money in money_values):
            raise ValueError("paper ledger event money cannot be negative")
        if self.filled_lots > self.requested_lots:
            raise ValueError("paper ledger fill cannot exceed requested lots")

        if self.status == PaperOrderStatus.REJECTED:
            if self.filled_lots != 0:
                raise ValueError("rejected paper ledger event cannot contain a fill")
            if any(
                money.amount != 0
                for money in (
                    self.purchase_cost,
                    self.sale_net_proceeds,
                    self.commission,
                    self.estimated_tax,
                )
            ):
                raise ValueError("rejected paper ledger event cannot contain amounts")
            if self.cash_after != self.cash_before:
                raise ValueError("rejected paper ledger event cannot change cash")
            if self.position_lots_after != self.position_lots_before:
                raise ValueError("rejected paper ledger event cannot change position")
            return self

        if self.filled_lots <= 0:
            raise ValueError("filled paper ledger event requires positive filled lots")
        if self.status == PaperOrderStatus.FILLED:
            if self.filled_lots != self.requested_lots:
                raise ValueError("filled paper ledger event must fill requested lots")
        elif self.filled_lots >= self.requested_lots:
            raise ValueError("partial paper ledger event requires unfilled lots")

        if self.side == PaperLedgerSide.PURCHASE:
            if self.source_schema != "paper_purchase_result":
                raise ValueError("purchase event requires purchase result source")
            if self.sale_net_proceeds.amount != 0 or self.estimated_tax.amount != 0:
                raise ValueError("purchase event cannot contain sale proceeds or tax")
            if self.cash_after.amount != (
                self.cash_before.amount - self.purchase_cost.amount
            ):
                raise ValueError("paper purchase ledger cash does not reconcile")
            if self.position_lots_after != (
                self.position_lots_before + self.filled_lots
            ):
                raise ValueError("paper purchase ledger position does not reconcile")
        else:
            if self.source_schema != "paper_sale_result":
                raise ValueError("sale event requires sale result source")
            if self.purchase_cost.amount != 0:
                raise ValueError("sale event cannot contain purchase cost")
            if self.cash_after.amount != (
                self.cash_before.amount + self.sale_net_proceeds.amount
            ):
                raise ValueError("paper sale ledger cash does not reconcile")
            if self.position_lots_after != (
                self.position_lots_before - self.filled_lots
            ):
                raise ValueError("paper sale ledger position does not reconcile")
            if self.position_lots_after < 0:
                raise ValueError("paper sale ledger position cannot be negative")
        return self


class PaperAccountLedgerV1(ContractModel):
    metadata: ContractMetadata
    currency: CurrencyCode
    initial_cash: Money
    final_cash: Money
    initial_positions: Annotated[
        tuple[PaperLedgerPositionV1, ...],
        Field(max_length=256),
    ]
    final_positions: Annotated[
        tuple[PaperLedgerPositionV1, ...],
        Field(max_length=256),
    ]
    events: Annotated[
        tuple[PaperLedgerEventV1, ...],
        Field(min_length=1, max_length=512),
    ]
    scenario_ids: Annotated[
        tuple[Annotated[str, Field(min_length=3, max_length=256)], ...],
        Field(min_length=1, max_length=512),
    ]
    total_purchase_cost: Money
    total_sale_net_proceeds: Money
    total_commission: Money
    total_estimated_tax: Money
    filled_purchase_lots: NonNegativeInt
    filled_sale_lots: NonNegativeInt
    rejected_event_count: NonNegativeInt
    paper_only: Literal[True] = True
    broker_order_created: Literal[False] = False
    no_cross_currency_aggregation: Literal[True] = True
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @staticmethod
    def _position_map(
        positions: tuple[PaperLedgerPositionV1, ...],
        *,
        label: str,
    ) -> dict[str, PaperLedgerPositionV1]:
        keys = [position.stable_key for position in positions]
        if keys != sorted(keys) or len(keys) != len(set(keys)):
            raise ValueError(f"{label} positions must be sorted and unique")
        return {position.stable_key: position for position in positions}

    @model_validator(mode="after")
    def validate_ledger(self) -> PaperAccountLedgerV1:
        if self.metadata.schema_name != "paper_account_ledger":
            raise ValueError("schema_name must be paper_account_ledger")
        money_values = (
            self.initial_cash,
            self.final_cash,
            self.total_purchase_cost,
            self.total_sale_net_proceeds,
            self.total_commission,
            self.total_estimated_tax,
        )
        if any(money.currency != self.currency for money in money_values):
            raise ValueError("paper account ledger money must use one currency")
        if any(money.amount < 0 for money in money_values):
            raise ValueError("paper account ledger money cannot be negative")

        initial = self._position_map(self.initial_positions, label="initial")
        expected_final = self._position_map(self.final_positions, label="final")
        event_sequences = [event.sequence for event in self.events]
        if event_sequences != list(range(1, len(self.events) + 1)):
            raise ValueError("paper ledger event sequences must be contiguous")
        expected_scenario_ids = tuple(event.scenario_id for event in self.events)
        if self.scenario_ids != expected_scenario_ids:
            raise ValueError("paper ledger scenario IDs do not reconcile")
        if len(self.scenario_ids) != len(set(self.scenario_ids)):
            raise ValueError("paper ledger scenario IDs must be unique")
        event_times = [event.occurred_at for event in self.events]
        if event_times != sorted(event_times):
            raise ValueError("paper ledger events must be time ordered")

        current_cash = self.initial_cash.amount
        current_positions: dict[str, PaperLedgerPositionV1] = dict(initial)
        purchase_cost = Decimal("0")
        sale_proceeds = Decimal("0")
        commission = Decimal("0")
        estimated_tax = Decimal("0")
        purchase_lots = 0
        sale_lots = 0
        rejected = 0

        for event in self.events:
            if event.cash_before.currency != self.currency:
                raise ValueError("paper ledger event currency mismatch")
            if event.cash_before.amount != current_cash:
                raise ValueError("paper ledger cash-before state mismatch")
            existing = current_positions.get(event.stable_key)
            expected_lots = existing.lots if existing is not None else 0
            if event.position_lots_before != expected_lots:
                raise ValueError("paper ledger position-before state mismatch")
            if existing is not None:
                if existing.lot_size != event.lot_size:
                    raise ValueError("paper ledger lot size changed")
                if (
                    existing.instrument_uid is not None
                    and event.instrument_uid is not None
                    and existing.instrument_uid != event.instrument_uid
                ):
                    raise ValueError("paper ledger instrument identity changed")

            current_cash = event.cash_after.amount
            if event.position_lots_after == 0:
                current_positions.pop(event.stable_key, None)
            else:
                current_positions[event.stable_key] = PaperLedgerPositionV1(
                    stable_key=event.stable_key,
                    instrument_uid=(
                        event.instrument_uid
                        if event.instrument_uid is not None
                        else existing.instrument_uid if existing is not None else None
                    ),
                    lot_size=event.lot_size,
                    lots=event.position_lots_after,
                )
            purchase_cost += event.purchase_cost.amount
            sale_proceeds += event.sale_net_proceeds.amount
            commission += event.commission.amount
            estimated_tax += event.estimated_tax.amount
            if event.status == PaperOrderStatus.REJECTED:
                rejected += 1
            elif event.side == PaperLedgerSide.PURCHASE:
                purchase_lots += event.filled_lots
            else:
                sale_lots += event.filled_lots

        if self.final_cash.amount != current_cash:
            raise ValueError("paper ledger final cash does not reconcile")
        replayed_final = tuple(
            sorted(current_positions.values(), key=lambda position: position.stable_key)
        )
        if self.final_positions != replayed_final or expected_final != current_positions:
            raise ValueError("paper ledger final positions do not reconcile")
        if self.total_purchase_cost.amount != purchase_cost:
            raise ValueError("paper ledger purchase cost does not reconcile")
        if self.total_sale_net_proceeds.amount != sale_proceeds:
            raise ValueError("paper ledger sale proceeds do not reconcile")
        if self.total_commission.amount != commission:
            raise ValueError("paper ledger commission does not reconcile")
        if self.total_estimated_tax.amount != estimated_tax:
            raise ValueError("paper ledger estimated tax does not reconcile")
        if self.filled_purchase_lots != purchase_lots:
            raise ValueError("paper ledger purchase lots do not reconcile")
        if self.filled_sale_lots != sale_lots:
            raise ValueError("paper ledger sale lots do not reconcile")
        if self.rejected_event_count != rejected:
            raise ValueError("paper ledger rejected count does not reconcile")
        return self
