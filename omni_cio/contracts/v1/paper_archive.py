from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel, CurrencyCode
from omni_cio.contracts.v1.paper_ledger import PaperAccountLedgerV1


PositiveInt = Annotated[int, Field(gt=0)]
HexDigest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class PaperLedgerArchiveRecordV1(ContractModel):
    format_version: Literal["1.0"] = "1.0"
    canonicalization: Literal["json-sorted-utf8-v1"] = "json-sorted-utf8-v1"
    digest_algorithm: Literal["sha256"] = "sha256"
    authentication_algorithm: Literal["hmac-sha256"] = "hmac-sha256"
    sequence: PositiveInt
    sealed_at: datetime
    key_id: Annotated[
        str,
        Field(pattern=r"^[a-z0-9][a-z0-9_.:-]{2,127}$"),
    ]
    account_masked_id: Annotated[str, Field(min_length=4, max_length=64)]
    currency: CurrencyCode
    event_count: PositiveInt
    previous_record_digest: HexDigest
    ledger_digest: HexDigest
    record_digest: HexDigest
    authentication_tag: HexDigest
    ledger: PaperAccountLedgerV1
    authenticated: Literal[True] = True
    storage_backend_attached: Literal[False] = False
    paper_only: Literal[True] = True
    broker_order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("sealed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("paper archive timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_record_metadata(self) -> PaperLedgerArchiveRecordV1:
        if self.sealed_at < self.ledger.metadata.retrieved_at:
            raise ValueError("paper archive cannot predate the ledger snapshot")
        if self.account_masked_id != self.ledger.metadata.account.masked_id:
            raise ValueError("paper archive account does not match ledger")
        if self.currency != self.ledger.currency:
            raise ValueError("paper archive currency does not match ledger")
        if self.event_count != len(self.ledger.events):
            raise ValueError("paper archive event count does not match ledger")
        if self.ledger.paper_only is not True:
            raise ValueError("paper archive requires paper-only ledger")
        if self.ledger.broker_order_created is not False:
            raise ValueError("paper archive cannot contain a broker order")
        if self.ledger.execution_ready is not False:
            raise ValueError("paper archive cannot contain execution-ready state")
        if self.ledger.trading_methods is not False:
            raise ValueError("paper archive cannot contain trading methods")
        return self
