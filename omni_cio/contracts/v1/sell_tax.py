from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import (
    ContractMetadata,
    ContractModel,
    CurrencyCode,
    Money,
)


PositiveInt = Annotated[int, Field(gt=0)]


class SellTaxEvidenceStatus(StrEnum):
    CONFIRMED = "confirmed"
    UNAVAILABLE = "unavailable"


class SellTaxEvidenceMethod(StrEnum):
    BROKER_CONFIRMED_ESTIMATE = "broker_confirmed_estimate"
    VERIFIED_REPORT_RECONSTRUCTION = "verified_report_reconstruction"
    UNAVAILABLE = "unavailable"


class SellTaxEvidenceV1(ContractModel):
    metadata: ContractMetadata
    stable_key: Annotated[str, Field(min_length=3, max_length=256)]
    instrument_uid: Annotated[str, Field(min_length=1, max_length=256)]
    position_uid: Annotated[str | None, Field(max_length=256)] = None
    currency: CurrencyCode
    lot_size: PositiveInt
    quantity_lots: PositiveInt
    quantity_units: PositiveInt
    gross_proceeds: Money
    canonical_commission: Money
    evidence_status: SellTaxEvidenceStatus
    method: SellTaxEvidenceMethod
    evidence_as_of: datetime
    source_period_start: datetime | None = None
    source_period_end: datetime | None = None
    estimated_tax: Money | None = None
    zero_tax_reason: Annotated[str | None, Field(max_length=512)] = None
    confirmed: bool
    final_tax_liability: Literal[False] = False
    no_legal_tax_guarantee: Literal[True] = True
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("evidence_as_of", "source_period_start", "source_period_end")
    @classmethod
    def require_aware_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("sell-tax evidence timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_evidence(self) -> SellTaxEvidenceV1:
        if self.metadata.schema_name != "sell_tax_evidence":
            raise ValueError("schema_name must be sell_tax_evidence")
        if self.quantity_units != self.lot_size * self.quantity_lots:
            raise ValueError("sell-tax quantity units do not reconcile")
        if self.gross_proceeds.currency != self.currency:
            raise ValueError("sell-tax gross proceeds currency mismatch")
        if self.canonical_commission.currency != self.currency:
            raise ValueError("sell-tax commission currency mismatch")
        if self.canonical_commission.amount < 0:
            raise ValueError("sell-tax commission cannot be negative")
        if self.source_period_start is None != (self.source_period_end is None):
            raise ValueError("sell-tax source period must be complete or absent")
        if (
            self.source_period_start is not None
            and self.source_period_end is not None
            and self.source_period_end < self.source_period_start
        ):
            raise ValueError("sell-tax source period is invalid")
        if (
            self.source_period_end is not None
            and self.evidence_as_of < self.source_period_end
        ):
            raise ValueError("sell-tax evidence cannot predate its source period")

        expected_confirmed = self.evidence_status == SellTaxEvidenceStatus.CONFIRMED
        if self.confirmed != expected_confirmed:
            raise ValueError("sell-tax confirmation must match evidence status")

        if self.confirmed:
            if self.method == SellTaxEvidenceMethod.UNAVAILABLE:
                raise ValueError("confirmed sell-tax evidence requires a method")
            if self.estimated_tax is None:
                raise ValueError("confirmed sell-tax evidence requires estimated tax")
            if self.estimated_tax.currency != self.currency:
                raise ValueError("sell-tax estimated tax currency mismatch")
            if self.estimated_tax.amount < 0:
                raise ValueError("sell-tax estimated tax cannot be negative")
            if self.estimated_tax.amount == 0 and not self.zero_tax_reason:
                raise ValueError("confirmed zero tax requires a verified reason")
            if self.estimated_tax.amount > 0 and self.zero_tax_reason is not None:
                raise ValueError("zero-tax reason is allowed only for zero tax")
            if self.metadata.quality.quality.value != "verified":
                raise ValueError("confirmed sell-tax evidence must be verified")
            if self.metadata.quality.completeness.value != "complete":
                raise ValueError("confirmed sell-tax evidence must be complete")
        else:
            if self.method != SellTaxEvidenceMethod.UNAVAILABLE:
                raise ValueError("unavailable sell-tax evidence requires unavailable method")
            if self.estimated_tax is not None:
                raise ValueError("unavailable sell-tax evidence cannot contain estimated tax")
            if self.zero_tax_reason is not None:
                raise ValueError("unavailable sell-tax evidence cannot contain zero-tax reason")

        return self
